# Oracle Linux 8.10 / Python 3.6 agent

## 1. Create the one-machine enrollment on the office monitor

Copy the credential-free CenterEK-Linux-Setup folder to the office Windows server
as C:\CenterEK\CenterEK-Linux-Setup. In an administrator PowerShell:

```powershell
powershell.exe -NoProfile -File "C:\CenterEK\CenterEK-Linux-Setup\Create-LinuxPackage.ps1"
```

This uses the existing office registry to create a dedicated endpoint credential
for VOLO-PRODDB. It does not create an AD user or change any ESXi/FortiGate key.
It preserves duplicate registrations and packages. The resulting folder is:
C:\CenterEK\CenterEK-Linux-Setup\packages\VOLO-PRODDB.
It contains the Linux scripts, public office panel CA and enrollment.local.json.
That enrollment is a secret: do not paste it into chat, email it or commit it.

## 2. Transfer the generated package securely

Copy only the generated VOLO-PRODDB folder from the RDP session to this PC as
C:\Users\ensar.karayel\VOLO-PRODDB. On this PC, use the already tested SSH route:

```cmd
scp -r "C:\Users\ensar.karayel\VOLO-PRODDB" oraclevolo@192.168.1.8:~/
```

Enter the existing SSH password locally. It is never stored by CenterEK.
Do not bypass an unexpected SSH host-key warning.

## 3. Install in the existing Linux SSH session

```bash
cd ~/VOLO-PRODDB
chmod 600 enrollment.local.json
sudo python3 install_linux_agent.py
systemctl status centerek-agent.service --no-pager
```

The installer first verifies the local hostname and sends one real report over
verified HTTPS to the office monitor. No account/unit is created if that preflight
fails. It then creates the dedicated non-login centerek-agent system account and
a restricted systemd service. Existing installation paths/accounts are preserved;
a partial failure requires inspection, not blindly deleting production files.
It does not change firewall, SELinux, system CA trust or Oracle Database settings.
No pip packages are needed. Python 3.6 syntax is checked, but a real Oracle Linux
installation and end-to-end acceptance must still be confirmed.

## Data and operational checks

Reports include aggregate CPU, MemAvailable-based RAM, global IPv4 adapters and
local xfs/ext/btrfs filesystem capacity. Bind mounts are deduplicated by device.
Network filesystems, Oracle queries and physical disk/RAID health are not covered.
Linux interactive sessions are not collected. Windows user sessions come from
the separate Windows WTS endpoint agent.

```bash
journalctl -u centerek-agent.service -n 10 --no-pager
```

Expect LINUX_REPORT_ACCEPTED. The office relay forwards the source timestamps to
Azure; fresh RAM/disk rows must be confirmed there. Service active state alone is
not proof of accepted telemetry. Check certificate errors without disabling TLS.
After acceptance, remove the plaintext enrollment from both transfer locations;
preserve /etc/centerek-agent/agent.json, owned by the dedicated service account.
The agent has no inbound listening port and survives SSH logout/reboot.
