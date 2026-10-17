import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src/processing"))

import intelligence_triage_alerts_v17 as alerts


def sample_report(priority="critical", contradicted=1):
    return {
        "candidates": [{
            "candidate_key": "attack:1",
            "triage_priority": priority,
            "contradicted_checks": contradicted,
            "reasons": [
                {"code": "high_priority_task"},
                {"code": "missing_documentation"},
            ],
        }],
        "verification_error": None,
    }


class TestTriageAlertsV17(unittest.TestCase):

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.database = Path(self.temp.name) / "test.db"

    def tearDown(self):
        self.temp.cleanup()

    def test_initialize(self):
        alerts.initialize(self.database)

        result = alerts.summary(self.database)

        self.assertEqual(
            result["counts"]["active"],
            0,
        )

    def test_build_alerts(self):
        result = alerts.build_alerts(
            sample_report()
        )

        self.assertEqual(len(result), 4)

    def test_create_alerts(self):
        result = alerts.synchronize(
            sample_report(),
            self.database,
        )

        self.assertEqual(result["created"], 4)

    def test_no_duplicates(self):
        alerts.synchronize(
            sample_report(),
            self.database,
        )

        result = alerts.synchronize(
            sample_report(),
            self.database,
        )

        self.assertEqual(result["created"], 0)
        self.assertEqual(result["updated"], 0)

    def test_resolve_alerts(self):
        alerts.synchronize(
            sample_report(),
            self.database,
        )

        result = alerts.synchronize(
            {
                "candidates": [],
                "verification_error": None,
            },
            self.database,
        )

        self.assertEqual(result["resolved"], 4)

    def test_reactivate_alert(self):
        alerts.synchronize(
            sample_report(),
            self.database,
        )

        alerts.synchronize(
            {
                "candidates": [],
                "verification_error": None,
            },
            self.database,
        )

        result = alerts.synchronize(
            sample_report(),
            self.database,
        )

        self.assertEqual(result["updated"], 4)

    def test_mark_read(self):
        alerts.synchronize(
            sample_report(),
            self.database,
        )

        current = alerts.list_alerts(
            database=self.database,
        )

        alert_id = current["alerts"][0]["id"]

        result = alerts.mark_read(
            alert_id,
            self.database,
        )

        self.assertTrue(result["is_read"])

    def test_unknown_alert(self):
        self.assertIsNone(
            alerts.mark_read(
                999,
                self.database,
            )
        )

    def test_summary(self):
        alerts.synchronize(
            sample_report(),
            self.database,
        )

        result = alerts.summary(self.database)

        self.assertEqual(
            result["counts"]["active"],
            4,
        )

    def test_invalid_filter(self):
        with self.assertRaises(ValueError):
            alerts.list_alerts(
                status="unknown",
                database=self.database,
            )

    def test_incomplete_verification(self):
        with self.assertRaises(RuntimeError):
            alerts.synchronize(
                {
                    "candidates": [],
                    "verification_error": "Test error",
                },
                self.database,
            )


if __name__ == "__main__":
    unittest.main()
