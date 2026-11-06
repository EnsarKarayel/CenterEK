"""NetWatch: dependency-free, local-first availability monitor."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import ipaddress
import json
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys
import threading
import time
import connectors
import insights
import csv
import io
import re
import ssl
from http.cookies import SimpleCookie
import auth as authentication
import directory
import endpoints
import agents
import device_settings
import collector_settings
import network_settings
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = Path(__file__).resolve().parent
STARTED_AT = time.time()


def validate(config):
    for key, minimum, maximum in [('interval', 5, 3600), ('threshold', 1, 20), ('timeout', 1, 10)]:
        if type(config.get(key)) is not int or not minimum <= config[key] <= maximum:
            raise ValueError('Geçersiz ayar: ' + key)
    devices = config.get('devices', [])
    if not 1 <= len(devices) <= 1024:
        raise ValueError('1-1024 cihaz gerekli')
    ids = set()
    for d in devices:
        ipaddress.ip_address(d['host'])
        if d['id'] in ids or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', d['id']) or not d['name']:
            raise ValueError('Cihaz kimliği benzersiz ve adı dolu olmalı')
        ids.add(d['id'])
        if d['method'] not in ('icmp', 'tcp'):
            raise ValueError('Yöntem icmp veya tcp olmalı')
        if d['method'] == 'tcp' and (type(d.get('port')) is not int or not 1 <= d['port'] <= 65535):
            raise ValueError('Geçersiz TCP portu')
        collector = d.get('collector')
        if collector:
            if collector.get('type') not in ('esxi', 'fortigate', 'snmp'):
                raise ValueError('Desteklenmeyen ölçüm bağlantısı')
            if 'port' in collector and (type(collector['port']) is not int or not 1 <= collector['port'] <= 65535):
                raise ValueError('Geçersiz bağlantı portu')
    graph = {d['id']: d.get('depends_on', []) for d in devices}
    if any(not isinstance(parents, list) or not all(isinstance(p, str) for p in parents) for parents in graph.values()):
        raise ValueError('depends_on bir cihaz ID listesi olmalı')
    visited = set()
    def visit(node, path):
        if node in path:
            raise ValueError('Cihaz bağımlılıklarında döngü var')
        if node in visited:
            return
        for parent in graph[node]:
            if parent not in graph:
                raise ValueError('Bağımlı cihaz bulunamadı: ' + parent)
            visit(parent, path | {node})
        visited.add(node)
    for device in graph:
        visit(device, set())
    return config


def probe(d, timeout):
    start = time.monotonic()
    try:
        if d['method'] == 'tcp':
            with socket.create_connection((d['host'], d['port']), timeout):
                pass
        else:
            args = ['ping', '-n', '1', '-w', str(timeout * 1000), d['host']] if sys.platform == 'win32' else ['ping', '-n', '-c', '1', '-W', str(timeout), d['host']]
            result = subprocess.run(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                    timeout=timeout + 2, creationflags=0x08000000 if sys.platform == 'win32' else 0)
            if result.returncode:
                return False, None, 'ICMP yanıtı alınamadı'
        return True, round((time.monotonic() - start) * 1000, 1), None
    except (OSError, subprocess.SubprocessError) as exc:
        return False, None, type(exc).__name__


class Store:
    def __init__(self, path):
        self.lock = threading.RLock()
        self.db = sqlite3.connect(str(path), check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS state (id TEXT PRIMARY KEY, status TEXT, failures INTEGER,
            checked REAL, latency REAL, error TEXT);
        CREATE TABLE IF NOT EXISTS incidents (id INTEGER PRIMARY KEY, device TEXT,
            started REAL, confirmed REAL, ended REAL);
        CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value REAL);
        CREATE TABLE IF NOT EXISTS samples (device TEXT, checked REAL, ok INTEGER, latency REAL);
        CREATE INDEX IF NOT EXISTS samples_device_checked ON samples(device, checked);
        CREATE TABLE IF NOT EXISTS metrics (device TEXT PRIMARY KEY, checked REAL, payload TEXT);
        CREATE TABLE IF NOT EXISTS metric_samples (device TEXT, checked REAL, payload TEXT);
        CREATE INDEX IF NOT EXISTS metric_samples_device_checked ON metric_samples(device, checked);
        ''')

    def record(self, device, ok, latency, error, threshold, now=None):
        now = time.time() if now is None else now
        with self.lock, self.db:
            row = self.db.execute('SELECT * FROM state WHERE id=?', (device,)).fetchone()
            failures = 0 if ok else (row['failures'] if row else 0) + 1
            status = 'up' if ok else ('down' if failures >= threshold else 'suspect')
            opened = self.db.execute('SELECT id FROM incidents WHERE device=? AND ended IS NULL', (device,)).fetchone()
            if not ok and failures == 1:
                self.db.execute('INSERT OR REPLACE INTO meta VALUES (?,?)', ('first:' + device, now))
            if status == 'down' and not opened:
                first = self.db.execute('SELECT value FROM meta WHERE key=?', ('first:' + device,)).fetchone()
                self.db.execute('INSERT INTO incidents(device,started,confirmed) VALUES (?,?,?)', (device, first[0] if first else now, now))
            if ok and opened:
                self.db.execute('UPDATE incidents SET ended=? WHERE id=?', (now, opened['id']))
            self.db.execute('INSERT OR REPLACE INTO state VALUES (?,?,?,?,?,?)', (device, status, failures, now, latency, error))
            self.db.execute('INSERT INTO samples VALUES (?,?,?,?)', (device, now, int(ok), latency))

    def record_metrics(self, device, result, now=None):
        now = time.time() if now is None else now
        with self.lock, self.db:
            previous = self.db.execute('SELECT * FROM metrics WHERE device=?', (device,)).fetchone()
            old = json.loads(previous['payload']) if previous else {}
            old_interfaces = {str(x.get('name')): x for x in old.get('values', {}).get('interfaces', [])}
            delta = now - previous['checked'] if previous else 0
            for interface in result.get('values', {}).get('interfaces', []):
                last = old_interfaces.get(str(interface.get('name')), {})
                for direction in ('rx', 'tx'):
                    current, before = interface.get(direction + '_bytes'), last.get(direction + '_bytes')
                    discontinuity = interface.get('counter_discontinuity') != last.get('counter_discontinuity')
                    interface[direction + '_mbps'] = (round((current - before) * 8 / delta / 1e6, 4)
                        if type(current) is int and type(before) is int and current >= before
                        and 0 < delta < 180 and old.get('status') == 'ok' and not discontinuity else None)
            payload = json.dumps(result, ensure_ascii=False)
            self.db.execute('INSERT OR REPLACE INTO metrics VALUES (?,?,?)', (device, now, payload))
            history = dict(result, values={k: v for k, v in result.get('values', {}).items() if k != 'clients'})
            self.db.execute('INSERT INTO metric_samples VALUES (?,?,?)', (device, now, json.dumps(history, ensure_ascii=False)))

    def inventory(self, config):
        rows, sources = [], []
        with self.lock:
            for device in config['devices']:
                if device.get('collector', {}).get('type') != 'fortigate':
                    continue
                metric = self.db.execute('SELECT * FROM metrics WHERE device=?', (device['id'],)).fetchone()
                payload = json.loads(metric['payload']) if metric else {}
                values = payload.get('values', {})
                stale = not metric or time.time() - metric['checked'] > 180
                sources.append({'device': device['id'], 'name': device['name'], 'checked': metric['checked'] if metric else None,
                                'status': values.get('inventory_status', 'unknown'), 'stale': stale,
                                'errors': values.get('section_errors', []), 'limit': values.get('inventory_limit', 2000)})
                for client in values.get('clients', []):
                    rows.append(dict(client, firewall=device['name'], checked=metric['checked'], stale=stale))
            discovered = []
            for device in config['devices']:
                if not device.get('discovered'):
                    continue
                state = self.db.execute('SELECT * FROM state WHERE id=?', (device['id'],)).fetchone()
                checked = state['checked'] if state else None
                stale = checked is None or time.time() - checked > max(180, config.get('interval', 30) * 3)
                discovered.append({'hostname': device['name'] if device['name'] != device['host'] else None,
                                   'ip': device['host'], 'mac': None, 'os': None, 'type': device.get('kind'),
                                   'source': 'Otomatik keşif / erişim', 'checked': checked, 'collected_at': checked,
                                   'stale': stale, 'online': None if stale or state['status'] not in ('up', 'down') else state['status'] == 'up'})
            if discovered:
                rows.extend(discovered)
                sources.append({'name': 'Otomatik ağ keşfi', 'status': 'ok',
                                'checked': max((c['checked'] or 0 for c in discovered)),
                                'stale': all(c['stale'] for c in discovered), 'limit': 1024, 'errors': []})
        imported = directory.load(ROOT / 'data' / 'directory-inventory.json')
        rows.extend(imported.pop('clients', []))
        return {'clients': rows, 'sources': sources, 'directory': imported}

    def prune(self):
        with self.lock, self.db:
            cutoff = time.time() - 30 * 86400
            self.db.execute('DELETE FROM samples WHERE checked < ?', (cutoff,))
            self.db.execute('DELETE FROM metric_samples WHERE checked < ?', (cutoff,))

    def history(self, device):
        with self.lock:
            since = time.time() - 86400
            samples = [dict(r) for r in self.db.execute(
                'SELECT checked,ok,latency FROM samples WHERE device=? AND checked>=? ORDER BY checked', (device, since))]
            metrics = [{'checked': r['checked'], **json.loads(r['payload'])} for r in self.db.execute(
                'SELECT checked,payload FROM metric_samples WHERE device=? AND checked>=? ORDER BY checked', (device, since))]
            return {'samples': samples, 'metrics': metrics}

    def snapshot(self, config):
        with self.lock:
            states = {r['id']: dict(r) for r in self.db.execute('SELECT * FROM state')}
            devices = []
            for d in config['devices']:
                row = {key: d.get(key) for key in ('id', 'name', 'host', 'kind', 'method', 'port', 'vendor', 'model', 'agent_computer')}
                row['depends_on'] = d.get('depends_on', [])
                row.update(states.get(d['id'], {'status': 'unknown', 'checked': None}))
                row['stale'] = row['checked'] is None or time.time() - row['checked'] > config['interval'] * 2 + config['timeout'] + 2
                metric = self.db.execute('SELECT * FROM metrics WHERE device=?', (d['id'],)).fetchone()
                row['metrics'] = ({'checked': metric['checked'], **json.loads(metric['payload'])} if metric else
                                  {'status': 'unconfigured', 'error': 'Ölçüm bağlantısı yapılandırılmadı', 'values': {}, 'checked': None})
                row['metrics']['stale'] = not metric or time.time() - metric['checked'] > 180
                row['metrics']['values'].pop('clients', None)
                counts = self.db.execute('SELECT COUNT(*),SUM(ok) FROM samples WHERE device=? AND checked>=?',
                                         (d['id'], time.time() - 86400)).fetchone()
                row['availability_24h'] = round(100 * counts[1] / counts[0], 2) if counts[0] else None
                row['sample_count_24h'] = counts[0]
                devices.append(row)
            incidents = [dict(r) for r in self.db.execute('SELECT * FROM incidents ORDER BY id DESC LIMIT 100')]
            return {'devices': devices, 'incidents': incidents, 'alerts': insights.alerts(devices),
                    'now': time.time(), 'interval': config['interval'], 'version': '0.6.1-preview',
                    'runtime': {'started': STARTED_AT, 'uptime_seconds': round(time.time()-STARTED_AT),
                                'mode': os.environ.get('CENTEREK_RUN_MODE', 'interactive')}}


def collect(config, store, stop):
    with ThreadPoolExecutor(max_workers=32) as pool:
        while not stop.is_set():
            started = time.monotonic()
            devices = tuple(config['devices'])
            results = pool.map(lambda d: probe(d, config['timeout']), devices)
            for d, result in zip(devices, results):
                store.record(d['id'], *result, config['threshold'])
            store.prune()
            stop.wait(max(0, config['interval'] - (time.monotonic() - started)))


def collect_metrics(config, store, stop):
    with ThreadPoolExecutor(max_workers=4) as pool:
        while not stop.is_set():
            devices = tuple(config['devices'])
            for device, result in zip(devices, pool.map(connectors.read, devices)):
                store.record_metrics(device['id'], result)
            stop.wait(60)


def handler(store, config, auth, registry=None):
    if auth is None:
        raise ValueError('Kimlik doğrulama bileşeni gerekli')
    registry = registry or agents.Registry(store, ROOT)
    class Handler(BaseHTTPRequestHandler):
        def respond(self, status, body=b'', mime='application/json; charset=utf-8', headers=None):
            self.send_response(status)
            self.send_header('Content-Type', mime)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
            for key, value in (headers or {}).items():
                self.send_header(key, value)
            self.end_headers()
            self.wfile.write(body)

        def token(self):
            try:
                cookie = SimpleCookie(self.headers.get('Cookie', ''))
                return cookie['centerek_session'].value if 'centerek_session' in cookie else ''
            except Exception:
                return ''

        def do_POST(self):
            if self.path in ('/api/agent/endpoint', '/api/agent/directory'):
                if not isinstance(self.connection, ssl.SSLSocket):
                    self.respond(403, b'{"error":"HTTPS required"}')
                    return
                try:
                    length = int(self.headers.get('Content-Length', 0))
                    maximum = 256 * 1024 if self.path.endswith('/endpoint') else 5 * 1024 * 1024
                    if not 1 <= length <= maximum or self.headers.get_content_type() != 'application/json':
                        raise ValueError()
                    payload = json.loads(self.rfile.read(length).decode('utf-8-sig'), parse_constant=lambda x: (_ for _ in ()).throw(ValueError()))
                    header = self.headers.get('Authorization', '')
                    token = header[7:] if header.startswith('Bearer ') else ''
                    status = registry.ingest(token, payload, self.path.rsplit('/', 1)[-1])
                    self.respond(status, b'{}')
                except (ValueError, TypeError):
                    self.respond(400, b'{}')
                except OSError:
                    self.respond(503, b'{}')
                return
            if not auth or self.path not in ('/api/login', '/api/logout', '/api/accounts', '/api/devices', '/api/collectors', '/api/access-settings'):
                self.respond(404)
                return
            expected = {('https://' if auth.secure else 'http://') + self.headers.get('Host', '')}
            if auth.public_origin:
                expected.add(auth.public_origin)
            if self.headers.get('Origin') not in expected or self.headers.get('Sec-Fetch-Site') == 'cross-site':
                self.respond(403, b'{"error":"Origin rejected"}')
                return
            if self.path == '/api/logout':
                auth.logout(self.token())
                self.respond(200, b'{}', headers={'Set-Cookie': auth.cookie(clear=True)})
                return
            if self.path in ('/api/accounts', '/api/devices', '/api/collectors', '/api/access-settings'):
                user = auth.user(self.token())
                if not user or user['role'] != 'admin':
                    self.respond(403, b'{}')
                    return
                try:
                    length = int(self.headers.get('Content-Length', 0))
                    if not 1 <= length <= 4096 or self.headers.get_content_type() != 'application/json':
                        raise ValueError('Geçersiz istek')
                    payload = json.loads(self.rfile.read(length))
                    if not isinstance(payload, dict) or any(not isinstance(payload.get(k, ''), str) or len(payload.get(k, '')) > 256 for k in ('current_password', 'username', 'password', 'role', 'action')):
                        raise ValueError('Geçersiz alan')
                    check, error = auth.login(user['username'], payload.get('current_password', ''), self.client_address[0])
                    if error:
                        self.respond(429 if error == 'limited' else 403, b'{}')
                        return
                    auth.logout(check)
                    if self.path == '/api/access-settings':
                        network_settings.stage(ROOT, payload.get('settings'))
                        with store.lock, store.db:
                            store.db.execute('INSERT INTO account_audit VALUES (?,?,?,?)', (time.time(), user['username'], 'access-settings-stage', 'server'))
                        self.respond(200, b'{"restart_required":true}')
                        return
                    if self.path == '/api/collectors':
                        if not isinstance(self.connection, ssl.SSLSocket) and not ipaddress.ip_address(self.server.server_address[0]).is_loopback:
                            self.respond(403, b'{}')
                            return
                        if payload.get('action') == 'test':
                            result = connectors.read(collector_settings.prepare(config, payload.get('collector')))
                            self.respond(200, json.dumps({'ok': result['status'] == 'ok', 'error': result.get('error')}).encode())
                        elif payload.get('action') == 'save':
                            collector_settings.save(config, payload.get('collector'), getattr(store, 'config_path', ROOT / 'config.local.json'), ROOT / 'data' / 'secure' / 'service-secrets.local.json', validate)
                            with store.lock, store.db:
                                store.db.execute('INSERT INTO account_audit VALUES (?,?,?,?)', (time.time(), user['username'], 'collector-save', payload['collector']['id']))
                            self.respond(200, b'{}')
                        else:
                            raise ValueError('Geçersiz işlem')
                        return
                    if self.path == '/api/devices':
                        if payload.get('action') == 'test':
                            _, device = device_settings.candidate(config, payload.get('device'), validate)
                            ok, latency, error = probe(device, 2)
                            self.respond(200, json.dumps({'ok': ok, 'latency': latency, 'error': error}).encode())
                        elif payload.get('action') == 'save':
                            device = device_settings.save(config, payload.get('device'), getattr(store, 'config_path', ROOT / 'config.local.json'), validate)
                            with store.lock, store.db:
                                store.db.execute('INSERT INTO account_audit VALUES (?,?,?,?)', (time.time(), user['username'], 'device-save', device['id']))
                            self.respond(200, b'{}')
                        else:
                            raise ValueError('Geçersiz işlem')
                        return
                    auth.manage(user['username'], payload.get('action'), payload.get('username', ''), payload.get('password', ''), payload.get('role', 'viewer'))
                    self.respond(200, b'{}')
                except sqlite3.IntegrityError:
                    self.respond(409, b'{"error":"Account already exists"}')
                except (ValueError, TypeError):
                    self.respond(400, b'{"error":"Invalid account operation"}')
                except OSError:
                    self.respond(503, b'{"error":"Settings could not be saved"}')
                return
            try:
                length = int(self.headers.get('Content-Length', 0))
                if not 1 <= length <= 4096 or self.headers.get_content_type() != 'application/json':
                    raise ValueError()
                payload = json.loads(self.rfile.read(length))
                username, password = payload['username'], payload['password']
                if not isinstance(username, str) or not isinstance(password, str) or len(username) > 64 or len(password) > 256:
                    raise ValueError()
            except (ValueError, KeyError, TypeError):
                self.respond(400, b'{}')
                return
            token, error = auth.login(username, password, self.client_address[0])
            if error:
                self.respond(429 if error == 'limited' else 401, b'{"error":"Login failed"}')
            else:
                self.respond(200, b'{}', headers={'Set-Cookie': auth.cookie(token)})

        def do_GET(self):
            if self.path == '/theme.css':
                self.respond(200, (ROOT / 'web' / 'theme.css').read_bytes(), 'text/css; charset=utf-8')
                return
            if self.path == '/i18n.js':
                self.respond(200, (ROOT / 'web' / 'i18n.js').read_bytes(), 'text/javascript; charset=utf-8')
                return
            if self.path == '/login':
                self.respond(200, (ROOT / 'web' / 'login.html').read_bytes(), 'text/html; charset=utf-8')
                return
            user = auth.user(self.token()) if auth else None
            if auth and not user:
                self.respond(401 if self.path.startswith('/api/') else 303, b'{}', headers={} if self.path.startswith('/api/') else {'Location': '/login'})
                return
            if self.path == '/api/me':
                self.respond(200, json.dumps(user or {'username': 'test', 'role': 'viewer'}).encode())
                return
            if self.path == '/api/status':
                body = json.dumps(store.snapshot(config), ensure_ascii=False).encode('utf-8')
                mime = 'application/json; charset=utf-8'
            elif self.path == '/api/inventory':
                body = json.dumps(store.inventory(config), ensure_ascii=False).encode('utf-8')
                mime = 'application/json; charset=utf-8'
            elif self.path == '/api/sessions':
                imported = directory.load(ROOT / 'data' / 'directory-inventory.json')
                body = json.dumps(endpoints.load(ROOT / 'data' / 'endpoint-sessions', imported), ensure_ascii=False).encode('utf-8')
                mime = 'application/json; charset=utf-8'
            elif self.path == '/api/accounts':
                if auth and user['role'] != 'admin':
                    self.respond(403, b'{}')
                    return
                with store.lock:
                    rows = [dict(r) for r in store.db.execute('SELECT username,role,enabled FROM users')] if auth else []
                body = json.dumps(rows).encode()
                mime = 'application/json; charset=utf-8'
            elif self.path == '/api/setup':
                if not user or user['role'] != 'admin':
                    self.respond(403, b'{}')
                    return
                snapshot = store.snapshot(config)
                imported = directory.load(ROOT / 'data' / 'directory-inventory.json')
                computers = endpoints.load(ROOT / 'data' / 'endpoint-sessions', imported)['computers']
                body = json.dumps({'https': isinstance(self.connection, ssl.SSLSocket),
                                   'profiles': collector_settings.PROFILES,
                                   'access': network_settings.summary(ROOT),
                                   'sources': [{'name': d['name'], 'host': d.get('host'),
                                                'kind': d.get('kind'), 'status': d['metrics']['status'],
                                                'stale': d['metrics'].get('stale', True),
                                                'checked': d['metrics'].get('checked')}
                                               for d in snapshot['devices']],
                                   'directory': {'status': imported.get('status'), 'stale': imported.get('stale', True),
                                                 'domain': imported.get('domain'), 'users': len(imported.get('users', []))},
                                   'endpoints': {'reported': len(computers),
                                                 'current': sum(not c['stale'] and c['status'] == 'ok' for c in computers)}}, ensure_ascii=False).encode('utf-8')
                mime = 'application/json; charset=utf-8'
            elif self.path == '/api/agents':
                if user['role'] != 'admin':
                    self.respond(403, b'{}')
                    return
                body = json.dumps(registry.list(), ensure_ascii=False).encode('utf-8')
                mime = 'application/json; charset=utf-8'
            elif self.path in ('/app.js', '/live.js', '/dashboard.js', '/style.css'):
                body = (ROOT / 'web' / self.path[1:]).read_bytes()
                mime = 'text/javascript; charset=utf-8' if self.path.endswith('.js') else 'text/css; charset=utf-8'
            elif self.path == '/api/report.csv':
                data = store.snapshot(config)
                stream = io.StringIO(newline='')
                writer = csv.writer(stream)
                writer.writerow(['Cihaz', 'IP', 'Durum', 'Son kontrol (Unix UTC)', '24s başarılı kontrol %', '24s ölçüm sayısı'])
                def safe(value):
                    value = '' if value is None else str(value)
                    return "'" + value if value.lstrip().startswith(('=', '+', '-', '@')) else value
                for d in data['devices']:
                    writer.writerow([safe(v) for v in (d['name'], d['host'], 'stale' if d['stale'] else d['status'], d['checked'], d['availability_24h'], d['sample_count_24h'])])
                body = ('\ufeff' + stream.getvalue()).encode('utf-8')
                mime = 'text/csv; charset=utf-8'
            elif self.path.startswith('/api/history/'):
                device = self.path[len('/api/history/'):]
                agent_ids = {'agent-' + a['id'] for a in registry.list() if a['kind'] == 'endpoint'}
                if device not in {d['id'] for d in config['devices']} | agent_ids:
                    self.send_error(404)
                    return
                body = json.dumps(store.history(device), ensure_ascii=False).encode('utf-8')
                mime = 'application/json; charset=utf-8'
            elif self.path == '/api/discovery':
                path = ROOT / 'data' / 'discovery.json'
                try:
                    body = json.dumps(json.loads(path.read_text(encoding='utf-8')) if path.exists() else []).encode('utf-8')
                except (ValueError, OSError):
                    self.send_error(503)
                    return
                mime = 'application/json; charset=utf-8'
            elif self.path == '/api/discovery-status':
                path = ROOT / 'data' / 'discovery-status.local.json'
                try:
                    value = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {'status': 'disabled'}
                except (ValueError, OSError):
                    value = {'status': 'error'}
                body = json.dumps(value).encode('utf-8')
                mime = 'application/json; charset=utf-8'
            elif self.path == '/':
                body = (ROOT / 'web' / 'index.html').read_bytes()
                mime = 'text/html; charset=utf-8'
            else:
                self.send_error(404)
                return
            self.respond(200, body, mime)

        def setup(self):
            super().setup()
            self.connection.settimeout(15)

        def log_message(self, *args):
            pass
    return Handler


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', default=str(ROOT / 'config.local.json'))
    parser.add_argument('--port', type=int)
    parser.add_argument('--check-config', action='store_true')
    parser.add_argument('--bind')
    parser.add_argument('--tls-cert')
    parser.add_argument('--tls-key')
    args = parser.parse_args()
    if not args.check_config:
        network_settings.apply_pending(ROOT)
    network_path = ROOT / 'server.local.json'
    network = json.loads(network_path.read_text(encoding='utf-8-sig')) if network_path.exists() else {}
    args.bind = args.bind or network.get('bind', '127.0.0.1')
    args.port = args.port or network.get('port', 8765)
    for key in ('tls_cert', 'tls_key'):
        value = getattr(args, key) or network.get(key)
        if value:
            value = str(ROOT / value) if not Path(value).is_absolute() else value
        setattr(args, key, value)
    config = validate(json.loads(Path(args.config).read_text(encoding='utf-8-sig')))
    if args.check_config:
        print('Yapılandırma geçerli:', len(config['devices']), 'cihaz')
        return
    (ROOT / 'data').mkdir(exist_ok=True)
    store = Store(ROOT / 'data' / 'monitor.sqlite3')
    store.config_path = Path(args.config)
    if bool(args.tls_cert) != bool(args.tls_key):
        parser.error('TLS sertifika ve anahtar birlikte gerekli')
    if not ipaddress.ip_address(args.bind).is_loopback and not args.tls_cert:
        parser.error('Ağdan erişim için TLS sertifika ve anahtar gerekli')
    auth = authentication.Auth(store, secure=bool(args.tls_cert), public_origin=network.get('public_origin'))
    if not auth.count():
        print('İlk kullanıcıyı oluşturun: python users.py add --role admin')
        store.db.close()
        return
    secret_path = ROOT / 'data' / 'secure' / 'service-secrets.local.json'
    if secret_path.exists():
        os.environ.update(collector_settings.service_secrets.load(secret_path))
    stop = threading.Event()
    server = ThreadingHTTPServer((args.bind, args.port), handler(store, config, auth))
    if args.tls_cert:
        tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        tls.minimum_version = ssl.TLSVersion.TLSv1_2
        tls.load_cert_chain(args.tls_cert, args.tls_key)
        server.socket = tls.wrap_socket(server.socket, server_side=True)
    worker = threading.Thread(target=collect, args=(config, store, stop), daemon=True)
    worker.start()
    metric_worker = threading.Thread(target=collect_metrics, args=(config, store, stop), daemon=True)
    metric_worker.start()
    if config.get('discovery', {}).get('enabled'):
        import network_discovery
        threading.Thread(target=network_discovery.run, args=(ROOT, stop),
                         kwargs={'config': config, 'config_path': store.config_path, 'validate': validate}, daemon=True).start()
    print('CenterEK: ' + ('https://' if args.tls_cert else 'http://') + args.bind + ':' + str(args.port), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        server.server_close()
        worker.join()
        metric_worker.join()
        store.db.close()


if __name__ == '__main__':
    main()
