"""Admin collector provisioning with machine-protected credentials."""
import copy
import json
import os
from pathlib import Path
import secrets
import ssl
import tempfile
import device_settings
import service_secrets
from file_security import restrict


def prepare(config, payload):
    if not isinstance(payload, dict):
        raise ValueError('Geçersiz bağlantı')
    device = next((copy.deepcopy(d) for d in config['devices'] if d['id'] == payload.get('id')), None)
    kind = payload.get('type')
    fields = {'esxi': ('username', 'password'), 'fortigate': ('token',), 'snmp': ('community',)}
    if not device or kind not in fields:
        raise ValueError('Cihaz ve bağlantı türü gerekli')
    port = payload.get('port')
    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError('Geçersiz port')
    credentials = payload.get('credentials')
    if not isinstance(credentials, dict) or any(not isinstance(credentials.get(k), str) or not 1 <= len(credentials[k]) <= 2048 for k in fields[kind]):
        raise ValueError('Kimlik bilgileri gerekli')
    settings = {'type': kind, 'port': port, '_credentials': {k: credentials[k] for k in fields[kind]}}
    ca = payload.get('ca_file', '')
    if not isinstance(ca, str) or len(ca) > 1024:
        raise ValueError('Geçersiz CA yolu')
    if ca and kind != 'snmp':
        ssl.create_default_context(cafile=ca)
        settings['ca_file'] = ca
    device['collector'] = settings
    return device


def save(config, payload, config_path, secure_path, validate):
    with device_settings.LOCK:
        device = prepare(config, payload)
        settings = device['collector']
        raw = settings.pop('_credentials')
        secure_path = Path(secure_path)
        secure_path.parent.mkdir(parents=True, exist_ok=True)
        restrict(secure_path.parent, directory=True)
        stored = json.loads(secure_path.read_text(encoding='utf-8-sig')) if secure_path.exists() else {'schema': 1, 'environment': {}}
        if stored.get('schema') != 1 or not isinstance(stored.get('environment'), dict):
            raise ValueError('Geçersiz kimlik deposu')
        values = {}
        for key, value in raw.items():
            variable = 'CENTEREK_UI_' + secrets.token_hex(12).upper()
            settings[key + '_env'] = variable
            stored['environment'][variable] = service_secrets.protect(value)
            values[variable] = value
        handle, temporary = tempfile.mkstemp(dir=secure_path.parent, suffix='.local.json')
        try:
            with os.fdopen(handle, 'w', encoding='utf-8') as stream:
                json.dump(stored, stream)
            restrict(temporary)
            os.replace(temporary, secure_path)
        finally:
            Path(temporary).unlink(missing_ok=True)
        new = copy.deepcopy(config)
        new['devices'] = [device if d['id'] == device['id'] else d for d in new['devices']]
        validate(new)
        # Persist before publishing runtime settings. Old environment names remain valid.
        device_settings.save(new, device, config_path, validate)
        os.environ.update(values)
        config['devices'] = new['devices']
