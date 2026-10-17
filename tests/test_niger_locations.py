import sys
import unittest
from pathlib import Path

sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[1] / "src" / "processing")
)

from detect_niger_locations import detect_locations


class TestNigerLocations(unittest.TestCase):

    def test_niamey(self):
        result = detect_locations(
            "Explosions reported in Niamey, Niger"
        )
        self.assertTrue(
            any(loc["name"] == "Niamey" for loc in result)
        )

    def test_agadez(self):
        result = detect_locations(
            "Une opération militaire à Agadez"
        )
        self.assertTrue(
            any(loc["name"] == "Agadez" for loc in result)
        )

    def test_tillaberi(self):
        result = detect_locations(
            "Attaque dans la région de Tillabéri"
        )
        self.assertTrue(
            any(loc["name"] == "Tillabéri" for loc in result)
        )

    def test_no_location(self):
        result = detect_locations(
            "International diplomatic meeting"
        )
        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()
