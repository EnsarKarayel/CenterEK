import json
from contextlib import closing
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

import installer_core
import maintenance
import monitor


class MaintenanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / 'Customer CenterEK'
        self.root.mkdir()
        self.program_data = self.base / 'ProgramData'
        self.program_data.mkdir()
        self.patch_env = patch.dict('os.environ', {'ProgramData': str(self.program_data)})
        self.patch_env.start()
        self.addCleanup(self.patch_env.stop)
        self.registration = patch.object(installer_core, 'register_product')
        self.registration.start()
        self.addCleanup(self.registration.stop)
        self.unregister = patch.object(installer_core, 'unregister_product')
        self.unregister.start()
        self.addCleanup(self.unregister.stop)
        for name in ('data/secure', 'certs/panel', '_internal', 'web'):
            (self.root / name).mkdir(parents=True)
        (self.root / 'CenterEK.exe').write_bytes(b'old runtime')
        (self.root / '_internal/old.dll').write_bytes(b'old library')
        (self.root / 'web/index.html').write_text('old ui')
        (self.root / 'config.local.json').write_text('{"customer":"preserve"}')
        (self.root / 'data/secure/agent.local.json').write_text('encrypted-secret')
        (self.root / 'certs/panel/panel-key.pem').write_text('customer-private-key')
        (self.root / 'installation.local.json').write_text(json.dumps({'product': 'CenterEK', 'version': '0.7.0-preview', 'status': 'ready'}))
        with closing(sqlite3.connect(self.root / 'data/monitor.sqlite3')) as db, db:
            db.execute('CREATE TABLE accounts(name TEXT)')
            db.execute('INSERT INTO accounts VALUES (?)', ('customer-admin',))
        self.original_db = (self.root / 'data/monitor.sqlite3').read_bytes()
        self.assets = self.base / 'payload'
        (self.assets / 'web').mkdir(parents=True)
        (self.assets / 'web/index.html').write_text('new ui')
        for name in installer_core.SCRIPTS:
            (self.assets / name).write_text('# trusted packaged script')
        self.bundle = self.base / 'bundle'
        (self.bundle / '_internal').mkdir(parents=True)
        (self.bundle / '_internal/new.dll').write_bytes(b'new library')
        self.exe = self.bundle / 'Setup.exe'
        self.exe.write_bytes(b'new runtime')
        self.actions = []

    def controller(self, root, action, state):
        self.actions.append(action)
        if action == 'Stop':
            state.write_text('[]')

    def upgrade(self, **kwargs):
        return maintenance.upgrade(self.root, self.exe, self.assets, controller=self.controller, readiness=kwargs.get('readiness', lambda root: None))

    def assert_customer_preserved(self):
        self.assertEqual(self.original_db, (self.root / 'data/monitor.sqlite3').read_bytes())
        self.assertEqual('encrypted-secret', (self.root / 'data/secure/agent.local.json').read_text())
        self.assertEqual('customer-private-key', (self.root / 'certs/panel/panel-key.pem').read_text())

    def test_upgrade_preserves_database_accounts_and_secrets(self):
        snapshot = Path(self.upgrade())
        self.assertEqual(b'new runtime', (self.root / 'CenterEK.exe').read_bytes())
        self.assertFalse((self.root / '_internal/old.dll').exists())
        self.assertTrue((self.root / '_internal/new.dll').exists())
        self.assert_customer_preserved()
        self.assertEqual('ready', maintenance.verify_snapshot(self.root, snapshot)['status'])
        self.assertEqual(['Stop', 'Resume'], self.actions)

    def test_failed_readiness_restores_old_runtime_and_database_after_migration(self):
        def fail(root):
            with closing(sqlite3.connect(root / 'data/monitor.sqlite3')) as db, db:
                db.execute('DROP TABLE accounts')
            raise RuntimeError('new release fails health check')
        with self.assertRaisesRegex(RuntimeError, 'Previous installation restored'):
            self.upgrade(readiness=fail)
        self.assertEqual(b'old runtime', (self.root / 'CenterEK.exe').read_bytes())
        self.assert_customer_preserved()
        self.assertEqual(['Stop', 'Resume', 'Stop', 'Resume'], self.actions)

    def test_manual_rollback_takes_safety_snapshot_and_restores_previous_release(self):
        self.upgrade()
        safety = Path(maintenance.rollback(self.root, controller=self.controller, readiness=lambda root: None))
        self.assertEqual(b'old runtime', (self.root / 'CenterEK.exe').read_bytes())
        self.assert_customer_preserved()
        self.assertEqual('rollback', maintenance.verify_snapshot(self.root, safety)['action'])
        self.assertEqual(b'new runtime', (safety / 'files/CenterEK.exe').read_bytes())

    def test_uninstall_removes_code_and_retains_customer_data(self):
        snapshot = Path(maintenance.uninstall(self.root, controller=self.controller))
        self.assertFalse((self.root / 'CenterEK.exe').exists())
        self.assertFalse((self.root / '_internal').exists())
        self.assert_customer_preserved()
        self.assertTrue((self.root / 'config.local.json').exists())
        self.assertEqual('uninstalled', maintenance.read_json(self.root / 'installation.local.json')['status'])
        self.assertEqual('uninstall', maintenance.verify_snapshot(self.root, snapshot)['action'])

    def test_tampered_snapshot_rejected_before_stopping_current_installation(self):
        snapshot = Path(self.upgrade())
        (snapshot / 'files/CenterEK.exe').write_bytes(b'tampered')
        before = list(self.actions)
        with self.assertRaisesRegex(ValueError, 'integrity'):
            maintenance.rollback(self.root, controller=self.controller)
        self.assertEqual(before, self.actions)

    def test_tampered_task_backup_refused_before_restoring_tasks(self):
        snapshot = Path(self.upgrade())
        (snapshot / 'tasks.json').write_text('altered task')
        before = list(self.actions)
        with self.assertRaisesRegex(ValueError, 'Task backup integrity'):
            maintenance.rollback(self.root, controller=self.controller)
        self.assertEqual(before, self.actions)

    def test_same_or_older_package_refused_before_stopping(self):
        self.upgrade()
        before = list(self.actions)
        with self.assertRaisesRegex(ValueError, 'newer version'):
            self.upgrade()
        self.assertEqual(before, self.actions)

    def test_snapshot_failure_resumes_original_tasks(self):
        with patch.object(maintenance.shutil, 'copytree', side_effect=OSError('disk full')):
            with self.assertRaises(OSError):
                self.upgrade()
        self.assertEqual(['Stop', 'Resume'], self.actions)
        self.assert_customer_preserved()

    def test_foreign_snapshot_and_unmanaged_root_rejected(self):
        with self.assertRaises(ValueError):
            maintenance.verify_snapshot(self.root, self.base)
        (self.root / 'installation.local.json').write_text('{"product":"other","status":"ready"}')
        with self.assertRaises(ValueError):
            self.upgrade()
        self.assertEqual([], self.actions)

    def test_uninstall_failure_restores_tasks_and_files(self):
        def fail_remove(root, action, state):
            self.controller(root, action, state)
            if action == 'Remove':
                raise RuntimeError('scheduler refused removal')
        with self.assertRaisesRegex(RuntimeError, 'Uninstall failed'):
            maintenance.uninstall(self.root, controller=fail_remove)
        self.assertEqual(b'old runtime', (self.root / 'CenterEK.exe').read_bytes())
        self.assert_customer_preserved()
        self.assertEqual(['Stop', 'Remove', 'Resume'], self.actions)

    def test_interrupted_upgrade_can_be_recovered_from_journal(self):
        with patch.object(maintenance.shutil, 'copy2', side_effect=SystemExit('power loss')):
            with self.assertRaises(SystemExit):
                self.upgrade()
        self.assertTrue((maintenance.backup_base(self.root) / 'active.json').exists())
        with self.assertRaisesRegex(RuntimeError, 'Interrupted maintenance'):
            self.upgrade()
        maintenance.recover(self.root, controller=self.controller, readiness=lambda root: None)
        self.assertEqual(b'old runtime', (self.root / 'CenterEK.exe').read_bytes())
        self.assert_customer_preserved()
        self.assertFalse((maintenance.backup_base(self.root) / 'active.json').exists())

    def test_concurrent_maintenance_is_refused(self):
        base = maintenance.backup_base(self.root)
        base.mkdir(parents=True)
        with maintenance.MonitorInstance(base / 'maintenance.lock'):
            with self.assertRaisesRegex(RuntimeError, 'MONITOR_ALREADY_RUNNING'):
                self.upgrade()
        self.assertEqual([], self.actions)

    def test_uninstalled_product_can_be_restored_without_recreating_accounts(self):
        maintenance.uninstall(self.root, controller=self.controller)
        maintenance.restore_uninstalled(self.root, controller=self.controller, readiness=lambda root: None)
        self.assertEqual(b'old runtime', (self.root / 'CenterEK.exe').read_bytes())
        self.assert_customer_preserved()
        self.assertEqual('ready', maintenance.read_json(self.root / 'installation.local.json')['status'])

    def test_bad_database_backup_stops_upgrade_and_resumes_original_tasks(self):
        (self.root / 'data/monitor.sqlite3').write_bytes(b'corrupt baseline')
        with self.assertRaises(sqlite3.DatabaseError):
            self.upgrade()
        self.assertEqual(b'old runtime', (self.root / 'CenterEK.exe').read_bytes())
        self.assertEqual(['Stop', 'Resume'], self.actions)

    def test_monitor_start_is_blocked_during_file_replacement(self):
        base = maintenance.backup_base(self.root)
        base.mkdir(parents=True)
        (base / 'active.json').write_text('{"phase":"restoring"}')
        with patch.object(monitor, 'ROOT', self.root), patch('sys.argv', ['monitor.py']), patch('monitor._main') as startup:
            with self.assertRaisesRegex(RuntimeError, 'MAINTENANCE_IN_PROGRESS'):
                monitor.main()
            startup.assert_not_called()

    def test_frozen_maintenance_runtime_survives_rollback_outside_application(self):
        base = maintenance.backup_base(self.root)
        base.mkdir(parents=True)
        with patch.object(sys, 'frozen', True, create=True), patch.object(sys, 'executable', str(self.exe)), patch.object(installer_core, 'register_product') as register:
            maintenance.register_current(self.root)
            manager = Path(maintenance.read_json(base / 'manager.json')['path'])
            self.assertFalse(manager.is_relative_to(self.root))
            self.assertEqual(b'new runtime', manager.read_bytes())
            self.assertTrue((manager.parent / '_internal/new.dll').is_file())
            register.assert_called_once_with(self.root, '0.7.0-preview', manager=manager)
