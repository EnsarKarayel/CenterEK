"""Generate a bounded TLS-verifying gateway config, without deploying resources."""
import argparse
import ipaddress
import re
from pathlib import Path
from urllib.parse import urlsplit


def assert_publishable(auth, *, tenant_id, client_id, principal_ids, origin=None):
    """Fail closed before external ingress; use the LIVE ARM authConfig response."""
    import uuid
    tenant_id = str(uuid.UUID(tenant_id))
    client_id = str(uuid.UUID(client_id))
    expected = {str(uuid.UUID(value)) for value in principal_ids}
    if not expected:
        raise ValueError('At least one explicitly approved identity is required')
    if origin is not None:
        parsed = urlsplit(origin)
        if parsed.scheme != 'https' or not parsed.hostname or parsed.netloc != parsed.hostname or parsed.path or parsed.query or parsed.fragment:
            raise ValueError('Expected an exact public HTTPS origin')
    props = auth.get('properties', {})
    providers = props.get('identityProviders', {})
    aad = providers.get('azureActiveDirectory', {})
    registration = aad.get('registration', {})
    validation = aad.get('validation', {})
    policy = validation.get('defaultAuthorizationPolicy', {}).get('allowedPrincipals', {})
    global_policy = props.get('globalValidation', {})
    checks = (
        props.get('platform', {}).get('enabled') is True,
        props.get('httpSettings', {}).get('requireHttps') is True,
        global_policy.get('unauthenticatedClientAction') == 'RedirectToLoginPage',
        global_policy.get('redirectToProvider') == 'azureActiveDirectory',
        not global_policy.get('excludedPaths'),
        aad.get('enabled') is True,
        registration.get('clientId', '').lower() == client_id,
        registration.get('openIdIssuer', '').rstrip('/') == f'https://login.microsoftonline.com/{tenant_id}/v2.0',
        registration.get('clientSecretSettingName') == 'entra-client-secret',
        set(validation.get('allowedAudiences', [])) == {client_id},
        set(policy.get('identities', [])) == expected,
        not policy.get('groups'),
        props.get('login', {}).get('allowedExternalRedirectUrls', []) in ([], [origin]) if origin else not props.get('login', {}).get('allowedExternalRedirectUrls'),
        all(not value.get('enabled') for name, value in providers.items() if name != 'azureActiveDirectory'),
    )
    if not all(checks):
        raise ValueError('Live authentication configuration does not match approved access scope')


def nginx_config(backend_ip, backend_name, port=8765):
    address = ipaddress.IPv4Address(backend_ip)
    if not any(address in ipaddress.ip_network(n) for n in ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16')):
        raise ValueError('Backend must use RFC1918 addressing')
    if not re.fullmatch(r'[a-zA-Z0-9](?:[a-zA-Z0-9.-]{0,251}[a-zA-Z0-9])?', backend_name):
        raise ValueError('Invalid backend certificate DNS name')
    if type(port) is not int or not 1024 <= port <= 65535:
        raise ValueError('Invalid backend port')
    return '''worker_processes 1;
pid /tmp/nginx.pid;
error_log /dev/stderr warn;
events { worker_connections 256; }
http {
    server_tokens off;
    access_log off;
    client_body_temp_path /tmp/client_body;
    proxy_temp_path /tmp/proxy;
    limit_req_zone $binary_remote_addr zone=requests:1m rate=30r/s;
    limit_conn_zone $binary_remote_addr zone=connections:1m;
    server {
        listen 8080;
        client_max_body_size 8k;
        client_body_timeout 10s;
        client_header_timeout 10s;
        keepalive_timeout 30s;
        limit_req zone=requests burst=60 nodelay;
        limit_req_status 429;
        limit_conn connections 40;
        add_header Strict-Transport-Security "max-age=31536000" always;
        # Endpoint enrollment stays private; interactive access only.
        location ^~ /api/agent/ { return 403; }
        location / {
            proxy_pass https://BACKEND:PORT;
            proxy_ssl_verify on;
            proxy_ssl_trusted_certificate /etc/centerek/backend-ca.pem;
            proxy_ssl_server_name on;
            proxy_ssl_name BACKEND_NAME;
            proxy_ssl_protocols TLSv1.2 TLSv1.3;
            proxy_ssl_verify_depth 2;
            proxy_http_version 1.1;
            proxy_set_header Host $host;
            proxy_set_header Connection "";
            proxy_set_header Authorization "";
            proxy_set_header X-Forwarded-For "";
            proxy_set_header X-Forwarded-Host "";
            proxy_set_header Forwarded "";
            proxy_connect_timeout 5s;
            proxy_read_timeout 30s;
            proxy_send_timeout 15s;
            proxy_buffering on;
        }
    }
}
'''.replace('BACKEND_NAME', backend_name).replace('BACKEND', str(address)).replace('PORT', str(port))


def telemetry_config(backend_ip, backend_name, port=8765):
    """Only one POST path; valid scoped site tokens are checked by the backend."""
    config = nginx_config(backend_ip, backend_name, port)
    config = config.replace('client_max_body_size 8k;', 'client_max_body_size 8m;')
    config = config.replace('rate=30r/s;', 'rate=2r/s;').replace('burst=60', 'burst=10')
    config = config.replace('location ^~ /api/agent/ { return 403; }', 'location / { return 403; }')
    config = config.replace('        location / {\n            proxy_pass',
        '        location = /api/agent/site {\n            limit_except POST { deny all; }\n            proxy_pass')
    config = config.replace('proxy_set_header Authorization "";', 'proxy_set_header Authorization $http_authorization;')
    return config


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backend-ip', required=True)
    parser.add_argument('--backend-name', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(nginx_config(args.backend_ip, args.backend_name), encoding='utf-8')


if __name__ == '__main__':
    main()
