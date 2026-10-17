import json
import re
import sqlite3
import unicodedata
from pathlib import Path
from datetime import datetime
from difflib import SequenceMatcher

DATABASE = Path("data/intelligence.db")
OUTPUT = Path("data/processed/event_candidates.json")

KEYWORDS = {
    "armed_attack": [
        "attack", "attaque", "ataque",
        "explosion", "explosions", "explosão",
        "terrorist", "terroriste",
    ],
    "military_mutiny": [
        "mutiny", "mutinerie", "motín", "motim",
    ],
    "coup_attempt": [
        "coup", "golpe de estado",
        "tentative de coup",
    ],
    "kidnapping": [
        "kidnapped", "kidnapping",
        "enlèvement", "secuestro",
    ],
    "release": [
        "released", "freed", "libéré",
        "libération", "liberado",
    ],
    "international_agreement": [
        "agreement", "accord", "acuerdo",
    ],
    "military_appointment": [
        "appointed", "nommé", "nombrado",
    ],
}

MONTHS = {
    "january": 1, "february": 2, "march": 3,
    "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9,
    "october": 10, "november": 11, "december": 12,

    "janvier": 1, "février": 2, "mars": 3,
    "avril": 4, "mai": 5, "juin": 6,
    "juillet": 7, "août": 8, "septembre": 9,
    "octobre": 10, "novembre": 11, "décembre": 12,

    "enero": 1, "febrero": 2, "marzo": 3,
    "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9,
    "octubre": 10, "noviembre": 11, "diciembre": 12,
}


def normalize(text):
    text = unicodedata.normalize("NFKD", text or "")
    return "".join(
        c for c in text
        if not unicodedata.combining(c)
    ).lower()


NORMALIZED_MONTHS = {
    normalize(name): number
    for name, number in MONTHS.items()
}

MONTH_PATTERN = "|".join(
    sorted(NORMALIZED_MONTHS, key=len, reverse=True)
)

DATE_PATTERN = re.compile(
    rf"\b(\d{{1,2}})\s+(?:de\s+)?"
    rf"({MONTH_PATTERN})\s+(?:de\s+)?"
    rf"(\d{{4}})\b"
)


def split_sentences(text):
    return [
        sentence.strip()
        for sentence in re.split(
            r"(?<=[.!?])\s+|\n+",
            text or ""
        )
        if sentence.strip()
    ]


def extract_evidence(content, event_type):
    keywords = [
        normalize(keyword)
        for keyword in KEYWORDS.get(event_type, [])
    ]

    evidence = []

    for sentence in split_sentences(content):
        normalized = normalize(sentence)

        if any(
            re.search(
                r"(?<!\w)" + re.escape(keyword) + r"(?!\w)",
                normalized
            )
            for keyword in keywords
        ):
            evidence.append({
                "text": sentence[:500],
                "source": "article_content",
                "verified": False,
            })

        if len(evidence) >= 3:
            break

    return evidence


def extract_dates(content):
    dates = []

    for match in DATE_PATTERN.finditer(normalize(content)):
        day, month, year = match.groups()

        try:
            date = datetime(
                int(year),
                NORMALIZED_MONTHS[month],
                int(day)
            ).date().isoformat()

            dates.append(date)

        except ValueError:
            continue

    return sorted(set(dates))


def similarity(a, b):
    return SequenceMatcher(
        None,
        normalize(a),
        normalize(b)
    ).ratio()


def enrich():
    candidates = json.loads(
        OUTPUT.read_text(encoding="utf-8")
    )

    connection = sqlite3.connect(
        f"file:{DATABASE}?mode=ro",
        uri=True
    )

    connection.row_factory = sqlite3.Row

    for candidate in candidates:
        article = connection.execute(
            """
            SELECT title, content
            FROM articles
            WHERE id = ?
            """,
            (candidate["article_id"],)
        ).fetchone()

        if article is None:
            candidate["evidence"] = []
            candidate["mentioned_dates"] = []
            candidate["possible_related"] = []
            continue

        content = article["content"] or ""

        candidate["evidence"] = extract_evidence(
            content,
            candidate["event_type"]
        )

        candidate["mentioned_dates"] = extract_dates(
            content
        )

        candidate["event_date"] = None
        candidate["date_verified"] = False
        candidate["location_verified"] = False
        candidate["review_required"] = True

    for candidate in candidates:
        related = []

        for other in candidates:
            if candidate is other:
                continue

            if candidate["event_type"] != other["event_type"]:
                continue

            score = similarity(
                candidate["title"],
                other["title"]
            )

            if score >= 0.65:
                related.append({
                    "article_id": other["article_id"],
                    "similarity": round(score, 3),
                })

        candidate["possible_related"] = related

    connection.close()

    OUTPUT.write_text(
        json.dumps(
            candidates,
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )

    return candidates


if __name__ == "__main__":
    candidates = enrich()

    print("\nEVENT INTELLIGENCE ENGINE V2")
    print("=" * 55)

    for candidate in candidates:
        print()
        print("TIPO:", candidate["event_type"])
        print("TÍTULO:", candidate["title"])
        print("EVIDENCIAS:", len(candidate["evidence"]))
        print("FECHAS:", candidate["mentioned_dates"])
        print("RELACIONADOS:", len(candidate["possible_related"]))

    print()
    print("TOTAL CANDIDATOS:", len(candidates))
    print("EVENTOS CONFIRMADOS MODIFICADOS: 0")
