import argparse
import csv
import fcntl
import io
import json
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DB = ROOT / 'data' / 'intelligence.db'
LOCK = ROOT / 'data' / 'meridian_operations_v18_v21.lock'

def utcnow():
    return datetime.now(timezone.utc).isoformat()

def connection(db_path=None):
    path = Path(db_path) if db_path is not None else DB
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA busy_timeout=10000')
    return db

def initialize(db_path=None):
    with connection(db_path) as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS meridian_operation_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                duration_seconds REAL,
                status TEXT NOT NULL,
                pipeline_status TEXT NOT NULL DEFAULT 'pending',
                alert_status TEXT NOT NULL DEFAULT 'pending',
                alerts_created INTEGER NOT NULL DEFAULT 0,
                alerts_updated INTEGER NOT NULL DEFAULT 0,
                alerts_resolved INTEGER NOT NULL DEFAULT 0,
                error_message TEXT,
                pipeline_output_tail TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_meridian_operation_runs_started
            ON meridian_operation_runs(started_at);
        """)

def history(db_path=None, limit=50):
    initialize(db_path)
    limit = max(1, min(int(limit), 200))
    with connection(db_path) as db:
        rows = db.execute('SELECT * FROM meridian_operation_runs ORDER BY id DESC LIMIT ?', (limit,)).fetchall()
    return [dict(row) for row in rows]

def execute(db_path=None, lock_path=None, pipeline_runner=None, alert_runner=None, timeout=900):
    initialize(db_path)
    lock_path = Path(lock_path) if lock_path else LOCK
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open('a+') as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('Ya existe una ejecución de operaciones en curso')
        started = time.monotonic()
        with connection(db_path) as db:
            run_id = db.execute(
                "INSERT INTO meridian_operation_runs (started_at,status) VALUES (?,'running')",
                (utcnow(),)
            ).lastrowid
        pipeline_status, alert_status, status = 'pending', 'pending', 'failed'
        alert_result, error, output = {}, None, ''
        try:
            if pipeline_runner is None:
                script = ROOT / 'run_pipeline.py'
                if not script.is_file():
                    raise RuntimeError('No existe run_pipeline.py')
                result = subprocess.run(
                    [sys.executable, str(script)], cwd=str(ROOT),
                    capture_output=True, text=True, timeout=timeout, check=False
                )
                output = (result.stdout + '\n' + result.stderr)[-5000:]
                if result.returncode != 0:
                    raise RuntimeError(f'Pipeline terminó con código {result.returncode}: {output[-1500:]}')
            else:
                pipeline_runner()
            pipeline_status = 'success'
            if alert_runner is None:
                from intelligence_triage_v16 import analyze
                from intelligence_triage_alerts_v17 import synchronize
                report = analyze()
                if report.get('verification_error'):
                    raise RuntimeError('Verificación documental incompleta: ' + str(report['verification_error']))
                alert_result = synchronize(triage_report=report)
            else:
                alert_result = alert_runner()
            alert_status = 'success'
            status = 'success'
        except Exception as exc:
            error = str(exc)[:4000]
            if pipeline_status == 'pending':
                pipeline_status = 'failed'
                alert_status = 'skipped'
            else:
                alert_status = 'failed'
        finally:
            duration = round(time.monotonic() - started, 3)
            with connection(db_path) as db:
                db.execute("""
                    UPDATE meridian_operation_runs SET finished_at=?, duration_seconds=?,
                    status=?, pipeline_status=?, alert_status=?, alerts_created=?,
                    alerts_updated=?, alerts_resolved=?, error_message=?, pipeline_output_tail=?
                    WHERE id=?
                """, (
                    utcnow(), duration, status, pipeline_status, alert_status,
                    int(alert_result.get('created', 0)), int(alert_result.get('updated', 0)),
                    int(alert_result.get('resolved', 0)), error, output, run_id
                ))
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
        return {'run_id': run_id, 'status': status, 'pipeline_status': pipeline_status,
                'alert_status': alert_status, 'alerts': alert_result, 'error': error}

def health(db_path=None, stale_hours=48):
    initialize(db_path)
    issues = []
    latest = history(db_path, 1)
    latest = latest[0] if latest else None
    if not (ROOT / 'run_pipeline.py').is_file():
        issues.append({'code': 'pipeline_missing', 'message': 'No se encuentra run_pipeline.py'})
    if latest is None:
        issues.append({'code': 'never_executed', 'message': 'No hay ejecuciones registradas en V18-V21'})
    else:
        if latest['status'] == 'failed':
            issues.append({'code': 'last_run_failed', 'message': 'La última ejecución terminó con errores'})
        if latest['status'] == 'running':
            issues.append({'code': 'run_unfinished', 'message': 'Hay una ejecución sin resultado final registrado'})
        try:
            started = datetime.fromisoformat(latest['started_at'])
            if datetime.now(timezone.utc) - started > timedelta(hours=stale_hours):
                issues.append({'code': 'stale_pipeline', 'message': f'Última ejecución hace más de {stale_hours} horas'})
        except (TypeError, ValueError):
            issues.append({'code': 'invalid_timestamp', 'message': 'Fecha de ejecución inválida'})
    return {'country': 'Niger', 'status': 'attention' if issues else 'ok',
            'issues': issues, 'latest_run': latest, 'stale_hours': stale_hours,
            'automatic_event_confirmation': False}

def report(db_path=None):
    runs = history(db_path, 100)
    return {'country': 'Niger', 'versions': [18, 19, 20, 21],
            'health': health(db_path), 'runs': runs,
            'summary': {'total_runs': len(runs),
                        'successful_runs': sum(r['status'] == 'success' for r in runs),
                        'failed_runs': sum(r['status'] == 'failed' for r in runs)},
            'automatic_event_confirmation': False}

def safe_csv(value):
    s = str(value if value is not None else '')
    return "'" + s if s.lstrip().startswith(('=', '+', '-', '@')) else s

def report_csv(db_path=None):
    output = io.StringIO()
    writer = csv.writer(output)
    columns = ['id','started_at','finished_at','duration_seconds','status',
               'pipeline_status','alert_status','alerts_created','alerts_updated',
               'alerts_resolved','error_message']
    writer.writerow(columns)
    for row in history(db_path, 200):
        writer.writerow([safe_csv(row.get(col)) for col in columns])
    return output.getvalue()

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--run', action='store_true')
    group.add_argument('--status', action='store_true')
    group.add_argument('--report', action='store_true')
    group.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    if args.run:
        result = execute()
    elif args.report:
        result = report()
    elif args.dry_run:
        result = {'country':'Niger', 'execution_performed':False,
                  'pipeline_exists':(ROOT/'run_pipeline.py').is_file(),
                  'dependencies':['intelligence_triage_v16','intelligence_triage_alerts_v17']}
    else:
        result = health()
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    if args.run and result['status'] != 'success':
        sys.exit(1)
