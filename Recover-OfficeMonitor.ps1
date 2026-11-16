param([string]$Root='C:\CenterEK',[string]$PythonPath='C:\Program Files\Python311\python.exe')
$ErrorActionPreference='Stop'
function Test-OwnedMonitorProcess($Process,[string]$Root){
    $rootPath=[IO.Path]::GetFullPath($Root).TrimEnd('\')
    $options=[Text.RegularExpressions.RegexOptions]::IgnoreCase -bor [Text.RegularExpressions.RegexOptions]::CultureInvariant
    $command=[string]$Process.CommandLine
    if($Process.Name -in @('python.exe','pythonw.exe')){
        $entry=[Regex]::Escape((Join-Path $rootPath 'start.py'))
        return [Regex]::IsMatch($command,('^\s*(?:"[^"]+"|[^\s"]+)\s+(?:-u\s+)?(?:"'+$entry+'"|'+$entry+')(?=\s|$)'),$options)
    }
    if($Process.Name -in @('powershell.exe','pwsh.exe')){
        $entry=[Regex]::Escape((Join-Path $rootPath 'Run-SystemTask.ps1'))
        return -not [Regex]::IsMatch($command,'(?:^|\s)-(?:Command|EncodedCommand)(?:\s|$)',$options) -and [Regex]::IsMatch($command,('(?:^|\s)-File\s+(?:"'+$entry+'"|'+$entry+')(?=\s|$)'),$options) -and [Regex]::IsMatch($command,'(?:^|\s)-Mode\s+"?Server"?(?=\s|$)',$options)
    }
    return $false
}
$identity=[Security.Principal.WindowsIdentity]::GetCurrent()
if(-not(New-Object Security.Principal.WindowsPrincipal($identity)).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){throw 'Administrator CMD required on 1.15'}
$rootPath=(Resolve-Path -LiteralPath $Root).Path.TrimEnd('\')
if($rootPath -ieq [IO.Path]::GetPathRoot($rootPath).TrimEnd('\') -or (Get-Item -Force -LiteralPath $rootPath).Attributes -band [IO.FileAttributes]::ReparsePoint){throw 'Dedicated non-reparse monitor root required'}
$name='CenterEK-Server-System'
$task=Get-ScheduledTask -TaskName $name
$actions=@($task.Actions)
if($actions.Count -ne 1 -or $task.Principal.UserId -notin @('SYSTEM','S-1-5-18','NT AUTHORITY\SYSTEM') -or -not(Test-OwnedMonitorProcess ([pscustomobject]@{Name='powershell.exe';CommandLine=('"'+$actions[0].Execute+'" '+$actions[0].Arguments)}) $rootPath)){throw 'Task does not belong to this monitor installation'}
if($task.State -eq 'Disabled'){throw 'Intentionally disabled task preserved'}
foreach($file in @('start.py','Run-SystemTask.ps1','data\monitor.sqlite3')){if(-not(Test-Path -LiteralPath (Join-Path $rootPath $file))){throw ('Missing monitor component: '+$file)}}
if(-not(Test-Path -LiteralPath $PythonPath)){throw 'Existing Python installation required'}
# Refuse to interrupt an unrelated application that happens to own this port.
foreach($connection in @(Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue)){
    $process=Get-CimInstance Win32_Process -Filter ('ProcessId='+$connection.OwningProcess)
    if(-not(Test-OwnedMonitorProcess $process $rootPath)){throw 'Port 8765 has an unrelated owner; nothing stopped'}
}
$backup=Join-Path $rootPath ('data\monitor-recovery-'+[Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $backup|Out-Null
$backupAcl=New-Object Security.AccessControl.DirectorySecurity
$backupAcl.SetAccessRuleProtection($true,$false)
$backupAcl.SetOwner((New-Object Security.Principal.SecurityIdentifier('S-1-5-32-544')))
foreach($sid in @('S-1-5-18','S-1-5-32-544')){$backupAcl.AddAccessRule((New-Object Security.AccessControl.FileSystemAccessRule((New-Object Security.Principal.SecurityIdentifier($sid)),'FullControl','ContainerInherit,ObjectInherit','None','Allow')))}
Set-Acl -LiteralPath $backup -AclObject $backupAcl
Export-ScheduledTask -TaskName $name|Set-Content -LiteralPath (Join-Path $backup 'task-before.xml') -Encoding UTF8
$backupProgram=@'
import sqlite3,sys,time
from contextlib import closing
deadline=time.monotonic()+60
def progress(status, remaining, total):
    if time.monotonic()>deadline: raise TimeoutError('backup deadline')
with closing(sqlite3.connect(sys.argv[1],timeout=5)) as source:
    if source.execute('PRAGMA quick_check').fetchone()[0]!='ok': raise RuntimeError('source integrity check failed')
    with closing(sqlite3.connect(sys.argv[2])) as target:
        source.backup(target,pages=128,progress=progress,sleep=0.05)
        if target.execute('PRAGMA quick_check').fetchone()[0]!='ok': raise RuntimeError('backup integrity check failed')
print('DATABASE_BACKUP_OK',flush=True)
'@
[IO.File]::WriteAllText((Join-Path $backup 'backup.py'),$backupProgram,[Text.UTF8Encoding]::new($false))
Write-Output ('RECOVERY_BACKUP='+$backup)
Disable-ScheduledTask -TaskName $name|Out-Null
Stop-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2
try{
    # Only exact-root server wrappers and direct start.py processes. No wildcard
    # taskkill, other Python applications, SQL services or lock-file deletion.
    foreach($kind in @('wrapper','python')){
        $processes=@(Get-CimInstance Win32_Process -Filter "Name='powershell.exe' OR Name='pwsh.exe' OR Name='python.exe' OR Name='pythonw.exe'")
        foreach($process in $processes){
            $isPython=$process.Name -in @('python.exe','pythonw.exe')
            if(($kind -eq 'python') -ne $isPython){continue}
            if(Test-OwnedMonitorProcess $process $rootPath){
                $current=Get-CimInstance Win32_Process -Filter ('ProcessId='+$process.ProcessId) -ErrorAction SilentlyContinue
                if($current -and $current.CreationDate -eq $process.CreationDate -and (Test-OwnedMonitorProcess $current $rootPath)){Stop-Process -Id $current.ProcessId -Force;Write-Output ('STOPPED_OWN_MONITOR_PID='+$current.ProcessId)}
            }
        }
    }
    Start-Sleep -Seconds 2
    if(@(Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue).Count){throw 'A listener remains after owned-process cleanup; no new instance started'}
    $arguments=@(('"'+(Join-Path $backup 'backup.py')+'"'),('"'+(Join-Path $rootPath 'data\monitor.sqlite3')+'"'),('"'+(Join-Path $backup 'monitor.sqlite3')+'"'))
    $process=[Diagnostics.Process]::new()
    $process.StartInfo=[Diagnostics.ProcessStartInfo]::new($PythonPath,($arguments -join ' '))
    $process.StartInfo.WorkingDirectory=$rootPath
    $process.StartInfo.UseShellExecute=$false;$process.StartInfo.CreateNoWindow=$true
    $process.StartInfo.WindowStyle=[Diagnostics.ProcessWindowStyle]::Hidden
    $process.StartInfo.RedirectStandardOutput=$true;$process.StartInfo.RedirectStandardError=$true
    try{
        [void]$process.Start()
        if(-not $process.WaitForExit(90000)){$process.Kill();throw 'Database backup timed out'}
        [IO.File]::WriteAllText((Join-Path $backup 'backup.log'),$process.StandardOutput.ReadToEnd())
        [IO.File]::WriteAllText((Join-Path $backup 'backup-error.log'),$process.StandardError.ReadToEnd())
        if($process.ExitCode -ne 0){throw ('Database integrity/backup failed; private diagnostic: '+$backup)}
    }finally{$process.Dispose()}
    Write-Output 'DATABASE_BACKUP_OK'
    $settings=$task.Settings
    $settings.ExecutionTimeLimit='PT0S';$settings.MultipleInstances=2
    Set-ScheduledTask -TaskName $name -Settings $settings|Out-Null
    Enable-ScheduledTask -TaskName $name|Out-Null
    Start-ScheduledTask -TaskName $name
    Start-Sleep -Seconds 8
    $listeners=@(Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue)
    $owners=@($listeners.OwningProcess|Sort-Object -Unique)
    Write-Output ('LISTENER_PROCESS_COUNT='+$owners.Count)
    $listeners|Select-Object LocalAddress,LocalPort,OwningProcess|Format-Table -AutoSize
    if($owners.Count -ne 1){throw 'Expected one server listener; inspect server log before claiming recovery'}
    Write-Output 'MONITOR_SINGLE_INSTANCE_RESTORED: verify agent HTTP ingestion and fresh cloud source timestamps.'
}catch{
    # Keep a failed cleanup/integrity phase stopped rather than racing another
    # writer. Do not delete/replace the database or automatically restore it.
    Write-Output ('RECOVERY_FAILED: inspect task state and backup diagnostics at '+$backup)
    throw
}
