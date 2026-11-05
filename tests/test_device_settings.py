import json
from pathlib import Path
import tempfile
import unittest
import device_settings
import monitor


class DeviceSettingsTests(unittest.TestCase):
    def config(self):
        return {'interval': 30, 'threshold': 3, 'timeout': 2, 'devices': [
            {'id': 'sw1', 'name': 'Core', 'host': '192.0.2.1', 'kind': 'Switch', 'method': 'icmp',
             'collector': {'type': 'snmp', 'community_env': 'PRIVATE_COMMUNITY'}}]}

    def test_atomic_save_preserves_source_and_backs_up(self):
        config = self.config()
        payload = {'id': 'sw1', 'name': 'Core renamed', 'host': '192.0.2.1', 'kind': 'Switch', 'method': 'tcp', 'port': 443}
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'config.local.json'
            original = json.dumps(config)
            path.write_text(original, encoding='utf-8')
            device_settings.save(config, payload, path, monitor.validate)
            self.assertEqual(json.loads(path.read_text())['devices'][0]['name'], 'Core renamed')
            self.assertEqual((path.parent / 'config.backup.local.json').read_text(), original)
            self.assertEqual(config['devices'][0]['collector']['community_env'], 'PRIVATE_COMMUNITY')

    def test_reject_host_change_and_invalid_port_without_mutation(self):
        config = self.config()
        payload = {'id': 'sw1', 'name': 'Core', 'host': '192.0.2.2', 'kind': 'Switch', 'method': 'icmp'}
        with self.assertRaises(ValueError):
            device_settings.candidate(config, payload, monitor.validate)
        payload.update(id='new', method='tcp', port=70000)
        with self.assertRaises(ValueError):
            device_settings.candidate(config, payload, monitor.validate)
        self.assertEqual(len(config['devices']), 1)

    def test_new_device_and_removed_tcp_port(self):
        config = self.config()
        payload = {'id': 'new', 'name': 'Server', 'host': '192.0.2.2', 'kind': 'Sunucu', 'method': 'tcp', 'port': 443}
        new, _ = device_settings.candidate(config, payload, monitor.validate)
        payload['method'] = 'icmp'
        changed, _ = device_settings.candidate(new, payload, monitor.validate)
        self.assertNotIn('port', changed['devices'][1])
