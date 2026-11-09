"""Local-only filesystem capacity helper; no credential or network imports."""
import json
import math
import os
from pathlib import Path
import time

CACHE=Path('/var/lib/centerek-fs/volumes.json')
LOCAL=('xfs','ext4','ext3','ext2','btrfs','vfat')


def volumes():
    result=[];seen=set()
    for line in Path('/proc/self/mountinfo').read_text().splitlines():
        left,right=line.split(' - ',1);fields=left.split();kind=right.split()[0]
        if kind not in LOCAL or len(result)>=128:continue
        mount=fields[4].replace('\\040',' ').replace('\\011','\t').replace('\\134','\\')
        if fields[2] in seen or not os.path.isdir(mount):continue
        seen.add(fields[2])
        try:
            stat=os.statvfs(mount);total=stat.f_blocks*stat.f_frsize;free=max(0,min(total,stat.f_bavail*stat.f_frsize))
            result.append({'name':mount,'format':kind,'total_gb':round(total/1024.0**3,2),'free_gb':round(free/1024.0**3,2)})
        except OSError:continue
    return result


def cached(path=CACHE,now=None):
    path=Path(path);now=time.time() if now is None else now
    try:
        if path.is_symlink() or path.stat().st_size>128*1024:return None
        data=json.loads(path.read_text())
        stamp=data['collected_at']
        if data.get('schema')!=1 or type(stamp) not in (int,float) or not math.isfinite(stamp) or not 0<=now-stamp<=150:return None
        rows=data['volumes']
        if not isinstance(rows,list) or len(rows)>128:return None
        clean=[]
        for row in rows:
            if not isinstance(row.get('name'),str) or len(row['name'])>4096 or row.get('format') not in LOCAL:return None
            total,free=row['total_gb'],row['free_gb']
            if any(type(v) not in (int,float) or not math.isfinite(v) for v in (total,free)) or not 0<=free<=total<=100000000:return None
            clean.append({k:row[k] for k in ('name','format','total_gb','free_gb')})
        return clean
    except (OSError,ValueError,TypeError,KeyError,AttributeError):return None


def main():
    if CACHE.is_symlink() or CACHE.parent.is_symlink():raise ValueError('Unsafe cache path')
    payload={'schema':1,'collected_at':time.time(),'volumes':volumes()}
    temporary=CACHE.with_name('volumes.'+str(os.getpid())+'.'+os.urandom(6).hex()+'.tmp')
    try:
        with temporary.open('x',encoding='utf-8') as output:
            os.fchmod(output.fileno(),0o640);json.dump(payload,output,allow_nan=False)
        temporary.replace(CACHE)
    finally:
        if temporary.exists():temporary.unlink()
    print('FILESYSTEM_COUNTERS_UPDATED',flush=True)

if __name__=='__main__':main()
