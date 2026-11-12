$ErrorActionPreference='Stop'
$repo=Split-Path -Parent $PSScriptRoot
$tokens=$null;$errors=$null
$ast=[Management.Automation.Language.Parser]::ParseFile((Join-Path $repo 'Publish-DomainPullLauncher.ps1'),[ref]$tokens,[ref]$errors)
if($errors){throw 'Publisher parse error'}
$function=$ast.Find({param($node) $node -is [Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq 'New-DomainPullLauncher'},$true)
. ([scriptblock]::Create($function.Extent.Text))
$source=[Management.Automation.Language.Parser]::ParseFile((Join-Path $repo 'Invoke-DomainRollout.ps1'),[ref]$tokens,[ref]$errors)
$template=$source.Find({param($node) $node -is [Management.Automation.Language.AssignmentStatementAst] -and $node.Left.Extent.Text -eq '$command' -and $node.Right -is [Management.Automation.Language.CommandExpressionAst] -and $node.Right.Expression -is [Management.Automation.Language.StringConstantExpressionAst]},$true).Right.Expression.Value
$origin='\\VOLO.volonet.local\CenterEKDeploy$'
$receipt='\\VOLO.volonet.local\CenterEKDeployLogs$\gpo-pull-00000000000000000000000000000000\{COMPUTER}\result.json'
$launcher=New-DomainPullLauncher $template $origin $receipt
if($launcher.Length -ge 8191 -or $launcher -match '__[A-Z_]+__|EncodedCommand|\bBypass\b|Unblock-File|Set-ExecutionPolicy'){throw 'Unsafe launcher output'}
if(-not $launcher.Contains('DomainRole -ne 1') -or -not $launcher.Contains('Get-ScheduledTask') -or -not $launcher.Contains('.Replace(''{COMPUTER}'',$env:COMPUTERNAME)') -or -not $launcher.Contains('if(-not(Test-Path')){throw 'Missing workstation/existing-agent/receipt gating'}
if(-not $launcher.Contains('"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"')){throw 'Launcher executable relies on search PATH'}
Write-Output 'PASS real bootstrap compacted within CMD limit with protected guards'
foreach($bad in @('\\VOLO.local\bad%path','\\VOLO.local\bad''path','\\VOLO.local\bad!path')){
    $rejected=$false;try{New-DomainPullLauncher $template $bad $receipt}catch{$rejected=$true}
    if(-not $rejected){throw 'Unsafe CMD origin was accepted'}
}
Write-Output 'PASS CMD input metacharacter rejection'
# Real CMD -> PowerShell fixture, with only the environmental early-exit checks
# removed locally. The production launcher is never executed/published here.
$fixture=Join-Path $env:TEMP ('centerek-cmd-test-'+[Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path (Join-Path $fixture $env:COMPUTERNAME) -Force|Out-Null
$done=Join-Path $fixture 'done.txt'
$testTemplate="& {`r`n# comment must not swallow following commands`r`n`$text='CMD_FIXTURE_OK'`r`n`$text | Set-Content -LiteralPath '"+$done+"'`r`n}"
$test=New-DomainPullLauncher $testTemplate $origin $receipt
$test=$test.Replace("if((Get-CimInstance Win32_ComputerSystem).DomainRole -ne 1){exit 0};if(Get-ScheduledTask -TaskName 'CenterEK-Endpoint-System' -ErrorAction SilentlyContinue){exit 0};",'')
$test=$test.Replace((Split-Path -Parent (Split-Path -Parent $receipt)),$fixture)
$cmd=Join-Path $fixture 'fixture.cmd'
[IO.File]::WriteAllText($cmd,$test,[Text.Encoding]::ASCII)
$process=[Diagnostics.Process]::new()
$process.StartInfo=[Diagnostics.ProcessStartInfo]::new('cmd.exe',('/d /c "'+$cmd+'"'))
$process.StartInfo.UseShellExecute=$false;$process.StartInfo.CreateNoWindow=$true
try{
    [void]$process.Start()
    if(-not $process.WaitForExit(15000)){$process.Kill();throw 'Native CMD fixture timed out'}
    if($process.ExitCode -ne 0 -or -not(Test-Path -LiteralPath $done) -or (Get-Content -LiteralPath $done -Raw).Trim() -ne 'CMD_FIXTURE_OK'){throw 'CMD quoting/pipe fixture failed'}
    Write-Output 'PASS real CMD quoting and PowerShell pipeline fixture'
}finally{
    $process.Dispose()
    $absolute=[IO.Path]::GetFullPath($fixture)
    if($absolute.StartsWith(([IO.Path]::GetFullPath($env:TEMP).TrimEnd('\')+'\centerek-cmd-test-'),[StringComparison]::OrdinalIgnoreCase)){Remove-Item -LiteralPath $absolute -Recurse -Force}
}
