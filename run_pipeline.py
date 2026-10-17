import subprocess
import sys
from datetime import datetime


PIPELINE_STEPS = [
    (
        "Recopilación de noticias de Níger",
        "src/collectors/gdelt_collector.py"
    ),
    (
        "Limpieza de datos GDELT",
        "src/processing/clean_gdelt.py"
    ),
    (
        "Importación de artículos",
        "src/database/import_articles.py"
    ),
    (
        "Extracción de texto",
        "src/processing/extract_article_text.py"
    ),
    (
        "Extracción de entidades",
        "src/processing/extract_entities.py"
    ),
    (
        "Normalización de entidades",
        "src/processing/normalize_entities.py"
    ),
    (
        "Entity Resolution",
        "src/processing/resolve_entities.py"
    ),
    (
        "Extracción y persistencia de eventos",
        "src/processing/build_event_candidates.py"
    ),
    (
        "Geocodificación",
        "src/processing/geocode_events.py"
    ),
    (
        "Persistencia de lugares",
        "src/processing/store_locations.py"
    ),
    (
        "Cálculo de confidence",
        "src/processing/calculate_confidence.py"
    ),
    (
        "Comprobación de base de datos",
        "src/database/check_database.py"
    ),
    (
        "Exportación GeoJSON",
        "src/processing/export_event_candidates.py"
        "src/processing/export_events_geojson.py"
    ),
    (
        "Exportación Intelligence JSON",
        "src/processing/export_intelligence_json.py"
    ),
    (
        "Exportación Knowledge Graph",
        "src/processing/export_knowledge_graph.py"
    )
]


def run_step(number, total, name, script):
    print()
    print("=" * 70)
    print(f"[{number}/{total}] {name}")
    print(f"Ejecutando: {script}")
    print("=" * 70)

    result = subprocess.run(
        [sys.executable, script]
    )

    if result.returncode != 0:
        print()
        print("PIPELINE DETENIDO")
        print(f"Ha fallado: {name}")
        print(f"Script: {script}")
        print(f"Código de salida: {result.returncode}")
        sys.exit(result.returncode)

    print()
    print(f"OK: {name}")


def main():
    start_time = datetime.now()

    print()
    print("GEOPOLITICAL OSINT PLATFORM")
    print("OSINT PROCESSING PIPELINE")
    print()
    print(
        "Inicio:",
        start_time.strftime("%Y-%m-%d %H:%M:%S")
    )

    total = len(PIPELINE_STEPS)

    for number, step in enumerate(
        PIPELINE_STEPS,
        start=1
    ):
        name, script = step

        run_step(
            number,
            total,
            name,
            script
        )

    end_time = datetime.now()
    duration = end_time - start_time

    print()
    print("=" * 70)
    print("PIPELINE COMPLETADO")
    print("=" * 70)
    print(
        "Fin:",
        end_time.strftime("%Y-%m-%d %H:%M:%S")
    )
    print(
        "Duración:",
        str(duration).split(".")[0]
    )


if __name__ == "__main__":
    main()
