# Computer startup script: executes as the domain computer's SYSTEM account.
$ErrorActionPreference='Stop'
if([Security.Principal.WindowsIdentity]::GetCurrent().User.Value -ne 'S-1-5-18'){throw 'Computer startup SYSTEM context required'}
$machine=Get-CimInstance Win32_ComputerSystem
if(-not $machine.PartOfDomain -or $machine.DomainRole -ne 1){exit 0}
$root=Join-Path $env:ProgramData 'CenterEK-Agent'
if(Test-Path -LiteralPath $root){
    $task=Get-ScheduledTask -TaskName 'CenterEK-Endpoint-System' -ErrorAction SilentlyContinue
    if($task){exit 0}
    throw 'Existing installation requires repair; it was not overwritten'
}
if($env:COMPUTERNAME -notmatch '^[A-Za-z0-9][A-Za-z0-9-]{0,14}$'){throw 'Invalid computer name'}
$package=Join-Path $PSScriptRoot ('packages\'+$env:COMPUTERNAME)
if(-not(Test-Path -LiteralPath (Join-Path $package 'enrollment.local.json'))){exit 0}
& (Join-Path $package 'Install-EndpointPilot.ps1')
# Remove only the local plaintext bootstrap copy after successful task installation.
if(Get-ScheduledTask -TaskName 'CenterEK-Endpoint-System' -ErrorAction SilentlyContinue){
    Remove-Item -LiteralPath (Join-Path $root 'enrollment.local.json') -Force
}
