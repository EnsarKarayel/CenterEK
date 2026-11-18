"""Add fixed PWA assets to an existing gateway; preserve protected backend access."""
import argparse
import base64
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import time
import uuid
from urllib.request import Request, build_opener

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import panel_app
from file_security import restrict
from browser_access import PANEL_PUBLIC_PATHS, assert_publishable, with_panel_assets
from publish_browser_access import NoRedirect, probe_anonymous


def public_archive():
    buffer = io.BytesIO()
    hashes = {}
    written = set()
    with tarfile.open(fileobj=buffer, mode='w:gz') as archive:
        for route, (name, _) in panel_app.FILES.items():
            relative = 'panel/index.html' if route == '/panel/' else route.lstrip('/')
            data = (ROOT / 'web/panel' / name).read_bytes()
            hashes[route] = hashlib.sha256(data).hexdigest()
            if relative in written:
                continue
            written.add(relative)
            entry = tarfile.TarInfo(relative)
            entry.size = len(data)
            entry.mode = 0o644
            archive.addfile(entry, io.BytesIO(data))
    return base64.b64encode(buffer.getvalue()).decode('ascii'), hashes


def verify_assets(origin, hashes):
    opener = build_opener(NoRedirect)
    for route, (_, mime) in panel_app.FILES.items():
        with opener.open(Request(origin + route, headers={'Cache-Control': 'no-cache'}), timeout=30) as response:
            if response.status != 200 or hashlib.sha256(response.read()).hexdigest() != hashes[route]:
                raise RuntimeError('Live PWA asset mismatch')
            if response.headers.get_content_type() != mime.split(';')[0]:
                raise RuntimeError('Live PWA asset MIME mismatch')
            if response.headers.get('Cache-Control') != 'no-store':
                raise RuntimeError('Live PWA cache policy mismatch')
            if route == '/panel-worker.js' and response.headers.get('Service-Worker-Allowed') != '/':
                raise RuntimeError('Live PWA scope mismatch')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--azure-python', type=Path)
    parser.add_argument('--subscription', required=True)
    parser.add_argument('--resource-group', required=True)
    parser.add_argument('--app-name', required=True)
    parser.add_argument('--tenant-id', required=True)
    parser.add_argument('--client-id', required=True)
    parser.add_argument('--principal-id', action='append', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    restrict(args.output, directory=True)
    command = [str(args.azure_python), '-m', 'azure.cli'] if args.azure_python else ['az']

    def az(*arguments):
        result = subprocess.run(command + list(arguments) + ['--only-show-errors', '-o', 'json'],
                                capture_output=True, text=True, encoding='utf-8', timeout=180)
        if result.returncode:
            raise RuntimeError('Azure operation failed (response suppressed to protect secrets)')
        return json.loads(result.stdout) if result.stdout.strip() else None

    def save(name, data):
        path = args.output / name
        path.touch(exist_ok=False)
        restrict(path)
        path.write_text(json.dumps(data, indent=2), encoding='utf-8')
        return path

    if az('account', 'show')['id'] != args.subscription:
        raise ValueError('Unexpected Azure subscription')
    base = f'https://management.azure.com/subscriptions/{args.subscription}/resourceGroups/{args.resource_group}/providers/Microsoft.App/containerApps/{args.app_name}'
    api = '?api-version=2025-07-01'
    app = az('rest', '--method', 'get', '--url', base + api)
    auth = az('rest', '--method', 'get', '--url', base + '/authConfigs/current' + api)
    ingress = app['properties']['configuration']['ingress']
    origin = 'https://' + ingress['fqdn']
    expected = dict(tenant_id=args.tenant_id, client_id=args.client_id, principal_ids=args.principal_id, origin=origin)
    assert_publishable(auth, **expected)
    if (app['properties']['provisioningState'] != 'Succeeded' or not ingress['external']
            or ingress['allowInsecure'] or ingress['targetPort'] != 8080
            or len(app['properties']['template']['containers']) != 1):
        raise ValueError('Gateway is not in the expected healthy HTTPS configuration')
    secrets = az('rest', '--method', 'post', '--url', base + '/listSecrets' + api)['value']
    nginx = next(s['value'] for s in secrets if s['name'] == 'nginx-config')
    del secrets
    config = with_panel_assets(nginx)
    encoded, hashes = public_archive()
    save('app-before.json', app)
    save('auth-before.json', auth)
    save('nginx-before.json', {'config': nginx})
    template = copy.deepcopy(app['properties']['template'])
    container = template['containers'][0]
    if container['name'] != 'browser-gateway':
        raise ValueError('Unexpected gateway container')
    volume = next(v for v in template['volumes'] if v['name'] == 'configuration')
    volume['secrets'].extend([{'secretRef': 'pwa-assets', 'path': 'pwa-assets.b64'}, {'secretRef': 'pwa-nginx-config', 'path': 'pwa-nginx.conf'}])
    container['command'] = ['sh', '-c']
    container['args'] = ["set -eu; mkdir -p /tmp/centerek-panel; base64 -d /etc/centerek/pwa-assets.b64 | tar -xz --no-same-owner -C /tmp/centerek-panel; nginx -t -c /etc/centerek/pwa-nginx.conf; exec nginx -c /etc/centerek/pwa-nginx.conf -g 'daemon off;'"]
    template['revisionSuffix'] = 'pwa-' + uuid.uuid4().hex[:10]
    updated_auth = copy.deepcopy(auth['properties'])
    updated_auth['globalValidation']['excludedPaths'] = list(PANEL_PUBLIC_PATHS)
    assert_publishable({'properties': updated_auth}, **expected, panel_assets=True)
    save('plan.json', {'origin': origin, 'public_paths': PANEL_PUBLIC_PATHS, 'asset_sha256': hashes,
         'protected': ['/', '/login', '/api/*', '/.auth/*'], 'new_resources': False, 'applied': False})
    print('PLAN_READY exact public static assets only; backend/auth identities/scaling unchanged', flush=True)
    if not args.apply:
        return

    def patch(body, auth_config=False):
        path = save('request-' + uuid.uuid4().hex + '.json', body)
        return az('rest', '--method', 'put' if auth_config else 'patch', '--url', base + ('/authConfigs/current' if auth_config else '') + api, '--body', '@' + str(path.resolve()))

    def wait():
        deadline = time.monotonic() + 240
        while time.monotonic() < deadline:
            current = az('rest', '--method', 'get', '--url', base + api)
            props = current['properties']
            if props.get('provisioningState') == 'Succeeded' and props.get('latestRevisionName') == props.get('latestReadyRevisionName'):
                return current
            if props.get('provisioningState') in ('Failed', 'Canceled'):
                raise RuntimeError('Gateway revision failed')
            time.sleep(5)
        raise RuntimeError('Gateway readiness timeout')

    changed = False
    try:
        az('containerapp', 'secret', 'set', '--name', args.app_name, '--resource-group', args.resource_group,
           '--secrets', 'pwa-assets=' + encoded, 'pwa-nginx-config=' + config)
        print('PUBLIC_ASSET_SECRETS_ADDED', flush=True)
        changed = True
        patch({'properties': {'template': template}})
        wait()
        print('PWA_REVISION_READY', flush=True)
        patch({'properties': updated_auth}, auth_config=True)
        deadline = time.monotonic() + 120
        while True:
            try:
                verify_assets(origin, hashes)
                probe_anonymous(origin)
                break
            except Exception:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(5)
        live_auth = az('rest', '--method', 'get', '--url', base + '/authConfigs/current' + api)
        assert_publishable(live_auth, **expected, panel_assets=True)
        current = wait()
        save('result.json', {'ok': True, 'origin': origin, 'start_url': origin + '/panel/',
             'revision': current['properties']['latestReadyRevisionName'], 'assets_verified': hashes,
             'anonymous_panel_api_blocked': True, 'interactive_login': 'pending-user-acceptance'})
        print('PWA_PUBLISHED_AND_ANONYMOUS_API_BLOCKED ' + origin + '/panel/', flush=True)
    except Exception as error:
        if changed:
            print('RESTORING_PREVIOUS_GATEWAY', flush=True)
            patch({'properties': auth['properties']}, auth_config=True)
            restore = copy.deepcopy(app['properties']['template'])
            restore['revisionSuffix'] = 'pwa-rollback-' + uuid.uuid4().hex[:8]
            patch({'properties': {'template': restore}})
            wait()
        save('failure.json', {'ok': False, 'error_type': type(error).__name__, 'rollback_attempted': changed})
        raise


if __name__ == '__main__':
    main()
