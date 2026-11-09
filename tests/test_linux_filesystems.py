import json
from pathlib import Path
import tempfile
import unittest
import linux_filesystems
import install_filesystem_metrics
class FilesystemIsolationTests(unittest.TestCase):
 def test_fresh_counter_cache_and_no_fake_freshness(self):
  with tempfile.TemporaryDirectory() as folder:
   path=Path(folder)/'volumes.json'
   data={'schema':1,'collected_at':100,'volumes':[{'name':'/home','format':'xfs','total_gb':1000,'free_gb':900}]}
   path.write_text(json.dumps(data))
   self.assertEqual(linux_filesystems.cached(path,now=120)[0]['name'],'/home')
   self.assertIsNone(linux_filesystems.cached(path,now=251))
   self.assertIsNone(linux_filesystems.cached(path,now=99))
   data['volumes'][0]['free_gb']=1001;path.write_text(json.dumps(data))
   self.assertIsNone(linux_filesystems.cached(path,now=120))
 def test_filesystem_helper_is_separate_and_cannot_use_network_or_credentials(self):
  service,timer=install_filesystem_metrics.units('/usr/bin/python3.6')
  self.assertIn('User=centerek-fs',service)
  self.assertIn('PrivateNetwork=true',service)
  self.assertIn('RestrictAddressFamilies=AF_UNIX',service)
  self.assertIn('InaccessiblePaths=-/etc/centerek-agent',service)
  self.assertNotIn('--config',service)
  self.assertIn('OnUnitActiveSec=60s',timer)
  self.assertIn('StateDirectoryMode=0750',service)
if __name__=='__main__':unittest.main()
