import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(
    0,
    str(ROOT / "src" / "processing")
)

from enrich_event_candidates import (
    extract_evidence,
    extract_dates,
    similarity,
)


class TestEventEnrichment(unittest.TestCase):

    def test_extract_attack_evidence(self):
        text = (
            "The government held a meeting. "
            "An armed attack killed soldiers near Tera."
        )

        evidence = extract_evidence(
            text,
            "armed_attack"
        )

        self.assertEqual(len(evidence), 1)
        self.assertFalse(evidence[0]["verified"])

    def test_extract_french_date(self):
        text = "L'attaque a eu lieu le 14 août 2026."

        dates = extract_dates(text)

        self.assertIn("2026-08-14", dates)

    def test_extract_spanish_date(self):
        text = "El ataque ocurrió el 15 de agosto de 2026."

        dates = extract_dates(text)

        self.assertIn("2026-08-15", dates)

    def test_title_similarity(self):
        score = similarity(
            "Niger military mutiny reported",
            "Niger military mutiny reported"
        )

        self.assertEqual(score, 1.0)

    def test_irrelevant_evidence(self):
        evidence = extract_evidence(
            "The weather was sunny.",
            "armed_attack"
        )

        self.assertEqual(evidence, [])


if __name__ == "__main__":
    unittest.main()
