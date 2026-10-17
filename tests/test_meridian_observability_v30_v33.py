import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src/processing'))
from meridian_observability_v30_v33 import analyze, date_parse, csv_safe, export_csv

class TestObservability(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'test.sqlite'
        with sqlite3.connect(self.path) as db:
            db.executescript("""
            CREATE TABLE articles(id INTEGER PRIMARY KEY, url TEXT, published_at TEXT);
            CREATE TABLE events(id INTEGER PRIMARY KEY);
            CREATE TABLE meridian_operation_runs(id INTEGER PRIMARY KEY, started_at TEXT, finished_at TEXT, status TEXT);
            CREATE TABLE triage_alerts_v17(id INTEGER PRIMARY KEY, status TEXT);
            INSERT INTO articles VALUES(1,'https://one.example/a','2026-10-15T00:00:00Z');
            INSERT INTO articles VALUES(2,'https://two.example/b','2026-09-01');
            INSERT INTO articles VALUES(3,'https://one.example/c',NULL);
            INSERT INTO events VALUES(1);
            INSERT INTO meridian_operation_runs VALUES(1,'2026-10-16','2026-10-16','success');
            INSERT INTO triage_alerts_v17 VALUES(1,'active');
            """)
        self.now = datetime(2026, 10, 17, tzinfo=timezone.utc)
    def tearDown(self): self.tmp.cleanup()
    def report(self): return analyze(self.path, self.now)
    def test_counts(self):
        s = self.report()['summary']
        self.assertEqual((s['articles'],s['domains'],s['events_in_database']), (3,2,1))
    def test_dates(self):
        s = self.report()['summary']
        self.assertEqual((s['articles_last_7_days'],s['articles_over_30_days'],s['articles_missing_or_invalid_dates']), (1,1,1))
    def test_pipeline(self): self.assertEqual(self.report()['summary']['last_pipeline_status'], 'success')
    def test_alerts(self): self.assertEqual(self.report()['summary']['active_alerts'], 1)
    def test_not_confirmed(self): self.assertFalse(self.report()['automatic_confirmation'])
    def test_csv(self): self.assertIn('one.example', export_csv(self.report()))
    def test_csv_injection(self): self.assertEqual(csv_safe('=1+2'), "'=1+2")
    def test_bad_date(self): self.assertIsNone(date_parse('not a date'))
    def test_optional_tables(self):
        with sqlite3.connect(self.path) as db: db.execute('DROP TABLE triage_alerts_v17')
        self.assertEqual(self.report()['summary']['active_alerts'], 0)
if __name__ == '__main__': unittest.main()
