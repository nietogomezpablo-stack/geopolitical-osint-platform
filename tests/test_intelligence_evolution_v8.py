import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src/processing"))

import intelligence_evolution_v8 as evolution


def candidate(title="Attack reported"):
    return {
        "title": title,
        "event_type": "armed_attack",
        "evidence": ["Report"],
        "locations": ["Niamey"],
        "investigation": {
            "candidate_key": "armed_attack:1",
        },
        "analysis_v5": {
            "article_ids": ["1"],
            "sources": {
                "urls": ["https://example.org/news"]
            },
        },
    }


class TestEvolutionV8(unittest.TestCase):

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.database = Path(self.temp.name) / "test.db"
        self.patcher = patch.object(
            evolution,
            "DATABASE",
            self.database,
        )
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        self.temp.cleanup()

    def test_hash_deterministic(self):
        self.assertEqual(
            evolution.content_hash({"a": 1}),
            evolution.content_hash({"a": 1}),
        )

    def test_changes_detected(self):
        changes = evolution.differences(
            {"title": "Old"},
            {"title": "New"},
        )
        self.assertIn("title", changes)

    def test_first_version(self):
        result = evolution.synchronize({
            "candidates": [candidate()]
        })
        self.assertEqual(result["new_candidates"], 1)

    def test_no_duplicate_version(self):
        report = {"candidates": [candidate()]}

        evolution.synchronize(report)
        result = evolution.synchronize(report)

        self.assertEqual(
            result["updated_candidates"],
            0,
        )

        history = evolution.candidate_history(
            "armed_attack:1"
        )

        self.assertEqual(len(history["versions"]), 1)

    def test_updated_version(self):
        evolution.synchronize({
            "candidates": [candidate("Old")]
        })

        result = evolution.synchronize({
            "candidates": [candidate("New")]
        })

        self.assertEqual(
            result["updated_candidates"],
            1,
        )

        history = evolution.candidate_history(
            "armed_attack:1"
        )

        self.assertEqual(len(history["versions"]), 2)

    def test_disappearance(self):
        evolution.synchronize({
            "candidates": [candidate()]
        })

        result = evolution.synchronize({
            "candidates": [{
                **candidate(),
                "investigation": {
                    "candidate_key": "other:2"
                },
            }]
        })

        self.assertEqual(
            result["disappeared_candidates"],
            1,
        )

    def test_empty_dataset_safe(self):
        evolution.synchronize({
            "candidates": [candidate()]
        })

        result = evolution.synchronize({
            "candidates": []
        })

        self.assertEqual(
            result["disappeared_candidates"],
            0,
        )


if __name__ == "__main__":
    unittest.main()
