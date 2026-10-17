import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src/processing'))
from meridian_release_v34_v50 import analyze, csv_cell, export_csv, normalized_url, parse_date, MILESTONES

class TestRelease(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'data.db'
        with sqlite3.connect(self.path) as db:
            db.executescript("""
                CREATE TABLE articles(id INTEGER PRIMARY KEY, url TEXT, published_at TEXT);
                CREATE TABLE events(id INTEGER PRIMARY KEY);
                CREATE TABLE triage_alerts_v17(id INTEGER PRIMARY KEY, candidate_key TEXT, status TEXT);
                CREATE TABLE meridian_operation_runs(id INTEGER PRIMARY KEY, started_at TEXT, status TEXT);
                INSERT INTO articles VALUES(1, 'https://news.test/a', '2026-10-15T00:00:00+00:00');
                INSERT INTO articles VALUES(2, 'http://news.test/a?utm_source=x', '2026-09-01T00:00:00+00:00');
                INSERT INTO articles VALUES(3, NULL, NULL);
                INSERT INTO events VALUES(1);
                INSERT INTO triage_alerts_v17 VALUES(1, 'armed_attack:9', 'active');
                INSERT INTO triage_alerts_v17 VALUES(2, 'armed_attack:9', 'active');
                INSERT INTO meridian_operation_runs VALUES(1, '2026-10-17', 'success');
            """)
        self.report = analyze(self.path, datetime(2026, 10, 17, tzinfo=timezone.utc))
    def tearDown(self):
        self.temp.cleanup()
    def test_versions(self):
        self.assertEqual(list(MILESTONES), list(range(34, 51)))
    def test_country(self):
        self.assertEqual(self.report['country'], 'Niger')
    def test_count(self):
        self.assertEqual(self.report['summary']['articles'], 3)
    def test_events(self):
        self.assertEqual(self.report['summary']['events_recorded'], 1)
    def test_alerts(self):
        self.assertEqual(self.report['summary']['alerts_active'], 2)
    def test_candidates(self):
        self.assertEqual(self.report['summary']['candidate_references'], 1)
    def test_duplicates(self):
        self.assertEqual(self.report['summary']['duplicate_extra_records'], 1)
    def test_missing(self):
        self.assertEqual(self.report['summary']['articles_missing_dates'], 1)
    def test_recent(self):
        self.assertEqual(self.report['summary']['articles_last_7_days'], 1)
    def test_old(self):
        self.assertEqual(self.report['summary']['articles_older_than_30_days'], 1)
    def test_integrity(self):
        self.assertEqual(self.report['summary']['sqlite_integrity'], 'ok')
    def test_no_confirmation(self):
        self.assertFalse(self.report['automatic_confirmation'])
    def test_csv_safe(self):
        self.assertEqual(csv_cell('=1+2'), "'=1+2")
    def test_csv_report(self):
        self.assertIn('articles,3', export_csv(self.report))
    def test_invalid_url(self):
        self.assertEqual(normalized_url('javascript:alert(1)'), '')
    def test_invalid_date(self):
        self.assertIsNone(parse_date('not-a-date'))
    def test_missing_db(self):
        with self.assertRaises(FileNotFoundError):
            analyze(self.path.parent / 'missing.db')

if __name__ == '__main__':
    unittest.main()
