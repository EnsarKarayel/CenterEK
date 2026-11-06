"""Reject site-local data, unsafe paths and unexpected installer payloads."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import sys
import zipfile


def check(folder):
    folder = Path(folder)
    manifest = json.loads((folder / 'release-manifest.json').read_text(encoding='utf-8-sig'))
    name = manifest['archive']
    if Path(name).name != name or not name.endswith('.zip'):
        raise ValueError('Invalid archive name')
    archive = folder / name
    if hashlib.sha256(archive.read_bytes()).hexdigest() != manifest['sha256']:
        raise ValueError('Archive digest mismatch')
    with zipfile.ZipFile(archive) as package:
        files = package.namelist()
        for name in files:
            path = PurePosixPath(name.replace('\\', '/'))
            lower = path.as_posix().lower()
            if path.is_absolute() or '..' in path.parts or ':' in lower or path.parts[0] != 'CenterEK-Setup':
                raise ValueError('Unsafe archive path')
            if ('.local.' in lower or lower.endswith(('.sqlite3', '.sqlite3-wal', '.sqlite3-shm', '.pfx', '.p12'))
                    or any(part in ('data', 'certs', '.git', '.github') for part in path.parts)
                    or Path(lower).name in ('panel-key.pem', 'login.local.txt')):
                raise ValueError('Site-local data must never enter the release: ' + name)
        if 'CenterEK-Setup/CenterEK-Setup.exe' not in files:
            raise ValueError('Installer missing')
    print('Archive SHA-256, paths and site-data exclusion passed:', len(files), 'entries')


if __name__ == '__main__':
    check(sys.argv[1])
