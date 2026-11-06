"""Check live gateway identity policy, then optionally publish and probe HTTPS.

Does not create identities, change passwords or broaden an allowlist. Run only
after the separately approved gateway deployment and private backend readiness.
"""
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
import time
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from browser_access import assert_publishable


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, newurl):
        return None


def probe_anonymous(origin, settle_seconds=0):
    opener = build_opener(NoRedirect)
    for path in ('/', '/api/status', '/api/inventory', '/api/accounts'):
        # A caller-provided identity header must never bypass platform auth.
        request = Request(origin + path, headers={'X-MS-CLIENT-PRINCIPAL-ID': 'untrusted-client'})
        deadline = time.monotonic() + settle_seconds
        while True:
            try:
                with opener.open(request, timeout=30) as response:
                    code, headers = response.status, response.headers
            except HTTPError as error:
                code, headers = error.code, error.headers
            # ARM success precedes ingress propagation. Never accept a 404/5xx
            # as protection, and never retry an unexpected successful response.
            if code not in (404, 502, 503) or time.monotonic() >= deadline:
                break
            time.sleep(3)
        if code in (401, 403):
            continue
        location = urlsplit(headers.get('Location', ''))
        same_host = not location.netloc or location.netloc == urlsplit(origin).netloc
        login_redirect = same_host and location.path == '/.auth/login/aad'
        if code not in (302, 303, 307) or not login_redirect:
            raise RuntimeError(f'Anonymous protection failed for {path}: HTTP {code}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--azure-python', type=Path, help='Python environment containing azure.cli; otherwise use az')
    parser.add_argument('--resource-group', required=True)
    parser.add_argument('--app-name', required=True)
    parser.add_argument('--tenant-id', required=True)
    parser.add_argument('--client-id', required=True)
    parser.add_argument('--principal-id', action='append', required=True)
    parser.add_argument('--publish', action='store_true', help='Enable external ingress only after policy validation')
    args = parser.parse_args()
    for value in (args.resource_group, args.app_name):
        if not re.fullmatch(r'[A-Za-z0-9_.-]{1,90}', value):
            parser.error('Invalid Azure resource name')
    command = [str(args.azure_python), '-m', 'azure.cli'] if args.azure_python else ['az']

    def az(*arguments):
        retries = 3 if '--method' in arguments and arguments[arguments.index('--method') + 1] == 'get' else 1
        for attempt in range(retries):
            result = subprocess.run(command + list(arguments) + ['-o', 'json', '--only-show-errors'], capture_output=True, text=True, encoding='utf-8')
            if not result.returncode:
                return json.loads(result.stdout) if result.stdout.strip() else None
            if attempt + 1 < retries:
                time.sleep(3)
        # Never print an ARM response that might reflect a secret parameter.
        raise RuntimeError('Azure operation failed; inspect the Azure deployment activity log')

    subscription = az('account', 'show')['id']
    if not re.fullmatch(r'[a-fA-F0-9-]{36}', subscription):
        raise ValueError('Invalid subscription ID')
    base = f'https://management.azure.com/subscriptions/{subscription}/resourceGroups/{args.resource_group}/providers/Microsoft.App/containerApps/{args.app_name}'
    api = '?api-version=2025-07-01'

    def wait_ready():
        deadline = time.monotonic() + 150
        while True:
            current = az('rest', '--method', 'get', '--url', base + api)
            state = current['properties'].get('provisioningState')
            if state == 'Succeeded':
                return current
            if state in ('Failed', 'Canceled') or time.monotonic() >= deadline:
                raise RuntimeError('Gateway control-plane update did not become ready')
            time.sleep(3)

    def check_auth():
        auth = az('rest', '--method', 'get', '--url', base + '/authConfigs/current' + api)
        assert_publishable(auth, tenant_id=args.tenant_id, client_id=args.client_id, principal_ids=args.principal_id)

    check_auth()
    app = az('rest', '--method', 'get', '--url', base + api)
    properties = app['properties']
    if properties.get('provisioningState') != 'Succeeded' or not properties.get('latestReadyRevisionName') or properties.get('latestReadyRevisionName') != properties.get('latestRevisionName'):
        raise RuntimeError('Gateway revision is not ready; external ingress unchanged')
    ingress = properties['configuration']['ingress']
    if ingress.get('allowInsecure') is not False or ingress.get('targetPort') != 8080:
        raise RuntimeError('Unexpected HTTPS gateway port/policy')
    print('LIVE_AUTH_SCOPE_VERIFIED')
    if not args.publish:
        print('External ingress unchanged. Use --publish only after backend readiness.')
        return

    def set_external(enabled):
        candidate = {**ingress, 'external': enabled}
        candidate.pop('fqdn', None)
        az('rest', '--method', 'patch', '--url', base + api,
           '--body', json.dumps({'properties': {'configuration': {'ingress': candidate}}}))
        current = wait_ready()
        if current['properties']['configuration']['ingress']['external'] is not enabled:
            raise RuntimeError('Gateway ingress did not reach the requested state')

    try:
        set_external(True)
        check_auth()
        current = az('rest', '--method', 'get', '--url', base + api)
        host = current['properties']['configuration']['ingress']['fqdn']
        if not re.fullmatch(r'[a-z0-9.-]+\.azurecontainerapps\.io', host):
            raise RuntimeError('Unexpected Azure-managed hostname')
        origin = 'https://' + host
        probe_anonymous(origin, settle_seconds=120)
        print('ANONYMOUS_REQUESTS_BLOCKED')
        print(origin)
        print('Approved interactive Microsoft and CenterEK sign-in still require user acceptance.')
    except Exception:
        wait_ready()
        set_external(False)
        print('External ingress disabled after failed verification.', file=sys.stderr)
        raise


if __name__ == '__main__':
    main()
