"""Preserve endpoint volumes in older office receivers without replacing the app."""
import ast
import datetime
from pathlib import Path
import sys
from file_security import restrict


def segment(source):
    tree=ast.parse(source)
    matches=[node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=='endpoint_report']
    if len(matches)!=1 or [a.arg for a in matches[0].args.args]!=['data','computer'] or matches[0].decorator_list:
        raise ValueError('Unrecognized endpoint validator; nothing changed')
    if not any(isinstance(node,ast.FunctionDef) and node.name=='host' for node in tree.body):
        raise ValueError('Required host validator missing; nothing changed')
    node=matches[0]
    return node,ast.get_source_segment(source,node)


def replace_validator(source,payload):
    node,old=segment(source)
    if "'volumes'" in old or '"volumes"' in old:return source,False
    candidate=source.splitlines(keepends=True)
    # Self-contained standard-library imports; preserve the existing host check.
    lines=payload.strip().splitlines()
    lines.insert(1,'    import math, ipaddress')
    candidate=''.join(candidate[:node.lineno-1])+'\n'.join(lines)+'\n'+''.join(candidate[node.end_lineno:])
    compile(candidate,'office-endpoint-validator','exec')
    return candidate,True


def main():
    root=Path('C:/CenterEK');relay=Path('C:/CenterEK-Relay')
    payload=(Path(__file__).resolve().parent/'endpoint_validator_payload.py').read_text(encoding='utf-8-sig')
    changes=[]
    for path in (root/'agents.py',relay/'agents.py'):
        if not path.is_file() or path.is_symlink() or path.parent.is_symlink():raise ValueError('Expected regular office receiver/relay files')
        original=path.read_bytes();source=original.decode('utf-8-sig')
        candidate,needed=replace_validator(source,payload)
        print(path, 'UPDATE_REQUIRED' if needed else 'VOLUMES_ALREADY_SUPPORTED')
        if needed:changes.append((path,original,candidate))
    if not changes:
        print('NO_CHANGES: both validators already preserve disks. Inspect the systemd collector mount namespace next.')
        return
    stamp=datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    for path,original,candidate in changes:
        if path.read_bytes()!=original:raise RuntimeError('Concurrent edit; reopen updater')
    for path,original,candidate in changes:
        backup=path.with_name('agents.before-volumes.'+stamp+'.local.py')
        with backup.open('xb') as output:restrict(backup);output.write(original)
        temporary=path.with_name('agents.volumes.'+stamp+'.tmp')
        with temporary.open('x',encoding='utf-8') as output:restrict(temporary);output.write(candidate)
        temporary.replace(path)
    import subprocess
    result=subprocess.run(['powershell.exe','-NoProfile','-File',str(Path(__file__).resolve().parent/'Restart-OfficeMonitor.ps1'),'-Root',str(root)],capture_output=True,timeout=50)
    if result.returncode:raise RuntimeError('Validator updated but monitor restart failed; restart matching CenterEK-Server-System task')
    print('UPDATED: only outdated endpoint validator functions changed; config, accounts, FortiGate keys and database are preserved.')

if __name__=='__main__':main()
