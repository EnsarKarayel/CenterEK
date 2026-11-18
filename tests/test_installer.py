from dataclasses import replace
from pathlib import Path
import tempfile
import unittest
import ctypes
import os
from types import SimpleNamespace
from unittest.mock import patch
import installer_core


class InstallerValidationTests(unittest.TestCase):
    def test_disk_requirement_includes_nested_runtime_and_growth(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            executable = root / 'setup.exe'
            executable.write_bytes(b'launcher')
            assets = root / '_internal'
            runtime = assets / 'nested/python.dll'
            runtime.parent.mkdir(parents=True)
            runtime.write_bytes(b'runtime')
            self.assertEqual(600 * 1024**2, installer_core.required_install_space(executable, assets))
            original_stat = Path.stat
            def sized_stat(path, *args, **kwargs):
                result = original_stat(path, *args, **kwargs)
                if path == runtime:
                    fields = list(result)
                    fields[6] = 400 * 1024**2
                    return os.stat_result(fields)
                return result
            with patch.object(Path, 'stat', sized_stat):
                self.assertEqual(2 * (400 * 1024**2 + len(b'launcher')),
                                 installer_core.required_install_space(executable, assets))

    @unittest.skipUnless(os.name == 'nt', 'Windows native computer identity')
    def test_native_computer_identity_matches_windows_not_long_dns_name(self):
        self.assertEqual(os.environ['COMPUTERNAME'].upper(), installer_core.windows_computer_name())
        class NativeCall:
            def __call__(self, kind, buffer, size):
                self.kind = kind
                buffer.value = 'QA-PC'
                return True
        native = NativeCall()
        with patch.object(ctypes, 'WinDLL', return_value=SimpleNamespace(GetComputerNameExW=native)), patch.object(installer_core.socket, 'gethostname', return_value='qa-pc-with-a-long-dns-identity.example.invalid'):
            self.assertEqual('QA-PC', installer_core.windows_computer_name())
            self.assertEqual(0, native.kind)

    @unittest.skipUnless(os.name == 'nt', 'Windows native computer identity')
    def test_identity_failure_does_not_fall_back_to_unrelated_dns_name(self):
        class NativeFailure:
            def __call__(self, *args): return False
        with patch.object(ctypes, 'WinDLL', return_value=SimpleNamespace(GetComputerNameExW=NativeFailure())), patch.object(ctypes, 'get_last_error', return_value=5):
            with self.assertRaises(OSError):
                installer_core.windows_computer_name()

    def test_fresh_local_defaults_and_password_redaction(self):
        with tempfile.TemporaryDirectory() as temporary:
            options = installer_core.Options(str(Path(temporary) / 'CenterEK'), 'admin', 'private-install-password')
            target = installer_core.validate(options)
            self.assertFalse(target.exists())
            self.assertEqual(options.address, '127.0.0.1')
            self.assertNotIn(options.password, repr(options))

    def test_existing_data_and_unsafe_paths_rejected_without_mutation(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / 'CenterEK'
            target.mkdir()
            marker = target / 'customer-data.txt'
            marker.write_text('preserve')
            options = installer_core.Options(str(target), 'admin', 'private-install-password')
            with self.assertRaises(ValueError):
                installer_core.validate(options)
            self.assertEqual(marker.read_text(), 'preserve')
            for bad in (str(Path(target.anchor)), 'relative-folder'):
                with self.assertRaises(ValueError):
                    installer_core.validate(replace(options, target=bad))

    def test_invalid_network_password_and_ca_selection(self):
        with tempfile.TemporaryDirectory() as temporary:
            options = installer_core.Options(str(Path(temporary) / 'CenterEK'), 'admin', 'private-install-password')
            for change in ({'address':'0.0.0.0'}, {'mode':'lan','address':'127.0.0.1'},
                           {'mode':'lan','address':'8.8.8.8'}, {'port':True}, {'port':443},
                           {'password':'short'}, {'trust_ca':False}, {'hostname':'bad/host'}):
                with self.assertRaises(ValueError):
                    installer_core.validate(replace(options, **change))
            self.assertEqual(installer_core.validate(replace(options, mode='lan', address='192.168.1.50')),
                             Path(options.target).resolve())
