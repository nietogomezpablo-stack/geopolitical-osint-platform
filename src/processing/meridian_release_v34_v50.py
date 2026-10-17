"""Meridian OSINT: paquete final V34-V50, diagnóstico local de solo lectura."""
import argparse
import csv
import io
import json
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
DATABASE = ROOT / 'data/intelligence.db'

MILESTONES = {
    34: 'Inventario de datos',
    35: 'Integridad referencial',
    36: 'Cobertura de artículos',
    37: 'Inventario de acontecimientos',
    38: 'Revisión de alertas',
    39: 'Estado de investigaciones',
    40: 'Estado de auditorías',
    41: 'Supervisión de ejecuciones',
    42: 'Distribución de fuentes',
    43: 'Detección de duplicados exactos',
    44: 'Calidad de metadatos',
    45: 'Antigüedad de las fuentes',
    46: 'Informe de riesgos',
    47: 'Exportación JSON',
    48: 'Exportación CSV segura',
    49: 'API de diagnóstico de solo lectura',
    50: 'Panel final y pruebas de aceptación',
}

def table_exists(db, name):
    return db.execute('SELECT 1 FROM sqlite_master WHERE type=? AND name=?', ('table', name)).fetchone() is not None

def rows(db, name):
    if not table_exists(db, name):
        return []
    return [dict(row) for row in db.execute('SELECT * FROM "' + name + '"')]

def first(row, names):
    for name in names:
        value = row.get(name)
        if value is not None and str(value).strip():
            return value
    return None

def parse_date(value):
    if value is None or str(value).strip() == '':
        return None
    try:
        parsed = datetime.fromisoformat(str(value).strip().replace('Z', '+00:00'))
        return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)
    except (ValueError, OverflowError, TypeError):
        return None

def normalized_url(value):
    if not value:
        return ''
    try:
        p = urlsplit(str(value).strip())
        host = (p.hostname or '').lower()
        if p.scheme.lower() not in ('http', 'https') or not host:
            return ''
        return host + (p.path.rstrip('/') or '/')
    except ValueError:
        return ''

def analyze(db_path=None, reference_time=None):
    now = reference_time or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    path = Path(db_path or DATABASE)
    if not path.is_file():
        raise FileNotFoundError('No existe la base de datos: ' + str(path))
    # SQLite en modo solo lectura: ningún análisis puede escribir en producción.
    with sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True) as db:
        db.row_factory = sqlite3.Row
        tables = {r['name'] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        integrity = db.execute('PRAGMA quick_check').fetchone()[0]
        articles = rows(db, 'articles')
        events = rows(db, 'events')
        alerts = rows(db, 'triage_alerts_v17')
        investigations = rows(db, 'investigations')
        audits = rows(db, 'evidence_audits')
        cases = rows(db, 'investigation_cases')
        tasks = rows(db, 'investigation_tasks')
        runs = rows(db, 'meridian_operation_runs')
        relations = {}
        for table, left, right in (
            ('event_articles', 'event_id', 'article_id'),
            ('event_entities', 'event_id', 'entity_id'),
            ('event_locations', 'event_id', 'location_id'),
        ):
            if table not in tables:
                relations[table] = {'present': False, 'orphaned': None}
                continue
            cols = {r['name'] for r in db.execute('PRAGMA table_info("' + table + '")')}
            if left not in cols or right not in cols:
                relations[table] = {'present': True, 'orphaned': None}
                continue
            target = {'event_articles': 'articles', 'event_entities': 'entities', 'event_locations': 'locations'}[table]
            if target not in tables:
                relations[table] = {'present': True, 'orphaned': None}
                continue
            # Los nombres de tabla y columna son constantes definidas arriba.
            count = db.execute(
                'SELECT COUNT(*) FROM "' + table + '" r '
                'LEFT JOIN events e ON r.event_id=e.id '
                'LEFT JOIN "' + target + '" t ON r."' + right + '"=t.id '
                'WHERE e.id IS NULL OR t.id IS NULL'
            ).fetchone()[0] if 'events' in tables else None
            relations[table] = {'present': True, 'orphaned': count}

    domains = Counter()
    urls = Counter()
    dated = recent = old = future = 0
    missing_url = missing_date = 0
    for article in articles:
        raw_url = first(article, ('url', 'article_url', 'source_url', 'link'))
        url = normalized_url(raw_url)
        if url:
            urls[url] += 1
            domains[url.split('/')[0]] += 1
        else:
            missing_url += 1
        date = parse_date(first(article, ('published_at', 'publication_date', 'published_date', 'date', 'seendate', 'created_at')))
        if date is None:
            missing_date += 1
        else:
            dated += 1
            days = (now - date).total_seconds() / 86400
            if days < -1:
                future += 1
            elif days <= 7:
                recent += 1
            if days > 30:
                old += 1

    active = [a for a in alerts if a.get('status') == 'active']
    candidates = sorted({str(a['candidate_key']) for a in alerts if a.get('candidate_key')})
    latest_run = max(runs, key=lambda r: str(r.get('started_at') or ''), default=None)
    duplicate_groups = sum(count > 1 for count in urls.values())
    duplicate_excess = sum(count - 1 for count in urls.values() if count > 1)
    warnings = []
    if integrity != 'ok':
        warnings.append('La comprobación de integridad SQLite no ha devuelto OK.')
    if not articles:
        warnings.append('No hay noticias almacenadas.')
    if missing_date:
        warnings.append(f'{missing_date} noticias sin fecha válida reconocible.')
    if missing_url:
        warnings.append(f'{missing_url} noticias sin URL válida reconocible.')
    if future:
        warnings.append(f'{future} noticias tienen fechas futuras.')
    if duplicate_excess:
        warnings.append(f'{duplicate_excess} registros comparten URL normalizada con otro artículo.')
    if active:
        warnings.append(f'{len(active)} alertas activas pendientes de revisión.')
    if latest_run and latest_run.get('status') != 'success':
        warnings.append('La última ejecución registrada no terminó correctamente.')
    for name, detail in relations.items():
        if detail['orphaned']:
            warnings.append(f'{name} tiene {detail["orphaned"]} relaciones huérfanas.')

    return {
        'country': 'Niger',
        'release': 50,
        'generated_at': now.isoformat(),
        'summary': {
            'articles': len(articles), 'events_recorded': len(events),
            'alerts_active': len(active), 'candidate_references': len(candidates),
            'investigations': len(investigations), 'audits': len(audits),
            'cases': len(cases), 'tasks': len(tasks), 'pipeline_runs': len(runs),
            'latest_pipeline_status': latest_run.get('status') if latest_run else None,
            'sqlite_integrity': integrity, 'unique_source_domains': len(domains),
            'duplicate_url_groups': duplicate_groups, 'duplicate_extra_records': duplicate_excess,
            'articles_last_7_days': recent, 'articles_older_than_30_days': old,
            'articles_missing_dates': missing_date, 'articles_missing_urls': missing_url,
            'articles_future_dated': future, 'warning_count': len(warnings),
        },
        'sources': [{'domain': k, 'articles': v} for k, v in domains.most_common(30)],
        'candidate_keys': candidates,
        'referential_integrity': relations,
        'warnings': warnings,
        'milestones': [{'version': v, 'feature': title} for v, title in MILESTONES.items()],
        'limitations': [
            'El informe es descriptivo y no verifica la veracidad de las noticias.',
            'Las alertas no son acontecimientos confirmados.',
            'La detección de duplicados es por URL normalizada, no por contenido.',
            'La antigüedad depende de la columna de fecha reconocida.',
            'No se ejecutan ni se modifican procesos, investigaciones o eventos.',
        ],
        'automatic_confirmation': False,
    }

def csv_cell(value):
    value = '' if value is None else str(value)
    return "'" + value if value.lstrip().startswith(('=', '+', '-', '@', '\t', '\r')) else value

def export_csv(report):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(('metric', 'value'))
    for key, value in report['summary'].items():
        writer.writerow((csv_cell(key), csv_cell(value)))
    return output.getvalue()

def export_json(report, output=None):
    path = Path(output or ROOT / 'data/exports/meridian_release_v50.json')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    return path

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--export', action='store_true')
    args = parser.parse_args()
    report = analyze()
    if args.export:
        print('INFORME:', export_json(report))
    print(json.dumps(report['summary'], ensure_ascii=False, indent=2))
    for warning in report['warnings']:
        print('REVISAR:', warning)
