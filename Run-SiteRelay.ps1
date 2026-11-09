param([string]$SourceRoot='C:\CenterEK',[string]$PythonPath='C:\Program Files\Python311\python.exe')
$ErrorActionPreference='Stop'
$root=Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $root
$folder=Join-Path $root 'data\logs'
New-Item -ItemType Directory -Path $folder -Force|Out-Null
$log=Join-Path $folder 'office-relay.log'
while($true){
    if((Test-Path -LiteralPath $log) -and (Get-Item -LiteralPath $log).Length -gt 2MB){Move-Item -LiteralPath $log -Destination ($log+'.1') -Force}
    try{
        # A fresh process per report bounds memory and lets the log rotate.
        & $PythonPath (Join-Path $root 'site_push.py') --source-root $SourceRoot --agent-config (Join-Path $root 'site-agent.local.json') 2>&1|Out-File -LiteralPath $log -Append -Encoding utf8
    }catch{('OFFICE_RELAY_PROCESS_FAILED '+[DateTime]::UtcNow.ToString('o'))|Out-File -LiteralPath $log -Append -Encoding utf8}
    Start-Sleep -Seconds 30
}
