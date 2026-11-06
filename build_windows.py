"""Build a self-contained, unsigned Windows preview from a strict payload allowlist."""
import datetime
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import installer_core


def main():
    if os.name != 'nt' or platform.machine().lower() not in ('amd64', 'x86_64'):
        raise SystemExit('Build on Windows x64.')
    root = Path(__file__).resolve().parent
    stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    output = root / 'data/releases' / (installer_core.VERSION + '-' + stamp)
    payload = output / 'payload'
    payload.mkdir(parents=True)
    web_files = ('index.html', 'login.html', 'app.js', 'live.js', 'dashboard.js', 'i18n.js', 'style.css', 'theme.css')
    (payload / 'web').mkdir()
    for name in web_files:
        shutil.copy2(root / 'web' / name, payload / 'web' / name)
    for name in installer_core.SCRIPTS:
        (payload / name).write_text((root / name).read_text(encoding='utf-8-sig'), encoding='utf-8-sig')
    shutil.copy2(root / 'INSTALLATION.md', payload / 'INSTALLATION.md')
    distributions = ('pyinstaller', 'pyvmomi', 'pysnmp', 'cryptography', 'cffi', 'pyasn1', 'urllib3')
    dependencies = {}
    for name in distributions:
        try:
            distribution = importlib.metadata.distribution(name)
        except importlib.metadata.PackageNotFoundError:
            continue
        dependencies[name] = distribution.version
        for file in distribution.files or []:
            if 'license' in str(file).lower() and Path(str(file)).suffix.lower() in ('.txt', '.md', ''):
                source = Path(distribution.locate_file(file))
                if source.is_file():
                    destination = payload / 'licenses' / name / source.name
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, destination)
    (payload / 'THIRD-PARTY.txt').write_text('Bundled components (preview inventory; commercial license review remains required):\n' +
                                          '\n'.join(name + ' ' + version for name, version in dependencies.items()), encoding='utf-8')
    command = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--onedir', '--windowed',
               '--noupx', '--name', 'CenterEK-Setup', '--distpath', str(output / 'dist'), '--workpath', str(output / 'build'),
               '--specpath', str(output), '--paths', str(root / '.vendor'), '--add-data', str(payload) + os.pathsep + '.']
    for package in ('pyVmomi', 'pyVim', 'pysnmp', 'pyasn1', 'cryptography', 'cffi'):
        command += ['--collect-all', package]
    command += [str(root / 'setup_app.py')]
    subprocess.run(command, check=True, cwd=root)
    bundle = output / 'dist/CenterEK-Setup'
    shutil.copy2(root / 'INSTALLATION.md', bundle / 'READ-ME.md')
    archive = shutil.make_archive(str(output / ('CenterEK-Setup-' + installer_core.VERSION + '-win-x64')), 'zip',
                                  root_dir=output / 'dist', base_dir='CenterEK-Setup')
    path = Path(archive)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest = {'version': installer_core.VERSION, 'runtime': platform.python_version(), 'architecture': 'x64',
                'signed': False, 'sha256': digest, 'bytes': path.stat().st_size, 'dependencies': dependencies,
                'archive': path.name, 'customer_installation_test': 'pending'}
    (output / 'release-manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    path.with_suffix('.zip.sha256').write_text(digest + '  ' + path.name + '\n', encoding='utf-8')
    print('ARCHIVE=' + str(path), flush=True)
    print('BUNDLE=' + str(bundle), flush=True)


if __name__ == '__main__':
    main()
