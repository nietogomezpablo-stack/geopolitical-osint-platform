import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src/processing"))

import intelligence_triage_v16 as triage


def sample_data():
    return {
        "cases": [{
            "candidate_key": "attack:1",
            "analyst_notes": "Revisar fuentes",
        }],
        "tasks": [{
            "id": 1,
            "candidate_key": "attack:1",
            "title": "Verificar fecha",
            "status": "pending",
            "priority": "high",
        }],
        "audits": [{
            "candidate_key": "attack:1",
            "check_code": "event_date_verified",
            "status": "contradicted",
        }],
    }


def sample_verification():
    return {
        "candidates": [{
            "candidate_key": "attack:1",
            "title": "Incident in Niger",
            "pending_checks": [{
                "code": "event_date_verified",
            }],
        }]
    }


class TestTriageV16(unittest.TestCase):

    def test_priority_labels(self):
        self.assertEqual(triage.priority_label(0), "low")
        self.assertEqual(triage.priority_label(10), "medium")
        self.assertEqual(triage.priority_label(30), "high")
        self.assertEqual(triage.priority_label(60), "critical")

    def test_contradicted_evidence(self):
        result = triage.calculate_case(
            "attack:1",
            audits=[{
                "status": "contradicted",
            }],
        )

        self.assertEqual(
            result["triage_score"],
            40,
        )

    def test_high_priority_task(self):
        result = triage.calculate_case(
            "attack:1",
            tasks=[{
                "status": "pending",
                "priority": "high",
            }],
        )

        self.assertEqual(
            result["triage_score"],
            20,
        )

    def test_completed_task_not_prioritized(self):
        result = triage.calculate_case(
            "attack:1",
            tasks=[{
                "status": "completed",
                "priority": "high",
            }],
        )

        self.assertEqual(
            result["triage_score"],
            0,
        )

    def test_full_analysis(self):
        result = triage.analyze(
            sample_data(),
            sample_verification(),
        )

        self.assertEqual(
            result["candidate_count"],
            1,
        )

        self.assertEqual(
            result["candidates"][0]["triage_priority"],
            "critical",
        )

    def test_no_automatic_confirmation(self):
        result = triage.analyze(
            sample_data(),
            sample_verification(),
        )

        self.assertFalse(
            result["candidates"][0][
                "automatic_event_confirmation"
            ]
        )

    def test_candidate_lookup(self):
        result = triage.get_candidate(
            "attack:1",
            sample_data(),
            sample_verification(),
        )

        self.assertEqual(
            result["candidate_key"],
            "attack:1",
        )

    def test_unknown_candidate(self):
        self.assertIsNone(
            triage.get_candidate(
                "unknown",
                sample_data(),
                sample_verification(),
            )
        )

    def test_csv_export(self):
        content = triage.export_csv(
            sample_data(),
            sample_verification(),
        )

        self.assertIn(
            "triage_priority",
            content,
        )

        self.assertIn(
            "attack:1",
            content,
        )

    def test_csv_formula_protection(self):
        self.assertEqual(
            triage.csv_safe("=1+1"),
            "'=1+1",
        )

    def test_missing_database(self):
        with tempfile.TemporaryDirectory() as directory:
            data = triage.load_data(
                Path(directory) / "missing.db"
            )

        self.assertEqual(data["cases"], [])
        self.assertEqual(data["tasks"], [])
        self.assertEqual(data["audits"], [])


if __name__ == "__main__":
    unittest.main()
