"""Create an OS-admin-authorized site enrollment, encrypted to the installer."""
import base64
import json
from pathlib import Path
import secrets
from urllib.parse import urlsplit
import agents
from file_security import restrict

CONTEXT = b'CenterEK site enrollment v1'


def create(root, options_file, report_file):
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding, rsa
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    import monitor
    root, options_file, report_file = Path(root).resolve(), Path(options_file), Path(report_file)
    if not (root / 'installation.local.json').is_file() or options_file.stat().st_size > 16384 or report_file.exists():
        raise ValueError('Existing installation, bounded options and fresh output are required')
    options = json.loads(options_file.read_text(encoding='utf-8-sig'))
    public = serialization.load_pem_public_key(options['public_key'].encode('ascii'))
    if not isinstance(public, rsa.RSAPublicKey) or not 3072 <= public.key_size <= 4096:
        raise ValueError('A 3072–4096 bit RSA recipient key is required')
    parsed = urlsplit(options['url'])
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.path not in ('', '/') or parsed.query or parsed.fragment:
        raise ValueError('Exact HTTPS telemetry origin required')
    store = monitor.Store(root / 'data/monitor.sqlite3')
    registry = agents.Registry(store, root)
    record = None
    try:
        record = registry.register(options['computer'], 'site', networks=options['networks'],
            directory_domain=options.get('directory_domain'), directory_server=options.get('directory_server'))
        record.update({key: options.get(key) for key in ('url', 'networks', 'directory_domain', 'directory_server')})
        key, nonce = secrets.token_bytes(32), secrets.token_bytes(12)
        ciphertext = AESGCM(key).encrypt(nonce, json.dumps(record).encode('utf-8'), CONTEXT)
        wrapped = public.encrypt(key, padding.OAEP(mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=CONTEXT))
        result = {'schema': 1, 'id': record['id'], 'computer': record['computer'],
            'wrapped_key': base64.b64encode(wrapped).decode('ascii'), 'nonce': base64.b64encode(nonce).decode('ascii'),
            'ciphertext': base64.b64encode(ciphertext).decode('ascii')}
        report_file.parent.mkdir(parents=True, exist_ok=True)
        with report_file.open('x', encoding='utf-8') as output:
            json.dump(result, output)
        restrict(report_file)
    except Exception:
        if record:
            registry.revoke(record['id'])
        raise
    finally:
        store.db.close()
