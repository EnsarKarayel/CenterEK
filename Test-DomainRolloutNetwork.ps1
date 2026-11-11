param(
    [Parameter(Mandatory=$true)][string]$RetryReport,
    [ValidateRange(1,8)][int]$Throttle=4,
    [string]$DnsServer='192.168.1.10'
)
# Read-only endpoint diagnostics. No authentication by IP, installation, port
# opening, restart or AD/DNS record modification. Probe only office /22 IPs.
$ErrorActionPreference='Stop'
Import-Module ActiveDirectory
$file=Get-Item -LiteralPath $RetryReport
if($file.Length -gt 10MB -or ($file.Attributes -band [IO.FileAttributes]::ReparsePoint)){throw 'Unsafe input report'}
$rows=@(Import-Csv -LiteralPath $RetryReport)
if(-not $rows.Count -or $rows.Count -gt 20000 -or 'Computer' -notin $rows[0].PSObject.Properties.Name -or 'Status' -notin $rows[0].PSObject.Properties.Name){throw 'Invalid rollout report'}
$names=@($rows|Where-Object {$_.Status -in @('REMOTE_ACCESS_FAILED','REMOTE_ACCESS_TIMEOUT_OR_JOB_FAILED')}|ForEach-Object {
    if($_.Computer -cnotmatch '^[A-Za-z0-9][A-Za-z0-9-]{0,14}$'){throw 'Invalid computer name'}
    $_.Computer.ToUpperInvariant()
}|Sort-Object -Unique)
$domain=Get-ADDomain
$targets=@(Get-ADComputer -Filter * -Properties Enabled,OperatingSystem,DNSHostName,LastLogonDate|Where-Object {
    $names -icontains $_.Name -and $_.Enabled -and $_.OperatingSystem -cmatch '^Windows (8|10|11)(\b|\.)' -and $_.DNSHostName -ieq ($_.Name+'.'+$domain.DNSRoot)
}|Sort-Object Name)
$output=Join-Path $PSScriptRoot ('network-audit-'+[Guid]::NewGuid().ToString('N')+'.csv')
$worker={
    param($Computer,$Fqdn,$LastLogon,$DnsServer)
    $ErrorActionPreference='Stop'
    $result=[ordered]@{Computer=$Computer;Fqdn=$Fqdn;DnsServer=$DnsServer;Addresses='';ProbedAddresses='';OutsideScopeAddresses='';PingResponded=$false;Tcp445=$false;Tcp135=$false;Status='DNS_LOOKUP_FAILED';LastLogonApproxDays='';ErrorType=''}
    if($LastLogon){$result.LastLogonApproxDays=[Math]::Floor(([DateTime]::UtcNow-([DateTime]$LastLogon).ToUniversalTime()).TotalDays)}
    function Office-Address([string]$Text){
        $ip=$null
        if(-not [Net.IPAddress]::TryParse($Text,[ref]$ip) -or $ip.AddressFamily -ne [Net.Sockets.AddressFamily]::InterNetwork){return $false}
        $b=$ip.GetAddressBytes()
        return $b[0] -eq 192 -and $b[1] -eq 168 -and $b[2] -le 3 -and -not ($b[2] -eq 0 -and $b[3] -eq 0) -and -not ($b[2] -eq 3 -and $b[3] -eq 255)
    }
    function Probe-Port([string]$Address,[int]$Port){
        $client=[Net.Sockets.TcpClient]::new()
        $wait=$null
        try{
            $async=$client.BeginConnect($Address,$Port,$null,$null)
            $wait=$async.AsyncWaitHandle
            if(-not $wait.WaitOne(1200)){return $false}
            $client.EndConnect($async)
            return $client.Connected
        }catch{return $false}
        finally{$client.Close();if($wait){$wait.Close()}}
    }
    function Probe-Ping([string]$Address){
        $ping=[Net.NetworkInformation.Ping]::new()
        try{return $ping.Send($Address,1000).Status -eq [Net.NetworkInformation.IPStatus]::Success}
        catch{return $false}finally{$ping.Dispose()}
    }
    try{
        $records=@(Resolve-DnsName -Name $Fqdn -Type A -DnsOnly -Server $DnsServer -QuickTimeout)
        $addresses=@($records|Where-Object IPAddress|ForEach-Object IPAddress|Sort-Object -Unique)
        if(-not $addresses.Count){$result.Status='DNS_NO_A_RECORD';return [pscustomobject]$result}
        $result.Addresses=$addresses -join ','
        $allowed=@($addresses|Where-Object {Office-Address $_})
        $result.OutsideScopeAddresses=@($addresses|Where-Object {-not(Office-Address $_)}) -join ','
        if(-not $allowed.Count){$result.Status='DNS_IP_OUTSIDE_OFFICE_SCOPE';return [pscustomobject]$result}
        # Bound even unexpectedly multi-homed/stale DNS answers.
        $probe=@($allowed|Select-Object -First 4)
        $result.ProbedAddresses=$probe -join ','
        foreach($address in $probe){
            if(Probe-Ping $address){$result.PingResponded=$true}
            if(Probe-Port $address 445){$result.Tcp445=$true}
            if(Probe-Port $address 135){$result.Tcp135=$true}
        }
        if($result.Tcp445 -or $result.Tcp135){$result.Status='MANAGEMENT_PORT_RESPONSE'}
        elseif($result.PingResponded){$result.Status='PING_ONLY_PORTS_CLOSED_OR_FILTERED'}
        else{$result.Status='NO_PROBE_RESPONSE'}
    }catch{$result.ErrorType=$_.Exception.GetType().FullName}
    [pscustomobject]$result
}
Write-Output ('NETWORK_AUDIT_TARGETS='+$targets.Count)
for($index=0;$index -lt $targets.Count;$index+=$Throttle){
    $jobs=@()
    foreach($computer in @($targets|Select-Object -Skip $index -First $Throttle)){
        $jobs+=@{Computer=$computer.Name;Job=(Start-Job -ScriptBlock $worker -ArgumentList $computer.Name,$computer.DNSHostName,$computer.LastLogonDate,$DnsServer)}
    }
    $deadline=[DateTime]::UtcNow.AddSeconds(45)
    foreach($entry in $jobs){
        $done=Wait-Job -Job $entry.Job -Timeout ([Math]::Max(1,[int]($deadline-[DateTime]::UtcNow).TotalSeconds))
        $received=if($done){@(Receive-Job -Job $entry.Job -ErrorAction SilentlyContinue)}else{@()}
        if(-not $received.Count){
            Stop-Job -Job $entry.Job
            $received=@([pscustomobject]@{Computer=$entry.Computer;Fqdn='';DnsServer=$DnsServer;Addresses='';ProbedAddresses='';OutsideScopeAddresses='';PingResponded=$false;Tcp445=$false;Tcp135=$false;Status='AUDIT_TIMEOUT_OR_JOB_FAILED';LastLogonApproxDays='';ErrorType=''})
        }
        foreach($row in $received){
            $row|Select-Object Computer,Fqdn,DnsServer,Addresses,ProbedAddresses,OutsideScopeAddresses,PingResponded,Tcp445,Tcp135,Status,LastLogonApproxDays,ErrorType|Export-Csv -LiteralPath $output -NoTypeInformation -Append -Encoding UTF8
            Write-Output ($row.Computer+' '+$row.Status+' IP='+$row.Addresses+' ping='+$row.PingResponded+' tcp445='+$row.Tcp445+' tcp135='+$row.Tcp135)
        }
        Remove-Job -Job $entry.Job
    }
}
if(Test-Path -LiteralPath $output){Import-Csv -LiteralPath $output|Group-Object Status|Select-Object Name,Count|Format-Table -AutoSize}
Write-Output ('REPORT='+$output)
Write-Output 'No response does not prove offline. DNS may be stale; open ports do not establish endpoint identity or deployment permission. LastLogonApproxDays is replicated AD metadata, not current user presence.'
