"""Fresh systemd installation for the unprivileged Linux resource agent."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import linux_collector

ACCOUNT='centerek-agent'
APP=Path('/opt/centerek-agent')
ETC=Path('/etc/centerek-agent')
UNIT=Path('/etc/systemd/system/centerek-agent.service')


def service_unit(python):
    if not python.startswith('/') or any(c in python for c in '\n\r" %'):
        raise ValueError('Unsupported interpreter path')
    return '''[Unit]
Description=CenterEK read-only Linux resource collector
Wants=network-online.target
After=network-online.target

[Service]
Type=simple
User=centerek-agent
Group=centerek-agent
ExecStart=PYTHON -u /opt/centerek-agent/linux_collector.py --config /etc/centerek-agent/agent.json --ca /etc/centerek-agent/panel-ca.pem
Restart=on-failure
RestartSec=30
NoNewPrivileges=true
PrivateTmp=true
PrivateDevices=true
ProtectSystem=strict
ProtectHome=true
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true
RestrictSUIDSGID=true
CapabilityBoundingSet=
RestrictAddressFamilies=AF_INET AF_INET6 AF_UNIX AF_NETLINK
MemoryMax=128M
CPUQuota=5%
Nice=10
UMask=0077

[Install]
WantedBy=multi-user.target
'''.replace('PYTHON',python)


def install(source):
    if not hasattr(os,'geteuid') or os.geteuid()!=0:
        raise PermissionError('Run sudo python3 install_linux_agent.py')
    import pwd
    source=Path(source).resolve()
    for path in (APP,ETC,UNIT):
        if path.exists() or path.is_symlink(): raise ValueError('Existing installation preserved: '+str(path))
        if path.parent.is_symlink(): raise ValueError('Symlink installation parent rejected')
    for name in ('linux_collector.py','enrollment.local.json','panel-ca.pem'):
        path=source/name
        if not path.is_file() or path.is_symlink():raise ValueError('Missing/unsafe installation component')
    try:pwd.getpwnam(ACCOUNT)
    except KeyError:pass
    else:raise ValueError('Existing service account preserved')
    if not shutil.which('systemctl') or not shutil.which('useradd') or not shutil.which('systemd-analyze'):
        raise RuntimeError('systemd and useradd are required')
    python=str(Path(sys.executable).resolve())
    info=Path(python).stat()
    if info.st_uid!=0 or info.st_mode & 0o022:raise PermissionError('Use a root-owned Python interpreter')
    unit=service_unit(python)
    enrollment=source/'enrollment.local.json'
    enrollment.chmod(0o600)
    config=json.loads(enrollment.read_text(encoding='utf-8-sig'))
    if config.get('platform')!='linux':raise ValueError('Linux-specific endpoint package required')
    # Real identity-bound TLS preflight before creating any service account/unit.
    report=linux_collector.collect(config['computer'])
    linux_collector.send(report,config,source/'panel-ca.pem')
    subprocess.check_call(['useradd','--system','--user-group','--no-create-home','--home-dir','/nonexistent','--shell','/sbin/nologin',ACCOUNT])
    account=pwd.getpwnam(ACCOUNT)
    APP.mkdir(mode=0o755);ETC.mkdir(mode=0o750)
    os.chown(str(ETC),0,account.pw_gid)
    shutil.copyfile(str(source/'linux_collector.py'),str(APP/'linux_collector.py'))
    (APP/'linux_collector.py').chmod(0o644)
    target=ETC/'agent.json'
    with target.open('x',encoding='utf-8') as output:
        os.fchmod(output.fileno(),0o600);os.fchown(output.fileno(),account.pw_uid,account.pw_gid)
        json.dump(config,output)
    shutil.copyfile(str(source/'panel-ca.pem'),str(ETC/'panel-ca.pem'))
    (ETC/'panel-ca.pem').chmod(0o644)
    with UNIT.open('x',encoding='ascii') as output:output.write(unit)
    UNIT.chmod(0o644)
    subprocess.check_call(['systemd-analyze','verify',str(UNIT)])
    from install_filesystem_metrics import apply
    apply(source,restart=False)
    subprocess.check_call(['systemctl','daemon-reload'])
    subprocess.check_call(['systemctl','enable','--now','centerek-agent.service'])
    subprocess.check_call(['systemctl','is-active','--quiet','centerek-agent.service'])
    print('LINUX_AGENT_INSTALLED: unprivileged systemd service active. No firewall, SELinux, database or system CA settings changed.')
    print('After confirming Azure receipt, remove enrollment.local.json from transfer locations. Keep /etc/centerek-agent/agent.json.')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,default=Path(__file__).resolve().parent)
    args=parser.parse_args()
    try:install(args.source)
    except Exception as error:
        # Never print bearer-bearing request objects or raw HTTP response bodies.
        print('INSTALL_FAILED '+type(error).__name__+': '+(str(error) if isinstance(error,(ValueError,PermissionError)) else 'Check HTTPS trust, office reachability and enrollment. Existing service data was not overwritten.'))
        raise SystemExit(1)

if __name__=='__main__':main()
