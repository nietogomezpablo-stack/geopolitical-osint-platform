import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src/processing'))
from meridian_correlations_v26_v29 import analyze, similarity, csv_safe, export_csv

class TestCorrelations(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / 'test.db'
        with sqlite3.connect(self.db) as con:
            con.executescript("""
                CREATE TABLE articles(id INTEGER PRIMARY KEY, title TEXT, url TEXT, content TEXT);
                CREATE TABLE triage_alerts_v17(id INTEGER PRIMARY KEY, candidate_key TEXT);
                INSERT INTO articles VALUES (1,'Ataque en Agadez el 2026-10-01','https://a.example/x','Reportado el 2026-10-01');
                INSERT INTO articles VALUES (2,'Ataque en Agadez el 2026-10-02','https://b.example/y','Reportado el 2026-10-02');
                INSERT INTO articles VALUES (3,'Economía regional y agricultura','https://c.example/z','');
                INSERT INTO triage_alerts_v17 VALUES (1,'armed_attack:9');
            """)
    def tearDown(self):
        self.tmp.cleanup()
    def test_similarity(self):
        self.assertGreater(similarity('Ataque en Agadez', 'Ataque en Agadez'), 0.99)
    def test_empty(self):
        self.assertEqual(similarity('', ''), 0)
    def test_report(self):
        r = analyze(self.db, threshold=0.6)
        self.assertEqual(r['summary']['articles'], 3)
        self.assertEqual(r['summary']['alerts'], 1)
        self.assertFalse(r['automatic_confirmation'])
    def test_discrepancy_only_candidate(self):
        r = analyze(self.db, threshold=0.6)
        self.assertTrue(any(x['type'] == 'different_dates_mentioned' for x in r['potential_discrepancies']))
        self.assertTrue(all(x['status'] == 'requires_manual_review' for x in r['potential_discrepancies']))
    def test_csv_safe(self):
        self.assertEqual(csv_safe('=1+1'), "'=1+1")
    def test_csv(self):
        self.assertIn('article_a', export_csv(analyze(self.db)))
    def test_missing_optional_table(self):
        with sqlite3.connect(self.db) as con:
            con.execute('DROP TABLE triage_alerts_v17')
        self.assertEqual(analyze(self.db)['summary']['alerts'], 0)

if __name__ == '__main__':
    unittest.main()
