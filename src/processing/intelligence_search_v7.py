import csv
import io
import sqlite3
import unicodedata
from collections import Counter
from pathlib import Path

from intelligence_analysis_v5 import build_report, csv_safe

ROOT = Path(__file__).resolve().parents[2]
DATABASE = ROOT / "data/intelligence.db"

VALID_STATUSES = {
    "pending",
    "investigating",
    "reviewed",
    "dismissed",
}

VALID_PRIORITIES = {
    "high",
    "medium",
    "low",
}

VALID_SORTS = {
    "priority",
    "title",
    "status",
    "type",
}


def normalize(value):
    text = unicodedata.normalize(
        "NFKD",
        str(value or ""),
    )

    return "".join(
        character
        for character in text
        if not unicodedata.combining(character)
    ).casefold()


def searchable_text(candidate):
    investigation = candidate.get("investigation") or {}
    analysis = candidate.get("analysis_v5") or {}

    fields = [
        candidate.get("title", ""),
        candidate.get("event_type", ""),
        investigation.get("notes", ""),
        investigation.get("status", ""),
        analysis.get("priority", ""),
        " ".join(
            analysis.get("sources", {}).get("domains", [])
        ),
    ]

    return normalize(" ".join(map(str, fields)))


def search(
    query="",
    status="",
    priority="",
    event_type="",
    sort="priority",
    report=None,
):
    if status and status not in VALID_STATUSES:
        raise ValueError("Estado inválido")

    if priority and priority not in VALID_PRIORITIES:
        raise ValueError("Prioridad inválida")

    if sort not in VALID_SORTS:
        raise ValueError("Ordenación inválida")

    if report is None:
        report = build_report()

    candidates = report.get("candidates", [])
    terms = normalize(query).split()

    results = []

    for candidate in candidates:
        investigation = candidate.get("investigation") or {}
        analysis = candidate.get("analysis_v5") or {}

        if status and investigation.get("status") != status:
            continue

        if priority and analysis.get("priority") != priority:
            continue

        if event_type and candidate.get("event_type") != event_type:
            continue

        text = searchable_text(candidate)

        if not all(term in text for term in terms):
            continue

        results.append(candidate)

    priority_order = {
        "high": 0,
        "medium": 1,
        "low": 2,
    }

    if sort == "priority":
        results.sort(
            key=lambda item: (
                priority_order.get(
                    item.get("analysis_v5", {}).get("priority"),
                    3,
                ),
                normalize(item.get("title")),
            )
        )

    elif sort == "title":
        results.sort(
            key=lambda item: normalize(item.get("title"))
        )

    elif sort == "status":
        results.sort(
            key=lambda item: (
                item.get("investigation", {}).get("status", ""),
                normalize(item.get("title")),
            )
        )

    elif sort == "type":
        results.sort(
            key=lambda item: (
                item.get("event_type", ""),
                normalize(item.get("title")),
            )
        )

    return {
        "country": "Niger",
        "total": len(results),
        "available_types": sorted({
            item.get("event_type")
            for item in candidates
            if item.get("event_type")
        }),
        "results": results,
    }


def investigation_timeline(limit=100):
    limit = max(1, min(int(limit), 500))

    if not DATABASE.exists():
        return {
            "country": "Niger",
            "total": 0,
            "entries": [],
        }

    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row

    try:
        exists = connection.execute("""
            SELECT 1
            FROM sqlite_master
            WHERE type = 'table'
              AND name = 'investigation_history'
        """).fetchone()

        if not exists:
            return {
                "country": "Niger",
                "total": 0,
                "entries": [],
            }

        total = connection.execute("""
            SELECT COUNT(*)
            FROM investigation_history
        """).fetchone()[0]

        rows = connection.execute("""
            SELECT
                id,
                candidate_key,
                previous_status,
                new_status,
                notes,
                changed_at
            FROM investigation_history
            ORDER BY id DESC
            LIMIT ?
        """, (limit,)).fetchall()

        return {
            "country": "Niger",
            "total": total,
            "entries": [dict(row) for row in rows],
        }

    finally:
        connection.close()


def activity_summary():
    report = build_report()
    timeline = investigation_timeline(limit=500)

    statuses = Counter(
        item.get("investigation", {}).get("status", "pending")
        for item in report.get("candidates", [])
    )

    priorities = Counter(
        item.get("analysis_v5", {}).get("priority", "low")
        for item in report.get("candidates", [])
    )

    return {
        "country": "Niger",
        "candidates": len(report.get("candidates", [])),
        "investigation_changes": timeline["total"],
        "statuses": dict(statuses),
        "priorities": dict(priorities),
    }


def search_csv(**filters):
    result = search(**filters)
    output = io.StringIO()

    writer = csv.DictWriter(
        output,
        fieldnames=[
            "candidate_key",
            "title",
            "event_type",
            "status",
            "priority",
            "notes",
        ],
    )

    writer.writeheader()

    for candidate in result["results"]:
        investigation = candidate.get("investigation") or {}
        analysis = candidate.get("analysis_v5") or {}

        writer.writerow({
            "candidate_key":
                investigation.get("candidate_key", ""),
            "title": csv_safe(candidate.get("title", "")),
            "event_type": csv_safe(
                candidate.get("event_type", "")
            ),
            "status": investigation.get("status", ""),
            "priority": analysis.get("priority", ""),
            "notes": csv_safe(
                investigation.get("notes", "")
            ),
        })

    return output.getvalue()


if __name__ == "__main__":
    result = search()
    print("Candidatos indexados:", result["total"])
    print("Tipos:", result["available_types"])
    print("Actividad:", activity_summary())
