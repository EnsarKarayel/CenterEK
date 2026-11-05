"""Interactive local configuration. Never persists passwords or API tokens."""
import json
from pathlib import Path
from monitor import ROOT, validate


def main():
    path = ROOT / 'config.local.json'
    config = json.loads(path.read_text(encoding='utf-8-sig'))
    for n, device in enumerate(config['devices'], 1):
        print(n, device['name'], device['host'])
    number = int(input('Cihaz numarası: '))
    if not 1 <= number <= len(config['devices']):
        raise ValueError('Geçersiz cihaz numarası')
    device = config['devices'][number - 1]
    kind = input('Bağlantı türü (esxi / fortigate / snmp): ').strip().lower()
    if kind not in ('esxi', 'fortigate', 'snmp'):
        raise ValueError('Desteklenmeyen tür')
    prefix = 'CENTEREK_' + ''.join(c if c.isalnum() else '_' for c in device['id']).upper()
    settings = {'type': kind, 'port': int(input('Port (boş: varsayılan): ') or {'esxi': 443, 'fortigate': 4443, 'snmp': 161}[kind])}
    keys = {'esxi': ['username', 'password'], 'fortigate': ['token'], 'snmp': ['community']}[kind]
    for key in keys:
        settings[key + '_env'] = prefix + '_' + key.upper()
    if kind != 'snmp':
        print('HTTPS sertifikası doğrulanır. Özel CA / kendinden imzalı sertifika için PEM dosyasını kullanın.')
        ca = input('Güvenilen CA PEM dosya yolu (sistem deposu için boş): ').strip().strip('"')
        if ca:
            if not Path(ca).is_file():
                raise ValueError('Sertifika dosyası bulunamadı')
            settings['ca_file'] = ca
    else:
        print('SNMPv2c community şifrelenmez. Cihazda yalnızca okuma ve izleme IP kısıtlaması kullanın.')
    device['collector'] = settings
    validate(config)
    backup = ROOT / 'config.backup.local.json'
    backup.write_bytes(path.read_bytes())
    path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding='utf-8')
    print('Kaydedildi. Diğer cihazlar için tekrar çalıştırın. Başlatmak için: python start.py')


if __name__ == '__main__':
    main()
