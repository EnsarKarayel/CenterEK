"""Read a locally supplied directory snapshot; never assumes a lease means online."""
import datetime
import ipaddress
import json


def normalize_mac(value):
    text = ''.join(c for c in str(value).lower() if c in '0123456789abcdef')
    # DHCP client identifiers are not always Ethernet MAC addresses.
    return ':'.join(text[n:n+2] for n in range(0, 12, 2)) if len(text) == 12 else ''


def load(path):
    if not path.exists():
        return {'status': 'unconfigured', 'message': 'AD/DHCP/DNS dosyası henüz aktarılmadı', 'clients': [], 'computers': []}
    try:
        if path.stat().st_size > 20 * 1024 * 1024:
            raise ValueError()
        data = json.loads(path.read_text(encoding='utf-8-sig'))
        if data.get('schema') != 1:
            raise ValueError()
        stamp = datetime.datetime.fromisoformat(data['collected_at'].replace('Z', '+00:00'))
        age = (datetime.datetime.now(datetime.timezone.utc) - stamp).total_seconds()
        if age < -300:
            raise ValueError()
        computers = data.get('computers', [])
        users = data.get('users', [])
        if not isinstance(users, list) or len(users) > 20000:
            raise ValueError()
        if not isinstance(computers, list) or len(computers) > 20000:
            raise ValueError()
        by_fqdn = {}
        for computer in computers:
            key = str(computer.get('fqdn') or '').rstrip('.').lower()
            if key:
                by_fqdn.setdefault(key, []).append(computer)
        rows = []
        for source, items in [('DHCP kirası', data.get('leases', [])), ('DNS kaydı', data.get('dns', []))]:
            if not isinstance(items, list) or len(items) > 20000:
                raise ValueError()
            for item in items:
                try:
                    ip = str(ipaddress.ip_address(item['ip']))
                except (ValueError, KeyError):
                    continue
                name = str(item.get('hostname') or item.get('fqdn') or '')
                matches = by_fqdn.get(name.rstrip('.').lower(), [])
                c = matches[0] if len(matches) == 1 else {}
                rows.append({'ip': ip, 'mac': normalize_mac(item.get('mac', '')), 'hostname': name,
                             'os': str(c.get('os') or ''), 'vendor': '', 'type': 'Domain kaydı' if c else '',
                             'interface': '', 'online': None, 'last_seen': None, 'source': source,
                             'lease_state': item.get('state'), 'lease_expires': item.get('expires'),
                             'domain': str(data.get('domain') or ''), 'ad_enabled': c.get('enabled'),
                             'stale': age > 900, 'collected_at': data['collected_at']})
        return {'status': 'ok', 'collected_at': data['collected_at'], 'stale': age > 900,
                'domain': str(data.get('domain') or ''), 'netbios': str(data.get('netbios') or ''), 'server': str(data.get('server') or ''),
                'errors': data.get('errors', []), 'computers': computers, 'users': users, 'clients': rows,
                'authenticated': data.get('authenticated', False), 'received_at': data.get('received_at')}
    except (ValueError, TypeError, KeyError, OSError, AttributeError):
        return {'status': 'error', 'message': 'Dizin dosyası okunamadı veya biçimi geçersiz', 'clients': [], 'computers': []}
