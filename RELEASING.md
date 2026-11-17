# Windows ürün sürümü hazırlama

Müşteri dosyası: `CenterEK-Setup-<sürüm>-win-x64.exe`. Python veya elle dosya kopyalama gerekmez. İlk yönetici parolası müşterinin bilgisayarında belirlenir; şirket ağına ait ayarlar, Azure anahtarları ve mevcut kullanıcı veritabanı paketlenmez.

1. Özellik dalında değişikliği ve `installer_core.VERSION` sürümünü hazırlayın, PR açın.
2. GitHub Actions CI, Python 3.11/3.12 testlerini ve Azure şablon doğrulamasını çalıştırır; başarılıysa Windows kurulumunu derler. Paket içindeki HTTPS/kimlik doğrulama smoke testlerini ve arşiv içerik kontrolünü tamamlar.
3. İlgili CI çalışmasının `centerek-windows-<commit>` artifact dosyasından EXE, SHA256, manifest ve test raporlarını alın. Manifestteki commit ile incelediğiniz commit aynı olmalıdır. CI artifact saklama süresi 14 gündür; müşteri dağıtımı için GitHub Release gerekir.
4. Python kurulu olmayan temiz Windows 11 ve Server 2019+ makinelerinde INSTALLATION.md ve MAINTENANCE.md kabul listelerini tamamlayın. Mevcut paket kurulumlarında yedekli yükseltme, geri alma, yarım kalan bakımın kurtarılması ve veri saklayan kaldırma ayrı ayrı doğrulanmalıdır. Kaynak kod kurulumunu otomatik yükseltmeyin.
5. PR onayları ve gerekli kontroller tamamlanınca birleştirin. Main commit için üretilen paketi ayrıca doğrulayın; PR artifact dosyasıyla main paketini karıştırmayın.
6. GitHub Releases ekranında main commit üzerinde `v<sürüm>` etiketiyle taslak ön sürüm hazırlayın. EXE, EXE SHA256, release-manifest.json ve kabul raporlarını ekleyin. Ticari yayın öncesinde kod imzası, üçüncü taraf lisans incelemesi, gerçek makinelerde bakım kabulü, ürün lisansı ve destek koşulları tamamlanmalıdır.

Tek dosya setup yalnızca dağıtım katmanıdır; mevcut kurulum sihirbazını açar ve sihirbaz kapatılıncaya kadar geçici çalışma zamanını korur. UAC izni iptal edilirse kurulum başlamaz. Setup açılışının, kurulumun tamamlandığı anlamına gelmediğini kabul testinde kontrol edin.
