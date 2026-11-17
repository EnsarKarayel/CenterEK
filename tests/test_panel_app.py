import importlib.util
import json
from pathlib import Path
import struct
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import build_opener, ProxyHandler
from http.server import ThreadingHTTPServer
import auth
import monitor
import panel_app

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('build_store_panel', ROOT / 'scripts/store/build_panel.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class PanelAppTests(unittest.TestCase):
    def test_public_assets_do_not_expose_authenticated_api_or_arbitrary_files(self):
        store = monitor.Store(':memory:')
        server = ThreadingHTTPServer(('127.0.0.1', 0), monitor.handler(store, {'devices': []}, auth.Auth(store)))
        thread = threading.Thread(target=server.serve_forever)
        thread.start()
        client = build_opener(ProxyHandler({}))
        base = 'http://127.0.0.1:' + str(server.server_port)
        try:
            for route, (_, mime) in panel_app.FILES.items():
                with self.subTest(route=route), client.open(base + route) as response:
                    self.assertEqual(response.status, 200)
                    self.assertEqual(response.headers['Content-Type'], mime)
                    self.assertEqual(response.headers['Cache-Control'], 'no-store')
                    if route == '/panel-worker.js':
                        self.assertEqual(response.headers['Service-Worker-Allowed'], '/')
            for route in ('/api/status', '/api/sessions', '/api/accounts', '/api/license'):
                with self.subTest(route=route), self.assertRaises(HTTPError) as caught:
                    client.open(base + route)
                self.assertEqual(caught.exception.code, 401)
                caught.exception.close()
            with client.open(base + '/panel/../../config.local.json') as response:
                self.assertTrue(response.url.endswith('/login'))
                self.assertNotIn(b'agent_token', response.read())
        finally:
            server.shutdown(); server.server_close(); thread.join(); store.db.close()

    def test_manifest_icons_and_export_are_complete_and_public_only(self):
        manifest = json.loads((ROOT / 'web/panel/manifest.webmanifest').read_text(encoding='utf-8'))
        self.assertEqual(manifest['start_url'], '/panel/')
        self.assertEqual(manifest['display'], 'standalone')
        for size in (192, 512):
            data = (ROOT / f'web/panel/icon-{size}.png').read_bytes()
            self.assertEqual(struct.unpack('!II', data[16:24]), (size, size))
            self.assertEqual(data, builder.icon(size))
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'export'
            report = builder.export(output, 'https://panel.example')
            self.assertFalse(report['store_ready'])
            self.assertFalse(report['msix_created'])
            files = list((output / 'public').rglob('*'))
            self.assertEqual(sum(p.is_file() for p in files), len({name for name, _ in panel_app.FILES.values()}))
            self.assertFalse(any(p.suffix in ('.json', '.py', '.exe', '.ps1', '.sqlite3') for p in files))
            with self.assertRaises(FileExistsError):
                builder.export(output, 'https://panel.example')

    def test_export_rejects_insecure_or_credential_bearing_origin(self):
        with tempfile.TemporaryDirectory() as tmp:
            for origin in ('http://panel.example', 'https://user:pass@panel.example', 'https://panel.example/path', 'https://panel.example/?token=secret'):
                with self.subTest(origin=origin), self.assertRaises(ValueError):
                    builder.export(Path(tmp) / 'bad', origin)


if __name__ == '__main__':
    unittest.main()
