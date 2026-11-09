$ErrorActionPreference='Stop'
$identity=[Security.Principal.WindowsIdentity]::GetCurrent()
$principal=New-Object Security.Principal.WindowsPrincipal($identity)
if(-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){throw 'Open PowerShell as administrator; no files were changed.'}
& 'C:\Program Files\Python311\python.exe' (Join-Path $PSScriptRoot 'office_endpoint_update.py')
if($LASTEXITCODE){throw 'Endpoint field update failed; preserve backups and inspect the error.'}
