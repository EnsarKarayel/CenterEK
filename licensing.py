"""Offline annual subscriptions. Only publisher public keys ship with the app."""
import base64
import json
from pathlib import Path
import sys
import threading
import time
import uuid


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode('ascii')


def verify(envelope, keys, installation_id, now):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    from cryptography.exceptions import InvalidSignature
    try:
        if set(envelope) != {'key_id', 'payload', 'signature'}:
            raise ValueError()
        payload = envelope['payload']
        if set(payload) != {'schema', 'product', 'license_id', 'installation_id', 'customer', 'issued_at', 'expires_at'}:
            raise ValueError()
        key = Ed25519PublicKey.from_public_bytes(base64.b64decode(keys[envelope['key_id']], validate=True))
        key.verify(base64.b64decode(envelope['signature'], validate=True), canonical(payload))
        if payload['schema'] != 1 or type(payload['schema']) is not int or payload['product'] != 'CenterEK':
            raise ValueError()
        if payload['installation_id'] != installation_id or uuid.UUID(payload['license_id']).hex != payload['license_id']:
            raise ValueError()
        if not isinstance(payload['customer'], str) or not 1 <= len(payload['customer']) <= 200:
            raise ValueError()
        issued, expires = payload['issued_at'], payload['expires_at']
        if type(issued) is not int or type(expires) is not int or not 0 < expires - issued <= 366 * 86400:
            raise ValueError()
        state = 'not_yet_valid' if now < issued else 'expired' if now >= expires else 'active'
        return {'status': state, 'monitoring_allowed': state == 'active', 'expires_at': expires, 'customer': payload['customer']}
    except (ValueError, TypeError, KeyError, InvalidSignature, OverflowError, AttributeError):
        return {'status': 'invalid', 'monitoring_allowed': False}


class Gate:
    def __init__(self, root, policy=None, clock=time.time):
        self.root = Path(root)
        self.clock = clock
        self.lock = threading.RLock()
        if policy is None:
            assets = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))
            path = assets / 'release-policy.json'
            try:
                policy = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {'mode': 'blocked' if getattr(sys, 'frozen', False) else 'preview'}
            except (OSError, ValueError):
                policy = {'mode': 'blocked'}
        self.policy = policy if isinstance(policy, dict) else {'mode': 'blocked'}

    def installation_id(self):
        record = json.loads((self.root / 'installation.local.json').read_text(encoding='utf-8'))
        value = record['installation_id']
        if uuid.UUID(value).hex != value:
            raise ValueError('Invalid installation identity')
        return value

    def status(self):
        with self.lock:
            if self.policy.get('mode') == 'preview':
                return {'status': 'preview', 'monitoring_allowed': True}
            if self.policy.get('mode') != 'commercial':
                return {'status': 'configuration_error', 'monitoring_allowed': False}
            path = self.root / 'data/license.local.json'
            if not path.exists():
                return {'status': 'missing', 'monitoring_allowed': False}
            try:
                if path.stat().st_size > 16384:
                    raise ValueError()
                return verify(json.loads(path.read_text(encoding='utf-8')), self.policy['public_keys'], self.installation_id(), self.clock())
            except (OSError, ValueError, KeyError, TypeError):
                return {'status': 'invalid', 'monitoring_allowed': False}

    def allowed(self):
        return self.status()['monitoring_allowed']

    def activate(self, envelope):
        with self.lock:
            result = verify(envelope, self.policy.get('public_keys', {}), self.installation_id(), self.clock())
            if result['status'] != 'active':
                raise ValueError('License is invalid, expired, not yet valid, or belongs to another installation')
            from file_security import restrict
            folder = self.root / 'data'
            temporary = folder / ('license-' + uuid.uuid4().hex + '.local.tmp')
            try:
                temporary.touch(exist_ok=False)
                restrict(temporary)
                temporary.write_bytes(canonical(envelope))
                temporary.replace(folder / 'license.local.json')
            finally:
                temporary.unlink(missing_ok=True)
            return result


def allowed(store):
    gate = getattr(store, 'license_gate', None)
    return gate is None or gate.allowed()
