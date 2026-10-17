import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src/processing"))

import intelligence_orchestrator_v10 as orchestrator


class TestOrchestratorV10(unittest.TestCase):

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()

        self.database = Path(self.temp.name) / "test.db"
        self.lock = Path(self.temp.name) / "test.lock"

        self.db_patch = patch.object(
            orchestrator,
            "DATABASE",
            self.database,
        )

        self.lock_patch = patch.object(
            orchestrator,
            "LOCK_FILE",
            self.lock,
        )

        self.db_patch.start()
        self.lock_patch.start()

    def tearDown(self):
        self.db_patch.stop()
        self.lock_patch.stop()
        self.temp.cleanup()

    def test_initialize(self):
        orchestrator.initialize()

        status = orchestrator.operational_status()

        self.assertEqual(status["total_runs"], 0)

    def test_create_run(self):
        run_id = orchestrator.create_run()

        self.assertEqual(run_id, 1)

    def test_finish_run(self):
        run_id = orchestrator.create_run()

        orchestrator.finish_run(
            run_id,
            "completed",
            1.5,
            {"test": True},
        )

        runs = orchestrator.list_runs()

        self.assertEqual(
            runs["runs"][0]["status"],
            "completed",
        )

    def test_successful_execution(self):
        with patch.object(
            orchestrator,
            "run_steps",
            return_value={"test": "ok"},
        ):
            result = orchestrator.execute()

        self.assertEqual(
            result["status"],
            "completed",
        )

    def test_failed_execution(self):
        with patch.object(
            orchestrator,
            "run_steps",
            side_effect=ValueError("Test failure"),
        ):
            result = orchestrator.execute()

        self.assertEqual(
            result["status"],
            "failed",
        )

        self.assertEqual(
            orchestrator.operational_status()["failed_runs"],
            1,
        )

    def test_lock(self):
        with orchestrator.execution_lock():
            with self.assertRaises(RuntimeError):
                with orchestrator.execution_lock():
                    pass

    def test_run_history(self):
        orchestrator.create_run()

        result = orchestrator.list_runs()

        self.assertEqual(len(result["runs"]), 1)


if __name__ == "__main__":
    unittest.main()
