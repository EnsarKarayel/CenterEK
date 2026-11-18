param([string]$RelayRoot='C:\CenterEK-Relay')
# Preserve enrollment, task action/principal, source app and running process.
$ErrorActionPreference='Stop'
function Assert-RelayTaskIdentity($Task,[string]$Root){
    $actions=@($Task.Actions)
    $exe=Join-Path $env:WINDIR 'System32\WindowsPowerShell\v1.0\powershell.exe'
    $wrapper=Join-Path ([IO.Path]::GetFullPath($Root)) 'Run-SiteRelay.ps1'
    if($Task.TaskName -ne 'CenterEK-OfficeRelay-System' -or $Task.Principal.UserId -notin @('SYSTEM','S-1-5-18','NT AUTHORITY\SYSTEM') -or $actions.Count -ne 1 -or $actions[0].Execute -ine $exe -or $actions[0].Arguments.IndexOf(('-File "'+$wrapper+'"'),[StringComparison]::OrdinalIgnoreCase) -lt 0 -or $actions[0].Arguments -match '(?:^|\s)-(?:EncodedCommand|Command)(?:\s|$)'){
        throw 'Unexpected task action/account preserved; manual review required'
    }
}
function New-RelayTaskPatch($Task){
    $triggers=@($Task.Triggers)
    $marker=@($triggers|Where-Object {$_.Id -eq 'CenterEKRelayRecoveryV1'})
    if($marker.Count -gt 1 -or ($marker.Count -and ($marker[0].Repetition.Interval -ne 'PT5M' -or -not $marker[0].Enabled))){throw 'Unexpected recovery trigger preserved'}
    if(-not $marker.Count){
        $namespace='Root/Microsoft/Windows/TaskScheduler'
        $repeat=New-CimInstance -Namespace $namespace -ClassName MSFT_TaskRepetitionPattern -ClientOnly -Property @{Interval='PT5M';StopAtDurationEnd=$false}
        $recovery=New-CimInstance -Namespace $namespace -ClassName MSFT_TaskTimeTrigger -ClientOnly -Property @{Id='CenterEKRelayRecoveryV1';Enabled=$true;StartBoundary=(Get-Date).AddMinutes(5).ToString('yyyy-MM-ddTHH:mm:ss');Repetition=$repeat}
        $recovery.PSObject.TypeNames.Add('Microsoft.Management.Infrastructure.CimInstance#MSFT_TaskTrigger')
        $triggers+=$recovery
    }
    $Task.Settings.ExecutionTimeLimit='PT0S'
    $Task.Settings.MultipleInstances=2 # IgnoreNew: a running relay is not duplicated.
    [pscustomobject]@{Settings=$Task.Settings;Triggers=$triggers}
}
$identity=[Security.Principal.WindowsIdentity]::GetCurrent()
if(-not(New-Object Security.Principal.WindowsPrincipal($identity)).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){throw 'Administrator CMD required on the relay server'}
$root=(Resolve-Path -LiteralPath $RelayRoot).Path
if((Get-Item -Force -LiteralPath $root).Attributes -band [IO.FileAttributes]::ReparsePoint){throw 'Unsafe relay path'}
$name='CenterEK-OfficeRelay-System'
$task=Get-ScheduledTask -TaskName $name
Assert-RelayTaskIdentity $task $root
$folder=Join-Path $root 'data\task-backups'
New-Item -ItemType Directory -Path $folder -Force|Out-Null
if((Get-Item -Force -LiteralPath $folder).Attributes -band [IO.FileAttributes]::ReparsePoint){throw 'Unsafe backup path'}
$backup=Join-Path $folder ('office-relay-'+[Guid]::NewGuid().ToString('N')+'.xml')
Export-ScheduledTask -TaskName $name|Set-Content -LiteralPath $backup -Encoding UTF8
Write-Output ('TASK_BACKUP='+$backup)
$patch=New-RelayTaskPatch $task
Set-ScheduledTask -TaskName $name -Settings $patch.Settings -Trigger $patch.Triggers|Out-Null
$current=Get-ScheduledTask -TaskName $name
if([Xml.XmlConvert]::ToTimeSpan($current.Settings.ExecutionTimeLimit) -ne [TimeSpan]::Zero -or $current.Settings.MultipleInstances -ne 2 -or @($current.Triggers|Where-Object {$_.Id -eq 'CenterEKRelayRecoveryV1' -and $_.Enabled -and $_.Repetition.Interval -eq 'PT5M'}).Count -ne 1){throw ('Task update verification failed; original XML retained: '+$backup)}
if($current.State -ne 'Running'){Start-ScheduledTask -TaskName $name}
Write-Output 'RELAY_TASK_REPAIRED: execution limit removed; five-minute recovery; existing running instance preserved.'
Get-ScheduledTask -TaskName 'CenterEK-*'|Select-Object TaskName,State,@{Name='ExecutionTimeLimit';Expression={$_.Settings.ExecutionTimeLimit}}
