$ErrorActionPreference='Stop'
$failed=$false
$root=Resolve-Path (Join-Path $PSScriptRoot '../..')
$files=@(Get-ChildItem -LiteralPath $root -Filter '*.ps1')+@(Get-ChildItem -LiteralPath (Join-Path $root 'scripts') -Filter '*.ps1' -Recurse)
foreach($file in $files){
    $tokens=$null;$errors=$null
    [Management.Automation.Language.Parser]::ParseFile($file.FullName,[ref]$tokens,[ref]$errors)|Out-Null
    if($errors.Count){$failed=$true;Write-Output $file.Name;$errors|ForEach-Object {Write-Output $_.Message}}
}
if($failed){throw 'PowerShell parse checks failed'}
Write-Output ('PowerShell parse checks passed: '+$files.Count+' scripts')
