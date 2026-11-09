$ErrorActionPreference='Stop'
$python='C:\Program Files\Python311\python.exe'
if(-not(Test-Path -LiteralPath $python)){throw 'Python 3.11 was not found at the existing office installation path'}
$identity=[Security.Principal.WindowsIdentity]::GetCurrent()
$principal=New-Object Security.Principal.WindowsPrincipal($identity)
if(-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){throw 'Run in administrator CMD or PowerShell'}
$ErrorActionPreference='Continue'
& $python -c "import importlib.util,sys;sys.exit(0 if importlib.util.find_spec('pyVim') else 1)"
$dependencyMissing=$LASTEXITCODE -ne 0
$ErrorActionPreference='Stop'
if($dependencyMissing){
 & $python -m pip install --disable-pip-version-check pyvmomi==8.0.3.0.1
 if($LASTEXITCODE){throw 'ESXi SDK installation failed; existing monitor was not changed'}
}
& $python (Join-Path $PSScriptRoot 'office_setup.py') --root C:\CenterEK
if($LASTEXITCODE){throw 'Connection wizard failed; check the local error'}
