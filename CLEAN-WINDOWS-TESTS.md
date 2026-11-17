# Temiz Windows kabulü

0.9.2 paketi Python bulunmayan gerçek Windows 11 Enterprise Sandbox'ta temiz kurulum, HTTPS giriş, SYSTEM görevleri, uç ajan alımı, Windows kaydı, veri saklayan kaldırma ve aynı hesapla geri kurma testlerini geçti. Yerel rapor `data/clean-windows/0.9.2-20261117/reports/clean-windows-report.json` içindedir. Bu sonuç dış setup/UAC, kalıcı yeniden başlatma, Server veya imzalı ticari kabulü tamamlanmış saymaz. Mevcut Azure CenterEK sunucusu silinmez veya yeniden imajlanmaz.

## Hazırlanan Sandbox testi

```powershell
powershell.exe -NoProfile -File scripts\qa\New-SandboxTest.ps1 -ReleaseFolder data\releases\RELEASE -OutputFolder data\clean-windows\NEW-TEST
```

Üretilen WSB, yalnızca paket klasörünü salt okunur ve ayrı rapor klasörünü yazılabilir eşler. Ağ, pano ve vGPU kapalıdır. Host üzerinde kurulum yapılmaz. Sandbox içinde Windows yönetici onayı gerekir. `Test-CleanWindows.ps1`, sanal makine/boş kurulum/Python bulunmaması kontrollerini geçmeden çalışmaz. Rastgele yönetici parolası yalnızca misafirde oluşturulur; rapora yazılmaz ve geçici seçenek dosyası sonunda silinir.

Test gerçek SYSTEM sunucu/uç ajan görevlerini, HTTPS girişini, yerel ajan alımını, Windows uygulama kaydını, veri saklayan kaldırmayı ve aynı hesapla geri kurmayı kontrol eder. Ticari pakette rapor klasörüne açık kurulum kimliği isteği yazılır; yayıncı misafire özel anahtar taşımadan QA lisansı üretip `qa-license.json` olarak rapor klasörüne bırakır.

Ön sürümler arasında gerçek yükseltme/geri alma regresyonu için üreticiye `-PreviousReleaseFolder` eklenebilir. Önceki gerçek paket ayrı salt okunur dizine açılır; misafir önce eski paketi kurar, yenisine yükseltir ve eskiye döner. Her aşamada aynı hesap ve kurulum kimliği doğrulanır. Bu mod `isolated-windows-preview-lifecycle` türünde rapor üretir ve ticari kabul yerine kullanılamaz.

0.9.1 → 0.9.2 → 0.9.1 akışı Windows 11 Sandbox'ta başarıyla gözlendi; ardından veri saklayan kaldırma ve aynı hesapla geri kurma da geçti. Sonuçlar `docs/acceptance/0.9.2-preview/windows11-upgrade-rollback.json` içindedir.

Bu otomasyon iç paketle kurulum yapar. Dış setup çift tıklama/UAC etkileşimi ve yeniden başlatma testi raporda otomatik başarılı yapılmaz. Sandbox kapanınca silindiği için kalıcı Windows yeniden başlatma kabulü için ayrı temiz VM gerekir. Windows 11 ve desteklenen Server sürümlerinde ayrı kabul tutulmalıdır.

## Satışa hazır kontrolü

`scripts/release/check_commercial.py` gerçek imzaları yeniden doğrular; ticari politika, nihai EULA özeti/satıcı onayı, aynı ikiliye ait temiz Windows raporu, gerçek UAC/setup ve reboot kabulü eksikse hata döndürür. Ön sürüme `sale_ready:true` yazmak için test sonuçları veya onay dosyaları uydurulmaz.

```powershell
python scripts/release/check_commercial.py data/releases/RELEASE --acceptance C:/Acceptance/clean-windows-report.json --legal-approval C:/ReleaseApproval/approval.json
```

Onay JSON'u satıcının `approved:true`, `seller`, `country`, `support_email`, `publisher_thumbprint`, `approved_eula_sha256`, `third_party_review_sha256` kararını kaydeder. Son alan gözden geçirilen üçüncü taraf bileşen envanterini bağlar. Kabul raporundaki `reboot_test`, `uac_interaction`, `outer_setup_ui` alanları yalnızca gerçekten doğrulanınca `passed` olmalıdır. Otomatik rapor `pending` üretir.
