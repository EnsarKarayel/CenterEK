# Office → Azure telemetry

The office installation stays in place. Its relay reads the existing monitor
SQLite database in read-only mode and the existing AD/endpoint report files.
Only allowlisted measurements and inventory fields leave the office. The relay
does not decrypt FortiGate/ESXi/SNMP credentials and does not change any device.

Traffic: office SYSTEM task → outbound HTTPS → machine-only Azure ingress →
scoped, revocable site credential → private application. The telemetry ingress
accepts only POST `/api/agent/site`; panel, login, health and other paths are not
published there. The normal dashboard continues using Microsoft sign-in.

Each office registration explicitly specifies its private network (for VOLO,
`192.168.0.0/22`), optional directory domain (`volonet.local`) and source server
(`VOLO`). The site cannot overwrite Azure's own device IDs. AD transfer requires
explicit domain/source registration; only one office owns the directory slot in
this single-tenant preview. Site enrollment tokens are generated once, protected
by machine DPAPI and file ACLs on the office server, and revocable from Azure.

Source measurement timestamps are preserved. A live relay does not turn old
source files into fresh measurements. It sends the currently available data;
hardware/session information for computers without endpoint agents stays
unmeasured. Discovering an IP or reading AD does not provide RAM or live sessions.

## Rollout and acceptance

- [ ] Deploy the backend supporting scoped site ingestion through reviewed CI.
- [ ] Deploy telemetry ingress internally; validate nginx, private TLS and 401
  for missing/invalid credentials before enabling external HTTPS.
- [ ] Register VOLO office and securely deliver its one-time enrollment.
- [ ] Extract relay files to a separate `C:\CenterEK-Relay` folder on 1.15.
  Do not overwrite `C:\CenterEK` or its existing SYSTEM tasks/configuration.
- [ ] Run `Install-SiteRelay.ps1` as administrator with the protected enrollment.
  It creates `CenterEK-OfficeRelay-System`, starts at boot and survives logoff.
- [ ] Verify an accepted report, server/FortiGate counts, actual AD user/computer
  counts, source timestamps and fresh endpoint data in the Azure dashboard.
- [ ] Securely remove the plaintext enrollment and test revocation/renewal.

No inbound office firewall port, public AD/LDAP, public ESXi/iDRAC or FortiGate
management access is required. Existing source collector permissions and agent
deployment remain prerequisites. Linux resource/Dell hardware collection is
still a separate feature; the bridge does not manufacture unsupported readings.

The extra Consumption ingress scales 0–1 replicas and can consume trial credit.
This is a separate, token-authenticated machine interface, not an exemption in
the dashboard's Microsoft authentication policy. Gateway limits do not establish
DDoS immunity or production security certification.
