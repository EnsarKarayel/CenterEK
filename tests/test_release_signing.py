import importlib.util
from pathlib import Path
import tempfile
import json
import zipfile
import unittest
from unittest.mock import patch
import release_signing

spec = importlib.util.spec_from_file_location('commercial_gate', Path(__file__).resolve().parents[1] / 'scripts/release/check_commercial.py')
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


class CommercialReleaseTests(unittest.TestCase):
    def artifact_fixture(self, folder):
        folder = Path(folder)
        bundle = folder / 'dist/CenterEK-Setup'
        assets = bundle / '_internal'
        assets.mkdir(parents=True)
        (bundle / 'CenterEK-Setup.exe').write_bytes(b'inner signed fixture')
        (assets / 'EULA.txt').write_bytes(b'approved terms')
        (assets / 'THIRD-PARTY.txt').write_bytes(b'reviewed inventory')
        (assets / 'release-policy.json').write_text(json.dumps({'mode': 'commercial', 'public_keys': {'test': 'test-public-key'}}))
        legal = {'seller': 'Test seller', 'country': 'TR', 'support_email': 'test@example.invalid'}
        (assets / 'publisher.json').write_text(json.dumps(legal))
        (folder / 'setup.exe').write_bytes(b'outer signed fixture')
        with zipfile.ZipFile(folder / 'bundle.zip', 'w') as archive:
            for path in bundle.rglob('*'):
                if path.is_file():
                    archive.write(path, 'CenterEK-Setup/' + path.relative_to(bundle).as_posix())
        manifest = {'setup': 'setup.exe', 'archive': 'bundle.zip',
                    'setup_sha256': gate.digest(folder / 'setup.exe'), 'sha256': gate.digest(folder / 'bundle.zip'),
                    'eula_sha256': gate.digest(assets / 'EULA.txt'), 'third_party_sha256': gate.digest(assets / 'THIRD-PARTY.txt')}
        acceptance = {'setup_sha256': manifest['setup_sha256'], 'bundle_exe_sha256': gate.digest(bundle / 'CenterEK-Setup.exe')}
        return folder, bundle, manifest, acceptance, legal

    def test_exact_approved_artifacts_pass_integrity(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder, _, manifest, acceptance, legal = self.artifact_fixture(tmp)
            self.assertEqual([], gate.assess_artifacts(folder, manifest, acceptance, legal))

    def test_changed_outer_setup_and_archive_are_rejected(self):
        for name in ('setup.exe', 'bundle.zip'):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                folder, _, manifest, acceptance, legal = self.artifact_fixture(tmp)
                with (folder / name).open('ab') as stream:
                    stream.write(b'changed')
                self.assertTrue(gate.assess_artifacts(folder, manifest, acceptance, legal))

    def test_stale_outer_acceptance_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder, _, manifest, acceptance, legal = self.artifact_fixture(tmp)
            acceptance['setup_sha256'] = '0' * 64
            self.assertTrue(any('Outer setup' in issue for issue in gate.assess_artifacts(folder, manifest, acceptance, legal)))

    def test_changed_or_extra_extracted_payload_is_rejected(self):
        for name in ('_internal/EULA.txt', '_internal/extra.dll'):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                folder, bundle, manifest, acceptance, legal = self.artifact_fixture(tmp)
                (bundle / name).write_bytes(b'changed payload')
                self.assertTrue(gate.assess_artifacts(folder, manifest, acceptance, legal))

    def test_approval_must_match_packaged_legal_text_and_seller(self):
        for field in ('eula_sha256', 'third_party_sha256', 'seller'):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as tmp:
                folder, _, manifest, acceptance, legal = self.artifact_fixture(tmp)
                (legal if field == 'seller' else manifest)[field] = 'different'
                self.assertTrue(gate.assess_artifacts(folder, manifest, acceptance, legal))

    def test_unsafe_manifest_and_archive_paths_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder, _, manifest, acceptance, legal = self.artifact_fixture(tmp)
            manifest['setup'] = '../setup.exe'
            self.assertTrue(gate.assess_artifacts(folder, manifest, acceptance, legal))
            manifest['setup'] = 'setup.exe'
            with zipfile.ZipFile(folder / 'bundle.zip', 'a') as archive:
                archive.writestr('CenterEK-Setup/../outside.txt', b'unsafe')
            manifest['sha256'] = gate.digest(folder / 'bundle.zip')
            self.assertTrue(gate.assess_artifacts(folder, manifest, acceptance, legal))

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
