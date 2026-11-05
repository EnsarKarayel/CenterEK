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
        if d['id'] in ids or not d['id'] or not d['name']:
            raise ValueError('Cihaz kimliği benzersiz ve adı dolu olmalı')
        ids.add(d['id'])
        if d['method'] not in ('icmp', 'tcp'):
            raise ValueError('Yöntem icmp veya tcp olmalı')
        if d['method'] == 'tcp' and (type(d.get('port')) is not int or not 1 <= d['port'] <= 65535):
            raise ValueError('Geçersiz TCP portu')
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

    def snapshot(self, config):
        with self.lock:
            states = {r['id']: dict(r) for r in self.db.execute('SELECT * FROM state')}
            devices = []
            for d in config['devices']:
                row = dict(d)
                row.update(states.get(d['id'], {'status': 'unknown', 'checked': None}))
                row['stale'] = row['checked'] is None or time.time() - row['checked'] > config['interval'] * 2 + config['timeout'] + 2
                devices.append(row)
            incidents = [dict(r) for r in self.db.execute('SELECT * FROM incidents ORDER BY id DESC LIMIT 100')]
            return {'devices': devices, 'incidents': incidents, 'now': time.time(), 'interval': config['interval']}


def collect(config, store, stop):
    with ThreadPoolExecutor(max_workers=32) as pool:
        while not stop.is_set():
            started = time.monotonic()
            results = pool.map(lambda d: probe(d, config['timeout']), config['devices'])
            for d, result in zip(config['devices'], results):
                store.record(d['id'], *result, config['threshold'])
            stop.wait(max(0, config['interval'] - (time.monotonic() - started)))


def handler(store, config):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == '/api/status':
                body = json.dumps(store.snapshot(config), ensure_ascii=False).encode('utf-8')
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
    print('NetWatch: http://127.0.0.1:' + str(args.port), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        server.server_close()
        worker.join()
        store.db.close()


if __name__ == '__main__':
    main()
