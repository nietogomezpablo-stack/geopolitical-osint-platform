import sqlite3

DATABASE_PATH = "data/intelligence.db"

connection = sqlite3.connect(DATABASE_PATH)
connection.execute("PRAGMA foreign_keys = ON")
cursor = connection.cursor()

article_id = 4

title = "Ataque del MPLJ contra fuerzas de seguridad en Séguédine"
event_date = "2026-08-14"
event_type = "armed_attack"
country = "Niger"
location = "Séguédine"
description = "Ataques reivindicados por el MPLJ contra posiciones de las fuerzas de seguridad nigerinas en Séguédine, con varios soldados muertos y daños materiales."
confidence = 0.8

cursor.execute(
    """
    SELECT id
    FROM events
    WHERE event_date = ?
      AND event_type = ?
      AND country = ?
      AND location = ?
    ORDER BY id
    LIMIT 1
    """,
    (
        event_date,
        event_type,
        country,
        location
    )
)

existing_event = cursor.fetchone()

if existing_event is not None:
    event_id = existing_event[0]
    print("Evento ya existente.")

else:
    cursor.execute(
        """
        INSERT INTO events (
            title,
            event_date,
            event_type,
            country,
            location,
            description,
            confidence
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            title,
            event_date,
            event_type,
            country,
            location,
            description,
            confidence
        )
    )

    event_id = cursor.lastrowid
    print("Evento nuevo creado.")

cursor.execute(
    """
    INSERT OR IGNORE INTO event_articles (
        event_id,
        article_id
    )
    VALUES (?, ?)
    """,
    (
        event_id,
        article_id
    )
)

connection.commit()
connection.close()

print("Event ID:", event_id)
print("Article ID:", article_id)
