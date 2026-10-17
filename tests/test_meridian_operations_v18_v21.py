import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src' / 'processing'))
import meridian_operations_v18_v21 as ops

class TestOperations(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Path(self.temp.name) / 'test.db'
        self.lock = Path(self.temp.name) / 'test.lock'
    def tearDown(self):
        self.temp.cleanup()
    def test_initialization(self):
        self.assertEqual(ops.history(self.db), [])
    def test_success(self):
        calls = []
        result = ops.execute(self.db, self.lock,
            pipeline_runner=lambda: calls.append('pipeline'),
            alert_runner=lambda: (calls.append('alerts') or {'created': 2}))
        self.assertEqual(result['status'], 'success')
        self.assertEqual(calls, ['pipeline', 'alerts'])
        self.assertEqual(ops.history(self.db)[0]['alerts_created'], 2)
    def test_pipeline_failure_skips_alerts(self):
        calls = []
        def fail():
            raise RuntimeError('pipeline failed')
        result = ops.execute(self.db, self.lock, fail, lambda: calls.append('alerts'))
        self.assertEqual(result['alert_status'], 'skipped')
        self.assertEqual(calls, [])
    def test_alert_failure(self):
        def fail():
            raise RuntimeError('alerts failed')
        result = ops.execute(self.db, self.lock, lambda: None, fail)
        self.assertEqual(result['pipeline_status'], 'success')
        self.assertEqual(result['alert_status'], 'failed')
    def test_health_before_first_run(self):
        result = ops.health(self.db)
        self.assertIn('never_executed', [i['code'] for i in result['issues']])
    def test_report(self):
        ops.execute(self.db, self.lock, lambda: None, lambda: {})
        self.assertEqual(ops.report(self.db)['summary']['successful_runs'], 1)
    def test_csv_formula_protection(self):
        self.assertEqual(ops.safe_csv('=SUM(A1)'), "'=SUM(A1)")
    def test_csv(self):
        self.assertIn('pipeline_status', ops.report_csv(self.db))
    def test_no_auto_confirmation(self):
        self.assertFalse(ops.report(self.db)['automatic_event_confirmation'])
    def test_lock_prevents_concurrency(self):
        with self.lock.open('a+') as handle:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaises(RuntimeError):
                ops.execute(self.db, self.lock, lambda: None, lambda: {})
