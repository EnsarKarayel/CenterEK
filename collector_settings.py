"""Admin collector provisioning with machine-protected credentials."""
import copy
import json
import os
from pathlib import Path
import secrets
import ssl
import tempfile
import device_settings
import service_secrets
from file_security import restrict

PROFILES = [
    {'name': 'Genel ağ cihazı · SNMP', 'status': 'implemented',
     'scope': 'Switch, router, firewall, AP: IF-MIB port durumu, hız, trafik ve hata sayaçları; SNMPv3 authPriv veya v2c.',
     'limits': 'Cihaz MIB/yetkilerine bağlıdır. Her marka/model doğrulanmadı; VLAN, PoE, VPN ve oturum bilgisi bu profilde yok.'},
    {'name': 'VMware ESXi', 'status': 'implemented', 'scope': 'CPU, RAM ve datastore ölçümleri; HTTPS salt okunur hesap.',
     'limits': 'Fiziksel disk/RAID ve donanım sıcaklığı ayrı yönetim kaynağı gerektirir.'},
    {'name': 'FortiGate REST API', 'status': 'implemented', 'scope': 'Sistem ve arayüz ölçümleri, kaynak API yanıtına bağlı cihaz envanteri.',
     'limits': 'FortiOS sürümü ve API izinleriyle doğrulanmalıdır; diğer firewall API’leriyle aynı değildir.'},
    {'name': 'Windows uç ajanı', 'status': 'implemented', 'scope': 'Yerel CPU/RAM, disk birimleri, IP ve Windows oturum raporları.',
     'limits': 'Ajan kaydı/kurulumu gerekir. RAM modülü ve fiziksel disk modeli henüz yok.'},
    {'name': 'Active Directory / DNS ajanı', 'status': 'implemented', 'scope': 'Mevcut yetkili hesapla kullanıcı, bilgisayar ve DNS envanteri.',
     'limits': 'Açık oturum bilgisi uç ajanından gelir; AD kaydı anlık oturum değildir.'},
    {'name': 'Linux kaynak ajanı / Dell iDRAC', 'status': 'planned', 'scope': 'Planlanan Linux donanım ve Redfish sağlık okuyucuları.',
     'limits': 'Henüz uygulanmadı. ICMP/TCP erişimi kaynak ölçümü yerine geçmez.'},
    {'name': 'Diğer üreticilerin özel API’leri', 'status': 'planned', 'scope': 'Üretici bazlı bağlantı adaptörleri.',
     'limits': 'Henüz uygulanmadı; genel SNMP yalnızca desteklenen ortak MIB alanlarını sağlar.'},
]


def prepare(config, payload):
    if not isinstance(payload, dict):
        raise ValueError('Geçersiz bağlantı')
    device = next((copy.deepcopy(d) for d in config['devices'] if d['id'] == payload.get('id')), None)
    kind = payload.get('type')
    fields = {'esxi': ('username', 'password'), 'fortigate': ('token',), 'snmp': ('community',)}
    version = payload.get('version', '2c')
    if kind == 'snmp':
        if version not in ('2c', '3'):
            raise ValueError('Geçersiz SNMP sürümü')
        if version == '3':
            fields['snmp'] = ('username', 'auth_password', 'privacy_password')
    if not device or kind not in fields:
        raise ValueError('Cihaz ve bağlantı türü gerekli')
    port = payload.get('port')
    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError('Geçersiz port')
    credentials = payload.get('credentials')
    if not isinstance(credentials, dict) or any(not isinstance(credentials.get(k), str) or not 1 <= len(credentials[k]) <= 2048 for k in fields[kind]):
        raise ValueError('Kimlik bilgileri gerekli')
    settings = {'type': kind, 'port': port, '_credentials': {k: credentials[k] for k in fields[kind]}}
    if kind == 'snmp':
        settings['version'] = version
        if version == '3':
            if any(len(credentials[k]) < 8 for k in ('auth_password', 'privacy_password')):
                raise ValueError('SNMPv3 parolaları en az 8 karakter olmalı')
            algorithm = payload.get('auth_protocol', 'sha256')
            if algorithm not in ('sha256', 'sha1'):
                raise ValueError('Desteklenmeyen kimlik algoritması')
            settings.update(auth_protocol=algorithm, privacy_protocol='aes128')
    ca = payload.get('ca_file', '')
    if not isinstance(ca, str) or len(ca) > 1024:
        raise ValueError('Geçersiz CA yolu')
    if ca and kind != 'snmp':
        ssl.create_default_context(cafile=ca)
        settings['ca_file'] = ca
    device['collector'] = settings
    return device


def save(config, payload, config_path, secure_path, validate):
    with device_settings.LOCK:
        device = prepare(config, payload)
        settings = device['collector']
        raw = settings.pop('_credentials')
        secure_path = Path(secure_path)
        secure_path.parent.mkdir(parents=True, exist_ok=True)
        restrict(secure_path.parent, directory=True)
        stored = json.loads(secure_path.read_text(encoding='utf-8-sig')) if secure_path.exists() else {'schema': 1, 'environment': {}}
        if stored.get('schema') != 1 or not isinstance(stored.get('environment'), dict):
            raise ValueError('Geçersiz kimlik deposu')
        values = {}
        for key, value in raw.items():
            variable = 'CENTEREK_UI_' + secrets.token_hex(12).upper()
            settings[key + '_env'] = variable
            stored['environment'][variable] = service_secrets.protect(value)
            values[variable] = value
        handle, temporary = tempfile.mkstemp(dir=secure_path.parent, suffix='.local.json')
        try:
            with os.fdopen(handle, 'w', encoding='utf-8') as stream:
                json.dump(stored, stream)
            restrict(temporary)
            os.replace(temporary, secure_path)
        finally:
            Path(temporary).unlink(missing_ok=True)
        new = copy.deepcopy(config)
        new['devices'] = [device if d['id'] == device['id'] else d for d in new['devices']]
        validate(new)
        # Persist before publishing runtime settings. Old environment names remain valid.
        device_settings.save(new, device, config_path, validate)
        os.environ.update(values)
        config['devices'] = new['devices']
