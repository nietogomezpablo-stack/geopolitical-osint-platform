import csv
import io
import json
from collections import Counter
from pathlib import Path

from intelligence_analysis_v5 import build_report
from intelligence_provenance_v12 import analyze as analyze_provenance

ROOT = Path(__file__).resolve().parents[2]


def as_list(value):
    if value is None:
        return []

    if isinstance(value, list):
        return value

    if isinstance(value, (tuple, set)):
        return list(value)

    return [value]


def nonempty(value):
    if value is None:
        return False

    if isinstance(value, str):
        return bool(value.strip())

    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)

    return bool(value)


def extract_date_mentions(candidate):
    values = []

    for field in (
        "date_mentions",
        "explicit_dates",
        "mentioned_dates",
    ):
        values.extend(as_list(candidate.get(field)))

    return [
        value
        for value in values
        if nonempty(value)
    ]


def extract_location_mentions(candidate):
    values = []

    for field in (
        "locations",
        "location_mentions",
        "mentioned_locations",
    ):
        values.extend(as_list(candidate.get(field)))

    return [
        value
        for value in values
        if nonempty(value)
    ]


def verified_date(candidate):
    for field in (
        "verified_event_date",
        "explicit_event_date",
    ):
        value = candidate.get(field)

        if nonempty(value):
            return value

    return None


def verified_location(candidate):
    for field in (
        "verified_event_location",
        "verified_location",
    ):
        value = candidate.get(field)

        if nonempty(value):
            return value

    return None


def verify_candidate(candidate, provenance=None):
    investigation = candidate.get("investigation") or {}
    analysis = candidate.get("analysis_v5") or {}

    key = investigation.get("candidate_key")

    provenance = provenance or {}

    dates = extract_date_mentions(candidate)
    locations = extract_location_mentions(candidate)

    event_date = verified_date(candidate)
    event_location = verified_location(candidate)

    article_count = provenance.get(
        "article_count",
        0,
    )

    domain_count = provenance.get(
        "domain_count",
        0,
    )

    source_urls = provenance.get(
        "source_urls",
        [],
    )

    checks = []

    def add_check(code, label, passed, explanation):
        checks.append({
            "code": code,
            "label": label,
            "passed": bool(passed),
            "explanation": explanation,
        })

    add_check(
        "source_identified",
        "Fuente documental identificada",
        bool(source_urls),
        (
            "Existen URLs asociadas al candidato."
            if source_urls
            else "No se han identificado URLs asociadas."
        ),
    )

    add_check(
        "article_associated",
        "Artículo asociado",
        article_count > 0,
        (
            f"Hay {article_count} referencias de artículos."
            if article_count
            else "No hay identificadores de artículos asociados."
        ),
    )

    add_check(
        "date_mentioned",
        "Fecha mencionada en documentación",
        bool(dates),
        (
            "Se han detectado menciones de fechas."
            if dates
            else "No se han detectado menciones de fechas."
        ),
    )

    add_check(
        "event_date_verified",
        "Fecha del acontecimiento verificada",
        bool(event_date),
        (
            "Existe un campo explícito de fecha verificada."
            if event_date
            else "No existe fecha del acontecimiento verificada."
        ),
    )

    add_check(
        "location_mentioned",
        "Ubicación mencionada",
        bool(locations),
        (
            "Se han identificado menciones geográficas."
            if locations
            else "No se han identificado menciones geográficas."
        ),
    )

    add_check(
        "event_location_verified",
        "Ubicación del acontecimiento verificada",
        bool(event_location),
        (
            "Existe un campo explícito de ubicación verificada."
            if event_location
            else "No existe ubicación del incidente verificada."
        ),
    )

    add_check(
        "multiple_domains_identified",
        "Varios dominios identificados",
        domain_count >= 2,
        (
            f"Se han identificado {domain_count} dominios."
            if domain_count >= 2
            else "Se han identificado menos de dos dominios."
        ),
    )

    passed = sum(
        1
        for check in checks
        if check["passed"]
    )

    total = len(checks)

    pending = [
        check
        for check in checks
        if not check["passed"]
    ]

    return {
        "candidate_key": key,
        "title": candidate.get("title"),
        "event_type": candidate.get("event_type"),
        "investigation_status": investigation.get(
            "status",
            "pending",
        ),
        "review_priority": analysis.get(
            "priority",
            "unknown",
        ),
        "date_mentions": dates,
        "location_mentions": locations,
        "verified_event_date": event_date,
        "verified_event_location": event_location,
        "article_count": article_count,
        "domain_count": domain_count,
        "source_urls": source_urls,
        "checks": checks,
        "passed_checks": passed,
        "total_checks": total,
        "pending_checks": pending,
        "documentation_coverage_percent": round(
            passed / total * 100,
            1,
        ) if total else 0,
        "event_factually_verified": False,
        "independent_corroboration_verified": False,
    }


def analyze(report=None, provenance=None):
    if report is None:
        report = build_report()

    if provenance is None:
        provenance = analyze_provenance(report=report)

    provenance_by_key = {
        item["candidate_key"]: item
        for item in provenance.get("candidates", [])
    }

    results = []

    for candidate in report.get("candidates", []):
        investigation = candidate.get("investigation") or {}
        key = investigation.get("candidate_key")

        if not key:
            continue

        results.append(
            verify_candidate(
                candidate,
                provenance_by_key.get(key),
            )
        )

    pending_counts = Counter()

    for item in results:
        for check in item["pending_checks"]:
            pending_counts[check["code"]] += 1

    return {
        "country": "Niger",
        "candidate_count": len(results),
        "candidates": results,
        "most_common_information_gaps": [
            {
                "code": code,
                "candidate_count": count,
            }
            for code, count in pending_counts.most_common()
        ],
        "methodology": {
            "documentation_coverage_is_truth_probability": False,
            "automatic_event_confirmation": False,
            "independent_corroboration_verified": False,
            "date_mentions_are_event_dates": False,
            "location_mentions_are_incident_locations": False,
            "verified_fields_are_not_independently_audited": True,
        },
    }


def candidate_verification(key, report=None, provenance=None):
    result = analyze(report, provenance)

    for candidate in result["candidates"]:
        if candidate["candidate_key"] == key:
            return candidate

    return None


def export_csv(report=None, provenance=None):
    result = analyze(report, provenance)

    output = io.StringIO()

    writer = csv.writer(output)

    writer.writerow([
        "candidate_key",
        "title",
        "event_type",
        "investigation_status",
        "review_priority",
        "article_count",
        "domain_count",
        "passed_checks",
        "total_checks",
        "documentation_coverage_percent",
        "pending_checks",
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
            safe(candidate["investigation_status"]),
            safe(candidate["review_priority"]),
            candidate["article_count"],
            candidate["domain_count"],
            candidate["passed_checks"],
            candidate["total_checks"],
            candidate["documentation_coverage_percent"],
            safe("; ".join(
                check["code"]
                for check in candidate["pending_checks"]
            )),
        ])

    return output.getvalue()


if __name__ == "__main__":
    result = analyze()

    print("País:", result["country"])
    print("Candidatos:", result["candidate_count"])

    for gap in result["most_common_information_gaps"]:
        print(
            gap["code"],
            "→",
            gap["candidate_count"],
            "candidatos",
        )
