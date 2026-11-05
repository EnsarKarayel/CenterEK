param([Parameter(Mandatory=$true)][string]$EnrollmentFile,
      [string]$OutputFile="$PSScriptRoot\agent.local.json")
$ErrorActionPreference='Stop'
$enrollment=Get-Content -LiteralPath $EnrollmentFile -Raw | ConvertFrom-Json
$uri=[Uri]$enrollment.url
if ($uri.Scheme -ne 'https' -or $uri.UserInfo -or $uri.AbsolutePath -ne '/' -or $uri.Query -or $uri.Fragment) { throw 'Geçersiz HTTPS adresi' }
if ($enrollment.computer.Split('.')[0] -ine $env:COMPUTERNAME) { throw 'Kayıt dosyası bu bilgisayara ait değil' }
if ($enrollment.kind -notin @('endpoint','directory')) { throw 'Geçersiz ajan türü' }
if (Test-Path -LiteralPath $OutputFile) { throw 'Mevcut ajan ayarı var; üzerine yazılmadı' }
$secret=ConvertTo-SecureString $enrollment.token -AsPlainText -Force
$settings=[ordered]@{id=$enrollment.id;computer=$enrollment.computer;kind=$enrollment.kind;
    url=$enrollment.url;token_encrypted=($secret | ConvertFrom-SecureString)}
$settings | ConvertTo-Json | Set-Content -LiteralPath $OutputFile -Encoding UTF8
$identity=[Security.Principal.WindowsIdentity]::GetCurrent().Name
& icacls.exe $OutputFile /inheritance:r /grant:r "${identity}:(F)" '*S-1-5-18:(F)' '*S-1-5-32-544:(F)' | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Dosya izinleri uygulanamadı; kurulumu kontrol edin' }
Write-Host "Ajan anahtarı bu Windows kullanıcısına bağlı DPAPI ile korundu: $OutputFile"
Write-Host 'Düz anahtarlı kayıt dosyasını güvenli aktarım yerinden ve hedef bilgisayardan kaldırın.'
