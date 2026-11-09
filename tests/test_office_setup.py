import json
from pathlib import Path
import tempfile
import unittest
import office_setup

class OfficeSetupTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
  (self.root/'data/secure').mkdir(parents=True)
  self.config={'devices':[{'id':'esxi-a','host':'192.168.1.5','name':'ESXi host','kind':'ESXi'}, {'id':'firewall','host':'192.168.1.1','name':'Firewall','collector':{'type':'fortigate','token_env':'FORTI_TOKEN'}}]}
  (self.root/'config.local.json').write_text(json.dumps(self.config))
  (self.root/'data/secure/service-secrets.local.json').write_text(json.dumps({'schema':1,'environment':{'FORTI_TOKEN':'UNCHANGED-MACHINE-CIPHERTEXT'}}))
 def tearDown(self):self.temp.cleanup()
 def test_preserves_existing_ciphertext_and_does_not_write_cleartext(self):
  result=office_setup.save_esxi(self.root,[{'id':'esxi-a','username':'reader','password':'CLEAR-MUST-NOT-PERSIST'}],protector=lambda value:'PROTECTED',probe=lambda d,s:{'memory_total_gb':128,'datastores':[{}]})
  stored=json.loads((self.root/'data/secure/service-secrets.local.json').read_text())
  self.assertEqual(stored['environment']['FORTI_TOKEN'],'UNCHANGED-MACHINE-CIPHERTEXT')
  self.assertEqual(result[0]['memory_total_gb'],128)
  for path in self.root.rglob('*'):
   if path.is_file():self.assertNotIn('CLEAR-MUST-NOT-PERSIST',path.read_text())
  config=json.loads((self.root/'config.local.json').read_text())
  self.assertEqual(config['devices'][1],self.config['devices'][1])
 def test_failed_connection_does_not_change_configuration_or_secrets(self):
  before={path:path.read_bytes() for path in self.root.rglob('*.json')}
  def failure(*args):raise ConnectionError('not connected')
  with self.assertRaises(ConnectionError):office_setup.save_esxi(self.root,[{'id':'esxi-a','username':'reader','password':'secret'}],probe=failure)
  self.assertEqual(before,{path:path.read_bytes() for path in self.root.rglob('*.json')})
 def test_non_esxi_device_cannot_be_reconfigured(self):
  with self.assertRaises(ValueError):office_setup.save_esxi(self.root,[{'id':'firewall','username':'reader','password':'secret'}])

if __name__=='__main__':unittest.main()
