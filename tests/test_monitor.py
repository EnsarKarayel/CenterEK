import json
import socket
import threading
import unittest
from urllib.request import urlopen, build_opener, HTTPCookieProcessor, Request
import http.cookiejar
from http.server import ThreadingHTTPServer
import monitor
import auth


class MonitoringTests(unittest.TestCase):
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
