param([string]$OutputFile = "$env:USERPROFILE\Desktop\directory-inventory.json")
# Run locally on the authorized AD/DHCP/DNS server. Read-only queries only.
$ErrorActionPreference = 'Stop'
$result = [ordered]@{
    schema = 1
    collected_at = (Get-Date).ToUniversalTime().ToString('o')
    server = $env:COMPUTERNAME
    domain = ''
    netbios = ''
    computers = @()
    users = @()
    leases = @()
    dns = @()
    errors = @()
}
try {
    Import-Module ActiveDirectory
    $adDomain = Get-ADDomain
    $result.domain = $adDomain.DNSRoot
    $result.netbios = $adDomain.NetBIOSName
    $result.users = @(Get-ADUser -Filter * -Properties DisplayName,LastLogonDate | ForEach-Object {
        [ordered]@{ username=$_.SamAccountName; display_name=$_.DisplayName; enabled=$_.Enabled;
            last_logon=if ($_.LastLogonDate) { $_.LastLogonDate.ToUniversalTime().ToString('o') } else { $null } }
    })
    $result.computers = @(Get-ADComputer -Filter * -Properties DNSHostName,OperatingSystem,LastLogonDate | ForEach-Object {
        [ordered]@{ name=$_.Name; fqdn=$_.DNSHostName; os=$_.OperatingSystem; enabled=$_.Enabled;
            last_logon=if ($_.LastLogonDate) { $_.LastLogonDate.ToUniversalTime().ToString('o') } else { $null } }
    })
} catch { $result.errors += 'AD: sorgu başarısız; modül ve okuma yetkisini kontrol edin.' }
try {
    Import-Module DhcpServer
    $result.leases = @(Get-DhcpServerv4Scope | ForEach-Object {
        Get-DhcpServerv4Lease -ScopeId $_.ScopeId -AllLeases | ForEach-Object {
            [ordered]@{ ip=$_.IPAddress.IPAddressToString; mac=[string]$_.ClientId; hostname=$_.HostName;
                state=[string]$_.AddressState; expires=if ($_.LeaseExpiryTime) { $_.LeaseExpiryTime.ToUniversalTime().ToString('o') } else { $null } }
        }
    })
} catch { $result.errors += 'DHCP: hizmet/modül bulunamadı veya okuma yetkisi yok.' }
try {
    Import-Module DnsServer
    $result.dns = @(Get-DnsServerZone | Where-Object { -not $_.IsReverseLookupZone } | ForEach-Object {
        $zone = $_.ZoneName
        Get-DnsServerResourceRecord -ZoneName $zone -RRType A | ForEach-Object {
            [ordered]@{ fqdn=if ($_.HostName -eq '@') { $zone } else { $_.HostName+'.'+$zone };
                ip=$_.RecordData.IPv4Address.IPAddressToString }
        }
    })
} catch { $result.errors += 'DNS: hizmet/modül bulunamadı veya okuma yetkisi yok.' }
$result | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $OutputFile -Encoding UTF8
Write-Host "Dosya oluşturuldu: $OutputFile"
Write-Host "AD: $($result.computers.Count) / DHCP: $($result.leases.Count) / DNS: $($result.dns.Count)"
foreach ($item in $result.errors) { Write-Warning $item }
