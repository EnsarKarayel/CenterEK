param([Parameter(Mandatory=$true)][string]$AgentConfig,
      [string]$OutputFile="$PSScriptRoot\directory-inventory.local.json",[switch]$Watch)
$ErrorActionPreference='Stop'
. "$PSScriptRoot\Send-Report.ps1"
do {
    try {
        & "$PSScriptRoot\Export-DirectoryInventory.ps1" -OutputFile $OutputFile
        Send-CenterEKReport -AgentConfig $AgentConfig -ReportFile $OutputFile
    } catch { Write-Warning 'Dizin raporu gönderilemedi. Modül/yetki, HTTPS sertifikası ve ajan anahtarını kontrol edin.' }
    if ($Watch) { Start-Sleep -Seconds 300 }
} while ($Watch)
