import json
import sqlite3
import hashlib
from datetime import datetime, timezone
from pathlib import Path

from intelligence_analysis_v5 import build_report

ROOT = Path(__file__).resolve().parents[2]
DB = ROOT / "data/intelligence.db"

ALERT_TYPES = {
    "new_candidate",
    "priority_changed",
    "status_changed",
}


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def connection():
    DB.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    return db


def initialize():
    with connection() as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS intelligence_snapshots (
                candidate_key TEXT PRIMARY KEY,
                priority TEXT NOT NULL,
                investigation_status TEXT NOT NULL,
                first_seen TEXT NOT NULL,
                last_seen TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS intelligence_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fingerprint TEXT NOT NULL UNIQUE,
                candidate_key TEXT NOT NULL,
                alert_type TEXT NOT NULL,
                severity TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                created_at TEXT NOT NULL,
                is_read INTEGER NOT NULL DEFAULT 0
                    CHECK (is_read IN (0, 1))
            );

            CREATE INDEX IF NOT EXISTS idx_alerts_created
            ON intelligence_alerts(created_at DESC);

            CREATE INDEX IF NOT EXISTS idx_alerts_read
            ON intelligence_alerts(is_read);
        """)


def fingerprint(*parts):
    payload = json.dumps(
        parts,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def create_alert(
    db,
    key,
    alert_type,
    severity,
    title,
    description,
    transition,
):
    unique = fingerprint(
        key,
        alert_type,
        transition,
    )

    result = db.execute("""
        INSERT OR IGNORE INTO intelligence_alerts (
            fingerprint,
            candidate_key,
            alert_type,
            severity,
            title,
            description,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        unique,
        key,
        alert_type,
        severity,
        title,
        description,
        timestamp(),
    ))

    return result.rowcount == 1


def synchronize(report=None):
    initialize()

    if report is None:
        report = build_report()

    created = 0
    processed = 0

    with connection() as db:
        for candidate in report.get("candidates", []):
            investigation = candidate.get("investigation") or {}
            analysis = candidate.get("analysis_v5") or {}

            key = investigation.get("candidate_key")
            priority = analysis.get("priority")
            status = investigation.get("status")

            if not key or not priority or not status:
                continue

            processed += 1

            previous = db.execute("""
                SELECT priority, investigation_status
                FROM intelligence_snapshots
                WHERE candidate_key = ?
            """, (key,)).fetchone()

            title = str(
                candidate.get("title") or "Acontecimiento sin título"
            )[:300]

            if previous is None:
                created += create_alert(
                    db,
                    key,
                    "new_candidate",
                    "medium",
                    "Nuevo candidato OSINT",
                    title,
                    "first_seen",
                )

                db.execute("""
                    INSERT INTO intelligence_snapshots (
                        candidate_key,
                        priority,
                        investigation_status,
                        first_seen,
                        last_seen
                    )
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    key,
                    priority,
                    status,
                    timestamp(),
                    timestamp(),
                ))

                continue

            if previous["priority"] != priority:
                transition = (
                    previous["priority"]
                    + "->"
                    + priority
                )

                created += create_alert(
                    db,
                    key,
                    "priority_changed",
                    "high" if priority == "high" else "medium",
                    "Cambio de prioridad",
                    title + " · " + transition,
                    transition,
                )

            if previous["investigation_status"] != status:
                transition = (
                    previous["investigation_status"]
                    + "->"
                    + status
                )

                created += create_alert(
                    db,
                    key,
                    "status_changed",
                    "low",
                    "Cambio de estado de investigación",
                    title + " · " + transition,
                    transition,
                )

            db.execute("""
                UPDATE intelligence_snapshots
                SET priority = ?,
                    investigation_status = ?,
                    last_seen = ?
                WHERE candidate_key = ?
            """, (
                priority,
                status,
                timestamp(),
                key,
            ))

    return {
        "country": "Niger",
        "processed_candidates": processed,
        "new_alerts": created,
    }


def list_alerts(unread_only=False, limit=200):
    initialize()

    limit = max(1, min(int(limit), 500))

    sql = """
        SELECT
            id,
            candidate_key,
            alert_type,
            severity,
            title,
            description,
            created_at,
            is_read
        FROM intelligence_alerts
    """

    if unread_only:
        sql += " WHERE is_read = 0"

    sql += " ORDER BY id DESC LIMIT ?"

    with connection() as db:
        rows = db.execute(sql, (limit,)).fetchall()

        counts = db.execute("""
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN is_read = 0 THEN 1 ELSE 0 END)
                    AS unread
            FROM intelligence_alerts
        """).fetchone()

    return {
        "country": "Niger",
        "total": counts["total"],
        "unread": counts["unread"] or 0,
        "alerts": [dict(row) for row in rows],
    }


def mark_read(alert_id, is_read=True):
    initialize()

    with connection() as db:
        result = db.execute("""
            UPDATE intelligence_alerts
            SET is_read = ?
            WHERE id = ?
        """, (
            1 if is_read else 0,
            alert_id,
        ))

    return result.rowcount == 1


if __name__ == "__main__":
    result = synchronize()
    print("Sincronización:", result)
    print("Alertas:", list_alerts()["total"])
