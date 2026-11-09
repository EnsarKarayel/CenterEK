$ErrorActionPreference='Stop'
& 'C:\Program Files\Python311\python.exe' (Join-Path $PSScriptRoot 'create_windows_pilot.py')
if($LASTEXITCODE){throw 'Windows package creation failed; existing registration was preserved'}
