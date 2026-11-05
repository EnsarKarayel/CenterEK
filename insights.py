"""Explain observations without claiming an unmeasured root cause."""
def alerts(devices):
    by_id = {d['id']: d for d in devices}
    result = []
    for d in devices:
        def add(severity, title, explanation, action):
            result.append({'device': d['id'], 'name': d['name'], 'severity': severity,
                           'title': title, 'explanation': explanation, 'action': action})
        if d['stale']:
            add('warning', 'Güncel erişim ölçümü yok', 'Cihazın durumu doğrulanamıyor.', 'İzleme uygulamasını ve son kontrol zamanını kontrol edin.')
        elif d['status'] == 'down':
            parents = [by_id[p]['name'] for p in d.get('depends_on', []) if p in by_id
                       and by_id[p]['status'] == 'down' and not by_id[p]['stale']]
            add('critical', 'Cihaza erişilemiyor',
                'Tanımlı üst bağlantıda da erişim sorunu var: ' + ', '.join(parents) if parents else 'Art arda erişim kontrolleri başarısız oldu; güç veya ağ arızası kesinleştirilmedi.',
                'Önce tanımlı üst cihazı kontrol edin.' if parents else 'Switch portunu, cihaz gücünü ve yönetim servisini kontrol edin.')
        elif d['status'] == 'suspect':
            add('warning', 'Erişim doğrulanıyor', 'Başarısız kontroller kesinti eşiğine henüz ulaşmadı.', 'Sonraki kontrolü ve bağlantı durumunu inceleyin.')
        metrics = d['metrics']
        if metrics['status'] == 'error' or (metrics['status'] == 'ok' and metrics['stale']):
            add('warning', 'Kaynak ölçümü alınamıyor', metrics.get('error') or 'Ölçüm güncel değil.', 'Okuma hesabını, sertifikayı ve cihaz API/SNMP erişimini kontrol edin.')
        if metrics['status'] == 'ok' and not metrics['stale']:
            for key, label in [('cpu_percent', 'CPU'), ('memory_percent', 'RAM')]:
                value = metrics['values'].get(key)
                if isinstance(value, (int, float)) and value >= 90:
                    add('warning', label + ' kullanımı yüksek', 'Son ölçüm: %' + str(value) + '. Tek ölçüm gözlemidir.', 'Geçmiş grafiğinde sürekliliği kontrol edin.')
    return sorted(result, key=lambda x: x['severity'] != 'critical')
