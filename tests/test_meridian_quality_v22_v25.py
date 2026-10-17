import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(
    0,
    str(ROOT / "src/processing"),
)

from meridian_quality_v22_v25 import (
    analyze,
    canonical_url,
    csv_safe,
    export_csv,
)


class TestQualityV22V25(unittest.TestCase):

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()

        self.path = (
            Path(self.temp.name) / "test.db"
        )

        with sqlite3.connect(self.path) as db:
            db.executescript("""
                CREATE TABLE articles (
                    id INTEGER PRIMARY KEY,
                    url TEXT
                );

                CREATE TABLE events (
                    id INTEGER PRIMARY KEY
                );

                CREATE TABLE triage_alerts_v17 (
                    id INTEGER PRIMARY KEY,
                    candidate_key TEXT,
                    alert_type TEXT,
                    status TEXT
                );

                CREATE TABLE evidence_audits (
                    id INTEGER PRIMARY KEY,
                    candidate_key TEXT,
                    status TEXT
                );

                INSERT INTO articles VALUES
                    (1, 'https://example.com/news?utm_source=x'),
                    (2, 'https://example.com/news'),
                    (3, 'https://other.com/story');

                INSERT INTO events VALUES (1);

                INSERT INTO triage_alerts_v17 VALUES
                    (1, 'armed_attack:9',
                     'insufficient_documentation', 'active'),
                    (2, 'armed_attack:9',
                     'high_priority', 'active'),
                    (3, 'release:2',
                     'insufficient_documentation', 'active');
            """)

    def tearDown(self):
        self.temp.cleanup()

    def test_url_normalization(self):
        self.assertEqual(
            canonical_url(
                "http://example.com/news?utm_source=x"
            ),
            "https://example.com/news",
        )

    def test_duplicate_detection(self):
        report = analyze(self.path)

        self.assertEqual(
            report["summary"]["duplicate_article_records"],
            1,
        )

    def test_candidate_count(self):
        report = analyze(self.path)

        self.assertEqual(
            report["summary"]["candidate_references"],
            2,
        )

    def test_alert_count(self):
        report = analyze(self.path)

        self.assertEqual(
            report["summary"]["alerts_active"],
            3,
        )

    def test_events(self):
        report = analyze(self.path)

        self.assertEqual(
            report["summary"]["events_in_database"],
            1,
        )

    def test_review_required(self):
        report = analyze(self.path)

        self.assertTrue(
            all(
                item["review_required"]
                for item in report["candidates"]
            )
        )

    def test_no_auto_confirmation(self):
        report = analyze(self.path)

        self.assertFalse(
            report["automatic_confirmation"]
        )

    def test_csv_export(self):
        report = analyze(self.path)

        content = export_csv(report)

        self.assertIn(
            "armed_attack:9",
            content,
        )

    def test_csv_formula_protection(self):
        self.assertEqual(
            csv_safe("=SUM(1,2)"),
            "'=SUM(1,2)",
        )

    def test_missing_optional_tables(self):
        with sqlite3.connect(self.path) as db:
            db.execute(
                "DROP TABLE evidence_audits"
            )

        report = analyze(self.path)

        self.assertEqual(
            len(report["candidates"]),
            2,
        )


if __name__ == "__main__":
    unittest.main()
