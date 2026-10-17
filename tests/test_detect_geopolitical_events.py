import sys
import unittest
from pathlib import Path

sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[1] / "src" / "processing")
)

from detect_geopolitical_events import classify


class TestEventDetection(unittest.TestCase):

    def test_mutiny(self):
        categories, _ = classify(
            "Niger mutiny puts Russia's role to the test"
        )
        self.assertIn("military_mutiny", categories)

    def test_release(self):
        categories, _ = classify(
            "American missionary kidnapped in Niger released"
        )
        self.assertIn("release", categories)

    def test_armed_attack(self):
        categories, _ = classify(
            "Ataque armado contra fuerzas de seguridad"
        )
        self.assertIn("armed_attack", categories)

    def test_uncertainty(self):
        categories, uncertain = classify(
            "Niger : tentative de coup d'État ?"
        )
        self.assertIn("coup_attempt", categories)
        self.assertTrue(uncertain)

    def test_irrelevant(self):
        categories, _ = classify(
            "Nigar Fərhad sərbəst buraxıldı"
        )
        self.assertEqual(categories, [])


if __name__ == "__main__":
    unittest.main()
