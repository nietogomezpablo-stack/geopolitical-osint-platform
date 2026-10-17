import json
import re
import sqlite3
import unicodedata
from collections import defaultdict
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]
DATABASE = ROOT / "data/intelligence.db"
INPUT = ROOT / "data/processed/event_candidates.json"
OUTPUT = ROOT / "data/processed/event_intelligence_v4.json"

FAMILIES = {
    "coup_attempt": "military_instability",
    "military_mutiny": "military_instability",
    "armed_attack": "armed_attack",
    "kidnapping": "kidnapping",
    "release": "release",
    "military_appointment": "appointment",
    "international_agreement": "agreement",
}

STOPWORDS = {
    "niger", "nigerien", "nigerienne",
    "the", "and", "for", "with", "from", "after",
    "dans", "pour", "avec", "apres", "une", "des",
    "les", "sur", "est", "son", "aux", "cette",
    "this", "that", "their", "says", "news",
    "conflict", "state", "du", "de", "la", "le",
    "un", "en", "et", "au", "d", "l", "a",
    "el", "los", "las", "del", "por", "una",
    "para", "con", "que", "como", "sobre",
}

EVENT_LABELS = {
    "coup_attempt": "Intento de golpe de Estado",
    "military_mutiny": "Motín militar",
    "armed_attack": "Ataque armado",
    "kidnapping": "Secuestro",
    "release": "Liberación",
    "military_appointment": "Nombramiento militar",
    "international_agreement": "Acuerdo internacional",
}


def normalize(text):
    text = unicodedata.normalize("NFKD", str(text or ""))
    return "".join(
        character for character in text
        if not unicodedata.combining(character)
    ).lower()


def tokenize(text):
    return {
        token
        for token in re.findall(r"[a-z]{3,}", normalize(text))
        if token not in STOPWORDS
    }


def similarity(a, b):
    a_tokens = tokenize(a)
    b_tokens = tokenize(b)

    jaccard = (
        len(a_tokens & b_tokens) / len(a_tokens | b_tokens)
        if a_tokens | b_tokens else 0
    )

    sequence = SequenceMatcher(
        None, normalize(a), normalize(b)
    ).ratio()

    return round(max(jaccard, sequence), 3)


def source_domain(url):
    try:
        parsed = urlparse(url or "")
        if parsed.scheme not in ("http", "https"):
            return None
        host = parsed.hostname
        if not host:
            return None
        return host.lower().removeprefix("www.")
    except ValueError:
        return None


def source_urls(candidate):
    urls = candidate.get("source_urls") or [
        candidate.get("url")
    ]
    return sorted({
        url for url in urls
        if source_domain(url)
    })


def article_ids(candidate):
    return sorted({
        int(value)
        for value in (
            candidate.get("source_articles")
            or [candidate["article_id"]]
        )
    })


def locations(candidate):
    return {
        normalize(item.get("name"))
        for item in candidate.get("locations", [])
        if item.get("name")
    }


def parse_date(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(
            str(value).replace("Z", "+00:00")
        ).date()
    except (ValueError, TypeError):
        return None


def compare(a, b):
    family_a = FAMILIES.get(
        a["event_type"], a["event_type"]
    )
    family_b = FAMILIES.get(
        b["event_type"], b["event_type"]
    )

    if family_a != family_b:
        return 0.0, []

    if set(article_ids(a)) & set(article_ids(b)):
        return 1.0, ["same_article"]

    score = 0.0
    reasons = []

    title_score = similarity(a["title"], b["title"])

    score += title_score * 0.50

    if title_score >= 0.45:
        reasons.append("similar_titles")

    common_locations = locations(a) & locations(b)

    if common_locations:
        score += 0.15
        reasons.append("shared_location_reference")

    date_a = parse_date(a.get("publication_date"))
    date_b = parse_date(b.get("publication_date"))

    if date_a and date_b:
        difference = abs((date_a - date_b).days)

        if difference <= 3:
            score += 0.20
            reasons.append("publication_dates_close")
        elif difference <= 14:
            score += 0.08

    if a["event_type"] == b["event_type"]:
        score += 0.15
        reasons.append("same_event_type")
    else:
        reasons.append("related_event_types")

    return round(min(score, 1.0), 3), reasons


def evidence_coverage(candidate):
    evidence = candidate.get("evidence") or []
    urls = source_urls(candidate)

    domains = {
        domain for domain in map(source_domain, urls)
        if domain
    }

    return {
        "evidence_fragments": len(evidence),
        "source_urls": len(urls),
        "source_domains": len(domains),
        "location_references": len(
            candidate.get("locations") or []
        ),
        "mentioned_dates": len(
            candidate.get("mentioned_dates") or []
        ),
        "independent_sources_verified": False,
        "truth_score": None,
    }


def build_report(candidates):
    candidates = [dict(item) for item in candidates]

    for index, candidate in enumerate(candidates):
        candidate["candidate_id"] = index + 1
        candidate["event_label"] = EVENT_LABELS.get(
            candidate["event_type"],
            candidate["event_type"]
        )
        candidate["article_ids"] = article_ids(candidate)
        candidate["source_urls"] = source_urls(candidate)
        candidate["coverage"] = evidence_coverage(candidate)

        candidate["event_verified"] = False
        candidate["event_date"] = None
        candidate["date_verified"] = False
        candidate["location_verified"] = False
        candidate["review_required"] = True
        candidate["related_candidates"] = []

    relationships = []

    for i in range(len(candidates)):
        for j in range(i + 1, len(candidates)):
            a = candidates[i]
            b = candidates[j]

            score, reasons = compare(a, b)

            if score < 0.55:
                continue

            relation = {
                "candidate_a": a["candidate_id"],
                "candidate_b": b["candidate_id"],
                "similarity": score,
                "reasons": reasons,
                "same_event_verified": False,
            }

            relationships.append(relation)

            a["related_candidates"].append({
                "candidate_id": b["candidate_id"],
                "similarity": score,
                "reasons": reasons,
            })

            b["related_candidates"].append({
                "candidate_id": a["candidate_id"],
                "similarity": score,
                "reasons": reasons,
            })

    # Agrupación automática únicamente cuando los candidatos
    # comparten un artículo exacto. Las coincidencias entre
    # artículos distintos siguen siendo hipótesis.
    parent = list(range(len(candidates)))

    def find(index):
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(a, b):
        a = find(a)
        b = find(b)
        if a != b:
            parent[b] = a

    for relation in relationships:
        if "same_article" in relation["reasons"]:
            union(
                relation["candidate_a"] - 1,
                relation["candidate_b"] - 1
            )

    groups = defaultdict(list)

    for index in range(len(candidates)):
        groups[find(index)].append(index)

    clusters = []

    for number, indices in enumerate(groups.values(), 1):
        members = [candidates[i] for i in indices]

        clusters.append({
            "cluster_id": number,
            "candidate_ids": [
                member["candidate_id"]
                for member in members
            ],
            "article_ids": sorted({
                article
                for member in members
                for article in member["article_ids"]
            }),
            "event_types": sorted({
                member["event_type"]
                for member in members
            }),
            "title": members[0]["title"],
            "event_verified": False,
            "review_required": True,
        })

    domains = {
        domain
        for candidate in candidates
        for url in candidate["source_urls"]
        if (domain := source_domain(url))
    }

    return {
        "version": 4,
        "country": "Niger",
        "summary": {
            "candidates": len(candidates),
            "clusters": len(clusters),
            "possible_relationships": len(relationships),
            "source_domains": len(domains),
            "verified_events_created": 0,
        },
        "candidates": candidates,
        "clusters": clusters,
        "relationships": relationships,
    }


def main():
    if not INPUT.exists():
        raise SystemExit(
            "Falta event_candidates.json. "
            "Ejecuta primero el exportador y el enriquecimiento."
        )

    candidates = json.loads(
        INPUT.read_text(encoding="utf-8")
    )

    result = build_report(candidates)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    temporary = OUTPUT.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    temporary.replace(OUTPUT)

    print("\nMERIDIAN OSINT V4")
    print("=" * 55)

    for key, value in result["summary"].items():
        print(f"{key}: {value}")

    print("Archivo:", OUTPUT)


if __name__ == "__main__":
    main()
