import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src/processing"))

from intelligence_search_v7 import (
    normalize,
    search,
    searchable_text,
)


def sample_report():
    return {
        "candidates": [
            {
                "title": "Attaque à Niamey",
                "event_type": "armed_attack",
                "investigation": {
                    "candidate_key": "armed_attack:1",
                    "status": "pending",
                    "notes": "Revisar fuentes",
                },
                "analysis_v5": {
                    "priority": "high",
                    "sources": {
                        "domains": ["example.org"]
                    },
                },
            },
            {
                "title": "Military appointment",
                "event_type": "military_appointment",
                "investigation": {
                    "candidate_key": "military_appointment:2",
                    "status": "reviewed",
                    "notes": "",
                },
                "analysis_v5": {
                    "priority": "low",
                    "sources": {
                        "domains": []
                    },
                },
            },
        ]
    }


class TestSearchV7(unittest.TestCase):

    def test_accents(self):
        self.assertEqual(
            normalize("Níger"),
            "niger",
        )

    def test_search_title(self):
        result = search(
            query="niamey",
            report=sample_report(),
        )
        self.assertEqual(result["total"], 1)

    def test_search_notes(self):
        result = search(
            query="fuentes",
            report=sample_report(),
        )
        self.assertEqual(result["total"], 1)

    def test_search_domain(self):
        result = search(
            query="example.org",
            report=sample_report(),
        )
        self.assertEqual(result["total"], 1)

    def test_status_filter(self):
        result = search(
            status="reviewed",
            report=sample_report(),
        )
        self.assertEqual(result["total"], 1)

    def test_priority_filter(self):
        result = search(
            priority="high",
            report=sample_report(),
        )
        self.assertEqual(result["total"], 1)

    def test_combined_filters(self):
        result = search(
            query="niamey",
            priority="high",
            status="pending",
            report=sample_report(),
        )
        self.assertEqual(result["total"], 1)

    def test_invalid_priority(self):
        with self.assertRaises(ValueError):
            search(
                priority="critical",
                report=sample_report(),
            )

    def test_title_sort(self):
        result = search(
            sort="title",
            report=sample_report(),
        )

        self.assertEqual(
            result["results"][0]["title"],
            "Attaque à Niamey",
        )


if __name__ == "__main__":
    unittest.main()
