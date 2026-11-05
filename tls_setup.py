"""Create a scoped pilot CA and a server certificate; never disables TLS checks."""
import argparse
import datetime
import ipaddress
from pathlib import Path
import os
import subprocess
import json
from file_security import restrict


def create(output, hostname, ips):
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID
    output = Path(output)
    if output.exists():
        raise ValueError('Sertifika klasörü zaten var; mevcut anahtarlar üzerine yazılmaz')
    names = [x509.DNSName(hostname)] + [x509.IPAddress(ipaddress.ip_address(ip)) for ip in ips]
    now = datetime.datetime.now(datetime.timezone.utc)
    ca_key, server_key = (rsa.generate_private_key(public_exponent=65537, key_size=3072) for _ in range(2))
    ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'CenterEK Pilot CA')])
    # Limit the pilot CA to the requested panel hostname and host IPs.
    constraints = [x509.DNSName(hostname)] + [x509.IPAddress(ipaddress.ip_network(ip + ('/128' if ':' in ip else '/32'), strict=False)) for ip in ips]
    ca = (x509.CertificateBuilder().subject_name(ca_name).issuer_name(ca_name).public_key(ca_key.public_key())
          .serial_number(x509.random_serial_number()).not_valid_before(now-datetime.timedelta(minutes=5))
          .not_valid_after(now+datetime.timedelta(days=365))
          .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
          .add_extension(x509.KeyUsage(False, False, False, False, False, True, True, False, False), critical=True)
          .add_extension(x509.NameConstraints(permitted_subtrees=constraints, excluded_subtrees=None), critical=True)
          .add_extension(x509.SubjectKeyIdentifier.from_public_key(ca_key.public_key()), critical=False)
          .sign(ca_key, hashes.SHA256()))
    cert = (x509.CertificateBuilder().subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, hostname)]))
            .issuer_name(ca_name).public_key(server_key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now-datetime.timedelta(minutes=5)).not_valid_after(now+datetime.timedelta(days=180))
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .add_extension(x509.KeyUsage(True, False, True, False, False, False, False, False, False), critical=True)
            .add_extension(x509.SubjectAlternativeName(names), critical=False)
            .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
            .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()), critical=False)
            .sign(ca_key, hashes.SHA256()))
    output.mkdir(parents=True)
    restrict(output, directory=True)
    files = {'panel-ca.pem': ca.public_bytes(serialization.Encoding.PEM),
             'panel-cert.pem': cert.public_bytes(serialization.Encoding.PEM),
             'panel-key.pem': server_key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())}
    # The CA private key stays only in memory. Renewal uses a new explicitly
    # distributed pilot CA; a production deployment should use the company's CA.
    for name, data in files.items():
        with (output / name).open('xb') as destination:
            destination.write(data)
    return cert.fingerprint(hashes.SHA256()).hex()


def main():
    parser = argparse.ArgumentParser(description='Pilot HTTPS sertifikası üretimi; kurum CA sertifikası da kullanılabilir')
    parser.add_argument('--hostname', required=True)
    parser.add_argument('--ip', action='append', required=True)
    parser.add_argument('--output', type=Path, default=Path('certs/panel'))
    parser.add_argument('--configure-server', action='store_true', help='Geçerli klasöre server.local.json ayarını da oluştur')
    args = parser.parse_args()
    if args.configure_server and Path('server.local.json').exists():
        parser.error('server.local.json zaten var; üzerine yazılmaz')
    fingerprint = create(args.output, args.hostname, args.ip)
    print('Sertifika üretildi:', args.output)
    print('Sunucu sertifikası SHA256:', fingerprint)
    print('İstemcilere yalnızca panel-ca.pem dosyasını aktarın; panel-key.pem sunucuda kalmalı.')
    if args.configure_server:
        settings = {'bind': str(ipaddress.ip_address(args.ip[0])), 'port': 8765,
                    'tls_cert': str(args.output / 'panel-cert.pem'), 'tls_key': str(args.output / 'panel-key.pem')}
        with Path('server.local.json').open('x', encoding='utf-8') as output:
            json.dump(settings, output, indent=2)
        print('server.local.json oluşturuldu. start.py HTTPS ayarını otomatik kullanacak.')


if __name__ == '__main__':
    main()
