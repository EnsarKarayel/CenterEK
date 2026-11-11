$ErrorActionPreference='Stop'
$tokens=$null;$errors=$null
$ast=[Management.Automation.Language.Parser]::ParseFile((Join-Path (Split-Path -Parent $PSScriptRoot) 'Test-DomainRolloutNetwork.ps1'),[ref]$tokens,[ref]$errors)
if($errors){throw 'Audit parse failure'}
$assignment=$ast.Find({param($node) $node -is [Management.Automation.Language.AssignmentStatementAst] -and $node.Left.Extent.Text -eq '$worker'},$true)
$text=$assignment.Right.Extent.Text.Trim()
$port=$assignment.Find({param($node) $node -is [Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq 'Probe-Port'},$true)
$ping=$assignment.Find({param($node) $node -is [Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq 'Probe-Ping'},$true)
$text=$text.Replace($port.Extent.Text,'function Probe-Port([string]$Address,[int]$Port){$script:probed+=$Address;return ($script:scenario -eq ''smb'' -and $Port -eq 445) -or ($script:scenario -eq ''rpc'' -and $Port -eq 135)}')
$text=$text.Replace($ping.Extent.Text,'function Probe-Ping([string]$Address){return $script:scenario -eq ''ping''}')
$worker=[scriptblock]::Create($text.Substring(1,$text.Length-2))
function Resolve-DnsName {
    param($Name,$Type,[switch]$DnsOnly,$Server,[switch]$QuickTimeout)
    if($Name -ne 'pc-08.volonet.local' -or $Server -ne '192.168.1.10' -or $Type -ne 'A'){throw 'Unexpected DNS target'}
    if($script:scenario -eq 'dnsfail'){throw 'Simulated DNS failure'}
    if($script:scenario -eq 'noa'){return @()}
    if($script:scenario -eq 'outside'){return @('203.0.113.1','192.168.4.1','192.168.0.0','192.168.3.255','::1')|ForEach-Object {[pscustomobject]@{IPAddress=$_}}}
    if($script:scenario -eq 'multi'){return @(10..15|ForEach-Object {[pscustomobject]@{IPAddress=('192.168.1.'+$_)}})}
    return @('192.168.1.41','203.0.113.1')|ForEach-Object {[pscustomobject]@{IPAddress=$_}}
}
foreach($case in @('dnsfail','noa','outside','none','ping','smb','rpc','multi')){
    $script:scenario=$case;$script:probed=@()
    $r=& $worker 'PC-08' 'pc-08.volonet.local' $null '192.168.1.10'
    $expected=@{dnsfail='DNS_LOOKUP_FAILED';noa='DNS_NO_A_RECORD';outside='DNS_IP_OUTSIDE_OFFICE_SCOPE';none='NO_PROBE_RESPONSE';ping='PING_ONLY_PORTS_CLOSED_OR_FILTERED';smb='MANAGEMENT_PORT_RESPONSE';rpc='MANAGEMENT_PORT_RESPONSE';multi='NO_PROBE_RESPONSE'}[$case]
    if($r.Status -ne $expected){throw ('Incorrect audit status '+$case+': '+$r.Status)}
    if(@($script:probed|Where-Object {-not $_.StartsWith('192.168.1.')} ).Count){throw 'Audit probed outside office scope'}
    if($case -in @('dnsfail','noa','outside') -and $script:probed.Count){throw 'Invalid/no DNS answers triggered a transport probe'}
    if($case -eq 'multi' -and $script:probed.Count -ne 8){throw 'Multiple DNS answers were not capped at four addresses'}
    if($case -eq 'smb' -and (-not $r.Tcp445 -or $r.Tcp135)){throw 'SMB and RPC results conflated'}
    Write-Output ('PASS '+$case)
}
# Real socket probe only against a locally owned ephemeral loopback listener.
. ([scriptblock]::Create($port.Extent.Text))
$listener=[Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback,0)
try{
    $listener.Start();$portNumber=$listener.LocalEndpoint.Port
    if(-not(Probe-Port '127.0.0.1' $portNumber)){throw 'Local open socket probe failed'}
}finally{$listener.Stop()}
if(Probe-Port '127.0.0.1' $portNumber){throw 'Closed socket was reported open'}
Write-Output 'PASS real loopback open/closed socket probe'
