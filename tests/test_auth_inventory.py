import datetime
import http.cookiejar
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.request import Request, build_opener, HTTPCookieProcessor
from urllib.error import HTTPError
from http.server import ThreadingHTTPServer
import auth
import connectors
import directory
import endpoints
import monitor


class AuthTests(unittest.TestCase):
    def setUp(self):
        self.store = monitor.Store(':memory:')
        self.auth = auth.Auth(self.store)
        self.auth.add_user('operator', 'test-password-long', 'admin')
        self.config = {'interval': 30, 'devices': [{'id': 'a', 'name': 'test'}]}
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), monitor.handler(self.store, self.config, self.auth))
        self.thread = threading.Thread(target=self.server.serve_forever)
        self.thread.start()
        self.base = 'http://127.0.0.1:' + str(self.server.server_port)
        self.client = build_opener(HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.store.db.close()

    def login(self, password='test-password-long', origin=None):
        req = Request(self.base + '/api/login', data=json.dumps({'username': 'operator', 'password': password}).encode(),
                      headers={'Content-Type': 'application/json', 'Origin': origin or self.base})
        return self.client.open(req)

    def test_all_data_routes_protected_and_login_logout(self):
        for route in ['/api/status', '/api/inventory', '/api/sessions', '/api/report.csv', '/api/history/a', '/api/accounts', '/api/agents', '/api/setup']:
            with self.assertRaises(HTTPError) as error:
                self.client.open(self.base + route)
            self.assertEqual(error.exception.code, 401)
        with self.login() as response:
            cookie = response.headers['Set-Cookie']
            self.assertIn('HttpOnly', cookie)
            self.assertIn('SameSite=Strict', cookie)
        with self.client.open(self.base + '/api/status') as response:
            self.assertEqual(response.status, 200)
        with self.client.open(self.base + '/api/me') as response:
            user = json.load(response)
            self.assertEqual(user['username'], 'operator')
            self.assertNotIn('credential', user)
        with self.client.open(Request(self.base + '/api/logout', data=b'', headers={'Origin': self.base})):
            pass
        with self.assertRaises(HTTPError):
            self.client.open(self.base + '/api/status')

    def test_csrf_blocked(self):
        with self.assertRaises(HTTPError) as error:
            self.login(origin='https://other.invalid')
        self.assertEqual(error.exception.code, 403)

    def test_account_management_requires_admin_reauthentication(self):
        self.login().close()
        def change(**fields):
            data = {'action': 'create', 'username': 'reader', 'password': 'new-password-long',
                    'current_password': 'test-password-long', 'role': 'viewer'}
            data.update(fields)
            return self.client.open(Request(self.base + '/api/accounts', data=json.dumps(data).encode(),
                                           headers={'Origin': self.base, 'Content-Type': 'application/json'}))
        with self.assertRaises(HTTPError) as error:
            change(current_password='incorrect')
        self.assertEqual(error.exception.code, 403)
        change().close()
        token, _ = self.auth.login('reader', 'new-password-long', 'test-client')
        self.assertIsNotNone(self.auth.user(token))
        for route in ('/api/accounts', '/api/setup'):
            with self.assertRaises(HTTPError) as denied:
                build_opener().open(Request(self.base + route, headers={'Cookie': 'centerek_session=' + token}))
            self.assertEqual(denied.exception.code, 403)
        with self.client.open(self.base + '/api/setup') as response:
            readiness = json.load(response)
        self.assertFalse(readiness['https'])
        self.assertNotIn('password', json.dumps(readiness))
        change(action='disable', username='reader').close()
        self.assertIsNone(self.auth.user(token))
        with self.assertRaises(HTTPError) as error:
            change(action='disable', username='operator')
        self.assertEqual(error.exception.code, 400)
        with self.store.lock:
            rows = [tuple(r) for r in self.store.db.execute('SELECT actor,action,target FROM account_audit')]
        self.assertEqual(rows, [('operator', 'create', 'reader'), ('operator', 'disable', 'reader')])

    def test_failed_login_throttled(self):
        for n in range(6):
            with self.assertRaises(HTTPError) as error:
                self.login(password='incorrect')
            self.assertEqual(error.exception.code, 429 if n == 5 else 401)

    def test_viewer_cannot_list_accounts(self):
        with self.store.lock, self.store.db:
            self.store.db.execute("UPDATE users SET role='viewer'")
        with self.login():
            pass
        for route in ('/api/accounts', '/api/agents'):
            with self.assertRaises(HTTPError) as error:
                self.client.open(self.base + route)
            self.assertEqual(error.exception.code, 403)

    def test_password_not_plaintext_and_disabled_session_revoked(self):
        row = dict(self.store.db.execute('SELECT * FROM users').fetchone())
        self.assertNotIn('test-password-long', json.dumps(row))
        token, _ = self.auth.login('operator', 'test-password-long', 'test')
        self.assertIsNotNone(self.auth.user(token))
        with self.store.lock, self.store.db:
            self.store.db.execute('UPDATE users SET enabled=0')
        self.assertIsNone(self.auth.user(token))


class InventoryTests(unittest.TestCase):
    def test_fortigate_partial_sections_keep_working_traffic(self):
        class Response:
            def __init__(self, values): self.values = values
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self, limit): return json.dumps({'status': 'success', 'results': self.values}).encode()
        def response(req, timeout):
            if 'system/status' in req.full_url:
                return Response({'model': 'FG100F'})
            if 'system/interface' in req.full_url:
                return Response({'wan1': {'link': True, 'rx_bytes': 100}})
            if 'resource/usage' in req.full_url:
                return Response({'cpu': [{'current': 0}], 'mem': [{'current': 34}]})
            raise HTTPError(req.full_url, 403, 'Forbidden', {}, None)
        with patch.dict('os.environ', {'TEST_TOKEN': 'secret'}), patch.object(connectors, 'build_opener') as factory:
            factory.return_value.open.side_effect = response
            data = connectors.fortigate({'host': '127.0.0.1'}, {'token_env': 'TEST_TOKEN'})
        self.assertEqual(data['cpu_percent'], 0)
        self.assertEqual(data['memory_percent'], 34)
        self.assertEqual(len(data['interfaces']), 1)
        self.assertEqual(data['inventory_status'], 'error')
        self.assertIn('HTTP 403', data['section_errors'][0])

    def test_client_dedup_and_no_online_inference(self):
        rows = connectors.normalize_clients([{'ipv4_address': '192.0.2.1', 'mac': 'aa:bb', 'hostname': '<script>'}] * 2)
        self.assertEqual(len(rows), 1)
        self.assertIsNone(rows[0]['online'])

    def test_directory_and_session_domain_match_staleness(self):
        (monitor.ROOT / 'data').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=monitor.ROOT / 'data') as temp:
            path = Path(temp)
            now = datetime.datetime.now(datetime.timezone.utc)
            directory_file = path / 'directory.json'
            directory_file.write_text(json.dumps({'schema': 1, 'collected_at': now.isoformat(),
                'domain': 'example.local', 'netbios': 'EXAMPLE', 'computers': [],
                'users': [{'username': 'alice', 'display_name': 'Alice'}]}), encoding='utf-8')
            imported = directory.load(directory_file)
            reports = path / 'reports'
            reports.mkdir()
            report = {'schema': 1, 'collected_at': (now-datetime.timedelta(seconds=200)).isoformat(),
                'computer': 'pc1', 'ips': ['192.0.2.1'], 'status': 'ok', 'sessions': [
                    {'username': 'alice', 'domain': 'EXAMPLE', 'state': 0, 'id': 1},
                    {'username': 'alice', 'domain': 'OTHER', 'state': 4, 'id': 2}]}
            (reports / 'pc1.json').write_text(json.dumps(report), encoding='utf-8')
            result = endpoints.load(reports, imported)
            self.assertTrue(result['sessions'][0]['ad_match'])
            self.assertFalse(result['sessions'][1]['ad_match'])
            self.assertTrue(result['sessions'][0]['stale'])

    def test_inventory_not_duplicated_into_history(self):
        store = monitor.Store(':memory:')
        try:
            store.record_metrics('a', {'status': 'ok', 'values': {'clients': [{'ip': '192.0.2.1'}]} })
            payload = store.db.execute('SELECT payload FROM metric_samples').fetchone()[0]
            self.assertNotIn('192.0.2.1', payload)
            self.assertIn('192.0.2.1', store.db.execute('SELECT payload FROM metrics').fetchone()[0])
        finally:
            store.db.close()


if __name__ == '__main__':
    unittest.main()
