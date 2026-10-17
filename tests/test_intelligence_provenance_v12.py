import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src/processing"))

from intelligence_provenance_v12 import (
    normalize_url,
    domain_of,
    analyze,
    candidate_provenance,
    export_csv,
)


def sample_report():
    return {
        "candidates": [
            {
                "title": "Incident in Niger",
                "event_type": "armed_attack",
                "investigation": {
                    "candidate_key": "attack:1",
                },
                "analysis_v5": {
                    "article_ids": [1],
                    "sources": {
                        "urls": [
                            "https://example.org/news?utm_source=x"
                        ]
                    },
                },
            },
            {
                "title": "Another candidate",
                "event_type": "military_mutiny",
                "investigation": {
                    "candidate_key": "mutiny:2",
                },
                "analysis_v5": {
                    "article_ids": [1],
                    "sources": {
                        "urls": [
                            "https://another.org/story"
                        ]
                    },
                },
            },
        ]
    }


def sample_articles():
    return [
        {
            "id": 1,
            "title": "Incident in Niger",
            "url": "https://example.org/news",
        },
        {
            "id": 2,
            "title": "Duplicate article",
            "url": "https://example.org/news?utm_campaign=test",
        },
    ]


class TestProvenanceV12(unittest.TestCase):

    def test_normalize_url(self):
        self.assertEqual(
            normalize_url(
                "HTTPS://EXAMPLE.ORG/news/?utm_source=test"
            ),
            "https://example.org/news",
        )

    def test_remove_tracking(self):
        self.assertEqual(
            normalize_url(
                "https://example.org/a?utm_medium=email&id=2"
            ),
            "https://example.org/a?id=2",
        )

    def test_reject_javascript(self):
        self.assertEqual(
            normalize_url("javascript:alert(1)"),
            "",
        )

    def test_domain(self):
        self.assertEqual(
            domain_of("https://example.org/news"),
            "example.org",
        )

    def test_duplicate_urls(self):
        result = analyze(
            sample_report(),
            sample_articles(),
        )

        self.assertEqual(
            len(result["duplicate_url_groups"]),
            1,
        )

    def test_shared_article(self):
        result = analyze(
            sample_report(),
            sample_articles(),
        )

        self.assertEqual(
            len(result["shared_articles"]),
            1,
        )

    def test_candidate_lookup(self):
        result = candidate_provenance(
            "attack:1",
            sample_report(),
            sample_articles(),
        )

        self.assertEqual(
            result["article_count"],
            1,
        )

    def test_unknown_candidate(self):
        result = candidate_provenance(
            "unknown",
            sample_report(),
            sample_articles(),
        )

        self.assertIsNone(result)

    def test_csv_export(self):
        content = export_csv(
            sample_report(),
            sample_articles(),
        )

        self.assertIn(
            "candidate_key",
            content,
        )

        self.assertIn(
            "attack:1",
            content,
        )


if __name__ == "__main__":
    unittest.main()
