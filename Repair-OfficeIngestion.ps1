param([switch]$Apply,[switch]$AllowScopedPublic)
$ErrorActionPreference='Stop'
function Add-OfficeIngestionRule([string]$Category,[switch]$AllowScopedPublic){
    if($Category -notin @('Private','DomainAuthenticated') -and -not($Category -eq 'Public' -and $AllowScopedPublic)){throw 'NETWORK_PROFILE_NOT_PRIVATE: explicit scoped-public option required; no changes made'}
    $profiles=if($Category -eq 'Public'){@('Public')}else{@('Domain','Private')}
    $name='CenterEK-Office-Agent-Ingest-8765'
    if(Get-NetFirewallRule -Name $name -ErrorAction SilentlyContinue){throw 'Existing named rule preserved; inspect it rather than overwriting'}
    New-NetFirewallRule -Name $name -DisplayName 'CenterEK office agent HTTPS ingestion' -Description 'CenterEK scoped office receiver; reversible dedicated rule' -Direction Inbound -Action Allow -Protocol TCP -LocalAddress '192.168.1.15' -LocalPort 8765 -RemoteAddress @('192.168.1.0/24','192.168.2.0/24') -Profile $profiles -EdgeTraversalPolicy Block|Out-Null
    Write-Output 'OFFICE_INGEST_RULE_CREATED'
}
$identity=[Security.Principal.WindowsIdentity]::GetCurrent()
if(-not(New-Object Security.Principal.WindowsPrincipal($identity)).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){throw 'Administrator CMD required'}
if($env:COMPUTERNAME -ine 'DATASQL'){throw 'This repair is only for DATASQL / 192.168.1.15'}
$root='C:\CenterEK'
if(-not(Test-Path -LiteralPath (Join-Path $root 'start.py')) -or (Get-Item -LiteralPath $root -Force).Attributes -band [IO.FileAttributes]::ReparsePoint){throw 'Expected source installation not found'}
$addresses=@(Get-NetIPAddress -AddressFamily IPv4 -IPAddress '192.168.1.15')
if($addresses.Count -ne 1){throw 'Expected a single local office address'}
$profile=Get-NetConnectionProfile -InterfaceIndex $addresses[0].InterfaceIndex
if(@($profile).Count -ne 1){throw 'Expected a single active connection profile'}
$category=[string]$profile.NetworkCategory
$listeners=@(Get-NetTCPConnection -LocalAddress '192.168.1.15' -LocalPort 8765 -State Listen)
$owners=@($listeners|Select-Object -ExpandProperty OwningProcess -Unique)
if($owners.Count -ne 1){throw 'Expected one existing receiver; nothing restarted'}
$process=Get-CimInstance Win32_Process -Filter ('ProcessId='+$owners[0])
$entry=[Regex]::Escape((Join-Path $root 'start.py'))
if($process.Name -notin @('python.exe','pythonw.exe') -or $process.CommandLine -notmatch ('(?i)^\s*(?:"[^"]+"|[^\s"]+)\s+(?:-u\s+)?(?:"'+$entry+'"|'+$entry+')(?=\s|$)')){throw 'Listener is not the expected CenterEK source process'}
$profiles=if($category -eq 'Public' -and $AllowScopedPublic){@('Public')}else{@('Domain','Private')}
@{computer=$env:COMPUTERNAME;category=$category;local_address='192.168.1.15';port=8765;pid=$owners[0];remote=@('192.168.1.0/24','192.168.2.0/24');profiles=$profiles;apply=[bool]$Apply}|ConvertTo-Json -Compress
if(-not $Apply){'PLAN_ONLY: no changes made';return}
if($category -notin @('Private','DomainAuthenticated') -and -not($category -eq 'Public' -and $AllowScopedPublic)){throw ('NETWORK_PROFILE_NOT_PRIVATE='+$category+'; no changes made')}
if((Get-Service MpsSvc).Status -ne 'Running'){throw 'Windows Firewall service is not running; no changes made'}
$backup=Join-Path $root ('data\ingestion-rule-'+[Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $backup|Out-Null
$acl=New-Object Security.AccessControl.DirectorySecurity
$acl.SetAccessRuleProtection($true,$false)
foreach($sid in @('S-1-5-18','S-1-5-32-544')){$acl.AddAccessRule((New-Object Security.AccessControl.FileSystemAccessRule((New-Object Security.Principal.SecurityIdentifier($sid)),'FullControl','ContainerInherit,ObjectInherit','None','Allow')))}
Set-Acl -LiteralPath $backup -AclObject $acl
@{before_rule_present=[bool](Get-NetFirewallRule -Name 'CenterEK-Office-Agent-Ingest-8765' -ErrorAction SilentlyContinue);category=$category;undo='Remove-NetFirewallRule -Name CenterEK-Office-Agent-Ingest-8765'}|ConvertTo-Json|Set-Content -LiteralPath (Join-Path $backup 'before.json') -Encoding UTF8
Add-OfficeIngestionRule $category -AllowScopedPublic:$AllowScopedPublic
'BACKUP='+$backup
'VERIFY_FROM_CLIENT_AND_AZURE: rule creation alone does not prove fresh reports'
