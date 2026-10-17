import argparse
import csv
import io
import json
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

ROOT = Path(__file__).resolve().parents[2]
DB = ROOT / "data/intelligence.db"
OUTPUT = ROOT / "data/exports/quality_v25.json"


def now():
    return datetime.now(timezone.utc).isoformat()


def connect(db_path=None):
    db = sqlite3.connect(str(db_path or DB))
    db.row_factory = sqlite3.Row
    return db


def table_exists(db, name):
    return db.execute(
        "SELECT 1 FROM sqlite_master "
        "WHERE type='table' AND name=?",
        (name,)
    ).fetchone() is not None


def columns(db, table):
    if not table_exists(db, table):
        return set()

    return {
        row["name"]
        for row in db.execute(
            'PRAGMA table_info("' + table + '")'
        )
    }


def read_table(db, table):
    if not table_exists(db, table):
        return []

    # El nombre procede exclusivamente del código, no del usuario.
    return [
        dict(row)
        for row in db.execute(
            'SELECT * FROM "' + table + '"'
        )
    ]


def canonical_url(value):
    if not value:
        return ""

    try:
        parsed = urlsplit(str(value).strip())

        if parsed.scheme.lower() not in ("http", "https"):
            return ""

        host = (parsed.hostname or "").lower()

        if not host:
            return ""

        port = (
            f":{parsed.port}"
            if parsed.port and parsed.port not in (80, 443)
            else ""
        )

        path = parsed.path.rstrip("/") or "/"

        tracking = {
            "utm_source",
            "utm_medium",
            "utm_campaign",
            "utm_content",
            "utm_term",
            "fbclid",
            "gclid",
        }

        query = urlencode(
            sorted(
                (key, value)
                for key, value in parse_qsl(
                    parsed.query,
                    keep_blank_values=True,
                )
                if key.lower() not in tracking
            )
        )

        return urlunsplit(
            ("https", host + port, path, query, "")
        )

    except (ValueError, TypeError):
        return ""


def domain(value):
    try:
        return (urlsplit(value).hostname or "").lower()
    except ValueError:
        return ""


def candidate_keys(db):
    """
    V22:
    Las alertas son referencias de investigación,
    no acontecimientos verificados.
    """

    alerts = read_table(db, "triage_alerts_v17")

    keys = sorted({
        str(row.get("candidate_key"))
        for row in alerts
        if row.get("candidate_key")
    })

    return keys, alerts


def article_inventory(db):
    """
    V23:
    Lee el esquema real de articles.
    No presupone columnas inexistentes.
    """

    available = columns(db, "articles")

    if not available:
        return {
            "count": 0,
            "url_column": None,
            "duplicate_groups": [],
            "duplicate_records": 0,
            "unique_domains": 0,
            "missing_urls": 0,
            "url_coverage": None,
        }

    url_column = next(
        (
            column
            for column in (
                "url",
                "article_url",
                "source_url",
                "link",
            )
            if column in available
        ),
        None,
    )

    rows = read_table(db, "articles")

    if url_column is None:
        return {
            "count": len(rows),
            "url_column": None,
            "duplicate_groups": [],
            "duplicate_records": 0,
            "unique_domains": None,
            "missing_urls": None,
            "url_coverage": None,
        }

    groups = defaultdict(list)
    domains = set()
    missing = 0

    for index, row in enumerate(rows):
        url = canonical_url(row.get(url_column))

        if not url:
            missing += 1
            continue

        identifier = row.get("id", index)

        groups[url].append(identifier)

        host = domain(url)

        if host:
            domains.add(host)

    duplicates = [
        {
            "url": url,
            "article_ids": ids,
            "occurrences": len(ids),
        }
        for url, ids in groups.items()
        if len(ids) > 1
    ]

    duplicates.sort(
        key=lambda item: (
            -item["occurrences"],
            item["url"],
        )
    )

    return {
        "count": len(rows),
        "url_column": url_column,
        "duplicate_groups": duplicates,
        "duplicate_records": sum(
            group["occurrences"] - 1
            for group in duplicates
        ),
        "unique_domains": len(domains),
        "missing_urls": missing,
        "url_coverage": (
            round(
                100 * (len(rows) - missing) / len(rows),
                1,
            )
            if rows else None
        ),
    }


def documentary_quality(db, keys, alerts):
    """
    V24:
    Diagnóstico de documentación pendiente.

    No afirma que una fuente sea verdadera.
    No convierte alertas en acontecimientos.
    """

    by_candidate = defaultdict(list)

    for alert in alerts:
        key = alert.get("candidate_key")

        if key:
            by_candidate[str(key)].append(alert)

    audits = read_table(db, "evidence_audits")
    audit_by_candidate = defaultdict(list)

    for audit in audits:
        key = audit.get("candidate_key")

        if key:
            audit_by_candidate[str(key)].append(audit)

    investigations = read_table(db, "investigations")
    investigation_keys = {
        str(row.get("candidate_key"))
        for row in investigations
        if row.get("candidate_key")
    }

    cases = read_table(db, "investigation_cases")
    case_keys = {
        str(row.get("candidate_key"))
        for row in cases
        if row.get("candidate_key")
    }

    result = []

    for key in keys:
        candidate_alerts = by_candidate[key]
        candidate_audits = audit_by_candidate[key]

        insufficient = any(
            alert.get("alert_type")
            == "insufficient_documentation"
            and alert.get("status") == "active"
            for alert in candidate_alerts
        )

        contradicted = any(
            audit.get("status") == "contradicted"
            for audit in candidate_audits
        )

        supported = sum(
            audit.get("status") == "supported"
            for audit in candidate_audits
        )

        result.append({
            "candidate_key": key,
            "alert_count": len(candidate_alerts),
            "active_alert_count": sum(
                alert.get("status") == "active"
                for alert in candidate_alerts
            ),
            "insufficient_documentation_alert": insufficient,
            "audit_records": len(candidate_audits),
            "supported_checks": supported,
            "contradicted_checks": sum(
                audit.get("status") == "contradicted"
                for audit in candidate_audits
            ),
            "has_investigation_record": (
                key in investigation_keys
            ),
            "has_case_record": key in case_keys,
            "review_required": (
                insufficient
                or contradicted
                or not candidate_audits
            ),
            "verification_status": "not_independently_verified",
        })

    return result


def analyze(db_path=None):
    with connect(db_path) as db:
        keys, alerts = candidate_keys(db)
        articles = article_inventory(db)
        candidates = documentary_quality(
            db,
            keys,
            alerts,
        )

        events = (
            db.execute(
                "SELECT COUNT(*) FROM events"
            ).fetchone()[0]
            if table_exists(db, "events")
            else 0
        )

        active_alerts = sum(
            alert.get("status") == "active"
            for alert in alerts
        )

        unresolved = sum(
            candidate["review_required"]
            for candidate in candidates
        )

        result = {
            "country": "Niger",
            "version": 25,
            "generated_at": now(),
            "summary": {
                "articles": articles["count"],
                "events_in_database": events,
                "candidate_references": len(keys),
                "alerts_total": len(alerts),
                "alerts_active": active_alerts,
                "candidates_requiring_review": unresolved,
                "duplicate_url_groups": len(
                    articles["duplicate_groups"]
                ),
                "duplicate_article_records": (
                    articles["duplicate_records"]
                ),
            },
            "articles": articles,
            "candidates": candidates,
            "limitations": [
                "Las alertas no son eventos confirmados.",
                "La ausencia de auditorías no demuestra falsedad.",
                "Los duplicados se detectan por URL normalizada.",
                "Las fuentes no se verifican independientemente.",
                "Los candidatos se identifican mediante las claves de las alertas V17.",
            ],
            "automatic_confirmation": False,
        }

        return result


def export_json(report=None, output=None):
    report = report or analyze()
    path = Path(output or OUTPUT)

    path.parent.mkdir(parents=True, exist_ok=True)

    path.write_text(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    return path


def csv_safe(value):
    text = str(value if value is not None else "")

    if text.lstrip().startswith(
        ("=", "+", "-", "@", "\t", "\r")
    ):
        return "'" + text

    return text


def export_csv(report=None):
    report = report or analyze()

    buffer = io.StringIO()
    writer = csv.writer(buffer)

    fields = [
        "candidate_key",
        "alert_count",
        "active_alert_count",
        "insufficient_documentation_alert",
        "audit_records",
        "supported_checks",
        "contradicted_checks",
        "has_investigation_record",
        "has_case_record",
        "review_required",
        "verification_status",
    ]

    writer.writerow(fields)

    for candidate in report["candidates"]:
        writer.writerow([
            csv_safe(candidate.get(field))
            for field in fields
        ])

    return buffer.getvalue()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--report",
        action="store_true",
    )

    parser.add_argument(
        "--export",
        action="store_true",
    )

    args = parser.parse_args()

    report = analyze()

    if args.export:
        path = export_json(report)
        print("INFORME EXPORTADO:", path)

    print(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
        )
    )
