"""Unprivileged Linux resource collector; no database or SSH credentials needed."""
import argparse
import datetime
import json
import os
from pathlib import Path
import socket
import ssl
import subprocess
import time
from urllib.parse import urlsplit
from urllib.request import Request, HTTPSHandler, HTTPRedirectHandler, ProxyHandler, build_opener


def memory(text):
    values = {}
    for line in text.splitlines():
        key, separator, value = line.partition(':')
        if separator and value.strip(): values[key] = int(value.split()[0])*1024
    total, available = values['MemTotal'], values['MemAvailable']
    if not 0 <= available <= total or total <= 0: raise ValueError('Invalid memory counters')
    return {'memory_total_gb':round(total/1024.0**3,2), 'memory_used_gb':round((total-available)/1024.0**3,2),
            'memory_percent':round(100.0*(total-available)/total,1)}


def cpu(text):
    values = [int(v) for v in text.splitlines()[0].split()[1:9]]
    if len(values)<4 or any(v<0 for v in values):raise ValueError('Invalid CPU counters')
    return sum(values), values[3]+(values[4] if len(values)>4 else 0)


def collect(computer):
    if computer.upper() not in (socket.gethostname().upper(),socket.gethostname().split('.')[0].upper()):
        raise ValueError('Enrollment belongs to a different computer')
    addresses = subprocess.check_output(['ip','-j','-4','address','show'],universal_newlines=True,timeout=5)
    interfaces=[]
    for adapter in json.loads(addresses):
        for addr in adapter.get('addr_info',[]):
            if addr.get('scope')!='global':continue
            interfaces.append({'ip':addr['local'],'name':adapter['ifname'],'mac':adapter.get('address'),
                'transport':('wireless' if (Path('/sys/class/net')/adapter['ifname']/'wireless').exists() else
                             'wired' if (Path('/sys/class/net')/adapter['ifname']/'device').exists() else 'other')})
    resources=memory(Path('/proc/meminfo').read_text())
    before=cpu(Path('/proc/stat').read_text());time.sleep(1);after=cpu(Path('/proc/stat').read_text())
    delta=after[0]-before[0]
    resources['cpu_percent']=round(max(0,min(100,100.0*(delta-(after[1]-before[1]))/delta)),1) if delta>0 else None
    volumes=[];seen=set()
    # Local mounted filesystems only. No recursive file/database access or NFS probes.
    for line in Path('/proc/self/mountinfo').read_text().splitlines():
        left,right=line.split(' - ',1);fields=left.split();fstype=right.split()[0]
        if fstype not in ('xfs','ext4','ext3','ext2','btrfs') or len(volumes)>=128:continue
        mount=fields[4].replace('\\040',' ').replace('\\011','\t').replace('\\134','\\')
        if fields[2] in seen or not os.path.isdir(mount):continue
        seen.add(fields[2])
        try:
            stat=os.statvfs(mount);total=stat.f_blocks*stat.f_frsize;free=max(0,min(total,stat.f_bavail*stat.f_frsize))
            volumes.append({'name':mount,'format':fstype,'total_gb':round(total/1024.0**3,2),'free_gb':round(free/1024.0**3,2)})
        except OSError:continue
    return {'schema':1,'platform':'linux','computer':computer.upper(),'status':'ok',
        'collected_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'interval_seconds':60,
        'ips':sorted(set(i['ip'] for i in interfaces)), 'interfaces':interfaces,'resources':resources,
        'volumes':volumes,'sessions':[],'address_source':'Yerel ağ kartları'}


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None


def send(report,config,ca):
    parsed=urlsplit(config['url'])
    if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password or parsed.path not in ('','/') or parsed.query or parsed.fragment:
        raise ValueError('Exact HTTPS office origin required')
    if config.get('kind')!='endpoint':raise ValueError('Per-machine endpoint enrollment required')
    request=Request(config['url'].rstrip('/')+'/api/agent/endpoint',data=json.dumps(report,allow_nan=False).encode('utf-8'),
        headers={'Authorization':'Bearer '+config['token'],'Content-Type':'application/json'})
    opener=build_opener(ProxyHandler({}),HTTPSHandler(context=ssl.create_default_context(cafile=str(ca))),NoRedirect())
    try:
        with opener.open(request,timeout=25) as response:
            if response.status!=202:raise RuntimeError('Report not accepted')
    finally:request.remove_header('Authorization')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path);parser.add_argument('--ca',type=Path);parser.add_argument('--once',action='store_true')
    args=parser.parse_args()
    if not args.config and not args.once:parser.error('--config is required for background collection')
    config=None
    if args.config:
        if args.config.stat().st_mode & 0o077:raise PermissionError('Credential file must be mode 600')
        config=json.loads(args.config.read_text(encoding='utf-8-sig'))
        if not args.ca:parser.error('--ca is required')
    while True:
        try:
            report=collect(config['computer'] if config else socket.gethostname().split('.')[0])
            if config:send(report,config,args.ca);print('LINUX_REPORT_ACCEPTED',flush=True)
            else:print(json.dumps(report,ensure_ascii=False))
        except Exception as error:
            print('LINUX_REPORT_FAILED '+type(error).__name__,flush=True)
            if args.once:raise SystemExit(1)
        if args.once:return
        time.sleep(60)

if __name__=='__main__':main()
