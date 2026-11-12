$ErrorActionPreference='Stop'
$identity=[Security.Principal.WindowsIdentity]::GetCurrent()
$principal=New-Object Security.Principal.WindowsPrincipal($identity)
if(-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){throw 'Run PowerShell as administrator'}
$source=Split-Path -Parent $MyInvocation.MyCommand.Path
$root=Join-Path $env:ProgramData 'CenterEK-Agent'
if(Test-Path -LiteralPath $root){throw 'Existing agent installation preserved; do not overwrite it'}
$files=@('Collect-EndpointSessions.ps1','Send-Report.ps1','Setup-Agent.ps1','Install-SystemTask.ps1','Run-SystemTask.ps1','enrollment.local.json','panel-ca.pem')
foreach($name in $files){
 $path=Join-Path $source $name
 if(-not(Test-Path -LiteralPath $path) -or ((Get-Item -LiteralPath $path).Attributes -band [IO.FileAttributes]::ReparsePoint)){throw ('Missing/unsafe package component: '+$name)}
}
$enrollment=Get-Content -LiteralPath (Join-Path $source 'enrollment.local.json') -Raw|ConvertFrom-Json
if($enrollment.kind -ne 'endpoint' -or $enrollment.computer.Split('.')[0] -ine $env:COMPUTERNAME){throw 'This package belongs to a different computer'}
if((Get-Item -Force -LiteralPath $env:ProgramData).Attributes -band [IO.FileAttributes]::ReparsePoint){throw 'Reparse-point ProgramData rejected'}
New-Item -ItemType Directory -Path $root|Out-Null
$acl=New-Object Security.AccessControl.DirectorySecurity
$acl.SetAccessRuleProtection($true,$false)
$admins=New-Object Security.Principal.SecurityIdentifier('S-1-5-32-544')
$acl.SetOwner($admins)
foreach($sid in @('S-1-5-18','S-1-5-32-544')){
 $acl.AddAccessRule((New-Object Security.AccessControl.FileSystemAccessRule((New-Object Security.Principal.SecurityIdentifier($sid)),'FullControl','ContainerInherit,ObjectInherit','None','Allow')))
}
Set-Acl -LiteralPath $root -AclObject $acl
foreach($name in $files){Copy-Item -LiteralPath (Join-Path $source $name) -Destination (Join-Path $root $name)}
& icacls.exe $root /setowner '*S-1-5-32-544' /T /C|Out-Null
if($LASTEXITCODE){throw 'Agent code owner protection failed'}
& icacls.exe (Join-Path $root '*') /reset /T /C|Out-Null
if($LASTEXITCODE){throw 'Agent code ACL protection failed'}
$settings=Join-Path $root 'agent.local.json'
& (Join-Path $root 'Setup-Agent.ps1') -EnrollmentFile (Join-Path $root 'enrollment.local.json') -OutputFile $settings
& (Join-Path $root 'Install-SystemTask.ps1') -Mode Endpoint -AgentConfig $settings -CACertificate (Join-Path $root 'panel-ca.pem')
Write-Output 'Endpoint installed in protected ProgramData as SYSTEM; no inbound port was opened.'
Write-Output 'After verifying receipt, remove enrollment.local.json from transfer locations. Preserve data\secure agent settings.'
