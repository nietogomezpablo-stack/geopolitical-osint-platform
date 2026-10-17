import sqlite3
import spacy

modelo_frances = spacy.load("fr_core_news_lg")
modelo_multilingue = spacy.load("xx_ent_wiki_sm")

connection = sqlite3.connect("data/intelligence.db")
cursor = connection.cursor()

cursor.execute("""
SELECT a.id, a.content, a.language
FROM articles a
WHERE a.content IS NOT NULL
AND NOT EXISTS (
    SELECT 1
    FROM article_processing ap
    WHERE ap.article_id = a.id
    AND ap.ner_processed = 1
)
""")

articles = cursor.fetchall()

print("Artículos para analizar:", len(articles))

menciones_detectadas = 0

for article_id, content, language in articles:
    print("Analizando artículo:", article_id, "-", language)

    if language == "French":
        nlp = modelo_frances
    else:
        nlp = modelo_multilingue

    doc = nlp(content)

    for entity in doc.ents:
        text = entity.text.strip()

        if not text:
            continue

        cursor.execute(
            """
            INSERT INTO entity_mentions (
                article_id,
                entity_id,
                text,
                detected_type,
                start_char,
                end_char
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                article_id,
                None,
                text,
                entity.label_,
                entity.start_char,
                entity.end_char
            )
        )

        menciones_detectadas += 1

    cursor.execute(
        '''
        INSERT INTO article_processing (article_id, ner_processed)
        VALUES (?, 1)
        ON CONFLICT(article_id)
        DO UPDATE SET ner_processed = 1
        ''',
        (article_id,)
    )

connection.commit()
connection.close()

print()
print("Análisis NER terminado.")
print("Menciones detectadas:", menciones_detectadas)
