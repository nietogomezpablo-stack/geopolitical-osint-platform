import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(
    0,
    str(ROOT / "src/processing")
)

from intelligence_analysis_v5 import (
    calculate_priority,
    csv_safe,
    get_domain,
    has_explicit_date,
    has_verified_location,
    possible_duplicates,
)


class TestIntelligenceV5(unittest.TestCase):

    def test_domain(self):
        self.assertEqual(
            get_domain("https://www.example.org/news"),
            "example.org",
        )

    def test_invalid_domain(self):
        self.assertIsNone(
            get_domain("javascript:alert(1)")
        )

    def test_date_mentions_not_verified(self):
        self.assertFalse(
            has_explicit_date({
                "date_mentions": ["2025-06-13"]
            })
        )

    def test_location_mentions_not_verified(self):
        self.assertFalse(
            has_verified_location({
                "locations": ["Niamey"]
            })
        )

    def test_priority(self):
        result = calculate_priority({
            "article_id": 1,
            "evidence": ["Evidence"],
        })

        self.assertEqual(
            result["priority"],
            "high",
        )

    def test_csv_formula(self):
        self.assertEqual(
            csv_safe("=1+1"),
            "'=1+1",
        )

    def test_shared_article(self):
        candidates = [
            {
                "title": "Coup attempt",
                "article_id": 10,
                "investigation": {
                    "candidate_key": "a"
                },
            },
            {
                "title": "Military mutiny",
                "article_id": 10,
                "investigation": {
                    "candidate_key": "b"
                },
            },
        ]

        result = possible_duplicates(candidates)

        self.assertEqual(len(result), 1)
        self.assertFalse(
            result[0]["verified_same_event"]
        )


if __name__ == "__main__":
    unittest.main()
