import argparse
import json
import os
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from intelligence_orchestrator_v10 import (
    execute as execute_intelligence,
    execution_lock,
)

ROOT = Path(__file__).resolve().parents[2]
DATABASE = ROOT / "data/intelligence.db"
PIPELINE = ROOT / "run_pipeline.py"

# El bloqueo de V11 es independiente del de V10:
# V11 conserva su bloqueo mientras ejecuta V10.
LOCK_FILE = ROOT / "data/meridian_full_pipeline.lock"

MAX_LOG_CHARS = 30000


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
            CREATE TABLE IF NOT EXISTS full_pipeline_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                status TEXT NOT NULL,
                duration_seconds REAL,
                collection_returncode INTEGER,
                collection_output TEXT,
                intelligence_result_json TEXT,
                error_message TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_full_pipeline_runs
            ON full_pipeline_runs(started_at DESC);
        """)


def plan():
    return {
        "country": "Niger",
        "mode": "full_update",
        "collection_script": str(PIPELINE),
        "steps": [
            {
                "step": 1,
                "name": "Recopilación y procesamiento",
                "script": "run_pipeline.py",
            },
            {
                "step": 2,
                "name": "Análisis de candidatos",
                "engine": "V10",
            },
            {
                "step": 3,
                "name": "Sincronización de alertas",
                "engine": "V6",
            },
            {
                "step": 4,
                "name": "Registro de evolución",
                "engine": "V8",
            },
            {
                "step": 5,
                "name": "Informe de inteligencia",
                "engine": "V9",
            },
        ],
        "automatic_event_confirmation": False,
    }


def execute_collection(timeout=900):
    if not PIPELINE.is_file():
        raise FileNotFoundError(
            f"No existe el pipeline: {PIPELINE}"
        )

    process = subprocess.run(
        [sys.executable, str(PIPELINE)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
        env={
            **os.environ,
            "PYTHONUNBUFFERED": "1",
        },
    )

    combined_output = (
        process.stdout
        + "\n"
        + process.stderr
    )

    return {
        "returncode": process.returncode,
        "output": combined_output[-MAX_LOG_CHARS:],
    }


def execute_full_update(
    dry_run=False,
    timeout=900,
):
    if dry_run:
        return {
            "status": "dry_run",
            "plan": plan(),
        }

    initialize()

    # Se utiliza un bloqueo propio para impedir
    # dos actualizaciones completas simultáneas.
    import fcntl

    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)

    with open(LOCK_FILE, "a+") as lock:
        try:
            fcntl.flock(
                lock.fileno(),
                fcntl.LOCK_EX | fcntl.LOCK_NB,
            )

        except BlockingIOError:
            raise RuntimeError(
                "Ya hay una actualización completa en curso"
            )

        start = time.monotonic()

        with connect() as db:
            cursor = db.execute("""
                INSERT INTO full_pipeline_runs (
                    started_at,
                    status
                )
                VALUES (?, 'running')
            """, (now(),))

            run_id = cursor.lastrowid

        collection = None
        intelligence = None
        error = None
        status = "failed"

        try:
            collection = execute_collection(timeout=timeout)

            if collection["returncode"] != 0:
                raise RuntimeError(
                    "La recopilación terminó con código "
                    + str(collection["returncode"])
                )

            intelligence = execute_intelligence()

            if intelligence["status"] != "completed":
                raise RuntimeError(
                    intelligence.get(
                        "error",
                        "Falló el análisis de inteligencia",
                    )
                )

            status = "completed"

        except subprocess.TimeoutExpired:
            error = (
                "La recopilación superó el tiempo máximo "
                "permitido"
            )

        except Exception as exception:
            error = str(exception)

        duration = time.monotonic() - start

        with connect() as db:
            db.execute("""
                UPDATE full_pipeline_runs
                SET
                    finished_at = ?,
                    status = ?,
                    duration_seconds = ?,
                    collection_returncode = ?,
                    collection_output = ?,
                    intelligence_result_json = ?,
                    error_message = ?
                WHERE id = ?
            """, (
                now(),
                status,
                round(duration, 3),
                (
                    collection["returncode"]
                    if collection else None
                ),
                (
                    collection["output"]
                    if collection else None
                ),
                (
                    json.dumps(
                        intelligence,
                        ensure_ascii=False,
                        default=str,
                    )
                    if intelligence else None
                ),
                error,
                run_id,
            ))

        fcntl.flock(
            lock.fileno(),
            fcntl.LOCK_UN,
        )

        return {
            "run_id": run_id,
            "status": status,
            "duration_seconds": round(duration, 3),
            "collection": collection,
            "intelligence": intelligence,
            "error": error,
        }


def list_runs(limit=30):
    initialize()

    limit = max(1, min(int(limit), 100))

    with connect() as db:
        rows = db.execute("""
            SELECT
                id,
                started_at,
                finished_at,
                status,
                duration_seconds,
                collection_returncode,
                error_message
            FROM full_pipeline_runs
            ORDER BY id DESC
            LIMIT ?
        """, (limit,)).fetchall()

    return {
        "country": "Niger",
        "runs": [dict(row) for row in rows],
    }


def get_run(run_id):
    initialize()

    with connect() as db:
        row = db.execute("""
            SELECT *
            FROM full_pipeline_runs
            WHERE id = ?
        """, (run_id,)).fetchone()

    if row is None:
        return None

    result = dict(row)

    if result["intelligence_result_json"]:
        result["intelligence"] = json.loads(
            result.pop("intelligence_result_json")
        )
    else:
        result.pop("intelligence_result_json")
        result["intelligence"] = None

    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--run",
        action="store_true",
        help="Ejecutar recopilación y análisis",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Mostrar el plan sin ejecutar nada",
    )

    parser.add_argument(
        "--timeout",
        type=int,
        default=900,
        help="Tiempo máximo de recopilación en segundos",
    )

    arguments = parser.parse_args()

    if arguments.timeout < 1:
        parser.error("--timeout debe ser positivo")

    if arguments.run:
        result = execute_full_update(
            timeout=arguments.timeout,
        )

    else:
        result = execute_full_update(
            dry_run=True,
        )

    print(json.dumps(
        result,
        ensure_ascii=False,
        indent=2,
        default=str,
    ))

    if result["status"] == "failed":
        sys.exit(1)
