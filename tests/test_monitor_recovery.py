from pathlib import Path
from contextlib import closing
import re
import sqlite3
import subprocess
import sys
import tempfile
import unittest


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
