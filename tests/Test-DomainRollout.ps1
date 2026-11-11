$ErrorActionPreference='Stop'
$path=Join-Path (Split-Path -Parent $PSScriptRoot) 'Invoke-DomainRollout.ps1'
$tokens=$null;$errors=$null
$ast=[Management.Automation.Language.Parser]::ParseFile($path,[ref]$tokens,[ref]$errors)
if($errors){throw 'Rollout script parse failure'}
$assignment=$ast.Find({param($node) $node -is [Management.Automation.Language.AssignmentStatementAst] -and $node.Left.Extent.Text -eq '$worker'},$true)
$text=$assignment.Right.Extent.Text.Trim()
$worker=[scriptblock]::Create($text.Substring(1,$text.Length-2))
# Fake only the remote scheduler boundary: never connect, register, install,
# access AD, change permissions or run the embedded endpoint command.
function New-Object {param([string]$ComObject) if($ComObject -ne 'Schedule.Service'){throw 'Unexpected COM class'};return $script:service}
function Start-Sleep {param([int]$Seconds)}
foreach($scenario in @('existing','disabled','blocked','success','failed','timeout')){
    $script:scenario=$scenario;$script:registered=0;$script:deleted=0
    $script:task=[pscustomobject]@{State=3;LastTaskResult=0}
    $script:running=[pscustomobject]@{State=3}
    if($scenario -eq 'failed'){$script:task.LastTaskResult=1}
    if($scenario -eq 'timeout'){$script:running.State=4;$script:task.State=4}
    $script:task|Add-Member ScriptMethod Run {param($nothing) return $script:running}
    $script:folder=[pscustomobject]@{}
    $script:folder|Add-Member ScriptMethod GetTask {
        param($name)
        if($name -eq 'CenterEK-Endpoint-System'){
            if($script:scenario -in @('existing','disabled') -or ($script:scenario -eq 'success' -and $script:registered)){
                return [pscustomobject]@{Enabled=($script:scenario -ne 'disabled')}
            }
            throw [IO.FileNotFoundException]::new('Expected missing task')
        }
        return $script:task
    }
    $script:folder|Add-Member ScriptMethod RegisterTaskDefinition {
        param($name,$definition,$flags,$user,$password,$logon,$sddl)
        if($flags -ne 2 -or $user -ne 'SYSTEM' -or $password -or $logon -ne 5){throw 'Unsafe task registration'}
        if($definition.PSObject.Properties.Name -contains 'Triggers'){throw 'Bootstrap must be demand-only'}
        if($script:action.Arguments -match '(?:^|\s)-ExecutionPolicy|EncodedCommand|\bBypass\b'){throw 'Policy bypass rejected'}
        if($script:action.Arguments -notmatch 'script_access' -or $script:action.Arguments -notmatch 'package_access'){throw 'Missing diagnostics'}
        $script:registered++;return $script:task
    }
    $script:folder|Add-Member ScriptMethod DeleteTask {param($name,$flags) $script:deleted++}
    $script:service=[pscustomobject]@{}
    $script:service|Add-Member ScriptMethod Connect {param($fqdn) if($script:scenario -eq 'blocked'){throw [UnauthorizedAccessException]::new('Blocked')}}
    $script:service|Add-Member ScriptMethod GetFolder {param($path) return $script:folder}
    $script:service|Add-Member ScriptMethod NewTask {
        param($flags)
        $script:action=[pscustomobject]@{Path='';Arguments=''}
        $actions=[pscustomobject]@{}
        $actions|Add-Member ScriptMethod Create {param($kind) return $script:action}
        return [pscustomobject]@{RegistrationInfo=[pscustomobject]@{Description=''};Principal=[pscustomobject]@{UserId='';LogonType=0;RunLevel=0};Settings=[pscustomobject]@{ExecutionTimeLimit='';DisallowStartIfOnBatteries=$true;StopIfGoingOnBatteries=$true;AllowDemandStart=$false};Actions=$actions}
    }
    $timeout=if($scenario -eq 'timeout'){-1}else{30}
    $result=& $worker 'PC-07' 'pc-07.volonet.local' '\\VOLO.volonet.local\CenterEKDeploy$\Start-DomainEndpoint.ps1' '\\VOLO.volonet.local\CenterEKDeployLogs$\run\PC-07\result.json' $timeout
    $expected=@{existing='EXISTING_TASK';disabled='EXISTING_TASK_DISABLED';blocked='REMOTE_ACCESS_FAILED';success='TASK_REGISTERED_VERIFY_TELEMETRY';failed='INSTALL_FAILED';timeout='REMOTE_TASK_TIMEOUT'}[$scenario]
    if($result.Status -ne $expected){throw ('Unexpected '+$scenario+' result: '+($result|ConvertTo-Json -Compress))}
    if($scenario -in @('existing','disabled','blocked') -and $script:registered){throw 'Existing/blocked machine modified'}
    if($scenario -in @('success','failed') -and $script:deleted -ne 1){throw 'Completed bootstrap not cleaned up'}
    if($scenario -eq 'timeout' -and $script:deleted){throw 'Running task was deleted'}
    if($scenario -eq 'success'){$diagnosticArguments=$script:action.Arguments}
    Write-Output ('PASS '+$scenario)
}
# Exercise the actual powershell.exe command-line quoting and diagnostic writer
# against a local failure fixture, without any remote host or enrollment key.
Remove-Item Function:\New-Object
Remove-Item Function:\Start-Sleep
$fixture=Join-Path $env:TEMP ('centerek-rollout-test-'+[Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path (Join-Path $fixture ('packages\'+$env:COMPUTERNAME)) -Force|Out-Null
$source=Join-Path $fixture 'Start-DomainEndpoint.ps1'
Set-Content -LiteralPath $source -Value "throw 'EXPECTED_TEST_FAILURE'" -Encoding UTF8
Set-Content -LiteralPath (Join-Path $fixture ('packages\'+$env:COMPUTERNAME+'\enrollment.local.json')) -Value '{}' -Encoding UTF8
$receipt=Join-Path $fixture 'result.json'
$arguments=$diagnosticArguments.Replace('\\VOLO.volonet.local\CenterEKDeploy$',$fixture).Replace('\\VOLO.volonet.local\CenterEKDeployLogs$\run\PC-07\result.json',$receipt)
$process=[Diagnostics.Process]::new()
$process.StartInfo=[Diagnostics.ProcessStartInfo]::new('powershell.exe',$arguments)
$process.StartInfo.UseShellExecute=$false
$process.StartInfo.CreateNoWindow=$true
try{
    [void]$process.Start()
    if(-not $process.WaitForExit(15000)){$process.Kill();throw 'Diagnostic process timeout'}
    if($process.ExitCode -ne 1 -or -not(Test-Path -LiteralPath $receipt)){throw 'Diagnostic invocation did not capture the failure'}
    $record=Get-Content -LiteralPath $receipt -Raw|ConvertFrom-Json
    if($record.stage -ne 'installer' -or $record.error_id -ne 'EXPECTED_TEST_FAILURE' -or -not $record.script_access -or -not $record.package_access){throw 'Diagnostic content incorrect'}
    Write-Output 'PASS native diagnostic process'
}finally{
    $process.Dispose()
    $absolute=[IO.Path]::GetFullPath($fixture)
    if($absolute.StartsWith(([IO.Path]::GetFullPath($env:TEMP).TrimEnd('\')+'\centerek-rollout-test-'),[StringComparison]::OrdinalIgnoreCase)){
        Remove-Item -LiteralPath $absolute -Recurse -Force
    }
}
