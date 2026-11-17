import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile
from installer_core import powershell_env


@unittest.skipUnless(os.name == 'nt', 'Windows PowerShell config generator')
class SandboxConfigurationTests(unittest.TestCase):
    def test_real_generator_creates_isolated_readonly_payload_mapping(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            release = root / 'release'
            release.mkdir()
            archive = release / 'package.zip'
            with zipfile.ZipFile(archive, 'w') as package:
                package.writestr('CenterEK-Setup/CenterEK-Setup.exe', b'non-executable fixture')
            (release / 'release-manifest.json').write_text(json.dumps({'archive': archive.name, 'sha256': hashlib.sha256(archive.read_bytes()).hexdigest()}))
            output = root / 'test'
            source = Path(__file__).resolve().parents[1] / 'scripts/qa/New-SandboxTest.ps1'
            subprocess.run(['powershell.exe', '-NoProfile', '-File', str(source), '-ReleaseFolder', str(release), '-OutputFolder', str(output)], env=powershell_env(), capture_output=True, check=True, timeout=30)
            tree = ET.parse(output / 'CenterEK-CleanWindows.wsb')
            self.assertEqual('Disable', tree.findtext('Networking'))
            self.assertEqual('Disable', tree.findtext('ClipboardRedirection'))
            mappings = tree.findall('MappedFolders/MappedFolder')
            self.assertEqual(2, len(mappings))
            self.assertEqual('true', mappings[0].findtext('ReadOnly'))
            self.assertEqual('false', mappings[1].findtext('ReadOnly'))
            self.assertEqual((output / 'reports').resolve(), Path(mappings[1].findtext('HostFolder')).resolve())
            self.assertIn('-ConfirmIsolatedMachine', tree.findtext('LogonCommand/Command'))
            self.assertFalse((output / 'reports/clean-windows-report.json').exists())
