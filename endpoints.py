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
            stale = age > 150
            computers.append({'computer': data['computer'], 'ips': data.get('ips', []),
                              'status': data['status'], 'error': data.get('error'),
                              'checked': data['collected_at'], 'stale': stale,
                              'resources': data.get('resources', {}), 'interfaces': data.get('interfaces', []),
                              'primary_ip': data.get('primary_ip'), 'authenticated': data.get('authenticated', False),
                              'agent_id': data.get('agent_id'),
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
    return {'sessions': rows, 'computers': computers}
