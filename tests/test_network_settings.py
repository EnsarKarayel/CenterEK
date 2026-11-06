import json
from pathlib import Path
import socket
import tempfile
import unittest
from unittest.mock import patch
import network_settings as settings


class AccessSettingsTests(unittest.TestCase):
    def test_tls_certificate_must_cover_selected_private_ip(self):
        import tls_setup
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with patch('tls_setup.restrict'):
                tls_setup.create(root / 'certs/panel', 'panel.example.local', ['127.0.0.1', '192.168.1.15'])
            current = {'tls_cert': 'certs/panel/panel-cert.pem', 'tls_key': 'certs/panel/panel-key.pem'}
            payload = {'mode': 'proxy', 'bind': '192.168.1.15', 'port': 8765, 'public_origin': 'https://panel.example.com', 'gateway_protection_confirmed': True}
            self.assertEqual(settings.validate(root, current, payload)['public_origin'], 'https://panel.example.com')
            payload['bind'] = '192.168.1.16'
            with self.assertRaises(ValueError):
                settings.validate(root, current, payload)

    def test_local_stages_without_changing_active_settings(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            settings.stage(root, {'mode': 'local', 'bind': '127.0.0.1', 'port': 9876})
            self.assertFalse((root / 'server.local.json').exists())
            self.assertTrue(settings.summary(root)['restart_required'])

    def test_remote_requires_tls_and_rejects_public_or_wildcard(self):
        for mode, address in [('vpn', '192.168.1.15'), ('proxy', '127.0.0.1'), ('vpn', '0.0.0.0'), ('vpn', '8.8.8.8'), ('vpn', '240.0.0.1')]:
            with self.subTest(address=address), self.assertRaises(ValueError):
                settings.validate('.', {}, {'mode': mode, 'bind': address, 'port': 8765, 'public_origin': 'https://panel.example.com', 'gateway_protection_confirmed': True})

    def test_origin_has_no_credentials_path_or_ip(self):
        self.assertEqual(settings.public_origin('https://PANEL.example.com:443/'), 'https://panel.example.com')
        for value in ['http://panel.example.com', 'https://8.8.8.8', 'https://user:pass@panel.example.com', 'https://panel.example.com/path', 'https://panel.example.com?token=abc']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                settings.public_origin(value)

    def test_failed_change_preserves_active_and_success_ignores_injected_fields(self):
        with tempfile.TemporaryDirectory() as folder, socket.socket() as occupied:
            root = Path(folder)
            active = root / 'server.local.json'
            active.write_text(json.dumps({'bind': '127.0.0.1', 'port': 8765}))
            occupied.bind(('127.0.0.1', 0))
            settings.stage(root, {'mode': 'local', 'bind': '127.0.0.1', 'port': occupied.getsockname()[1]})
            settings.apply_pending(root)
            self.assertEqual(settings.load(root)['port'], 8765)
            self.assertTrue(settings.summary(root)['previous_change_failed'])
            with socket.socket() as free:
                free.bind(('127.0.0.1', 0))
                port = free.getsockname()[1]
            settings.stage(root, {'mode': 'local', 'bind': '127.0.0.1', 'port': port})
            pending = root / 'server.pending.local.json'
            candidate = json.loads(pending.read_text())
            candidate['tls_key'] = 'injected-key'
            pending.write_text(json.dumps(candidate))
            settings.apply_pending(root)
            self.assertEqual(settings.load(root)['port'], port)
            self.assertNotIn('tls_key', settings.load(root))
