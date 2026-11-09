# Office resource connections and Windows endpoint pilot

Run Start-OfficeConnections.ps1 as administrator on the existing monitoring
server. Keep this helper in a separate folder; do not replace the existing
CenterEK installation. The helper uses its existing config and background tasks.

## ESXi

Select hosts, enter local ESXi credentials and optionally select their trusted
PEM CA. The helper verifies HTTPS and reads CPU/RAM/datastores before saving any
configuration. Failed authentication/certificate tests preserve existing settings.
Existing encrypted FortiGate credentials are retained without decrypting them.
Passwords are stored only in machine DPAPI ciphertext; never copy them to Git.
The matching CenterEK-Server-System task is restarted after successful setup.
No ESXi write API is called. Datastore capacity is not physical disk/RAID health.

If ESXi certificates are not trusted or do not contain the configured IP, use a
certificate and DNS/IP combination that validates. Certificate verification is
never disabled. The helper does not auto-trust a network-discovered certificate.

## Windows users / resources

Enter the computer name and office HTTPS origin, then create its endpoint agent
package. Copy only that generated package to the matching computer and run
Install-EndpointPilot.ps1 as administrator. The package contains a unique,
computer-bound enrollment: treat it as a credential, never email it or commit it.
A duplicate existing enrollment is preserved rather than silently rotating it.

The installer protects its key with DPAPI and creates the existing SYSTEM startup
task, which survives logoff. It trusts only the supplied office panel CA and opens
no inbound endpoint port. The local WTS collector reports interactive session
identity/state plus IP/MAC adapters, CPU/RAM and volume space. Reports travel to
the office monitor and then through the office relay to Azure.

After an accepted report, remove the plaintext enrollment from both transfer
locations. Preserve protected agent.local.json / data/secure configuration.
A session marked active is not proof the user is physically present or unlocked.
AD matching is account + domain matching and depends on directory freshness.

Pilot verification precedes domain-wide deployment. GPO distribution, Linux
resource monitoring and Dell hardware sensor/RAID collection are separate work.
