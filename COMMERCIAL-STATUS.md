# Ticari yayın durumu — 17 Kasım 2026

**Satışa hazır değil; 0.9.2-preview geliştirme/kabul sürümüdür.**

## Yeniden başlatma sonrası gerçek Windows kabulü

Windows Sandbox, ürün sahibi bilgisayarı yeniden başlattıktan sonra çalıştırıldı. Python kurulu olmayan Windows 11 Enterprise 26100 misafirde 0.9.2 paketinin temiz kurulumu, HTTPS giriş, SYSTEM sunucu/ajan görevleri, uç ajan alımı, Windows uygulama kaydı, veri saklayan kaldırma ve aynı hesapla geri kurma başarılı tamamlandı. Rapor: `data/clean-windows/0.9.2-20261117/reports/clean-windows-report.json` (`ok:true`). Dış setup/UAC etkileşimi ve kalıcı VM yeniden başlatma alanları hâlâ `pending` durumundadır; bu rapor imzalı ticari kabul değildir.

Ayrı temiz misafirde gerçek 0.9.1 → 0.9.2 yükseltme ve 0.9.2 → 0.9.1 geri alma, aynı hesap/kurulum kimliği korunarak geçti. Ardından kaldırma ve aynı hesapla geri kurma da geçti. Paylaşılabilir sonuçlar `docs/acceptance/0.9.2-preview/` altında kaydedildi; ham tanı günlükleri Git'e alınmadı.

İlk gerçek testlerde yakalanan iki hata düzeltildi: DNS adı ile Windows NetBIOS adının farklı olması nedeniyle yanlış ajan kimliği; Windows PowerShell 5.1'in JSON görev dizisini tek iç içe öğe olarak döndürmesi nedeniyle kaldırma/geri yükleme hatası. Bilgisayar eşleşme ve görev sahipliği korumaları gevşetilmedi. 132 Python testi ve Windows PowerShell boş/tek/çoklu görev JSON testleri geçti.

## Tamamlanan teknik hazırlık

- Ürün sahibi profili: Ensar Karayel, Türkiye, karayelensar@gmail.com. Tek kaynak `legal/publisher.json`; kimlik bilgisi ürün sahibi tarafından verilmiştir, sertifika otoritesi doğrulaması değildir.
- Kullanıcının ek bilgileri: Keçiören, Ankara; rolü kurucu. Bireysel/şirket statüsü ve tam tebligat adresi henüz kesinleşmedi. Destek taslağı müşteri tarafından kurulum, e-posta üzerinden kurulum/ekran sorularının değerlendirilmesi ve ileride açılırsa ticket kanalıdır; uzun vadeli yönetim veya SLA taahhüdü verilmedi. Bu bilgiler nihai sözleşme onayı değildir.
- Yıllık, kurulum kimliğine bağlı imzalı abonelik; süre sonunda ölçüm/keşif/ajan alımını durdurma; geçmiş/CSV erişimini koruma; panelden yenileme.
- Gerçek paketli uygulamada geçici QA anahtarıyla doğal süre bitişi, geçmişe erişim ve aynı süreçte yenileme doğrulandı. Bu test temiz Windows kabulü değildir; QA paketi satış kontrolünden geçemez.
- Nihai sözleşmeyi gösterme, açık kabul ve kabul edilen metnin SHA256/tarih kaydı; yeni metinli yükseltmede yeniden kabul.
- EXE ve PowerShell betiklerini sertifika sağlayıcısıyla imzalama/zaman damgası/doğrulama entegrasyonu. Gerçek üretim sertifikasıyla henüz çalıştırılmadı.
- Temiz Windows/Sandbox test üreticisi ve gerçek görev/ajan/kaldırma/geri kurma betiği. Otomatik rapor UAC/dış setup/reboot alanlarını kendiliğinden başarılı yapmaz.
- Ticari yayın kontrolü eksik şartlarda `sale_ready:false` üretir. CI'deki `--report-only` denetimi ön sürüm testlerinin geçmesine izin verir; yayın onayı değildir.
- Yayın denetimi artık dış setup ve ZIP özetlerini, açılmış paketin tüm dosyalarını, paket içindeki sözleşme/üçüncü taraf envanteri ve satıcı profilini de doğrular. Değişen dış setup eski kabul kaydıyla onaylanmaz. Bu denetim çalışması mevcut 0.9.2 ikilisini veya önceki kabul kanıtını değiştirmez.

## Bekleyen somut adımlar

### Microsoft Store ücretsiz imzalama incelemesi — 17 Kasım 2026

Ürün sahibi ayrı ücretsiz Store panel uygulaması geliştirilmesini, sunucu/ajanların mevcut setup'ta kalmasını seçti. İlk PWA kaynakları, sabit dosya sunumu, hassas veri önbelleklemeden offline ekranı ve web dağıtım çıktısı üreticisi hazırlandı. Detaylar `STORE-PANEL.md` içindedir. Bu durum Store'a gönderim, canlı Azure dağıtımı, MSIX üretimi veya Microsoft onayı değildir; tam sunucu ürününün satış engellerini kaldırmaz.

Sonuç: Mevcut CenterEK sunucu + ajan setup'ı için doğrudan ve onayı garantili bir ücretsiz Store/MSIX dönüşümü bulunmadı. Bu bir Microsoft ret kararı değil, mevcut kod ile yayımlanmış gereksinimlerin mühendislik karşılaştırmasıdır. Paket hazırlanıp Store'a gönderilmedi; hesap veya ücretli hizmet açılmadı.

| Mevcut uygulama davranışı | Kod kanıtı | Store/MSIX etkisi |
| --- | --- | --- |
| Dış setup yönetici izni ister | `build_windows.py`, `--uac-admin` | Standart kullanıcıyla çalışan Store istemcisinden farklı; yükseltme izni kısıtlı yetenek onayına bağlı olabilir. |
| Sunucu ve ajan SYSTEM olarak açılışta/oturum kapalıyken çalışır | `Install-SystemTask.ps1`, `New-ScheduledTaskPrincipal -UserId SYSTEM` | Mevcut zamanlanmış görevler MSIX servis bildirimi değildir. Windows servislerine dönüşüm yeni geliştirme gerektirir; paketli LocalSystem servisleri için iki kısıtlı yetenek gerekir. |
| Makine kök sertifika deposuna panel CA'sı eklenir; isteğe bağlı LAN firewall kuralı oluşturulur | `installer_core.py`, `certutil -addstore Root`, `Setup-Network.ps1` çağrısı | Sadece EXE'yi MSIX içine koymak bu yönetici işlemlerini Store'a uygun hale getirmez. |
| Program/veri kurulum kökünde tutulur; bakım eski program ve verileri geri koyar | `installer_core.py`, `maintenance.py` | MSIX'in paket dosyaları ve yaşam döngüsüne göre veri dizinleri ile güncelleme/geri alma yeniden tasarlanmalı. |
| AD ve diğer cihazlardan veri toplamak ayrı yetkili ajanlara bağlıdır | `Install-SystemTask.ps1`, `installer_core.py` | Store'daki panel istemcisinin imzası, harici sunucu/ajan EXE'lerini imzalamaz. |

[Microsoft imzalama rehberine](https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/code-signing-options) göre ücretsiz imzalama, sertifikasyondan geçen Store MSIX paketi içindir. Store'a mevcut MSI/EXE yükleyicisini sunmak sertifika ihtiyacını kaldırmaz. [Yetenek rehberi](https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/app-capability-declarations), `allowElevation` için sıkı onay ölçütleri belirtir; `packagedServices` ve `localSystemServices` için çoğu Store başvurusunun onaylanmadığını açıklar. MSIX servis desteği ile Store kabulü aynı şey değildir. Eski genel paketleme rehberindeki geniş yükseltme yasağı yerine bu daha ayrıntılı yetenek/onay ayrımı esas alınmıştır.

Uygulanabilir aday: Azure'daki veya müşterinin HTTPS paneline bağlanan ayrı bir **CenterEK panel istemcisi/PWA**. Bu istemci standart kullanıcıyla çalışır; yerel sunucu/ajan kurmaz ve yönetici işlemi yapmaz. [Microsoft'un PWA dağıtım yolu](https://learn.microsoft.com/en-us/microsoft-edge/progressive-web-apps/how-to/microsoft-store) buna yönelik paketleme akışını açıklar. Mevcut web arayüzünde web app manifesti, PWA simgeleri ve service worker bulunmadığından hazır Store paketi olduğu söylenemez. Oturum/kişisel veri yanıtları çevrimdışı önbelleğe alınmamalı; Azure Entra ve CenterEK girişleri ayrıca test edilmeli.

Bu adayın sonraki işleri: PWA manifest/simgeler ve uygun çevrimdışı hata ekranı, HTTPS erişimi ve oturum testleri, gizlilik ve destek sayfaları, Partner Center ürün kimliği, üretim verisi içermeyen inceleme ortamı/hesabı, Windows paketleme ve sertifikasyon. [Store politikaları](https://learn.microsoft.com/en-us/windows/apps/publish/store-policies) 10.2.4 bağımlılıkların açıklanmasını, 10.3 çalışan sunucu/demo erişimini ve 10.5 gizlilik koşullarını gerektirir. Yalnızca sahibinin hesabına açık mevcut staging, genel ürün incelemesi için hazırlanmış sayılmaz. Store istemcisi tek başına müşterinin bütün bilgisayarlarını izlemeye başlamaz; sunucu/ajanlar ayrıca kurulur. Tam yerel ürünü ücretsiz imzalanmış saymak veya mevcut satış denetimini bu gerekçeyle geçersiz kılmak doğru değildir.

Karar noktası: Müşterinin tüm sunucu/ajan altyapısını tek setup ile kurması hedefi korunuyorsa mevcut bağımsız yükleyici geliştirmesi sürer ve güvenilir imza konusu açık kalır. Ayrı Store panel istemcisi, ürün sahibinin bu kapsamı seçmesi durumunda bağımsız kanal olarak geliştirilebilir. Sertifika satın alma kararı bu değerlendirmeyle otomatik verilmedi.

1. **Manuel yeniden başlatma tamamlandı:** Ürün sahibi yeniden başlattığını bildirdi ve Sandbox çalıştırılarak doğrulandı. Agent otomatik yeniden başlatma yapmadı.
2. **Temiz Windows kabulünün kalan kapsamı:** Temel kurulum/kaldırma/geri kurma yukarıdaki raporla geçti. Kalıcı yeniden başlatma, dış setup/UAC, imzalı ticari paket ve Server kabulü ayrıca tamamlanmalıdır. Sandbox kapanınca silinir; Azure'daki mevcut sunucu test için silinmez.
3. **Güvenilir kod imzalama sertifikası:** Makinede henüz yok; satın alma veya kimlik doğrulaması yapılmadı. Türkiye için ticari CA yolu hazırlandı. Bireysel/şirket başvuru ve donanım/bulut anahtar seçeneği sağlayıcıyla teyit edilmelidir. Ücretli hizmet açılmadı.
4. **Sözleşme/satış koşulları:** Satıcı bilgileriyle inceleme taslağı üretildi; satıcı adresi/ticari bilgiler, destek kapsamı ve satış şartları kesinleşmeli. Nihai sözleşme veya üçüncü taraf lisans incelemesi adına otomatik onay üretilmedi.
5. **Üretim lisans anahtarı:** Anahtar oluşturma/dağıtım aracı hazır; üretim özel anahtarı henüz oluşturulmadı. QA özel anahtarı yalnızca test belleğinde üretildi ve kalıcı kaydedilmedi.

Windows özelliğini etkinleştirme ve test hazırlığı, ürünün Microsoft tarafından onaylandığı veya hukuki uygunluğun doğrulandığı anlamına gelmez. Gerçek imza, aynı ikili için temiz kabul ve nihai satıcı onayı tamamlanmadan 1.0 ticari sürüm yayımlanmaz.
