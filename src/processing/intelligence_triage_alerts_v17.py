import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATABASE = ROOT / "data/intelligence.db"

ALERT_TYPES = {
    "critical_priority",
    "high_priority",
    "contradicted_evidence",
    "high_priority_tasks",
    "insufficient_documentation",
}


def now():
    return datetime.now(timezone.utc).isoformat()


def connect(database=None):
    path = Path(database) if database else DATABASE

    path.parent.mkdir(parents=True, exist_ok=True)

    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA busy_timeout = 5000")

    return db


def initialize(database=None):
    with connect(database) as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS triage_alerts_v17 (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                candidate_key TEXT NOT NULL,
                alert_type TEXT NOT NULL,
                severity TEXT NOT NULL,
                message TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                is_read INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                resolved_at TEXT,
                UNIQUE(candidate_key, alert_type)
            );

            CREATE INDEX IF NOT EXISTS idx_triage_alerts_v17_status
            ON triage_alerts_v17(status);

            CREATE INDEX IF NOT EXISTS idx_triage_alerts_v17_candidate
            ON triage_alerts_v17(candidate_key);
        """)


def build_alerts(triage_report):
    alerts = []

    for candidate in triage_report.get("candidates", []):
        key = candidate.get("candidate_key")

        if not key:
            continue

        priority = candidate.get(
            "triage_priority",
            "low",
        )

        if priority == "critical":
            alerts.append({
                "candidate_key": key,
                "alert_type": "critical_priority",
                "severity": "critical",
                "message": (
                    "La investigación presenta prioridad crítica."
                ),
            })

        elif priority == "high":
            alerts.append({
                "candidate_key": key,
                "alert_type": "high_priority",
                "severity": "high",
                "message": (
                    "La investigación presenta prioridad alta."
                ),
            })

        contradicted = candidate.get(
            "contradicted_checks",
            0,
        )

        if contradicted > 0:
            alerts.append({
                "candidate_key": key,
                "alert_type": "contradicted_evidence",
                "severity": "high",
                "message": (
                    f"Existen {contradicted} comprobaciones "
                    "con evidencias contradictorias."
                ),
            })

        reasons = {
            reason.get("code")
            for reason in candidate.get("reasons", [])
        }

        if "high_priority_task" in reasons:
            alerts.append({
                "candidate_key": key,
                "alert_type": "high_priority_tasks",
                "severity": "medium",
                "message": (
                    "Existen tareas abiertas de prioridad alta."
                ),
            })

        if (
            "insufficient_evidence" in reasons
            or "missing_documentation" in reasons
        ):
            alerts.append({
                "candidate_key": key,
                "alert_type": "insufficient_documentation",
                "severity": "medium",
                "message": (
                    "La investigación necesita comprobaciones "
                    "documentales adicionales."
                ),
            })

    return alerts


def synchronize(triage_report=None, database=None):
    if triage_report is None:
        from intelligence_triage_v16 import analyze
        triage_report = analyze()

    # Si la verificación falló, no cerramos alertas basándonos
    # en información potencialmente incompleta.
    if triage_report.get("verification_error"):
        raise RuntimeError(
            "No se sincronizan alertas porque la "
            "verificación documental está incompleta: "
            + str(triage_report["verification_error"])
        )

    initialize(database)

    generated = build_alerts(triage_report)

    active_keys = {
        (item["candidate_key"], item["alert_type"])
        for item in generated
    }

    created = 0
    updated = 0
    resolved = 0

    timestamp = now()

    with connect(database) as db:
        for item in generated:
            previous = db.execute("""
                SELECT *
                FROM triage_alerts_v17
                WHERE candidate_key = ?
                  AND alert_type = ?
            """, (
                item["candidate_key"],
                item["alert_type"],
            )).fetchone()

            if previous is None:
                db.execute("""
                    INSERT INTO triage_alerts_v17 (
                        candidate_key,
                        alert_type,
                        severity,
                        message,
                        status,
                        is_read,
                        created_at,
                        updated_at
                    )
                    VALUES (?, ?, ?, ?, 'active', 0, ?, ?)
                """, (
                    item["candidate_key"],
                    item["alert_type"],
                    item["severity"],
                    item["message"],
                    timestamp,
                    timestamp,
                ))

                created += 1

            elif (
                previous["status"] != "active"
                or previous["severity"] != item["severity"]
                or previous["message"] != item["message"]
            ):
                db.execute("""
                    UPDATE triage_alerts_v17
                    SET
                        severity = ?,
                        message = ?,
                        status = 'active',
                        is_read = 0,
                        updated_at = ?,
                        resolved_at = NULL
                    WHERE id = ?
                """, (
                    item["severity"],
                    item["message"],
                    timestamp,
                    previous["id"],
                ))

                updated += 1

        existing = db.execute("""
            SELECT
                id,
                candidate_key,
                alert_type
            FROM triage_alerts_v17
            WHERE status = 'active'
        """).fetchall()

        for row in existing:
            key = (
                row["candidate_key"],
                row["alert_type"],
            )

            if key not in active_keys:
                db.execute("""
                    UPDATE triage_alerts_v17
                    SET
                        status = 'resolved',
                        resolved_at = ?,
                        updated_at = ?
                    WHERE id = ?
                """, (
                    timestamp,
                    timestamp,
                    row["id"],
                ))

                resolved += 1

    return {
        "country": "Niger",
        "generated_conditions": len(generated),
        "created": created,
        "updated": updated,
        "resolved": resolved,
    }


def list_alerts(status="active", limit=100, database=None):
    initialize(database)

    if status not in ("active", "resolved", "all"):
        raise ValueError("Estado de filtro inválido")

    limit = max(1, min(int(limit), 500))

    with connect(database) as db:
        if status == "all":
            rows = db.execute("""
                SELECT *
                FROM triage_alerts_v17
                ORDER BY
                    CASE severity
                        WHEN 'critical' THEN 0
                        WHEN 'high' THEN 1
                        ELSE 2
                    END,
                    updated_at DESC,
                    id DESC
                LIMIT ?
            """, (limit,)).fetchall()

        else:
            rows = db.execute("""
                SELECT *
                FROM triage_alerts_v17
                WHERE status = ?
                ORDER BY
                    CASE severity
                        WHEN 'critical' THEN 0
                        WHEN 'high' THEN 1
                        ELSE 2
                    END,
                    updated_at DESC,
                    id DESC
                LIMIT ?
            """, (
                status,
                limit,
            )).fetchall()

    return {
        "country": "Niger",
        "alerts": [dict(row) for row in rows],
    }


def mark_read(alert_id, database=None):
    initialize(database)

    with connect(database) as db:
        cursor = db.execute("""
            UPDATE triage_alerts_v17
            SET is_read = 1
            WHERE id = ?
        """, (alert_id,))

        if cursor.rowcount == 0:
            return None

    return {
        "id": alert_id,
        "is_read": True,
    }


def summary(database=None):
    initialize(database)

    with connect(database) as db:
        rows = db.execute("""
            SELECT
                status,
                severity,
                COUNT(*) AS total
            FROM triage_alerts_v17
            GROUP BY status, severity
        """).fetchall()

        unread = db.execute("""
            SELECT COUNT(*)
            FROM triage_alerts_v17
            WHERE status = 'active'
              AND is_read = 0
        """).fetchone()[0]

    counts = {
        "active": 0,
        "resolved": 0,
        "critical": 0,
        "high": 0,
        "medium": 0,
    }

    for row in rows:
        counts[row["status"]] += row["total"]

        if row["status"] == "active":
            counts[row["severity"]] += row["total"]

    return {
        "country": "Niger",
        "counts": counts,
        "unread_active": unread,
        "automatic_event_confirmation": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--sync",
        action="store_true",
    )

    parser.add_argument(
        "--status",
        action="store_true",
    )

    arguments = parser.parse_args()

    if arguments.sync:
        result = synchronize()
    else:
        result = summary()

    print(json.dumps(
        result,
        ensure_ascii=False,
        indent=2,
    ))
