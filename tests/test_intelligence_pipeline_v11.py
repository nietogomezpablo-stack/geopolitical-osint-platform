import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src/processing"))

import intelligence_pipeline_v11 as pipeline


class TestPipelineV11(unittest.TestCase):

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()

        self.database = Path(self.temp.name) / "test.db"
        self.lock = Path(self.temp.name) / "test.lock"

        self.db_patch = patch.object(
            pipeline,
            "DATABASE",
            self.database,
        )

        self.lock_patch = patch.object(
            pipeline,
            "LOCK_FILE",
            self.lock,
        )

        self.db_patch.start()
        self.lock_patch.start()

    def tearDown(self):
        self.db_patch.stop()
        self.lock_patch.stop()
        self.temp.cleanup()

    def test_plan_country(self):
        self.assertEqual(
            pipeline.plan()["country"],
            "Niger",
        )

    def test_dry_run(self):
        result = pipeline.execute_full_update(
            dry_run=True,
        )

        self.assertEqual(
            result["status"],
            "dry_run",
        )

        self.assertFalse(self.database.exists())

    def test_successful_execution(self):
        with patch.object(
            pipeline,
            "execute_collection",
            return_value={
                "returncode": 0,
                "output": "Collection OK",
            },
        ):
            with patch.object(
                pipeline,
                "execute_intelligence",
                return_value={
                    "status": "completed",
                },
            ):
                result = pipeline.execute_full_update()

        self.assertEqual(
            result["status"],
            "completed",
        )

    def test_collection_failure(self):
        with patch.object(
            pipeline,
            "execute_collection",
            return_value={
                "returncode": 1,
                "output": "Collection failed",
            },
        ):
            result = pipeline.execute_full_update()

        self.assertEqual(
            result["status"],
            "failed",
        )

    def test_intelligence_failure(self):
        with patch.object(
            pipeline,
            "execute_collection",
            return_value={
                "returncode": 0,
                "output": "Collection OK",
            },
        ):
            with patch.object(
                pipeline,
                "execute_intelligence",
                return_value={
                    "status": "failed",
                    "error": "Analysis failed",
                },
            ):
                result = pipeline.execute_full_update()

        self.assertEqual(
            result["status"],
            "failed",
        )

    def test_history(self):
        pipeline.initialize()

        result = pipeline.list_runs()

        self.assertEqual(result["runs"], [])

    def test_missing_run(self):
        self.assertIsNone(
            pipeline.get_run(999)
        )


if __name__ == "__main__":
    unittest.main()
