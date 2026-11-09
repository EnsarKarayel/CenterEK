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
              'sessions': [], 'source': 'Kimliği doğrulanmış uç ajan',
              'address_source': data.get('address_source') if data.get('address_source') in ('Yerel ağ kartları', 'DNS çözümlemesi') else 'Bilinmiyor', 'resources': {}, 'interfaces': [],
              'error': 'Uç bilgisayar ölçüm hatası' if data['status'] == 'error' else None}
    platform=data.get('platform','unknown')
    if platform not in ('windows','linux','unknown'): raise ValueError('Invalid endpoint platform')
    result['platform']=platform
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
