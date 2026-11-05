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
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = Path(__file__).resolve().parent


def validate(config):
    for key, minimum, maximum in [('interval', 5, 3600), ('threshold', 1, 20), ('timeout', 1, 10)]:
        if type(config.get(key)) is not int or not minimum <= config[key] <= maximum:
            raise ValueError('Geçersiz ayar: ' + key)
    devices = config.get('devices', [])
    if not 1 <= len(devices) <= 256:
        raise ValueError('1-256 cihaz gerekli')
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
            self.db.execute('INSERT INTO metric_samples VALUES (?,?,?)', (device, now, payload))

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
                row = {key: d.get(key) for key in ('id', 'name', 'host', 'kind', 'method', 'port')}
                row['depends_on'] = d.get('depends_on', [])
                row.update(states.get(d['id'], {'status': 'unknown', 'checked': None}))
                row['stale'] = row['checked'] is None or time.time() - row['checked'] > config['interval'] * 2 + config['timeout'] + 2
                metric = self.db.execute('SELECT * FROM metrics WHERE device=?', (d['id'],)).fetchone()
                row['metrics'] = ({'checked': metric['checked'], **json.loads(metric['payload'])} if metric else
                                  {'status': 'unconfigured', 'error': 'Ölçüm bağlantısı yapılandırılmadı', 'values': {}, 'checked': None})
                row['metrics']['stale'] = not metric or time.time() - metric['checked'] > 180
                counts = self.db.execute('SELECT COUNT(*),SUM(ok) FROM samples WHERE device=? AND checked>=?',
                                         (d['id'], time.time() - 86400)).fetchone()
                row['availability_24h'] = round(100 * counts[1] / counts[0], 2) if counts[0] else None
                row['sample_count_24h'] = counts[0]
                devices.append(row)
            incidents = [dict(r) for r in self.db.execute('SELECT * FROM incidents ORDER BY id DESC LIMIT 100')]
            return {'devices': devices, 'incidents': incidents, 'alerts': insights.alerts(devices),
                    'now': time.time(), 'interval': config['interval'], 'version': '0.2.0'}


def collect(config, store, stop):
    with ThreadPoolExecutor(max_workers=32) as pool:
        while not stop.is_set():
            started = time.monotonic()
            results = pool.map(lambda d: probe(d, config['timeout']), config['devices'])
            for d, result in zip(config['devices'], results):
                store.record(d['id'], *result, config['threshold'])
            store.prune()
            stop.wait(max(0, config['interval'] - (time.monotonic() - started)))


def collect_metrics(config, store, stop):
    with ThreadPoolExecutor(max_workers=4) as pool:
        while not stop.is_set():
            for device, result in zip(config['devices'], pool.map(connectors.read, config['devices'])):
                store.record_metrics(device['id'], result)
            stop.wait(60)


def handler(store, config):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == '/api/status':
                body = json.dumps(store.snapshot(config), ensure_ascii=False).encode('utf-8')
                mime = 'application/json; charset=utf-8'
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
                if device not in {d['id'] for d in config['devices']}:
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
            elif self.path == '/':
                body = (ROOT / 'web' / 'index.html').read_bytes()
                mime = 'text/html; charset=utf-8'
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header('Content-Type', mime)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; frame-ancestors 'none'; base-uri 'none'")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass
    return Handler


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', default=str(ROOT / 'config.local.json'))
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--check-config', action='store_true')
    args = parser.parse_args()
    config = validate(json.loads(Path(args.config).read_text(encoding='utf-8-sig')))
    if args.check_config:
        print('Yapılandırma geçerli:', len(config['devices']), 'cihaz')
        return
    (ROOT / 'data').mkdir(exist_ok=True)
    store = Store(ROOT / 'data' / 'monitor.sqlite3')
    stop = threading.Event()
    server = ThreadingHTTPServer(('127.0.0.1', args.port), handler(store, config))
    worker = threading.Thread(target=collect, args=(config, store, stop), daemon=True)
    worker.start()
    metric_worker = threading.Thread(target=collect_metrics, args=(config, store, stop), daemon=True)
    metric_worker.start()
    print('NetWatch: http://127.0.0.1:' + str(args.port), flush=True)
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
