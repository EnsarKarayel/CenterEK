param([switch]$Apply,[string]$Inventory='C:\CenterEK\data\directory-inventory.json')
$ErrorActionPreference='Stop'
$python='C:\Program Files\Python311\python.exe'
if(-not(Test-Path -LiteralPath $python)){throw 'Office Python was not found'}
$arguments=@((Join-Path $PSScriptRoot 'domain_rollout.py'),'--inventory',$Inventory)
if($Apply){$arguments+='--apply'}
& $python @arguments
if($LASTEXITCODE){throw 'Rollout preparation failed; preserve output for diagnosis'}
