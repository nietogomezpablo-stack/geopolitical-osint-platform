import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATABASE = ROOT / "data/intelligence.db"

VALID_STATUSES = {
    "pending",
    "in_progress",
    "completed",
    "dismissed",
}

VALID_PRIORITIES = {
    "high",
    "medium",
    "low",
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
            CREATE TABLE IF NOT EXISTS investigation_cases (
                candidate_key TEXT PRIMARY KEY,
                analyst_notes TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS investigation_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                candidate_key TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'pending',
                priority TEXT NOT NULL DEFAULT 'medium',
                source_reference TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(candidate_key)
                    REFERENCES investigation_cases(candidate_key)
            );

            CREATE TABLE IF NOT EXISTS investigation_case_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                candidate_key TEXT NOT NULL,
                action TEXT NOT NULL,
                details_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_case_tasks_candidate
            ON investigation_tasks(candidate_key);

            CREATE INDEX IF NOT EXISTS idx_case_history_candidate
            ON investigation_case_history(candidate_key);
        """)


def validate_key(candidate_key):
    if not isinstance(candidate_key, str):
        raise ValueError("Identificador inválido")

    if not candidate_key.strip() or len(candidate_key) > 500:
        raise ValueError("Identificador inválido")


def record_history(db, key, action, details):
    db.execute("""
        INSERT INTO investigation_case_history (
            candidate_key,
            action,
            details_json,
            created_at
        )
        VALUES (?, ?, ?, ?)
    """, (
        key,
        action,
        json.dumps(
            details,
            ensure_ascii=False,
            default=str,
        ),
        now(),
    ))


def ensure_case(db, candidate_key):
    db.execute("""
        INSERT INTO investigation_cases (
            candidate_key,
            analyst_notes,
            created_at,
            updated_at
        )
        VALUES (?, '', ?, ?)
        ON CONFLICT(candidate_key) DO NOTHING
    """, (
        candidate_key,
        now(),
        now(),
    ))


def update_notes(candidate_key, notes):
    validate_key(candidate_key)

    if not isinstance(notes, str) or len(notes) > 20000:
        raise ValueError("Notas inválidas")

    initialize()

    with connect() as db:
        ensure_case(db, candidate_key)

        previous = db.execute("""
            SELECT analyst_notes
            FROM investigation_cases
            WHERE candidate_key = ?
        """, (candidate_key,)).fetchone()

        if previous["analyst_notes"] == notes:
            return {
                "candidate_key": candidate_key,
                "changed": False,
            }

        db.execute("""
            UPDATE investigation_cases
            SET analyst_notes = ?,
                updated_at = ?
            WHERE candidate_key = ?
        """, (
            notes,
            now(),
            candidate_key,
        ))

        record_history(
            db,
            candidate_key,
            "notes_updated",
            {
                "previous_notes": previous["analyst_notes"],
                "new_notes": notes,
            },
        )

    return {
        "candidate_key": candidate_key,
        "changed": True,
    }


def create_task(
    candidate_key,
    title,
    description="",
    priority="medium",
    source_reference="",
):
    validate_key(candidate_key)

    if not isinstance(title, str):
        raise ValueError("Título inválido")

    if not title.strip() or len(title) > 300:
        raise ValueError("Título inválido")

    if (
        not isinstance(description, str)
        or len(description) > 10000
    ):
        raise ValueError("Descripción inválida")

    if priority not in VALID_PRIORITIES:
        raise ValueError("Prioridad inválida")

    if (
        not isinstance(source_reference, str)
        or len(source_reference) > 2000
    ):
        raise ValueError("Referencia inválida")

    initialize()

    with connect() as db:
        ensure_case(db, candidate_key)

        cursor = db.execute("""
            INSERT INTO investigation_tasks (
                candidate_key,
                title,
                description,
                status,
                priority,
                source_reference,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, 'pending', ?, ?, ?, ?)
        """, (
            candidate_key,
            title,
            description,
            priority,
            source_reference,
            now(),
            now(),
        ))

        task_id = cursor.lastrowid

        record_history(
            db,
            candidate_key,
            "task_created",
            {
                "task_id": task_id,
                "title": title,
                "priority": priority,
            },
        )

    return {
        "id": task_id,
        "candidate_key": candidate_key,
        "status": "pending",
    }


def update_task(
    task_id,
    status=None,
    priority=None,
):
    if status is None and priority is None:
        raise ValueError("No hay cambios solicitados")

    if status is not None and status not in VALID_STATUSES:
        raise ValueError("Estado inválido")

    if priority is not None and priority not in VALID_PRIORITIES:
        raise ValueError("Prioridad inválida")

    initialize()

    with connect() as db:
        previous = db.execute("""
            SELECT *
            FROM investigation_tasks
            WHERE id = ?
        """, (task_id,)).fetchone()

        if previous is None:
            return None

        new_status = status or previous["status"]
        new_priority = priority or previous["priority"]

        if (
            new_status == previous["status"]
            and new_priority == previous["priority"]
        ):
            return {
                "id": task_id,
                "changed": False,
            }

        db.execute("""
            UPDATE investigation_tasks
            SET status = ?,
                priority = ?,
                updated_at = ?
            WHERE id = ?
        """, (
            new_status,
            new_priority,
            now(),
            task_id,
        ))

        record_history(
            db,
            previous["candidate_key"],
            "task_updated",
            {
                "task_id": task_id,
                "previous_status": previous["status"],
                "new_status": new_status,
                "previous_priority": previous["priority"],
                "new_priority": new_priority,
            },
        )

    return {
        "id": task_id,
        "changed": True,
        "status": new_status,
        "priority": new_priority,
    }


def get_case(candidate_key):
    validate_key(candidate_key)
    initialize()

    with connect() as db:
        case = db.execute("""
            SELECT *
            FROM investigation_cases
            WHERE candidate_key = ?
        """, (candidate_key,)).fetchone()

        tasks = db.execute("""
            SELECT *
            FROM investigation_tasks
            WHERE candidate_key = ?
            ORDER BY id DESC
        """, (candidate_key,)).fetchall()

        history = db.execute("""
            SELECT *
            FROM investigation_case_history
            WHERE candidate_key = ?
            ORDER BY id DESC
            LIMIT 100
        """, (candidate_key,)).fetchall()

    return {
        "candidate_key": candidate_key,
        "case": dict(case) if case else None,
        "tasks": [dict(row) for row in tasks],
        "history": [
            {
                **dict(row),
                "details": json.loads(row["details_json"]),
            }
            for row in history
        ],
    }


def list_cases(limit=100):
    initialize()

    limit = max(1, min(int(limit), 500))

    with connect() as db:
        rows = db.execute("""
            SELECT
                c.candidate_key,
                c.analyst_notes,
                c.created_at,
                c.updated_at,
                COUNT(t.id) AS total_tasks,
                SUM(
                    CASE
                        WHEN t.status = 'pending'
                        THEN 1 ELSE 0
                    END
                ) AS pending_tasks,
                SUM(
                    CASE
                        WHEN t.status = 'completed'
                        THEN 1 ELSE 0
                    END
                ) AS completed_tasks
            FROM investigation_cases c
            LEFT JOIN investigation_tasks t
              ON t.candidate_key = c.candidate_key
            GROUP BY c.candidate_key
            ORDER BY c.updated_at DESC
            LIMIT ?
        """, (limit,)).fetchall()

    return {
        "country": "Niger",
        "cases": [dict(row) for row in rows],
    }


def summary():
    initialize()

    with connect() as db:
        cases = db.execute("""
            SELECT COUNT(*)
            FROM investigation_cases
        """).fetchone()[0]

        rows = db.execute("""
            SELECT status, COUNT(*) AS total
            FROM investigation_tasks
            GROUP BY status
        """).fetchall()

    counts = {
        status: 0
        for status in VALID_STATUSES
    }

    for row in rows:
        counts[row["status"]] = row["total"]

    return {
        "country": "Niger",
        "total_cases": cases,
        "task_status_counts": counts,
        "automatic_event_confirmation": False,
    }


if __name__ == "__main__":
    print(json.dumps(
        summary(),
        ensure_ascii=False,
        indent=2,
    ))
