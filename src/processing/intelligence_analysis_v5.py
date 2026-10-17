import csv
import io
import json
import re
from collections import Counter
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import urlparse

from investigation_manager import (
    get_candidates,
    list_investigations,
)

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "data/processed/intelligence_analysis_v5.json"


def normalized_text(value):
    value = str(value or "").lower()
    value = re.sub(r"[^\w\s]", " ", value)
    return " ".join(value.split())


def get_domain(url):
    if not isinstance(url, str):
        return None

    try:
        parsed = urlparse(url.strip())
    except ValueError:
        return None

    if parsed.scheme not in ("http", "https"):
        return None

    domain = (parsed.hostname or "").lower()

    if domain.startswith("www."):
        domain = domain[4:]

    return domain or None


def get_article_ids(candidate):
    ids = candidate.get("article_ids")

    if isinstance(ids, list):
        return sorted({
            str(item)
            for item in ids
            if item is not None
        })

    article_id = candidate.get("article_id")

    return (
        [str(article_id)]
        if article_id is not None
        else []
    )


def get_sources(candidate):
    urls = []

    for field in ("url", "source_url", "article_url"):
        value = candidate.get(field)

        if isinstance(value, str):
            urls.append(value)

    for field in ("urls", "source_urls", "sources"):
        values = candidate.get(field)

        if not isinstance(values, list):
            continue

        for item in values:
            if isinstance(item, str):
                urls.append(item)

            elif isinstance(item, dict):
                for key in ("url", "source_url"):
                    value = item.get(key)

                    if isinstance(value, str):
                        urls.append(value)

    domains = {
        domain
        for url in urls
        if (domain := get_domain(url))
    }

    return {
        "urls": sorted(set(urls)),
        "domains": sorted(domains),
        "domain_count": len(domains),
    }


def evidence_count(candidate):
    evidence = candidate.get("evidence")

    if isinstance(evidence, list):
        return len([
            item for item in evidence
            if item
        ])

    if isinstance(evidence, dict):
        return sum(
            bool(value)
            for value in evidence.values()
        )

    return 1 if evidence else 0


def has_explicit_date(candidate):
    for field in (
        "event_date",
        "explicit_event_date",
        "verified_event_date",
    ):
        if candidate.get(field):
            return True

    # Las fechas mencionadas en el texto NO son
    # necesariamente fechas del acontecimiento.
    return False


def has_verified_location(candidate):
    for field in (
        "verified_location",
        "verified_event_location",
    ):
        if candidate.get(field):
            return True

    # Una mención de Niamey, Agadez, etc.
    # no demuestra que el incidente ocurriera allí.
    return False


def calculate_priority(candidate):
    score = 0
    reasons = []

    if evidence_count(candidate):
        score += 2
        reasons.append("Contiene fragmentos de evidencia")

    if get_article_ids(candidate):
        score += 1
        reasons.append("Tiene artículos identificables")

    if not has_explicit_date(candidate):
        score += 2
        reasons.append("Falta verificar la fecha del hecho")

    if not has_verified_location(candidate):
        score += 2
        reasons.append("Falta verificar la ubicación del hecho")

    sources = get_sources(candidate)

    if not sources["domains"]:
        score += 1
        reasons.append("Falta identificar una fuente web")

    if score >= 7:
        priority = "high"
    elif score >= 4:
        priority = "medium"
    else:
        priority = "low"

    return {
        "priority": priority,
        "review_score": score,
        "reasons": reasons,
    }


def verification_checklist(candidate):
    checks = []

    if not has_explicit_date(candidate):
        checks.append({
            "code": "event_date",
            "label": "Comprobar fecha exacta del acontecimiento",
        })

    if not has_verified_location(candidate):
        checks.append({
            "code": "event_location",
            "label": "Comprobar ubicación real del incidente",
        })

    if not get_sources(candidate)["domains"]:
        checks.append({
            "code": "original_source",
            "label": "Identificar la publicación original",
        })

    checks.extend([
        {
            "code": "independent_corroboration",
            "label": "Buscar corroboración independiente",
        },
        {
            "code": "historical_context",
            "label": "Descartar que sea una referencia histórica",
        },
        {
            "code": "claim_status",
            "label": "Distinguir hechos de afirmaciones no verificadas",
        },
    ])

    return checks


def possible_duplicates(candidates):
    matches = []

    for index, left in enumerate(candidates):
        for right in candidates[index + 1:]:
            shared_ids = sorted(
                set(get_article_ids(left))
                & set(get_article_ids(right))
            )

            left_title = normalized_text(
                left.get("title", "")
            )

            right_title = normalized_text(
                right.get("title", "")
            )

            similarity = (
                SequenceMatcher(
                    None,
                    left_title,
                    right_title,
                ).ratio()
                if left_title and right_title
                else 0
            )

            if shared_ids or similarity >= 0.86:
                matches.append({
                    "left": left["investigation"]["candidate_key"],
                    "right": right["investigation"]["candidate_key"],
                    "shared_article_ids": shared_ids,
                    "title_similarity": round(similarity, 3),
                    "relationship": (
                        "shared_article"
                        if shared_ids
                        else "similar_title"
                    ),
                    "verified_same_event": False,
                })

    return matches


def build_report():
    candidates = list_investigations()

    analyzed = []

    for candidate in candidates:
        priority = calculate_priority(candidate)
        sources = get_sources(candidate)

        analyzed.append({
            **candidate,
            "analysis_v5": {
                **priority,
                "sources": sources,
                "evidence_count": evidence_count(candidate),
                "article_ids": get_article_ids(candidate),
                "verification_checklist":
                    verification_checklist(candidate),
                "automatically_verified": False,
            },
        })

    order = {
        "high": 0,
        "medium": 1,
        "low": 2,
    }

    analyzed.sort(
        key=lambda item: (
            order[item["analysis_v5"]["priority"]],
            item["investigation"]["candidate_key"],
        )
    )

    domains = Counter()

    for candidate in analyzed:
        domains.update(
            candidate["analysis_v5"]["sources"]["domains"]
        )

    return {
        "version": 5,
        "country": "Niger",
        "generated_at":
            datetime.now(timezone.utc).isoformat(),
        "summary": {
            "candidates": len(analyzed),
            "high_priority": sum(
                item["analysis_v5"]["priority"] == "high"
                for item in analyzed
            ),
            "medium_priority": sum(
                item["analysis_v5"]["priority"] == "medium"
                for item in analyzed
            ),
            "low_priority": sum(
                item["analysis_v5"]["priority"] == "low"
                for item in analyzed
            ),
            "unique_source_domains": len(domains),
            "automatically_verified_events": 0,
        },
        "source_domains": [
            {
                "domain": domain,
                "candidate_mentions": count,
                "independent_source_verified": False,
            }
            for domain, count in domains.most_common()
        ],
        "possible_duplicates": possible_duplicates(analyzed),
        "candidates": analyzed,
    }


def export_json():
    report = build_report()

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    OUTPUT.write_text(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    return OUTPUT


def csv_safe(value):
    text = str(value or "")

    if text.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + text

    return text


def export_csv_text():
    report = build_report()
    output = io.StringIO()

    fields = [
        "candidate_key",
        "title",
        "event_type",
        "status",
        "priority",
        "review_score",
        "evidence_count",
        "article_ids",
        "source_domains",
        "notes",
        "verification_tasks",
    ]

    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()

    for candidate in report["candidates"]:
        analysis = candidate["analysis_v5"]
        investigation = candidate["investigation"]

        writer.writerow({
            "candidate_key":
                investigation["candidate_key"],
            "title": csv_safe(candidate.get("title")),
            "event_type": candidate.get("event_type"),
            "status": investigation["status"],
            "priority": analysis["priority"],
            "review_score": analysis["review_score"],
            "evidence_count": analysis["evidence_count"],
            "article_ids": ", ".join(analysis["article_ids"]),
            "source_domains": ", ".join(
                analysis["sources"]["domains"]
            ),
            "notes": csv_safe(investigation["notes"]),
            "verification_tasks": " | ".join(
                item["label"]
                for item in analysis["verification_checklist"]
            ),
        })

    return output.getvalue()


if __name__ == "__main__":
    output = export_json()
    report = build_report()

    print("Archivo:", output)
    print("Resumen:", report["summary"])
    print(
        "Posibles duplicados:",
        len(report["possible_duplicates"])
    )
