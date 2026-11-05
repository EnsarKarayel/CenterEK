param([Parameter(Mandatory=$true)][ValidateSet('Server','Directory','Endpoint')][string]$Mode,
      [string]$AgentConfig,[string]$CACertificate,[string]$PythonPath='C:\Program Files\Python311\python.exe')
$ErrorActionPreference='Stop'
$identity=[Security.Principal.WindowsIdentity]::GetCurrent()
if (-not (New-Object Security.Principal.WindowsPrincipal($identity)).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { throw 'Yönetici CMD ile çalıştırın.' }
$root=Split-Path -Parent $MyInvocation.MyCommand.Path
$root=[IO.Path]::GetFullPath($root)
if ($root.TrimEnd('\') -eq [IO.Path]::GetPathRoot($root).TrimEnd('\') -or $root -ieq $env:WINDIR) { throw 'Program klasörü gerekli.' }
if ((Get-Item -LiteralPath $root).Attributes -band [IO.FileAttributes]::ReparsePoint) {throw 'Program klasörü sembolik bağlantı olamaz.'}
if (@(Get-ChildItem -LiteralPath $root -Recurse -Force | Where-Object {$_.Attributes -band [IO.FileAttributes]::ReparsePoint}).Count) {throw 'Program klasöründe sembolik bağlantı var; izinler değiştirilmedi.'}
$wrapper=Join-Path $root 'Run-SystemTask.ps1'
if (-not (Test-Path -LiteralPath $wrapper)) { throw 'Run-SystemTask.ps1 aynı klasörde olmalı.' }
if ($root.Contains('"') -or $PythonPath.Contains('"')) { throw 'Geçersiz yol.' }
$secureFolder=Join-Path $root 'data\secure'
$taskName='CenterEK-'+$Mode+'-System'
$previous=Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($previous -and -not @($previous.Actions | Where-Object {$_.Arguments -and $_.Arguments.IndexOf($wrapper,[StringComparison]::OrdinalIgnoreCase) -ge 0}).Count) { throw 'Aynı isimde başka bir görev var; değiştirilmedi.' }
$legacy=Get-ScheduledTask -TaskName ('CenterEK-'+$Mode.ToLower()) -ErrorAction SilentlyContinue
if ($legacy -and -not @($legacy.Actions | Where-Object {$_.Arguments -and $_.Arguments.IndexOf($root,[StringComparison]::OrdinalIgnoreCase) -ge 0}).Count) { throw 'Eski görev farklı klasöre bağlı; otomatik değiştirilmedi.' }
if ($Mode -eq 'Server') {
    if (-not (Test-Path -LiteralPath $PythonPath)) { throw 'Python yolu bulunamadı.' }
    if (-not (Test-Path -LiteralPath (Join-Path $root 'start.py'))) { throw 'CenterEK sunucu klasöründe çalıştırın.' }
    $process=Start-Process -FilePath $PythonPath -ArgumentList @(('"'+(Join-Path $root 'start.py')+'"'),'--non-interactive','--check-config') -WorkingDirectory $root -Wait -PassThru -WindowStyle Hidden
    if ($process.ExitCode -ne 0) { throw 'Önce service_secrets.py ile arka plan kimliklerini kaydedin; ayarları kontrol edin.' }
    $networkFile=Join-Path $root 'server.local.json'
    $address='127.0.0.1';$port=8765
    if (Test-Path -LiteralPath $networkFile) { $network=Get-Content -LiteralPath $networkFile -Raw|ConvertFrom-Json;if($network.bind){$address=$network.bind};if($network.port){$port=$network.port} }
    if ($address -eq '0.0.0.0') {$address='127.0.0.1'}
    $client=New-Object Net.Sockets.TcpClient
    try {$attempt=$client.BeginConnect($address,$port,$null,$null);if($attempt.AsyncWaitHandle.WaitOne(1000) -and $client.Connected){throw 'Önce elle çalışan start.py penceresinde Ctrl+C yapın.'}} finally {$client.Close()}
} else {
    $required=if($Mode -eq 'Directory'){@('Export-DirectoryInventory.ps1','Send-DirectoryInventory.ps1','Send-Report.ps1')}else{@('Collect-EndpointSessions.ps1','Send-Report.ps1')}
    foreach($file in $required){if(-not(Test-Path -LiteralPath (Join-Path $root $file))){throw ('Eksik dosya: '+$file)}}
    if (-not $AgentConfig -or -not $CACertificate) { throw '-AgentConfig ve -CACertificate gerekli.' }
    $AgentConfig=(Resolve-Path -LiteralPath $AgentConfig).Path
    $CACertificate=(Resolve-Path -LiteralPath $CACertificate).Path
    $configuration=Get-Content -LiteralPath $AgentConfig -Raw | ConvertFrom-Json
    if ($configuration.kind -ine $Mode -or $configuration.computer.Split('.')[0] -ine $env:COMPUTERNAME) { throw 'Ajan türü/bilgisayar eşleşmiyor.' }
    $uri=[Uri]$configuration.url
    if ($uri.Scheme -ne 'https') {throw 'HTTPS gerekli.'}
    Add-Type -AssemblyName System.Security
    if ($configuration.token_machine) {
        $clear=[Security.Cryptography.ProtectedData]::Unprotect([Convert]::FromBase64String($configuration.token_machine),$null,[Security.Cryptography.DataProtectionScope]::LocalMachine)
    } else {
        $secret=ConvertTo-SecureString $configuration.token_encrypted
        $ptr=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($secret)
        try {$clear=[Text.Encoding]::UTF8.GetBytes([Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr))} finally {[Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)}
    }
    try {$machine=[Convert]::ToBase64String([Security.Cryptography.ProtectedData]::Protect($clear,$null,[Security.Cryptography.DataProtectionScope]::LocalMachine))} finally {[Array]::Clear($clear,0,$clear.Length)}
    New-Item -ItemType Directory -Path $secureFolder -Force | Out-Null
    & icacls.exe $secureFolder /inheritance:r /grant:r '*S-1-5-18:(OI)(CI)(F)' '*S-1-5-32-544:(OI)(CI)(F)' | Out-Null
    if ($LASTEXITCODE -ne 0) {throw 'Gizli klasör izinleri uygulanamadı.'}
    $systemConfig=Join-Path $secureFolder 'agent.system.local.json'
    [ordered]@{id=$configuration.id;computer=$configuration.computer;kind=$configuration.kind;url=$configuration.url;token_machine=$machine} | ConvertTo-Json | Set-Content -LiteralPath $systemConfig -Encoding UTF8
    $certificate=New-Object Security.Cryptography.X509Certificates.X509Certificate2($CACertificate)
    if (-not @($certificate.Extensions|Where-Object {$_.Oid.Value -eq '2.5.29.19' -and $_.CertificateAuthority}).Count) {throw 'CA sertifikası gerekli.'}
    & certutil.exe -addstore Root $CACertificate | Out-Null
    if ($LASTEXITCODE -ne 0) {throw 'Makine sertifika deposu güncellenemedi.'}
    $AgentConfig=$systemConfig
}
# SYSTEM executes these scripts: replace the program ACL with SYSTEM/admin only,
# then remove child-specific write grants by resetting inheritance.
$acl=New-Object Security.AccessControl.DirectorySecurity
$acl.SetAccessRuleProtection($true,$false)
foreach($sid in @('S-1-5-18','S-1-5-32-544')){
    $principalSid=New-Object Security.Principal.SecurityIdentifier($sid)
    $rule=New-Object Security.AccessControl.FileSystemAccessRule($principalSid,'FullControl','ContainerInherit,ObjectInherit','None','Allow')
    $acl.AddAccessRule($rule)
}
Set-Acl -LiteralPath $root -AclObject $acl
& icacls.exe (Join-Path $root '*') /reset /T /C | Out-Null
if ($LASTEXITCODE -ne 0) {throw 'Program dosyası izinleri uygulanamadı; görev kurulmadı.'}
$backups=Join-Path $root 'data\task-backups'
New-Item -ItemType Directory -Path $backups -Force | Out-Null
foreach($item in @($previous,$legacy)) {if($item){Export-ScheduledTask -TaskName $item.TaskName | Set-Content -LiteralPath (Join-Path $backups ($item.TaskName+'-'+(Get-Date -Format yyyyMMddHHmmss)+'.xml')) -Encoding UTF8}}
$arguments='-NoProfile -WindowStyle Hidden -File "'+$wrapper+'" -Mode '+$Mode+' -PythonPath "'+$PythonPath+'"'
if($Mode -ne 'Server'){$arguments+=' -AgentConfig "'+$AgentConfig+'"'}
$action=New-ScheduledTaskAction -Execute (Join-Path $env:WINDIR 'System32\WindowsPowerShell\v1.0\powershell.exe') -Argument $arguments -WorkingDirectory $root
$startup=New-ScheduledTaskTrigger -AtStartup
$recovery=New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(5) -RepetitionInterval (New-TimeSpan -Minutes 5) -RepetitionDuration (New-TimeSpan -Days 3650)
$recovery.Repetition.Duration=''
$principal=New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest
$settings=New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 99 -RestartInterval (New-TimeSpan -Minutes 1) -MultipleInstances IgnoreNew -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
if($previous){Stop-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue}
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger @($startup,$recovery) -Principal $principal -Settings $settings -Force | Out-Null
if($legacy){Disable-ScheduledTask -TaskName $legacy.TaskName|Out-Null;Stop-ScheduledTask -TaskName $legacy.TaskName -ErrorAction SilentlyContinue}
Start-ScheduledTask -TaskName $taskName
Write-Host "Kuruldu: $taskName. SYSTEM hesabıyla açılışta ve oturum kapalıyken çalışır; görünür pencere açmaz."
Write-Host "Günlük: $root\data\logs\$($Mode.ToLower()).log"
