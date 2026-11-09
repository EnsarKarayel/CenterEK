"""Read local collector reports and match AD users by domain and account name."""
import datetime
import json


def load(folder, directory):
    rows, computers = [], []
    domain = str(directory.get('domain') or '').lower()
    users = {str(u.get('username') or '').lower(): u for u in directory.get('users', [])}
    domain_names = {domain, str(directory.get('netbios') or '').lower()} - {''}
    for path in sorted(folder.glob('*.json'))[:2000]:
        try:
            if path.stat().st_size > 1024 * 1024:
                raise ValueError()
            data = json.loads(path.read_text(encoding='utf-8-sig'))
            stamp = datetime.datetime.fromisoformat(data['collected_at'].replace('Z', '+00:00'))
            age = (datetime.datetime.now(datetime.timezone.utc) - stamp).total_seconds()
            if data.get('authenticated') and data.get('received_at'):
                received = datetime.datetime.fromisoformat(data['received_at'].replace('Z', '+00:00'))
                age = max(age, (datetime.datetime.now(datetime.timezone.utc) - received).total_seconds())
            if data.get('schema') != 1 or age < -300 or not isinstance(data.get('sessions'), list):
                raise ValueError()
            if not isinstance(data.get('ips', []), list) or not all(isinstance(ip, str) for ip in data.get('ips', [])):
                raise ValueError()
            interval=data.get('interval_seconds',60)
            interval=interval if type(interval) is int and 15 <= interval <= 300 else 60
            stale = age > max(150, interval*3)
            computers.append({'computer': data['computer'], 'ips': data.get('ips', []),
                              'status': data['status'], 'error': data.get('error'),
                              'checked': data['collected_at'], 'stale': stale,
                              'resources': data.get('resources', {}), 'interfaces': data.get('interfaces', []),
                              'volumes': data.get('volumes', []),
                              'primary_ip': data.get('primary_ip'), 'authenticated': data.get('authenticated', False),
                              'agent_id': data.get('agent_id'),
                              'interval_seconds': interval,
                              'received_at': data.get('received_at'), 'address_source': data.get('address_source', 'DNS çözümlemesi')})
            for session in (data['sessions'][:100] if data['status'] == 'ok' else []):
                account = str(session.get('username') or '')
                session_domain = str(session.get('domain') or '')
                user = users.get(account.lower(), {}) if session_domain.lower() in domain_names else {}
                state = session.get('state')
                rows.append({'username': account, 'domain': session_domain, 'display_name': user.get('display_name') or '',
                             'ad_match': bool(user), 'computer': data['computer'], 'ips': data.get('ips', []),
                             'session_id': session.get('id'), 'state': 'active' if state == 0 else 'disconnected' if state == 4 else 'other',
                             'checked': data['collected_at'], 'stale': stale, 'source': 'Windows WTS',
                             'address_source': data.get('address_source', 'Bilinmiyor'), 'primary_ip': data.get('primary_ip'),
                             'authenticated': data.get('authenticated', False), 'ad_stale': directory.get('stale', True)})
        except (ValueError, TypeError, KeyError, OSError, AttributeError):
            computers.append({'computer': path.stem, 'status': 'error', 'stale': True, 'error': 'Geçersiz oturum raporu'})
    return {'sessions': rows, 'computers': computers,
            'inventory': computer_inventory(directory, computers, rows)}


def computer_inventory(directory, reports, sessions):
    """AD inventory is visible without an agent; users require fresh host reports."""
    def short(value): return str(value or '').rstrip('.').split('.')[0].upper()
    domain=str(directory.get('domain') or '').lower().rstrip('.')
    ad=directory.get('computers',[])
    counts={}
    for item in ad:
        key=short(item.get('name') or item.get('fqdn'));counts[key]=counts.get(key,0)+1
    dns={}
    for item in directory.get('clients',[]):
        name=str(item.get('hostname') or '').lower().rstrip('.')
        if item.get('source')=='DNS kaydı' and item.get('ip'):dns.setdefault(name,set()).add(item['ip'])
    result=[];used=set()
    for item in ad:
        name=item.get('name') or short(item.get('fqdn'));key=short(name)
        fqdn=str(item.get('fqdn') or (key+'.'+domain if domain else key)).lower().rstrip('.')
        matches=[r for r in reports if short(r.get('computer'))==key and ('.' not in r.get('computer','') or str(r['computer']).lower().rstrip('.')==fqdn)] if counts.get(key)==1 else []
        current=[r for r in matches if not r.get('stale') and r.get('status')=='ok']
        report=current[0] if len(current)==1 else None
        if report:used.add(id(report))
        active=[s for s in sessions if report and s['computer']==report['computer'] and not s['stale'] and s['state']=='active']
        result.append({'computer':name,'fqdn':fqdn,'os':item.get('os'),'ad_enabled':item.get('enabled'),
            'in_ad':True,'ad_stale':directory.get('stale',True),'dns_ips':sorted(dns.get(fqdn,set())),
            'ips':report.get('ips',[]) if report else sorted(dns.get(fqdn,set())),
            'address_source':'Yerel ağ kartları' if report else 'DNS kaydı',
            'users':[{'username':s['username'],'domain':s['domain'],'ad_match':s.get('ad_match',False)} for s in active],
            'report_status':'fresh' if report else 'ambiguous' if len(current)>1 else 'stale' if matches else 'missing',
            'checked':report.get('checked') if report else None})
    ad_names=set(counts)
    for report in reports:
        if id(report) in used or short(report.get('computer')) in ad_names:continue
        active=[s for s in sessions if s['computer']==report['computer'] and not s['stale'] and s['state']=='active']
        result.append({'computer':report['computer'],'fqdn':None,'os':None,'ad_enabled':None,'in_ad':False,
            'dns_ips':[],'ips':report.get('ips',[]),'address_source':report.get('address_source'),
            'users':[{'username':s['username'],'domain':s['domain'],'ad_match':s.get('ad_match',False)} for s in active],
            'report_status':'fresh' if not report['stale'] and report['status']=='ok' else 'stale','checked':report.get('checked')})
    return result
