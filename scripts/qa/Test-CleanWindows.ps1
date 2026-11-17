param([Parameter(Mandatory=$true)][string]$Bundle,
      [Parameter(Mandatory=$true)][string]$ReportFolder,
      [switch]$ConfirmIsolatedMachine)
$ErrorActionPreference='Stop'
$identity=[Security.Principal.WindowsIdentity]::GetCurrent()
if(-not (New-Object Security.Principal.WindowsPrincipal($identity)).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){throw 'Run inside the isolated test Windows as administrator'}
$machine=Get-CimInstance Win32_ComputerSystem
if(-not $ConfirmIsolatedMachine -or $machine.Model -notmatch 'Virtual Machine|VirtualBox|VMware' -or $env:COMPUTERNAME -eq 'VOLO' -or $env:COMPUTERNAME -eq 'DATASQL'){throw 'Explicitly confirmed isolated VM required; never run on the office servers'}
$target='C:\CenterEK-QA'
if(Test-Path -LiteralPath $target){throw 'Fresh VM required; target already exists'}
if(@(Get-ScheduledTask -TaskName 'CenterEK-*' -ErrorAction SilentlyContinue).Count){throw 'Fresh VM required; CenterEK tasks already exist'}
$python=@(foreach($key in @('HKLM:\SOFTWARE\Python\PythonCore','HKLM:\SOFTWARE\WOW6432Node\Python\PythonCore','HKCU:\SOFTWARE\Python\PythonCore')){if(Test-Path $key){Get-ChildItem $key}})
$pythonCommands=@(Get-Command python.exe,python3.exe -ErrorAction SilentlyContinue|Where-Object {$_.Source -notlike '*\Microsoft\WindowsApps\*'})
if($python.Count -or $pythonCommands.Count){throw 'A clean Windows image without Python is required'}
$exe=Join-Path ([IO.Path]::GetFullPath($Bundle)) 'CenterEK-Setup.exe'
if(-not(Test-Path -LiteralPath $exe)){throw 'Complete extracted bundle required'}
New-Item -ItemType Directory -Path $ReportFolder -Force|Out-Null
$result=[ordered]@{kind='isolated-windows';python_absent=$true;os=(Get-CimInstance Win32_OperatingSystem).Caption;build=[Environment]::OSVersion.Version.ToString();bundle_exe_sha256=(Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash.ToLower();steps=[ordered]@{};ok=$false;reboot_test='pending';uac_interaction='pending';outer_setup_ui='pending'}
$private=Join-Path $env:TEMP ('CenterEK-QA-'+[Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $private|Out-Null
& icacls.exe $private /inheritance:r /grant:r ('*'+$identity.User.Value+':(OI)(CI)(F)') '*S-1-5-18:(OI)(CI)(F)' '*S-1-5-32-544:(OI)(CI)(F)'|Out-Null
if($LASTEXITCODE){throw 'Cannot protect acceptance credentials'}
$options=Join-Path $private 'options.local.json'
$password=[Guid]::NewGuid().ToString('N')+'-'+[Guid]::NewGuid().ToString('N')
function Invoke-Packaged([string[]]$Arguments,[string]$Report){
    $process=Start-Process -FilePath $exe -ArgumentList $Arguments -WindowStyle Hidden -PassThru -Wait
    if($process.ExitCode -or -not(Test-Path -LiteralPath $Report) -or -not(Get-Content -LiteralPath $Report -Raw|ConvertFrom-Json).ok){throw 'Packaged operation failed; inspect isolated guest logs'}
}
try{
    $policy=Get-Content -LiteralPath (Join-Path $Bundle '_internal\release-policy.json') -Raw|ConvertFrom-Json
    if($policy.mode -eq 'commercial'){
        $signature=Get-AuthenticodeSignature -LiteralPath $exe
        if($signature.Status -ne 'Valid' -or -not $signature.TimeStamperCertificate){throw 'Commercial executable is not trusted by the clean Windows image'}
        $result.steps.trusted_signature=$true
        $result.publisher_thumbprint=$signature.SignerCertificate.Thumbprint
    }
    @{target=$target;username='qa-admin';password=$password;port=18765;mode='local';address='127.0.0.1';hostname='localhost';language='tr';endpoint=$true;directory=$false;trust_ca=$true;firewall=$false;auto_discover=$false}|ConvertTo-Json|Set-Content -LiteralPath $options -Encoding UTF8
    $installReport=Join-Path $private 'install.json'
    Invoke-Packaged @('--unattended-install',('"'+$options+'"'),'--report',('"'+$installReport+'"')) $installReport
    $result.steps.install=$true
    [Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12
    $base='https://127.0.0.1:18765'
    $session=New-Object Microsoft.PowerShell.Commands.WebRequestSession
    $body=@{username='qa-admin';password=$password}|ConvertTo-Json
    Invoke-RestMethod -Uri ($base+'/api/login') -Method Post -ContentType 'application/json' -Headers @{Origin=$base} -Body $body -WebSession $session|Out-Null
    $result.steps.login=$true
    $status=Invoke-RestMethod -Uri ($base+'/api/status') -WebSession $session
    $result.version=$status.version
    $result.license_mode=$status.license.status
    $result.steps.https=$true
    if($status.license.status -ne 'preview'){
        $installation=Get-Content -LiteralPath (Join-Path $target 'installation.local.json') -Raw|ConvertFrom-Json
        @{installation_id=$installation.installation_id;customer='CenterEK clean Windows QA';days=1}|ConvertTo-Json|Set-Content -LiteralPath (Join-Path $ReportFolder 'license-request.json') -Encoding UTF8
        $licensePath=Join-Path $ReportFolder 'qa-license.json'
        $activated=$false
        foreach($attempt in 1..150){
            if(Test-Path -LiteralPath $licensePath){
                Invoke-RestMethod -Uri ($base+'/api/license') -Method Post -ContentType 'application/json' -Headers @{Origin=$base} -Body (Get-Content -LiteralPath $licensePath -Raw) -WebSession $session|Out-Null
                $activated=$true;break
            }
            Start-Sleep -Seconds 2
        }
        if(-not $activated){throw 'Publisher-signed QA license was not provided'}
        $status=Invoke-RestMethod -Uri ($base+'/api/status') -WebSession $session
        $result.license_mode=$status.license.status
    }
    $tasks=@(Get-ScheduledTask -TaskName 'CenterEK-Server-System','CenterEK-Endpoint-System')
    if($tasks.Count -ne 2 -or @($tasks|Where-Object {$_.State -ne 'Running' -or $_.Principal.UserId -notin @('SYSTEM','S-1-5-18','NT AUTHORITY\SYSTEM') -or $_.Settings.ExecutionTimeLimit -ne 'PT0S'}).Count){throw 'SYSTEM tasks are not healthy'}
    $result.steps.system_tasks=$true
    $received=$false
    foreach($attempt in 1..30){
        $sessions=Invoke-RestMethod -Uri ($base+'/api/sessions') -WebSession $session
        if(@($sessions.computers).Count){$received=$true;break}
        Start-Sleep -Seconds 2
    }
    if(-not $received){throw 'No endpoint telemetry reached the isolated panel'}
    $result.steps.endpoint_received=$true
    $entry=Get-ItemProperty -LiteralPath 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\CenterEK'
    if($entry.InstallLocation -ine $target){throw 'Apps & Features registration missing'}
    $result.steps.windows_registration=$true
    $removeReport=Join-Path $private 'remove.json'
    Invoke-Packaged @('--maintenance-action','uninstall','--root',('"'+$target+'"'),'--report',('"'+$removeReport+'"')) $removeReport
    if((Test-Path -LiteralPath (Join-Path $target 'CenterEK.exe')) -or @(Get-ScheduledTask -TaskName 'CenterEK-*' -ErrorAction SilentlyContinue).Count){throw 'Uninstall left code/tasks behind'}
    if(-not(Test-Path -LiteralPath (Join-Path $target 'data\monitor.sqlite3'))){throw 'Uninstall removed customer data'}
    $result.steps.uninstall_preserves_data=$true
    $restoreReport=Join-Path $private 'restore.json'
    Invoke-Packaged @('--maintenance-action','restore_uninstalled','--root',('"'+$target+'"'),'--report',('"'+$restoreReport+'"')) $restoreReport
    Invoke-RestMethod -Uri ($base+'/api/login') -Method Post -ContentType 'application/json' -Headers @{Origin=$base} -Body $body -WebSession $session|Out-Null
    $result.steps.restored_same_account=$true
    $result.ok=$true
}catch{$result.error_type=$_.Exception.GetType().FullName;throw}
finally{
    $password=$null;$body=$null
    Remove-Item -LiteralPath $options -Force -ErrorAction SilentlyContinue
    $result|ConvertTo-Json -Depth 8|Set-Content -LiteralPath (Join-Path $ReportFolder 'clean-windows-report.json') -Encoding UTF8
}
