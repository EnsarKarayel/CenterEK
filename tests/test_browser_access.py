import importlib.util
import copy
from pathlib import Path
import unittest
from unittest.mock import patch, MagicMock
from urllib.error import HTTPError

spec = importlib.util.spec_from_file_location('browser_access', Path(__file__).parents[1] / 'scripts/azure/browser_access.py')
gateway = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gateway)
publish_spec = importlib.util.spec_from_file_location('publish_browser_access', Path(__file__).parents[1] / 'scripts/azure/publish_browser_access.py')
publisher = importlib.util.module_from_spec(publish_spec)
with patch.dict('sys.modules', {'browser_access': gateway}):
    publish_spec.loader.exec_module(publisher)


class BrowserAccessTests(unittest.TestCase):
    def test_anonymous_api_and_spoofed_identity_cannot_reach_data(self):
        opener = MagicMock()
        opener.open.side_effect = HTTPError('https://panel.example/api/status', 302, 'Found', {'Location': '/.auth/login/aad'}, None)
        with patch.object(publisher, 'build_opener', return_value=opener):
            publisher.probe_anonymous('https://panel.example')
        self.assertEqual(opener.open.call_count, 4)
        for call in opener.open.call_args_list:
            self.assertIn('untrusted-client', dict(call.args[0].header_items()).values())
        for code, location in [(200, ''), (302, 'https://untrusted.example/login'), (302, '/api/status')]:
            opener.open.side_effect = HTTPError('https://panel.example/', code, 'Response', {'Location': location}, None)
            with self.subTest(code=code, location=location), patch.object(publisher, 'build_opener', return_value=opener), self.assertRaises(RuntimeError):
                publisher.probe_anonymous('https://panel.example')

    def test_publish_guard_rejects_anonymous_broadened_or_insecure_live_auth(self):
        tenant = '11111111-1111-1111-1111-111111111111'
        client = '22222222-2222-2222-2222-222222222222'
        user = '33333333-3333-3333-3333-333333333333'
        valid = {'properties': {
            'platform': {'enabled': True}, 'httpSettings': {'requireHttps': True},
            'globalValidation': {'unauthenticatedClientAction': 'RedirectToLoginPage', 'redirectToProvider': 'azureActiveDirectory'},
            'identityProviders': {'azureActiveDirectory': {'enabled': True,
                'registration': {'clientId': client, 'openIdIssuer': f'https://login.microsoftonline.com/{tenant}/v2.0', 'clientSecretSettingName': 'entra-client-secret'},
                'validation': {'allowedAudiences': [client], 'defaultAuthorizationPolicy': {'allowedPrincipals': {'identities': [user]}}}}}}}
        arguments = dict(tenant_id=tenant, client_id=client, principal_ids=[user])
        gateway.assert_publishable(valid, **arguments)
        changes = [
            (['platform', 'enabled'], False),
            (['httpSettings', 'requireHttps'], False),
            (['globalValidation', 'unauthenticatedClientAction'], 'AllowAnonymous'),
            (['globalValidation', 'excludedPaths'], ['/api/*']),
            (['identityProviders', 'azureActiveDirectory', 'registration', 'openIdIssuer'], 'https://login.microsoftonline.com/common/v2.0'),
            (['identityProviders', 'azureActiveDirectory', 'validation', 'defaultAuthorizationPolicy', 'allowedPrincipals', 'identities'], [user, client]),
        ]
        for path, value in changes:
            broken = copy.deepcopy(valid)
            target = broken['properties']
            for key in path[:-1]:
                target = target[key]
            target[path[-1]] = value
            with self.subTest(path=path), self.assertRaises(ValueError):
                gateway.assert_publishable(broken, **arguments)

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
