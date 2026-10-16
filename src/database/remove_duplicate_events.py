import sqlite3
from pathlib import Path
from datetime import datetime

DATABASE_PATH = Path("data/intelligence.db")

backup_path = DATABASE_PATH.with_name(
    "intelligence_backup_"
    + datetime.now().strftime("%Y%m%d_%H%M%S")
    + ".db"
)

source = sqlite3.connect(DATABASE_PATH)
backup = sqlite3.connect(backup_path)

source.backup(backup)
backup.close()
source.close()

print("Copia de seguridad:", backup_path)

connection = sqlite3.connect(DATABASE_PATH)
connection.execute("PRAGMA foreign_keys = ON")

cursor = connection.cursor()

original_id = 1
duplicate_ids = [5, 6, 7]

cursor.execute(
    """
    SELECT
        id,
        event_date,
        event_type,
        country,
        location
    FROM events
    WHERE id IN (1, 5, 6, 7)
    """
)

events = cursor.fetchall()

if len(events) != 4:
    connection.close()
    raise RuntimeError(
        "No se encontraron todos los eventos esperados."
    )

original = next(
    event for event in events
    if event[0] == original_id
)

for event in events:
    if event[1:] != original[1:]:
        connection.close()
        raise RuntimeError(
            f"El evento {event[0]} no coincide con el original."
        )

try:
    connection.execute("BEGIN")

    for duplicate_id in duplicate_ids:
        for table, column in [
            ("event_articles", "article_id"),
            ("event_entities", "entity_id"),
            ("event_locations", "location_id")
        ]:
            cursor.execute(
                f"""
                SELECT
                    {column},
                    relation_type
                FROM {table}
                WHERE event_id = ?
                """
                if table != "event_articles"
                else """
                SELECT article_id
                FROM event_articles
                WHERE event_id = ?
                """,
                (duplicate_id,)
            )

            rows = cursor.fetchall()

            for row in rows:
                if table == "event_articles":
                    cursor.execute(
                        """
                        INSERT OR IGNORE INTO event_articles (
                            event_id,
                            article_id
                        )
                        VALUES (?, ?)
                        """,
                        (original_id, row[0])
                    )

                else:
                    cursor.execute(
                        f"""
                        INSERT OR IGNORE INTO {table} (
                            event_id,
                            {column},
                            relation_type
                        )
                        VALUES (?, ?, ?)
                        """,
                        (
                            original_id,
                            row[0],
                            row[1]
                        )
                    )

        for table in [
            "event_articles",
            "event_entities",
            "event_locations"
        ]:
            cursor.execute(
                f"DELETE FROM {table} WHERE event_id = ?",
                (duplicate_id,)
            )

        cursor.execute(
            "DELETE FROM events WHERE id = ?",
            (duplicate_id,)
        )

    connection.commit()

except Exception:
    connection.rollback()
    connection.close()
    raise

cursor.execute(
    """
    SELECT id, title
    FROM events
    ORDER BY id
    """
)

print()
print("Eventos restantes:")

for event in cursor.fetchall():
    print(event[0], "-", event[1])

connection.close()

print()
print("Limpieza completada.")
