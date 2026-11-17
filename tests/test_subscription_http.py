import base64
import http.cookiejar
import json
from pathlib import Path
import ssl
import tempfile
import threading
import unittest
import uuid
from urllib.error import HTTPError
from urllib.request import Request, build_opener, HTTPSHandler, HTTPCookieProcessor, ProxyHandler
from unittest.mock import patch
from http.server import ThreadingHTTPServer
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
import agents
import auth
import licensing
import license_issuer
import monitor
import tls_setup


class SubscriptionHTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / 'data').mkdir()
        self.identity = uuid.uuid4().hex
        (self.root / 'installation.local.json').write_text(json.dumps({'installation_id': self.identity}))
        self.key = Ed25519PrivateKey.generate()
        public = base64.b64encode(self.key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)).decode()
        self.now = 2000000000
        self.gate = licensing.Gate(self.root, {'mode': 'commercial', 'public_keys': {'test': public}}, lambda: self.now)
        self.gate.activate(license_issuer.issue(self.key, 'test', 'Customer', self.identity, now=self.now))
        self.store = monitor.Store(':memory:')
        self.store.license_gate = self.gate
        self.accounts = auth.Auth(self.store, secure=True)
        self.accounts.add_user('admin', 'fixture-password-long', 'admin')
        self.registry = agents.Registry(self.store, self.root)
        self.agent = self.registry.register('PC01', 'endpoint')
        config = {'interval': 30, 'timeout': 1, 'threshold': 3, 'devices': [{'id': 'device', 'name': 'Historical device', 'host': '127.0.0.1', 'kind': 'Sunucu', 'method': 'tcp', 'port': 8765}]}
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), monitor.handler(self.store, config, self.accounts, self.registry))
        tls_setup.create(self.root / 'certs', 'localhost', ['127.0.0.1'])
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(str(self.root / 'certs/panel-cert.pem'), str(self.root / 'certs/panel-key.pem'))
        self.server.socket = context.wrap_socket(self.server.socket, server_side=True)
        self.thread = threading.Thread(target=self.server.serve_forever)
        self.thread.start()
        self.base = 'https://127.0.0.1:' + str(self.server.server_port)
        self.client = build_opener(ProxyHandler({}), HTTPSHandler(context=ssl.create_default_context(cafile=str(self.root / 'certs/panel-ca.pem'))), HTTPCookieProcessor(http.cookiejar.CookieJar()))
        with self.post('/api/login', {'username': 'admin', 'password': 'fixture-password-long'}):
            pass
        self.now += 366 * 86400

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.store.db.close()
        self.temp.cleanup()

    def post(self, route, payload, **headers):
        return self.client.open(Request(self.base + route, data=json.dumps(payload).encode(),
            headers=dict({'Origin': self.base, 'Content-Type': 'application/json'}, **headers)), timeout=5)

    def test_expired_subscription_allows_login_history_and_export(self):
        for route in ('/api/status', '/api/report.csv', '/api/history/device', '/api/license'):
            with self.client.open(self.base + route, timeout=5) as response:
                self.assertEqual(200, response.status)
        with self.client.open(self.base + '/api/license') as response:
            self.assertEqual('expired', json.load(response)['status'])

    def test_expired_subscription_rejects_authenticated_agent_before_ingestion(self):
        with patch.object(self.registry, 'ingest') as ingest:
            with self.assertRaises(HTTPError) as error:
                self.post('/api/agent/endpoint', {}, Authorization='Bearer ' + self.agent['token'])
            self.assertEqual(403, error.exception.code)
            error.exception.close()
            ingest.assert_not_called()

    def test_valid_renewal_reenables_collection_without_restarting(self):
        renewal = license_issuer.issue(self.key, 'test', 'Customer', self.identity, now=self.now)
        with self.post('/api/license', renewal) as response:
            self.assertEqual('active', json.load(response)['status'])
        self.assertTrue(self.gate.allowed())

    def test_cross_origin_activation_and_settings_change_rejected(self):
        renewal = license_issuer.issue(self.key, 'test', 'Customer', self.identity, now=self.now)
        with self.assertRaises(HTTPError) as error:
            self.client.open(Request(self.base + '/api/license', data=json.dumps(renewal).encode(), headers={'Origin': 'https://foreign.invalid', 'Content-Type': 'application/json'}))
        self.assertEqual(403, error.exception.code)
        error.exception.close()
        with self.assertRaises(HTTPError) as error:
            self.post('/api/devices', {})
        self.assertEqual(403, error.exception.code)
        error.exception.close()
