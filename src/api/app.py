import sqlite3
from flask import Flask, jsonify, request, send_from_directory

app = Flask(__name__)

DATABASE_PATH = "data/intelligence.db"


def get_connection():
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


@app.route("/")
def index():
    return send_from_directory(
        "../../web",
        "map.html"
    )


@app.route("/graph")
def graph():
    return send_from_directory(
        "../../web",
        "graph.html"
    )


@app.route("/api/health")
def health():
    return jsonify({
        "status": "ok",
        "service": "Geopolitical OSINT Platform API"
    })


@app.route("/api/events")
def get_events():
    country = request.args.get("country")
    event_type = request.args.get("type")

    connection = get_connection()
    cursor = connection.cursor()

    query = """
    SELECT
        id,
        title,
        event_date,
        event_type,
        country,
        location,
        latitude,
        longitude,
        description,
        confidence
    FROM events
    WHERE 1 = 1
    """

    parameters = []

    if country:
        query += " AND country = ?"
        parameters.append(country)

    if event_type:
        query += " AND event_type = ?"
        parameters.append(event_type)

    query += " ORDER BY event_date DESC"

    cursor.execute(
        query,
        parameters
    )

    events = [
        dict(row)
        for row in cursor.fetchall()
    ]

    connection.close()

    return jsonify({
        "count": len(events),
        "events": events
    })


@app.route("/api/events/<int:event_id>")
def get_event(event_id):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
    SELECT
        id,
        title,
        event_date,
        event_type,
        country,
        location,
        latitude,
        longitude,
        description,
        confidence
    FROM events
    WHERE id = ?
    """, (event_id,))

    event_row = cursor.fetchone()

    if event_row is None:
        connection.close()

        return jsonify({
            "error": "Event not found"
        }), 404

    event = dict(event_row)

    cursor.execute("""
    SELECT
        ent.id,
        ent.canonical_name,
        ent.entity_type,
        ee.relation_type
    FROM event_entities ee
    JOIN entities ent
        ON ee.entity_id = ent.id
    WHERE ee.event_id = ?
    """, (event_id,))

    event["entities"] = [
        dict(row)
        for row in cursor.fetchall()
    ]

    cursor.execute("""
    SELECT
        a.id,
        a.title,
        a.date,
        a.url,
        a.domain
    FROM event_articles ea
    JOIN articles a
        ON ea.article_id = a.id
    WHERE ea.event_id = ?
    ORDER BY a.date
    """, (event_id,))

    sources = [
        dict(row)
        for row in cursor.fetchall()
    ]

    event["sources"] = sources

    domains = {
        source["domain"]
        for source in sources
        if source["domain"]
    }

    event["corroboration"] = {
        "source_count": len(sources),
        "independent_domains": len(domains),
        "domains": sorted(domains)
    }

    connection.close()

    return jsonify(event)


@app.route("/api/stats")
def get_stats():
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("SELECT COUNT(*) FROM events")
    total_events = cursor.fetchone()[0]

    cursor.execute("""
    SELECT COUNT(*)
    FROM events
    WHERE latitude IS NOT NULL
    AND longitude IS NOT NULL
    """)
    geolocated_events = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM entities")
    total_entities = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM articles")
    total_sources = cursor.fetchone()[0]

    cursor.execute("""
    SELECT
        event_type,
        COUNT(*) AS total
    FROM events
    GROUP BY event_type
    ORDER BY total DESC
    """)

    events_by_type = [
        {
            "event_type": row["event_type"],
            "total": row["total"]
        }
        for row in cursor.fetchall()
    ]

    connection.close()

    return jsonify({
        "events": total_events,
        "geolocated_events": geolocated_events,
        "entities": total_entities,
        "sources": total_sources,
        "events_by_type": events_by_type
    })


@app.route("/api/graph")
def get_graph():
    connection = get_connection()
    cursor = connection.cursor()

    nodes = {}
    edges = []

    cursor.execute("""
    SELECT
        id,
        title,
        event_date,
        event_type,
        country,
        confidence
    FROM events
    """)

    for event in cursor.fetchall():
        node_id = f"event:{event['id']}"

        nodes[node_id] = {
            "id": node_id,
            "label": event["title"],
            "type": "event",
            "properties": {
                "event_date": event["event_date"],
                "event_type": event["event_type"],
                "country": event["country"],
                "confidence": event["confidence"]
            }
        }

    cursor.execute("""
    SELECT
        ee.event_id,
        ee.entity_id,
        ee.relation_type,
        ent.canonical_name,
        ent.entity_type
    FROM event_entities ee
    JOIN entities ent
        ON ee.entity_id = ent.id
    """)

    for relation in cursor.fetchall():
        node_id = f"entity:{relation['entity_id']}"

        nodes[node_id] = {
            "id": node_id,
            "label": relation["canonical_name"],
            "type": "entity",
            "properties": {
                "entity_type": relation["entity_type"]
            }
        }

        edges.append({
            "source": f"event:{relation['event_id']}",
            "target": node_id,
            "relation": relation["relation_type"]
        })

    cursor.execute("""
    SELECT
        el.event_id,
        el.location_id,
        el.relation_type,
        l.canonical_name,
        l.country,
        l.latitude,
        l.longitude
    FROM event_locations el
    JOIN locations l
        ON el.location_id = l.id
    """)

    for relation in cursor.fetchall():
        node_id = f"location:{relation['location_id']}"

        nodes[node_id] = {
            "id": node_id,
            "label": relation["canonical_name"],
            "type": "location",
            "properties": {
                "country": relation["country"],
                "latitude": relation["latitude"],
                "longitude": relation["longitude"]
            }
        }

        edges.append({
            "source": f"event:{relation['event_id']}",
            "target": node_id,
            "relation": relation["relation_type"]
        })

    cursor.execute("""
    SELECT
        ea.event_id,
        ea.article_id,
        a.title,
        a.date,
        a.url,
        a.domain
    FROM event_articles ea
    JOIN articles a
        ON ea.article_id = a.id
    """)

    for relation in cursor.fetchall():
        node_id = f"article:{relation['article_id']}"

        nodes[node_id] = {
            "id": node_id,
            "label": relation["title"],
            "type": "source",
            "properties": {
                "date": relation["date"],
                "url": relation["url"],
                "domain": relation["domain"]
            }
        }

        edges.append({
            "source": node_id,
            "target": f"event:{relation['event_id']}",
            "relation": "supports"
        })

    connection.close()

    return jsonify({
        "nodes": list(nodes.values()),
        "edges": edges
    })




# Candidatos pendientes de revisión: no son acontecimientos confirmados.
@app.route("/api/event-candidates", methods=["GET"])
def get_event_candidates():
    from flask import jsonify
    import json
    from pathlib import Path

    candidates_file = Path("data/processed/event_candidates.json")

    if not candidates_file.exists():
        return jsonify({
            "count": 0,
            "candidates": [],
            "message": "Todavía no se ha generado el archivo de candidatos."
        })

    try:
        candidates = json.loads(
            candidates_file.read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError):
        return jsonify({
            "error": "No se pudo leer el archivo de candidatos."
        }), 500

    return jsonify({
        "count": len(candidates),
        "candidates": candidates,
        "verified": False
    })




@app.route("/api/intelligence-v4")
def meridian_intelligence_v4():
    import json
    from pathlib import Path
    from flask import jsonify

    root = Path(__file__).resolve().parents[2]
    path = root / "data/processed/event_intelligence_v4.json"

    if not path.exists():
        return jsonify({
            "version": 4,
            "country": "Niger",
            "summary": {
                "candidates": 0,
                "clusters": 0,
                "possible_relationships": 0,
                "source_domains": 0,
                "verified_events_created": 0,
            },
            "candidates": [],
            "clusters": [],
            "relationships": [],
        })

    return jsonify(
        json.loads(path.read_text(encoding="utf-8"))
    )



@app.route("/api/investigations", methods=["GET"])
def meridian_list_investigations():
    import sys
    from pathlib import Path
    from flask import jsonify

    processing = (
        Path(__file__).resolve().parents[1]
        / "processing"
    )

    if str(processing) not in sys.path:
        sys.path.insert(0, str(processing))

    from investigation_manager import list_investigations

    candidates = list_investigations()

    return jsonify({
        "country": "Niger",
        "count": len(candidates),
        "candidates": candidates,
    })


@app.route("/api/investigations/<path:key>", methods=["PUT"])
def meridian_update_investigation(key):
    import sys
    from pathlib import Path
    from flask import jsonify, request

    processing = (
        Path(__file__).resolve().parents[1]
        / "processing"
    )

    if str(processing) not in sys.path:
        sys.path.insert(0, str(processing))

    from investigation_manager import update_investigation

    if not request.is_json:
        return jsonify({
            "error": "Se requiere JSON"
        }), 415

    payload = request.get_json(silent=True)

    if not isinstance(payload, dict):
        return jsonify({
            "error": "JSON inválido"
        }), 400

    try:
        result = update_investigation(
            key,
            payload.get("status"),
            payload.get("notes", "")
        )
    except ValueError as error:
        return jsonify({
            "error": str(error)
        }), 400

    return jsonify(result)


@app.route("/api/investigations/<path:key>/history")
def meridian_investigation_history(key):
    import sys
    from pathlib import Path
    from flask import jsonify

    processing = (
        Path(__file__).resolve().parents[1]
        / "processing"
    )

    if str(processing) not in sys.path:
        sys.path.insert(0, str(processing))

    from investigation_manager import get_history

    try:
        history = get_history(key)
    except ValueError as error:
        return jsonify({
            "error": str(error)
        }), 404

    return jsonify({
        "candidate_key": key,
        "history": history,
    })



@app.route("/api/intelligence-v5")
def meridian_intelligence_v5():
    import sys
    from pathlib import Path
    from flask import jsonify

    processing = (
        Path(__file__).resolve().parents[1]
        / "processing"
    )

    if str(processing) not in sys.path:
        sys.path.insert(0, str(processing))

    from intelligence_analysis_v5 import build_report

    return jsonify(build_report())


@app.route("/api/intelligence-v5/export.csv")
def meridian_intelligence_v5_csv():
    import sys
    from pathlib import Path
    from flask import Response

    processing = (
        Path(__file__).resolve().parents[1]
        / "processing"
    )

    if str(processing) not in sys.path:
        sys.path.insert(0, str(processing))

    from intelligence_analysis_v5 import export_csv_text

    return Response(
        export_csv_text(),
        mimetype="text/csv",
        headers={
            "Content-Disposition":
                "attachment; filename=meridian_niger_v5.csv"
        },
    )


@app.route("/api/intelligence-v5/export.json")
def meridian_intelligence_v5_json():
    import sys
    from pathlib import Path
    from flask import Response

    processing = (
        Path(__file__).resolve().parents[1]
        / "processing"
    )

    if str(processing) not in sys.path:
        sys.path.insert(0, str(processing))

    from intelligence_analysis_v5 import build_report
    import json

    return Response(
        json.dumps(
            build_report(),
            ensure_ascii=False,
            indent=2,
        ),
        mimetype="application/json",
        headers={
            "Content-Disposition":
                "attachment; filename=meridian_niger_v5.json"
        },
    )



@app.route("/api/intelligence-v6/alerts", methods=["GET"])
def meridian_v6_alerts():
    import sys
    from pathlib import Path
    from flask import jsonify, request

    processing = (
        Path(__file__).resolve().parents[1]
        / "processing"
    )

    if str(processing) not in sys.path:
        sys.path.insert(0, str(processing))

    from intelligence_alerts_v6 import list_alerts

    unread = request.args.get("unread") == "1"

    return jsonify(list_alerts(unread_only=unread))


@app.route(
    "/api/intelligence-v6/alerts/synchronize",
    methods=["POST"]
)
def meridian_v6_synchronize():
    import sys
    from pathlib import Path
    from flask import jsonify

    processing = (
        Path(__file__).resolve().parents[1]
        / "processing"
    )

    if str(processing) not in sys.path:
        sys.path.insert(0, str(processing))

    from intelligence_alerts_v6 import synchronize

    return jsonify(synchronize())


@app.route(
    "/api/intelligence-v6/alerts/<int:alert_id>/read",
    methods=["PUT"]
)
def meridian_v6_mark_read(alert_id):
    import sys
    from pathlib import Path
    from flask import jsonify, request

    processing = (
        Path(__file__).resolve().parents[1]
        / "processing"
    )

    if str(processing) not in sys.path:
        sys.path.insert(0, str(processing))

    from intelligence_alerts_v6 import mark_read

    payload = request.get_json(silent=True)

    if not isinstance(payload, dict):
        return jsonify({
            "error": "Se requiere JSON válido"
        }), 400

    is_read = payload.get("is_read", True)

    if not isinstance(is_read, bool):
        return jsonify({
            "error": "is_read debe ser booleano"
        }), 400

    updated = mark_read(alert_id, is_read)

    if not updated:
        return jsonify({
            "error": "Alerta no encontrada"
        }), 404

    return jsonify({
        "id": alert_id,
        "is_read": is_read,
        "updated": True,
    })

if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True
    )
