"""Diagnóstico de frescura, fuentes y cobertura. Solo lectura."""
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

def table_exists(db, table):
    return db.execute('SELECT 1 FROM sqlite_master WHERE type=? AND name=?', ('table', table)).fetchone() is not None

def rows(db, table):
    if not table_exists(db, table): return []
    return [dict(r) for r in db.execute('SELECT * FROM "' + table + '"')]

def date_parse(value):
    if not value: return None
    text = str(value).strip()
    try:
        parsed = datetime.fromisoformat(text.replace('Z', '+00:00'))
        return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)
    except (ValueError, OverflowError):
        return None

def first_value(row, names):
    for name in names:
        if row.get(name) not in (None, ''): return row[name]
    return None

def analyze(db_path=None, reference_time=None):
    now = reference_time or datetime.now(timezone.utc)
    if now.tzinfo is None: now = now.replace(tzinfo=timezone.utc)
    with sqlite3.connect(str(db_path or DATABASE)) as db:
        db.row_factory = sqlite3.Row
        articles = rows(db, 'articles')
        runs = rows(db, 'meridian_operation_runs')
        alerts = rows(db, 'triage_alerts_v17')
        events = rows(db, 'events')
    domains = Counter()
    recent_7d = 0
    older_30d = 0
    missing_dates = 0
    future_dates = 0
    dated = 0
    latest_article = None
    for article in articles:
        url = first_value(article, ('url', 'article_url', 'source_url', 'link'))
        if url:
            try:
                host = (urlsplit(str(url)).hostname or '').lower()
                if host: domains[host] += 1
            except ValueError: pass
        raw = first_value(article, ('published_at', 'publication_date', 'published_date', 'date', 'pub_date', 'seendate'))
        parsed = date_parse(raw)
        if parsed is None:
            missing_dates += 1
            continue
        dated += 1
        if latest_article is None or parsed > latest_article: latest_article = parsed
        age_days = (now - parsed).total_seconds() / 86400
        if age_days < -1: future_dates += 1
        elif age_days <= 7: recent_7d += 1
        if age_days > 30: older_30d += 1
    runs.sort(key=lambda x: str(x.get('started_at') or ''), reverse=True)
    latest_run = runs[0] if runs else None
    last_success = next((r for r in runs if r.get('status') == 'success'), None)
    active_alerts = sum(r.get('status') == 'active' for r in alerts)
    warnings = []
    if not articles: warnings.append('No hay artículos almacenados.')
    if articles and not dated: warnings.append('No se han podido interpretar fechas de publicación: no se puede medir frescura.')
    if missing_dates: warnings.append(f'{missing_dates} artículos sin fecha interpretable.')
    if future_dates: warnings.append(f'{future_dates} artículos presentan fechas futuras; revisar zona horaria y origen.')
    if len(domains) < 2 and articles: warnings.append('Menos de dos dominios detectables: independencia de fuentes no evaluable.')
    if not last_success: warnings.append('No consta una ejecución completa satisfactoria en el historial disponible.')
    if latest_run and latest_run.get('status') != 'success': warnings.append('La última ejecución del pipeline no fue satisfactoria.')
    return {
        'country': 'Niger', 'version': 33, 'generated_at': now.isoformat(),
        'summary': {'articles': len(articles), 'events_in_database': len(events),
                    'domains': len(domains), 'articles_dated': dated,
                    'articles_last_7_days': recent_7d, 'articles_over_30_days': older_30d,
                    'articles_missing_or_invalid_dates': missing_dates,
                    'articles_with_future_dates': future_dates,
                    'active_alerts': active_alerts, 'pipeline_runs': len(runs),
                    'last_pipeline_status': latest_run.get('status') if latest_run else None,
                    'last_successful_run_at': last_success.get('finished_at') if last_success else None,
                    'latest_article_date': latest_article.isoformat() if latest_article else None},
        'source_distribution': [{'domain': k, 'articles': v} for k,v in domains.most_common()],
        'warnings': warnings,
        'limitations': ['Las fechas se leen de las columnas disponibles; no se infiere su validez.',
                        'Distintos dominios no garantizan independencia editorial.',
                        'La antigüedad de artículos no mide por sí sola cobertura de sucesos.',
                        'Los eventos registrados y las alertas no se verifican en este diagnóstico.'],
        'automatic_confirmation': False,
    }

def csv_safe(value):
    s = str(value if value is not None else '')
    return "'" + s if s.lstrip().startswith(('=', '+', '-', '@', '\t', '\r')) else s

def export_csv(report):
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(['domain', 'articles'])
    for row in report['source_distribution']:
        writer.writerow([csv_safe(row['domain']), row['articles']])
    return out.getvalue()

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--export', action='store_true')
    args = parser.parse_args()
    report = analyze()
    if args.export:
        target = ROOT / 'data/exports/observability_v33.json'
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print('EXPORTADO:', target)
    print(json.dumps(report, ensure_ascii=False, indent=2))
