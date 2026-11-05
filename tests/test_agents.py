import datetime
import json
from pathlib import Path
import ssl
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from http.server import ThreadingHTTPServer
import agents
import auth
import monitor


def report(computer='PC01'):
    return {'schema': 1, 'computer': computer, 'collected_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'status': 'ok', 'ips': ['192.0.2.10'], 'primary_ip': '192.0.2.10', 'address_source': 'Yerel ağ kartları',
            'interfaces': [{'name': 'Ethernet', 'ip': '192.0.2.10'}],
            'resources': {'cpu_percent': 0, 'memory_percent': 50},
            'sessions': [{'username': 'alice', 'domain': 'EXAMPLE', 'id': 1, 'state': 0}]}


class AgentTests(unittest.TestCase):
    def setUp(self):
        (monitor.ROOT / 'data').mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=monitor.ROOT / 'data')
        self.root = Path(self.temp.name)
        self.store = monitor.Store(':memory:')
        self.registry = agents.Registry(self.store, self.root)
        self.enrollment = self.registry.register('PC01', 'endpoint')

    def tearDown(self):
        self.store.db.close()
        self.temp.cleanup()

    def test_bound_identity_and_bad_token(self):
        self.assertEqual(self.registry.ingest(self.enrollment['token'], report('PC02'), 'endpoint'), 400)
        self.assertEqual(self.registry.ingest('unknown', report(), 'endpoint'), 401)
        self.assertEqual(self.registry.ingest(self.enrollment['token'], report(), 'directory'), 401)
        self.assertFalse((self.root / 'data' / 'endpoint-sessions' / 'PC02.json').exists())

    def test_latest_report_replay_rate_limit_and_revoke(self):
        data = report()
        self.assertEqual(self.registry.ingest(self.enrollment['token'], data, 'endpoint'), 202)
        saved = json.loads((self.root / 'data' / 'endpoint-sessions' / 'PC01.json').read_text(encoding='utf-8'))
        self.assertTrue(saved['authenticated'])
        self.assertEqual(saved['resources']['cpu_percent'], 0)
        history = self.store.history('agent-' + self.enrollment['id'])
        self.assertEqual(history['metrics'][0]['values']['memory_percent'], 50)
        self.assertEqual(self.registry.ingest(self.enrollment['token'], data, 'endpoint'), 409)
        data['collected_at'] = (datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(seconds=1)).isoformat()
        self.assertEqual(self.registry.ingest(self.enrollment['token'], data, 'endpoint'), 429)
        self.registry.revoke(self.enrollment['id'])
        self.assertEqual(self.registry.ingest(self.enrollment['token'], data, 'endpoint'), 401)
        self.assertNotIn(self.enrollment['token'], json.dumps(self.registry.list()))

    def test_stale_future_invalid_addresses_rejected(self):
        for delta in (-500, 500):
            data = report()
            data['collected_at'] = (datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(seconds=delta)).isoformat()
            self.assertEqual(self.registry.ingest(self.enrollment['token'], data, 'endpoint'), 400)
        data = report()
        data['ips'] = ['not-an-address']
        self.assertEqual(self.registry.ingest(self.enrollment['token'], data, 'endpoint'), 400)

    def test_directory_scope_and_field_allowlist(self):
        agent = self.registry.register('DC01', 'directory')
        data = {'schema': 1, 'server': 'DC01', 'collected_at': report()['collected_at'], 'domain': 'example.local',
                'netbios': 'EXAMPLE', 'users': [{'username': 'alice', 'password': 'MUST-NOT-PERSIST'}]}
        self.assertEqual(self.registry.ingest(agent['token'], data, 'directory'), 202)
        text = (self.root / 'data' / 'directory-inventory.json').read_text(encoding='utf-8')
        self.assertNotIn('MUST-NOT-PERSIST', text)

    def test_upload_requires_real_tls_not_auth_flag(self):
        accounts = auth.Auth(self.store, secure=True)
        server = ThreadingHTTPServer(('127.0.0.1', 0), monitor.handler(self.store, {'devices': []}, accounts, self.registry))
        thread = threading.Thread(target=server.serve_forever)
        thread.start()
        try:
            req = Request('http://127.0.0.1:'+str(server.server_port)+'/api/agent/endpoint', data=json.dumps(report()).encode(),
                          headers={'Authorization': 'Bearer '+self.enrollment['token'], 'Content-Type': 'application/json'})
            with self.assertRaises(HTTPError) as error:
                urlopen(req)
            self.assertEqual(error.exception.code, 403)
        finally:
            server.shutdown(); server.server_close(); thread.join()

    def test_real_tls_upload_certificate_validation(self):
        try:
            import cryptography
        except ImportError:
            self.skipTest('Optional cryptography package is required for the TLS integration test')
        import tls_setup
        certs = self.root / 'certs'
        tls_setup.create(certs, 'localhost', ['127.0.0.1'])
        accounts = auth.Auth(self.store, secure=True)
        server = ThreadingHTTPServer(('127.0.0.1', 0), monitor.handler(self.store, {'devices': []}, accounts, self.registry))
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(certs/'panel-cert.pem', certs/'panel-key.pem')
        server.socket = ctx.wrap_socket(server.socket, server_side=True)
        thread = threading.Thread(target=server.serve_forever)
        thread.start()
        try:
            url = 'https://127.0.0.1:'+str(server.server_port)+'/api/agent/endpoint'
            req = Request(url, data=json.dumps(report()).encode(), headers={
                'Authorization': 'Bearer '+self.enrollment['token'], 'Content-Type': 'application/json'})
            with urlopen(req, context=ssl.create_default_context(cafile=str(certs/'panel-ca.pem'))) as response:
                self.assertEqual(response.status, 202)
            # A client without the explicit CA must reject the certificate.
            from urllib.error import URLError
            with self.assertRaises(URLError):
                urlopen(req, context=ssl.create_default_context())
        finally:
            server.shutdown(); server.server_close(); thread.join()


if __name__ == '__main__':
    unittest.main()
