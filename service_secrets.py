"""Windows machine-scoped DPAPI secrets for unattended background tasks."""
import base64
import ctypes
from ctypes import wintypes
import getpass
import json
import os
from pathlib import Path
import tempfile
from file_security import restrict


class Blob(ctypes.Structure):
    _fields_ = [('size', wintypes.DWORD), ('data', ctypes.POINTER(ctypes.c_ubyte))]


def transform(raw, decrypt=False):
    if os.name != 'nt':
        raise OSError('Windows DPAPI gerekli')
    crypt = ctypes.WinDLL('crypt32', use_last_error=True)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    operation = crypt.CryptUnprotectData if decrypt else crypt.CryptProtectData
    operation.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
                          ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
    operation.restype = wintypes.BOOL
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    memory = ctypes.create_string_buffer(raw)
    source = Blob(len(raw), ctypes.cast(memory, ctypes.POINTER(ctypes.c_ubyte)))
    result = Blob()
    # CRYPTPROTECT_UI_FORBIDDEN | CRYPTPROTECT_LOCAL_MACHINE on encryption.
    flags = 1 if decrypt else 5
    if not operation(ctypes.byref(source), None, None, None, None, flags, ctypes.byref(result)):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        return ctypes.string_at(result.data, result.size)
    finally:
        kernel.LocalFree(ctypes.cast(result.data, ctypes.c_void_p))
        ctypes.memset(memory, 0, len(memory))


def protect(value):
    return base64.b64encode(transform(value.encode('utf-8'))).decode('ascii')


def unprotect(value):
    return transform(base64.b64decode(value, validate=True), True).decode('utf-8')


def load(path):
    payload = json.loads(Path(path).read_text(encoding='utf-8-sig'))
    if payload.get('schema') != 1 or not isinstance(payload.get('environment'), dict):
        raise ValueError('Geçersiz arka plan kimlik dosyası')
    return {name: unprotect(value) for name, value in payload['environment'].items()}


def configure():
    import monitor
    config = monitor.validate(json.loads((monitor.ROOT / 'config.local.json').read_text(encoding='utf-8-sig')))
    output = monitor.ROOT / 'data' / 'secure' / 'service-secrets.local.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    restrict(output.parent, directory=True)
    values = {}
    for device in config['devices']:
        for key, variable in device.get('collector', {}).items():
            if key.endswith('_env') and variable not in values:
                prompt = device['name'] + ' (' + key[:-4] + '): '
                value = input(prompt) if key == 'username_env' else getpass.getpass(prompt)
                if not value:
                    raise ValueError('Boş kimlik bilgisi kaydedilmez')
                values[variable] = protect(value)
    temporary = output.with_suffix('.tmp')
    try:
        with temporary.open('w', encoding='utf-8') as destination:
            json.dump({'schema': 1, 'environment': values}, destination, indent=2)
        restrict(temporary)
        os.replace(temporary, output)
    finally:
        temporary.unlink(missing_ok=True)
    print('Arka plan kimlik bilgileri bu makineye bağlı DPAPI ile kaydedildi.')


if __name__ == '__main__':
    configure()
