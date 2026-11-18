param([ValidateSet('Collector','Directory','Endpoint')][string]$Role='Collector')
# Read-only: do not restart tasks, edit firewall, read credentials or change files.
$ErrorActionPreference='Stop'
$identity=[Security.Principal.WindowsIdentity]::GetCurrent()
if(-not (New-Object Security.Principal.WindowsPrincipal($identity)).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){
    throw 'Administrator PowerShell/CMD required; no changes were made'
}
$report=[ordered]@{schema=1;read_only=$true;computer=$env:COMPUTERNAME;role=$Role;utc=(Get-Date).ToUniversalTime().ToString('o');tasks=@();roots=@();listeners=@();logs=@();firewall=@()}
$roots=if($Role -eq 'Collector'){@('C:\CenterEK','C:\CenterEK-Relay')}elseif($Role -eq 'Directory'){@('C:\CenterEK-AD')}else{@((Join-Path $env:ProgramData 'CenterEK-Agent'))}
$names=if($Role -eq 'Collector'){@('CenterEK-Server-System','CenterEK-OfficeRelay-System')}elseif($Role -eq 'Directory'){@('CenterEK-Directory-System')}else{@('CenterEK-Endpoint-System')}
foreach($name in $names){
    $task=Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
    if(-not $task){$report.tasks+=@{name=$name;present=$false};continue}
    $info=Get-ScheduledTaskInfo -TaskName $name
    $report.tasks+=@{name=$name;present=$true;state=[string]$task.State;last_run=$info.LastRunTime.ToUniversalTime().ToString('o');last_result=$info.LastTaskResult;limit=$task.Settings.ExecutionTimeLimit;multiple_instances=[string]$task.Settings.MultipleInstances;principal=$task.Principal.UserId}
}
foreach($root in $roots){
    $entry=[ordered]@{root=$root;exists=(Test-Path -LiteralPath $root);endpoint_files=0;newest_endpoint_utc=$null;directory_file_utc=$null}
    if($entry.exists){
        $files=@(Get-ChildItem -LiteralPath (Join-Path $root 'data\endpoint-sessions') -Filter '*.json' -File -ErrorAction SilentlyContinue)
        $entry.endpoint_files=$files.Count
        if($files.Count){$entry.newest_endpoint_utc=($files|Sort-Object LastWriteTimeUtc -Descending|Select-Object -First 1).LastWriteTimeUtc.ToString('o')}
        foreach($relative in @('data\directory-inventory.json','data\directory-inventory.local.json')){
            $path=Join-Path $root $relative
            if(Test-Path -LiteralPath $path){$entry.directory_file_utc=(Get-Item -LiteralPath $path).LastWriteTimeUtc.ToString('o')}
        }
        foreach($kind in @('server','endpoint','directory','office-relay')){
            $path=Join-Path $root ('data\logs\'+$kind+'.log')
            if(-not(Test-Path -LiteralPath $path)){continue}
            $file=Get-Item -LiteralPath $path
            $markers=@(foreach($line in @(Get-Content -LiteralPath $path -Tail 50)){
                $code=$null
                foreach($pattern in @('OFFICE_RELAY_ACCEPTED','OFFICE_RELAY_HTTP_\d+','database is locked','actively refused','gönderilemedi','Rapor HTTPS ile alındı','çıkış kodu:\s*\d+','Başlatılıyor','ConnectionError','TimeoutError','SSLError','Traceback')){
                    if($line -match $pattern){$code=$Matches[0];break}
                }
                if($code){@{marker=$code;timestamp=if($line -match '^\s*([0-9T:.+Z-]{15,40})'){$Matches[1]}else{$null}}}
            })
            $report.logs+=@{root=$root;kind=$kind;modified_utc=$file.LastWriteTimeUtc.ToString('o');markers=$markers}
        }
    }
    $report.roots+=$entry
}
foreach($connection in @(Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue)){
    $process=Get-CimInstance Win32_Process -Filter ('ProcessId='+$connection.OwningProcess)
    $report.listeners+=@{address=$connection.LocalAddress;port=$connection.LocalPort;pid=$connection.OwningProcess;process=$process.Name;known_root=@($roots|Where-Object {$process.CommandLine -match [Regex]::Escape($_)}).Count -gt 0}
}
if($Role -eq 'Collector'){
    try{
        foreach($filter in @(Get-NetFirewallPortFilter|Where-Object {$_.LocalPort -eq '8765'})){
            foreach($rule in @(Get-NetFirewallRule -AssociatedNetFirewallPortFilter $filter)){
                $addresses=@(Get-NetFirewallAddressFilter -AssociatedNetFirewallRule $rule|Select-Object -ExpandProperty RemoteAddress)
                $report.firewall+=@{name=$rule.Name;enabled=[string]$rule.Enabled;direction=[string]$rule.Direction;action=[string]$rule.Action;profile=[string]$rule.Profile;remote=$addresses}
            }
        }
    }catch{$report.firewall_error=$_.Exception.GetType().Name}
}
if($Role -ne 'Collector'){
    $client=New-Object Net.Sockets.TcpClient
    try{
        $pending=$client.BeginConnect('192.168.1.15',8765,$null,$null)
        if(-not $pending.AsyncWaitHandle.WaitOne(3000)){throw 'Receiver connection timed out'}
        $client.EndConnect($pending);$report.office_receiver_tcp=$true
    }catch{$report.office_receiver_tcp=$false;$report.receiver_error=$_.Exception.GetType().Name}
    finally{$client.Close()}
}
$report|ConvertTo-Json -Depth 8
