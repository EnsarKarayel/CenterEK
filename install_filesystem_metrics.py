"""Add credential-free, network-isolated filesystem metrics beside an existing agent."""
import argparse
import datetime
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

APP=Path('/opt/centerek-agent')
UNITS=Path('/etc/systemd/system')
ACCOUNT='centerek-fs'


def units(python):
    if not python.startswith('/') or any(c in python for c in '\n\r" %'):raise ValueError('Unsupported interpreter path')
    service='''[Unit]
Description=CenterEK local filesystem capacity counters

[Service]
Type=oneshot
User=centerek-fs
Group=centerek-agent
ExecStart=PYTHON /opt/centerek-agent/linux_filesystems.py
StateDirectory=centerek-fs
StateDirectoryMode=0750
PrivateNetwork=true
RestrictAddressFamilies=AF_UNIX
InaccessiblePaths=-/etc/centerek-agent -/run -/tmp -/var/tmp
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=read-only
PrivateDevices=true
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true
CapabilityBoundingSet=
RestrictSUIDSGID=true
MemoryMax=64M
CPUQuota=5%
TimeoutStartSec=25
UMask=0027
'''.replace('PYTHON',python)
    timer='''[Unit]
Description=Refresh CenterEK filesystem counters

[Timer]
OnBootSec=10s
OnUnitActiveSec=60s
AccuracySec=1s
Unit=centerek-filesystems.service

[Install]
WantedBy=timers.target
'''
    return service,timer


def apply(source,restart=True):
    if not hasattr(os,'geteuid') or os.geteuid()!=0:raise PermissionError('Run sudo python3 install_filesystem_metrics.py')
    import pwd
    source=Path(source).resolve()
    account=pwd.getpwnam('centerek-agent')
    main=UNITS/'centerek-agent.service'
    if not main.is_file() or main.is_symlink() or APP.is_symlink() or not APP.is_dir():raise ValueError('Existing CenterEK agent required')
    text=main.read_text()
    if 'User=centerek-agent' not in text or 'ProtectHome=true' not in text or '/opt/centerek-agent/linux_collector.py' not in text:
        raise ValueError('Unrecognized main unit; protections were not changed')
    service,timer=units(str(Path(sys.executable).resolve()))
    for path in (UNITS/'centerek-filesystems.service',UNITS/'centerek-filesystems.timer',Path('/var/lib/centerek-fs')):
        if path.exists() or path.is_symlink():raise ValueError('Existing filesystem helper preserved')
    try:pwd.getpwnam(ACCOUNT)
    except KeyError:pass
    else:raise ValueError('Existing filesystem service account preserved')
    for name in ('linux_filesystems.py','linux_collector.py'):
        path=source/name
        if not path.is_file() or path.is_symlink():raise ValueError('Missing/unsafe helper component')
    for name in ('linux_filesystems.py','linux_collector.py'):
        path=APP/name
        if path.is_symlink() or (path.exists() and (path.stat().st_uid!=0 or path.stat().st_mode & 0o022)):
            raise PermissionError('Existing agent code must be administrator-owned and protected')
    subprocess.check_call(['useradd','--system','--no-create-home','--home-dir','/nonexistent','--shell','/sbin/nologin','--gid',str(account.pw_gid),ACCOUNT])
    stamp=datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    for name in ('linux_collector.py','linux_filesystems.py'):
        target=APP/name
        if target.exists():
            backup=APP/(name+'.before-filesystems-'+stamp)
            shutil.copyfile(str(target),str(backup));backup.chmod(0o600)
        temporary=APP/(name+'.'+stamp+'.tmp')
        with temporary.open('xb') as output:
            os.fchmod(output.fileno(),0o644);output.write((source/name).read_bytes())
        temporary.replace(target)
    for name,body in (('centerek-filesystems.service',service),('centerek-filesystems.timer',timer)):
        path=UNITS/name
        with path.open('x',encoding='ascii') as output:output.write(body)
        path.chmod(0o644)
    subprocess.check_call(['systemd-analyze','verify',str(UNITS/'centerek-filesystems.service'),str(UNITS/'centerek-filesystems.timer')])
    subprocess.check_call(['systemctl','daemon-reload'])
    subprocess.check_call(['systemctl','start','centerek-filesystems.service'])
    subprocess.check_call(['systemctl','enable','--now','centerek-filesystems.timer'])
    if restart:subprocess.check_call(['systemctl','try-restart','centerek-agent.service'])
    payload=json.loads(Path('/var/lib/centerek-fs/volumes.json').read_text())
    print('FILESYSTEM_HELPER_INSTALLED count='+str(len(payload['volumes'])))
    print('Main agent ProtectHome=true and credentials are unchanged. The separate filesystem helper has no network access.')


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--source',type=Path,default=Path(__file__).resolve().parent)
    args=parser.parse_args()
    try:apply(args.source)
    except Exception as error:
        print('FILESYSTEM_INSTALL_FAILED '+type(error).__name__+': '+(str(error) if isinstance(error,(ValueError,PermissionError)) else 'Inspect local systemd diagnostics; credentials were not changed.'))
        raise SystemExit(1)

if __name__=='__main__':main()
