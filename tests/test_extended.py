import json
import time
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch
import connectors
import discover
import insights
import monitor


class ExtendedTests(unittest.TestCase):
    def setUp(self):
        self.store = monitor.Store(':memory:')
        self.config = {'interval': 30, 'threshold': 3, 'timeout': 2, 'devices': [
            {'id': 'a', 'name': 'test', 'host': '127.0.0.1', 'method': 'tcp', 'port': 443,
             'collector': {'type': 'esxi', 'username_env': 'PRIVATE_USER', 'password_env': 'PRIVATE_PASSWORD'}}]}

    def tearDown(self):
        self.store.db.close()

    def test_configuration_secrets_not_in_response(self):
        data = json.dumps(self.store.snapshot(self.config))
        self.assertNotIn('PRIVATE_', data)
        self.assertNotIn('collector', data)

    def test_history_sample_ratio_and_retention(self):
        now = time.time()
        self.store.record('a', True, 10, None, 3, now - 60)
        self.store.record('a', False, None, 'timeout', 3, now)
        self.assertEqual(self.store.snapshot(self.config)['devices'][0]['availability_24h'], 50)
        self.assertEqual(len(self.store.history('a')['samples']), 2)
        self.store.record('a', True, 1, None, 3, now - 40 * 86400)
        self.store.prune()
        self.assertEqual(self.store.db.execute('SELECT COUNT(*) FROM samples').fetchone()[0], 2)

    def test_rate_reset_and_discontinuity(self):
        def metric(rx, discontinuity=0):
            return {'status': 'ok', 'values': {'interfaces': [{'name': 'port1', 'rx_bytes': rx,
                                                             'counter_discontinuity': discontinuity}]}}
        self.store.record_metrics('a', metric(100), 100)
        self.store.record_metrics('a', metric(7500100), 160)
        result = json.loads(self.store.db.execute('SELECT payload FROM metrics').fetchone()[0])
        self.assertEqual(result['values']['interfaces'][0]['rx_mbps'], 1)
        self.store.record_metrics('a', metric(1), 220)
        result = json.loads(self.store.db.execute('SELECT payload FROM metrics').fetchone()[0])
        self.assertIsNone(result['values']['interfaces'][0]['rx_mbps'])
        self.store.record_metrics('a', metric(1000, 1), 280)
        result = json.loads(self.store.db.execute('SELECT payload FROM metrics').fetchone()[0])
        self.assertIsNone(result['values']['interfaces'][0]['rx_mbps'])

    def test_esxi_uses_physical_cores_not_threads(self):
        summary = NS(hardware=NS(memorySize=128 * 1024**3, cpuMhz=2000, numCpuCores=8, model='R740'),
                     quickStats=NS(overallMemoryUsage=65536, overallCpuUsage=8000, uptime=123), overallStatus='green')
        values = connectors.esxi_summary(summary)
        self.assertEqual(values['cpu_percent'], 50)
        self.assertEqual(values['memory_percent'], 50)
        summary.quickStats.overallMemoryUsage = None
        self.assertIsNone(connectors.esxi_summary(summary)['memory_percent'])

    def test_error_messages_do_not_leak_secrets(self):
        with patch.dict('os.environ', {'PRIVATE_USER': 'user', 'PRIVATE_PASSWORD': 'secret'}):
            with patch.object(connectors, 'esxi', side_effect=RuntimeError('secret')):
                result = connectors.read(self.config['devices'][0])
        self.assertEqual(result['status'], 'error')
        self.assertNotIn('secret', json.dumps(result))

    def test_discovery_bounded_and_range_correct(self):
        self.assertEqual(len(discover.addresses('192.168.1.1', '192.168.3.255')), 767)
        for start, end in [('8.8.8.8', '8.8.8.9'), ('192.168.3.2', '192.168.1.1'), ('192.168.1.1', '192.168.8.255')]:
            with self.assertRaises(ValueError):
                discover.addresses(start, end)

    def test_dependency_cycle_rejected(self):
        self.config['devices'][0]['depends_on'] = ['a']
        with self.assertRaises(ValueError):
            monitor.validate(self.config)

    def test_stale_metrics_do_not_raise_resource_alarm(self):
        devices = [{'id': 'a', 'name': 'a', 'stale': False, 'status': 'up',
                    'metrics': {'status': 'ok', 'stale': True, 'error': None, 'values': {'cpu_percent': 99}}}]
        alerts = insights.alerts(devices)
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]['title'], 'Kaynak ölçümü alınamıyor')


if __name__ == '__main__':
    unittest.main()
