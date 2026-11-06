"""Run the packaged server in an isolated fixture; no tasks, trust or LAN scans."""
import argparse
import http.cookiejar
import json
from pathlib import Path
import secrets
import shutil
import socket
import ssl
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import auth
import monitor
import tls_setup


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    bundle = args.bundle.resolve()
    result = {'routes': {}, 'controlled_no_lan_scan': True}
    with tempfile.TemporaryDirectory(prefix='frozen-smoke-', dir=args.report.resolve().parent) as temporary:
        root = Path(temporary)
        (root / 'data').mkdir()
        shutil.copytree(bundle / '_internal/web', root / 'web')
        # The real packaged worker runs, but the fixture supplies zero networks.
        (root / 'Detect-Networks.ps1').write_text("param([string]$OutputFile)\n'[]'|Set-Content -LiteralPath $OutputFile -Encoding UTF8\n", encoding='utf-8-sig')
        with socket.socket() as reservation:
            reservation.bind(('127.0.0.1', 0))
            port = reservation.getsockname()[1]
        config = {'interval': 5, 'threshold': 3, 'timeout': 1, 'discovery': {'enabled': True, 'auto_add': True},
                  'devices': [{'id': 'self', 'name': 'Frozen smoke test', 'host': '127.0.0.1',
                               'kind': 'Sunucu', 'method': 'tcp', 'port': port}]}
        (root / 'config.local.json').write_text(json.dumps(config), encoding='utf-8')
        password = secrets.token_urlsafe(20)
        store = monitor.Store(root / 'data/monitor.sqlite3')
        auth.Auth(store).add_user('smoke-admin', password, 'admin')
        store.db.close()
        certs = root / 'certs/panel'
        tls_setup.create(certs, 'localhost', ['127.0.0.1'])
        (root / 'server.local.json').write_text(json.dumps({'bind': '127.0.0.1', 'port': port,
            'tls_cert': 'certs/panel/panel-cert.pem', 'tls_key': 'certs/panel/panel-key.pem'}), encoding='utf-8')
        process = subprocess.Popen([str(bundle / 'CenterEK-Setup.exe'), '--serve', '--root', str(root)],
                                   cwd=root, creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            base = 'https://127.0.0.1:' + str(port)
            client = urllib.request.build_opener(urllib.request.ProxyHandler({}),
                urllib.request.HTTPSHandler(context=ssl.create_default_context(cafile=str(certs / 'panel-ca.pem'))),
                urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
            for _ in range(30):
                try:
                    with client.open(base + '/login', timeout=2) as response:
                        result['https'] = response.status == 200
                    break
                except OSError:
                    time.sleep(1)
            try:
                client.open(base + '/api/status')
                result['protected'] = False
            except urllib.error.HTTPError as error:
                result['protected'] = error.code == 401
            with client.open(urllib.request.Request(base + '/api/login', data=json.dumps({
                'username': 'smoke-admin', 'password': password}).encode(),
                headers={'Origin': base, 'Content-Type': 'application/json'})) as response:
                result['login'] = response.status
            for route in ('/api/status','/api/setup','/api/sessions','/dashboard.js','/theme.css','/i18n.js'):
                with client.open(base + route, timeout=5) as response:
                    result['routes'][route] = response.status
                    response.read()
            for _ in range(20):
                with client.open(base + '/api/discovery-status') as response:
                    status = json.load(response)
                if status['status'] in ('complete', 'error'):
                    break
                time.sleep(1)
            result['discovery_worker'] = status['status'] == 'complete' and status['total'] == 0
            result['ok'] = result.get('https') and result['protected'] and result['login'] == 200 and result['discovery_worker'] and all(v == 200 for v in result['routes'].values())
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill();process.wait()
    args.report.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result['ok'] else 1)


if __name__ == '__main__':
    main()
