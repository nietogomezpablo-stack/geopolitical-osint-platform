"""Análisis documental exploratorio. No verifica ni confirma eventos."""
import csv
import io
import json
import re
import sqlite3
import unicodedata
from collections import defaultdict
from datetime import datetime, timezone
from difflib import SequenceMatcher
from itertools import combinations
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
DB = ROOT / 'data/intelligence.db'
STOPWORDS = frozenset('de del la las el los un una y o en a al por para con que se su sus sobre entre desde tras the and for with from this that into after niger nigerien nigerian news'.split())
DATE_RE = re.compile(r'\b(?:19|20)\d{2}-\d{2}-\d{2}\b')
# Solo coordenadas explícitas; los nombres de lugares no se infieren automáticamente.
COORD_RE = re.compile(r'(?<!\d)(-?\d{1,2}\.\d{3,})\s*[,;]\s*(-?\d{1,3}\.\d{3,})(?!\d)')

def table_exists(db, table):
    return db.execute('SELECT 1 FROM sqlite_master WHERE type=? AND name=?', ('table', table)).fetchone() is not None

def rows(db, table):
    if table not in {'articles', 'triage_alerts_v17'} or not table_exists(db, table):
        return []
    return [dict(row) for row in db.execute('SELECT * FROM "' + table + '"')]

def first_value(record, names):
    for name in names:
        value = record.get(name)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ''

def normalized(text):
    text = unicodedata.normalize('NFKD', str(text or '')).casefold()
    text = ''.join(c for c in text if not unicodedata.combining(c))
    return re.sub(r'\s+', ' ', re.sub(r'[^\w\s]', ' ', text)).strip()

def tokens(text):
    return {w for w in normalized(text).split() if len(w) >= 3 and w not in STOPWORDS}

def similarity(a, b):
    a, b = normalized(a), normalized(b)
    if not a or not b:
        return 0.0
    ta, tb = tokens(a), tokens(b)
    jaccard = len(ta & tb) / len(ta | tb) if (ta | tb) else 0.0
    sequence = SequenceMatcher(None, a, b).ratio()
    return round(0.65 * jaccard + 0.35 * sequence, 4)

def host(url):
    try:
        hostname = (urlsplit(url).hostname or '').lower().rstrip('.')
        return hostname.removeprefix('www.')
    except (TypeError, ValueError):
        return ''

def collect_articles(db):
    result = []
    for index, article in enumerate(rows(db, 'articles')):
        title = first_value(article, ('title', 'headline', 'name'))
        url = first_value(article, ('url', 'article_url', 'source_url', 'link'))
        date = first_value(article, ('published_at', 'publication_date', 'published', 'date', 'seendate'))
        body = first_value(article, ('text', 'content', 'body', 'summary', 'description'))
        result.append({'id': str(article.get('id', index)), 'title': title,
                       'url': url, 'domain': host(url), 'date': date,
                       'body_excerpt': body[:500]})
    return result

def article_pairs(articles, threshold=0.74, max_articles=2000):
    """Pares sugeridos por similitud de títulos; no equivalen a un mismo evento."""
    selected = [a for a in articles if a['title']]
    if len(selected) > max_articles:
        selected = selected[:max_articles]
    result = []
    for a, b in combinations(selected, 2):
        if a['id'] == b['id']:
            continue
        score = similarity(a['title'], b['title'])
        if score >= threshold:
            result.append({'article_a': a['id'], 'article_b': b['id'],
                           'title_a': a['title'], 'title_b': b['title'],
                           'similarity': score, 'domain_a': a['domain'],
                           'domain_b': b['domain'],
                           'same_domain': bool(a['domain'] and a['domain'] == b['domain']),
                           'assessment': 'possible_same_story_manual_review'})
    return sorted(result, key=lambda x: (-x['similarity'], x['article_a'], x['article_b']))

def source_analysis(articles, pairs):
    domains = defaultdict(list)
    for article in articles:
        if article['domain']:
            domains[article['domain']].append(article['id'])
    same_domain = sum(p['same_domain'] for p in pairs)
    return {'unique_domains': len(domains),
            'domain_article_counts': [{'domain': domain, 'count': len(ids)}
                                      for domain, ids in sorted(domains.items(), key=lambda x: (-len(x[1]), x[0]))],
            'similar_title_pairs_same_domain': same_domain,
            'similar_title_pairs_different_domains': len(pairs) - same_domain,
            'caution': 'Dominios distintos no garantizan fuentes independientes: pueden republicar la misma agencia.'}

def possible_discrepancies(pairs, articles):
    lookup = {a['id']: a for a in articles}
    findings = []
    for pair in pairs:
        a, b = lookup[pair['article_a']], lookup[pair['article_b']]
        dates = [set(DATE_RE.findall(a['title'] + ' ' + a['body_excerpt'])),
                 set(DATE_RE.findall(b['title'] + ' ' + b['body_excerpt']))]
        if dates[0] and dates[1] and dates[0].isdisjoint(dates[1]):
            findings.append({'article_a': a['id'], 'article_b': b['id'],
                             'type': 'different_dates_mentioned',
                             'values_a': sorted(dates[0]), 'values_b': sorted(dates[1]),
                             'status': 'requires_manual_review'})
        coords = [set(COORD_RE.findall(a['body_excerpt'])), set(COORD_RE.findall(b['body_excerpt']))]
        if coords[0] and coords[1] and coords[0].isdisjoint(coords[1]):
            findings.append({'article_a': a['id'], 'article_b': b['id'],
                             'type': 'different_coordinates_mentioned',
                             'values_a': [list(x) for x in sorted(coords[0])],
                             'values_b': [list(x) for x in sorted(coords[1])],
                             'status': 'requires_manual_review'})
    return findings

def analyze(db_path=None, threshold=0.74):
    path = Path(db_path) if db_path else DB
    if not path.is_file():
        raise FileNotFoundError('Base de datos no encontrada: ' + str(path))
    with sqlite3.connect(path) as db:
        db.row_factory = sqlite3.Row
        articles = collect_articles(db)
        alerts = rows(db, 'triage_alerts_v17')
    pairs = article_pairs(articles, threshold=threshold)
    sources = source_analysis(articles, pairs)
    discrepancies = possible_discrepancies(pairs, articles)
    return {'country': 'Niger', 'version': 29,
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'summary': {'articles': len(articles), 'alerts': len(alerts),
                        'possible_similar_pairs': len(pairs),
                        'domains': sources['unique_domains'],
                        'potential_discrepancies': len(discrepancies)},
            'similar_articles': pairs, 'sources': sources,
            'potential_discrepancies': discrepancies,
            'methodology': {'title_similarity_threshold': threshold,
                            'similarity_is_not_event_identity': True,
                            'different_dates_are_not_proven_contradictions': True,
                            'different_domains_are_not_proven_independent_sources': True,
                            'maximum_articles_compared': 2000},
            'automatic_confirmation': False}

def csv_safe(value):
    s = str(value if value is not None else '')
    return "'" + s if s.lstrip().startswith(('=', '+', '-', '@', '\t', '\r')) else s

def export_csv(report):
    stream = io.StringIO()
    writer = csv.writer(stream)
    fields = ['article_a', 'article_b', 'title_a', 'title_b', 'similarity', 'domain_a', 'domain_b', 'same_domain', 'assessment']
    writer.writerow(fields)
    for pair in report['similar_articles']:
        writer.writerow([csv_safe(pair.get(key)) for key in fields])
    return stream.getvalue()

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--export', action='store_true')
    args = parser.parse_args()
    report = analyze()
    if args.export:
        output = ROOT / 'data/exports/meridian_correlations_v29.json'
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print('Informe:', output)
    print(json.dumps(report['summary'], ensure_ascii=False, indent=2))
