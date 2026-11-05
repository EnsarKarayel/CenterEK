import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import monitor
import service_secrets
import start


class UnattendedTests(unittest.TestCase):
    @unittest.skipUnless(os.name == 'nt', 'Windows DPAPI')
    def test_machine_dpapi_roundtrip_and_no_plaintext(self):
        encrypted = service_secrets.protect('test-only-background-key')
        self.assertNotIn('test-only-background-key', encrypted)
        self.assertEqual(service_secrets.unprotect(encrypted), 'test-only-background-key')

    def test_missing_background_secret_never_prompts(self):
        with tempfile.TemporaryDirectory(dir=monitor.ROOT/'data') as temp:
            root = Path(temp)
            config = {'interval':30,'threshold':3,'timeout':2,'devices':[
                {'id':'a','name':'test','host':'127.0.0.1','method':'tcp','port':443,
                 'collector':{'type':'fortigate','token_env':'TEST_BACKGROUND_SECRET'}}]}
            (root/'config.local.json').write_text(json.dumps(config),encoding='utf-8')
            with patch.object(monitor,'ROOT',root), patch('sys.argv',['start.py','--non-interactive']), patch.dict(os.environ,{},clear=True), patch('getpass.getpass',side_effect=AssertionError('Unexpected prompt')):
                with self.assertRaises(SystemExit):
                    start.main()

    @unittest.skipUnless(os.name == 'nt', 'Windows DPAPI')
    def test_background_secret_loads_without_prompt(self):
        with tempfile.TemporaryDirectory(dir=monitor.ROOT/'data') as temp:
            root=Path(temp)
            config={'interval':30,'threshold':3,'timeout':2,'devices':[
                {'id':'a','name':'test','host':'127.0.0.1','method':'tcp','port':443,
                 'collector':{'type':'fortigate','token_env':'TEST_BACKGROUND_SECRET'}}]}
            (root/'config.local.json').write_text(json.dumps(config),encoding='utf-8')
            folder=root/'data'/'secure'
            folder.mkdir(parents=True)
            (folder/'service-secrets.local.json').write_text(json.dumps({'schema':1,'environment':{
                'TEST_BACKGROUND_SECRET':service_secrets.protect('test-only-background-key')}}),encoding='utf-8')
            with patch.object(monitor,'ROOT',root),patch.object(monitor,'main') as main,patch('sys.argv',['start.py','--non-interactive']),patch.dict(os.environ,{},clear=True),patch('getpass.getpass',side_effect=AssertionError('Unexpected prompt')):
                start.main()
                self.assertEqual(os.environ['TEST_BACKGROUND_SECRET'],'test-only-background-key')
                main.assert_called_once()


if __name__ == '__main__':
    unittest.main()
