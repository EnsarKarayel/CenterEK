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

## Central on-demand installation and diagnosis

Run Invoke-DomainRollout.ps1 locally on the domain distribution server as an authorized domain administrator. It uses the existing remote Task Scheduler RPC service, not WinRM/WMI or remote user passwords. No firewall or execution-policy bypass is added. Default mode only lists targets/packages.

```cmd
powershell.exe -NoProfile -File "C:\CenterEK-AD\CenterEK-Domain-Rollout\Invoke-DomainRollout.ps1" -ComputerName PC-07 -Apply
```

First verify that the pilot actually reports to Azure. Then omit -ComputerName to process all eligible domain workstations, four at a time (up to eight with -Throttle). The command window must remain open until the distribution run completes; installed agents themselves require no open window. No endpoint reboot is performed. Existing agent tasks, including disabled tasks, are preserved and reported; disabled tasks need review rather than automatic enabling. Missing packages do not create new credentials. Servers/DCs/disabled AD accounts are excluded. Offline/blocked targets are reported and may install later through GPO.

Each on-demand bootstrap task has a unique name, no startup/scheduled trigger, a three-minute execution limit, and is removed after completion. Timed-out/running tasks are retained and named in the report for investigation. Existing manually created deployment tasks are not replaced or deleted.

The first apply run creates a separate encrypted CenterEKDeployLogs$ share rooted at C:\ProgramData\CenterEK-DeploymentReceipts. Domain computers have change access at the share layer, but NTFS grants write access only to each computer's own new per-run receipt folder. The existing code/package share stays read-only. Receipts contain policy scope, source access, error ID/type/line and whether an agent task was registered; no enrollment secrets or source/error-line text is logged. Treat receipts as untrusted computer-supplied diagnostics, not authenticated proof of installation or telemetry. A bounded locked-handle reader rejects diagnostic files resolving outside the expected path.

The CSV beside the invoker contains one status per target, bootstrap exit code, diagnostic path, unresolved temporary task name and error type. TASK_REGISTERED_VERIFY_TELEMETRY means a task appeared and bootstrap returned zero; it does not claim Azure delivery. INSTALL_FAILED or REMOTE_ACCESS_FAILED must be investigated before claiming fleet coverage. In particular Last Result 1 alone is insufficient to determine execution policy, permissions or installer failure.

Windows client systems with all policy scopes Undefined default to Restricted. The bootstrap, persistent task wrapper and child collector now request RemoteSigned only for their own PowerShell processes; no registry/global execution policy is written, and MachinePolicy/UserPolicy still take precedence. Internet-origin unsigned scripts and stricter enterprise policy can still block execution; sign the package appropriately rather than using Bypass/Unrestricted or removing origin marks. Some environments treat UNC paths as internet paths, so validate pilot behavior before fleet rollout.

For packages already published before this fix, the central invoker upgrades only Install-SystemTask.ps1 and Run-SystemTask.ps1 after normalized source hashes match the reviewed legacy bytes. It validates both before changing either, retains originals beside them and preserves unknown/local revisions with PACKAGE_RUNTIME_REVIEW_REQUIRED. Enrollment/CA, AD settings and existing installed agents are untouched. The remote running-task handle is refreshed before evaluating completion, preventing a cached running state from reporting a completed failure as a timeout.

Central installation copies only that computer's eight package components into a newly generated local ProgramData staging directory, restricted to SYSTEM and administrators, and invokes its local Install-EndpointPilot.ps1. Copying retains origin streams; the invoker neither strips Zone.Identifier nor unblocks internet-marked scripts. If RemoteSigned blocks a copied script, the receipt includes bounded security-exception text and per-script zone IDs (no raw origin URLs). Stage files, including the plaintext enrollment copy, are individually removed afterward; no recursive endpoint directory deletion occurs. SCHED_E_TASK_NOT_RUNNING from a refreshed completed instance is interpreted as completion, then the registered task exit code is evaluated.

To retry only network failures from a previous CSV, supply -RetryReport with that local report path, plus -Apply. Selection includes REMOTE_ACCESS_FAILED and REMOTE_ACCESS_TIMEOUT_OR_JOB_FAILED only; successful/installed, no-package and installer-failure rows are excluded. Targets are deduplicated and revalidated against current enabled AD workstation accounts. Without -Apply this still only previews. -ComputerName and -RetryReport are mutually exclusive.

The remote scheduler tries the AD FQDN first, followed by its validated short computer name only for network-path/RPC-unavailable errors. Access denied or policy errors are not retried under another name. There is no IP-based authentication fallback, host-file change or resolver configuration change. A successful authoritative DNS query does not prove that the server's default resolver, RPC service or network path can reach the target; remaining failures record both attempted names where applicable.

## Optional separate local DNS client repair

Repair-OfficeDnsClient.ps1 is a separately invoked administrative change, not an automatic side effect of agent rollout. Default mode previews. -Apply selects the one local interface owning 192.168.1.10, verifies this is the intended volonet.local domain controller with a running DNS service, and preflights AD host/service records and public github.com resolution explicitly through the internal resolver. Failure before that gate leaves settings unchanged. Public DNS servers are not suitable as direct DNS clients on this AD DC; use the internal DNS server, with external resolution supplied by existing server recursion/forwarders. See [Microsoft DNS client recommendations](https://learn.microsoft.com/en-us/troubleshoot/windows-server/networking/best-practices-for-dns-client-settings).

The apply transaction backs up the selected IPv4 client instance, interface identity, effective server list and automatic/static mode in an admin/SYSTEM-only dns-backups folder. It sets that IPv4 instance's DNS server to the local internal resolver, clears cache and verifies normal host, AD SRV and public lookups without forcing a DNS server. On failure it restores the original static list or DHCP/automatic mode; a failed rollback is explicitly reported. Other interfaces, IPv6 instances, IP/gateway, AD/DNS zones, forwarders, DHCP and firewalls are not modified. This cannot fix an unreachable/stale endpoint IP or closed management ports; perform further transport diagnostics separately.

## Read-only audit of remaining network failures

Test-DomainRolloutNetwork.ps1 -RetryReport <latest-failed-rollout.csv> selects only remaining network-failure rows, revalidates enabled AD workstations, resolves their AD FQDNs against the internal DNS server and probes ping/TCP445/TCP135 without authenticating to the endpoints. A DNS record is not proof of current device identity. Only addresses in this office's 192.168.0.0/22 are probed; network/broadcast endpoints and answers outside the scope are excluded. At most four addresses per account and four parallel jobs by default are used, with bounded socket/job waits.

CSV/status output separates failed/no DNS answers, out-of-scope DNS IPs, no probe response, ping-only response and management-port response. No probe response cannot distinguish powered-off, stale IP, routing/VLAN issues or traffic filtering. A port response does not establish deployment permissions or endpoint identity. LastLogonApproxDays is approximate replicated AD account metadata, not live login/user presence. The audit never installs, restarts, changes firewall/DNS/AD, deletes accounts or authenticates by IP.

References: [Microsoft execution policies](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_execution_policies?view=powershell-5.1), [IRunningTask.Refresh](https://learn.microsoft.com/en-us/windows/win32/api/taskschd/nf-taskschd-irunningtask-refresh).

Startup skips existing installations. A broken partial installation is reported rather than overwritten. Keep the distribution available for offline PCs; after verified installation remove its plaintext enrollment from private transfer copies/distribution as appropriate. Do not remove protected data\secure settings on the endpoint. Revoke individual credentials through the existing registry if a machine is retired. Removing the GPO link stops new installations; it does not uninstall working agents. No automatic reboot or remote firewall opening is performed.
