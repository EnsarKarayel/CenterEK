"""Publisher workstation tool. Never bundle private signing keys with a customer app."""
import argparse
import base64
import getpass
import json
from pathlib import Path
import time
import uuid

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from file_security import restrict
from licensing import canonical


def issue(key, key_id, customer, installation_id, days=365, now=None):
    now = int(time.time()) if now is None else now
    if type(days) is not int or not 1 <= days <= 366 or uuid.UUID(installation_id).hex != installation_id:
        raise ValueError('Valid installation identity and 1–366 days required')
    if not isinstance(customer, str) or not 1 <= len(customer) <= 200:
        raise ValueError('Customer name required')
    payload = {'schema': 1, 'product': 'CenterEK', 'license_id': uuid.uuid4().hex,
               'installation_id': installation_id, 'customer': customer, 'issued_at': now,
               'expires_at': now + days * 86400}
    return {'key_id': key_id, 'payload': payload, 'signature': base64.b64encode(key.sign(canonical(payload))).decode('ascii')}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['generate-key', 'issue'])
    parser.add_argument('--private-key', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--key-id', required=True)
    parser.add_argument('--request', type=Path)
    args = parser.parse_args()
    if args.output.exists() or (args.action == 'generate-key' and args.private_key.exists()):
        parser.error('Refusing to overwrite existing key/output')
    password = getpass.getpass('Private signing key password (12+ characters): ')
    if len(password) < 12:
        parser.error('A password of at least 12 characters is required')
    if args.action == 'generate-key':
        if password != getpass.getpass('Repeat password: '):
            parser.error('Passwords do not match')
        key = Ed25519PrivateKey.generate()
        parent = args.private_key.parent.resolve()
        if not args.private_key.is_absolute() or parent == Path(parent.anchor) or (parent.exists() and any(parent.iterdir())):
            parser.error('Use a new, dedicated absolute key folder (for example data/secure/license-signing)')
        args.private_key.parent.mkdir(parents=True, exist_ok=True)
        restrict(args.private_key.parent, directory=True)
        args.private_key.touch(exist_ok=False)
        restrict(args.private_key)
        args.private_key.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                                      serialization.BestAvailableEncryption(password.encode())))
        result = {'key_id': args.key_id, 'public_key': base64.b64encode(key.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw)).decode('ascii')}
    else:
        if not args.request:
            parser.error('--request is required')
        key = serialization.load_pem_private_key(args.private_key.read_bytes(), password=password.encode())
        if not isinstance(key, Ed25519PrivateKey):
            parser.error('Ed25519 private key required')
        request = json.loads(args.request.read_text(encoding='utf-8-sig'))
        result = issue(key, args.key_id, **request)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.touch(exist_ok=False)
    restrict(args.output)
    args.output.write_bytes(canonical(result))
    print('Created: ' + str(args.output))


if __name__ == '__main__':
    main()
