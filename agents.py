"""Scoped machine credentials and authenticated telemetry ingestion."""
import argparse
import datetime
import hashlib
import hmac
import ipaddress
import json
import math
import os
from pathlib import Path
import re
import secrets
import time
import subprocess
from file_security import restrict
from urllib.parse import urlsplit


def timestamp(value):
    stamp = datetime.datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    if stamp.tzinfo is None:
        raise ValueError('Saat dilimi gerekli')
    return stamp.timestamp()


def host(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9.-]{0,251}[A-Za-z0-9]|[A-Za-z0-9]', value):
        raise ValueError('Geçersiz bilgisayar adı')
    return value.rstrip('.').upper()


def endpoint_report(data, computer):
    if data.get('schema') != 1 or host(data.get('computer')) != computer:
        raise ValueError('Bilgisayar eşleşmiyor')
    if data.get('status') not in ('ok', 'error'):
        raise ValueError('Geçersiz durum')
    ips = data.get('ips', [])
    sessions = data.get('sessions', [])
    if not isinstance(ips, list) or len(ips) > 64 or not isinstance(sessions, list) or len(sessions) > 100:
        raise ValueError('Kayıt sayısı sınırı')
    result = {'schema': 1, 'computer': computer, 'collected_at': data['collected_at'],
              'status': data['status'], 'ips': [str(ipaddress.ip_address(ip)) for ip in ips],
              'sessions': [], 'source': 'Kimliği doğrulanmış Windows ajanı',
              'address_source': data.get('address_source') if data.get('address_source') in ('Yerel ağ kartları', 'DNS çözümlemesi') else 'Bilinmiyor', 'resources': {}, 'interfaces': [],
              'error': 'Uç bilgisayar ölçüm hatası' if data['status'] == 'error' else None}
    interval=data.get('interval_seconds',60)
    if type(interval) is not int or not 15 <= interval <= 300:
        raise ValueError('Geçersiz ölçüm aralığı')
    result['interval_seconds']=interval
    for session in sessions:
        if type(session.get('id')) is not int or type(session.get('state')) is not int or not 0 <= session['state'] <= 9:
            raise ValueError('Geçersiz oturum')
        for key in ('username', 'domain'):
            if not isinstance(session.get(key), str) or len(session[key]) > 256:
                raise ValueError('Geçersiz kullanıcı alanı')
        result['sessions'].append({k: session[k] for k in ('id', 'state', 'username', 'domain')})
    primary = data.get('primary_ip')
    if primary:
        primary = str(ipaddress.ip_address(primary))
        if primary not in result['ips']:
            raise ValueError('Birincil IP yerel adreslerden biri olmalı')
        result['primary_ip'] = primary
    for key in ('cpu_percent', 'memory_percent', 'memory_total_gb', 'memory_used_gb'):
        value = data.get('resources', {}).get(key)
        if type(value) in (int, float) and 0 <= value <= (100 if key.endswith('_percent') else 1000000):
            result['resources'][key] = value
    interfaces = data.get('interfaces', [])
    if not isinstance(interfaces, list) or len(interfaces) > 128:
        raise ValueError('Geçersiz arayüzler')
    for interface in interfaces:
        ip = str(ipaddress.ip_address(interface['ip']))
        if ip not in result['ips']:
            raise ValueError('Arayüz IP eşleşmiyor')
        transport = interface.get('transport', 'unknown')
        if transport not in ('wired', 'wireless', 'other', 'unknown'):
            raise ValueError('Geçersiz ağ türü')
        mac = interface.get('mac')
        if mac is not None and (not isinstance(mac, str) or not re.fullmatch(r'(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}', mac)):
            raise ValueError('Geçersiz MAC adresi')
        result['interfaces'].append({'ip': ip, 'name': str(interface.get('name', ''))[:120], 'transport': transport, 'mac': mac.lower() if mac else None})
    volumes = data.get('volumes', [])
    if not isinstance(volumes, list) or len(volumes) > 128:
        raise ValueError('Geçersiz disk listesi')
    result['volumes'] = []
    for volume in volumes:
        if not isinstance(volume, dict):
            raise ValueError('Geçersiz disk')
        total, free = volume.get('total_gb'), volume.get('free_gb')
        if any(type(v) not in (int, float) or not math.isfinite(v) for v in (total, free)) or not 0 <= free <= total <= 100000000:
            raise ValueError('Geçersiz disk kapasitesi')
        result['volumes'].append({'name': str(volume.get('name', ''))[:120],
                                  'format': str(volume.get('format', ''))[:40],
                                  'total_gb': total, 'free_gb': free})
    return result


def directory_report(data, computer):
    if data.get('schema') != 1 or host(data.get('server')) != computer:
        raise ValueError('Dizin sunucusu eşleşmiyor')
    result = {'schema': 1, 'server': computer, 'collected_at': data['collected_at']}
    for key in ('domain', 'netbios'):
        if not isinstance(data.get(key), str) or len(data[key]) > 253:
            raise ValueError('Geçersiz domain')
        result[key] = data[key]
    fields = {'users': ('username', 'display_name', 'enabled', 'last_logon'),
              'computers': ('name', 'fqdn', 'os', 'enabled', 'last_logon'),
              'leases': ('ip', 'mac', 'hostname', 'state', 'expires'), 'dns': ('fqdn', 'ip')}
    for section, keys in fields.items():
        rows = data.get(section, [])
        if not isinstance(rows, list) or len(rows) > 20000:
            raise ValueError('Geçersiz dizin listesi')
        result[section] = []
        for row in rows:
            if not isinstance(row, dict) or any(not (v is None or type(v) in (str, bool)) or (isinstance(v, str) and len(v) > 1024) for k, v in row.items() if k in keys):
                raise ValueError('Geçersiz dizin kaydı')
            result[section].append({k: row.get(k) for k in keys})
    errors = data.get('errors', [])
    if not isinstance(errors, list) or len(errors) > 20 or any(not isinstance(e, str) or len(e) > 1024 for e in errors):
        raise ValueError('Geçersiz hata listesi')
    result['errors'] = errors
    return result


class Registry:
    def __init__(self, store, root):
        self.store, self.root = store, Path(root)
        with store.lock, store.db:
            store.db.execute('''CREATE TABLE IF NOT EXISTS agents (
                id TEXT PRIMARY KEY, computer TEXT, kind TEXT, digest TEXT, enabled INTEGER,
                received REAL, reported REAL, UNIQUE(computer,kind))''')

    def register(self, computer, kind):
        computer = host(computer)
        if kind not in ('endpoint', 'directory'):
            raise ValueError('Geçersiz ajan türü')
        agent_id = secrets.token_hex(12)
        token = agent_id + '.' + secrets.token_urlsafe(32)
        with self.store.lock, self.store.db:
            self.store.db.execute('INSERT INTO agents VALUES (?,?,?,?,1,NULL,NULL)',
                                  (agent_id, computer, kind, hashlib.sha256(token.encode()).hexdigest()))
        return {'id': agent_id, 'computer': computer, 'kind': kind, 'token': token}

    def list(self):
        with self.store.lock:
            return [dict(r) for r in self.store.db.execute('SELECT id,computer,kind,enabled,received,reported FROM agents ORDER BY computer')]

    def revoke(self, agent_id):
        with self.store.lock, self.store.db:
            self.store.db.execute('UPDATE agents SET enabled=0 WHERE id=?', (agent_id,))

    def ingest(self, token, data, kind):
        if not isinstance(token, str) or len(token) > 160:
            return 401
        agent_id = token.split('.')[0]
        with self.store.lock, self.store.db:
            row = self.store.db.execute('SELECT * FROM agents WHERE id=? AND enabled=1', (agent_id,)).fetchone()
            if not row or row['kind'] != kind or not hmac.compare_digest(row['digest'], hashlib.sha256(token.encode()).hexdigest()):
                return 401
            now = time.time()
            try:
                stamp = timestamp(data['collected_at'])
                if not now - 180 <= stamp <= now + 60:
                    raise ValueError('Eski veya gelecek tarihli rapor')
                if row['reported'] is not None and stamp <= row['reported']:
                    return 409
                if row['received'] is not None and now - row['received'] < 5:
                    return 429
                report = endpoint_report(data, row['computer']) if kind == 'endpoint' else directory_report(data, row['computer'])
            except (ValueError, KeyError, TypeError, AttributeError):
                return 400
            report['received_at'] = datetime.datetime.fromtimestamp(now, datetime.timezone.utc).isoformat()
            report['agent_id'] = row['id']
            report['authenticated'] = True
            folder = self.root / 'data'
            if kind == 'endpoint':
                folder /= 'endpoint-sessions'
                filename = row['computer'] + '.json'
            else:
                filename = 'directory-inventory.json'
            folder.mkdir(parents=True, exist_ok=True)
            target = folder / filename
            if folder.is_symlink() or target.is_symlink():
                return 400
            temporary = folder / (filename + '.' + secrets.token_hex(8) + '.upload.tmp')
            try:
                with temporary.open('x', encoding='utf-8') as output:
                    json.dump(report, output, ensure_ascii=False, allow_nan=False)
                os.replace(temporary, target)
            except FileExistsError:
                return 503
            except Exception:
                temporary.unlink(missing_ok=True)
                raise
            self.store.db.execute('UPDATE agents SET received=?,reported=? WHERE id=?', (now, stamp, agent_id))
            if kind == 'endpoint':
                metric = {'status': report['status'], 'error': report.get('error'), 'values': report['resources']}
                payload = json.dumps(metric, ensure_ascii=False)
                self.store.db.execute('INSERT OR REPLACE INTO metrics VALUES (?,?,?)', ('agent-' + agent_id, now, payload))
                self.store.db.execute('INSERT INTO metric_samples VALUES (?,?,?)', ('agent-' + agent_id, now, payload))
        return 202


def main():
    import monitor
    parser = argparse.ArgumentParser(description='CenterEK ajan kaydı; AD hesabı oluşturmaz')
    parser.add_argument('action', choices=['register', 'list', 'revoke'])
    parser.add_argument('--computer')
    parser.add_argument('--kind', choices=['endpoint', 'directory'], default='endpoint')
    parser.add_argument('--url')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--id')
    args = parser.parse_args()
    (monitor.ROOT / 'data').mkdir(exist_ok=True)
    store = monitor.Store(monitor.ROOT / 'data' / 'monitor.sqlite3')
    registry = Registry(store, monitor.ROOT)
    try:
        if args.action == 'list':
            for row in registry.list():
                print(row['id'], row['computer'], row['kind'], 'aktif' if row['enabled'] else 'iptal', row['received'])
        elif args.action == 'revoke':
            if not args.id:
                parser.error('--id gerekli')
            registry.revoke(args.id)
            print('Gönderim anahtarı iptal edildi.')
        else:
            url = urlsplit(args.url or '')
            if not args.computer or not args.output or url.scheme != 'https' or not url.hostname or url.username or url.password or url.path not in ('', '/') or url.query or url.fragment:
                parser.error('--computer, --output ve https://SUNUCU:PORT biçiminde --url gerekli')
            if args.output.exists():
                parser.error('Mevcut kayıt dosyasının üzerine yazılmaz')
            args.output.parent.mkdir(parents=True, exist_ok=True)
            record = registry.register(args.computer, args.kind)
            record['url'] = args.url.rstrip('/')
            with args.output.open('x', encoding='utf-8') as output:
                json.dump(record, output, indent=2)
            try:
                restrict(args.output)
            except (PermissionError, OSError, subprocess.SubprocessError):
                registry.revoke(record['id'])
                args.output.unlink(missing_ok=True)
                raise PermissionError('Kayıt dosyası korunamadı')
            print('Kayıt dosyası oluşturuldu:', args.output)
            print('Dosya tek bilgisayara ait gizli anahtar içerir; güvenli aktarın ve Setup-Agent.ps1 ile koruyun.')
    finally:
        store.db.close()


if __name__ == '__main__':
    main()
