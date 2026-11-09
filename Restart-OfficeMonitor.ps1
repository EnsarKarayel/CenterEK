param([Parameter(Mandatory=$true)][string]$Root)
$ErrorActionPreference='Stop'
$rootPath=(Resolve-Path -LiteralPath $Root).Path
$wrapper=Join-Path $rootPath 'Run-SystemTask.ps1'
$name='CenterEK-Server-System'
$task=Get-ScheduledTask -TaskName $name
if(-not @($task.Actions|Where-Object {$_.Arguments -and $_.Arguments.IndexOf($wrapper,[StringComparison]::OrdinalIgnoreCase) -ge 0}).Count){throw 'Task does not belong to this installation'}
$start=Join-Path $rootPath 'start.py'
$pattern='(?i)(?:^|[\s"])'+[Regex]::Escape($start)+'(?=["\s]|$)'
Stop-ScheduledTask -TaskName $name
Start-Sleep -Seconds 2
Get-CimInstance Win32_Process -Filter "Name='python.exe'"|Where-Object {$_.CommandLine -match $pattern}|ForEach-Object {Stop-Process -Id $_.ProcessId -Force}
Start-ScheduledTask -TaskName $name
Write-Output 'Only the matching CenterEK monitor task was restarted.'
