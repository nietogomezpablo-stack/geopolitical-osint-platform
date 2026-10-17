import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATABASE = ROOT / "data/intelligence.db"

VALID_STATUSES = {
    "pending",
    "supported",
    "contradicted",
    "insufficient",
}

VALID_CHECKS = {
    "source_identified",
    "article_associated",
    "date_mentioned",
    "event_date_verified",
    "location_mentioned",
    "event_location_verified",
    "multiple_domains_identified",
}


def now():
    return datetime.now(timezone.utc).isoformat()


def connect():
    DATABASE.parent.mkdir(parents=True, exist_ok=True)

    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA busy_timeout = 5000")

    return db


def initialize():
    with connect() as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS evidence_audits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                candidate_key TEXT NOT NULL,
                check_code TEXT NOT NULL,
                status TEXT NOT NULL,
                analyst_notes TEXT NOT NULL DEFAULT '',
                source_reference TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL,
                UNIQUE(candidate_key, check_code)
            );

            CREATE TABLE IF NOT EXISTS evidence_audit_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                candidate_key TEXT NOT NULL,
                check_code TEXT NOT NULL,
                previous_status TEXT,
                new_status TEXT NOT NULL,
                previous_notes TEXT,
                new_notes TEXT NOT NULL,
                previous_source_reference TEXT,
                new_source_reference TEXT NOT NULL,
                changed_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_evidence_audit_candidate
            ON evidence_audits(candidate_key);

            CREATE INDEX IF NOT EXISTS idx_evidence_history_candidate
            ON evidence_audit_history(candidate_key);
        """)


def validate(
    candidate_key,
    check_code,
    status,
    notes,
    source_reference,
):
    if not isinstance(candidate_key, str):
        raise ValueError("candidate_key inválido")

    if not candidate_key.strip() or len(candidate_key) > 500:
        raise ValueError("candidate_key inválido")

    if check_code not in VALID_CHECKS:
        raise ValueError("Comprobación desconocida")

    if status not in VALID_STATUSES:
        raise ValueError("Estado desconocido")

    if not isinstance(notes, str) or len(notes) > 10000:
        raise ValueError("Notas inválidas")

    if (
        not isinstance(source_reference, str)
        or len(source_reference) > 2000
    ):
        raise ValueError("Referencia inválida")


def update_audit(
    candidate_key,
    check_code,
    status,
    notes="",
    source_reference="",
):
    validate(
        candidate_key,
        check_code,
        status,
        notes,
        source_reference,
    )

    initialize()

    timestamp = now()

    with connect() as db:
        previous = db.execute("""
            SELECT
                status,
                analyst_notes,
                source_reference
            FROM evidence_audits
            WHERE candidate_key = ?
              AND check_code = ?
        """, (
            candidate_key,
            check_code,
        )).fetchone()

        if previous:
            unchanged = (
                previous["status"] == status
                and previous["analyst_notes"] == notes
                and previous["source_reference"] == source_reference
            )

            if unchanged:
                return {
                    "candidate_key": candidate_key,
                    "check_code": check_code,
                    "status": status,
                    "changed": False,
                }

        db.execute("""
            INSERT INTO evidence_audits (
                candidate_key,
                check_code,
                status,
                analyst_notes,
                source_reference,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(candidate_key, check_code)
            DO UPDATE SET
                status = excluded.status,
                analyst_notes = excluded.analyst_notes,
                source_reference = excluded.source_reference,
                updated_at = excluded.updated_at
        """, (
            candidate_key,
            check_code,
            status,
            notes,
            source_reference,
            timestamp,
        ))

        db.execute("""
            INSERT INTO evidence_audit_history (
                candidate_key,
                check_code,
                previous_status,
                new_status,
                previous_notes,
                new_notes,
                previous_source_reference,
                new_source_reference,
                changed_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            candidate_key,
            check_code,
            previous["status"] if previous else None,
            status,
            previous["analyst_notes"] if previous else None,
            notes,
            previous["source_reference"] if previous else None,
            source_reference,
            timestamp,
        ))

    return {
        "candidate_key": candidate_key,
        "check_code": check_code,
        "status": status,
        "changed": True,
        "updated_at": timestamp,
    }


def list_audits(candidate_key=None):
    initialize()

    with connect() as db:
        if candidate_key:
            rows = db.execute("""
                SELECT *
                FROM evidence_audits
                WHERE candidate_key = ?
                ORDER BY check_code
            """, (candidate_key,)).fetchall()

        else:
            rows = db.execute("""
                SELECT *
                FROM evidence_audits
                ORDER BY updated_at DESC, id DESC
            """).fetchall()

    return {
        "country": "Niger",
        "audits": [dict(row) for row in rows],
    }


def audit_history(candidate_key):
    initialize()

    with connect() as db:
        rows = db.execute("""
            SELECT *
            FROM evidence_audit_history
            WHERE candidate_key = ?
            ORDER BY id DESC
        """, (candidate_key,)).fetchall()

    return {
        "candidate_key": candidate_key,
        "history": [dict(row) for row in rows],
    }


def audit_summary():
    initialize()

    with connect() as db:
        rows = db.execute("""
            SELECT
                status,
                COUNT(*) AS total
            FROM evidence_audits
            GROUP BY status
        """).fetchall()

        candidates = db.execute("""
            SELECT COUNT(DISTINCT candidate_key)
            FROM evidence_audits
        """).fetchone()[0]

    counts = {
        status: 0
        for status in VALID_STATUSES
    }

    for row in rows:
        counts[row["status"]] = row["total"]

    return {
        "country": "Niger",
        "audited_candidates": candidates,
        "status_counts": counts,
        "automatic_event_confirmation": False,
    }


if __name__ == "__main__":
    print(json.dumps(
        audit_summary(),
        ensure_ascii=False,
        indent=2,
    ))
