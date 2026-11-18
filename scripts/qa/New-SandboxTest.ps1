param([Parameter(Mandatory=$true)][string]$ReleaseFolder,[Parameter(Mandatory=$true)][string]$OutputFolder,[string]$PreviousReleaseFolder)
$ErrorActionPreference='Stop'
$release=(Resolve-Path -LiteralPath $ReleaseFolder).Path
$output=[IO.Path]::GetFullPath($OutputFolder)
if(Test-Path -LiteralPath $output){throw 'Choose a new dedicated test folder'}
New-Item -ItemType Directory -Path $output|Out-Null
$payload=Join-Path $output 'payload'
$reports=Join-Path $output 'reports'
New-Item -ItemType Directory -Path $payload,$reports|Out-Null
$manifest=Get-Content -LiteralPath (Join-Path $release 'release-manifest.json') -Raw|ConvertFrom-Json
$archive=Join-Path $release $manifest.archive
if((Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash -ine $manifest.sha256){throw 'Release archive hash mismatch'}
Expand-Archive -LiteralPath $archive -DestinationPath $payload
if($manifest.setup){
    $setup=Join-Path $release $manifest.setup
    if((Get-FileHash -LiteralPath $setup -Algorithm SHA256).Hash -ine $manifest.setup_sha256){throw 'Setup hash mismatch'}
    Copy-Item -LiteralPath $setup -Destination $payload
}
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'Test-CleanWindows.ps1') -Destination $payload
$guestArguments='-NoProfile -ExecutionPolicy RemoteSigned -File C:\CenterEK-Payload\Test-CleanWindows.ps1 -Bundle C:\CenterEK-Payload\CenterEK-Setup -ReportFolder C:\CenterEK-Reports -ConfirmIsolatedMachine'
if($manifest.setup){$guestArguments+=' -SetupPath "C:\CenterEK-Payload\'+$manifest.setup+'"'}
if($PreviousReleaseFolder){
    $previous=(Resolve-Path -LiteralPath $PreviousReleaseFolder).Path
    $previousManifest=[IO.File]::ReadAllText((Join-Path $previous 'release-manifest.json'))|ConvertFrom-Json
    $previousArchive=Join-Path $previous $previousManifest.archive
    if((Get-FileHash -LiteralPath $previousArchive -Algorithm SHA256).Hash -ine $previousManifest.sha256){throw 'Previous release archive hash mismatch'}
    $previousPayload=Join-Path $payload 'Previous'
    New-Item -ItemType Directory -Path $previousPayload|Out-Null
    Expand-Archive -LiteralPath $previousArchive -DestinationPath $previousPayload
    $guestArguments+=' -PreviousBundle C:\CenterEK-Payload\Previous\CenterEK-Setup'
}
$launch="Start-Process powershell.exe -Verb RunAs -WindowStyle Hidden -ArgumentList '"+$guestArguments.Replace("'","''")+"'"
$escape={param($value) [Security.SecurityElement]::Escape($value)}
$xml='<Configuration><Networking>Disable</Networking><vGPU>Disable</vGPU><ClipboardRedirection>Disable</ClipboardRedirection><MappedFolders><MappedFolder><HostFolder>'+(& $escape $payload)+'</HostFolder><SandboxFolder>C:\CenterEK-Payload</SandboxFolder><ReadOnly>true</ReadOnly></MappedFolder><MappedFolder><HostFolder>'+(& $escape $reports)+'</HostFolder><SandboxFolder>C:\CenterEK-Reports</SandboxFolder><ReadOnly>false</ReadOnly></MappedFolder></MappedFolders><LogonCommand><Command>powershell.exe -NoProfile -Command '+(& $escape ('"'+$launch+'"'))+'</Command></LogonCommand></Configuration>'
$path=Join-Path $output 'CenterEK-CleanWindows.wsb'
$xml|Set-Content -LiteralPath $path -Encoding UTF8
$manual=[xml]$xml
[void]$manual.Configuration.RemoveChild($manual.Configuration.LogonCommand)
$manual.Save((Join-Path $output 'CenterEK-ManualSetup.wsb'))
'SANDBOX_CONFIG='+$path
'REPORT_FOLDER='+$reports
'NOT_STARTED: open the WSB only on a host with Windows Sandbox installed; approve UAC inside the disposable guest.'
