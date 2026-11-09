# Domain workstation rollout

Status: prepared tooling; live AD publication/GPO rollout is not yet performed.

## Office flow

PC (SYSTEM, 60-second measurements) -> verified HTTPS 192.168.1.15:8765 -> existing scoped office relay -> Azure dashboard. No Python is installed on endpoints. AD supplies identities; endpoint reports supply actual signed-in Windows sessions. Offline PCs install on a later domain-connected startup. VPN-only/off-domain machines require a separate deployment route.

Each workstation gets its own enrollment credential, bound to its name. Never put all enrollment files in SYSVOL, NETLOGON, email or a generally readable share. The publisher creates an encrypted SMB3 share on the domain server with access-based enumeration and machine-specific NTFS ACLs: a computer can read only its own package. Domain computers can read the common startup script but cannot alter it. Shared credentials and user passwords are not used.

## 1. Prepare on 192.168.1.15

Copy the supplied CenterEK-Domain-Rollout folder to C:\CenterEK\CenterEK-Domain-Rollout. Use administrator CMD:

```cmd
powershell.exe -NoProfile -File "C:\CenterEK\CenterEK-Domain-Rollout\Prepare-DomainRollout.ps1"
```

This writes rollout-plan.csv and does not register agents. Review it. Only enabled Windows 8/10/11 workstations with matching AD DNS names are eligible; servers, DCs, disabled accounts and unknown OS entries are excluded. Existing endpoint registrations are preserved. An existing credential without an installed agent needs repair/re-enrollment; it is not silently replaced. The AD snapshot must be less than 24 hours old. If a different inventory path is used, pass -Inventory with the exact local JSON file.

Then create the per-PC packages:

```cmd
powershell.exe -NoProfile -File "C:\CenterEK\CenterEK-Domain-Rollout\Prepare-DomainRollout.ps1" -Apply
```

Keep the entire folder private during transfer to VOLO (192.168.1.10), for example C:\CenterEK-Domain-Rollout. It now contains machine credentials. Never send the folder contents to chat or commit them. Retry preserves earlier registrations; a partial failed run may require reviewing generated packages before continuing.

## 2. Publish on VOLO

Use domain administrator CMD locally on VOLO:

```cmd
powershell.exe -NoProfile -File "C:\CenterEK-Domain-Rollout\Publish-DomainRollout.ps1"
```

Publisher revalidates every target against live AD before creating a share. It refuses an existing share/destination, does not reset existing shares, does not change firewall/UAC, and does not deploy to DCs. Keep SMB signing/domain policies intact. SMB3-capable Windows clients are required. If policy requires Authenticode, sign the scripts with the organization's code-signing certificate; do not bypass execution policy.

## 3. One-time GPO setup on VOLO

Open Group Policy Management (gpmc.msc). Create a new GPO named CenterEK Endpoint Rollout; initially link to a small workstation test OU. Do not edit Default Domain Policy or Default Domain Controllers Policy.

Edit: Computer Configuration -> Policies -> Windows Settings -> Scripts (Startup/Shutdown) -> Startup -> PowerShell Scripts -> Add. Use the exact STARTUP_SCRIPT UNC printed by the publisher (normally \\VOLO.volonet.local\CenterEKDeploy$\Start-DomainEndpoint.ps1). No parameters. Do not use a user logon script.

Keep existing security filtering/policy standards. Allow computer policy processing as appropriate for the selected OU. Ensure network is available during startup using the organization's existing startup/network policy; do not force reboot active workstations. After checking a pilot computer at its next scheduled restart, extend the link to the intended workstation OUs. Computers outside those OUs are not covered. Domain-root linking should be an explicit administrator decision, not an automatic default.

## 4. Verify and maintain

Expected task: CenterEK-Endpoint-System running as SYSTEM. Local installation: C:\ProgramData\CenterEK-Agent (SYSTEM/admin only). Logs: data\logs\endpoint.log. Within a few measurement/relay cycles, Azure shows fresh timestamp, CPU, memory, disk capacity/free space and reported Windows sessions. An active Windows session does not prove physical user presence or an unlocked screen.

Startup skips existing installations. A broken partial installation is reported rather than overwritten. Keep the distribution available for offline PCs; after verified installation remove its plaintext enrollment from private transfer copies/distribution as appropriate. Do not remove protected data\secure settings on the endpoint. Revoke individual credentials through the existing registry if a machine is retired. Removing the GPO link stops new installations; it does not uninstall working agents. No automatic reboot or remote firewall opening is performed.
