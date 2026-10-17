import json
import sys
import time
from pathlib import Path

import requests

API_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
OUTPUT = Path("data/raw/gdelt_niger.json")

PARAMS = {
    "query": '"Niger" -Nigeria -"Niger Delta"',
    "mode": "ArtList",
    "maxrecords": 50,
    "format": "json",
}

HEADERS = {
    "User-Agent": "Meridian-OSINT/0.1"
}


def main():
    print("Meridian OSINT - GDELT Collector - Niger")

    for attempt in range(1, 4):
        try:
            response = requests.get(
                API_URL,
                params=PARAMS,
                headers=HEADERS,
                timeout=30,
            )

            print(
                f"Intento {attempt}/3 - "
                f"HTTP {response.status_code}"
            )

            if response.status_code == 429:
                if attempt < 3:
                    wait = 5 * attempt
                    print(f"Esperando {wait} segundos...")
                    time.sleep(wait)
                    continue

                raise RuntimeError(
                    "GDELT ha limitado las peticiones."
                )

            response.raise_for_status()

            data = response.json()
            articles = data.get("articles", [])

            if not isinstance(articles, list):
                raise ValueError(
                    "Respuesta GDELT inesperada: "
                    "'articles' no es una lista."
                )

            if not articles:
                raise ValueError(
                    "GDELT no ha devuelto artículos. "
                    "No se sobrescribirán los datos anteriores."
                )

            OUTPUT.parent.mkdir(
                parents=True,
                exist_ok=True
            )

            # Escritura temporal para no corromper
            # el archivo anterior si algo falla.
            temporary = OUTPUT.with_suffix(".json.tmp")

            with temporary.open(
                "w",
                encoding="utf-8"
            ) as file:
                json.dump(
                    data,
                    file,
                    indent=4,
                    ensure_ascii=False
                )

            temporary.replace(OUTPUT)

            print(f"Noticias descargadas: {len(articles)}")
            print(f"Guardadas en: {OUTPUT}")

            return

        except (
            requests.RequestException,
            ValueError,
            RuntimeError
        ) as error:
            print(f"Error: {error}")

            if attempt < 3:
                wait = 5 * attempt
                print(f"Reintentando en {wait} segundos...")
                time.sleep(wait)

    print("ERROR: No se pudieron descargar noticias.")
    sys.exit(1)


if __name__ == "__main__":
    main()
