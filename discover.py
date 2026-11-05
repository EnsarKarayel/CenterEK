"""Explicit, bounded inventory discovery. Does not edit the active config."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import ipaddress
import json
from pathlib import Path
from monitor import probe


def addresses(start, end):
    first, last = ipaddress.IPv4Address(start), ipaddress.IPv4Address(end)
    if int(last) < int(first) or int(last) - int(first) >= 1024:
        raise ValueError('Bir taramada en fazla 1024 adres kullanılabilir')
    result = [ipaddress.IPv4Address(n) for n in range(int(first), int(last) + 1)]
    if not all(ip.is_private and not ip.is_loopback and not ip.is_link_local for ip in result):
        raise ValueError('Yalnızca yerel özel ağ adresleri kullanılabilir')
    return [str(ip) for ip in result]


def inspect(host):
    ports = []
    icmp = probe({'host': host, 'method': 'icmp'}, 1)[0]
    for port in (22, 80, 443, 445, 3389, 4443):
        if probe({'host': host, 'method': 'tcp', 'port': port}, 1)[0]:
            ports.append(port)
    if not icmp and not ports:
        return None
    # Port observations are evidence, never a manufacturer/OS classification.
    return {'host': host, 'icmp': icmp, 'open_tcp_ports': ports}


def main():
    parser = argparse.ArgumentParser(description='Belirtilen özel ağ aralığında ICMP ve 6 TCP servisi keşfi')
    parser.add_argument('--start', required=True)
    parser.add_argument('--end', required=True)
    parser.add_argument('--output', default='data/discovery.json')
    args = parser.parse_args()
    hosts = addresses(args.start, args.end)
    print(len(hosts), 'adres kontrol ediliyor; birkaç dakika sürebilir.', flush=True)
    with ThreadPoolExecutor(max_workers=24) as pool:
        results = [row for row in pool.map(inspect, hosts) if row]
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(results, indent=2), encoding='utf-8')
    for row in results:
        print(row['host'], 'ICMP:', row['icmp'], 'TCP:', row['open_tcp_ports'])
    print('Bulunan:', len(results), 'Rapor:', path)


if __name__ == '__main__':
    main()
