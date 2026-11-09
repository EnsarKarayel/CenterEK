import copy
import datetime
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
import agents
import monitor
import site_relay
import site_push
import site_enrollment


def payload():
    return {'schema': 1, 'computer': 'OFFICE-VOLO',
            'collected_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'devices': [{'id': 'firewall', 'name': 'Office FortiGate', 'host': '192.168.1.1',
                'kind': 'Firewall', 'method': 'tcp', 'port': 4443, 'collector_type': 'fortigate',
                'state': {'status': 'up', 'checked': time.time(), 'failures': 0, 'latency': 5},
                'metrics': {'status': 'ok', 'checked': time.time(), 'values': {'cpu_percent': 12,
                    'hostname': 'FG100F', 'token': 'MUST-NOT-LEAVE-OFFICE',
                    'clients': [{'ip': '192.168.1.239', 'hostname': 'PC01', 'mac': 'aa:bb:cc:dd:ee:ff'}],
                    'interfaces': [{'name': 'wan1', 'link': True, 'rx_bytes': 1000, 'tx_bytes': 2000}]}}}],
            'endpoints': []}


class SiteRelayTests(unittest.TestCase):
    def setUp(self):
        (monitor.ROOT / 'data').mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=monitor.ROOT / 'data')
        self.root = Path(self.temp.name)
        self.store = monitor.Store(':memory:')
        self.registry = agents.Registry(self.store, self.root)
        self.enrollment = self.registry.register('OFFICE-VOLO', 'site', networks=['192.168.0.0/22'],
                                                 directory_domain='volonet.local', directory_server='VOLO')

    def tearDown(self):
        self.store.db.close()
        self.temp.cleanup()

    def test_private_scope_and_global_id_isolation(self):
        for invalid in ['0.0.0.0/0', '8.8.8.0/24', '192.168.0.0/16']:
            with self.assertRaises(ValueError):
                site_relay.networks([invalid])
        data = payload()
        self.assertEqual(self.registry.ingest(self.enrollment['token'], data, 'site'), 202)
        rows = site_relay.load_devices(self.root)
        self.assertEqual(len(rows), 1)
        self.assertNotEqual(rows[0]['id'], 'firewall')
        self.assertEqual(rows[0]['site_id'], self.enrollment['id'])
        saved = (self.root / 'data/sites' / (self.enrollment['id'] + '.json')).read_text()
        self.assertNotIn('MUST-NOT-LEAVE-OFFICE', saved)
        self.assertNotIn(self.enrollment['token'], saved)
        metric = json.loads(self.store.db.execute('SELECT payload FROM metrics').fetchone()[0])
        self.assertEqual(metric['values']['clients'][0]['ip'], '192.168.1.239')

    def test_scope_escape_invalid_numbers_and_cross_kind_rejected(self):
        data = payload()
        data['devices'][0]['host'] = '10.42.1.4'
        self.assertEqual(self.registry.ingest(self.enrollment['token'], data, 'site'), 400)
        data = payload()
        data['devices'][0]['metrics']['values']['cpu_percent'] = float('nan')
        self.assertEqual(self.registry.ingest(self.enrollment['token'], data, 'site'), 400)
        self.assertEqual(self.registry.ingest(self.enrollment['token'], payload(), 'endpoint'), 401)
        self.assertEqual(self.store.db.execute('SELECT COUNT(*) FROM metrics').fetchone()[0], 0)

    def test_original_timestamps_not_refreshed_by_relay(self):
        data = payload()
        data['devices'][0]['state']['checked'] = time.time() - 1000
        data['devices'][0]['metrics']['checked'] = time.time() - 1000
        self.assertEqual(self.registry.ingest(self.enrollment['token'], data, 'site'), 202)
        rows = site_relay.load_devices(self.root)
        self.assertTrue(rows[0]['stale'])
        self.assertTrue(rows[0]['metrics']['stale'])
        self.assertNotIn('clients', rows[0]['metrics']['values'])

    def test_replay_revocation_and_duplicate_ids(self):
        data = payload()
        data['devices'].append(copy.deepcopy(data['devices'][0]))
        self.assertEqual(self.registry.ingest(self.enrollment['token'], data, 'site'), 400)
        data = payload()
        self.assertEqual(self.registry.ingest(self.enrollment['token'], data, 'site'), 202)
        self.assertEqual(self.registry.ingest(self.enrollment['token'], data, 'site'), 409)
        self.registry.revoke(self.enrollment['id'])
        self.assertEqual(self.registry.ingest(self.enrollment['token'], data, 'site'), 401)

    def test_directory_requires_explicit_domain_and_source(self):
        data = payload()
        data['directory'] = {'schema': 1, 'server': 'VOLO', 'domain': 'volonet.local', 'netbios': 'VOLONET',
            'collected_at': data['collected_at'], 'users': [{'username': 'alice', 'enabled': True, 'password': 'DO-NOT-RELAY'}],
            'computers': [], 'dns': [{'fqdn': 'PC01.volonet.local', 'ip': '192.168.1.239'}]}
        wrong = copy.deepcopy(data)
        wrong['directory']['domain'] = 'another.local'
        self.assertEqual(self.registry.ingest(self.enrollment['token'], wrong, 'site'), 400)
        self.assertEqual(self.registry.ingest(self.enrollment['token'], data, 'site'), 202)
        saved = json.loads((self.root / 'data/directory-inventory.json').read_text())
        self.assertEqual(saved['users'][0]['username'], 'alice')
        self.assertNotIn('password', saved['users'][0])

    def test_endpoint_namespaced_and_external_adapter_not_exported(self):
        data = payload()
        data['endpoints'] = [{'schema': 1, 'computer': 'PC01', 'status': 'ok', 'collected_at': data['collected_at'],
            'ips': ['192.168.1.239', '172.31.0.1'], 'sessions': [{'id': 1, 'state': 0, 'username': 'alice', 'domain': 'VOLONET'}],
            'interfaces': [{'ip': '192.168.1.239', 'name': 'Ethernet', 'transport': 'wired'}, {'ip': '172.31.0.1', 'name': 'Virtual'}],
            'resources': {'memory_total_gb': 32, 'password': 'NEVER-FORWARD'}}]
        self.assertEqual(self.registry.ingest(self.enrollment['token'], data, 'site'), 202)
        saved = json.loads(next((self.root/'data/endpoint-sessions').glob('*.json')).read_text())
        self.assertEqual(saved['computer'], 'PC01')
        self.assertEqual(saved['ips'], ['192.168.1.239'])
        self.assertEqual(len(saved['interfaces']), 1)
        self.assertNotIn('password', saved['resources'])
        self.assertTrue(saved['agent_id'].startswith('site-'+self.enrollment['id']))

    def test_client_strips_credentials_before_https_and_limits_origin(self):
        settings = dict(self.enrollment, url='https://telemetry.example', networks=['192.168.0.0/22'],
            directory_domain='volonet.local', directory_server='VOLO')
        data = payload()
        with patch.object(site_relay, 'snapshot', return_value=data):
            url, body = site_push.prepare(self.root, settings)
        self.assertEqual(url, 'https://telemetry.example/api/agent/site')
        self.assertNotIn(b'MUST-NOT-LEAVE-OFFICE', body)
        self.assertNotIn(self.enrollment['token'].encode(), body)
        self.assertEqual(self.registry.ingest(self.enrollment['token'], json.loads(body), 'site'), 202)
        self.assertEqual(site_relay.load_devices(self.root)[0]['status'], 'up')
        for invalid in ('http://telemetry.example', 'https://user:password@telemetry.example', 'https://telemetry.example/redirect'):
            with self.subTest(url=invalid), self.assertRaises(ValueError):
                site_push.prepare(self.root, dict(settings, url=invalid))

    def test_enrollment_is_encrypted_to_recipient_and_not_in_output(self):
        import base64
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa, padding
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        (self.root/'installation.local.json').write_text('{}')
        (self.root/'data').mkdir(exist_ok=True)
        private = rsa.generate_private_key(public_exponent=65537, key_size=3072)
        options = {'computer': 'BRANCH01', 'networks': ['192.168.0.0/22'], 'url': 'https://telemetry.example',
            'public_key': private.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode()}
        source, target = self.root/'options.json', self.root/'sealed.json'
        source.write_text(json.dumps(options))
        site_enrollment.create(self.root, source, target)
        envelope = json.loads(target.read_text())
        self.assertNotIn('token', envelope)
        key = private.decrypt(base64.b64decode(envelope['wrapped_key']), padding.OAEP(
            mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=site_enrollment.CONTEXT))
        record = json.loads(AESGCM(key).decrypt(base64.b64decode(envelope['nonce']),
            base64.b64decode(envelope['ciphertext']), site_enrollment.CONTEXT))
        self.assertEqual(record['computer'], 'BRANCH01')
        self.assertEqual(record['kind'], 'site')
        self.assertNotIn(record['token'], target.read_text())

    def test_readonly_snapshot_preserves_source_and_is_accepted_on_wire(self):
        (self.root/'data').mkdir(exist_ok=True)
        source = monitor.Store(self.root/'data/monitor.sqlite3')
        data = payload()['devices'][0]
        (self.root/'config.local.json').write_text(json.dumps({'devices': [dict(data, collector={'type':'fortigate', 'password':'HIDDEN'})]}))
        source.record('firewall', True, 5, None, 3)
        source.record_metrics('firewall', data['metrics'])
        source.db.close()
        settings = dict(self.enrollment, url='https://telemetry.example', networks=['192.168.0.0/22'])
        _, body = site_push.prepare(self.root, settings)
        self.assertNotIn(b'HIDDEN', body)
        self.assertNotIn(b'MUST-NOT-LEAVE-OFFICE', body)
        self.assertEqual(self.registry.ingest(self.enrollment['token'], json.loads(body), 'site'), 202)


if __name__ == '__main__':
    unittest.main()
