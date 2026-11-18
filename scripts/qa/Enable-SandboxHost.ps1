$ErrorActionPreference='Stop'
$identity=[Security.Principal.WindowsIdentity]::GetCurrent()
if(-not (New-Object Security.Principal.WindowsPrincipal($identity)).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){throw 'Windows administrator approval is required'}
$feature=Get-WindowsOptionalFeature -Online -FeatureName 'Containers-DisposableClientVM'
if($feature.State -eq 'Enabled'){'SANDBOX_ALREADY_ENABLED';return}
$result=Enable-WindowsOptionalFeature -Online -FeatureName 'Containers-DisposableClientVM' -All -NoRestart
$updated=Get-WindowsOptionalFeature -Online -FeatureName 'Containers-DisposableClientVM'
'SANDBOX_FEATURE='+$updated.State
'RESTART_NEEDED='+$result.RestartNeeded
'NO_RESTART_PERFORMED: save your work and restart manually when ready.'
