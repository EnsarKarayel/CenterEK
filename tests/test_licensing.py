import base64
import json
from pathlib import Path
import tempfile
import threading
import unittest
import uuid
from unittest.mock import patch
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
import licensing
import license_issuer
import monitor


class SubscriptionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'data').mkdir()
        self.identity = uuid.uuid4().hex
        (self.root / 'installation.local.json').write_text(json.dumps({'installation_id': self.identity}))
        self.key = Ed25519PrivateKey.generate()
        public = base64.b64encode(self.key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)).decode()
        self.now = 2000000000
        self.policy = {'mode': 'commercial', 'public_keys': {'test': public}}
        self.gate = licensing.Gate(self.root, self.policy, lambda: self.now)
        self.envelope = license_issuer.issue(self.key, 'test', 'Customer', self.identity, days=365, now=self.now)

    def test_valid_annual_license_and_expiration_boundary(self):
        self.gate.activate(self.envelope)
        self.assertTrue(self.gate.allowed())
        self.now = self.envelope['payload']['expires_at'] - 1
        self.assertTrue(self.gate.allowed())
        self.now += 1
        self.assertFalse(self.gate.allowed())
        self.assertEqual('expired', self.gate.status()['status'])

    def test_tampered_or_foreign_license_cannot_replace_working_license(self):
        self.gate.activate(self.envelope)
        before = (self.root / 'data/license.local.json').read_bytes()
        self.envelope['payload']['expires_at'] += 86400
        with self.assertRaises(ValueError):
            self.gate.activate(self.envelope)
        self.assertEqual(before, (self.root / 'data/license.local.json').read_bytes())
        foreign = license_issuer.issue(self.key, 'test', 'Other', uuid.uuid4().hex, now=self.now)
        with self.assertRaises(ValueError):
            self.gate.activate(foreign)

    def test_wrong_key_future_license_and_missing_license_stop_measurements(self):
        self.assertFalse(self.gate.allowed())
        self.envelope['key_id'] = 'untrusted'
        self.assertEqual('invalid', licensing.verify(self.envelope, self.policy['public_keys'], self.identity, self.now)['status'])
        future = license_issuer.issue(self.key, 'test', 'Customer', self.identity, now=self.now + 60)
        self.assertEqual('not_yet_valid', licensing.verify(future, self.policy['public_keys'], self.identity, self.now)['status'])

    def test_expired_subscription_keeps_history_but_rejects_new_samples(self):
        self.gate.activate(self.envelope)
        store = monitor.Store(':memory:')
        self.addCleanup(store.db.close)
        store.license_gate = self.gate
        store.record('device', True, 1, '', 3, now=self.now)
        store.record_metrics('device', {'status': 'ok', 'values': {'memory_percent': 25}}, now=self.now)
        self.now = self.envelope['payload']['expires_at']
        store.record('device', False, 0, 'new failure', 3, now=self.now)
        store.record_metrics('device', {'status': 'ok', 'values': {'memory_percent': 99}}, now=self.now)
        self.assertEqual(1, store.db.execute('SELECT COUNT(*) FROM samples').fetchone()[0])
        self.assertEqual(1, store.db.execute('SELECT COUNT(*) FROM metric_samples').fetchone()[0])
        self.assertEqual(25, json.loads(store.db.execute('SELECT payload FROM metrics').fetchone()[0])['values']['memory_percent'])

    def test_workers_do_not_contact_devices_without_active_subscription(self):
        store = monitor.Store(':memory:')
        self.addCleanup(store.db.close)
        store.license_gate = self.gate
        class Stop:
            def __init__(self): self.done = False
            def is_set(self): return self.done
            def wait(self, seconds): self.done = True
        with patch.object(monitor, 'probe') as probe, patch.object(monitor.connectors, 'read') as read:
            monitor.collect({'devices': [{'id': 'must-not-be-contacted'}]}, store, Stop())
            monitor.collect_metrics({'devices': [{'id': 'must-not-be-contacted'}]}, store, Stop())
            probe.assert_not_called()
            read.assert_not_called()

    def test_missing_frozen_policy_fails_closed(self):
        with patch.object(__import__('sys'), 'frozen', True, create=True), patch.object(__import__('sys'), '_MEIPASS', str(self.root), create=True):
            self.assertEqual('configuration_error', licensing.Gate(self.root).status()['status'])

    def test_subscription_cannot_be_issued_for_more_than_one_year(self):
        with self.assertRaises(ValueError):
            license_issuer.issue(self.key, 'test', 'Customer', self.identity, days=367, now=self.now)
