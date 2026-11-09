"""Real systemd acceptance on an ephemeral Linux CI runner only."""
import http.server
import json
import os
from pathlib import Path
import shutil
import socket
import ssl
import subprocess
import sys
import tempfile
import threading
import time

ROOT=Path(__file__).resolve().parents[2]
MOUNT=Path('/home/centerek-capacity-ci')


def run(*args,**kwargs):return subprocess.run(list(args),check=True,**kwargs)


def main():
    if sys.platform!='linux' or os.geteuid()!=0 or os.environ.get('GITHUB_ACTIONS')!='true':
        raise SystemExit('Ephemeral GitHub Linux runner with sudo only')
    if Path('/opt/centerek-agent').exists() or Path('/etc/centerek-agent').exists() or MOUNT.exists():
        raise SystemExit('Pre-existing installation/mount preserved')
    work=Path(tempfile.mkdtemp(prefix='centerek-linux-ci-'))
    server=None;thread=None;mounted=False
    received=[]
    class Receiver(http.server.BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_POST(self):
            length=int(self.headers.get('Content-Length','0'))
            if self.path!='/api/agent/endpoint' or self.headers.get('Authorization')!='Bearer ephemeral-ci-only' or not 0<length<=262144:
                self.send_error(401);return
            body=json.loads(self.rfile.read(length))
            if body.get('computer')!=socket.gethostname().split('.')[0].upper():self.send_error(400);return
            received.append(body);self.send_response(202);self.end_headers();self.wfile.write(b'{}')
    try:
        image=work/'filesystem.img'
        with image.open('wb') as output:output.truncate(64*1024*1024)
        run('mkfs.ext4','-q','-F',str(image))
        MOUNT.mkdir()
        run('mount','-o','loop',str(image),str(MOUNT));mounted=True
        run('openssl','req','-x509','-newkey','rsa:2048','-nodes','-days','1','-keyout',str(work/'server-key.pem'),
            '-out',str(work/'panel-ca.pem'),'-subj','/CN=localhost','-addext','subjectAltName=DNS:localhost,IP:127.0.0.1',stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Receiver)
        context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);context.load_cert_chain(work/'panel-ca.pem',work/'server-key.pem')
        server.socket=context.wrap_socket(server.socket,server_side=True)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        for name in ('linux_collector.py','linux_filesystems.py','install_linux_agent.py','install_filesystem_metrics.py'):
            shutil.copyfile(ROOT/name,work/name)
        (work/'enrollment.local.json').write_text(json.dumps({'computer':socket.gethostname().split('.')[0].upper(),
            'kind':'endpoint','platform':'linux','url':'https://127.0.0.1:'+str(server.server_port),'token':'ephemeral-ci-only'}))
        run('/usr/bin/python3',str(work/'install_linux_agent.py'))
        deadline=time.monotonic()+100
        # First upload is installer preflight. The second must come from the
        # actual unprivileged, private-home network service through the cache.
        while len(received)<2 and time.monotonic()<deadline:time.sleep(1)
        assert len(received)>=2,'Unattended network service did not report'
        assert any(v['name']==str(MOUNT) for v in received[1]['volumes']),'Protected-home capacity missing from real service report'
        assert subprocess.run(['sudo','-u','centerek-fs','test','-r','/etc/centerek-agent/agent.json']).returncode!=0,'Filesystem helper can read upload credential'
        assert subprocess.run(['sudo','-u','centerek-agent','test','-w','/var/lib/centerek-fs/volumes.json']).returncode!=0,'Network agent can alter filesystem cache'
        pid=subprocess.check_output(['systemctl','show','centerek-agent.service','--property=MainPID','--value'],text=True).strip()
        assert int(pid)>0
        assert subprocess.run(['nsenter','--mount','--target',pid,'--','test','-e',str(MOUNT)]).returncode!=0,'Network service can reach protected home mount'
        private=subprocess.check_output(['systemctl','show','centerek-filesystems.service','--property=PrivateNetwork','--value'],text=True).strip()
        assert private=='yes','Filesystem service is not network-isolated'
        print('LINUX_SYSTEMD_ACCEPTANCE_OK: verified HTTPS, private-home capacity, separate UIDs and credential/cache isolation')
    finally:
        for unit in ('centerek-agent.service','centerek-filesystems.timer','centerek-filesystems.service'):
            subprocess.run(['systemctl','stop',unit],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        if server:server.shutdown();server.server_close()
        if thread:thread.join(timeout=5)
        if mounted:run('umount',str(MOUNT))
        if MOUNT.exists():MOUNT.rmdir()
        # CI VM is disposed after the job; preserve service artifacts on failures
        # for inspection instead of deleting potentially unexpected system paths.
        shutil.rmtree(work)

if __name__=='__main__':main()
