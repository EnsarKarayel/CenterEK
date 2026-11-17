import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import release_signing

spec = importlib.util.spec_from_file_location('commercial_gate', Path(__file__).resolve().parents[1] / 'scripts/release/check_commercial.py')
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


class CommercialReleaseTests(unittest.TestCase):
    def test_preview_without_real_acceptance_is_never_sale_ready(self):
        issues = gate.assess({'version': '0.9.0-preview', 'signed': False, 'license_mode': 'preview'}, {}, {})
        self.assertGreater(len(issues), 10)
        self.assertTrue(any('signature' in issue for issue in issues))
        self.assertTrue(any('EULA' in issue for issue in issues))
        self.assertTrue(any('reboot' in issue for issue in issues))

    def test_success_boolean_cannot_substitute_for_required_acceptance_steps(self):
        issues = gate.assess({'version': '1.0.0', 'signed': True, 'license_mode': 'commercial', 'eula_sha256': 'expected'},
                            {'ok': True, 'kind': 'isolated-windows', 'python_absent': True},
                            {'approved': True, 'seller': 'Seller', 'country': 'TR', 'support_email': 'support@example.invalid', 'publisher_thumbprint': 'A' * 40, 'approved_eula_sha256': 'wrong'})
        self.assertTrue(any('mismatched' in issue for issue in issues))
        self.assertTrue(any('endpoint_received' in issue for issue in issues))

    def test_invalid_certificate_or_timestamp_refused_before_signing(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'setup.exe'
            path.write_bytes(b'fixture')
            with patch.object(release_signing.subprocess, 'run') as run:
                with self.assertRaises(ValueError):
                    release_signing.sign(path, 'invalid', 'https://timestamp.example.invalid', 'signtool.exe')
                with self.assertRaises(ValueError):
                    release_signing.sign(path, 'A' * 40, 'http://timestamp.example.invalid', 'signtool.exe')
                run.assert_not_called()

    def test_signing_uses_sha256_and_checks_the_actual_publisher(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'setup.exe'
            path.write_bytes(b'fixture')
            with patch.object(release_signing.subprocess, 'run') as run, patch.object(release_signing, 'verify') as verify:
                run.return_value.returncode = 0
                release_signing.sign(path, 'A' * 40, 'https://timestamp.example.invalid', 'signtool.exe')
                command = run.call_args.args[0]
                self.assertEqual('SHA256', command[command.index('/fd') + 1])
                self.assertEqual('SHA256', command[command.index('/td') + 1])
                verify.assert_called_once_with(path.resolve(), 'A' * 40)
