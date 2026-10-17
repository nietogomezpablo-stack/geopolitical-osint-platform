import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src/processing"))

import intelligence_alerts_v6 as alerts


def candidate(
    key="armed_attack:1",
    priority="high",
    status="pending",
):
    return {
        "title": "Test Niger event",
        "investigation": {
            "candidate_key": key,
            "status": status,
        },
        "analysis_v5": {
            "priority": priority,
        },
    }


class TestAlertsV6(unittest.TestCase):

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.database = Path(self.temp.name) / "test.db"
        self.patch = patch.object(alerts, "DB", self.database)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.temp.cleanup()

    def test_new_candidate(self):
        result = alerts.synchronize({
            "candidates": [candidate()]
        })

        self.assertEqual(result["new_alerts"], 1)
        self.assertEqual(alerts.list_alerts()["total"], 1)

    def test_no_duplicate_alerts(self):
        report = {"candidates": [candidate()]}

        alerts.synchronize(report)
        result = alerts.synchronize(report)

        self.assertEqual(result["new_alerts"], 0)
        self.assertEqual(alerts.list_alerts()["total"], 1)

    def test_priority_change(self):
        alerts.synchronize({
            "candidates": [candidate(priority="medium")]
        })

        result = alerts.synchronize({
            "candidates": [candidate(priority="high")]
        })

        self.assertEqual(result["new_alerts"], 1)

    def test_status_change(self):
        alerts.synchronize({
            "candidates": [candidate(status="pending")]
        })

        result = alerts.synchronize({
            "candidates": [candidate(status="investigating")]
        })

        self.assertEqual(result["new_alerts"], 1)

    def test_mark_read(self):
        alerts.synchronize({
            "candidates": [candidate()]
        })

        alert_id = alerts.list_alerts()["alerts"][0]["id"]

        self.assertTrue(alerts.mark_read(alert_id))
        self.assertEqual(alerts.list_alerts()["unread"], 0)

    def test_unknown_alert(self):
        alerts.initialize()
        self.assertFalse(alerts.mark_read(99999))

    def test_fingerprint_deterministic(self):
        first = alerts.fingerprint("a", "b")
        second = alerts.fingerprint("a", "b")
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
