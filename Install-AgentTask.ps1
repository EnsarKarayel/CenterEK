param([Parameter(Mandatory=$true)][string]$AgentConfig)
$ErrorActionPreference='Stop'
$path=(Resolve-Path -LiteralPath $AgentConfig).Path
$config=Get-Content -LiteralPath $path -Raw | ConvertFrom-Json
$identity=[Security.Principal.WindowsIdentity]::GetCurrent().Name
$name='CenterEK-'+$config.kind
if (Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue) { throw "Görev zaten var: $name" }
if ($config.kind -eq 'endpoint') {
    $script=Join-Path $PSScriptRoot 'Collect-EndpointSessions.ps1'
} elseif ($config.kind -eq 'directory') {
    $script=Join-Path $PSScriptRoot 'Send-DirectoryInventory.ps1'
} else { throw 'Geçersiz ajan türü' }
$arguments='-NoProfile -File "'+$script+'" -AgentConfig "'+$path+'" -Watch'
$action=New-ScheduledTaskAction -Execute 'powershell.exe' -Argument $arguments -WorkingDirectory $PSScriptRoot
$trigger=New-ScheduledTaskTrigger -AtLogOn -User $identity
$principal=New-ScheduledTaskPrincipal -UserId $identity -LogonType Interactive -RunLevel Limited
$settings=New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -MultipleInstances IgnoreNew -StartWhenAvailable
Register-ScheduledTask -TaskName $name -Action $action -Trigger $trigger -Principal $principal -Settings $settings | Out-Null
Start-ScheduledTask -TaskName $name
Write-Host "Görev oluşturuldu: $name. Mevcut kullanıcı oturum açtığında çalışır; kullanıcı oturumu kapalıyken çalışmaz."
