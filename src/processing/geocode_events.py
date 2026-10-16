import sqlite3
import time
import requests

DATABASE_PATH = "data/intelligence.db"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

headers = {
    "User-Agent": "Geopolitical-OSINT-Platform/0.1"
}

connection = sqlite3.connect(DATABASE_PATH)
cursor = connection.cursor()

cursor.execute("""
SELECT
    id,
    location,
    country
FROM events
WHERE latitude IS NULL
AND longitude IS NULL
AND location IS NOT NULL
AND location != 'unknown'
""")

events = cursor.fetchall()

print("Eventos pendientes de geocodificación:", len(events))
print()

geocoded = 0
failed = 0

for event_id, location, country in events:
    query = f"{location}, {country}"

    params = {
        "q": query,
        "format": "jsonv2",
        "limit": 1
    }

    try:
        response = requests.get(
            NOMINATIM_URL,
            params=params,
            headers=headers,
            timeout=30
        )

        response.raise_for_status()

        results = response.json()

        if not results:
            print("NO ENCONTRADO:", query)
            failed += 1
            time.sleep(1)
            continue

        latitude = float(results[0]["lat"])
        longitude = float(results[0]["lon"])

        cursor.execute("""
        UPDATE events
        SET
            latitude = ?,
            longitude = ?
        WHERE id = ?
        """, (
            latitude,
            longitude,
            event_id
        ))

        connection.commit()

        geocoded += 1

        print(
            "OK:",
            event_id,
            "-",
            location,
            "→",
            latitude,
            longitude
        )

    except requests.RequestException as error:
        print(
            "ERROR:",
            event_id,
            "-",
            location,
            "-",
            error
        )

        failed += 1

    time.sleep(1)

connection.close()

print()
print("Geocodificación terminada.")
print("Eventos geocodificados:", geocoded)
print("Eventos sin resolver:", failed)
