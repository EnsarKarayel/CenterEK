"""Explicit in-place source update; preserves all site-local data and settings."""
import datetime
import io
from pathlib import Path
import shutil
import socket
import urllib.request
import zipfile
import argparse
import json

FILES = {
    'device_settings.py',
    'monitor.py', 'auth.py', 'users.py', 'connectors.py', 'directory.py', 'endpoints.py',
    'configure.py', 'discover.py', 'insights.py', 'start.py', 'update.py', 'requirements.txt',
    'README.md', 'PRODUCT.md', 'OPERATIONS.md', 'config.example.json',
    'Export-DirectoryInventory.ps1', 'Collect-EndpointSessions.ps1',
    'web/index.html', 'web/login.html', 'web/app.js', 'web/style.css',
    'agents.py', 'tls_setup.py', 'file_security.py', 'requirements-tls.txt', 'AGENT-SETUP.md',
    'Send-Report.ps1', 'Setup-Agent.ps1', 'Send-DirectoryInventory.ps1', 'Install-AgentTask.ps1',
    'START-AGENT.cmd', 'START-DIRECTORY.cmd',
    'Install-SystemTask.ps1', 'Run-SystemTask.ps1', 'service_secrets.py', 'UNATTENDED.md',
    'web/live.js',
}


def main():
    parser = argparse.ArgumentParser(description='CenterEK kaynak güncellemesi')
    parser.add_argument('--archive', type=Path, help='Önceden indirilen GitHub kaynak ZIP dosyası')
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    if not (root / 'monitor.py').is_file():
        raise SystemExit('Bu dosyayı mevcut CenterEK klasöründe çalıştırın.')
    network_file=root/'server.local.json'
    network=json.loads(network_file.read_text(encoding='utf-8-sig')) if network_file.exists() else {}
    bind=network.get('bind','127.0.0.1')
    if bind=='0.0.0.0':
        bind='127.0.0.1'
    try:
        with socket.create_connection((bind, network.get('port',8765)), timeout=1):
            raise SystemExit('Önce çalışan CenterEK programını Ctrl+C ile durdurun.')
    except OSError:
        pass
    if args.archive:
        print('Yerel güncelleme paketi okunuyor...', flush=True)
        with args.archive.open('rb') as source:
            raw = source.read(20 * 1024 * 1024 + 1)
    else:
        print('GitHub güncellemesi indiriliyor...', flush=True)
        try:
            with urllib.request.urlopen('https://github.com/EnsarKarayel/CenterEK/archive/refs/heads/main.zip', timeout=120) as response:
                raw = response.read(20 * 1024 * 1024 + 1)
        except urllib.error.URLError:
            raise SystemExit('İndirme başarısız. GitHub ZIP dosyasını başka bilgisayarda indirip --archive DOSYA.zip ile kullanın. TLS doğrulaması kapatılmaz.')
    if len(raw) > 20 * 1024 * 1024:
        raise SystemExit('Paket boyutu sınırı aşıldı.')
    archive = zipfile.ZipFile(io.BytesIO(raw))
    entries = {info.filename.partition('/')[2]: info for info in archive.infolist()}
    required = {'auth.py', 'users.py', 'monitor.py', 'agents.py', 'file_security.py',
                'Send-Report.ps1', 'Setup-Agent.ps1', 'web/app.js', 'web/login.html', 'web/style.css'}
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
