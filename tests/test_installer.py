from dataclasses import replace
from pathlib import Path
import tempfile
import unittest
import installer_core


class InstallerValidationTests(unittest.TestCase):
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
