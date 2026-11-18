"""Plan workstation rollout from AD; create individual credentials only with --apply."""
import argparse
import csv
import datetime
import json
from pathlib import Path
import re
import sys


def select_computers(snapshot):
    domain = str(snapshot.get('domain', '')).lower()
    if not re.fullmatch(r'[a-z0-9-]+(?:\.[a-z0-9-]+)+', domain):
        raise ValueError('AD domain missing or invalid')
    rows = snapshot.get('computers')
    if not isinstance(rows, list) or len(rows) > 20000:
        raise ValueError('Invalid AD computer inventory')
    result = []
    seen = set()
    for row in rows:
        name = str(row.get('name', '')).upper()
        if not re.fullmatch(r'[A-Z0-9][A-Z0-9-]{0,14}', name):
            continue
        if name in seen:
            raise ValueError('Duplicate AD computer: ' + name)
        seen.add(name)
        os_name = str(row.get('os', ''))
        fqdn = str(row.get('fqdn', '')).lower().rstrip('.')
        if row.get('enabled') is not True or not re.match(r'^Windows (?:8|10|11)(?:\b|\.)', os_name):
            continue
        # Unknown OS and all servers/DCs are deliberately outside this wave.
        if 'server' in os_name.lower() or fqdn != name.lower() + '.' + domain:
            continue
        result.append({'computer': name, 'fqdn': fqdn, 'os': os_name})
    return sorted(result, key=lambda row: row['computer'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('C:/CenterEK'))
    parser.add_argument('--inventory', type=Path)
    parser.add_argument('--url', default='https://192.168.1.15:8765')
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    assets = Path(__file__).resolve().parent
    inventory = args.inventory or args.root/'data/directory-inventory.json'
    if inventory.stat().st_size > 20 * 1024 * 1024:
        raise ValueError('Inventory too large')
    snapshot = json.loads(inventory.read_text(encoding='utf-8-sig'))
    stamp = datetime.datetime.fromisoformat(snapshot['collected_at'].replace('Z', '+00:00'))
    age = (datetime.datetime.now(datetime.timezone.utc) - stamp).total_seconds()
    if not 0 <= age <= 86400:
        raise ValueError('Refresh the AD inventory first (maximum age 24 hours)')
    rows = select_computers(snapshot)
    if args.apply:
        from office_setup import endpoint_package
        sys.path.insert(0, str(args.root.resolve()))
        import agents
        import monitor
        from file_security import restrict
        store = monitor.Store(args.root/'data/monitor.sqlite3')
        try:
            existing = {row['computer'].upper() for row in agents.Registry(store, args.root).list()
                        if row['kind'] == 'endpoint'}
        finally:
            store.db.close()
        for row in rows:
            name = row['computer']
            if name in existing:
                row['action'] = 'EXISTING_REGISTRATION_PRESERVED'
                continue
            endpoint_package(args.root, assets, name, args.url)
            existing.add(name)
            row['action'] = 'PACKAGE_CREATED'
        manifest = assets/'rollout.local.json'
        with manifest.open('w', encoding='utf-8') as stream:
            restrict(manifest)
            json.dump({'schema': 1, 'domain': snapshot['domain'], 'computers': rows}, stream, indent=2)
    else:
        for row in rows:
            row['action'] = 'PLAN_ONLY'
    output = assets/'rollout-plan.csv'
    with output.open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=['computer', 'fqdn', 'os', 'action'])
        writer.writeheader()
        writer.writerows(rows)
    print('WORKSTATIONS=' + str(len(rows)))
    print('PLAN=' + str(output))
    print('PACKAGES_READY' if args.apply else 'PLAN_ONLY: no registrations or AD changes')


if __name__ == '__main__':
    main()
