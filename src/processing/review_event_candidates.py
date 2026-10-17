import re
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime

from detect_geopolitical_events import classify, normalize

DATABASE = "data/intelligence.db"

def detect_status(title, category):
    text = normalize(title)

    if category == "kidnapping" and re.search(
        r"\b(released?|freed|liberation|libere|liberee|liberado|liberada)\b",
        text
    ):
        return "HISTORICAL_REFERENCE"

    if re.search(
        r"\b(dejouee?|foiled|thwarted|frustree?|frustrado|frustrada)\b",
        text
    ):
        return "FOILED_OR_PREVENTED"

    if re.search(
        r"\b(tentative|attempt|intento|tentativa|possible|alleged)\b",
        text
    ):
        return "UNCONFIRMED_OR_ATTEMPTED"

    return "REQUIRES_VERIFICATION"


def event_group(title, category):
    text = normalize(title)

    # Agrupación conservadora del caso identificado.
    if category == "release" and (
        "missionary" in text
        or "missionnaire" in text
    ):
        return "missionary_release_review"

    return None


def main():
    connection = sqlite3.connect(
        f"file:{DATABASE}?mode=ro",
        uri=True
    )

    articles = connection.execute("""
        SELECT id, date, language, title
        FROM articles
        ORDER BY date, id
    """).fetchall()

    candidates = []
    groups = defaultdict(list)

    for article_id, date, language, title in articles:
        categories, uncertain = classify(title)

        for category in categories:
            status = detect_status(title, category)
            group = event_group(title, category)

            candidate = {
                "article_id": article_id,
                "date": date,
                "language": language,
                "title": title,
                "category": category,
                "status": status,
                "group": group,
            }

            candidates.append(candidate)

            if group:
                groups[group].append(candidate)

    print("=" * 75)
    print("MERIDIAN OSINT - REVISIÓN DE CANDIDATOS")
    print("MODO LECTURA")
    print("=" * 75)

    for candidate in candidates:
        print()
        print("ARTÍCULO:", candidate["article_id"])
        print("PUBLICACIÓN:", candidate["date"])
        print("TIPO:", candidate["category"])
        print("ESTADO:", candidate["status"])
        print("GRUPO:", candidate["group"] or "Sin agrupar")
        print("TÍTULO:", candidate["title"])

    print()
    print("=" * 75)
    print("POSIBLES GRUPOS DE NOTICIAS")
    print("=" * 75)

    for group_name, members in groups.items():
        print()
        print("GRUPO:", group_name)
        print(
            "ARTÍCULOS:",
            sorted(set(m["article_id"] for m in members))
        )
        print(
            "CATEGORÍAS:",
            sorted(set(m["category"] for m in members))
        )

    print()
    print("Candidatos clasificados:", len(candidates))
    print("Grupos identificados:", len(groups))
    print("No se ha modificado la base de datos.")

    connection.close()


if __name__ == "__main__":
    main()
