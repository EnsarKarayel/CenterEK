"""Validated, staged access settings. Never opens NAT or modifies a proxy."""
import copy
import datetime
import ipaddress
import json
from pathlib import Path
import re
import socket
import ssl
from urllib.parse import urlsplit
import device_settings


def public_origin(value):
    if not isinstance(value, str) or len(value) > 2048:
        raise ValueError('Invalid public HTTPS address')
    parsed = urlsplit(value)
    if parsed.scheme != 'https' or parsed.username or parsed.password or parsed.path not in ('', '/') or parsed.query or parsed.fragment:
        raise ValueError('Use an HTTPS origin without credentials, path or query')
    hostname = (parsed.hostname or '').encode('idna').decode('ascii').lower()
    if not re.fullmatch(r'(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', hostname):
        raise ValueError('Use a DNS hostname for proxy access')
    try:
        ipaddress.ip_address(hostname)
    except ValueError:
        pass
    else:
        raise ValueError('Use a DNS hostname, not a public IP address')
    port = parsed.port
    if port is not None and not 1 <= port <= 65535:
        raise ValueError('Invalid port')
    return 'https://' + hostname + ((':' + str(port)) if port and port != 443 else '')


def certificate_paths(root, settings):
    root = Path(root).resolve()
    paths = []
    for key in ('tls_cert', 'tls_key'):
        value = settings.get(key)
        if not isinstance(value, str) or not value:
            raise ValueError('HTTPS certificate and key are required')
        path = Path(value)
        if path.is_absolute():
            path = path.resolve()
        else:
            if '..' in path.parts:
                raise ValueError('Certificate paths must stay inside the application certs folder')
            path = (root / path).resolve()
        if not path.is_relative_to(root / 'certs') or not path.is_file():
            raise ValueError('Certificate files must be inside the application certs folder')
        paths.append(path)
    return paths


def validate(root, current, payload):
    if not isinstance(payload, dict):
        raise ValueError('Invalid access settings')
    mode = payload.get('mode')
    if mode not in ('local', 'vpn', 'proxy'):
        raise ValueError('Invalid access mode')
    bind = ipaddress.IPv4Address(payload.get('bind', ''))
    if mode == 'local' and str(bind) != '127.0.0.1':
        raise ValueError('Local mode requires 127.0.0.1')
    private = any(bind in ipaddress.ip_network(net) for net in ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16'))
    if not (private or str(bind) == '127.0.0.1'):
        raise ValueError('Choose loopback or a specific private interface; direct Internet binding is not supported')
    if mode == 'vpn' and bind.is_loopback:
        raise ValueError('VPN/LAN mode requires a private interface address')
    port = payload.get('port')
    if type(port) is not int or not 1024 <= port <= 65535:
        raise ValueError('Port must be 1024–65535')
    result = copy.deepcopy(current)
    result.update(bind=str(bind), port=port, access_mode=mode)
    result.pop('public_origin', None)
    if mode == 'proxy':
        if payload.get('gateway_protection_confirmed') is not True:
            raise ValueError('Confirm MFA, rate limiting and backend isolation at the external gateway')
        result['public_origin'] = public_origin(payload.get('public_origin'))
    cert, key = current.get('tls_cert'), current.get('tls_key')
    if cert or key or mode != 'local':
        cert_path, key_path = certificate_paths(root, current)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(str(cert_path), str(key_path))
        from cryptography import x509
        certificate = x509.load_pem_x509_certificate(cert_path.read_bytes())
        addresses = certificate.extensions.get_extension_for_class(x509.SubjectAlternativeName).value.get_values_for_type(x509.IPAddress)
        if bind not in addresses:
            raise ValueError('The backend certificate does not cover the selected IP; install/provide a matching certificate first')
        if certificate.not_valid_after_utc <= datetime.datetime.now(datetime.timezone.utc):
            raise ValueError('The backend certificate has expired')
    return result


def load(root):
    path = Path(root) / 'server.local.json'
    return json.loads(path.read_text(encoding='utf-8-sig')) if path.exists() else {'bind': '127.0.0.1', 'port': 8765}


def stage(root, payload):
    with device_settings.LOCK:
        candidate = validate(root, load(root), payload)
        pending = Path(root) / 'server.pending.local.json'
        temporary = pending.with_suffix('.tmp')
        temporary.write_text(json.dumps(candidate, indent=2), encoding='utf-8')
        temporary.replace(pending)
        return candidate


def apply_pending(root):
    root = Path(root)
    pending = root / 'server.pending.local.json'
    if not pending.exists():
        return
    try:
        candidate = json.loads(pending.read_text(encoding='utf-8'))
        payload = {'mode': candidate.get('access_mode'), 'bind': candidate.get('bind'), 'port': candidate.get('port'),
                   'public_origin': candidate.get('public_origin'), 'gateway_protection_confirmed': True}
        candidate = validate(root, load(root), payload)
        with socket.socket() as check:
            if hasattr(socket, 'SO_EXCLUSIVEADDRUSE'):
                check.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            check.bind((candidate['bind'], candidate['port']))
        active = root / 'server.local.json'
        if active.exists():
            (root / 'server.backup.local.json').write_bytes(active.read_bytes())
        pending.write_text(json.dumps(candidate, indent=2), encoding='utf-8')
        pending.replace(active)
    except Exception:
        # Keep the current settings usable if the staged configuration cannot start.
        pending.replace(root / 'server.failed.local.json')


def summary(root):
    current = load(root)
    result = {key: current.get(key) for key in ('bind', 'port', 'access_mode', 'public_origin')}
    result['access_mode'] = result['access_mode'] or ('local' if current.get('bind', '127.0.0.1') == '127.0.0.1' else 'vpn')
    result['tls_configured'] = bool(current.get('tls_cert') and current.get('tls_key'))
    result['restart_required'] = (Path(root) / 'server.pending.local.json').exists()
    result['previous_change_failed'] = (Path(root) / 'server.failed.local.json').exists()
    return result
