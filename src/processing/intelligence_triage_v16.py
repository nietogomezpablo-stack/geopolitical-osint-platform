import argparse
import csv
import io
import json
import sqlite3
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATABASE = ROOT / "data/intelligence.db"

WEIGHTS = {
    "contradicted_evidence": 40,
    "high_priority_task": 20,
    "medium_priority_task": 10,
    "insufficient_evidence": 15,
    "pending_evidence": 5,
    "missing_documentation": 10,
}


def connect(database=None):
    path = Path(database) if database else DATABASE

    if not path.exists():
        return None

    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row

    return connection


def table_exists(db, name):
    return db.execute("""
        SELECT 1
        FROM sqlite_master
        WHERE type = 'table'
          AND name = ?
    """, (name,)).fetchone() is not None


def fetch_rows(db, table, columns):
    if not table_exists(db, table):
        return []

    existing = {
        row["name"]
        for row in db.execute(
            f"PRAGMA table_info({table})"
        )
    }

    if not set(columns).issubset(existing):
        return []

    query = (
        "SELECT "
        + ", ".join(columns)
        + " FROM "
        + table
    )

    return [
        dict(row)
        for row in db.execute(query).fetchall()
    ]


def load_data(database=None):
    db = connect(database)

    if db is None:
        return {
            "cases": [],
            "tasks": [],
            "audits": [],
        }

    try:
        return {
            "cases": fetch_rows(
                db,
                "investigation_cases",
                [
                    "candidate_key",
                    "analyst_notes",
                    "updated_at",
                ],
            ),
            "tasks": fetch_rows(
                db,
                "investigation_tasks",
                [
                    "id",
                    "candidate_key",
                    "title",
                    "status",
                    "priority",
                ],
            ),
            "audits": fetch_rows(
                db,
                "evidence_audits",
                [
                    "candidate_key",
                    "check_code",
                    "status",
                ],
            ),
        }
    finally:
        db.close()


def priority_label(score):
    if score >= 60:
        return "critical"

    if score >= 30:
        return "high"

    if score >= 10:
        return "medium"

    return "low"


def calculate_case(
    candidate_key,
    case=None,
    tasks=None,
    audits=None,
    verification=None,
):
    tasks = tasks or []
    audits = audits or []
    verification = verification or {}

    reasons = []
    score = 0

    def add_reason(code, points, description):
        nonlocal score

        score += points

        reasons.append({
            "code": code,
            "points": points,
            "description": description,
        })

    contradicted = [
        audit
        for audit in audits
        if audit.get("status") == "contradicted"
    ]

    insufficient = [
        audit
        for audit in audits
        if audit.get("status") == "insufficient"
    ]

    pending_audits = [
        audit
        for audit in audits
        if audit.get("status") == "pending"
    ]

    high_tasks = [
        task
        for task in tasks
        if task.get("status") in (
            "pending",
            "in_progress",
        )
        and task.get("priority") == "high"
    ]

    medium_tasks = [
        task
        for task in tasks
        if task.get("status") in (
            "pending",
            "in_progress",
        )
        and task.get("priority") == "medium"
    ]

    if contradicted:
        add_reason(
            "contradicted_evidence",
            WEIGHTS["contradicted_evidence"],
            (
                f"{len(contradicted)} comprobaciones "
                "con evidencias contradichas"
            ),
        )

    if high_tasks:
        add_reason(
            "high_priority_task",
            WEIGHTS["high_priority_task"],
            (
                f"{len(high_tasks)} tareas abiertas "
                "de prioridad alta"
            ),
        )

    if medium_tasks:
        add_reason(
            "medium_priority_task",
            WEIGHTS["medium_priority_task"],
            (
                f"{len(medium_tasks)} tareas abiertas "
                "de prioridad media"
            ),
        )

    if insufficient:
        add_reason(
            "insufficient_evidence",
            WEIGHTS["insufficient_evidence"],
            (
                f"{len(insufficient)} comprobaciones "
                "con evidencia insuficiente"
            ),
        )

    if pending_audits:
        add_reason(
            "pending_evidence",
            WEIGHTS["pending_evidence"],
            (
                f"{len(pending_audits)} comprobaciones "
                "pendientes de revisión"
            ),
        )

    pending_checks = verification.get(
        "pending_checks",
        [],
    )

    if pending_checks:
        add_reason(
            "missing_documentation",
            WEIGHTS["missing_documentation"],
            (
                f"{len(pending_checks)} comprobaciones "
                "documentales no satisfechas"
            ),
        )

    # Se limita a 100 para facilitar la comparación.
    # No es una probabilidad ni una medida de veracidad.
    score = min(score, 100)

    return {
        "candidate_key": candidate_key,
        "title": verification.get("title"),
        "triage_score": score,
        "triage_priority": priority_label(score),
        "reasons": reasons,
        "open_tasks": sum(
            1
            for task in tasks
            if task.get("status") in (
                "pending",
                "in_progress",
            )
        ),
        "contradicted_checks": len(contradicted),
        "insufficient_checks": len(insufficient),
        "analyst_notes_present": bool(
            (case or {}).get("analyst_notes", "").strip()
        ),
        "event_factually_verified": False,
        "automatic_event_confirmation": False,
    }


def analyze(data=None, verification=None):
    if data is None:
        data = load_data()

    if verification is None:
        try:
            from intelligence_verification_v13 import (
                analyze as analyze_verification,
            )

            verification = analyze_verification()

        except (
            ImportError,
            sqlite3.Error,
            KeyError,
            TypeError,
            ValueError,
        ) as error:
            verification = {
                "candidates": [],
                "error": str(error),
            }

    cases = {
        item["candidate_key"]: item
        for item in data.get("cases", [])
    }

    tasks = defaultdict(list)

    for item in data.get("tasks", []):
        tasks[item["candidate_key"]].append(item)

    audits = defaultdict(list)

    for item in data.get("audits", []):
        audits[item["candidate_key"]].append(item)

    verification_items = {
        item["candidate_key"]: item
        for item in verification.get("candidates", [])
        if item.get("candidate_key")
    }

    keys = (
        set(cases)
        | set(tasks)
        | set(audits)
        | set(verification_items)
    )

    results = []

    for key in keys:
        results.append(
            calculate_case(
                candidate_key=key,
                case=cases.get(key),
                tasks=tasks.get(key),
                audits=audits.get(key),
                verification=verification_items.get(key),
            )
        )

    results.sort(
        key=lambda item: (
            -item["triage_score"],
            item["candidate_key"],
        )
    )

    counts = {
        "critical": 0,
        "high": 0,
        "medium": 0,
        "low": 0,
    }

    for item in results:
        counts[item["triage_priority"]] += 1

    return {
        "country": "Niger",
        "candidate_count": len(results),
        "priority_counts": counts,
        "candidates": results,
        "verification_error": verification.get("error"),
        "methodology": {
            "type": "rule_based_investigation_triage",
            "weights": WEIGHTS,
            "score_is_truth_probability": False,
            "automatic_event_confirmation": False,
            "analyst_decisions_modified": False,
        },
    }


def get_candidate(key, data=None, verification=None):
    result = analyze(data, verification)

    for candidate in result["candidates"]:
        if candidate["candidate_key"] == key:
            return candidate

    return None


def csv_safe(value):
    text = str(value if value is not None else "")

    if text.lstrip().startswith(
        ("=", "+", "-", "@")
    ):
        return "'" + text

    return text


def export_csv(data=None, verification=None):
    result = analyze(data, verification)

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "candidate_key",
        "title",
        "triage_score",
        "triage_priority",
        "open_tasks",
        "contradicted_checks",
        "insufficient_checks",
        "reasons",
    ])

    for item in result["candidates"]:
        writer.writerow([
            csv_safe(item["candidate_key"]),
            csv_safe(item["title"]),
            item["triage_score"],
            item["triage_priority"],
            item["open_tasks"],
            item["contradicted_checks"],
            item["insufficient_checks"],
            csv_safe("; ".join(
                reason["description"]
                for reason in item["reasons"]
            )),
        ])

    return output.getvalue()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--json",
        action="store_true",
    )

    arguments = parser.parse_args()

    result = analyze()

    if arguments.json:
        print(json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
            default=str,
        ))

    else:
        print("País:", result["country"])
        print("Investigaciones:", result["candidate_count"])
        print("Críticas:", result["priority_counts"]["critical"])
        print("Altas:", result["priority_counts"]["high"])
        print("Medias:", result["priority_counts"]["medium"])
        print("Bajas:", result["priority_counts"]["low"])

        if result["verification_error"]:
            print(
                "Advertencia: verificación documental no disponible:",
                result["verification_error"],
            )
