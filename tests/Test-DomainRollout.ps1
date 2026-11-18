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
foreach($scenario in @('existing','disabled','blocked','registerblocked','success','fqdnonly','shortonly','bothnamesbad','finishedhandle','failed','namemismatch','timeout')){
    $script:scenario=$scenario;$script:registered=0;$script:deleted=0
    $script:connections=@()
    $script:task=[pscustomobject]@{State=3;LastTaskResult=0}
    $script:running=[pscustomobject]@{State=4}
    $script:running|Add-Member ScriptMethod Refresh {
        if($script:scenario -eq 'finishedhandle'){throw [Runtime.InteropServices.COMException]::new('No running instance',-2147216629)}
        if($script:scenario -ne 'timeout'){$this.State=3}
    }
    if($scenario -eq 'failed'){$script:task.LastTaskResult=1}
    if($scenario -eq 'namemismatch'){$script:task.LastTaskResult=13}
    if($scenario -eq 'timeout'){$script:running.State=4;$script:task.State=4}
    $script:task|Add-Member ScriptMethod Run {param($nothing) return $script:running}
    $script:folder=[pscustomobject]@{}
    $script:folder|Add-Member ScriptMethod GetTask {
        param($name)
        if($name -eq 'CenterEK-Endpoint-System'){
            if($script:scenario -in @('existing','disabled') -or ($script:scenario -in @('success','fqdnonly','shortonly','finishedhandle') -and $script:registered)){
                return [pscustomobject]@{Enabled=($script:scenario -ne 'disabled')}
            }
            throw [IO.FileNotFoundException]::new('Expected missing task')
        }
        return $script:task
    }
    $script:folder|Add-Member ScriptMethod RegisterTaskDefinition {
        param($name,$definition,$flags,$user,$password,$logon,$sddl)
        if($script:scenario -eq 'registerblocked'){throw [UnauthorizedAccessException]::new('Registration blocked')}
        if($flags -ne 2 -or $user -ne 'SYSTEM' -or $password -or $logon -ne 5){throw 'Unsafe task registration'}
        if($definition.PSObject.Properties.Name -contains 'Triggers'){throw 'Bootstrap must be demand-only'}
        if($script:action.Arguments -notmatch '^-NoProfile -NonInteractive -ExecutionPolicy RemoteSigned ' -or $script:action.Arguments -match 'EncodedCommand|\bBypass\b|\bUnrestricted\b|Set-ExecutionPolicy'){throw 'Unexpected process execution policy'}
        if($script:action.Arguments -notmatch 'script_access' -or $script:action.Arguments -notmatch 'package_access'){throw 'Missing diagnostics'}
        $script:registered++;return $script:task
    }
    $script:folder|Add-Member ScriptMethod DeleteTask {param($name,$flags) $script:deleted++}
    $script:service=[pscustomobject]@{}
    $script:service|Add-Member ScriptMethod Connect {
        param($name)
        $script:connections+=$name
        if($script:scenario -eq 'blocked'){throw [UnauthorizedAccessException]::new('Blocked')}
        if($script:scenario -eq 'bothnamesbad' -or ($script:scenario -eq 'shortonly' -and $name.Contains('.')) -or ($script:scenario -eq 'fqdnonly' -and -not $name.Contains('.'))){throw [Runtime.InteropServices.COMException]::new('Network name unavailable',-2147024843)}
    }
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
    $expected=@{existing='EXISTING_TASK';disabled='EXISTING_TASK_DISABLED';blocked='REMOTE_ACCESS_FAILED';registerblocked='REMOTE_OPERATION_FAILED';success='TASK_REGISTERED_VERIFY_TELEMETRY';fqdnonly='TASK_REGISTERED_VERIFY_TELEMETRY';shortonly='TASK_REGISTERED_VERIFY_TELEMETRY';bothnamesbad='REMOTE_ACCESS_FAILED';finishedhandle='TASK_REGISTERED_VERIFY_TELEMETRY';failed='INSTALL_FAILED';namemismatch='TARGET_NAME_MISMATCH';timeout='REMOTE_TASK_TIMEOUT'}[$scenario]
    if($result.Status -ne $expected){throw ('Unexpected '+$scenario+' result: '+($result|ConvertTo-Json -Compress))}
    if($scenario -in @('existing','disabled','blocked','bothnamesbad') -and $script:registered){throw 'Existing/blocked machine modified'}
    if($scenario -in @('success','fqdnonly','shortonly','finishedhandle','failed','namemismatch') -and $script:deleted -ne 1){throw 'Completed bootstrap not cleaned up'}
    if($scenario -eq 'fqdnonly' -and ($script:connections.Count -ne 1 -or $script:connections[0] -ne 'pc-07.volonet.local')){throw 'AD FQDN was not tried first'}
    if($scenario -eq 'shortonly' -and ($script:connections.Count -ne 2 -or $script:connections[1] -ne 'PC-07')){throw 'Network failure did not try AD short name'}
    if($scenario -eq 'blocked' -and $script:connections.Count -ne 1){throw 'Access denied incorrectly retried under another name'}
    if($scenario -eq 'bothnamesbad' -and ($script:connections.Count -ne 2 -or $result.ErrorType -notmatch 'pc-07.volonet.local=0x80070035;PC-07=0x80070035')){throw 'Both network failures not reported'}
    if($scenario -eq 'timeout' -and $script:deleted){throw 'Running task was deleted'}
    if($scenario -eq 'registerblocked' -and $result.ErrorType -notmatch '^register_bootstrap .*HRESULT=0x80070005$'){throw 'Registration failure stage/code lost'}
    if($scenario -eq 'success'){$diagnosticArguments=$script:action.Arguments}
    Write-Output ('PASS '+$scenario)
}
$retry=$ast.Find({param($node) $node -is [Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq 'Get-NetworkRetryNames'},$true)
. ([scriptblock]::Create($retry.Extent.Text))
$rows=@(
    [pscustomobject]@{Computer='PC-08';Status='REMOTE_ACCESS_FAILED'},
    [pscustomobject]@{Computer='pc-08';Status='REMOTE_ACCESS_FAILED'},
    [pscustomobject]@{Computer='DESKTOP-7I1O5U6';Status='REMOTE_ACCESS_FAILED'},
    [pscustomobject]@{Computer='PC-102';Status='TASK_REGISTERED_VERIFY_TELEMETRY'},
    [pscustomobject]@{Computer='PC-07';Status='EXISTING_TASK'},
    [pscustomobject]@{Computer='PC-54';Status='INSTALL_FAILED'}
)
$names=@(Get-NetworkRetryNames $rows)
if($names.Count -ne 2 -or 'PC-08' -notin $names -or 'DESKTOP-7I1O5U6' -notin $names){throw 'Retry scope includes successful/non-network targets or lost an ASCII I name'}
$rejected=$false
try{Get-NetworkRetryNames @([pscustomobject]@{Computer='..\PC-08';Status='REMOTE_ACCESS_FAILED'})}catch{$rejected=$true}
if(-not $rejected){throw 'Unsafe retry target was accepted'}
Write-Output 'PASS network-only retry scope, deduplication and target validation'
# Exercise the actual powershell.exe command-line quoting and diagnostic writer
# against a local failure fixture, without any remote host or enrollment key.
Remove-Item Function:\New-Object
Remove-Item Function:\Start-Sleep
$fixture=Join-Path $env:TEMP ('centerek-rollout-test-'+[Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path (Join-Path $fixture ('packages\'+$env:COMPUTERNAME)) -Force|Out-Null
$source=Join-Path $fixture 'Start-DomainEndpoint.ps1'
Set-Content -LiteralPath $source -Value "throw 'EXPECTED_TEST_FAILURE'" -Encoding UTF8
Set-Content -LiteralPath (Join-Path $fixture ('packages\'+$env:COMPUTERNAME+'\enrollment.local.json')) -Value '{}' -Encoding UTF8
$packageFixture=Join-Path $fixture ('packages\'+$env:COMPUTERNAME)
foreach($file in @('Collect-EndpointSessions.ps1','Send-Report.ps1','Setup-Agent.ps1','Install-SystemTask.ps1','Run-SystemTask.ps1','panel-ca.pem')){
    Set-Content -LiteralPath (Join-Path $packageFixture $file) -Value '# local test fixture' -Encoding UTF8
}
Set-Content -LiteralPath (Join-Path $packageFixture 'Install-EndpointPilot.ps1') -Value "throw 'EXPECTED_TEST_FAILURE'" -Encoding UTF8
$receipt=Join-Path $fixture 'result.json'
$arguments=$diagnosticArguments.Replace('\\VOLO.volonet.local\CenterEKDeploy$',$fixture).Replace('\\VOLO.volonet.local\CenterEKDeployLogs$\run\PC-07\result.json',$receipt)
$stagingParent=Join-Path $fixture 'stage-parent'
New-Item -ItemType Directory -Path $stagingParent|Out-Null
# The desktop test is not elevated/SYSTEM: preserve the same protected-directory
# structure but substitute only this test user's SID and an owned temp parent.
$testSid=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value
$arguments=$arguments.Replace('$env:ProgramData',("'"+$stagingParent+"'")).Replace('S-1-5-32-544',$testSid)
$arguments=$arguments.Replace('$expected=''PC-07''',('$expected='''+$env:COMPUTERNAME+''''))
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
    if(@($record.policy|Where-Object {$_.scope -eq 'Process' -and $_.policy -eq 'RemoteSigned'}).Count -ne 1){throw 'Diagnostic process policy not applied'}
    if(@(Get-ChildItem -LiteralPath $stagingParent -Force).Count){throw 'Protected staging files were not cleaned up'}
    Write-Output 'PASS native diagnostic process'
    Set-Content -LiteralPath (Join-Path $packageFixture 'Install-EndpointPilot.ps1') -Stream Zone.Identifier -Value "[ZoneTransfer]`r`nZoneId=3"
    [void]$process.Start()
    if(-not $process.WaitForExit(15000)){$process.Kill();throw 'Origin-mark test timed out'}
    $blocked=Get-Content -LiteralPath $receipt -Raw|ConvertFrom-Json
    if($blocked.error_type -ne 'System.Management.Automation.PSSecurityException' -or @($blocked.origin|Where-Object {$_.file -eq 'Install-EndpointPilot.ps1' -and $_.zone -eq 'ZoneId=3'}).Count -ne 1){throw 'RemoteSigned/origin mark was bypassed'}
    if(@(Get-ChildItem -LiteralPath $stagingParent -Force).Count){throw 'Blocked staging files were not cleaned up'}
    # Restore source marker only in the disposable test fixture.
    Remove-Item -LiteralPath (Join-Path $packageFixture 'Install-EndpointPilot.ps1') -Stream Zone.Identifier
    Write-Output 'PASS origin metadata preserved and RemoteSigned block reported'
    $mismatchReceipt=$receipt+'.identity.json'
    $mismatchArguments=$arguments.Replace(('$expected='''+$env:COMPUTERNAME+''''),'$expected=''WRONG-PC''').Replace($receipt,$mismatchReceipt)
    $process.StartInfo.Arguments=$mismatchArguments
    [void]$process.Start()
    if(-not $process.WaitForExit(15000)){$process.Kill();throw 'Identity test timed out'}
    $mismatch=Get-Content -LiteralPath $mismatchReceipt -Raw|ConvertFrom-Json
    if($process.ExitCode -ne 13 -or $mismatch.stage -ne 'identity' -or $mismatch.error_id -ne 'TargetComputerMismatch' -or @(Get-ChildItem -LiteralPath $stagingParent -Force).Count){throw 'Wrong-host deployment was not stopped before staging'}
    Write-Output 'PASS actual computer identity mismatch stops before staging'
    $runtime=$ast.Find({param($node) $node -is [Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq 'Update-PackageRuntime'},$true)
    . ([scriptblock]::Create($runtime.Extent.Text))
    $package=Join-Path $fixture 'runtime'
    New-Item -ItemType Directory -Path $package|Out-Null
    $repo=Split-Path -Parent $PSScriptRoot
    foreach($name in @('Install-SystemTask.ps1','Run-SystemTask.ps1')){
        $text=[IO.File]::ReadAllText((Join-Path $repo $name))
        if($name -eq 'Install-SystemTask.ps1'){
            $text=$text.Replace('$arguments=''-NoProfile -ExecutionPolicy RemoteSigned -WindowStyle Hidden -File "''','$arguments=''-NoProfile -WindowStyle Hidden -File "''').Replace('if($ServerExecutable){$arguments+=','if($ServerExecutable){$arguments=$arguments.Replace(''-NoProfile '',''-NoProfile -ExecutionPolicy RemoteSigned '');$arguments+=')
        }else{
            $text=$text.Replace('$arguments=@(''-NoProfile'',''-ExecutionPolicy'',''RemoteSigned'',''-File''','$arguments=@(''-NoProfile'',''-File''')
        }
        [IO.File]::WriteAllText((Join-Path $package $name),$text)
    }
    Update-PackageRuntime $package
    foreach($name in @('Install-SystemTask.ps1','Run-SystemTask.ps1')){
        $expected=[IO.File]::ReadAllText((Join-Path $repo $name)).Replace("`r`n","`n")
        $actual=[IO.File]::ReadAllText((Join-Path $package $name)).Replace("`r`n","`n")
        if($actual -cne $expected){throw ('Runtime patch mismatch: '+$name)}
    }
    Update-PackageRuntime $package
    Add-Content -LiteralPath (Join-Path $package 'Run-SystemTask.ps1') -Value '# local modification'
    $rejected=$false
    try{Update-PackageRuntime $package}catch{$rejected=$true}
    if(-not $rejected){throw 'Unknown runtime edit was overwritten'}
    Write-Output 'PASS known runtime upgrade, idempotence and unknown-version preservation'
    $reader=$ast.Find({param($node) $node -is [Management.Automation.Language.CommandAst] -and $node.GetCommandName() -eq 'Add-Type'},$true)
    Add-Type -TypeDefinition $reader.CommandElements[-1].Value
    $read=[CenterEKReceiptReader]::Read($receipt)|ConvertFrom-Json
    if($read.error_type -ne $blocked.error_type){throw 'Receipt handle read failed'}
    $linked=Join-Path $fixture 'linked'
    New-Item -ItemType Junction -Path $linked -Target $fixture|Out-Null
    $rejected=$false
    try{[void][CenterEKReceiptReader]::Read((Join-Path $linked 'result.json'))}catch{$rejected=$true}
    if(-not $rejected){throw 'Junction diagnostic was not rejected'}
    # Remove the junction itself, never traverse it during recursive cleanup.
    [IO.Directory]::Delete($linked)
    [IO.File]::WriteAllText($receipt,('x'*16385))
    $rejected=$false
    try{[void][CenterEKReceiptReader]::Read($receipt)}catch{$rejected=$true}
    if(-not $rejected){throw 'Oversize diagnostic was not rejected'}
    Write-Output 'PASS bounded receipt and junction rejection'
}finally{
    $process.Dispose()
    $absolute=[IO.Path]::GetFullPath($fixture)
    if($absolute.StartsWith(([IO.Path]::GetFullPath($env:TEMP).TrimEnd('\')+'\centerek-rollout-test-'),[StringComparison]::OrdinalIgnoreCase)){
        Remove-Item -LiteralPath $absolute -Recurse -Force
    }
}
