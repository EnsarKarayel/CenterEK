import unittest
from pathlib import Path
import office_endpoint_update
class OfficeEndpointUpdateTests(unittest.TestCase):
 def test_replace_only_old_validator_and_preserve_unrelated_code(self):
  original="import json\ndef host(value): return value\ndef endpoint_report(data, computer):\n    return {'computer': computer}\n\ndef other(): return 'KEEP-FIREWALL-AND-AD'\n"
  payload=(Path(__file__).parents[1]/'endpoint_validator_payload.py').read_text(encoding='utf-8')
  updated,needed=office_endpoint_update.replace_validator(original,payload)
  self.assertTrue(needed);self.assertIn("def other(): return 'KEEP-FIREWALL-AND-AD'",updated)
  namespace={};exec(updated,namespace)
  report=namespace['endpoint_report']({'schema':1,'computer':'PC01','status':'ok','collected_at':'now','ips':[],'sessions':[],'volumes':[{'name':'/','format':'xfs','total_gb':100,'free_gb':50}]},'PC01')
  self.assertEqual(report['volumes'][0]['free_gb'],50)
  same,needed=office_endpoint_update.replace_validator(updated,payload)
  self.assertFalse(needed);self.assertEqual(same,updated)
 def test_unknown_validator_fails_without_writing(self):
  with self.assertRaises(ValueError):office_endpoint_update.replace_validator('def endpoint_report(unexpected): pass','anything')
if __name__=='__main__':unittest.main()
