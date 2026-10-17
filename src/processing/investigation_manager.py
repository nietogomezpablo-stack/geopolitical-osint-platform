import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATABASE = ROOT / "data/intelligence.db"
CANDIDATES = ROOT / "data/processed/event_intelligence_v4.json"

STATUSES = {
    "pending",
    "investigating",
    "reviewed",
    "dismissed",
}


def connect():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize():
    with connect() as connection:
        connection.executescript("""
            CREATE TABLE IF NOT EXISTS investigations (
                candidate_key TEXT PRIMARY KEY,
                status TEXT NOT NULL DEFAULT 'pending',
                notes TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL,
                CHECK (
                    status IN (
                        'pending',
                        'investigating',
                        'reviewed',
                        'dismissed'
                    )
                )
            );

            CREATE TABLE IF NOT EXISTS investigation_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                candidate_key TEXT NOT NULL,
                previous_status TEXT,
                new_status TEXT NOT NULL,
                notes TEXT NOT NULL,
                changed_at TEXT NOT NULL,
                FOREIGN KEY(candidate_key)
                    REFERENCES investigations(candidate_key)
            );

            CREATE INDEX IF NOT EXISTS
                idx_investigation_history_candidate
            ON investigation_history(candidate_key);
        """)


def now():
    return datetime.now(timezone.utc).isoformat()


def candidate_key(candidate):
    # Clave basada en el tipo y los artículos originales.
    # No depende del orden de la lista ni del título.
    article_ids = candidate.get("article_ids") or [
        candidate["article_id"]
    ]

    return (
        candidate["event_type"]
        + ":"
        + ",".join(
            str(value)
            for value in sorted(set(article_ids))
        )
    )


def get_candidates():
    if not CANDIDATES.exists():
        return []

    report = json.loads(
        CANDIDATES.read_text(encoding="utf-8")
    )

    return report.get("candidates", [])


def valid_candidate_keys():
    return {
        candidate_key(candidate)
        for candidate in get_candidates()
    }


def list_investigations():
    initialize()

    candidates = get_candidates()

    with connect() as connection:
        rows = connection.execute("""
            SELECT candidate_key, status, notes, updated_at
            FROM investigations
        """).fetchall()

    saved = {
        row["candidate_key"]: dict(row)
        for row in rows
    }

    results = []

    for candidate in candidates:
        key = candidate_key(candidate)

        investigation = saved.get(key, {
            "candidate_key": key,
            "status": "pending",
            "notes": "",
            "updated_at": None,
        })

        results.append({
            **candidate,
            "investigation": investigation,
        })

    return results


def update_investigation(key, status, notes):
    if status not in STATUSES:
        raise ValueError("Estado de investigación inválido")

    if not isinstance(notes, str):
        raise ValueError("Las notas deben ser texto")

    if len(notes) > 10000:
        raise ValueError("Las notas superan 10000 caracteres")

    if key not in valid_candidate_keys():
        raise ValueError("El candidato no existe")

    initialize()

    timestamp = now()

    with connect() as connection:
        previous = connection.execute("""
            SELECT status, notes
            FROM investigations
            WHERE candidate_key = ?
        """, (key,)).fetchone()

        old_status = previous["status"] if previous else None
        old_notes = previous["notes"] if previous else None

        if (
            old_status == status
            and old_notes == notes
        ):
            return {
                "candidate_key": key,
                "status": status,
                "notes": notes,
                "updated_at": timestamp,
                "changed": False,
            }

        connection.execute("""
            INSERT INTO investigations (
                candidate_key,
                status,
                notes,
                updated_at
            )
            VALUES (?, ?, ?, ?)
            ON CONFLICT(candidate_key)
            DO UPDATE SET
                status = excluded.status,
                notes = excluded.notes,
                updated_at = excluded.updated_at
        """, (key, status, notes, timestamp))

        connection.execute("""
            INSERT INTO investigation_history (
                candidate_key,
                previous_status,
                new_status,
                notes,
                changed_at
            )
            VALUES (?, ?, ?, ?, ?)
        """, (
            key,
            old_status,
            status,
            notes,
            timestamp,
        ))

    return {
        "candidate_key": key,
        "status": status,
        "notes": notes,
        "updated_at": timestamp,
        "changed": True,
    }


def get_history(key):
    initialize()

    if key not in valid_candidate_keys():
        raise ValueError("El candidato no existe")

    with connect() as connection:
        rows = connection.execute("""
            SELECT
                previous_status,
                new_status,
                notes,
                changed_at
            FROM investigation_history
            WHERE candidate_key = ?
            ORDER BY id DESC
        """, (key,)).fetchall()

    return [dict(row) for row in rows]


if __name__ == "__main__":
    initialize()

    print("Base de datos de investigaciones preparada.")
    print("Candidatos:", len(get_candidates()))
    print("Investigaciones:", len(list_investigations()))
