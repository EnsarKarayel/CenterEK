param([Parameter(Mandatory=$true)][string]$Root,
      [Parameter(Mandatory=$true)][ValidateSet('Stop','Resume','Remove')][string]$Action,
      [Parameter(Mandatory=$true)][string]$StateFile)
$ErrorActionPreference='Stop'
$identity=[Security.Principal.WindowsIdentity]::GetCurrent()
if(-not (New-Object Security.Principal.WindowsPrincipal($identity)).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){throw 'Administrator permission required'}
$Root=[IO.Path]::GetFullPath($Root).TrimEnd('\')
if($Root -eq [IO.Path]::GetPathRoot($Root).TrimEnd('\')){throw 'Dedicated installation required'}
$wrapper=Join-Path $Root 'Run-SystemTask.ps1'
$exe=Join-Path $Root 'CenterEK.exe'
$names=@('CenterEK-Server-System','CenterEK-Endpoint-System','CenterEK-Directory-System')
function Assert-Owned($task){
    if($task.Principal.UserId -notin @('SYSTEM','S-1-5-18','NT AUTHORITY\SYSTEM')){throw 'Task principal mismatch'}
    if(@($task.Actions).Count -ne 1){throw 'Unexpected task actions'}
    $a=$task.Actions[0]
    $expected=Join-Path $env:WINDIR 'System32\WindowsPowerShell\v1.0\powershell.exe'
    if($a.Execute -ine $expected -or $a.WorkingDirectory -ine $Root){throw 'Task executable/root mismatch'}
    if($a.Arguments -match '(?i)-(?:Command|EncodedCommand|EncodedArguments)\b' -or
       @([regex]::Matches($a.Arguments,'(?i)(?:^|\s)-File\s')).Count -ne 1){throw 'Unexpected task command'}
    if($a.Arguments -notmatch ('(?i)-File\s+"'+[regex]::Escape($wrapper)+'"(?:\s|$)') -or
       $a.Arguments -notmatch ('(?i)-ServerExecutable\s+"'+[regex]::Escape($exe)+'"(?:\s|$)')){throw 'Task is not owned by this packaged installation'}
}
function Test-OwnedMaintenanceProcess($process){
    if(-not $process.ExecutablePath -or -not $process.CommandLine){return $false}
    if($process.ExecutablePath -ieq $exe){
        return ($process.CommandLine -match ('(?i)(?:^|\s)--serve\s+--root\s+"'+[regex]::Escape($Root)+'"(?:\s|$)'))
    }
    if($process.ExecutablePath -ine (Join-Path $env:WINDIR 'System32\WindowsPowerShell\v1.0\powershell.exe')){return $false}
    if($process.CommandLine -match '(?i)-(?:Command|EncodedCommand|EncodedArguments)\b'){return $false}
    foreach($script in @('Run-SystemTask.ps1','Collect-EndpointSessions.ps1','Send-DirectoryInventory.ps1')){
        if($process.CommandLine -match ('(?i)-File\s+"'+[regex]::Escape((Join-Path $Root $script))+'"(?:\s|$)')){return $true}
    }
    return $false
}
function Assert-TaskXml([string]$xml){
    $document=New-Object Xml.XmlDocument
    $document.XmlResolver=$null
    $document.LoadXml($xml)
    if(@($document.Task.Actions.ChildNodes).Count -ne 1 -or -not $document.Task.Actions.Exec){throw 'Unexpected XML task actions'}
    if(@($document.Task.Principals.Principal).Count -ne 1){throw 'Unexpected XML principals'}
    $entry=$document.Task.Actions.Exec
    Assert-Owned ([pscustomobject]@{Principal=[pscustomobject]@{UserId=$document.Task.Principals.Principal.UserId};Actions=@([pscustomobject]@{Execute=$entry.Command;Arguments=$entry.Arguments;WorkingDirectory=$entry.WorkingDirectory})})
}
function Convert-TaskState([string]$Json){
    # Windows PowerShell 5.1 emits a JSON array as one pipeline object.
    # Assign first, then enumerate explicitly to handle zero/one/many tasks.
    $decoded=ConvertFrom-Json -InputObject $Json
    foreach($entry in @($decoded)){$entry}
}
# Validate every matching task before making any change.
$tasks=@(foreach($name in $names){$t=Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue;if($t){Assert-Owned $t;$t}})
if($Action -eq 'Stop'){
    $state=@(foreach($t in $tasks){[ordered]@{name=$t.TaskName;enabled=[bool]$t.Settings.Enabled;xml=(Export-ScheduledTask -TaskName $t.TaskName)}})
    if(Test-Path -LiteralPath $StateFile){throw 'State file already exists'}
    ConvertTo-Json -InputObject $state -Depth 5 | Set-Content -LiteralPath $StateFile -Encoding UTF8
    foreach($t in $tasks){Disable-ScheduledTask -TaskName $t.TaskName|Out-Null}
    foreach($t in $tasks){Stop-ScheduledTask -TaskName $t.TaskName}
    # Stopping the wrapper can leave children behind. Match exact installation paths.
    foreach($p in @(Get-CimInstance Win32_Process)){
        if(Test-OwnedMaintenanceProcess $p){
            $current=Get-CimInstance Win32_Process -Filter ('ProcessId='+$p.ProcessId) -ErrorAction SilentlyContinue
            if($current -and $current.CreationDate -eq $p.CreationDate -and (Test-OwnedMaintenanceProcess $current)){
                Stop-Process -Id $p.ProcessId -Force -ErrorAction Stop
            }
        }
    }
    Start-Sleep -Milliseconds 500
    if(@(Get-CimInstance Win32_Process|Where-Object {$_.ExecutablePath -and $_.ExecutablePath -ieq $exe}).Count){throw 'Application did not stop'}
    return
}
$state=@(Convert-TaskState ([IO.File]::ReadAllText($StateFile)))
$seen=@{}
foreach($s in $state){
    if($s.name -notin $names -or $seen.ContainsKey($s.name)){throw 'Invalid task state'}
    $seen[$s.name]=$true
    Assert-TaskXml $s.xml
}
if($Action -eq 'Remove'){
    foreach($t in $tasks){Unregister-ScheduledTask -TaskName $t.TaskName -Confirm:$false}
}else{
    foreach($s in $state){
        Register-ScheduledTask -TaskName $s.name -Xml $s.xml -Force|Out-Null
        $restored=Get-ScheduledTask -TaskName $s.name
        Assert-Owned $restored
        if($s.enabled){Enable-ScheduledTask -TaskName $s.name|Out-Null;Start-ScheduledTask -TaskName $s.name}
        else{Disable-ScheduledTask -TaskName $s.name|Out-Null}
    }
}
