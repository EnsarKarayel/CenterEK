param(
    [string[]]$ComputerName,
    [switch]$Apply,
    [ValidateRange(1,8)][int]$Throttle=4,
    [ValidateRange(30,240)][int]$TimeoutSeconds=120,
    [string]$ShareName='CenterEKDeploy$'
)
# Run locally on the distribution server as an authorized domain administrator.
# No passwords, execution-policy bypass, firewall changes, or endpoint reboot.
$ErrorActionPreference='Stop'
Import-Module ActiveDirectory
$identity=[Security.Principal.WindowsIdentity]::GetCurrent()
if(-not(New-Object Security.Principal.WindowsPrincipal($identity)).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){throw 'Administrator required'}
$domain=Get-ADDomain
$share=Get-SmbShare -Name $ShareName
$expected=Join-Path $env:ProgramData 'CenterEK-DomainDistribution'
if($share.Path.TrimEnd('\') -ine $expected -or -not $share.EncryptData){throw 'Expected protected encrypted distribution share was not found'}
if((Get-Item -Force -LiteralPath $expected).Attributes -band [IO.FileAttributes]::ReparsePoint){throw 'Unsafe distribution path'}
$server=$env:COMPUTERNAME+'.'+$domain.DNSRoot
$origin='\\'+$server+'\'+$ShareName
$startup=$origin+'\Start-DomainEndpoint.ps1'
if(-not(Test-Path -LiteralPath (Join-Path $expected 'Start-DomainEndpoint.ps1'))){throw 'Startup script missing'}
$all=@(Get-ADComputer -Filter * -Properties Enabled,OperatingSystem,DNSHostName)
if($ComputerName){
    foreach($name in $ComputerName){if($name -cnotmatch '^[A-Za-z0-9][A-Za-z0-9-]{0,14}$'){throw 'Invalid requested computer name'}}
    $all=@($all|Where-Object {$ComputerName -icontains $_.Name})
    if($all.Count -ne @($ComputerName|Sort-Object -Unique).Count){throw 'Requested computer absent or ambiguous in AD'}
}
$targets=@($all|Where-Object {$_.Enabled -and $_.OperatingSystem -cmatch '^Windows (8|10|11)(\b|\.)' -and $_.Name -cmatch '^[A-Za-z0-9][A-Za-z0-9-]{0,14}$' -and $_.DNSHostName -ieq ($_.Name+'.'+$domain.DNSRoot)}|Sort-Object Name)
if($ComputerName -and $targets.Count -ne $all.Count){throw 'Requested target is not an enabled supported domain workstation'}
if(-not $Apply){
    $targets|Select-Object Name,DNSHostName,@{Name='Package';Expression={Test-Path -LiteralPath (Join-Path $expected ('packages\'+$_.Name+'\enrollment.local.json'))}}
    Write-Output 'PLAN_ONLY: use -Apply to request remote installation'
    return
}
function Protect-Folder([string]$Path,[string]$ReadSid,[bool]$Modify=$false){
    if(Test-Path -LiteralPath $Path){throw ('Existing run directory preserved: '+$Path)}
    New-Item -ItemType Directory -Path $Path|Out-Null
    $acl=New-Object Security.AccessControl.DirectorySecurity
    $acl.SetAccessRuleProtection($true,$false)
    $acl.SetOwner((New-Object Security.Principal.SecurityIdentifier('S-1-5-32-544')))
    foreach($sid in @('S-1-5-18','S-1-5-32-544')){
        $acl.AddAccessRule((New-Object Security.AccessControl.FileSystemAccessRule((New-Object Security.Principal.SecurityIdentifier($sid)),'FullControl','ContainerInherit,ObjectInherit','None','Allow')))
    }
    if($ReadSid){
        $rights=if($Modify){'Modify'}else{'ReadAndExecute'}
        $inherit=if($Modify){'ContainerInherit,ObjectInherit'}else{'None'}
        $acl.AddAccessRule((New-Object Security.AccessControl.FileSystemAccessRule((New-Object Security.Principal.SecurityIdentifier($ReadSid)),$rights,$inherit,'None','Allow')))
    }
    Set-Acl -LiteralPath $Path -AclObject $acl
}
$logShareName='CenterEKDeployLogs$'
$logRoot=Join-Path $env:ProgramData 'CenterEK-DeploymentReceipts'
$logShare=Get-SmbShare -Name $logShareName -ErrorAction SilentlyContinue
if($logShare){
    if($logShare.Path.TrimEnd('\') -ine $logRoot -or -not $logShare.EncryptData){throw 'Existing diagnostic share has unexpected settings'}
    $logAcl=Get-Acl -LiteralPath $logRoot
    $owner=(New-Object Security.Principal.NTAccount($logAcl.Owner)).Translate([Security.Principal.SecurityIdentifier]).Value
    if($owner -ne 'S-1-5-32-544' -or -not $logAcl.AreAccessRulesProtected -or ((Get-Item -Force -LiteralPath $logRoot).Attributes -band [IO.FileAttributes]::ReparsePoint)){throw 'Unsafe diagnostic root'}
}else{
    Protect-Folder $logRoot ($domain.DomainSID.Value+'-515')
    $reader=(New-Object Security.Principal.SecurityIdentifier($domain.DomainSID.Value+'-515')).Translate([Security.Principal.NTAccount]).Value
    $admins=(New-Object Security.Principal.SecurityIdentifier('S-1-5-32-544')).Translate([Security.Principal.NTAccount]).Value
    New-SmbShare -Name $logShareName -Path $logRoot -ChangeAccess $reader -FullAccess $admins -FolderEnumerationMode AccessBased -EncryptData $true|Out-Null
}
$run='diagnostic-'+[Guid]::NewGuid().ToString('N')
$runRoot=Join-Path $logRoot $run
Protect-Folder $runRoot ($domain.DomainSID.Value+'-515')
$reportPath=Join-Path $PSScriptRoot ($run+'.csv')
# Read a machine-owned diagnostic using a locked handle. Reject links that
# resolve outside the intended file before reading any bytes as administrator.
Add-Type -TypeDefinition @'
using System;
using System.IO;
using System.Text;
using System.Runtime.InteropServices;
using Microsoft.Win32.SafeHandles;
public static class CenterEKReceiptReader {
    [DllImport("kernel32.dll", CharSet=CharSet.Unicode, SetLastError=true)]
    static extern uint GetFinalPathNameByHandle(SafeFileHandle h, StringBuilder p, uint n, uint flags);
    public static string Read(string path) {
        string expected=Path.GetFullPath(path);
        using(var f=new FileStream(expected,FileMode.Open,FileAccess.Read,FileShare.Read)) {
            var name=new StringBuilder(32768);
            uint size=GetFinalPathNameByHandle(f.SafeFileHandle,name,(uint)name.Capacity,0);
            if(size==0 || size>=name.Capacity) throw new IOException("Cannot resolve diagnostic handle");
            string actual=name.ToString();
            if(actual.StartsWith(@"\\?\")) actual=actual.Substring(4);
            if(!String.Equals(actual,expected,StringComparison.OrdinalIgnoreCase) || f.Length>16384)
                throw new IOException("Unsafe diagnostic file");
            using(var r=new StreamReader(f,Encoding.UTF8,true)) return r.ReadToEnd();
        }
    }
}
'@
$worker={
    param($Computer,$Fqdn,$Startup,$Receipt,$Timeout)
    $ErrorActionPreference='Stop'
    $result=[ordered]@{Computer=$Computer;Status='REMOTE_ACCESS_FAILED';TaskResult='';Diagnostic=$Receipt;TemporaryTask='';ErrorType=''}
    function Existing-Agent($Folder){
        try{return $Folder.GetTask('CenterEK-Endpoint-System')}
        catch{
            $errorObject=$_.Exception
            while($errorObject.InnerException){$errorObject=$errorObject.InnerException}
            if($errorObject.HResult -eq -2147024894){return $null}
            throw
        }
    }
    $folder=$null;$created=$false;$temporary='CenterEK-Deploy-'+[Guid]::NewGuid().ToString('N')
    $stage='connect'
    try{
        $service=New-Object -ComObject Schedule.Service
        # Match the short AD name already used by schtasks /S. A stale FQDN
        # record must not silently select a different deployment target.
        $service.Connect($Computer)
        $stage='open_task_folder'
        $folder=$service.GetFolder('\')
        $stage='query_existing_agent'
        $agent=Existing-Agent $folder
        if($agent){
            $result.Status=if($agent.Enabled){'EXISTING_TASK'}else{'EXISTING_TASK_DISABLED'}
            return [pscustomobject]$result
        }
        # Inline wrapper captures script-loading/policy failures too. It does not
        # bypass execution policy or log credentials/script source/error lines.
        $command=@'
& {
    $ErrorActionPreference='Stop'
    $r=[ordered]@{computer=$env:COMPUTERNAME;collected_at=[DateTime]::UtcNow.ToString('o');stage='preflight';status='failed';identity=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value;language=[string]$ExecutionContext.SessionState.LanguageMode;policy=@();script_access=$false;package_access=$false;error_id='';error_type='';error_line=0;task_present=$false}
    $code=1
    try {
        $r.policy=@(Get-ExecutionPolicy -List|ForEach-Object {@{scope=[string]$_.Scope;policy=[string]$_.ExecutionPolicy}})
        $r.script_access=Test-Path -LiteralPath '__STARTUP__'
        $r.package_access=Test-Path -LiteralPath ('__PACKAGES__\'+$env:COMPUTERNAME+'\enrollment.local.json')
        if(-not $r.script_access -or -not $r.package_access){throw 'Deployment source unavailable'}
        $r.stage='installer'
        & '__STARTUP__' *> $null
        $r.task_present=[bool](Get-ScheduledTask -TaskName 'CenterEK-Endpoint-System' -ErrorAction SilentlyContinue)
        if($r.task_present){$r.status='task_registered';$code=0}else{throw 'Agent task absent after installer'}
    } catch {
        $r.error_id=[string]$_.FullyQualifiedErrorId
        $r.error_type=$_.Exception.GetType().FullName
        $r.error_line=$_.InvocationInfo.ScriptLineNumber
    }
    try {$r|ConvertTo-Json -Depth 5|Set-Content -LiteralPath '__RECEIPT__' -Encoding UTF8} catch {exit 2}
    exit $code
}
'@
        $packages=Split-Path -Parent $Startup
        $command=$command.Replace('__STARTUP__',$Startup).Replace('__PACKAGES__',($packages+'\packages')).Replace('__RECEIPT__',$Receipt)
        $stage='build_task_definition'
        $definition=$service.NewTask(0)
        $definition.RegistrationInfo.Description='CenterEK on-demand workstation deployment; machine-specific diagnostic receipt'
        $definition.Principal.UserId='SYSTEM';$definition.Principal.LogonType=5;$definition.Principal.RunLevel=1
        $definition.Settings.ExecutionTimeLimit='PT3M'
        $definition.Settings.DisallowStartIfOnBatteries=$false
        $definition.Settings.StopIfGoingOnBatteries=$false
        $definition.Settings.AllowDemandStart=$true
        $action=$definition.Actions.Create(0)
        $action.Path='%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe'
        $action.Arguments='-NoProfile -NonInteractive -WindowStyle Hidden -Command "'+$command.Replace('"','\"')+'"'
        # TASK_CREATE only; never replace an existing task. No startup trigger.
        $stage='register_bootstrap'
        $task=$folder.RegisterTaskDefinition($temporary,$definition,2,'SYSTEM',$null,5,$null)
        $created=$true;$result.TemporaryTask=$temporary
        $stage='run_bootstrap'
        $running=$task.Run($null)
        $stage='wait_bootstrap'
        $limit=[DateTime]::UtcNow.AddSeconds($Timeout)
        do{
            Start-Sleep -Seconds 2
            $task=$folder.GetTask($temporary)
        }while($running.State -in @(2,4) -and [DateTime]::UtcNow -lt $limit)
        if($running.State -in @(2,4)){$result.Status='REMOTE_TASK_TIMEOUT'}
        else{
            $result.TaskResult=[string]$task.LastTaskResult
            $stage='verify_agent'
            $agent=Existing-Agent $folder
            $result.Status=if($agent -and $task.LastTaskResult -eq 0){'TASK_REGISTERED_VERIFY_TELEMETRY'}else{'INSTALL_FAILED'}
        }
    }catch{
        $errorObject=$_.Exception
        while($errorObject.InnerException){$errorObject=$errorObject.InnerException}
        $result.Status=if($stage -eq 'connect'){'REMOTE_ACCESS_FAILED'}else{'REMOTE_OPERATION_FAILED'}
        $result.ErrorType=$stage+' '+$errorObject.GetType().FullName+' HRESULT=0x'+$errorObject.HResult.ToString('X8')
    }
    finally{
        if($created -and $folder){
            try{
                $task=$folder.GetTask($temporary)
                if($task.State -notin @(2,4)){$folder.DeleteTask($temporary,0);$result.TemporaryTask=''}
            }catch{if(-not $result.ErrorType){$result.ErrorType='TemporaryTaskCleanupFailed'}}
        }
    }
    [pscustomobject]$result
}
for($index=0;$index -lt $targets.Count;$index+=$Throttle){
    $jobs=@()
    foreach($computer in @($targets|Select-Object -Skip $index -First $Throttle)){
        $name=$computer.Name.ToUpperInvariant()
        if(-not(Test-Path -LiteralPath (Join-Path $expected ('packages\'+$name+'\enrollment.local.json')))){
            [pscustomobject]@{Computer=$name;Status='NO_PUBLISHED_PACKAGE';TaskResult='';Diagnostic='';TemporaryTask='';ErrorType=''}|Export-Csv -LiteralPath $reportPath -NoTypeInformation -Append -Encoding UTF8
            Write-Output ($name+' NO_PUBLISHED_PACKAGE');continue
        }
        Protect-Folder (Join-Path $runRoot $name) $computer.SID.Value $true
        $receipt='\\'+$server+'\'+$logShareName+'\'+$run+'\'+$name+'\result.json'
        $job=Start-Job -ScriptBlock $worker -ArgumentList $name,$computer.DNSHostName,$startup,$receipt,$TimeoutSeconds
        $jobs+=@{Job=$job;Computer=$name;Receipt=$receipt}
    }
    $deadline=[DateTime]::UtcNow.AddSeconds($TimeoutSeconds+30)
    foreach($entry in $jobs){
        $wait=[Math]::Max(1,[int]($deadline-[DateTime]::UtcNow).TotalSeconds)
        $done=Wait-Job -Job $entry.Job -Timeout $wait
        if($done){$rows=@(Receive-Job -Job $entry.Job -ErrorAction SilentlyContinue)}else{$rows=@()}
        if(-not $rows.Count){
            Stop-Job -Job $entry.Job
            $rows=@([pscustomobject]@{Computer=$entry.Computer;Status='REMOTE_ACCESS_TIMEOUT_OR_JOB_FAILED';TaskResult='';Diagnostic=$entry.Receipt;TemporaryTask='UNKNOWN_IF_CREATED';ErrorType=''})
        }
        foreach($row in $rows){
            $row|Select-Object Computer,Status,TaskResult,Diagnostic,TemporaryTask,ErrorType|Export-Csv -LiteralPath $reportPath -NoTypeInformation -Append -Encoding UTF8
            Write-Output ($row.Computer+' '+$row.Status+' result='+$row.TaskResult)
            if($row.ErrorType){Write-Output ('DETAIL='+$row.ErrorType)}
            # Receipts are untrusted per-machine data. Print only bounded JSON
            # fields; never execute or recursively enumerate machine content.
            $local=Join-Path $runRoot ($entry.Computer+'\result.json')
            if((Test-Path -LiteralPath $local) -and (Get-Item -LiteralPath $local).Length -le 16384){
                try{
                    $info=[CenterEKReceiptReader]::Read($local)|ConvertFrom-Json
                    $info|Select-Object computer,stage,status,script_access,package_access,error_id,error_type,error_line,policy|ConvertTo-Json -Depth 5
                }catch{Write-Output 'DIAGNOSTIC_INVALID'}
            }
        }
        Remove-Job -Job $entry.Job
    }
}
Write-Output ('REPORT='+$reportPath)
Write-Output 'A registered task does not prove Azure receipt. Offline/blocked machines remain pending; no firewall was changed.'
