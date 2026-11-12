$ErrorActionPreference='Stop'
$path=Join-Path (Split-Path -Parent $PSScriptRoot) 'Repair-OfficeDnsClient.ps1'
$tokens=$null;$errors=$null
$ast=[Management.Automation.Language.Parser]::ParseFile($path,[ref]$tokens,[ref]$errors)
if($errors){throw 'DNS repair parse error'}
$function=$ast.Find({param($node) $node -is [Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq 'Invoke-DnsClientTransaction'},$true)
. ([scriptblock]::Create($function.Extent.Text))
# Never use real networking commands or alter a DNS client in this test.
function Set-DnsClientServerAddress {param($InputObject,[string[]]$ServerAddresses,[switch]$ResetServerAddresses) $script:changes+=@{Servers=$ServerAddresses;Reset=[bool]$ResetServerAddresses};if($script:scenario -eq 'rollbackfails' -and $script:changes.Count -eq 2){throw 'Simulated rollback failure'}}
function Clear-DnsClientCache {}
function Get-DnsClientServerAddress {param($InterfaceIndex,$AddressFamily) return [pscustomobject]@{InterfaceAlias='Test NIC';ServerAddresses=@('192.168.1.10')}}
function Resolve-DnsName {param($Name,$Type,[switch]$DnsOnly) if($Name -eq 'github.com' -and $script:scenario -ne 'success'){throw 'Simulated public lookup failure'}; if($Type -eq 'SRV'){return [pscustomobject]@{NameTarget='volo.volonet.local'}};return [pscustomobject]@{Name=$Name;IPAddress='192.168.1.41'}}
foreach($case in @('success','staticrollback','automaticrollback','rollbackfails')){
    $script:scenario=$case;$script:changes=@();$failed=$false;$message=''
    try{$output=@(Invoke-DnsClientTransaction ([pscustomobject]@{InterfaceIndex=9}) @('195.175.39.50','195.175.39.49') ($case -eq 'automaticrollback') '192.168.1.10' 'volonet.local' 'PC-08.volonet.local')}
    catch{$failed=$true;$message=$_.Exception.Message}
    if($case -eq 'success'){
        if($failed -or $script:changes.Count -ne 1 -or 'DNS_CLIENT_FIXED' -notin $output){throw 'Success transaction failed'}
    }else{
        if(-not $failed -or $script:changes.Count -ne 2){throw 'Failed validation did not attempt rollback'}
        if($case -eq 'automaticrollback' -and -not $script:changes[1].Reset){throw 'Automatic DNS configuration was not restored'}
        if($case -eq 'staticrollback' -and (($script:changes[1].Servers -join ',') -ne '195.175.39.50,195.175.39.49' -or $script:changes[1].Reset)){throw 'Original static server list was not restored'}
        if($case -eq 'rollbackfails' -and $message -notmatch 'DNS_ROLLBACK_FAILED'){throw 'Failed rollback was falsely reported as restored'}
    }
    Write-Output ('PASS '+$case)
}
