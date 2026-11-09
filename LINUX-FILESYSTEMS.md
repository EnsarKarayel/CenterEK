# Private-home filesystem capacity

The network agent keeps ProtectHome=true. A separate centerek-fs system account
runs a short oneshot capacity helper with PrivateNetwork=true, AF_UNIX only and
no access to /etc/centerek-agent credentials. It reads local filesystem capacity,
not directory contents, and writes only an atomic metrics cache. The network agent
can read but not write this helper's cache. Cache older than 150 seconds is ignored.

The helper uses ProtectHome=read-only to retain /home filesystem metadata; its
separate UID, no-network namespace, empty capabilities, protected code and explicit
credential/socket-path isolation keep that access away from the network process.
The existing network agent's unit, credential and home isolation remain unchanged.
The systemd StateDirectory is the helper's only managed persistent write location.
Reference: https://freedesktop.org/software/systemd/man/latest/systemd.exec.html

## Existing Oracle Linux agent

From this Windows computer, copy the credential-free update folder through SSH:

```cmd
scp -r "C:\Users\ensar.karayel\Documents\ChatGPT\rapor\netwatch\data\secure-handoff\CenterEK-Linux-Filesystems" oraclevolo@192.168.1.8:~/
```

Then in the existing Linux SSH terminal:

```bash
cd ~/CenterEK-Linux-Filesystems
sudo python3 install_filesystem_metrics.py
systemctl status centerek-filesystems.timer --no-pager
```

Expect FILESYSTEM_HELPER_INSTALLED count=... . Existing helpers or accounts are
preserved rather than overwritten. The installer saves previous collector code,
keeps the enrollment, starts the local counter timer and restarts the existing
agent to read the cache. It does not change firewall, SELinux or Oracle settings.
Verify /home capacity reaches Azure in a fresh report; timer active alone is not
end-to-end acceptance. This upgrade still requires real Oracle Linux validation.
