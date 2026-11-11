param(
    [switch]$Apply,
    [string]$InternalDns='192.168.1.10',
    [string]$DomainName='volonet.local',
    [string]$ProbeName='PC-08.volonet.local'
)
# Local IPv4 DNS CLIENT repair only. No IP/gateway, DNS forwarder/zone, AD,
# firewall, service restart, endpoint DNS or DHCP changes.
$ErrorActionPreference='Stop'
function Invoke-DnsClientTransaction($DnsClient,[string[]]$OriginalServers,[bool]$WasAutomatic,[string]$Server,[string]$Domain,[string]$Probe){
    try{
        Set-DnsClientServerAddress -InputObject $DnsClient -ServerAddresses @($Server)
        Clear-DnsClientCache
        $current=Get-DnsClientServerAddress -InterfaceIndex $DnsClient.InterfaceIndex -AddressFamily IPv4
        if(@($current.ServerAddresses).Count -ne 1 -or $current.ServerAddresses[0] -ne $Server){throw 'DNS client setting did not persist'}
        # Use the normal resolver now, not -Server: validate the real consumer.
        $internal=@(Resolve-DnsName -Name $Probe -Type A -DnsOnly)
        if(-not @($internal|Where-Object IPAddress).Count){throw 'Normal AD host lookup failed'}
        $ldap=@(Resolve-DnsName -Name ('_ldap._tcp.dc._msdcs.'+$Domain) -Type SRV -DnsOnly)
        if(-not @($ldap|Where-Object NameTarget).Count){throw 'Normal AD service lookup failed'}
        $public=@(Resolve-DnsName -Name 'github.com' -Type A -DnsOnly)
        if(-not @($public|Where-Object IPAddress).Count){throw 'Normal public lookup failed'}
        Write-Output 'DNS_CLIENT_FIXED'
        $current|Select-Object InterfaceAlias,ServerAddresses
        $internal|Where-Object IPAddress|Select-Object Name,IPAddress
    }catch{
        $originalError=$_.Exception.GetType().FullName
        try{
            if($WasAutomatic){Set-DnsClientServerAddress -InputObject $DnsClient -ResetServerAddresses}
            else{Set-DnsClientServerAddress -InputObject $DnsClient -ServerAddresses $OriginalServers}
            Clear-DnsClientCache
            Write-Output 'DNS_ROLLED_BACK'
        }catch{throw ('DNS_ROLLBACK_FAILED: restore saved IPv4 DNS client settings; '+$originalError)}
        throw ('DNS validation failed; previous DNS client configuration restored. '+$originalError)
    }
}
$identity=[Security.Principal.WindowsIdentity]::GetCurrent()
if(-not(New-Object Security.Principal.WindowsPrincipal($identity)).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){throw 'Administrator CMD required on VOLO'}
if($DomainName -cnotmatch '^[a-zA-Z0-9-]+(\.[a-zA-Z0-9-]+)+$' -or -not $ProbeName.EndsWith('.'+$DomainName,[StringComparison]::OrdinalIgnoreCase)){throw 'Invalid AD DNS names'}
$machine=Get-CimInstance Win32_ComputerSystem
if($machine.DomainRole -notin @(4,5) -or $machine.Domain -ine $DomainName){throw 'Run only on the intended domain controller'}
$address=[Net.IPAddress]::Parse($InternalDns)
if($address.AddressFamily -ne [Net.Sockets.AddressFamily]::InterNetwork){throw 'Local IPv4 DNS address required'}
$interfaces=@(Get-NetIPAddress -IPAddress $InternalDns -AddressFamily IPv4)
if($interfaces.Count -ne 1){throw 'DNS IP must belong to exactly one local interface'}
if((Get-Service DNS).Status -ne 'Running'){throw 'Local DNS Server service is not running'}
$ip=$interfaces[0]
$dns=Get-DnsClientServerAddress -InterfaceIndex $ip.InterfaceIndex -AddressFamily IPv4
$old=@($dns.ServerAddresses)
$adapter=Get-NetAdapter -Name $ip.InterfaceAlias
$registry='HKLM:\SYSTEM\CurrentControlSet\Services\Tcpip\Parameters\Interfaces\'+([Guid]$adapter.InterfaceGuid).ToString('B')
$settings=Get-ItemProperty -LiteralPath $registry
$automatic=[string]::IsNullOrWhiteSpace([string]$settings.NameServer)
# Preflight local AD DNS and public recursion before writing any client setting.
$internal=@(Resolve-DnsName -Name $ProbeName -Type A -DnsOnly -Server $InternalDns)
$ldap=@(Resolve-DnsName -Name ('_ldap._tcp.dc._msdcs.'+$DomainName) -Type SRV -DnsOnly -Server $InternalDns)
$public=@(Resolve-DnsName -Name 'github.com' -Type A -DnsOnly -Server $InternalDns)
if(-not @($internal|Where-Object IPAddress).Count -or -not @($ldap|Where-Object NameTarget).Count -or -not @($public|Where-Object IPAddress).Count){throw 'Internal DNS preflight failed; client settings unchanged'}
Write-Output ('DNS_PREFLIGHT_OK interface='+$ip.InterfaceAlias+' old='+($old -join ',')+' proposed='+$InternalDns)
if(-not $Apply){Write-Output 'PLAN_ONLY: client settings unchanged';return}
$folder=Join-Path $PSScriptRoot 'dns-backups'
if(Test-Path -LiteralPath $folder){
    $item=Get-Item -Force -LiteralPath $folder
    $acl=Get-Acl -LiteralPath $folder
    $owner=(New-Object Security.Principal.NTAccount($acl.Owner)).Translate([Security.Principal.SecurityIdentifier]).Value
    if($item.Attributes -band [IO.FileAttributes]::ReparsePoint -or -not $acl.AreAccessRulesProtected -or $owner -ne 'S-1-5-32-544'){throw 'Unsafe DNS backup folder'}
}else{
    New-Item -ItemType Directory -Path $folder|Out-Null
    $acl=New-Object Security.AccessControl.DirectorySecurity
    $acl.SetAccessRuleProtection($true,$false)
    $acl.SetOwner((New-Object Security.Principal.SecurityIdentifier('S-1-5-32-544')))
    foreach($sid in @('S-1-5-18','S-1-5-32-544')){
        $acl.AddAccessRule((New-Object Security.AccessControl.FileSystemAccessRule((New-Object Security.Principal.SecurityIdentifier($sid)),'FullControl','ContainerInherit,ObjectInherit','None','Allow')))
    }
    Set-Acl -LiteralPath $folder -AclObject $acl
}
$backup=Join-Path $folder ('dns-client-'+[Guid]::NewGuid().ToString('N')+'.json')
[ordered]@{schema=1;computer=$env:COMPUTERNAME;interface_index=$ip.InterfaceIndex;interface_alias=$ip.InterfaceAlias;interface_guid=[string]$adapter.InterfaceGuid;family='IPv4';was_automatic=$automatic;servers=$old;proposed=$InternalDns;created_utc=[DateTime]::UtcNow.ToString('o')}|ConvertTo-Json -Depth 4|Set-Content -LiteralPath $backup -Encoding UTF8
Write-Output ('BACKUP='+$backup)
Invoke-DnsClientTransaction $dns $old $automatic $InternalDns $DomainName $ProbeName
