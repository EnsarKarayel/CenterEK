function Send-CenterEKReport {
    param([string]$AgentConfig, [string]$ReportFile)
    $settings = Get-Content -LiteralPath $AgentConfig -Raw | ConvertFrom-Json
    $uri = [Uri]$settings.url
    if ($uri.Scheme -ne 'https' -or $uri.UserInfo -or $uri.AbsolutePath -ne '/') { throw 'HTTPS sunucu kökü gerekli' }
    if ($settings.token_machine) {
        Add-Type -AssemblyName System.Security
        $bytes=[Convert]::FromBase64String($settings.token_machine)
        $clear=[Security.Cryptography.ProtectedData]::Unprotect($bytes,$null,[Security.Cryptography.DataProtectionScope]::LocalMachine)
        try { $secure=ConvertTo-SecureString ([Text.Encoding]::UTF8.GetString($clear)) -AsPlainText -Force }
        finally { [Array]::Clear($clear,0,$clear.Length) }
    } else { $secure = ConvertTo-SecureString $settings.token_encrypted }
    $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try {
        $token = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        $body = [IO.File]::ReadAllBytes((Resolve-Path -LiteralPath $ReportFile).Path)
        $headers = @{Authorization=('Bearer '+$token)}
        $endpoint = $settings.url.TrimEnd('/')+'/api/agent/'+$settings.kind
        # No certificate bypass or redirect: never forward the bearer to another host.
        Invoke-RestMethod -Method Post -Uri $endpoint -Headers $headers -ContentType 'application/json; charset=utf-8' -Body $body -TimeoutSec 20 -MaximumRedirection 0 | Out-Null
        Write-Host 'Rapor HTTPS ile alındı.'
    } finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
        $token=$null
        $headers=$null
    }
}
