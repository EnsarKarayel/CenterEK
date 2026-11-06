param([string]$Address,[int]$Port,[switch]$CheckDirectory,[switch]$CheckTasks)
$ErrorActionPreference='Stop'
if($CheckTasks){
    foreach($mode in @('Server','Endpoint','Directory')){
        if(Get-ScheduledTask -TaskName ('CenterEK-'+$mode+'-System') -ErrorAction SilentlyContinue){throw 'Mevcut CenterEK görevi bulundu; temiz kurulum üzerine yazmaz.'}
    }
    return
}
if($CheckDirectory){
    if(-not(Get-Module -ListAvailable ActiveDirectory)){throw 'ActiveDirectory modülü bulunamadı; AD rolü seçilmeden kurulabilir.'}
    return
}
if(-not $Address -or $Port -lt 1024 -or $Port -gt 65535){throw 'Geçersiz ağ ayarı.'}
$parsed=[Net.IPAddress]::Parse($Address)
if([Net.IPAddress]::IsLoopback($parsed) -or $parsed.ToString() -eq '0.0.0.0'){throw 'Belirli LAN adresi gerekli.'}
$ruleName='CenterEK-Panel-'+$Port
if(Get-NetFirewallRule -Name $ruleName -ErrorAction SilentlyContinue){throw 'Aynı isimde güvenlik duvarı kuralı var; değiştirilmedi.'}
New-NetFirewallRule -Name $ruleName -DisplayName ('CenterEK HTTPS '+$Port) -Direction Inbound -Action Allow -Protocol TCP -LocalPort $Port -LocalAddress $Address -RemoteAddress LocalSubnet -Profile Domain,Private | Out-Null
