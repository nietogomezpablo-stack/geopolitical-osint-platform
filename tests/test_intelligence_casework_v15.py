import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src/processing"))

import intelligence_casework_v15 as casework


class TestCaseworkV15(unittest.TestCase):

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.database = Path(self.temp.name) / "test.db"

        self.patcher = patch.object(
            casework,
            "DATABASE",
            self.database,
        )

        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        self.temp.cleanup()

    def test_initialize(self):
        casework.initialize()

        result = casework.summary()

        self.assertEqual(result["total_cases"], 0)

    def test_create_case_with_notes(self):
        result = casework.update_notes(
            "attack:1",
            "Investigation started",
        )

        self.assertTrue(result["changed"])

        case = casework.get_case("attack:1")

        self.assertEqual(
            case["case"]["analyst_notes"],
            "Investigation started",
        )

    def test_notes_history(self):
        casework.update_notes(
            "attack:1",
            "First note",
        )

        casework.update_notes(
            "attack:1",
            "Second note",
        )

        case = casework.get_case("attack:1")

        self.assertEqual(
            len(case["history"]),
            2,
        )

    def test_no_duplicate_notes(self):
        casework.update_notes(
            "attack:1",
            "Same note",
        )

        result = casework.update_notes(
            "attack:1",
            "Same note",
        )

        self.assertFalse(result["changed"])

    def test_create_task(self):
        result = casework.create_task(
            "attack:1",
            "Verify date",
            priority="high",
        )

        self.assertEqual(
            result["status"],
            "pending",
        )

    def test_update_task(self):
        task = casework.create_task(
            "attack:1",
            "Verify source",
        )

        result = casework.update_task(
            task["id"],
            status="completed",
        )

        self.assertEqual(
            result["status"],
            "completed",
        )

    def test_invalid_priority(self):
        with self.assertRaises(ValueError):
            casework.create_task(
                "attack:1",
                "Check",
                priority="urgent",
            )

    def test_invalid_status(self):
        task = casework.create_task(
            "attack:1",
            "Check",
        )

        with self.assertRaises(ValueError):
            casework.update_task(
                task["id"],
                status="confirmed_event",
            )

    def test_missing_task(self):
        self.assertIsNone(
            casework.update_task(
                999,
                status="completed",
            )
        )

    def test_list_cases(self):
        casework.update_notes(
            "attack:1",
            "Investigation",
        )

        result = casework.list_cases()

        self.assertEqual(
            len(result["cases"]),
            1,
        )

    def test_summary(self):
        casework.create_task(
            "attack:1",
            "Verify location",
        )

        result = casework.summary()

        self.assertEqual(
            result["task_status_counts"]["pending"],
            1,
        )


if __name__ == "__main__":
    unittest.main()
