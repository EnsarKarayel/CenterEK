import json
import socket
import threading
import unittest
from urllib.request import urlopen, build_opener, HTTPCookieProcessor, Request
import http.cookiejar
from http.server import ThreadingHTTPServer
import monitor
import auth
import tempfile
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError


class MonitoringTests(unittest.TestCase):
    def test_access_settings_require_admin_reauthentication_and_stage_only(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(monitor, 'ROOT', Path(folder)):
            accounts = auth.Auth(self.store, public_origin='https://panel.example.com')
            accounts.add_user('access-admin', 'access-test-password', 'admin')
            server = ThreadingHTTPServer(('127.0.0.1', 0), monitor.handler(self.store, {'devices': []}, accounts))
            thread = threading.Thread(target=server.serve_forever)
            thread.start()
            try:
                base = 'http://127.0.0.1:' + str(server.server_port)
                client = build_opener(HTTPCookieProcessor(http.cookiejar.CookieJar()))
                def post(route, payload, origin=base):
                    return client.open(Request(base + route, data=json.dumps(payload).encode(), headers={'Origin': origin, 'Content-Type': 'application/json'}))
                with post('/api/login', {'username': 'access-admin', 'password': 'access-test-password'}, 'https://panel.example.com'):
                    pass
                payload = {'current_password': 'wrong-password', 'settings': {'mode': 'local', 'bind': '127.0.0.1', 'port': 9876}}
                with self.assertRaises(HTTPError) as error:
                    post('/api/access-settings', payload)
                self.assertEqual(error.exception.code, 403)
                payload['current_password'] = 'access-test-password'
                with self.assertRaises(HTTPError) as error:
                    post('/api/access-settings', payload, 'https://evil.example.com')
                self.assertEqual(error.exception.code, 403)
                with post('/api/access-settings', payload) as response:
                    self.assertTrue(json.load(response)['restart_required'])
                self.assertTrue((Path(folder) / 'server.pending.local.json').exists())
                self.assertFalse((Path(folder) / 'server.local.json').exists())
            finally:
                server.shutdown()
                server.server_close()
                thread.join()

    def setUp(self):
        self.store = monitor.Store(':memory:')

    def tearDown(self):
        self.store.db.close()

    def test_threshold_recovery_and_no_duplicate_incidents(self):
        for t in range(1, 5):
            self.store.record('a', False, None, 'timeout', 3, t)
        incidents = self.store.db.execute('SELECT * FROM incidents').fetchall()
        self.assertEqual(len(incidents), 1)
        self.assertEqual(incidents[0]['started'], 1)
        self.assertEqual(incidents[0]['confirmed'], 3)
        self.store.record('a', True, 1, None, 3, 5)
        self.assertEqual(self.store.db.execute('SELECT ended FROM incidents').fetchone()[0], 5)

    def test_transient_failure_does_not_open_incident(self):
        self.store.record('a', False, None, 'timeout', 3, 1)
        self.store.record('a', True, 1, None, 3, 2)
        self.assertEqual(self.store.db.execute('SELECT COUNT(*) FROM incidents').fetchone()[0], 0)

    def test_real_tcp_probe(self):
        with socket.socket() as s:
            s.bind(('127.0.0.1', 0))
            s.listen()
            d = {'host': '127.0.0.1', 'port': s.getsockname()[1], 'method': 'tcp'}
            self.assertTrue(monitor.probe(d, 1)[0])
        self.assertFalse(monitor.probe(d, 1)[0])

    def test_http_unknown_stale_and_routes(self):
        config = {'interval': 30, 'devices': [{'id': 'a', 'name': 'test'}]}
        accounts = auth.Auth(self.store)
        accounts.add_user('http-test', 'http-test-password', 'viewer')
        server = ThreadingHTTPServer(('127.0.0.1', 0), monitor.handler(self.store, config, accounts))
        thread = threading.Thread(target=server.serve_forever)
        thread.start()
        try:
            base = 'http://127.0.0.1:' + str(server.server_port)
            client = build_opener(HTTPCookieProcessor(http.cookiejar.CookieJar()))
            with client.open(Request(base + '/api/login', data=json.dumps({'username': 'http-test', 'password': 'http-test-password'}).encode(),
                                     headers={'Origin': base, 'Content-Type': 'application/json'})):
                pass
            with client.open(base + '/api/status') as response:
                data = json.load(response)
                self.assertEqual(data['devices'][0]['status'], 'unknown')
                self.assertTrue(data['devices'][0]['stale'])
            with client.open(base) as response:
                self.assertIn(b'CenterEK', response.read())
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_invalid_target_rejected(self):
        with self.assertRaises(ValueError):
            monitor.validate({'interval': 30, 'threshold': 3, 'timeout': 2,
                              'devices': [{'id': 'a', 'name': 'bad', 'host': '-x', 'method': 'icmp'}]})


if __name__ == '__main__':
    unittest.main()
