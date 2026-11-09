"""Read-only office snapshots and scoped, credential-free cloud relay payloads."""
import datetime
import hashlib
import ipaddress
import json
import math
from pathlib import Path
import re
import sqlite3
import time

MAX_BYTES = 8 * 1024 * 1024


def networks(values):
    if not isinstance(values, list) or not 1 <= len(values) <= 8:
        raise ValueError('Office network scope is required')
    result = [ipaddress.ip_network(value, strict=True) for value in values]
    private = [ipaddress.ip_network(value) for value in ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16')]
    if any(net.version != 4 or not any(net.subnet_of(parent) for parent in private) for net in result) or sum(net.num_addresses for net in result) > 4096:
        raise ValueError('Use at most 4096 explicitly scoped private IPv4 addresses')
    return result


def in_scope(value, scope):
    try:
        address = ipaddress.ip_address(value)
        return any(address in net for net in scope)
    except (ValueError, TypeError):
        return False


def stamp(value):
    if type(value) in (int, float) and math.isfinite(value) and 0 <= value <= time.time() + 60:
        return value
    raise ValueError('Invalid source measurement timestamp')


def text(value, maximum=256):
    if value is None:
        return None
    if not isinstance(value, str) or len(value) > maximum:
        raise ValueError('Invalid inventory text')
    return value


def number(value, maximum=2**64):
    if value is None:
        return None
    if type(value) not in (float, int) or not math.isfinite(value) or not 0 <= value <= maximum:
        raise ValueError('Invalid measurement number')
    return value


def rows(value, maximum):
    if not isinstance(value, list) or len(value) > maximum or any(not isinstance(row, dict) for row in value):
        raise ValueError('Invalid or oversized inventory list')
    return value


def clean_metrics(metric, scope):
    if not isinstance(metric, dict) or metric.get('status') not in ('ok', 'error', 'unconfigured'):
        raise ValueError('Invalid metric state')
    result = {'status': metric['status'], 'error': None if metric['status'] == 'ok' else 'Office measurement unavailable', 'values': {}}
    values = metric.get('values', {})
    if not isinstance(values, dict):
        raise ValueError('Invalid metric values')
    clean = result['values']
    for key in ('cpu_percent', 'memory_percent', 'memory_total_gb', 'memory_used_gb', 'uptime_seconds', 'sessions'):
        if key in values:
            clean[key] = number(values[key], 100 if key.endswith('_percent') else 2**64)
    for key in ('hostname', 'model', 'version', 'health', 'protocol'):
        if key in values:
            clean[key] = text(values[key])
    for key in ('inventory_status',):
        if key in values:
            if values[key] not in ('ok', 'error', 'unknown'):
                raise ValueError('Invalid inventory status')
            clean[key] = values[key]
    if values.get('section_errors'):
        clean['section_errors'] = ['Office source reports incomplete measurements']
    clean['interfaces'] = []
    for interface in rows(values.get('interfaces', []), 256):
        row = {key: text(interface.get(key), 256) for key in ('name', 'alias')}
        for key in ('index', 'oper_status', 'admin_status', 'high_speed', 'speed', 'rx_bytes', 'tx_bytes', 'rx_errors', 'tx_errors', 'counter_discontinuity', 'rx_mbps', 'tx_mbps'):
            if key in interface:
                row[key] = number(interface[key])
        if 'link' in interface:
            if interface['link'] not in (True, False, None, 'up', 'down'):
                raise ValueError('Invalid link state')
            row['link'] = interface['link']
        clean['interfaces'].append(row)
    clean['datastores'] = []
    for datastore in rows(values.get('datastores', []), 128):
        total, free = number(datastore.get('capacity_gb')), number(datastore.get('free_gb'))
        if total is None or free is None or free > total or type(datastore.get('accessible')) is not bool:
            raise ValueError('Invalid datastore')
        clean['datastores'].append({'name': text(datastore.get('name')), 'capacity_gb': total, 'free_gb': free, 'accessible': datastore['accessible']})
    clean['network_adapters'] = []
    for nic in rows(values.get('network_adapters', []), 128):
        mac = nic.get('mac')
        if not isinstance(mac, str) or not re.fullmatch(r'(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}', mac):
            raise ValueError('Invalid adapter MAC')
        clean['network_adapters'].append({'name': text(nic.get('name')), 'mac': mac.lower()})
    clean['clients'] = []
    for client in rows(values.get('clients', []), 4000):
        if not in_scope(client.get('ip'), scope):
            continue
        row = {key: text(client.get(key), 256) for key in ('ip', 'mac', 'hostname', 'vendor', 'type', 'os', 'interface')}
        row.update(online=client.get('online') if type(client.get('online')) is bool else None,
                   last_seen=number(client.get('last_seen')), source='FortiGate via office relay')
        clean['clients'].append(row)
    clean['inventory_limit'] = 4000
    return result


def validate(data, enrollment, scope_values, *, directory_domain=None, directory_server=None):
    """Allowlist every transmitted field. Never trust source-supplied cloud IDs."""
    import agents
    scope = networks(scope_values)
    if not isinstance(data, dict) or data.get('schema') != 1 or data.get('computer') != enrollment['computer']:
        raise ValueError('Office relay identity mismatch')
    result = {'schema': 1, 'computer': data['computer'], 'collected_at': data['collected_at'], 'devices': [], 'endpoints': [], 'incidents': []}
    seen = set()
    for item in rows(data.get('devices', []), 1024):
        original = item.get('id')
        if not isinstance(original, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', original) or original in seen:
            raise ValueError('Invalid/duplicate office device ID')
        seen.add(original)
        if not in_scope(item.get('host'), scope) or item.get('method') not in ('icmp', 'tcp'):
            raise ValueError('Office device outside enrollment scope')
        port = item.get('port')
        if item['method'] == 'tcp' and (type(port) is not int or not 1 <= port <= 65535):
            raise ValueError('Invalid office service port')
        cloud_id = 'site-' + enrollment['id'] + '-' + hashlib.sha256(original.encode()).hexdigest()[:16]
        state = item.get('state', {})
        if state.get('status') not in ('up', 'down', 'unknown', 'suspect'):
            raise ValueError('Invalid office availability state')
        checked = None if state.get('checked') is None else stamp(state['checked'])
        failures = state.get('failures', 0)
        if type(failures) is not int or not 0 <= failures <= 1000000:
            raise ValueError('Invalid availability failures')
        row = {'id': cloud_id, 'source_id': original, 'name': text(item.get('name')) or original,
               'host': str(ipaddress.ip_address(item['host'])), 'kind': text(item.get('kind'), 80) or 'Device',
               'method': item['method'], 'port': port, 'site_id': enrollment['id'],
               'site': enrollment['computer'], 'depends_on': [],
               'status': 'unknown' if state['status'] == 'suspect' else state['status'], 'checked': checked, 'failures': failures,
               'latency': number(state.get('latency'), 60000),
               'error': 'Office availability check failed' if state['status'] == 'down' else None,
               'availability_24h': number(item.get('availability_24h'), 100),
               'sample_count_24h': int(number(item.get('sample_count_24h', 0), 1000000)),
               'metrics': clean_metrics(item.get('metrics', {'status': 'unconfigured', 'values': {}}), scope)}
        row['metrics']['checked'] = None if item.get('metrics', {}).get('checked') is None else stamp(item['metrics']['checked'])
        kind = item.get('collector_type')
        if kind is not None and kind not in ('esxi', 'fortigate', 'snmp'):
            raise ValueError('Invalid office collector type')
        row['collector_type'] = kind
        result['devices'].append(row)
    by_source = {row['source_id']: row['id'] for row in result['devices']}
    for incident in rows(data.get('incidents', []), 1000):
        if incident.get('device') not in by_source:
            continue
        original = incident.get('id')
        if type(original) is not int or not 0 < original < 2**63:
            raise ValueError('Invalid office incident ID')
        started, confirmed = stamp(incident.get('started')), stamp(incident.get('confirmed'))
        ended = None if incident.get('ended') is None else stamp(incident['ended'])
        if started > confirmed or (ended is not None and ended < confirmed):
            raise ValueError('Invalid incident timeline')
        result['incidents'].append({'id': 'site-' + enrollment['id'] + '-' + str(original),
            'device': by_source[incident['device']], 'started': started, 'confirmed': confirmed, 'ended': ended})
    if data.get('directory') is not None:
        if not directory_domain or not directory_server:
            raise ValueError('Directory transfer is not enabled for this office')
        directory = agents.directory_report(data['directory'], agents.host(directory_server))
        stamp(agents.timestamp(directory['collected_at']))
        if directory['domain'].lower() != directory_domain.lower():
            raise ValueError('Directory domain outside enrollment scope')
        directory['dns'] = [row for row in directory['dns'] if in_scope(row.get('ip'), scope)]
        directory['leases'] = [row for row in directory['leases'] if in_scope(row.get('ip'), scope)]
        if directory.get('errors'):
            directory['errors'] = ['Office directory source reports incomplete data']
        result['directory'] = directory
    for item in rows(data.get('endpoints', []), 2000):
        clean = agents.endpoint_report(item, agents.host(item.get('computer')))
        stamp(agents.timestamp(clean['collected_at']))
        clean['ips'] = [ip for ip in clean['ips'] if in_scope(ip, scope)]
        if not clean['ips']:
            continue
        clean['interfaces'] = [nic for nic in clean['interfaces'] if nic['ip'] in clean['ips']]
        if clean.get('primary_ip') not in clean['ips']:
            clean.pop('primary_ip', None)
        clean['agent_id'] = 'site-' + enrollment['id'] + '-' + hashlib.sha256(clean['computer'].encode()).hexdigest()[:16]
        clean['source'] = 'Office relay; source measurement timestamp preserved'
        clean['site_id'] = enrollment['id']
        result['endpoints'].append(clean)
    return result


def load_devices(root, now=None):
    result = []
    if not root:
        return result
    now = time.time() if now is None else now
    for path in sorted((Path(root) / 'data/sites').glob('*.json'))[:50]:
        try:
            if path.is_symlink() or path.stat().st_size > MAX_BYTES:
                continue
            data = json.loads(path.read_text(encoding='utf-8'))
            relay_stale = now - data['received'] > 180
            for row in data['devices']:
                row['stale'] = relay_stale or row['checked'] is None or now - row['checked'] > 90
                metric = row['metrics']
                metric['stale'] = relay_stale or metric['checked'] is None or now - metric['checked'] > 180
                # Clients are returned only by the inventory API, not duplicated in status.
                metric['values'].pop('clients', None)
                result.append(row)
        except (OSError, ValueError, KeyError, TypeError):
            continue
    return result


def load_incidents(root):
    result = []
    if root:
        for path in sorted((Path(root) / 'data/sites').glob('*.json'))[:50]:
            try:
                if not path.is_symlink() and path.stat().st_size <= MAX_BYTES:
                    result.extend(json.loads(path.read_text(encoding='utf-8')).get('incidents', []))
            except (OSError, ValueError, TypeError):
                continue
    return sorted(result, key=lambda row: row['started'], reverse=True)[:100]


def snapshot(root, computer):
    """Read the existing installation, never its accounts/secret tables or API keys."""
    root = Path(root).resolve()
    config = json.loads((root / 'config.local.json').read_text(encoding='utf-8-sig'))
    database = root / 'data/monitor.sqlite3'
    connection = sqlite3.connect(database.as_uri() + '?mode=ro', uri=True, timeout=5)
    connection.row_factory = sqlite3.Row
    result = {'schema': 1, 'computer': computer,
              'collected_at': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'devices': [], 'endpoints': [], 'incidents': []}
    try:
        connection.execute('BEGIN')
        for device in config['devices'][:1024]:
            row = {key: device.get(key) for key in ('id', 'name', 'host', 'kind', 'method', 'port')}
            row['collector_type'] = device.get('collector', {}).get('type')
            state = connection.execute('SELECT status,checked,failures,latency FROM state WHERE id=?', (device['id'],)).fetchone()
            row['state'] = dict(state) if state else {'status': 'unknown', 'checked': None}
            metric = connection.execute('SELECT checked,payload FROM metrics WHERE device=?', (device['id'],)).fetchone()
            row['metrics'] = dict(json.loads(metric['payload']), checked=metric['checked']) if metric else {'status': 'unconfigured', 'values': {}}
            counts = connection.execute('SELECT COUNT(*),SUM(ok) FROM samples WHERE device=? AND checked>=?', (device['id'], time.time()-86400)).fetchone()
            row.update(availability_24h=round(100*counts[1]/counts[0], 2) if counts[0] else None, sample_count_24h=counts[0])
            result['devices'].append(row)
        result['incidents'] = [dict(row) for row in connection.execute('SELECT id,device,started,confirmed,ended FROM incidents ORDER BY id DESC LIMIT 100')]
    finally:
        connection.close()
    directory = root / 'data/directory-inventory.json'
    if directory.is_file() and not directory.is_symlink() and directory.stat().st_size <= 5*1024*1024:
        result['directory'] = json.loads(directory.read_text(encoding='utf-8-sig'))
    for path in sorted((root / 'data/endpoint-sessions').glob('*.json'))[:2000]:
        if path.is_file() and not path.is_symlink() and path.stat().st_size <= 256*1024:
            result['endpoints'].append(json.loads(path.read_text(encoding='utf-8-sig')))
    return result
