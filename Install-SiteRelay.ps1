param([Parameter(Mandatory=$true)][string]$EnrollmentFile,
      [string]$SourceRoot='C:\CenterEK',
      [string]$PythonPath='C:\Program Files\Python311\python.exe')
$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest
$root=(Resolve-Path -LiteralPath $PSScriptRoot).Path
$source=(Resolve-Path -LiteralPath $SourceRoot).Path
if($root -eq [IO.Path]::GetPathRoot($root) -or $root -ieq $env:WINDIR -or $root -ieq $env:ProgramFiles){throw 'A dedicated relay directory is required'}
foreach($path in @($root,$source)){
    if((Get-Item -LiteralPath $path).Attributes -band [IO.FileAttributes]::ReparsePoint){throw 'Reparse-point installation directories are not supported'}
}
$name='CenterEK-OfficeRelay-System'
if(Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue){throw 'Existing relay task preserved'}
if($root -ieq $source){throw 'Use a separate relay folder; do not overwrite the running office application'}
if(-not(Test-Path -LiteralPath (Join-Path $source 'config.local.json')) -or -not(Test-Path -LiteralPath (Join-Path $source 'data\monitor.sqlite3'))){throw 'Existing office installation is required'}
if(-not(Test-Path -LiteralPath $PythonPath)){throw 'Existing Python installation was not found'}
$identity=[Security.Principal.WindowsIdentity]::GetCurrent()
$principal=New-Object Security.Principal.WindowsPrincipal($identity)
if(-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){throw 'Run as administrator'}
$enrollment=Get-Content -LiteralPath $EnrollmentFile -Raw|ConvertFrom-Json
$uri=[Uri]$enrollment.url
if($enrollment.kind -ne 'site' -or $uri.Scheme -ne 'https' -or $uri.UserInfo -or $uri.AbsolutePath -ne '/' -or $uri.Query -or $uri.Fragment){throw 'Invalid site enrollment'}
foreach($file in @('site_push.py','site_relay.py','agents.py','service_secrets.py','file_security.py','Run-SiteRelay.ps1')){
    if(-not(Test-Path -LiteralPath (Join-Path $root $file))){throw ('Missing relay component: '+$file)}
}
$settings=Join-Path $root 'site-agent.local.json'
if(Test-Path -LiteralPath $settings){throw 'Existing relay enrollment preserved; use an explicit rotation procedure'}
$acl=New-Object Security.AccessControl.DirectorySecurity
$acl.SetAccessRuleProtection($true,$false)
foreach($sid in @('S-1-5-18','S-1-5-32-544')){
    $acl.AddAccessRule((New-Object Security.AccessControl.FileSystemAccessRule((New-Object Security.Principal.SecurityIdentifier($sid)),'FullControl','ContainerInherit,ObjectInherit','None','Allow')))
}
Set-Acl -LiteralPath $root -AclObject $acl
& icacls.exe (Join-Path $root '*') /reset /T /C|Out-Null
if($LASTEXITCODE){throw 'Relay folder ACL protection failed'}
Add-Type -AssemblyName System.Security
$clear=[Text.Encoding]::UTF8.GetBytes($enrollment.token)
try{$protected=[Convert]::ToBase64String([Security.Cryptography.ProtectedData]::Protect($clear,$null,[Security.Cryptography.DataProtectionScope]::LocalMachine))}finally{[Array]::Clear($clear,0,$clear.Length)}
[ordered]@{id=$enrollment.id;computer=$enrollment.computer;kind='site';url=$enrollment.url;token_machine=$protected;networks=$enrollment.networks;directory_domain=$enrollment.directory_domain;directory_server=$enrollment.directory_server}|ConvertTo-Json -Depth 6|Set-Content -LiteralPath $settings -Encoding UTF8
$arguments='-NoProfile -WindowStyle Hidden -File "'+(Join-Path $root 'Run-SiteRelay.ps1')+'" -SourceRoot "'+$source+'" -PythonPath "'+$PythonPath+'"'
$action=New-ScheduledTaskAction -Execute (Join-Path $env:WINDIR 'System32\WindowsPowerShell\v1.0\powershell.exe') -Argument $arguments -WorkingDirectory $root
$trigger=New-ScheduledTaskTrigger -AtStartup
$account=New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest
$taskSettings=New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew -StartWhenAvailable -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
Register-ScheduledTask -TaskName $name -Action $action -Trigger $trigger -Principal $account -Settings $taskSettings|Out-Null
Start-ScheduledTask -TaskName $name
Write-Output 'Office relay installed as SYSTEM; no inbound firewall rule or device credentials were changed.'
Write-Output 'Securely remove the plaintext enrollment after verifying the first accepted report.'
