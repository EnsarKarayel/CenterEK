import http.cookiejar
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.request import urlopen
from urllib.error import HTTPError
from http.server import ThreadingHTTPServer
import auth
import monitor
import setup_app


class DeploymentTests(unittest.TestCase):
    def test_health_is_minimal_and_detects_dead_workers(self):
        store = monitor.Store(':memory:')
        server = ThreadingHTTPServer(('127.0.0.1', 0), monitor.handler(store, {'devices': []}, auth.Auth(store)))
        thread = threading.Thread(target=server.serve_forever)
        thread.start()
        try:
            url = 'http://127.0.0.1:' + str(server.server_port) + '/healthz'
            with urlopen(url) as response:
                self.assertEqual(json.load(response), {'status': 'ok'})
            store.health_workers = [threading.Thread()]
            with self.assertRaises(HTTPError) as error:
                urlopen(url)
            self.assertEqual(error.exception.code, 503)
            self.assertNotIn('devices', json.loads(error.exception.read()))
        finally:
            server.shutdown();server.server_close();thread.join();store.db.close()

    def test_headless_installer_reports_no_secret_on_failure(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            options = root / 'options.json'
            report = root / 'result.json'
            secret = 'never-log-this-private-password'
            options.write_text(json.dumps({'target': str(root / 'CenterEK'), 'username': 'azure-admin', 'password': secret}))
            with patch('installer_core.install', side_effect=RuntimeError(secret)):
                code = setup_app.unattended_install(options, report)
            self.assertEqual(code, 1)
            self.assertNotIn(secret, report.read_text())
            self.assertEqual(json.loads(report.read_text())['error_type'], 'RuntimeError')

    def test_headless_installer_passes_explicit_options(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            options = root / 'options.json'
            report = root / 'result.json'
            options.write_text(json.dumps({'target': str(root / 'CenterEK'), 'username': 'azure-admin', 'password': 'test-long-private-password', 'auto_discover': False}))
            observed = {}
            def install(configuration, *args):
                observed['discovery'] = configuration.auto_discover
                return 'https://10.42.1.4:8765'
            with patch('installer_core.install', side_effect=install):
                self.assertEqual(setup_app.unattended_install(options, report), 0)
            self.assertFalse(observed['discovery'])
            self.assertTrue(json.loads(report.read_text())['ok'])
