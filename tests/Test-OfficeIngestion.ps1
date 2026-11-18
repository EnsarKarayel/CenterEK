$ErrorActionPreference='Stop'
$path=Join-Path (Split-Path -Parent $PSScriptRoot) 'Repair-OfficeIngestion.ps1'
$tokens=$null;$errors=$null
$ast=[Management.Automation.Language.Parser]::ParseFile($path,[ref]$tokens,[ref]$errors)
if($errors){throw 'Office ingestion repair parse failure'}
$definition=$ast.Find({param($node) $node -is [Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq 'Add-OfficeIngestionRule'},$true)
. ([ScriptBlock]::Create($definition.Extent.Text))
# Mock firewall calls. Never alter the host firewall in this test.
function Get-NetFirewallRule {param($Name,$ErrorAction) if($script:exists){[pscustomobject]@{Name=$Name}}}
function New-NetFirewallRule {param($Name,$DisplayName,$Description,$Direction,$Action,$Protocol,$LocalAddress,$LocalPort,$RemoteAddress,$Profile,$EdgeTraversalPolicy) $script:called=$true;$script:actual=@{name=$Name;direction=$Direction;action=$Action;protocol=$Protocol;address=$LocalAddress;port=$LocalPort;remote=$RemoteAddress;profiles=$Profile;edge=$EdgeTraversalPolicy}}
foreach($category in @('Private','DomainAuthenticated','Public','Unknown')){
    $script:exists=$false;$script:called=$false;$failed=$false
    try{Add-OfficeIngestionRule $category|Out-Null}catch{$failed=$true}
    if($category -in @('Public','Unknown')){if(-not $failed -or $called){throw 'Unsafe profile accepted'}}
    else{
        if($failed -or -not $called){throw 'Valid office profile refused'}
        if($actual.address -ne '192.168.1.15' -or $actual.port -ne 8765 -or $actual.protocol -ne 'TCP' -or $actual.action -ne 'Allow' -or $actual.direction -ne 'Inbound' -or $actual.edge -ne 'Block'){throw 'Receiver rule widened'}
        if(($actual.remote -join ',') -ne '192.168.1.0/24,192.168.2.0/24' -or ($actual.profiles -join ',') -ne 'Domain,Private'){throw 'Office network/profile scope widened'}
    }
}
$script:exists=$true;$script:called=$false;$failed=$false
try{Add-OfficeIngestionRule 'Private'|Out-Null}catch{$failed=$true}
if(-not $failed -or $called){throw 'Existing rule was overwritten'}
$script:exists=$false;$script:called=$false
Add-OfficeIngestionRule 'Public' -AllowScopedPublic|Out-Null
if(-not $called -or ($actual.profiles -join ',') -ne 'Public' -or ($actual.remote -join ',') -ne '192.168.1.0/24,192.168.2.0/24' -or $actual.address -ne '192.168.1.15' -or $actual.port -ne 8765 -or $actual.edge -ne 'Block'){throw 'Explicit public rule exceeded its office scope'}
$script:called=$false;$failed=$false
try{Add-OfficeIngestionRule 'Unknown' -AllowScopedPublic|Out-Null}catch{$failed=$true}
if(-not $failed -or $called){throw 'Unknown profile accepted through explicit option'}
'Office ingestion rule scope and existing-rule preservation passed'
