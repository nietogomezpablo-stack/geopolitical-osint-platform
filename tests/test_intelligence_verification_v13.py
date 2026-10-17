import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src/processing"))

from intelligence_verification_v13 import (
    as_list,
    extract_date_mentions,
    extract_location_mentions,
    verified_date,
    verified_location,
    verify_candidate,
    analyze,
    candidate_verification,
    export_csv,
)


def candidate():
    return {
        "title": "Incident in Niamey",
        "event_type": "armed_attack",
        "date_mentions": ["2026-10-01"],
        "locations": ["Niamey"],
        "investigation": {
            "candidate_key": "attack:1",
            "status": "pending",
        },
        "analysis_v5": {
            "priority": "high",
        },
    }


def provenance():
    return {
        "candidates": [{
            "candidate_key": "attack:1",
            "article_count": 2,
            "domain_count": 2,
            "source_urls": [
                "https://example.org/news",
                "https://another.org/story",
            ],
        }]
    }


class TestVerificationV13(unittest.TestCase):

    def test_as_list(self):
        self.assertEqual(
            as_list("Niamey"),
            ["Niamey"],
        )

    def test_date_mentions(self):
        self.assertEqual(
            extract_date_mentions(candidate()),
            ["2026-10-01"],
        )

    def test_location_mentions(self):
        self.assertEqual(
            extract_location_mentions(candidate()),
            ["Niamey"],
        )

    def test_date_not_automatically_verified(self):
        self.assertIsNone(
            verified_date(candidate())
        )

    def test_location_not_automatically_verified(self):
        self.assertIsNone(
            verified_location(candidate())
        )

    def test_verified_fields(self):
        item = candidate()
        item["verified_event_date"] = "2026-10-01"
        item["verified_event_location"] = "Niamey"

        self.assertEqual(
            verified_date(item),
            "2026-10-01",
        )

        self.assertEqual(
            verified_location(item),
            "Niamey",
        )

    def test_checks(self):
        result = verify_candidate(
            candidate(),
            provenance()["candidates"][0],
        )

        self.assertEqual(
            result["total_checks"],
            7,
        )

        self.assertFalse(
            result["event_factually_verified"]
        )

    def test_analysis(self):
        result = analyze(
            {"candidates": [candidate()]},
            provenance(),
        )

        self.assertEqual(
            result["candidate_count"],
            1,
        )

    def test_candidate_lookup(self):
        result = candidate_verification(
            "attack:1",
            {"candidates": [candidate()]},
            provenance(),
        )

        self.assertEqual(
            result["article_count"],
            2,
        )

    def test_unknown_candidate(self):
        result = candidate_verification(
            "unknown",
            {"candidates": [candidate()]},
            provenance(),
        )

        self.assertIsNone(result)

    def test_csv(self):
        content = export_csv(
            {"candidates": [candidate()]},
            provenance(),
        )

        self.assertIn(
            "documentation_coverage_percent",
            content,
        )

        self.assertIn(
            "attack:1",
            content,
        )


if __name__ == "__main__":
    unittest.main()
