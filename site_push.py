"""Push existing office measurements over verified HTTPS; never send device credentials."""
import argparse
import json
from pathlib import Path
import ssl
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, ProxyHandler, HTTPSHandler, HTTPRedirectHandler, build_opener
import site_relay
import service_secrets


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def prepare(root, settings):
    parsed = urlsplit(settings.get('url', ''))
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.path not in ('', '/') or parsed.query or parsed.fragment:
        raise ValueError('Use an exact HTTPS server origin')
    if settings.get('kind') != 'site':
        raise ValueError('Office relay enrollment required')
    snapshot = site_relay.snapshot(root, settings['computer'])
    if not settings.get('directory_domain'):
        snapshot.pop('directory', None)
    snapshot = site_relay.validate(snapshot, settings, settings['networks'],
        directory_domain=settings.get('directory_domain'), directory_server=settings.get('directory_server'))
    # Validation returns cloud presentation rows. Transport keeps source IDs and
    # availability under state, so the receiving registry independently validates
    # the same wire schema and applies its own namespace exactly once.
    source_ids = {item['id']: item['source_id'] for item in snapshot['devices']}
    for item in snapshot['devices']:
        item['id'] = item.pop('source_id')
        item['state'] = {key: item.pop(key) for key in ('status', 'checked', 'failures', 'latency')}
    for incident in snapshot['incidents']:
        incident['device'] = source_ids[incident['device']]
        incident['id'] = int(incident['id'].rsplit('-', 1)[1])
    body = json.dumps(snapshot, ensure_ascii=False, allow_nan=False).encode('utf-8')
    if len(body) > site_relay.MAX_BYTES:
        raise ValueError('Office snapshot exceeds the 8 MiB transfer limit')
    return settings['url'].rstrip('/') + '/api/agent/site', body


def send(root, settings):
    url, body = prepare(root, settings)
    # Only the relay credential is decrypted. FortiGate/ESXi credentials are
    # neither read from the secret store nor included in the snapshot.
    token = service_secrets.unprotect(settings['token_machine'])
    context = ssl.create_default_context()
    opener = build_opener(ProxyHandler({}), HTTPSHandler(context=context), NoRedirect())
    request = Request(url, data=body, method='POST', headers={
        'Content-Type': 'application/json; charset=utf-8', 'Authorization': 'Bearer ' + token})
    try:
        with opener.open(request, timeout=30) as response:
            if response.status != 202:
                raise RuntimeError('Unexpected telemetry response')
        return len(body)
    finally:
        token = None
        request.remove_header('Authorization')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--agent-config', type=Path, required=True)
    parser.add_argument('--watch', action='store_true')
    args = parser.parse_args()
    while True:
        try:
            settings = json.loads(args.agent_config.read_text(encoding='utf-8-sig'))
            size = send(args.source_root, settings)
            print(time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'OFFICE_RELAY_ACCEPTED bytes=' + str(size), flush=True)
        except HTTPError as error:
            print(time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'OFFICE_RELAY_HTTP_' + str(error.code), flush=True)
            if not args.watch:
                raise SystemExit(1)
        except Exception:
            # Do not log snapshot content, secrets, account names or raw errors.
            print(time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'OFFICE_RELAY_FAILED', flush=True)
            if not args.watch:
                raise SystemExit(1)
        if not args.watch:
            return
        time.sleep(30)


if __name__ == '__main__':
    main()
