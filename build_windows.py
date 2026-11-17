"""Build a self-contained, unsigned Windows preview from a strict payload allowlist."""
import datetime
import argparse
import base64
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
    parser = argparse.ArgumentParser()
    parser.add_argument('--license-policy', type=Path)
    parser.add_argument('--sign-thumbprint')
    parser.add_argument('--signtool', type=Path)
    parser.add_argument('--timestamp-url')
    parser.add_argument('--eula-file', type=Path)
    parser.add_argument('--qa-only', action='store_true')
    args = parser.parse_args()
    if args.qa_only and '-preview' not in installer_core.VERSION:
        parser.error('QA-only bundles must use a preview version')
    if args.sign_thumbprint and (not args.signtool or not args.timestamp_url):
        parser.error('--signtool and --timestamp-url required with --sign-thumbprint')
    if os.name != 'nt' or platform.machine().lower() not in ('amd64', 'x86_64'):
        raise SystemExit('Build on Windows x64.')
    root = Path(__file__).resolve().parent
    stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    output = root / 'data/releases' / (installer_core.VERSION + '-' + stamp)
    payload = output / 'payload'
    payload.mkdir(parents=True)
    publisher = json.loads((root / 'legal/publisher.json').read_text(encoding='utf-8'))
    public_profile = {key: publisher[key] for key in ('seller', 'country', 'country_name', 'support_email')}
    (payload / 'publisher.json').write_text(json.dumps(public_profile, ensure_ascii=False), encoding='utf-8')
    policy = {'mode': 'preview', 'public_keys': {}}
    if args.license_policy:
        policy = json.loads(args.license_policy.read_text(encoding='utf-8-sig'))
        if set(policy) != {'mode', 'public_keys'} or policy['mode'] != 'commercial' or not policy['public_keys']:
            raise ValueError('Commercial policy requires public license verification keys only')
        for name, value in policy['public_keys'].items():
            if not isinstance(name, str) or len(base64.b64decode(value, validate=True)) != 32:
                raise ValueError('Invalid Ed25519 public key')
        if not args.eula_file or not args.eula_file.is_file():
            raise ValueError('Commercial build requires the final publisher-approved EULA file')
        text = args.eula_file.read_text(encoding='utf-8')
        if len(text) < 200 or any(marker in text.upper() for marker in ('[SATICI', '[DESTEK', 'TASLAK', 'DRAFT', 'PLACEHOLDER')):
            raise ValueError('Draft/unfilled EULA cannot enter a commercial package')
        shutil.copy2(args.eula_file, payload / 'EULA.txt')
    (payload / 'release-policy.json').write_text(json.dumps(policy), encoding='utf-8')
    web_files = ('index.html', 'login.html', 'app.js', 'live.js', 'dashboard.js', 'i18n.js', 'style.css', 'theme.css')
    (payload / 'web').mkdir()
    for name in web_files:
        shutil.copy2(root / 'web' / name, payload / 'web' / name)
    for name in installer_core.SCRIPTS:
        (payload / name).write_text((root / name).read_text(encoding='utf-8-sig'), encoding='utf-8-sig')
    shutil.copy2(root / 'INSTALLATION.md', payload / 'INSTALLATION.md')
    shutil.copy2(root / 'REMOTE-ACCESS.md', payload / 'REMOTE-ACCESS.md')
    shutil.copy2(root / 'MAINTENANCE.md', payload / 'MAINTENANCE.md')
    from packaging.requirements import Requirement
    distributions = ['pyinstaller', 'pyvmomi', 'pysnmp', 'cryptography', 'cffi', 'pyasn1', 'urllib3']
    dependencies = {}
    for name in distributions:
        if name in dependencies:
            continue
        try:
            distribution = importlib.metadata.distribution(name)
        except importlib.metadata.PackageNotFoundError:
            continue
        dependencies[name] = distribution.version
        for dependency in distribution.requires or []:
            requirement = Requirement(dependency)
            if not requirement.marker or requirement.marker.evaluate({'extra': ''}):
                if requirement.name not in distributions:
                    distributions.append(requirement.name)
        for file in distribution.files or []:
            if 'license' in str(file).lower() and Path(str(file)).suffix.lower() in ('.txt', '.md', ''):
                source = Path(distribution.locate_file(file))
                if source.is_file():
                    destination = payload / 'licenses' / name / source.name
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, destination)
    for name, source in [('Python', Path(sys.base_prefix) / 'LICENSE.txt'),
                         ('Tcl', Path(sys.base_prefix) / 'tcl/tcl8.6/license.terms'),
                         ('Tk', Path(sys.base_prefix) / 'tcl/tk8.6/license.terms')]:
        if source.is_file():
            target = payload / 'licenses' / name / source.name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            dependencies[name] = platform.python_version() if name == 'Python' else 'bundled runtime'
    (payload / 'THIRD-PARTY.txt').write_text('Runtime/build dependency inventory (commercial license review remains required; build tools may not be installed with the customer runtime):\n' +
                                          '\n'.join(name + ' ' + version for name, version in dependencies.items()), encoding='utf-8')
    command = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--onedir', '--windowed',
               '--noupx', '--name', 'CenterEK-Setup', '--distpath', str(output / 'dist'), '--workpath', str(output / 'build'),
               '--specpath', str(output), '--paths', str(root / '.vendor'), '--add-data', str(payload) + os.pathsep + '.']
    for package in ('pyVmomi', 'pyVim', 'pysnmp', 'pyasn1', 'cryptography', 'cffi'):
        command += ['--collect-all', package]
    command += [str(root / 'setup_app.py')]
    subprocess.run(command, check=True, cwd=root)
    bundle = output / 'dist/CenterEK-Setup'
    signatures = {}
    if args.sign_thumbprint:
        import release_signing
        for target in [bundle / 'CenterEK-Setup.exe', *(bundle / '_internal' / name for name in installer_core.SCRIPTS)]:
            signatures[target.relative_to(bundle).as_posix()] = release_signing.sign(target, args.sign_thumbprint, args.timestamp_url, args.signtool)
    shutil.copy2(root / 'INSTALLATION.md', bundle / 'READ-ME.md')
    archive = shutil.make_archive(str(output / ('CenterEK-Setup-' + installer_core.VERSION + '-win-x64')), 'zip',
                                  root_dir=output / 'dist', base_dir='CenterEK-Setup')
    path = Path(archive)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    bootstrap_payload = output / 'bootstrap-payload'
    bootstrap_payload.mkdir()
    shutil.copy2(path, bootstrap_payload / 'installer-payload.zip')
    setup_name = 'CenterEK-Setup-' + installer_core.VERSION + '-win-x64'
    subprocess.run([sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--onefile',
                    '--windowed', '--uac-admin', '--noupx', '--name', setup_name,
                    '--distpath', str(output), '--workpath', str(output / 'bootstrap-build'),
                    '--specpath', str(output), '--add-data', str(bootstrap_payload) + os.pathsep + '.',
                    str(root / 'setup_bootstrap.py')], check=True, cwd=root)
    setup = output / (setup_name + '.exe')
    if args.sign_thumbprint:
        signatures['setup'] = release_signing.sign(setup, args.sign_thumbprint, args.timestamp_url, args.signtool)
    setup_digest = hashlib.sha256(setup.read_bytes()).hexdigest()
    setup.with_suffix('.exe.sha256').write_text(setup_digest + '  ' + setup.name + '\n', encoding='utf-8')
    manifest = {'version': installer_core.VERSION, 'runtime': platform.python_version(), 'architecture': 'x64',
                'signed': bool(signatures), 'signatures': signatures, 'license_mode': policy['mode'], 'qa_only': args.qa_only,
                'eula_sha256': hashlib.sha256((payload / 'EULA.txt').read_bytes()).hexdigest() if (payload / 'EULA.txt').exists() else None,
                'third_party_sha256': hashlib.sha256((payload / 'THIRD-PARTY.txt').read_bytes()).hexdigest(),
                'sha256': digest, 'bytes': path.stat().st_size, 'dependencies': dependencies,
                'archive': path.name, 'setup': setup.name, 'setup_sha256': setup_digest,
                'setup_bytes': setup.stat().st_size, 'customer_installation_test': 'pending'}
    (output / 'release-manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    path.with_suffix('.zip.sha256').write_text(digest + '  ' + path.name + '\n', encoding='utf-8')
    print('ARCHIVE=' + str(path), flush=True)
    print('BUNDLE=' + str(bundle), flush=True)
    print('SETUP=' + str(setup), flush=True)


if __name__ == '__main__':
    main()
