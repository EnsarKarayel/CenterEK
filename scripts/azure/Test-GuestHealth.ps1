$ErrorActionPreference='Stop'
[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12
$network=Get-Content -LiteralPath 'C:\CenterEK\server.local.json' -Raw|ConvertFrom-Json
$address=[Net.IPAddress]::Parse($network.bind)
$port=[int]$network.port
if($address.AddressFamily -ne [Net.Sockets.AddressFamily]::InterNetwork -or $port -lt 1024 -or $port -gt 65535){throw 'Invalid private application target'}
$url='https://'+$address.ToString()+':'+$port+'/healthz'
$response=Invoke-RestMethod -Uri $url -TimeoutSec 10
if($response.status -ne 'ok'){throw 'Application is unavailable'}
Write-Output 'CENTEREK_HEALTH_OK'
