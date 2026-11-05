"""Read-only collectors. Credentials stay in environment variables, never in API output."""
import json
import asyncio
import os
import ssl
from urllib.request import Request, build_opener, HTTPSHandler, ProxyHandler, HTTPRedirectHandler


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def context(settings):
    return ssl.create_default_context(cafile=settings.get('ca_file'))


def secret(settings, name):
    value = os.environ.get(settings.get(name + '_env', ''), '')
    if not value:
        raise ValueError('Eksik ortam değişkeni: ' + name)
    return value


def esxi_summary(summary):
    hw, stats = summary.hardware, summary.quickStats
    total_mb = hw.memorySize / (1024 * 1024)
    capacity_mhz = hw.cpuMhz * hw.numCpuCores
    used_mb = getattr(stats, 'overallMemoryUsage', None)
    cpu = getattr(stats, 'overallCpuUsage', None)
    return {
        'cpu_percent': round(cpu / capacity_mhz * 100, 2) if cpu is not None and capacity_mhz else None,
        'memory_percent': round(used_mb / total_mb * 100, 2) if used_mb is not None and total_mb else None,
        'memory_used_gb': round(used_mb / 1024, 2) if used_mb is not None else None,
        'memory_total_gb': round(total_mb / 1024, 2),
        'uptime_seconds': getattr(stats, 'uptime', None),
        'model': hw.model,
        'health': str(summary.overallStatus),
    }


def esxi(device, settings):
    # Use explicit sessions and an API baseline supported by ESXi 6.7 and 8.0.
    from pyVim.connect import Connect, Disconnect
    from pyVmomi import vim
    session = Connect(host=device['host'], port=settings.get('port', 443),
                      user=secret(settings, 'username'), pwd=secret(settings, 'password'),
                      version='vim.version.version10', sslContext=context(settings),
                      httpConnectionTimeout=8)
    view = None
    try:
        content = session.RetrieveContent()
        view = content.viewManager.CreateContainerView(content.rootFolder, [vim.HostSystem], True)
        hosts = list(view.view)
        if len(hosts) != 1:
            raise ValueError('Doğrudan ESXi bağlantısında tek host bekleniyor')
        host = hosts[0]
        values = esxi_summary(host.summary)
        values['datastores'] = [
            {'name': ds.name, 'capacity_gb': round(ds.summary.capacity / 1024**3, 2),
             'free_gb': round(ds.summary.freeSpace / 1024**3, 2),
             'accessible': ds.summary.accessible}
            for ds in host.datastore]
        return values
    finally:
        try:
            if view:
                view.Destroy()
        finally:
            Disconnect(session)


def fortigate(device, settings):
    token = secret(settings, 'token')
    host = device['host']
    host = '[' + host + ']' if ':' in host else host
    base = 'https://' + host + ':' + str(settings.get('port', 4443))
    opener = build_opener(ProxyHandler({}), HTTPSHandler(context=context(settings)), NoRedirect())

    def get(path):
        req = Request(base + '/api/v2/monitor/system/' + path,
                      headers={'Authorization': 'Bearer ' + token})
        with opener.open(req, timeout=8) as response:
            raw = response.read(2 * 1024 * 1024 + 1)
        if len(raw) > 2 * 1024 * 1024:
            raise ValueError('API yanıtı çok büyük')
        data = json.loads(raw)
        if data.get('status') != 'success':
            raise ValueError('FortiGate API başarısız yanıt verdi')
        return data.get('results', {})

    status = get('status')
    result = {'model': status.get('model'), 'version': status.get('version'),
              'hostname': status.get('hostname'), 'interfaces': []}
    # Interface response fields differ by FortiOS; only known numeric counters
    # are interpreted, missing values stay null.
    interfaces = get('interface')
    entries = interfaces.items() if isinstance(interfaces, dict) else ((x.get('name', '?'), x) for x in interfaces)
    for name, value in entries:
        if not isinstance(value, dict):
            continue
        result['interfaces'].append({'name': name, 'link': value.get('link'),
                                     'rx_bytes': value.get('rx_bytes'), 'tx_bytes': value.get('tx_bytes'),
                                     'speed': value.get('speed')})
    return result


async def snmp_async(device, settings):
    from pysnmp.hlapi.v3arch.asyncio import (SnmpEngine, CommunityData, UdpTransportTarget,
                                            ContextData, ObjectType, ObjectIdentity, get_cmd, walk_cmd)
    engine = SnmpEngine()
    try:
        auth = CommunityData(secret(settings, 'community'), mpModel=1)
        target = await UdpTransportTarget.create((device['host'], settings.get('port', 161)), timeout=2, retries=0)

        async def walk(oid):
            result = {}
            async for err, status, index, binds in walk_cmd(
                    engine, auth, target, ContextData(), ObjectType(ObjectIdentity(oid)),
                    lexicographicMode=False, maxRows=128):
                if err or status:
                    raise RuntimeError('SNMP sorgusu başarısız')
                for key, value in binds:
                    try:
                        result[str(key).split('.')[-1]] = int(value)
                    except (ValueError, TypeError):
                        result[str(key).split('.')[-1]] = value.prettyPrint()
            return result

        err, status, _, binds = await get_cmd(engine, auth, target, ContextData(),
                                             ObjectType(ObjectIdentity('1.3.6.1.2.1.1.5.0')))
        if err or status:
            raise RuntimeError('SNMP erişimi başarısız')
        result = {'hostname': binds[0][1].prettyPrint(), 'interfaces': [], 'protocol': 'SNMPv2c'}
        roots = {'name': '1.3.6.1.2.1.2.2.1.2', 'oper_status': '1.3.6.1.2.1.2.2.1.8',
                 'speed': '1.3.6.1.2.1.2.2.1.5', 'rx_bytes': '1.3.6.1.2.1.31.1.1.1.6',
                 'tx_bytes': '1.3.6.1.2.1.31.1.1.1.10', 'rx_errors': '1.3.6.1.2.1.2.2.1.14',
                 'tx_errors': '1.3.6.1.2.1.2.2.1.20', 'counter_discontinuity': '1.3.6.1.2.1.31.1.1.1.19'}
        tables = dict(zip(roots, await asyncio.gather(*(walk(oid) for oid in roots.values()))))
        for index, name in tables['name'].items():
            row = {'index': index, 'name': str(name)}
            row.update({key: table.get(index) for key, table in tables.items() if key != 'name'})
            result['interfaces'].append(row)
        return result
    finally:
        engine.close_dispatcher()


def snmp(device, settings):
    async def bounded():
        return await asyncio.wait_for(snmp_async(device, settings), timeout=40)
    return asyncio.run(bounded())


def read(device):
    settings = device.get('collector')
    if not settings:
        return {'status': 'unconfigured', 'error': 'Ölçüm bağlantısı yapılandırılmadı', 'values': {}}
    try:
        kind = settings['type']
        values = {'esxi': esxi, 'fortigate': fortigate, 'snmp': snmp}[kind](device, settings)
        return {'status': 'ok', 'error': None, 'values': values}
    except Exception as exc:
        # Never expose exception messages: vendor libraries may include secrets.
        return {'status': 'error', 'error': 'Ölçüm alınamadı: ' + type(exc).__name__, 'values': {}}
