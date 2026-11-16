$ErrorActionPreference='Stop'
$tokens=$null;$errors=$null
$ast=[Management.Automation.Language.Parser]::ParseFile((Join-Path (Split-Path -Parent $PSScriptRoot) 'Recover-OfficeMonitor.ps1'),[ref]$tokens,[ref]$errors)
if($errors){throw 'Recovery parse error'}
$function=$ast.Find({param($node) $node -is [Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq 'Test-OwnedMonitorProcess'},$true)
. ([scriptblock]::Create($function.Extent.Text))
$cases=@(
    @('python.exe','"C:\Program Files\Python311\python.exe" -u C:\CenterEK\start.py --non-interactive',$true),
    @('python.exe','python.exe "C:\Center EK\start.py" --non-interactive',$true,'C:\Center EK'),
    @('python.exe','python.exe C:\CenterEK2\start.py',$false),
    @('python.exe','python.exe -c "print('' C:\CenterEK\start.py '')"',$false),
    @('python.exe','python.exe C:\ERP\start.py',$false),
    @('sqlservr.exe','sqlservr.exe C:\CenterEK\start.py',$false),
    @('powershell.exe','powershell.exe -NoProfile -File "C:\CenterEK\Run-SystemTask.ps1" -Mode Server',$true),
    @('powershell.exe','powershell.exe -File "C:\CenterEK\Run-SystemTask.ps1" -Mode Directory',$false),
    @('powershell.exe','powershell.exe -File "C:\Other\Run-SystemTask.ps1" -Mode Server',$false),
    @('powershell.exe','powershell.exe -Command anything -File "C:\CenterEK\Run-SystemTask.ps1" -Mode Server',$false)
)
foreach($case in $cases){
    $root=if($case.Count -eq 4){$case[3]}else{'C:\CenterEK'}
    $actual=Test-OwnedMonitorProcess ([pscustomobject]@{Name=$case[0];CommandLine=$case[1]}) $root
    if($actual -ne $case[2]){throw ('Unsafe process ownership classification: '+$case[1])}
}
Write-Output 'PASS exact-root process ownership: other Python, SQL, mode, prefix and inline commands excluded'
