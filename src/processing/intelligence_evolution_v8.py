import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from intelligence_analysis_v5 import build_report

ROOT = Path(__file__).resolve().parents[2]
DATABASE = ROOT / "data/intelligence.db"

# Campos de información de fuentes, no decisiones del analista.
TRACKED_FIELDS = (
    "title",
    "event_type",
    "article_ids",
    "evidence",
    "locations",
    "date_mentions",
    "source_urls",
)


def now():
    return datetime.now(timezone.utc).isoformat()


def connect():
    DATABASE.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    return db


def initialize():
    with connect() as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS candidate_versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                candidate_key TEXT NOT NULL,
                version_number INTEGER NOT NULL,
                content_hash TEXT NOT NULL,
                snapshot_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(candidate_key, version_number)
            );

            CREATE INDEX IF NOT EXISTS idx_candidate_versions_key
            ON candidate_versions(candidate_key);

            CREATE TABLE IF NOT EXISTS candidate_presence (
                candidate_key TEXT PRIMARY KEY,
                first_seen TEXT NOT NULL,
                last_seen TEXT NOT NULL,
                is_present INTEGER NOT NULL DEFAULT 1
                    CHECK(is_present IN (0, 1))
            );

            CREATE TABLE IF NOT EXISTS candidate_evolution_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                candidate_key TEXT NOT NULL,
                event_type TEXT NOT NULL,
                details_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_evolution_events_key
            ON candidate_evolution_events(candidate_key);
        """)


def canonical(value):
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def snapshot(candidate):
    analysis = candidate.get("analysis_v5") or {}

    return {
        "title": candidate.get("title"),
        "event_type": candidate.get("event_type"),
        "article_ids": analysis.get("article_ids", []),
        "evidence": candidate.get("evidence"),
        "locations": candidate.get("locations"),
        "date_mentions": candidate.get("date_mentions"),
        "source_urls": analysis.get("sources", {}).get("urls", []),
    }


def content_hash(data):
    return hashlib.sha256(
        canonical(data).encode("utf-8")
    ).hexdigest()


def differences(previous, current):
    changes = {}

    for field in TRACKED_FIELDS:
        before = previous.get(field)
        after = current.get(field)

        if canonical(before) != canonical(after):
            changes[field] = {
                "before": before,
                "after": after,
            }

    return changes


def record_event(db, key, event_type, details):
    db.execute("""
        INSERT INTO candidate_evolution_events (
            candidate_key,
            event_type,
            details_json,
            created_at
        )
        VALUES (?, ?, ?, ?)
    """, (
        key,
        event_type,
        canonical(details),
        now(),
    ))


def synchronize(report=None):
    initialize()

    if report is None:
        report = build_report()

    candidates = report.get("candidates", [])
    current_keys = set()

    result = {
        "country": "Niger",
        "processed": 0,
        "new_candidates": 0,
        "updated_candidates": 0,
        "unchanged_candidates": 0,
        "disappeared_candidates": 0,
        "reappeared_candidates": 0,
    }

    with connect() as db:
        for candidate in candidates:
            investigation = candidate.get("investigation") or {}
            key = investigation.get("candidate_key")

            if not key:
                continue

            current_keys.add(key)
            result["processed"] += 1

            data = snapshot(candidate)
            digest = content_hash(data)

            latest = db.execute("""
                SELECT
                    version_number,
                    content_hash,
                    snapshot_json
                FROM candidate_versions
                WHERE candidate_key = ?
                ORDER BY version_number DESC
                LIMIT 1
            """, (key,)).fetchone()

            presence = db.execute("""
                SELECT is_present
                FROM candidate_presence
                WHERE candidate_key = ?
            """, (key,)).fetchone()

            if latest is None:
                db.execute("""
                    INSERT INTO candidate_versions (
                        candidate_key,
                        version_number,
                        content_hash,
                        snapshot_json,
                        created_at
                    )
                    VALUES (?, 1, ?, ?, ?)
                """, (
                    key,
                    digest,
                    canonical(data),
                    now(),
                ))

                record_event(
                    db,
                    key,
                    "candidate_discovered",
                    {"version": 1},
                )

                result["new_candidates"] += 1

            elif latest["content_hash"] != digest:
                previous = json.loads(
                    latest["snapshot_json"]
                )

                changes = differences(previous, data)
                version = latest["version_number"] + 1

                db.execute("""
                    INSERT INTO candidate_versions (
                        candidate_key,
                        version_number,
                        content_hash,
                        snapshot_json,
                        created_at
                    )
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    key,
                    version,
                    digest,
                    canonical(data),
                    now(),
                ))

                record_event(
                    db,
                    key,
                    "candidate_information_updated",
                    {
                        "version": version,
                        "changes": changes,
                    },
                )

                result["updated_candidates"] += 1

            else:
                result["unchanged_candidates"] += 1

            if presence and not presence["is_present"]:
                record_event(
                    db,
                    key,
                    "candidate_reappeared",
                    {},
                )
                result["reappeared_candidates"] += 1

            db.execute("""
                INSERT INTO candidate_presence (
                    candidate_key,
                    first_seen,
                    last_seen,
                    is_present
                )
                VALUES (?, ?, ?, 1)
                ON CONFLICT(candidate_key)
                DO UPDATE SET
                    last_seen = excluded.last_seen,
                    is_present = 1
            """, (
                key,
                now(),
                now(),
            ))

        # Si el conjunto actual está vacío, no declaramos
        # desaparecidos: podría ser un fallo del pipeline.
        if current_keys:
            rows = db.execute("""
                SELECT candidate_key
                FROM candidate_presence
                WHERE is_present = 1
            """).fetchall()

            for row in rows:
                key = row["candidate_key"]

                if key in current_keys:
                    continue

                db.execute("""
                    UPDATE candidate_presence
                    SET is_present = 0
                    WHERE candidate_key = ?
                """, (key,))

                record_event(
                    db,
                    key,
                    "candidate_absent_from_latest_dataset",
                    {},
                )

                result["disappeared_candidates"] += 1

    return result


def list_evolution(limit=100):
    initialize()
    limit = max(1, min(int(limit), 500))

    with connect() as db:
        rows = db.execute("""
            SELECT
                id,
                candidate_key,
                event_type,
                details_json,
                created_at
            FROM candidate_evolution_events
            ORDER BY id DESC
            LIMIT ?
        """, (limit,)).fetchall()

    return {
        "country": "Niger",
        "events": [
            {
                **dict(row),
                "details": json.loads(row["details_json"]),
            }
            for row in rows
        ],
    }


def candidate_history(key):
    initialize()

    with connect() as db:
        versions = db.execute("""
            SELECT
                version_number,
                snapshot_json,
                created_at
            FROM candidate_versions
            WHERE candidate_key = ?
            ORDER BY version_number DESC
        """, (key,)).fetchall()

        events = db.execute("""
            SELECT
                event_type,
                details_json,
                created_at
            FROM candidate_evolution_events
            WHERE candidate_key = ?
            ORDER BY id DESC
        """, (key,)).fetchall()

    return {
        "candidate_key": key,
        "versions": [
            {
                "version": row["version_number"],
                "snapshot": json.loads(row["snapshot_json"]),
                "created_at": row["created_at"],
            }
            for row in versions
        ],
        "events": [
            {
                "event_type": row["event_type"],
                "details": json.loads(row["details_json"]),
                "created_at": row["created_at"],
            }
            for row in events
        ],
    }


if __name__ == "__main__":
    print("Sincronización V8:", synchronize())
    print("Eventos registrados:", len(list_evolution()["events"]))
