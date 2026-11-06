"""Bounded automatic discovery on connected private Ethernet/Wi-Fi networks."""
from concurrent.futures import ThreadPoolExecutor
import ipaddress
import json
import os
from pathlib import Path
import re
import subprocess
import time
import copy
import device_settings


def select_networks(adapters, limit=1024):
    networks, skipped = [], []
    total = 0
    for row in adapters[:128]:
        try:
            address = ipaddress.IPv4Address(row['ip'])
            network = ipaddress.IPv4Network((row['ip'], row['mask']), strict=False)
            if not address.is_private or address.is_loopback or address.is_link_local or not row.get('gateway'):
                continue
            if row.get('type') not in ('Ethernet', 'Wireless80211') or re.search(r'virtual|hyper-v|vpn|\btap\b|\btun\b', str(row.get('description', '')), re.I):
                continue
            if any(network.subnet_of(previous) for previous in networks):
                continue
            contained = [previous for previous in networks if previous.subnet_of(network)]
            count = network.num_addresses if network.prefixlen >= 31 else network.num_addresses - 2
            updated = total - sum(n.num_addresses if n.prefixlen >= 31 else n.num_addresses - 2 for n in contained) + count
            if updated > limit:
                skipped.append({'network': str(network), 'reason': 'Address limit exceeded; select a narrower range.'})
                continue
            networks = [n for n in networks if n not in contained] + [network]
            total = updated
        except (ValueError, KeyError, TypeError):
            continue
    return networks, skipped


def write_json(path, value):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')
    os.replace(temporary, path)


def add_discovered(config, rows, path, validate):
    with device_settings.LOCK:
        updated = copy.deepcopy(config)
        known = {d['host'] for d in updated['devices']}
        identifiers = {d['id'] for d in updated['devices']}
        added = 0
        for row in rows:
            if len(updated['devices']) >= 1024:
                break
            address = str(ipaddress.IPv4Address(row['host']))
            parsed = ipaddress.IPv4Address(address)
            if not parsed.is_private or parsed.is_loopback or parsed.is_link_local:
                continue
            identifier = 'auto-' + address.replace('.', '-')
            if address in known or identifier in identifiers:
                continue
            ports = row.get('open_tcp_ports', [])
            device = {'id': identifier, 'name': address, 'host': address, 'kind': 'Diğer',
                      'method': 'icmp' if row.get('icmp') else 'tcp', 'discovered': True}
            if device['method'] == 'tcp':
                if not ports:
                    continue
                device['port'] = ports[0]
            updated['devices'].append(device)
            known.add(address);identifiers.add(identifier);added += 1
        if added:
            validate(updated)
            path = Path(path)
            if path.exists():
                path.with_name('config.backup.local.json').write_bytes(path.read_bytes())
            write_json(path, updated)
            config['devices'] = updated['devices']
        return added


def run(root, stop, inspect_host=None, config=None, config_path=None, validate=None):
    root = Path(root)
    if inspect_host is None:
        from discover import inspect as inspect_host
    data = root / 'data'
    data.mkdir(exist_ok=True)
    status_path = data / 'discovery-status.local.json'
    while not stop.is_set():
        status = {'status': 'detecting', 'started': time.time(), 'networks': [], 'tested': 0, 'total': 0, 'found': 0}
        try:
            write_json(status_path, status)
            output = data / 'interfaces.local.json'
            executable = str(Path(os.environ['WINDIR']) / 'System32/WindowsPowerShell/v1.0/powershell.exe')
            result = subprocess.run([executable, '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'RemoteSigned',
                                     '-File', str(root / 'Detect-Networks.ps1'), '-OutputFile', str(output)],
                                    capture_output=True, timeout=25, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            if result.returncode:
                raise RuntimeError('Network interface detection failed')
            adapters = json.loads(output.read_text(encoding='utf-8-sig'))
            networks, skipped = select_networks(adapters)
            hosts = list(dict.fromkeys(str(ip) for network in networks for ip in network.hosts()))
            status.update(status='scanning', networks=[str(n) for n in networks], total=len(hosts), skipped=skipped)
            write_json(status_path, status)
            rows = []
            def inspect(address):
                return None if stop.is_set() else inspect_host(address)
            with ThreadPoolExecutor(max_workers=24) as pool:
                for row in pool.map(inspect, hosts):
                    if stop.is_set():
                        break
                    status['tested'] += 1
                    if row:
                        rows.append(row)
                        status['found'] = len(rows)
                        write_json(data / 'discovery.json', rows)
                    if status['tested'] % 24 == 0:
                        write_json(status_path, status)
            if not stop.is_set():
                write_json(data / 'discovery.json', rows)
                if config is not None and config.get('discovery', {}).get('auto_add'):
                    status['added'] = add_discovered(config, rows, config_path, validate)
                status.update(status='complete', completed=time.time())
                write_json(status_path, status)
        except Exception:
            status.update(status='error', error='Network discovery could not complete; check local interfaces and permissions.')
            write_json(status_path, status)
        stop.wait(3600)
