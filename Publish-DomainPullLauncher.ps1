param([string]$ShareName='CenterEKDeploy$')
# Publish a secret-free computer-startup CMD launcher. No GPO, firewall, DNS,
# endpoint or reboot changes; administrator links the dedicated GPO afterward.
$ErrorActionPreference='Stop'
function New-DomainPullLauncher([string]$Template,[string]$Origin,[string]$Receipt){
    if($Origin -cnotmatch '^\\\\[A-Za-z0-9.-]+\\[A-Za-z0-9$-]+$' -or $Receipt -cnotmatch '^\\\\[A-Za-z0-9.-]+\\CenterEKDeployLogs\$\\gpo-pull-[a-f0-9]{32}\\\{COMPUTER\}\\result\.json$'){throw 'Invalid protected pull origin/receipt'}
    $command=$Template.Replace('__STARTUP__',($Origin+'\Start-DomainEndpoint.ps1')).Replace('__PACKAGES__',($Origin+'\packages')).Replace('__RECEIPT__',$Receipt).Replace('__EXPECTED_COMPUTER__','')
    if($command -match '__[A-Z_]+__'){throw 'Unresolved bootstrap placeholder'}
    # Supported domain workstations only; already-installed endpoints exit
    # before downloading anything. The package remains computer-SID restricted.
    $prefix="if((Get-CimInstance Win32_ComputerSystem).DomainRole -ne 1){exit 0};if(Get-ScheduledTask -TaskName 'CenterEK-Endpoint-System' -ErrorAction SilentlyContinue){exit 0};"
    $prefix+="if(-not(Test-Path -LiteralPath (Split-Path -Parent ('"+$Receipt+"'.Replace('{COMPUTER}',`$env:COMPUTERNAME))))){exit 3};"
    $lines=@($command -split '\r?\n'|Where-Object {$_.Trim() -and -not $_.TrimStart().StartsWith('#')})
    $compact=$prefix+($lines -join ';')
    $tokens=$null;$errors=$null
    [void][Management.Automation.Language.Parser]::ParseInput($compact,[ref]$tokens,[ref]$errors)
    if($errors -or $compact.Contains('"') -or $compact.Contains('%') -or $compact.Contains('!') -or $compact.Length -gt 7000){throw 'CMD bootstrap is unsafe or too long'}
    # No Bypass/Unrestricted, encoded payload or origin-mark removal.
    return "@echo off`r`n"+'"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -NonInteractive -ExecutionPolicy RemoteSigned -WindowStyle Hidden -Command "'+$compact+"`"`r`nexit /b %errorlevel%`r`n"
}
$identity=[Security.Principal.WindowsIdentity]::GetCurrent()
if(-not(New-Object Security.Principal.WindowsPrincipal($identity)).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){throw 'Administrator CMD required on VOLO'}
Import-Module ActiveDirectory
$domain=Get-ADDomain
$share=Get-SmbShare -Name $ShareName
$root=Join-Path $env:ProgramData 'CenterEK-DomainDistribution'
if($share.Path.TrimEnd('\') -ine $root -or -not $share.EncryptData -or ((Get-Item -Force -LiteralPath $root).Attributes -band [IO.FileAttributes]::ReparsePoint)){throw 'Unexpected distribution share'}
$source=Join-Path $PSScriptRoot 'Invoke-DomainRollout.ps1'
$tokens=$null;$errors=$null
$ast=[Management.Automation.Language.Parser]::ParseFile($source,[ref]$tokens,[ref]$errors)
if($errors){throw 'Invalid reviewed invoker source'}
$literal=$ast.Find({param($node) $node -is [Management.Automation.Language.AssignmentStatementAst] -and $node.Left.Extent.Text -eq '$command' -and $node.Right -is [Management.Automation.Language.CommandExpressionAst] -and $node.Right.Expression -is [Management.Automation.Language.StringConstantExpressionAst]},$true)
$runtime=$ast.Find({param($node) $node -is [Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq 'Update-PackageRuntime'},$true)
if(-not $literal -or -not $runtime -or -not $literal.Right.Expression.Value.Contains('__EXPECTED_COMPUTER__') -or -not $literal.Right.Expression.Value.Contains(".Replace('{COMPUTER}',`$env:COMPUTERNAME)")){throw 'Current reviewed bootstrap/runtime updater missing; update Invoke-DomainRollout.ps1 too'}
. ([scriptblock]::Create($runtime.Extent.Text))
$origin='\\'+$env:COMPUTERNAME+'.'+$domain.DNSRoot+'\'+$ShareName
$target=Join-Path $root 'Start-CenterEKEndpoint.cmd'
if(Test-Path -LiteralPath $target){throw 'Existing pull launcher preserved; review before replacement'}
$logs=Get-SmbShare -Name 'CenterEKDeployLogs$'
$logRoot=Join-Path $env:ProgramData 'CenterEK-DeploymentReceipts'
if($logs.Path.TrimEnd('\') -ine $logRoot -or -not $logs.EncryptData -or ((Get-Item -Force -LiteralPath $logRoot).Attributes -band [IO.FileAttributes]::ReparsePoint)){throw 'Protected diagnostic share required'}
$run='gpo-pull-'+[Guid]::NewGuid().ToString('N')
$runRoot=Join-Path $logRoot $run
$readerSid=$domain.DomainSID.Value+'-515'
function New-ProtectedPullFolder([string]$Path,[string]$Sid,[bool]$Write){
    if(Test-Path -LiteralPath $Path){throw 'Existing pull diagnostic directory preserved'}
    New-Item -ItemType Directory -Path $Path|Out-Null
    $acl=New-Object Security.AccessControl.DirectorySecurity
    $acl.SetAccessRuleProtection($true,$false)
    $acl.SetOwner((New-Object Security.Principal.SecurityIdentifier('S-1-5-32-544')))
    foreach($id in @('S-1-5-18','S-1-5-32-544')){$acl.AddAccessRule((New-Object Security.AccessControl.FileSystemAccessRule((New-Object Security.Principal.SecurityIdentifier($id)),'FullControl','ContainerInherit,ObjectInherit','None','Allow')))}
    $rights=if($Write){'Modify'}else{'ReadAndExecute'}
    $inherit=if($Write){'ContainerInherit,ObjectInherit'}else{'None'}
    $acl.AddAccessRule((New-Object Security.AccessControl.FileSystemAccessRule((New-Object Security.Principal.SecurityIdentifier($Sid)),$rights,$inherit,'None','Allow')))
    Set-Acl -LiteralPath $Path -AclObject $acl
}
New-ProtectedPullFolder $runRoot $readerSid $false
$count=0;$held=@()
foreach($computer in @(Get-ADComputer -Filter * -Properties Enabled,OperatingSystem,DNSHostName)){
    if(-not $computer.Enabled -or $computer.OperatingSystem -cnotmatch '^Windows (8|10|11)(\b|\.)' -or $computer.Name -cnotmatch '^[A-Za-z0-9][A-Za-z0-9-]{0,14}$' -or $computer.DNSHostName -ine ($computer.Name+'.'+$domain.DNSRoot)){continue}
    $name=$computer.Name.ToUpperInvariant()
    $package=Join-Path $root ('packages\'+$name)
    if(-not(Test-Path -LiteralPath (Join-Path $package 'enrollment.local.json'))){continue}
    try{Update-PackageRuntime $package}catch{$held+=$name;continue}
    New-ProtectedPullFolder (Join-Path $runRoot $name) $computer.SID.Value $true
    $count++
}
if(-not $count){throw 'No eligible published workstation packages'}
$receipt='\\'+$env:COMPUTERNAME+'.'+$domain.DNSRoot+'\CenterEKDeployLogs$\'+$run+'\{COMPUTER}\result.json'
$text=New-DomainPullLauncher $literal.Right.Expression.Value $origin $receipt
$temp=Join-Path $root ([Guid]::NewGuid().ToString('N')+'.cmd.tmp')
[IO.File]::WriteAllText($temp,$text,[Text.Encoding]::ASCII)
$acl=Get-Acl -LiteralPath $temp
$acl.AddAccessRule((New-Object Security.AccessControl.FileSystemAccessRule((New-Object Security.Principal.SecurityIdentifier($readerSid)),'ReadAndExecute','Allow')))
Set-Acl -LiteralPath $temp -AclObject $acl
Move-Item -LiteralPath $temp -Destination $target
Write-Output ('PULL_PACKAGES_READY='+$count)
Write-Output ('CMD_STARTUP='+$origin+'\Start-CenterEKEndpoint.cmd')
Write-Output ('PULL_DIAGNOSTICS='+$runRoot)
foreach($name in $held){Write-Output ($name+' PACKAGE_RUNTIME_REVIEW_REQUIRED')}
Write-Output 'GPO_UNCHANGED: add CMD_STARTUP to the dedicated computer Startup Scripts tab; remove only its previous CenterEK PowerShell startup entry. Workstations install at their next domain-connected startup. No forced reboot.'
