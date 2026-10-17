import hashlib
import html
import json
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from intelligence_analysis_v5 import build_report

ROOT = Path(__file__).resolve().parents[2]
DATABASE = ROOT / "data/intelligence.db"
OUTPUT = ROOT / "data/processed/reports"


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
            CREATE TABLE IF NOT EXISTS intelligence_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                report_hash TEXT NOT NULL,
                country TEXT NOT NULL,
                title TEXT NOT NULL,
                generated_at TEXT NOT NULL,
                report_json TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_reports_generated
            ON intelligence_reports(generated_at DESC);
        """)


def event_summary():
    if not DATABASE.exists():
        return {
            "total": 0,
            "events": [],
        }

    with connect() as db:
        exists = db.execute("""
            SELECT 1
            FROM sqlite_master
            WHERE type = 'table'
              AND name = 'events'
        """).fetchone()

        if not exists:
            return {
                "total": 0,
                "events": [],
            }

        cursor = db.execute("""
            SELECT *
            FROM events
            ORDER BY id DESC
            LIMIT 100
        """)

        columns = [
            item[0]
            for item in cursor.description
        ]

        events = [
            dict(zip(columns, row))
            for row in cursor.fetchall()
        ]

        total = db.execute("""
            SELECT COUNT(*)
            FROM events
        """).fetchone()[0]

    return {
        "total": total,
        "events": events,
    }


def alert_summary():
    if not DATABASE.exists():
        return {
            "total": 0,
            "unread": 0,
        }

    with connect() as db:
        exists = db.execute("""
            SELECT 1
            FROM sqlite_master
            WHERE type = 'table'
              AND name = 'intelligence_alerts'
        """).fetchone()

        if not exists:
            return {
                "total": 0,
                "unread": 0,
            }

        row = db.execute("""
            SELECT
                COUNT(*) AS total,
                SUM(
                    CASE WHEN is_read = 0 THEN 1 ELSE 0 END
                ) AS unread
            FROM intelligence_alerts
        """).fetchone()

    return {
        "total": row["total"],
        "unread": row["unread"] or 0,
    }


def build_intelligence_report():
    analysis = build_report()
    candidates = analysis.get("candidates", [])

    statuses = Counter()
    priorities = Counter()
    event_types = Counter()
    missing_checks = Counter()
    domains = Counter()

    entries = []

    for candidate in candidates:
        investigation = candidate.get("investigation") or {}
        intelligence = candidate.get("analysis_v5") or {}

        status = investigation.get("status", "pending")
        priority = intelligence.get("priority", "low")
        event_type = candidate.get("event_type", "unknown")

        statuses[status] += 1
        priorities[priority] += 1
        event_types[event_type] += 1

        checks = intelligence.get(
            "verification_checklist",
            []
        )

        for check in checks:
            missing_checks[check.get("code", "unknown")] += 1

        sources = intelligence.get("sources") or {}

        for domain in sources.get("domains", []):
            domains[domain] += 1

        entries.append({
            "candidate_key":
                investigation.get("candidate_key"),
            "title": candidate.get("title"),
            "event_type": event_type,
            "investigation_status": status,
            "priority": priority,
            "notes": investigation.get("notes", ""),
            "evidence_count":
                intelligence.get("evidence_count", 0),
            "source_urls": sources.get("urls", []),
            "verification_checklist": checks,
            "verified_event": False,
        })

    registered_events = event_summary()

    report = {
        "report_version": 9,
        "country": "Niger",
        "title": "Meridian OSINT — Informe de inteligencia: Níger",
        "generated_at": now(),
        "methodology": {
            "source": "Datos locales del proyecto Meridian OSINT",
            "automatic_fact_verification": False,
            "generative_ai": False,
            "candidate_status_not_event_confirmation": True,
            "location_mentions_not_verified_incident_sites": True,
            "source_domains_not_independent_corroboration": True,
        },
        "executive_summary": {
            "registered_events": registered_events["total"],
            "unverified_candidates": len(candidates),
            "investigation_statuses": dict(statuses),
            "review_priorities": dict(priorities),
            "event_types": dict(event_types),
            "alerts": alert_summary(),
        },
        "information_gaps": [
            {
                "check": key,
                "candidate_count": count,
            }
            for key, count in missing_checks.most_common()
        ],
        "source_domains": [
            {
                "domain": domain,
                "candidate_mentions": count,
                "independence_verified": False,
            }
            for domain, count in domains.most_common()
        ],
        "registered_events": registered_events["events"],
        "candidate_investigations": entries,
        "conclusions": [
            "Los candidatos detectados requieren verificación humana.",
            "Las prioridades reflejan necesidades de investigación, no veracidad.",
            "Las menciones geográficas no confirman el lugar del incidente.",
            "Los dominios de fuentes no demuestran corroboración independiente.",
        ],
    }

    return report


def report_digest(report):
    comparable = {
        key: value
        for key, value in report.items()
        if key != "generated_at"
    }

    payload = json.dumps(
        comparable,
        ensure_ascii=False,
        sort_keys=True,
        default=str,
    )

    return hashlib.sha256(
        payload.encode("utf-8")
    ).hexdigest()


def save_report(report=None):
    initialize()

    if report is None:
        report = build_intelligence_report()

    digest = report_digest(report)

    with connect() as db:
        cursor = db.execute("""
            INSERT INTO intelligence_reports (
                report_hash,
                country,
                title,
                generated_at,
                report_json
            )
            VALUES (?, ?, ?, ?, ?)
        """, (
            digest,
            report["country"],
            report["title"],
            report["generated_at"],
            json.dumps(
                report,
                ensure_ascii=False,
                default=str,
            ),
        ))

        report_id = cursor.lastrowid

    OUTPUT.mkdir(parents=True, exist_ok=True)

    path = OUTPUT / f"niger_report_{report_id}.json"

    path.write_text(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )

    return {
        "id": report_id,
        "path": str(path),
        "report_hash": digest,
    }


def list_reports(limit=50):
    initialize()
    limit = max(1, min(int(limit), 200))

    with connect() as db:
        rows = db.execute("""
            SELECT
                id,
                report_hash,
                country,
                title,
                generated_at
            FROM intelligence_reports
            ORDER BY id DESC
            LIMIT ?
        """, (limit,)).fetchall()

    return {
        "country": "Niger",
        "reports": [dict(row) for row in rows],
    }


def get_report(report_id):
    initialize()

    with connect() as db:
        row = db.execute("""
            SELECT report_json
            FROM intelligence_reports
            WHERE id = ?
        """, (report_id,)).fetchone()

    if row is None:
        return None

    return json.loads(row["report_json"])


def render_html(report):
    escape = lambda value: html.escape(str(value or ""))

    summary = report["executive_summary"]

    rows = []

    for candidate in report["candidate_investigations"]:
        title = escape(candidate["title"])
        status = escape(candidate["investigation_status"])
        priority = escape(candidate["priority"])
        event_type = escape(candidate["event_type"])

        source_links = []

        for url in candidate["source_urls"]:
            if not isinstance(url, str):
                continue

            if not url.startswith(("https://", "http://")):
                continue

            safe_url = escape(url)

            source_links.append(
                '<a href="' + safe_url +
                '" target="_blank" rel="noopener noreferrer">' +
                safe_url + '</a>'
            )

        rows.append(
            "<tr>"
            f"<td>{title}</td>"
            f"<td>{event_type}</td>"
            f"<td>{status}</td>"
            f"<td>{priority}</td>"
            f"<td>{'<br>'.join(source_links)}</td>"
            "</tr>"
        )

    return """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Meridian OSINT — Informe Níger</title>
<style>
body {
    background:#0b1725;
    color:#e5eff8;
    font:14px Arial,sans-serif;
    margin:0;
    padding:35px;
}
main {max-width:1250px;margin:auto}
h1,h2 {color:#fff}
p {line-height:1.6}
table {width:100%;border-collapse:collapse;margin-top:15px}
th,td {border:1px solid #35516a;padding:10px;text-align:left}
th {background:#193149}
tr:nth-child(even) {background:#102337}
a {color:#8fc9ff;overflow-wrap:anywhere}
.note {color:#b6ccde}
</style>
</head>
<body>
<main>
<h1>Meridian OSINT — Informe de inteligencia: Níger</h1>
<p class="note">Generado: """ + escape(report["generated_at"]) + """</p>

<h2>Resumen</h2>
<p>Acontecimientos registrados en la base de datos:
<strong>""" + str(summary["registered_events"]) + """</strong></p>
<p>Candidatos pendientes de verificación independiente:
<strong>""" + str(summary["unverified_candidates"]) + """</strong></p>

<h2>Investigaciones</h2>
<table>
<thead>
<tr>
<th>Acontecimiento</th>
<th>Tipo</th>
<th>Estado de revisión</th>
<th>Prioridad</th>
<th>Fuentes</th>
</tr>
</thead>
<tbody>
""" + "\n".join(rows) + """
</tbody>
</table>

<h2>Limitaciones metodológicas</h2>
<p>Los candidatos no constituyen acontecimientos verificados.
Las prioridades no representan probabilidades de veracidad.
Las ubicaciones mencionadas no equivalen a lugares de incidentes
confirmados. Los dominios no demuestran independencia editorial.</p>
</main>
</body>
</html>"""


if __name__ == "__main__":
    result = save_report()
    print("Informe generado:", result)
    print("Informes guardados:", len(list_reports()["reports"]))
