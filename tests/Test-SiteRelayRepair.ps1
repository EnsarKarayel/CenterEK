$ErrorActionPreference='Stop'
$tokens=$null;$errors=$null
$ast=[Management.Automation.Language.Parser]::ParseFile((Join-Path (Split-Path -Parent $PSScriptRoot) 'Repair-SiteRelayTask.ps1'),[ref]$tokens,[ref]$errors)
if($errors){throw 'Repair parse failure'}
foreach($name in @('Assert-RelayTaskIdentity','New-RelayTaskPatch')){
    $function=$ast.Find({param($node) $node -is [Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq $name},$true)
    . ([scriptblock]::Create($function.Extent.Text))
}
# Construct real client-only Task Scheduler CIM types. Never query or change an
# installed task and never read enrollment/credential files.
$settings=New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Hours 72) -MultipleInstances Parallel -Priority 7
$boot=New-ScheduledTaskTrigger -AtStartup
$task=[pscustomobject]@{TaskName='CenterEK-OfficeRelay-System';Settings=$settings;Triggers=@($boot);Principal=[pscustomobject]@{UserId='SYSTEM'};Actions=@([pscustomobject]@{Execute=(Join-Path $env:WINDIR 'System32\WindowsPowerShell\v1.0\powershell.exe');Arguments='-NoProfile -WindowStyle Hidden -File "C:\CenterEK-Relay\Run-SiteRelay.ps1" -SourceRoot "C:\CenterEK"'})}
Assert-RelayTaskIdentity $task 'C:\CenterEK-Relay'
$patch=New-RelayTaskPatch $task
if($patch.Settings.ExecutionTimeLimit -ne 'PT0S' -or $patch.Settings.MultipleInstances -ne 2 -or $patch.Settings.Priority -ne 7){throw 'Settings patch replaced unrelated settings'}
if($patch.Triggers.Count -ne 2 -or $patch.Triggers[0] -ne $boot){throw 'Original startup trigger was not preserved'}
$recovery=$patch.Triggers[1]
if($recovery.Id -ne 'CenterEKRelayRecoveryV1' -or $recovery.Repetition.Interval -ne 'PT5M' -or $recovery.Repetition.StopAtDurationEnd -or -not $recovery.Enabled){throw 'Recovery trigger incorrect'}
$task.Triggers=$patch.Triggers
$again=New-RelayTaskPatch $task
if($again.Triggers.Count -ne 2){throw 'Repair duplicated the recovery trigger'}
Write-Output 'PASS real CIM unlimited runtime, startup preservation, recovery and idempotence'
$task.Principal.UserId='OTHER'
$blocked=$false;try{Assert-RelayTaskIdentity $task 'C:\CenterEK-Relay'}catch{$blocked=$true}
if(-not $blocked){throw 'Other-account task was accepted'}
$task.Principal.UserId='SYSTEM';$task.Actions[0].Arguments='-File "C:\Other\Run-SiteRelay.ps1"'
$blocked=$false;try{Assert-RelayTaskIdentity $task 'C:\CenterEK-Relay'}catch{$blocked=$true}
if(-not $blocked){throw 'Other installation task was accepted'}
$task.Actions[0].Arguments='-Command anything -File "C:\CenterEK-Relay\Run-SiteRelay.ps1"'
$blocked=$false;try{Assert-RelayTaskIdentity $task 'C:\CenterEK-Relay'}catch{$blocked=$true}
if(-not $blocked){throw 'Unexpected inline task was accepted'}
Write-Output 'PASS task account/action/path validation'
