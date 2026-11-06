import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import collector_settings
import connectors
import monitor


class CollectorSettingsTests(unittest.TestCase):
    def config(self):
        return {'interval': 30, 'timeout': 2, 'threshold': 3, 'devices': [
            {'id': 'fw', 'name': 'Firewall', 'kind': 'Firewall', 'host': '192.0.2.1', 'method': 'tcp', 'port': 443}]}

    def payload(self):
        return {'id': 'fw', 'type': 'fortigate', 'port': 4443, 'credentials': {'token': 'private-token-never-json'}}

    def test_ephemeral_test_has_no_environment_mutation(self):
        before = dict(os.environ)
        config = self.config()
        device = collector_settings.prepare(config, self.payload())
        self.assertEqual(connectors.secret(device['collector'], 'token'), 'private-token-never-json')
        self.assertEqual(dict(os.environ), before)
        self.assertNotIn('collector', config['devices'][0])

    def test_save_has_no_plaintext_and_preserves_old_secret_entries(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ), patch('collector_settings.restrict'), patch('collector_settings.service_secrets.protect', return_value='encrypted-value'):
            path = Path(folder) / 'config.local.json'
            secure = Path(folder) / 'secure' / 'service-secrets.local.json'
            secure.parent.mkdir()
            secure.write_text(json.dumps({'schema': 1, 'environment': {'OLD': 'old-encrypted'}}))
            config = self.config()
            path.write_text(json.dumps(config))
            collector_settings.save(config, self.payload(), path, secure, monitor.validate)
            serialized = path.read_text() + secure.read_text()
            self.assertNotIn('private-token-never-json', serialized)
            self.assertNotIn('_credentials', serialized)
            settings = config['devices'][0]['collector']
            self.assertEqual(connectors.secret(settings, 'token'), 'private-token-never-json')
            self.assertEqual(json.loads(secure.read_text())['environment']['OLD'], 'old-encrypted')

    def test_bad_fields_rejected(self):
        for change in ({'id': 'missing'}, {'port': True}, {'type': 'unknown'}, {'credentials': {'token': ''}}):
            data = self.payload()
            data.update(change)
            with self.assertRaises(ValueError):
                collector_settings.prepare(self.config(), data)

    def test_snmpv3_profile_validation(self):
        data = {'id': 'fw', 'type': 'snmp', 'port': 161, 'version': '3',
                'credentials': {'username': 'monitor', 'auth_password': 'auth-secret-long',
                                'privacy_password': 'privacy-secret-long'}}
        device = collector_settings.prepare(self.config(), data)
        settings = device['collector']
        self.assertEqual(settings['auth_protocol'], 'sha256')
        self.assertEqual(settings['privacy_protocol'], 'aes128')
        self.assertNotIn('community', settings['_credentials'])
        self.assertNotIn('collector', self.config()['devices'][0])
        for change in ({'version': '1'}, {'auth_protocol': 'md5'},
                       {'credentials': {'username': 'monitor', 'auth_password': 'short', 'privacy_password': 'long-enough'}}):
            invalid = dict(data)
            invalid.update(change)
            with self.assertRaises(ValueError):
                collector_settings.prepare(self.config(), invalid)

    def test_snmpv3_runtime_uses_auth_priv_and_legacy_still_works(self):
        try:
            from pysnmp.hlapi.v3arch.asyncio import UsmUserData, CommunityData
        except ImportError:
            self.skipTest('Optional SNMP SDK not installed')
        auth = connectors.snmp_auth({'version': '3', '_credentials': {
            'username': 'monitor', 'auth_password': 'auth-secret-long', 'privacy_password': 'privacy-secret-long'}})
        self.assertIsInstance(auth, UsmUserData)
        self.assertEqual(auth.security_level, 'authPriv')
        legacy = connectors.snmp_auth({'_credentials': {'community': 'read-only-test'}})
        self.assertIsInstance(legacy, CommunityData)
