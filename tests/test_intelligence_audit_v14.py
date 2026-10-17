import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src/processing"))

import intelligence_audit_v14 as audit


class TestAuditV14(unittest.TestCase):

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.database = Path(self.temp.name) / "test.db"

        self.patcher = patch.object(
            audit,
            "DATABASE",
            self.database,
        )

        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        self.temp.cleanup()

    def test_initialize(self):
        audit.initialize()

        result = audit.audit_summary()

        self.assertEqual(
            result["audited_candidates"],
            0,
        )

    def test_create_audit(self):
        result = audit.update_audit(
            "attack:1",
            "source_identified",
            "supported",
            "Source reviewed",
        )

        self.assertTrue(result["changed"])

    def test_update_audit(self):
        audit.update_audit(
            "attack:1",
            "source_identified",
            "pending",
        )

        audit.update_audit(
            "attack:1",
            "source_identified",
            "supported",
        )

        result = audit.list_audits("attack:1")

        self.assertEqual(
            result["audits"][0]["status"],
            "supported",
        )

    def test_no_duplicate_history(self):
        audit.update_audit(
            "attack:1",
            "source_identified",
            "pending",
        )

        result = audit.update_audit(
            "attack:1",
            "source_identified",
            "pending",
        )

        self.assertFalse(result["changed"])

        history = audit.audit_history("attack:1")

        self.assertEqual(
            len(history["history"]),
            1,
        )

    def test_history(self):
        audit.update_audit(
            "attack:1",
            "source_identified",
            "pending",
        )

        audit.update_audit(
            "attack:1",
            "source_identified",
            "supported",
        )

        history = audit.audit_history("attack:1")

        self.assertEqual(
            len(history["history"]),
            2,
        )

    def test_invalid_status(self):
        with self.assertRaises(ValueError):
            audit.update_audit(
                "attack:1",
                "source_identified",
                "confirmed_event",
            )

    def test_invalid_check(self):
        with self.assertRaises(ValueError):
            audit.update_audit(
                "attack:1",
                "unknown_check",
                "pending",
            )

    def test_summary(self):
        audit.update_audit(
            "attack:1",
            "source_identified",
            "supported",
        )

        result = audit.audit_summary()

        self.assertEqual(
            result["status_counts"]["supported"],
            1,
        )

    def test_contradiction(self):
        audit.update_audit(
            "attack:1",
            "event_date_verified",
            "contradicted",
            "Conflicting dates in reports",
        )

        result = audit.list_audits("attack:1")

        self.assertEqual(
            result["audits"][0]["status"],
            "contradicted",
        )


if __name__ == "__main__":
    unittest.main()
