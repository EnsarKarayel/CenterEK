import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('browser_access', Path(__file__).parents[1] / 'scripts/azure/browser_access.py')
gateway = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gateway)


class BrowserAccessTests(unittest.TestCase):
    def test_rejects_public_backend_and_config_injection(self):
        for ip, name, port in [('8.8.8.8', 'panel.local', 8765),
                               ('10.42.1.4', 'panel; return 200;', 8765),
                               ('10.42.1.4', 'panel\nssl_verify off', 8765),
                               ('10.42.1.4', 'panel', True),
                               ('10.42.1.4', 'panel', 65536)]:
            with self.subTest(ip=ip, name=name, port=port), self.assertRaises(ValueError):
                gateway.nginx_config(ip, name, port)

    def test_tls_verifies_private_certificate_and_preserves_origin_host(self):
        config = gateway.nginx_config('10.42.1.4', 'ce-staging')
        self.assertIn('proxy_pass https://10.42.1.4:8765;', config)
        self.assertIn('proxy_ssl_verify on;', config)
        self.assertIn('proxy_ssl_name ce-staging;', config)
        self.assertIn('proxy_set_header Host $host;', config)
        self.assertIn('location ^~ /api/agent/ { return 403; }', config)
        self.assertNotIn('proxy_ssl_verify off', config)


if __name__ == '__main__':
    unittest.main()
