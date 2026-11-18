import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from file_security import restrict
from installer_core import powershell_env


@unittest.skipUnless(os.name == 'nt', 'Windows NTFS ACL test')
class SecretACLTests(unittest.TestCase):
    def test_preexisting_explicit_everyone_permission_is_removed(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'private'
            path.mkdir()
            subprocess.run(['icacls.exe', str(path), '/grant', '*S-1-1-0:(OI)(CI)(F)'], capture_output=True, check=True)
            restrict(path, directory=True)
            child = path / 'key.pem'
            child.write_text('ephemeral fixture, not a key')
            script = "$ErrorActionPreference='Stop'; $a=Get-Acl -LiteralPath $env:ACL_TEST_PATH; @{protected=$a.AreAccessRulesProtected;current_sid=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value;sids=@($a.Access|ForEach-Object {$_.IdentityReference.Translate([Security.Principal.SecurityIdentifier]).Value})}|ConvertTo-Json -Compress"
            result = subprocess.run(['powershell.exe', '-NoProfile', '-Command', script], env=powershell_env(ACL_TEST_PATH=str(path)), capture_output=True, check=True)
            acl = json.loads(result.stdout)
            self.assertTrue(acl['protected'])
            self.assertNotIn('S-1-1-0', acl['sids'])
            self.assertIn('S-1-5-18', acl['sids'])
            self.assertIn('S-1-5-32-544', acl['sids'])
            self.assertEqual({acl['current_sid'], 'S-1-5-18', 'S-1-5-32-544'}, set(acl['sids']))
            self.assertEqual('ephemeral fixture, not a key', child.read_text())
