$ErrorActionPreference='Stop'
$python='C:\Program Files\Python311\python.exe'
& $python (Join-Path $PSScriptRoot 'create_linux_package.py') --root C:\CenterEK --computer VOLO-PRODDB --url https://192.168.1.15:8765
if($LASTEXITCODE){throw 'Linux package creation failed. Existing registration was preserved.'}
