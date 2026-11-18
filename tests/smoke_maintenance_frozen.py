"""Real packaged HTTPS process through maintenance; no Windows task/CA/registry changes."""
import argparse
from contextlib import closing
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import auth
import installer_core
import maintenance
import monitor
import tls_setup


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--previous-bundle', type=Path)
    args = parser.parse_args()
    bundle = args.bundle.resolve()
    initial = args.previous_bundle.resolve() if args.previous_bundle else bundle
    result = {'real_packaged_process': True, 'windows_resources_unchanged': True}
    process = None
    # Keep the fixture in the normal temp root; nesting the entire customer runtime
    # and backups under a long CI checkout/release path exceeds legacy Win32 limits.
    with tempfile.TemporaryDirectory(prefix='ce-maint-') as temporary:
        fixture = Path(temporary)
        root = fixture / 'Customer CenterEK'
        root.mkdir()
        shutil.copy2(initial / 'CenterEK-Setup.exe', root / 'CenterEK.exe')
        shutil.copytree(initial / '_internal', root / '_internal')
        shutil.copytree(initial / '_internal/web', root / 'web')
        for name in installer_core.SCRIPTS:
            if (initial / '_internal' / name).exists():
                shutil.copy2(initial / '_internal' / name, root / name)
        (root / 'data').mkdir()
        with socket.socket() as reservation:
            reservation.bind(('127.0.0.1', 0))
            port = reservation.getsockname()[1]
        config = {'interval': 5, 'threshold': 3, 'timeout': 1, 'discovery': {'enabled': False},
                  'devices': [{'id': 'self', 'name': 'Maintenance fixture', 'host': '127.0.0.1', 'kind': 'Sunucu', 'method': 'tcp', 'port': port}]}
        (root / 'config.local.json').write_text(json.dumps(config), encoding='utf-8')
        store = monitor.Store(root / 'data/monitor.sqlite3')
        try:
            auth.Auth(store).add_user('customer-admin', secrets.token_urlsafe(24), 'admin')
        finally:
            store.db.close()
        tls_setup.create(root / 'certs/panel', 'localhost', ['127.0.0.1'])
        (root / 'server.local.json').write_text(json.dumps({'bind': '127.0.0.1', 'port': port,
            'tls_cert': 'certs/panel/panel-cert.pem', 'tls_key': 'certs/panel/panel-key.pem'}), encoding='utf-8')
        # CI defaults to the current runtime with an older fixture manifest.
        # --previous-bundle additionally verifies real prior-version executables.
        (root / 'installation.local.json').write_text(json.dumps({'product': 'CenterEK', 'version': '0.7.0-preview', 'status': 'ready'}), encoding='utf-8')
        def controller(target, action, state):
            nonlocal process
            if action in ('Stop', 'Remove'):
                if process is not None and process.poll() is None:
                    process.terminate()
                    process.wait(timeout=15)
                if action == 'Stop':
                    state.write_text('[]')
            elif action == 'Resume':
                process = subprocess.Popen([str(root / 'CenterEK.exe'), '--serve', '--root', str(root)],
                                           cwd=root, creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            with patch.dict(os.environ, {'ProgramData': str(fixture / 'ProgramData')}), patch.object(installer_core, 'register_product'), patch.object(installer_core, 'unregister_product'):
                controller(root, 'Resume', None)
                installer_core.check_ready(root)
                maintenance.upgrade(root, bundle / 'CenterEK-Setup.exe', bundle / '_internal', controller=controller)
                result['upgrade_https'] = True
                maintenance.rollback(root, controller=controller)
                result['rollback_https'] = True
                maintenance.uninstall(root, controller=controller)
                result['uninstall_stopped'] = process.poll() is not None and not (root / 'CenterEK.exe').exists()
                with closing(__import__('sqlite3').connect(root / 'data/monitor.sqlite3')) as database:
                    result['database_retained'] = database.execute('PRAGMA quick_check').fetchone() == ('ok',)
                result['settings_retained'] = (root / 'config.local.json').is_file() and (root / 'certs/panel/panel-key.pem').is_file()
                result['ok'] = all(result.values())
                result['previous_release_bundle_provided'] = bool(args.previous_bundle)
        finally:
            if process is not None and process.poll() is None:
                process.terminate()
                process.wait(timeout=15)
    args.report.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, indent=2))
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
