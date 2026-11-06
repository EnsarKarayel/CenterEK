# Executed as SYSTEM by Azure VM Run Command. No public RDP/SSH or SAS required.
param([Parameter(Mandatory=$true)][ValidatePattern('^[a-z0-9]{3,24}$')][string]$StorageAccount,
      [Parameter(Mandatory=$true)][ValidatePattern('^[a-f0-9]{40}/[a-f0-9]{64}\.zip$')][string]$BlobName,
      [Parameter(Mandatory=$true)][ValidatePattern('^[a-f0-9]{64}$')][string]$ArchiveSHA256,
      [Parameter(Mandatory=$true)][ValidatePattern('^[a-f0-9]{40}$')][string]$Commit,
      [Parameter(Mandatory=$true)][ValidatePattern('^[a-zA-Z0-9-]{3,24}$')][string]$VaultName,
      [Parameter(Mandatory=$true)][string]$ClientCIDR)
$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest
[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12
$root='C:\CenterEK'
$work='C:\CenterEK-deploy'
$taskStates=@{}
if($BlobName -cne ($Commit+'/'+$ArchiveSHA256+'.zip')){throw 'Commit, digest and blob name must match'}
function Assert-SafeTree([string]$Path){
    $full=[IO.Path]::GetFullPath($Path)
    if($full -ine $root -and -not $full.StartsWith($work+'\',[StringComparison]::OrdinalIgnoreCase) -and $full -ine $work){throw 'Path outside deployment folders'}
    if(Test-Path -LiteralPath $full){
        if((Get-Item -LiteralPath $full).Attributes -band [IO.FileAttributes]::ReparsePoint){throw 'Reparse point rejected'}
        if(@(Get-ChildItem -LiteralPath $full -Recurse -Force|Where-Object {$_.Attributes -band [IO.FileAttributes]::ReparsePoint}).Count){throw 'Reparse point rejected'}
    }
}
function Protect-Folder([string]$Path){
    $acl=New-Object Security.AccessControl.DirectorySecurity
    $acl.SetAccessRuleProtection($true,$false)
    foreach($sid in @('S-1-5-18','S-1-5-32-544')){
        $identity=New-Object Security.Principal.SecurityIdentifier($sid)
        $acl.AddAccessRule((New-Object Security.AccessControl.FileSystemAccessRule($identity,'FullControl','ContainerInherit,ObjectInherit','None','Allow')))
    }
    Set-Acl -LiteralPath $Path -AclObject $acl
}
function Get-IdentityToken([string]$Resource){
    $uri='http://169.254.169.254/metadata/identity/oauth2/token?api-version=2018-02-01&resource='+[Uri]::EscapeDataString($Resource)
    return (Invoke-RestMethod -Uri $uri -Headers @{Metadata='true'} -TimeoutSec 30).access_token
}
function Stop-Application{
    foreach($name in @('CenterEK-Server-System','CenterEK-Endpoint-System','CenterEK-Directory-System')){
        $task=Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
        if($task){
            if(-not @($task.Actions|Where-Object {$_.Arguments -and $_.Arguments.Contains($root+'\Run-SystemTask.ps1')}).Count){throw 'Task belongs to a different application folder'}
            if(-not $taskStates.ContainsKey($name)){$taskStates[$name]=[bool]$task.Settings.Enabled}
            Disable-ScheduledTask -TaskName $name|Out-Null
            Stop-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
        }
    }
    Get-CimInstance Win32_Process -Filter "Name='CenterEK.exe'"|Where-Object {$_.ExecutablePath -ieq ($root+'\CenterEK.exe')}|ForEach-Object {Stop-Process -Id $_.ProcessId -Force -ErrorAction Stop}
    Start-Sleep -Seconds 2
}
function Start-Application{
    foreach($name in @('CenterEK-Server-System','CenterEK-Endpoint-System','CenterEK-Directory-System')){
        if($taskStates.ContainsKey($name) -and $taskStates[$name]){Enable-ScheduledTask -TaskName $name|Out-Null;Start-ScheduledTask -TaskName $name}
    }
}
function Test-Application{
    $network=Get-Content -LiteralPath (Join-Path $root 'server.local.json') -Raw|ConvertFrom-Json
    $url='https://'+$network.bind+':'+$network.port+'/healthz'
    for($attempt=0;$attempt -lt 45;$attempt++){
        try{if((Invoke-RestMethod -Uri $url -TimeoutSec 3).status -eq 'ok'){return}}catch{}
        Start-Sleep -Seconds 2
    }
    throw 'HTTPS/database/worker readiness check failed'
}
# RFC1918 clients only. Never accept 0.0.0.0/0 or a public source range.
if($ClientCIDR -notmatch '^(\d+\.\d+\.\d+\.\d+)/(\d{1,2})$'){throw 'A private IPv4 client CIDR is required'}
$clientAddress=[Net.IPAddress]::Parse($Matches[1]);$prefix=[int]$Matches[2];$bytes=$clientAddress.GetAddressBytes()
$private=($bytes[0] -eq 10 -and $prefix -ge 8) -or ($bytes[0] -eq 172 -and $bytes[1] -ge 16 -and $bytes[1] -le 31 -and $prefix -ge 12) -or ($bytes[0] -eq 192 -and $bytes[1] -eq 168 -and $prefix -ge 16)
if(-not $private -or $prefix -gt 32){throw 'Only a bounded private client network is supported'}
Assert-SafeTree $work;Assert-SafeTree $root
New-Item -ItemType Directory -Path $work -Force|Out-Null
Protect-Folder $work
$lock=[IO.File]::Open((Join-Path $work 'deployment.lock'),[IO.FileMode]::OpenOrCreate,[IO.FileAccess]::ReadWrite,[IO.FileShare]::None)
$staging=Join-Path $work ('staging\'+$Commit+'-'+[Guid]::NewGuid().ToString('N'))
$backup=$null;$backupReady=$false;$existing=Test-Path -LiteralPath (Join-Path $root 'installation.local.json');$stopped=$false
try{
    New-Item -ItemType Directory -Path $staging -Force|Out-Null
    $zip=Join-Path $staging 'release.zip'
    $token=Get-IdentityToken 'https://storage.azure.com/'
    Invoke-WebRequest -UseBasicParsing -Uri ('https://'+$StorageAccount+'.blob.core.windows.net/releases/'+$BlobName) -Headers @{Authorization=('Bearer '+$token);'x-ms-version'='2021-12-02'} -OutFile $zip -TimeoutSec 300
    $token=$null
    if((Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash.ToLowerInvariant() -cne $ArchiveSHA256){throw 'Downloaded artifact digest mismatch'}
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $package=[IO.Compression.ZipFile]::OpenRead($zip)
    try{
        if($package.Entries.Count -gt 15000){throw 'Too many archive entries'}
        $total=0L
        foreach($entry in $package.Entries){
            $name=$entry.FullName.Replace('\','/')
            if(-not $name.StartsWith('CenterEK-Setup/') -or $name.Contains(':') -or $name -match '(^|/)\.\.(/|$)' -or $name.Contains('.local.') -or $name -match '(^|/)(data|certs|\.git)(/|$)'){throw 'Unsafe release entry'}
            if((($entry.ExternalAttributes -shr 16) -band 0xF000) -eq 0xA000){throw 'Archive symlink rejected'}
            $total+=$entry.Length
            if($total -gt 600MB){throw 'Expanded archive too large'}
        }
    }finally{$package.Dispose()}
    Expand-Archive -LiteralPath $zip -DestinationPath (Join-Path $staging 'expanded')
    $bundle=Join-Path $staging 'expanded\CenterEK-Setup'
    $exe=Join-Path $bundle 'CenterEK-Setup.exe'
    $selfTest=Join-Path $staging 'self-test.json'
    $process=Start-Process -FilePath $exe -ArgumentList @('--self-test','--report',('"'+$selfTest+'"')) -PassThru -Wait -WindowStyle Hidden
    if($process.ExitCode -or -not (Get-Content -LiteralPath $selfTest -Raw|ConvertFrom-Json).ok){throw 'Guest package self-test failed'}
    if($existing){
        $installed=Get-Content -LiteralPath (Join-Path $root 'installation.local.json') -Raw|ConvertFrom-Json
        if($installed.status -ne 'ready'){throw 'Previous installation is incomplete; manual recovery required'}
        # Source-based customer installations are never silently converted.
        if(-not (Test-Path -LiteralPath (Join-Path $root 'CenterEK.exe'))){throw 'Packaged Azure installation required'}
        Stop-Application;$stopped=$true
        $backup=Join-Path $work ('backups\'+(Get-Date -Format yyyyMMddHHmmss)+'-'+$Commit)
        New-Item -ItemType Directory -Path $backup -Force|Out-Null
        Copy-Item -LiteralPath $root -Destination (Join-Path $backup 'CenterEK') -Recurse
        $backupReady=$true
        foreach($folder in @('_internal','web')){
            $destination=Join-Path $root $folder
            Assert-SafeTree $root
            Remove-Item -LiteralPath $destination -Recurse -Force
        }
        Copy-Item -LiteralPath $exe -Destination (Join-Path $root 'CenterEK.exe') -Force
        Copy-Item -LiteralPath (Join-Path $bundle '_internal') -Destination (Join-Path $root '_internal') -Recurse
        Copy-Item -LiteralPath (Join-Path $bundle '_internal\web') -Destination (Join-Path $root 'web') -Recurse
        Get-ChildItem -LiteralPath (Join-Path $bundle '_internal') -Filter '*.ps1'|ForEach-Object {Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $root $_.Name) -Force}
        Start-Application
    }else{
        if(Test-Path -LiteralPath $root){throw 'Fresh dedicated installation folder required'}
        $address=Invoke-RestMethod -Uri 'http://169.254.169.254/metadata/instance/network/interface/0/ipv4/ipAddress/0/privateIpAddress?api-version=2021-02-01&format=text' -Headers @{Metadata='true'} -TimeoutSec 30
        $token=Get-IdentityToken 'https://vault.azure.net'
        $secret=Invoke-RestMethod -Uri ('https://'+$VaultName+'.vault.azure.net/secrets/centerek-initial-admin?api-version=7.4') -Headers @{Authorization=('Bearer '+$token)} -TimeoutSec 30
        $options=Join-Path $staging 'options.local.json'
        @{target=$root;username='azure-admin';password=$secret.value;mode='lan';address=[string]$address;hostname=$env:COMPUTERNAME.ToLowerInvariant();port=8765;language='en';endpoint=$true;directory=$false;trust_ca=$true;firewall=$false;auto_discover=$false}|ConvertTo-Json|Set-Content -LiteralPath $options -Encoding UTF8
        $secret=$null;$token=$null
        $report=Join-Path $staging 'install-report.json'
        try{
            $process=Start-Process -FilePath $exe -ArgumentList @('--unattended-install',('"'+$options+'"'),'--report',('"'+$report+'"')) -PassThru -Wait -WindowStyle Hidden
            if($process.ExitCode -or -not (Get-Content -LiteralPath $report -Raw|ConvertFrom-Json).ok){throw 'Initial installation failed; private logs retained'}
        }finally{if(Test-Path -LiteralPath $options){Remove-Item -LiteralPath $options -Force}}
    }
    Test-Application
    $rule=Get-NetFirewallRule -Name 'CenterEK-Azure-VPN' -ErrorAction SilentlyContinue
    if($rule){$rule|Remove-NetFirewallRule}
    New-NetFirewallRule -Name 'CenterEK-Azure-VPN' -DisplayName 'CenterEK private VPN clients' -Direction Inbound -Action Allow -Protocol TCP -LocalPort 8765 -RemoteAddress $ClientCIDR -Profile Any|Out-Null
    @{commit=$Commit;sha256=$ArchiveSHA256;deployed_at=[DateTime]::UtcNow.ToString('o');backup=$backup}|ConvertTo-Json|Set-Content -LiteralPath (Join-Path $root 'data\release.local.json') -Encoding UTF8
    @{commit=$Commit;status='healthy';at=[DateTime]::UtcNow.ToString('o')}|ConvertTo-Json -Compress|Add-Content -LiteralPath (Join-Path $work 'deployments.jsonl') -Encoding UTF8
    Write-Output ('CENTEREK_DEPLOY_OK '+$Commit)
}catch{
    $failure=$_.Exception.GetType().Name
    if($backupReady){
        Stop-Application
        Assert-SafeTree $root;Assert-SafeTree $backup
        $failed=Join-Path $staging 'failed-installation'
        Assert-SafeTree $failed
        Move-Item -LiteralPath $root -Destination $failed
        Copy-Item -LiteralPath (Join-Path $backup 'CenterEK') -Destination $root -Recurse
        Start-Application
        Test-Application
        Write-Output ('CENTEREK_ROLLED_BACK '+$Commit)
    }elseif($stopped){Start-Application}
    @{commit=$Commit;status='failed';error_type=$failure;at=[DateTime]::UtcNow.ToString('o')}|ConvertTo-Json -Compress|Add-Content -LiteralPath (Join-Path $work 'deployments.jsonl') -Encoding UTF8
    throw 'CenterEK deployment failed. Inspect the private guest deployment history.'
}finally{$lock.Dispose()}
