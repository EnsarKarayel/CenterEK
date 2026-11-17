$ErrorActionPreference='Stop'
$errors=$null;$tokens=$null
$ast=[Management.Automation.Language.Parser]::ParseFile((Join-Path (Split-Path -Parent $PSScriptRoot) 'Maintenance-Tasks.ps1'),[ref]$tokens,[ref]$errors)
if($errors){throw 'Maintenance script parse error'}
foreach($name in @('Assert-Owned','Test-OwnedMaintenanceProcess','Assert-TaskXml')){
    $function=$ast.Find({param($node) $node -is [Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq $name},$true)
    . ([scriptblock]::Create($function.Extent.Text))
}
$Root='C:\Program Files\CenterEK'
$wrapper=Join-Path $Root 'Run-SystemTask.ps1'
$exe=Join-Path $Root 'CenterEK.exe'
$ps=Join-Path $env:WINDIR 'System32\WindowsPowerShell\v1.0\powershell.exe'
function New-FixtureTask([string]$arguments,[string]$principal='SYSTEM',[string]$directory=$Root){
    return [pscustomobject]@{Principal=[pscustomobject]@{UserId=$principal};Actions=@([pscustomobject]@{Execute=$ps;Arguments=$arguments;WorkingDirectory=$directory})}
}
$arguments='-NoProfile -ExecutionPolicy RemoteSigned -WindowStyle Hidden -File "'+$wrapper+'" -Mode Server -PythonPath "C:\Python\python.exe" -ServerExecutable "'+$exe+'"'
Assert-Owned (New-FixtureTask $arguments)
$xml='<Task xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task"><Principals><Principal><UserId>S-1-5-18</UserId></Principal></Principals><Actions><Exec><Command>'+$ps+'</Command><Arguments>'+[Security.SecurityElement]::Escape($arguments)+'</Arguments><WorkingDirectory>'+$Root+'</WorkingDirectory></Exec></Actions></Task>'
Assert-TaskXml $xml
$rejected=$false
try{Assert-TaskXml ($xml.Replace('S-1-5-18','OtherUser'))}catch{$rejected=$true}
if(-not $rejected){throw 'Foreign XML principal accepted'}
foreach($task in @((New-FixtureTask $arguments 'OtherUser'),(New-FixtureTask $arguments 'SYSTEM' 'C:\Other'),(New-FixtureTask ('-Command x '+$arguments)),(New-FixtureTask ($arguments.Replace($exe,'C:\Other\CenterEK.exe'))))){
    $failed=$false
    try{Assert-Owned $task}catch{$failed=$true}
    if(-not $failed){throw 'Foreign task accepted'}
}
$cases=@(
    @($exe,('"'+$exe+'" --serve --root "'+$Root+'"'),$true),
    @($exe,('"'+$exe+'" --self-test'),$false),
    @('C:\Other\CenterEK.exe',('CenterEK.exe --serve --root "'+$Root+'"'),$false),
    @($ps,('powershell.exe -File "'+$wrapper+'" -Mode Server'),$true),
    @($ps,('powershell.exe -Command x -File "'+$wrapper+'"'),$false),
    @($ps,'powershell.exe -File "C:\Other\Run-SystemTask.ps1" -Mode Server',$false),
    @('C:\Windows\System32\sqlservr.exe',('anything -File "'+$wrapper+'"'),$false)
)
foreach($case in $cases){
    $actual=Test-OwnedMaintenanceProcess ([pscustomobject]@{ExecutablePath=$case[0];CommandLine=$case[1]})
    if($actual -ne $case[2]){throw ('Process ownership mismatch: '+$case[1])}
}
'PASS maintenance: task ownership and exact-root process guards'
