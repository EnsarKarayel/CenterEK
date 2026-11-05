"""Restrict generated secrets to the creating user, SYSTEM and local admins."""
import os
from pathlib import Path
import re
import subprocess


def restrict(path, directory=False):
    path = Path(path)
    if os.name != 'nt':
        path.chmod(0o700 if directory else 0o600)
        return
    identity = subprocess.check_output(['whoami.exe', '/user', '/fo', 'csv', '/nh'], timeout=10)
    match = re.search(rb'S-1-\d+(?:-\d+)+', identity)
    if not match:
        raise PermissionError('Mevcut Windows kullanıcı SID değeri okunamadı')
    rights = '(OI)(CI)(F)' if directory else '(F)'
    principals = [match[0].decode('ascii'), 'S-1-5-18', 'S-1-5-32-544']
    result = subprocess.run(['icacls.exe', str(path.resolve()), '/inheritance:r', '/grant:r'] +
                            ['*' + sid + ':' + rights for sid in principals], capture_output=True, timeout=15)
    if result.returncode:
        raise PermissionError('Gizli dosya izinleri uygulanamadı')
