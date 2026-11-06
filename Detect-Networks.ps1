param([Parameter(Mandatory=$true)][string]$OutputFile)
$ErrorActionPreference='Stop'
$rows=@()
foreach($nic in [Net.NetworkInformation.NetworkInterface]::GetAllNetworkInterfaces()){
    if($nic.OperationalStatus -ne 'Up' -or $nic.NetworkInterfaceType -notin @('Ethernet','Wireless80211')){continue}
    $properties=$nic.GetIPProperties()
    $gateway=@($properties.GatewayAddresses|Where-Object{$_.Address.AddressFamily -eq 'InterNetwork' -and $_.Address.ToString() -ne '0.0.0.0'})
    foreach($address in $properties.UnicastAddresses){
        if($address.Address.AddressFamily -ne 'InterNetwork'){continue}
        $rows += [ordered]@{name=$nic.Name;description=$nic.Description;type=$nic.NetworkInterfaceType.ToString();ip=$address.Address.IPAddressToString;mask=$address.IPv4Mask.IPAddressToString;gateway=if($gateway.Count){$gateway[0].Address.IPAddressToString}else{$null}}
    }
}
$temporary=$OutputFile+'.tmp'
ConvertTo-Json -InputObject @($rows) -Depth 4|Set-Content -LiteralPath $temporary -Encoding UTF8
Move-Item -LiteralPath $temporary -Destination $OutputFile -Force
