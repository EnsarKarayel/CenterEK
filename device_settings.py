"""Atomic availability-device edits; collector secrets are never accepted here."""
import copy
import json
import os
import tempfile
from pathlib import Path
import threading

LOCK = threading.RLock()


def candidate(config, payload, validate):
    if not isinstance(payload, dict):
        raise ValueError('Geçersiz cihaz')
    device = {key: payload.get(key) for key in ('id', 'name', 'host', 'kind', 'method')}
    if any(not isinstance(value, str) for value in device.values()):
        raise ValueError('Geçersiz cihaz alanı')
    if not 1 <= len(device['name']) <= 128 or device['kind'] not in ('Sunucu', 'Linux', 'ESXi', 'Switch', 'Firewall', 'Access point', 'Bilgisayar', 'Diğer'):
        raise ValueError('Geçersiz ad veya tür')
    if device['method'] == 'tcp':
        device['port'] = payload.get('port')
    new = copy.deepcopy(config)
    previous = next((d for d in new['devices'] if d['id'] == device['id']), None)
    if previous:
        # Changing the host of a credentialled source needs a separate workflow.
        if previous.get('collector') and previous['host'] != device['host']:
            raise ValueError('Ölçüm kaynağı adresi bu ekrandan değiştirilemez')
        previous.update(device)
        if device['method'] == 'icmp':
            previous.pop('port', None)
    else:
        new['devices'].append(device)
    validate(new)
    return new, device


def save(config, payload, path, validate):
    path = Path(path)
    with LOCK:
        new, device = candidate(config, payload, validate)
        if path.exists():
            backup = path.with_name('config.backup.local.json')
            backup.write_bytes(path.read_bytes())
        handle, temporary = tempfile.mkstemp(prefix='.device-', suffix='.local.json', dir=path.parent)
        try:
            with os.fdopen(handle, 'w', encoding='utf-8') as stream:
                json.dump(new, stream, ensure_ascii=False, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            Path(temporary).unlink(missing_ok=True)
        config['devices'] = new['devices']
        return device
