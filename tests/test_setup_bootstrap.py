from pathlib import Path
import tempfile
import unittest
import zipfile
from setup_bootstrap import extract_payload


class SetupPayloadTests(unittest.TestCase):
    def test_payload_extracts_complete_bundle(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            archive = root / 'payload.zip'
            with zipfile.ZipFile(archive, 'w') as package:
                package.writestr('CenterEK-Setup/CenterEK-Setup.exe', b'executable')
                package.writestr('CenterEK-Setup/_internal/runtime.dll', b'runtime')
            executable = extract_payload(archive, root / 'output')
            self.assertEqual(b'executable', executable.read_bytes())

    def test_unsafe_paths_rejected_before_any_extraction(self):
        for name in ('../escaped.txt', '/escaped.txt', 'C:/escaped.txt', '..\\escaped.txt'):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                archive = root / 'payload.zip'
                with zipfile.ZipFile(archive, 'w') as package:
                    package.writestr('safe.txt', b'safe')
                    package.writestr(name, b'unsafe')
                with self.assertRaises(ValueError):
                    extract_payload(archive, root / 'output')
                self.assertFalse((root / 'output/safe.txt').exists())

    def test_incomplete_bundle_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            archive = Path(folder) / 'payload.zip'
            with zipfile.ZipFile(archive, 'w') as package:
                package.writestr('README.txt', b'incomplete')
            with self.assertRaises(ValueError):
                extract_payload(archive, Path(folder) / 'output')
