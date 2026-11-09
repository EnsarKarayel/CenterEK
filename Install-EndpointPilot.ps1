$ErrorActionPreference='Stop'
$root=Split-Path -Parent $MyInvocation.MyCommand.Path
$enrollment=Join-Path $root 'enrollment.local.json'
$settings=Join-Path $root 'agent.local.json'
$ca=Join-Path $root 'panel-ca.pem'
if(-not(Test-Path -LiteralPath $settings)){
 & (Join-Path $root 'Setup-Agent.ps1') -EnrollmentFile $enrollment -OutputFile $settings
}
$configuration=Get-Content -LiteralPath $settings -Raw|ConvertFrom-Json
if($configuration.kind -ne 'endpoint' -or $configuration.computer.Split('.')[0] -ine $env:COMPUTERNAME){throw 'This package belongs to a different computer'}
& (Join-Path $root 'Install-SystemTask.ps1') -Mode Endpoint -AgentConfig $settings -CACertificate $ca
Write-Output 'Endpoint installed. SYSTEM reports IP, sessions, RAM and disks; no inbound port was opened.'
