import argparse
import fcntl
import json
import os
import sqlite3
import sys
import time
import traceback
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATABASE = ROOT / "data/intelligence.db"
LOCK_FILE = ROOT / "data/meridian_orchestrator.lock"

STEPS = (
    "candidate_analysis",
    "alert_synchronization",
    "evolution_synchronization",
    "report_generation",
)


def now():
    return datetime.now(timezone.utc).isoformat()


def connect():
    DATABASE.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA busy_timeout = 5000")

    return connection


def initialize():
    with connect() as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS pipeline_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                status TEXT NOT NULL,
                duration_seconds REAL,
                results_json TEXT,
                error_message TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_pipeline_runs_started
            ON pipeline_runs(started_at DESC);
        """)


@contextmanager
def execution_lock():
    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)

    with open(LOCK_FILE, "a+") as lock:
        try:
            fcntl.flock(
                lock.fileno(),
                fcntl.LOCK_EX | fcntl.LOCK_NB,
            )
        except BlockingIOError:
            raise RuntimeError(
                "Ya existe una ejecución de Meridian en curso"
            )

        try:
            yield
        finally:
            fcntl.flock(
                lock.fileno(),
                fcntl.LOCK_UN,
            )


def create_run():
    initialize()

    with connect() as db:
        cursor = db.execute("""
            INSERT INTO pipeline_runs (
                started_at,
                status
            )
            VALUES (?, 'running')
        """, (now(),))

        return cursor.lastrowid


def finish_run(
    run_id,
    status,
    duration,
    results,
    error=None,
):
    with connect() as db:
        db.execute("""
            UPDATE pipeline_runs
            SET
                finished_at = ?,
                status = ?,
                duration_seconds = ?,
                results_json = ?,
                error_message = ?
            WHERE id = ?
        """, (
            now(),
            status,
            round(duration, 3),
            json.dumps(
                results,
                ensure_ascii=False,
                default=str,
            ),
            error,
            run_id,
        ))


def run_steps():
    from intelligence_analysis_v5 import (
        build_report,
        export_json,
    )

    from intelligence_alerts_v6 import (
        synchronize as synchronize_alerts,
    )

    from intelligence_evolution_v8 import (
        synchronize as synchronize_evolution,
    )

    from intelligence_reports_v9 import save_report

    results = {}

    # Una única fotografía lógica de los candidatos.
    report = build_report()

    export_path = export_json()

    results["candidate_analysis"] = {
        "candidates": len(report.get("candidates", [])),
        "export": str(export_path),
    }

    results["alert_synchronization"] = (
        synchronize_alerts(report=report)
    )

    results["evolution_synchronization"] = (
        synchronize_evolution(report=report)
    )

    results["report_generation"] = save_report()

    return results


def execute():
    with execution_lock():
        run_id = create_run()
        start = time.monotonic()
        results = {}

        try:
            results = run_steps()

        except Exception as error:
            duration = time.monotonic() - start

            finish_run(
                run_id,
                "failed",
                duration,
                results,
                str(error),
            )

            return {
                "run_id": run_id,
                "status": "failed",
                "error": str(error),
            }

        duration = time.monotonic() - start

        finish_run(
            run_id,
            "completed",
            duration,
            results,
        )

        return {
            "run_id": run_id,
            "status": "completed",
            "duration_seconds": round(duration, 3),
            "results": results,
        }


def list_runs(limit=30):
    initialize()

    limit = max(1, min(int(limit), 200))

    with connect() as db:
        rows = db.execute("""
            SELECT
                id,
                started_at,
                finished_at,
                status,
                duration_seconds,
                results_json,
                error_message
            FROM pipeline_runs
            ORDER BY id DESC
            LIMIT ?
        """, (limit,)).fetchall()

    runs = []

    for row in rows:
        item = dict(row)

        item["results"] = (
            json.loads(item.pop("results_json"))
            if item["results_json"]
            else {}
        )

        runs.append(item)

    return {
        "country": "Niger",
        "runs": runs,
    }


def operational_status():
    initialize()

    with connect() as db:
        row = db.execute("""
            SELECT
                COUNT(*) AS total,
                SUM(
                    CASE WHEN status = 'completed'
                    THEN 1 ELSE 0 END
                ) AS completed,
                SUM(
                    CASE WHEN status = 'failed'
                    THEN 1 ELSE 0 END
                ) AS failed
            FROM pipeline_runs
        """).fetchone()

    return {
        "country": "Niger",
        "total_runs": row["total"],
        "completed_runs": row["completed"] or 0,
        "failed_runs": row["failed"] or 0,
        "available_steps": list(STEPS),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--run",
        action="store_true",
        help="Ejecutar el análisis completo",
    )

    parser.add_argument(
        "--status",
        action="store_true",
        help="Mostrar estadísticas de ejecución",
    )

    arguments = parser.parse_args()

    if arguments.run:
        result = execute()

        print(json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
        ))

        if result["status"] != "completed":
            sys.exit(1)

    else:
        print(json.dumps(
            operational_status(),
            ensure_ascii=False,
            indent=2,
        ))
