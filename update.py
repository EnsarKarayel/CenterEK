"""Explicit in-place source update; preserves all site-local data and settings."""
import datetime
import io
from pathlib import Path
import shutil
import socket
import urllib.request
import zipfile

FILES = {
    'monitor.py', 'auth.py', 'users.py', 'connectors.py', 'directory.py', 'endpoints.py',
    'configure.py', 'discover.py', 'insights.py', 'start.py', 'update.py', 'requirements.txt',
    'README.md', 'PRODUCT.md', 'OPERATIONS.md', 'config.example.json',
    'Export-DirectoryInventory.ps1', 'Collect-EndpointSessions.ps1',
    'web/index.html', 'web/login.html', 'web/app.js', 'web/style.css',
}


def main():
    root = Path(__file__).resolve().parent
    if not (root / 'monitor.py').is_file():
        raise SystemExit('Bu dosyayı mevcut CenterEK klasöründe çalıştırın.')
    try:
        with socket.create_connection(('127.0.0.1', 8765), timeout=1):
            raise SystemExit('Önce çalışan CenterEK programını Ctrl+C ile durdurun.')
    except OSError:
        pass
    print('GitHub güncellemesi indiriliyor...', flush=True)
    with urllib.request.urlopen('https://github.com/EnsarKarayel/CenterEK/archive/refs/heads/main.zip', timeout=120) as response:
        raw = response.read(20 * 1024 * 1024 + 1)
    if len(raw) > 20 * 1024 * 1024:
        raise SystemExit('Paket boyutu sınırı aşıldı.')
    archive = zipfile.ZipFile(io.BytesIO(raw))
    entries = {info.filename.partition('/')[2]: info for info in archive.infolist()}
    required = {'auth.py', 'users.py', 'monitor.py', 'web/app.js', 'web/login.html', 'web/style.css'}
    if not required <= entries.keys():
        raise SystemExit('Beklenen güncelleme dosyaları bulunamadı.')
    for name in FILES & entries.keys():
        if entries[name].file_size > 5 * 1024 * 1024 or (root / name).is_symlink():
            raise SystemExit('Güvenli olmayan dosya veya boyut.')
    backup = root.with_name(root.name + '-backup-' + datetime.datetime.now().strftime('%Y%m%d-%H%M%S'))
    shutil.copytree(root, backup, ignore=shutil.ignore_patterns('.git', '.venv', '.vendor', '__pycache__'))
    print('Yedek oluşturuldu:', backup, flush=True)
    for name in sorted(FILES & entries.keys()):
        destination = root / name
        if destination.parent.is_symlink():
            raise SystemExit('Sembolik bağlantı hedefi güncellenmez.')
        destination.parent.mkdir(exist_ok=True, parents=True)
        destination.write_bytes(archive.read(entries[name]))
    print('Kaynaklar güncellendi. config.local.json, certs ve data korundu.')
    print('İlk panel kullanıcısı için: python users.py add --role admin')
    print('Ardından: python start.py')


if __name__ == '__main__':
    main()
