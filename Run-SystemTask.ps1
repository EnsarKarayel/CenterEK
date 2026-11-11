param([Parameter(Mandatory=$true)][ValidateSet('Server','Directory','Endpoint')][string]$Mode,
      [string]$AgentConfig,[string]$PythonPath='C:\Program Files\Python311\python.exe',[string]$ServerExecutable)
$ErrorActionPreference='Stop'
$root=Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $root
$logRoot=Join-Path $root 'data\logs'
New-Item -ItemType Directory -Path $logRoot -Force | Out-Null
$log=Join-Path $logRoot ($Mode.ToLower()+'.log')
function Write-CenterLog([string]$Message) {
    if ((Test-Path -LiteralPath $log) -and (Get-Item -LiteralPath $log).Length -gt 5MB) {
        Move-Item -LiteralPath $log -Destination ($log+'.1') -Force
    }
    ('{0} {1}' -f (Get-Date).ToUniversalTime().ToString('o'),$Message) | Out-File -FilePath $log -Append -Encoding utf8
}
if ($Mode -eq 'Server') {
    $env:CENTEREK_RUN_MODE='background'
    if($ServerExecutable){$executable=$ServerExecutable;$arguments=@('--serve','--root',('"'+$root+'"'))}
    else{$executable=$PythonPath;$arguments=@('-u',(Join-Path $root 'start.py'),'--non-interactive')}
} else {
    $executable=Join-Path $env:WINDIR 'System32\WindowsPowerShell\v1.0\powershell.exe'
    $script=if ($Mode -eq 'Directory') {'Send-DirectoryInventory.ps1'} else {'Collect-EndpointSessions.ps1'}
    $arguments=@('-NoProfile','-ExecutionPolicy','RemoteSigned','-File',(Join-Path $root $script),'-AgentConfig',$AgentConfig,'-Watch')
    if($Mode -eq 'Directory'){$arguments+=@('-OutputFile',(Join-Path $root 'data\directory-inventory.local.json'))}
    else{$arguments+=@('-OutputDirectory',(Join-Path $root 'data\endpoint-sessions'))}
}
while ($true) {
    try {
        Write-CenterLog ('Başlatılıyor: '+$Mode)
        $ErrorActionPreference='Continue'
        if($Mode -eq 'Server' -and $ServerExecutable){
            $process=Start-Process -FilePath $executable -ArgumentList $arguments -WorkingDirectory $root -Wait -PassThru -WindowStyle Hidden
            $code=$process.ExitCode
        } else {
            & $executable @arguments 2>&1 | ForEach-Object { Write-CenterLog ([string]$_) }
            $code=$LASTEXITCODE
        }
        $ErrorActionPreference='Stop'
        Write-CenterLog ('İşlem sonlandı; çıkış kodu: '+$code+'. 15 saniye sonra yeniden denenecek.')
    } catch { Write-CenterLog ('Çalıştırma hatası: '+$_.Exception.GetType().Name+'. 15 saniye sonra yeniden denenecek.') }
    Start-Sleep -Seconds 15
}
