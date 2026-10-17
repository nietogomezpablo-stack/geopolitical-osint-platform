import csv
import io
import json
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import (
    urlsplit,
    urlunsplit,
    parse_qsl,
    urlencode,
)

from intelligence_analysis_v5 import build_report

ROOT = Path(__file__).resolve().parents[2]
DATABASE = ROOT / "data/intelligence.db"

TRACKING_PARAMETERS = {
    "fbclid",
    "gclid",
    "mc_cid",
    "mc_eid",
    "ref",
    "source",
}


def normalize_url(url):
    if not isinstance(url, str):
        return ""

    url = url.strip()

    if not url:
        return ""

    try:
        parsed = urlsplit(url)

        if parsed.scheme.lower() not in ("http", "https"):
            return ""

        hostname = (parsed.hostname or "").lower()

        if not hostname:
            return ""

        port = parsed.port

        if port and not (
            parsed.scheme.lower() == "http" and port == 80
        ) and not (
            parsed.scheme.lower() == "https" and port == 443
        ):
            hostname = f"{hostname}:{port}"

        path = parsed.path.rstrip("/") or "/"

        parameters = [
            (key, value)
            for key, value in parse_qsl(
                parsed.query,
                keep_blank_values=True,
            )
            if not key.lower().startswith("utm_")
            and key.lower() not in TRACKING_PARAMETERS
        ]

        parameters.sort()

        return urlunsplit((
            parsed.scheme.lower(),
            hostname,
            path,
            urlencode(parameters),
            "",
        ))

    except (ValueError, TypeError):
        return ""


def domain_of(url):
    try:
        return urlsplit(url).hostname or ""
    except ValueError:
        return ""


def connect():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection


def article_catalog():
    if not DATABASE.exists():
        return []

    with connect() as db:
        table = db.execute("""
            SELECT 1
            FROM sqlite_master
            WHERE type = 'table'
              AND name = 'articles'
        """).fetchone()

        if not table:
            return []

        columns = {
            row["name"]
            for row in db.execute(
                "PRAGMA table_info(articles)"
            )
        }

        selected = [
            name
            for name in ("id", "url", "title")
            if name in columns
        ]

        if "id" not in selected or "url" not in selected:
            return []

        rows = db.execute(
            "SELECT " + ", ".join(selected) +
            " FROM articles"
        ).fetchall()

    return [dict(row) for row in rows]


def extract_article_ids(candidate):
    analysis = candidate.get("analysis_v5") or {}

    values = (
        analysis.get("article_ids")
        or candidate.get("article_ids")
        or []
    )

    if not isinstance(values, list):
        values = [values]

    return sorted({
        str(value)
        for value in values
        if value is not None
    })


def extract_source_urls(candidate):
    analysis = candidate.get("analysis_v5") or {}
    sources = analysis.get("sources") or {}

    urls = sources.get("urls") or []

    if not isinstance(urls, list):
        urls = [urls]

    return sorted({
        normalized
        for value in urls
        if (normalized := normalize_url(value))
    })


def analyze(report=None, articles=None):
    if report is None:
        report = build_report()

    if articles is None:
        articles = article_catalog()

    article_by_id = {
        str(article["id"]): article
        for article in articles
    }

    url_groups = defaultdict(list)

    for article in articles:
        normalized = normalize_url(
            article.get("url")
        )

        if normalized:
            url_groups[normalized].append(
                article.get("id")
            )

    duplicates = [
        {
            "normalized_url": url,
            "article_ids": ids,
        }
        for url, ids in url_groups.items()
        if len(ids) > 1
    ]

    candidates = []
    article_usage = defaultdict(set)

    for candidate in report.get("candidates", []):
        investigation = candidate.get("investigation") or {}
        key = investigation.get("candidate_key")

        if not key:
            continue

        ids = extract_article_ids(candidate)
        urls = set(extract_source_urls(candidate))

        matched_articles = []

        for article_id in ids:
            article_usage[article_id].add(key)

            article = article_by_id.get(article_id)

            if not article:
                continue

            normalized = normalize_url(
                article.get("url")
            )

            if normalized:
                urls.add(normalized)

            matched_articles.append({
                "id": article_id,
                "title": article.get("title"),
                "url": normalized,
            })

        domains = sorted({
            domain_of(url)
            for url in urls
            if domain_of(url)
        })

        candidates.append({
            "candidate_key": key,
            "title": candidate.get("title"),
            "event_type": candidate.get("event_type"),
            "article_ids": ids,
            "matched_articles": matched_articles,
            "source_urls": sorted(urls),
            "domains": domains,
            "article_count": len(ids),
            "domain_count": len(domains),
            "has_identifiable_sources": bool(urls),
            "independent_corroboration_verified": False,
        })

    shared_articles = [
        {
            "article_id": article_id,
            "candidate_keys": sorted(keys),
        }
        for article_id, keys in article_usage.items()
        if len(keys) > 1
    ]

    return {
        "country": "Niger",
        "candidate_count": len(candidates),
        "catalog_article_count": len(articles),
        "duplicate_url_groups": duplicates,
        "shared_articles": shared_articles,
        "candidates": candidates,
        "methodology": {
            "url_normalization": True,
            "duplicate_detection_basis": "normalized_url",
            "shared_article_detection": True,
            "independent_source_verification": False,
            "source_credibility_scoring": False,
        },
    }


def candidate_provenance(key, report=None, articles=None):
    result = analyze(report, articles)

    for candidate in result["candidates"]:
        if candidate["candidate_key"] == key:
            return candidate

    return None


def export_csv(report=None, articles=None):
    result = analyze(report, articles)

    output = io.StringIO()

    writer = csv.writer(output)

    writer.writerow([
        "candidate_key",
        "title",
        "event_type",
        "article_count",
        "domain_count",
        "domains",
        "source_urls",
    ])

    def safe(value):
        text = str(value or "")

        if text.lstrip().startswith(
            ("=", "+", "-", "@")
        ):
            return "'" + text

        return text

    for candidate in result["candidates"]:
        writer.writerow([
            safe(candidate["candidate_key"]),
            safe(candidate["title"]),
            safe(candidate["event_type"]),
            candidate["article_count"],
            candidate["domain_count"],
            safe("; ".join(candidate["domains"])),
            safe("; ".join(candidate["source_urls"])),
        ])

    return output.getvalue()


if __name__ == "__main__":
    result = analyze()

    print(
        "Candidatos analizados:",
        result["candidate_count"],
    )

    print(
        "Artículos catalogados:",
        result["catalog_article_count"],
    )

    print(
        "Grupos de URLs duplicadas:",
        len(result["duplicate_url_groups"]),
    )

    print(
        "Artículos compartidos entre candidatos:",
        len(result["shared_articles"]),
    )
