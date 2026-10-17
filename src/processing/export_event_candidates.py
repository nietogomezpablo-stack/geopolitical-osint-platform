
import json
import sqlite3
from pathlib import Path
from collections import defaultdict

from detect_geopolitical_events import classify
from review_event_candidates import detect_status, event_group
from detect_niger_locations import detect_locations

DATABASE = "data/intelligence.db"
OUTPUT = Path("data/processed/event_candidates.json")


def build_candidates():
    connection = sqlite3.connect(
        f"file:{DATABASE}?mode=ro",
        uri=True
    )

    connection.row_factory = sqlite3.Row

    articles = connection.execute("""
        SELECT id, date, title, content, language, url
        FROM articles
        ORDER BY date, id
    """).fetchall()

    candidates = []
    grouped = defaultdict(list)

    for article in articles:
        title = article["title"] or ""
        content = article["content"] or ""

        categories, uncertain = classify(title)

        for category in categories:
            status = detect_status(title, category)

            if status == "HISTORICAL_REFERENCE":
                continue

            group = event_group(title, category)

            # Buscar ubicaciones en el título y el contenido.
            # Las ubicaciones del cuerpo son referencias, no
            # coordenadas confirmadas del acontecimiento.
            title_locations = detect_locations(title)
            content_locations = detect_locations(content)

            locations_by_name = {}

            for loc in title_locations:
                loc = dict(loc)
                loc["evidence_source"] = "title"
                locations_by_name[loc["name"]] = loc

            for loc in content_locations:
                if loc["name"] not in locations_by_name:
                    loc = dict(loc)
                    loc["evidence_source"] = "article_content"
                    locations_by_name[loc["name"]] = loc

            locations = list(locations_by_name.values())

            candidate = {
                "article_id": article["id"],
                "publication_date": article["date"],
                "event_date": None,
                "title": title,
                "language": article["language"],
                "url": article["url"],
                "event_type": category,
                "status": status,
                "uncertain": uncertain,
                "country": "Niger",
                "locations": locations,
                "location_verified": False,
                "date_verified": False,
                "review_required": True,
                "group": group,
            }

            if group:
                grouped[(group, category)].append(candidate)
            else:
                candidates.append(candidate)

    # Agrupación provisional de noticias relacionadas.
    for (group_name, category), members in grouped.items():
        first = min(
            members,
            key=lambda item: item["publication_date"]
        )

        merged = dict(first)

        merged["source_articles"] = sorted(
            {item["article_id"] for item in members}
        )

        merged["source_urls"] = sorted(
            {
                item["url"]
                for item in members
                if item["url"]
            }
        )

        merged["locations"] = list({
            loc["name"]: loc
            for item in members
            for loc in item["locations"]
        }.values())

        merged["uncertain"] = any(
            item["uncertain"] for item in members
        )

        candidates.append(merged)

    connection.close()

    return sorted(
        candidates,
        key=lambda item: item["publication_date"],
        reverse=True
    )


def main():
    candidates = build_candidates()

    OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    OUTPUT.write_text(
        json.dumps(
            candidates,
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )

    print("\nCANDIDATOS GEOPOLÍTICOS")
    print("-" * 55)

    for candidate in candidates:
        print()
        print("TIPO:", candidate["event_type"])
        print("ESTADO:", candidate["status"])
        print("TÍTULO:", candidate["title"])
        print(
            "UBICACIONES:",
            [
                loc["name"]
                for loc in candidate["locations"]
            ] or ["No identificadas"]
        )

        sources = candidate.get(
            "source_articles",
            [candidate["article_id"]]
        )

        print("ARTÍCULOS ASOCIADOS:", len(sources))

    print()
    print("TOTAL CANDIDATOS:", len(candidates))
    print("ARCHIVO:", OUTPUT)
    print("EVENTOS CONFIRMADOS MODIFICADOS: 0")


if __name__ == "__main__":
    main()
