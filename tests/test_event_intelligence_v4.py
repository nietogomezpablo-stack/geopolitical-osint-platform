import sys
import unittest
from pathlib import Path

sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[1] / "src" / "processing")
)

from event_intelligence_v4 import (
    build_report,
    compare,
    source_domain,
    evidence_coverage,
)


def candidate(article_id, title, event_type="military_mutiny"):
    return {
        "article_id": article_id,
        "title": title,
        "event_type": event_type,
        "publication_date": "2026-10-16",
        "locations": [],
        "evidence": [],
        "mentioned_dates": [],
        "url": f"https://example.org/{article_id}",
    }


class TestV4(unittest.TestCase):

    def test_source_domain(self):
        self.assertEqual(
            source_domain("https://www.bbc.com/news/123"),
            "bbc.com"
        )

    def test_invalid_source(self):
        self.assertIsNone(
            source_domain("javascript:alert(1)")
        )

    def test_same_article(self):
        a = candidate(1, "Mutiny", "military_mutiny")
        b = candidate(1, "Coup", "coup_attempt")

        score, reasons = compare(a, b)

        self.assertEqual(score, 1)
        self.assertIn("same_article", reasons)

    def test_different_events(self):
        a = candidate(1, "Attack", "armed_attack")
        b = candidate(2, "Release", "release")

        score, _ = compare(a, b)

        self.assertEqual(score, 0)

    def test_no_automatic_confirmation(self):
        report = build_report([
            candidate(1, "Niger mutiny"),
            candidate(2, "Niger military mutiny"),
        ])

        self.assertTrue(all(
            not item["event_verified"]
            for item in report["candidates"]
        ))

    def test_distinct_articles_not_merged(self):
        report = build_report([
            candidate(1, "Niger military mutiny"),
            candidate(2, "Niger military mutiny"),
        ])

        self.assertEqual(
            report["summary"]["clusters"], 2
        )

    def test_same_article_grouped(self):
        report = build_report([
            candidate(1, "Mutiny", "military_mutiny"),
            candidate(1, "Coup", "coup_attempt"),
        ])

        self.assertEqual(
            report["summary"]["clusters"], 1
        )

    def test_no_truth_score(self):
        coverage = evidence_coverage(
            candidate(1, "Example")
        )

        self.assertIsNone(coverage["truth_score"])

    def test_source_domains_not_independence(self):
        item = candidate(1, "Example")
        item["source_urls"] = [
            "https://example.org/a",
            "https://example.org/b",
        ]

        coverage = evidence_coverage(item)

        self.assertEqual(coverage["source_domains"], 1)
        self.assertFalse(
            coverage["independent_sources_verified"]
        )


if __name__ == "__main__":
    unittest.main()
