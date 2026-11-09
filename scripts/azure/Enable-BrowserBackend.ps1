# Run on the staging VM only, after the separately approved gateway deployment.
$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest
$network=Get-Content -LiteralPath 'C:\CenterEK\server.local.json' -Raw|ConvertFrom-Json
if($network.bind -ne '10.42.1.4' -or [int]$network.port -ne 8765){throw 'Unexpected private backend; firewall unchanged'}
if(-not $network.tls_cert -or -not $network.tls_key){throw 'HTTPS backend required'}
$name='CenterEK-Azure-BrowserGateway'
$existing=Get-NetFirewallRule -Name $name -ErrorAction SilentlyContinue
if($existing){
    Set-NetFirewallRule -Name $name -Enabled True -Direction Inbound -Action Allow -Protocol TCP -LocalAddress '10.42.1.4' -LocalPort 8765 -RemoteAddress '10.43.0.0/23' -Profile Any|Out-Null
}else{
    New-NetFirewallRule -Name $name -DisplayName 'CenterEK authenticated browser gateway' -Direction Inbound -Action Allow -Protocol TCP -LocalAddress '10.42.1.4' -LocalPort 8765 -RemoteAddress '10.43.0.0/23' -Profile Any|Out-Null
}
$rule=Get-NetFirewallRule -Name $name
$addresses=$rule|Get-NetFirewallAddressFilter
$ports=$rule|Get-NetFirewallPortFilter
# Windows normalizes CIDR prefixes to dotted netmasks on some versions.
$remote=@($addresses.RemoteAddress)
$local=@($addresses.LocalAddress)
if($remote.Count -ne 1 -or $remote[0] -notin @('10.43.0.0/23','10.43.0.0/255.255.254.0') -or $local.Count -ne 1 -or $local[0] -ne '10.42.1.4' -or [string]$ports.LocalPort -ne '8765' -or [string]$ports.Protocol -ne 'TCP' -or $rule.Action -ne 'Allow' -or $rule.Enabled -ne 'True' -or $rule.Direction -ne 'Inbound'){throw 'Gateway firewall verification failed'}
Write-Output 'CENTEREK_PRIVATE_GATEWAY_FIREWALL_OK'
