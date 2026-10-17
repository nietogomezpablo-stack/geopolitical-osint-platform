import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src/processing"))

import intelligence_reports_v9 as reports


class TestReportsV9(unittest.TestCase):

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()

        self.db = Path(self.temp.name) / "reports.db"
        self.output = Path(self.temp.name) / "output"

        self.db_patch = patch.object(
            reports,
            "DATABASE",
            self.db,
        )

        self.output_patch = patch.object(
            reports,
            "OUTPUT",
            self.output,
        )

        self.db_patch.start()
        self.output_patch.start()

    def tearDown(self):
        self.db_patch.stop()
        self.output_patch.stop()
        self.temp.cleanup()

    def sample(self):
        return {
            "country": "Niger",
            "title": "Test report",
            "generated_at": "2026-10-17T10:00:00Z",
            "executive_summary": {
                "registered_events": 0,
                "unverified_candidates": 1,
            },
            "candidate_investigations": [{
                "title": "<script>alert(1)</script>",
                "event_type": "armed_attack",
                "investigation_status": "pending",
                "priority": "high",
                "source_urls": [
                    "https://example.org/news"
                ],
            }],
        }

    def test_report_hash_stable(self):
        first = self.sample()
        second = self.sample()

        second["generated_at"] = "2026-10-18T10:00:00Z"

        self.assertEqual(
            reports.report_digest(first),
            reports.report_digest(second),
        )

    def test_save_report(self):
        result = reports.save_report(self.sample())

        self.assertEqual(result["id"], 1)
        self.assertTrue(
            Path(result["path"]).exists()
        )

    def test_list_reports(self):
        reports.save_report(self.sample())

        result = reports.list_reports()

        self.assertEqual(
            len(result["reports"]),
            1,
        )

    def test_get_report(self):
        result = reports.save_report(self.sample())

        loaded = reports.get_report(result["id"])

        self.assertEqual(
            loaded["title"],
            "Test report",
        )

    def test_missing_report(self):
        self.assertIsNone(
            reports.get_report(999)
        )

    def test_html_escaping(self):
        output = reports.render_html(self.sample())

        self.assertNotIn(
            "<script>alert(1)</script>",
            output,
        )

        self.assertIn(
            "&lt;script&gt;",
            output,
        )


if __name__ == "__main__":
    unittest.main()
