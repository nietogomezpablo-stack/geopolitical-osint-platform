import re
import sqlite3
import unicodedata
from collections import Counter

DATABASE = "data/intelligence.db"

PATTERNS = {
    "coup_attempt": [
        r"\btentative de coup d etat\b",
        r"\bcoup attempt\b",
        r"\battempted coup\b",
        r"\bintento de golpe de estado\b",
        r"\btentativa de golpe de estado\b",
    ],
    "military_mutiny": [
        r"\bmutinerie\b",
        r"\bmutiny\b",
        r"\bmotin militar\b",
        r"\bmotim militar\b",
    ],
    "kidnapping": [
        r"\benlevement\b",
        r"\bkidnapp(?:ed|ing)?\b",
        r"\bsecuestro\b",
        r"\brapto\b",
    ],
    "release": [
        r"\blibere(?:e|s|es)?\b",
        r"\bliberation\b",
        r"\breleased?\b",
        r"\bfreed\b",
        r"\bliberad[oa]s?\b",
    ],
    "military_appointment": [
        r"\bchef d etat major\b",
        r"\bchief of staff\b",
        r"\bjefe del estado mayor\b",
        r"\bnew army chief\b",
    ],
    "international_agreement": [
        r"\baccord bilateral\b",
        r"\baccord de cooperation\b",
        r"\bbilateral agreement\b",
        r"\bcooperation agreement\b",
        r"\bacuerdo bilateral\b",
        r"\bacordo bilateral\b",
    ],
    "armed_attack": [
        r"\battaque terroriste\b",
        r"\battaque armee\b",
        r"\barmed attack\b",
        r"\bterrorist attack\b",
        r"\bataque armado\b",
        r"\bataque terrorista\b",
        r"\btiros e explosoes\b",
        r"\bshooting and explosions\b",
    ],
}

# Estas expresiones indican incertidumbre, no confirmación.
UNCERTAINTY = [
    r"\btentative\b",
    r"\battempt\b",
    r"\bintento\b",
    r"\btentativa\b",
    r"\bsuspected\b",
    r"\bpossible\b",
    r"\bpresume\b",
    r"\balleged\b",
    r"\bsuppose\b",
    r"\baccuse\b",
    r"\baccuses\b",
    r"\baccusation\b",
]

def normalize(text):
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(
        character for character in text
        if not unicodedata.combining(character)
    )
    text = text.lower()
    return re.sub(r"[^\w]+", " ", text).strip()

def classify(title):
    normalized = normalize(title)
    matches = []

    for event_type, patterns in PATTERNS.items():
        if any(re.search(pattern, normalized) for pattern in patterns):
            matches.append(event_type)

    uncertain = any(
        re.search(pattern, normalized)
        for pattern in UNCERTAINTY
    )

    return matches, uncertain

def main():
    connection = sqlite3.connect(DATABASE)

    articles = connection.execute("""
        SELECT id, date, language, title
        FROM articles
        ORDER BY id
    """).fetchall()

    counts = Counter()

    print("=" * 75)
    print("MERIDIAN OSINT - DETECCIÓN EXPLORATORIA")
    print("MODO LECTURA: NO SE MODIFICA SQLITE")
    print("=" * 75)

    for article_id, date, language, title in articles:
        categories, uncertain = classify(title)

        if not categories:
            continue

        for category in categories:
            counts[category] += 1

        print()
        print("ARTÍCULO:", article_id)
        print("FECHA PUBLICACIÓN:", date)
        print("IDIOMA:", language)
        print("CATEGORÍAS:", ", ".join(categories))
        print("INCERTIDUMBRE TEXTUAL:", "SÍ" if uncertain else "NO")
        print("EVIDENCIA:", title)

    print()
    print("=" * 75)
    print("RESUMEN")
    print("Artículos analizados:", len(articles))
    print("Candidatos por categoría:")

    for category, count in counts.most_common():
        print(f"  {category}: {count}")

    print()
    print("No se han creado acontecimientos.")
    connection.close()

if __name__ == "__main__":
    main()
