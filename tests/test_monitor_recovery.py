from pathlib import Path
from contextlib import closing
import re
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import monitor


class MonitorInstanceTests(unittest.TestCase):
    def test_second_process_is_blocked_and_crash_releases_lock(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'monitor.instance.lock'
            program = ('import sys,time; from pathlib import Path; '
                       'from monitor import MonitorInstance; '
                       'lock=MonitorInstance(Path(sys.argv[1])); lock.__enter__(); '
                       'print("LOCKED",flush=True); time.sleep(60)')
            child = subprocess.Popen([sys.executable, '-u', '-c', program, str(path)],
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                self.assertEqual('LOCKED', child.stdout.readline().strip())
                with self.assertRaisesRegex(RuntimeError, 'MONITOR_ALREADY_RUNNING'):
                    with monitor.MonitorInstance(path):
                        self.fail('Concurrent writer admitted')
            finally:
                child.kill()
                child.communicate(timeout=10)
            with monitor.MonitorInstance(path):
                self.assertTrue(path.exists())

    def test_lock_prevents_startup_side_effects(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with monitor.MonitorInstance(root / 'data' / 'monitor.instance.lock'):
                with patch.object(monitor, 'ROOT', root), patch.object(monitor, '_main') as startup, patch.object(sys, 'argv', ['monitor.py']):
                    with self.assertRaisesRegex(RuntimeError, 'MONITOR_ALREADY_RUNNING'):
                        monitor.main()
                    startup.assert_not_called()

    def test_config_check_does_not_require_server_lock(self):
        with patch.object(sys, 'argv', ['monitor.py', '--check-config']), patch.object(monitor, '_main') as startup, patch.object(monitor, 'MonitorInstance') as lock:
            monitor.main()
            startup.assert_called_once()
            lock.assert_not_called()


class MonitorRecoveryBackupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        text = (Path(__file__).resolve().parents[1]/'Recover-OfficeMonitor.ps1').read_text(encoding='utf-8-sig')
        self.program = re.search(r"\$backupProgram=@'\n(.*?)\n'@", text, re.S).group(1)
        self.source = self.root/'monitor.sqlite3'
        self.target = self.root/'backup.sqlite3'

    def tearDown(self):
        self.temp.cleanup()

    def test_sqlite_snapshot_keeps_source_rows_and_bytes(self):
        with closing(sqlite3.connect(self.source)) as db, db:
            db.execute('CREATE TABLE sample (id INTEGER PRIMARY KEY, value TEXT)')
            db.execute('INSERT INTO sample VALUES (1, ?)', ('monitoring sample',))
        before = self.source.read_bytes()
        result = subprocess.run([sys.executable, '-c', self.program, str(self.source), str(self.target)], capture_output=True, text=True, timeout=15)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn('DATABASE_BACKUP_OK', result.stdout)
        self.assertEqual(before, self.source.read_bytes())
        with closing(sqlite3.connect(self.target)) as db:
            self.assertEqual([(1, 'monitoring sample')], db.execute('SELECT * FROM sample').fetchall())
            self.assertEqual('ok', db.execute('PRAGMA quick_check').fetchone()[0])

    def test_corrupt_source_is_preserved_and_backup_not_claimed(self):
        self.source.write_bytes(b'not a SQLite database')
        result = subprocess.run([sys.executable, '-c', self.program, str(self.source), str(self.target)], capture_output=True, text=True, timeout=15)
        self.assertNotEqual(0, result.returncode)
        self.assertNotIn('DATABASE_BACKUP_OK', result.stdout)
        self.assertEqual(b'not a SQLite database', self.source.read_bytes())
        self.assertFalse(self.target.exists())
