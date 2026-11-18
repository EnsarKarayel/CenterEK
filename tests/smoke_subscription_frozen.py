"""Build a QA-only subscription runtime and exercise real expiry; no private key is saved."""
import argparse
import base64
import http.cookiejar
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import ssl
import subprocess
import sys
import tempfile
import time
import uuid
from urllib.error import HTTPError
from urllib.request import Request, build_opener, ProxyHandler, HTTPSHandler, HTTPCookieProcessor
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
import auth
import licensing
import license_issuer
import monitor
import tls_setup


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    source = Path(__file__).resolve().parents[1]
    result = {'kind': 'packaged-subscription-fixture', 'clean_windows_acceptance': False}
    key = Ed25519PrivateKey.generate()  # Intentionally ephemeral and never serialized.
    public = base64.b64encode(key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)).decode()
    with tempfile.TemporaryDirectory(prefix='qa-subscription-', dir=source / 'data') as build_inputs:
        inputs = Path(build_inputs)
        policy = inputs / 'policy.json'
        policy.write_text(json.dumps({'mode': 'commercial', 'public_keys': {'qa': public}}))
        eula = inputs / 'qa-terms.txt'
        eula.write_text('QA ONLY. NOT A CUSTOMER CONTRACT. No publisher approval, customer agreement or commercial release is asserted. '
                        'This ephemeral subscription fixture exists only to verify compiled-runtime expiry and renewal behavior. '
                        'Do not distribute or sell this test bundle.', encoding='utf-8')
        before = set((source / 'data/releases').iterdir())
        log = args.report.with_suffix('.build.local.log')
        with log.open('w', encoding='utf-8') as stream:
            subprocess.run([sys.executable, str(source / 'build_windows.py'), '--license-policy', str(policy), '--eula-file', str(eula), '--qa-only'],
                           cwd=source, stdout=stream, stderr=subprocess.STDOUT, check=True)
        created = set((source / 'data/releases').iterdir()) - before
        if len(created) != 1:
            raise RuntimeError('Could not identify the isolated QA build')
        release = created.pop()
        result['qa_release'] = release.name
        bundle = release / 'dist/CenterEK-Setup'
        with tempfile.TemporaryDirectory(prefix='ce-sub-') as temporary:
            root = Path(temporary)
            (root / 'data').mkdir()
            shutil.copytree(bundle / '_internal/web', root / 'web')
            identity = uuid.uuid4().hex
            (root / 'installation.local.json').write_text(json.dumps({'installation_id': identity}))
            with socket.socket() as reservation:
                reservation.bind(('127.0.0.1', 0))
                port = reservation.getsockname()[1]
            config = {'interval': 5, 'threshold': 1, 'timeout': 1, 'discovery': {'enabled': False},
                      'devices': [{'id': 'self', 'name': 'Subscription fixture', 'host': '127.0.0.1', 'kind': 'Sunucu', 'method': 'tcp', 'port': port}]}
            (root / 'config.local.json').write_text(json.dumps(config))
            store = monitor.Store(root / 'data/monitor.sqlite3')
            password = secrets.token_urlsafe(24)
            try:
                auth.Auth(store).add_user('qa-admin', password, 'admin')
            finally:
                store.db.close()
            tls_setup.create(root / 'certs/panel', 'localhost', ['127.0.0.1'])
            (root / 'server.local.json').write_text(json.dumps({'bind': '127.0.0.1', 'port': port,
                'tls_cert': 'certs/panel/panel-cert.pem', 'tls_key': 'certs/panel/panel-key.pem'}))
            process = subprocess.Popen([str(bundle / 'CenterEK-Setup.exe'), '--serve', '--root', str(root)], cwd=root, creationflags=subprocess.CREATE_NO_WINDOW)
            base = 'https://127.0.0.1:' + str(port)
            client = build_opener(ProxyHandler({}), HTTPSHandler(context=ssl.create_default_context(cafile=str(root / 'certs/panel/panel-ca.pem'))), HTTPCookieProcessor(http.cookiejar.CookieJar()))
            def post(path, payload):
                return client.open(Request(base + path, data=json.dumps(payload).encode(), headers={'Origin': base, 'Content-Type': 'application/json'}), timeout=4)
            def status():
                with client.open(base + '/api/status', timeout=4) as response:
                    return json.load(response)
            try:
                for attempt in range(30):
                    try:
                        with post('/api/login', {'username': 'qa-admin', 'password': password}): pass
                        break
                    except OSError:
                        time.sleep(1)
                first = status()
                result['missing_license_blocks_collection'] = first['license']['status'] == 'missing' and first['devices'][0]['checked'] is None
                license = license_issuer.issue(key, 'qa', 'Ephemeral QA fixture', identity)
                license['payload']['expires_at'] = int(time.time()) + 12
                license['signature'] = base64.b64encode(key.sign(licensing.canonical(license['payload']))).decode()
                with post('/api/license', license): pass
                deadline = time.monotonic() + 25
                saw_sample = False
                while time.monotonic() < deadline:
                    current = status()
                    saw_sample |= current['devices'][0]['checked'] is not None
                    if current['license']['status'] == 'expired': break
                    time.sleep(1)
                previous = status()
                time.sleep(6)
                expired = status()
                result['natural_expiry_stops_new_samples'] = saw_sample and expired['license']['status'] == 'expired' and previous['devices'][0]['checked'] == expired['devices'][0]['checked']
                with client.open(base + '/api/report.csv') as response:
                    result['expired_export_available'] = response.status == 200
                with post('/api/license', license_issuer.issue(key, 'qa', 'Ephemeral QA fixture', identity)): pass
                deadline = time.monotonic() + 10
                while time.monotonic() < deadline:
                    current = status()
                    if current['devices'][0]['checked'] != expired['devices'][0]['checked']: break
                    time.sleep(1)
                result['renewal_resumes_same_process'] = current['license']['status'] == 'active' and current['devices'][0]['checked'] != expired['devices'][0]['checked'] and process.poll() is None
                result['ok'] = all(result.get(name) is True for name in ('missing_license_blocks_collection', 'natural_expiry_stops_new_samples', 'expired_export_available', 'renewal_resumes_same_process'))
            finally:
                process.terminate()
                process.wait(timeout=15)
    args.report.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, indent=2))
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
