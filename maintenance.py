"""Offline, backed-up maintenance for packaged CenterEK installations."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import sys
import uuid
from functools import wraps

import installer_core
from file_security import restrict
from monitor import MonitorInstance


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def check_tree(root):
    for path in (root, *root.parents):
        if path.exists() and (path.is_symlink() or getattr(path.stat(), 'st_file_attributes', 0) & 0x400):
            raise ValueError('Junction/symlink paths are not supported')
    for path in root.rglob('*'):
        if path.is_symlink() or getattr(path.stat(), 'st_file_attributes', 0) & 0x400:
            raise ValueError('Installation contains a junction/symlink')


def validate_root(root, allow_uninstalled=False):
    root = Path(root)
    if not root.is_absolute() or root == Path(root.anchor) or '"' in str(root):
        raise ValueError('Select a dedicated CenterEK installation folder')
    check_tree(root)
    record = read_json(root / 'installation.local.json')
    expected = ('ready', 'uninstalled') if allow_uninstalled else ('ready',)
    if record.get('product') != 'CenterEK' or record.get('status') not in expected:
        raise ValueError('A completed packaged CenterEK installation is required')
    if (record['status'] == 'ready' and not (root / 'CenterEK.exe').is_file()) or not (root / 'data/monitor.sqlite3').is_file():
        raise ValueError('Installation is incomplete')
    if Path(sys.executable).resolve().is_relative_to(root.resolve()):
        raise ValueError('Start maintenance from the new setup or the maintenance launcher')
    return root.resolve(), record


def backup_base(root):
    identity = hashlib.sha256(str(Path(root).resolve()).casefold().encode()).hexdigest()[:24]
    return Path(os.environ.get('ProgramData', str(root.parent))) / 'CenterEK-Maintenance' / identity


def digest_tree(root):
    hashes = {}
    for path in sorted(root.rglob('*')):
        if path.is_file():
            with path.open('rb') as stream:
                hashes[path.relative_to(root).as_posix()] = hashlib.file_digest(stream, 'sha256').hexdigest()
    return hashes


def exclusive(operation):
    @wraps(operation)
    def run(root, *args, **kwargs):
        root, _ = validate_root(root, allow_uninstalled=operation.__name__ == 'restore_uninstalled')
        base = backup_base(root)
        check_tree(base)
        base.mkdir(parents=True, exist_ok=True)
        restrict(base, directory=True)
        with MonitorInstance(base / 'maintenance.lock'):
            if (base / 'active.json').exists():
                raise RuntimeError('Interrupted maintenance found. Use Recover before another operation.')
            return operation(root, *args, **kwargs)
    return run


def write_record(path, record):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(record, indent=2), encoding='utf-8')
    temporary.replace(path)


def control(root, action, state):
    installer_core.powershell(Path(__file__).resolve().parent / 'Maintenance-Tasks.ps1'
                              if not getattr(sys, 'frozen', False)
                              else Path(sys._MEIPASS) / 'Maintenance-Tasks.ps1',
                              '-Root', root, '-Action', action, '-StateFile', state)


def resume(root, state, controller):
    path = backup_base(root) / 'active.json'
    if path.exists():
        record = read_json(path)
        record['phase'] = 'starting'
        write_record(path, record)
    controller(root, 'Resume', state)


def snapshot(root, record, action, controller):
    base = backup_base(root)
    check_tree(base)
    base.mkdir(parents=True, exist_ok=True)
    restrict(base, directory=True)
    check_tree(base)
    required = sum(p.stat().st_size for p in root.rglob('*') if p.is_file())
    if shutil.disk_usage(base).free < required * 2 + 20 * 1024**2:
        raise ValueError('Insufficient free disk space for recovery backups')
    folder = base / uuid.uuid4().hex
    folder.mkdir()
    restrict(folder, directory=True)
    meta = {'root': str(root), 'product': 'CenterEK', 'version': record['version'],
            'action': action, 'status': 'preparing', 'created_at': datetime.datetime.now(datetime.timezone.utc).isoformat()}
    write_record(folder / 'snapshot.json', meta)
    write_record(base / 'active.json', {'snapshot': folder.name})
    try:
        controller(root, 'Stop', folder / 'tasks.json')
        # The scheduler wrapper and its children must be stopped before this point.
        with MonitorInstance(root / 'data/monitor.instance.lock'):
            shutil.copytree(root, folder / 'files', ignore=lambda directory, names: ['monitor.instance.lock'] if Path(directory) == root / 'data' else [])
        database = sqlite3.connect((folder / 'files/data/monitor.sqlite3').as_uri() + '?mode=ro', uri=True)
        try:
            if database.execute('PRAGMA quick_check').fetchone() != ('ok',):
                raise RuntimeError('Database backup integrity check failed')
        finally:
            database.close()
        meta.update(status='ready', hashes=digest_tree(folder / 'files'),
                    task_state_sha256=hashlib.sha256((folder / 'tasks.json').read_bytes()).hexdigest())
        write_record(folder / 'snapshot.json', meta)
    except Exception:
        if (folder / 'tasks.json').exists():
            resume(root, folder / 'tasks.json', controller)
        (base / 'active.json').unlink(missing_ok=True)
        raise
    return folder


def complete(root):
    (backup_base(root) / 'active.json').unlink(missing_ok=True)


def register_current(root):
    manager = None
    if getattr(sys, 'frozen', False):
        # Retain this maintenance runtime outside the application, so rolling back
        # to a release without maintenance support still leaves Apps & Features usable.
        base = backup_base(root)
        pointer = base / 'manager.json'
        if pointer.exists() and read_json(pointer).get('version') == installer_core.VERSION:
            candidate = Path(read_json(pointer)['path']).resolve()
            if candidate.is_relative_to(base.resolve()) and candidate.is_file():
                manager = candidate
        if manager is None:
            folder = base / ('manager-' + uuid.uuid4().hex)
            folder.mkdir()
            restrict(folder, directory=True)
            manager = folder / 'CenterEK.exe'
            shutil.copy2(sys.executable, manager)
            shutil.copytree(Path(sys.executable).parent / '_internal', folder / '_internal')
            write_record(pointer, {'path': str(manager), 'version': installer_core.VERSION})
    installer_core.register_product(root, read_json(root / 'installation.local.json')['version'], manager=manager)


def recover(root, progress=lambda text: None, controller=control, readiness=None):
    root = Path(root)
    if not root.is_absolute() or root == Path(root.anchor) or '"' in str(root):
        raise ValueError('Dedicated installation required')
    root = root.resolve()
    check_tree(root)
    base = backup_base(root)
    check_tree(base)
    with MonitorInstance(base / 'maintenance.lock'):
        name = read_json(base / 'active.json')['snapshot']
        if not re.fullmatch('[a-f0-9]{32}', name):
            raise ValueError('Invalid maintenance recovery journal')
        folder = base / name
        meta = read_json(folder / 'snapshot.json')
        if meta.get('root') != str(root) or meta.get('product') != 'CenterEK':
            raise ValueError('Recovery journal belongs to another installation')
        progress('Recovering interrupted maintenance')
        if meta.get('status') == 'ready':
            verify_snapshot(root, folder)
            controller(root, 'Stop', folder / ('recovery-stop-' + uuid.uuid4().hex + '.json'))
            restore_files(root, folder)
        elif meta.get('status') != 'preparing':
            raise ValueError('Invalid maintenance recovery state')
        if (folder / 'tasks.json').exists():
            resume(root, folder / 'tasks.json', controller)
        (readiness or installer_core.check_ready)(root)
        register_current(root)
        complete(root)
        return str(folder)


def verify_snapshot(root, folder):
    root = Path(root).resolve()
    base = backup_base(root).resolve()
    folder = Path(folder).resolve()
    if folder.parent != base or not re.fullmatch('[a-f0-9]{32}', folder.name):
        raise ValueError('Invalid recovery snapshot')
    check_tree(folder)
    meta = read_json(folder / 'snapshot.json')
    if meta.get('root') != str(root) or meta.get('status') != 'ready' or meta.get('product') != 'CenterEK':
        raise ValueError('Snapshot does not belong to this installation')
    if digest_tree(folder / 'files') != meta.get('hashes'):
        raise ValueError('Snapshot integrity check failed')
    if hashlib.sha256((folder / 'tasks.json').read_bytes()).hexdigest() != meta.get('task_state_sha256'):
        raise ValueError('Task backup integrity check failed')
    return meta


def restore_files(root, folder):
    verify_snapshot(root, folder)
    journal = backup_base(root) / 'active.json'
    if journal.exists():
        record = read_json(journal)
        record['phase'] = 'restoring'
        write_record(journal, record)
    # Preserve the displaced installation as evidence; never delete customer data.
    displaced = folder.parent / ('displaced-' + uuid.uuid4().hex)
    displaced.mkdir()
    restrict(displaced, directory=True)
    for item in list(root.iterdir()):
        shutil.move(str(item), str(displaced / item.name))
    shutil.copytree(folder / 'files', root, dirs_exist_ok=True)


def latest_snapshot(root, action):
    candidates = []
    base = backup_base(root)
    if base.exists():
        check_tree(base)
        for path in base.glob('*/snapshot.json'):
            meta = read_json(path)
            if meta.get('action') == action and meta.get('status') == 'ready' and meta.get('root') == str(root):
                candidates.append((meta['created_at'], path.parent))
    if not candidates:
        raise ValueError('No matching recovery snapshot exists')
    return max(candidates)[1]


def latest_upgrade(root):
    root, _ = validate_root(root)
    return latest_snapshot(root, 'upgrade')


def version_key(value):
    match = re.fullmatch(r'(\d+)\.(\d+)\.(\d+)(?:-preview)?', value)
    if not match:
        raise ValueError('Unsupported installation version')
    return tuple(map(int, match.groups())) + (0 if value.endswith('-preview') else 1,)


@exclusive
def upgrade(root, executable, assets, progress=lambda text: None, controller=control, readiness=None):
    root, record = validate_root(root)
    executable, assets = Path(executable), Path(assets)
    if version_key(installer_core.VERSION) <= version_key(record['version']):
        raise ValueError('Upgrade requires a newer version; use rollback to restore a backup')
    if not executable.is_file() or not (executable.parent / '_internal').is_dir():
        raise ValueError('Complete packaged runtime is required')
    if any(not (assets / name).is_file() for name in installer_core.SCRIPTS) or not (assets / 'web/index.html').is_file():
        raise ValueError('Installation payload is incomplete')
    progress('Stopping CenterEK and backing up all settings, accounts and measurements')
    folder = snapshot(root, record, 'upgrade', controller)
    try:
        for name in ('_internal', 'web', 'licenses'):
            source = executable.parent / name if name == '_internal' else assets / name
            if source.is_dir():
                destination = root / name
                if destination.exists():
                    shutil.rmtree(destination)
                shutil.copytree(source, destination)
        shutil.copy2(executable, root / 'CenterEK.exe')
        for name in (*installer_core.SCRIPTS, 'INSTALLATION.md', 'REMOTE-ACCESS.md', 'MAINTENANCE.md', 'THIRD-PARTY.txt'):
            if (assets / name).is_file():
                shutil.copy2(assets / name, root / name)
        record.update(version=installer_core.VERSION, recovery_snapshot=folder.name)
        write_record(root / 'installation.local.json', record)
        resume(root, folder / 'tasks.json', controller)
        (readiness or installer_core.check_ready)(root)
        register_current(root)
        complete(root)
    except Exception:
        progress('Upgrade failed; restoring previous installation')
        # Stop again into a separate state file; original task state remains intact.
        controller(root, 'Stop', folder / 'failed-tasks.json')
        restore_files(root, folder)
        resume(root, folder / 'tasks.json', controller)
        register_current(root)
        complete(root)
        raise RuntimeError('Upgrade failed. Previous installation restored; backup: ' + str(folder)) from None
    return str(folder)


@exclusive
def rollback(root, progress=lambda text: None, controller=control, readiness=None):
    root, record = validate_root(root)
    source = latest_upgrade(root)
    verify_snapshot(root, source)
    progress('Backing up current installation before rollback')
    safety = snapshot(root, record, 'rollback', controller)
    try:
        restore_files(root, source)
        resume(root, source / 'tasks.json', controller)
        (readiness or installer_core.check_ready)(root)
        register_current(root)
        complete(root)
    except Exception:
        controller(root, 'Stop', safety / 'failed-tasks.json')
        restore_files(root, safety)
        resume(root, safety / 'tasks.json', controller)
        register_current(root)
        complete(root)
        raise RuntimeError('Rollback failed; pre-rollback installation restored') from None
    return str(safety)


@exclusive
def uninstall(root, progress=lambda text: None, controller=control):
    root, record = validate_root(root)
    progress('Backing up installation; customer data and certificates will be retained')
    folder = snapshot(root, record, 'uninstall', controller)
    try:
        controller(root, 'Remove', folder / 'tasks.json')
        # Explicit managed-code allowlist. data/, certs/ and config files are retained.
        for name in ('_internal', 'web', 'licenses'):
            path = root / name
            if path.exists():
                shutil.rmtree(path)
        for name in ('CenterEK.exe', *installer_core.SCRIPTS, 'INSTALLATION.md', 'REMOTE-ACCESS.md', 'MAINTENANCE.md', 'THIRD-PARTY.txt'):
            (root / name).unlink(missing_ok=True)
        record.update(status='uninstalled', recovery_snapshot=folder.name)
        write_record(root / 'installation.local.json', record)
        installer_core.unregister_product(root)
        shortcut = Path(os.environ.get('ProgramData', r'C:\ProgramData')) / 'Microsoft/Windows/Start Menu/Programs/CenterEK/CenterEK.url'
        if shortcut.exists() and shortcut.read_text(encoding='utf-8') == '[InternetShortcut]\nURL=' + record.get('url', '') + '\n':
            shortcut.unlink()
        complete(root)
    except Exception:
        restore_files(root, folder)
        resume(root, folder / 'tasks.json', controller)
        register_current(root)
        complete(root)
        raise RuntimeError('Uninstall failed; installation restored from protected backup') from None
    return str(folder)


@exclusive
def restore_uninstalled(root, progress=lambda text: None, controller=control, readiness=None):
    root, record = validate_root(root, allow_uninstalled=True)
    if record['status'] != 'uninstalled':
        raise ValueError('Use rollback for an installed product')
    source = latest_snapshot(root, 'uninstall')
    verify_snapshot(root, source)
    progress('Restoring the protected pre-uninstall backup')
    write_record(backup_base(root) / 'active.json', {'snapshot': source.name})
    controller(root, 'Stop', source / ('restore-stop-' + uuid.uuid4().hex + '.json'))
    restore_files(root, source)
    resume(root, source / 'tasks.json', controller)
    (readiness or installer_core.check_ready)(root)
    register_current(root)
    complete(root)
    return str(source)
