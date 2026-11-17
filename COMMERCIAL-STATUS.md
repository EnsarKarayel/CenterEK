# Ticari yayın durumu — 17 Kasım 2026

**Satışa hazır değil; 0.9.2-preview geliştirme/kabul sürümüdür.**

## Yeniden başlatma sonrası gerçek Windows kabulü

Windows Sandbox, ürün sahibi bilgisayarı yeniden başlattıktan sonra çalıştırıldı. Python kurulu olmayan Windows 11 Enterprise 26100 misafirde 0.9.2 paketinin temiz kurulumu, HTTPS giriş, SYSTEM sunucu/ajan görevleri, uç ajan alımı, Windows uygulama kaydı, veri saklayan kaldırma ve aynı hesapla geri kurma başarılı tamamlandı. Rapor: `data/clean-windows/0.9.2-20261117/reports/clean-windows-report.json` (`ok:true`). Dış setup/UAC etkileşimi ve kalıcı VM yeniden başlatma alanları hâlâ `pending` durumundadır; bu rapor imzalı ticari kabul değildir.

Ayrı temiz misafirde gerçek 0.9.1 → 0.9.2 yükseltme ve 0.9.2 → 0.9.1 geri alma, aynı hesap/kurulum kimliği korunarak geçti. Ardından kaldırma ve aynı hesapla geri kurma da geçti. Paylaşılabilir sonuçlar `docs/acceptance/0.9.2-preview/` altında kaydedildi; ham tanı günlükleri Git'e alınmadı.

İlk gerçek testlerde yakalanan iki hata düzeltildi: DNS adı ile Windows NetBIOS adının farklı olması nedeniyle yanlış ajan kimliği; Windows PowerShell 5.1'in JSON görev dizisini tek iç içe öğe olarak döndürmesi nedeniyle kaldırma/geri yükleme hatası. Bilgisayar eşleşme ve görev sahipliği korumaları gevşetilmedi. 132 Python testi ve Windows PowerShell boş/tek/çoklu görev JSON testleri geçti.

## Tamamlanan teknik hazırlık

- Ürün sahibi profili: Ensar Karayel, Türkiye, karayelensar@gmail.com. Tek kaynak `legal/publisher.json`; kimlik bilgisi ürün sahibi tarafından verilmiştir, sertifika otoritesi doğrulaması değildir.
- Yıllık, kurulum kimliğine bağlı imzalı abonelik; süre sonunda ölçüm/keşif/ajan alımını durdurma; geçmiş/CSV erişimini koruma; panelden yenileme.
- Gerçek paketli uygulamada geçici QA anahtarıyla doğal süre bitişi, geçmişe erişim ve aynı süreçte yenileme doğrulandı. Bu test temiz Windows kabulü değildir; QA paketi satış kontrolünden geçemez.
- Nihai sözleşmeyi gösterme, açık kabul ve kabul edilen metnin SHA256/tarih kaydı; yeni metinli yükseltmede yeniden kabul.
- EXE ve PowerShell betiklerini sertifika sağlayıcısıyla imzalama/zaman damgası/doğrulama entegrasyonu. Gerçek üretim sertifikasıyla henüz çalıştırılmadı.
- Temiz Windows/Sandbox test üreticisi ve gerçek görev/ajan/kaldırma/geri kurma betiği. Otomatik rapor UAC/dış setup/reboot alanlarını kendiliğinden başarılı yapmaz.
- Ticari yayın kontrolü eksik şartlarda `sale_ready:false` üretir. CI'deki `--report-only` denetimi ön sürüm testlerinin geçmesine izin verir; yayın onayı değildir.
- Yayın denetimi artık dış setup ve ZIP özetlerini, açılmış paketin tüm dosyalarını, paket içindeki sözleşme/üçüncü taraf envanteri ve satıcı profilini de doğrular. Değişen dış setup eski kabul kaydıyla onaylanmaz. Bu denetim çalışması mevcut 0.9.2 ikilisini veya önceki kabul kanıtını değiştirmez.

## Bekleyen somut adımlar

1. **Manuel yeniden başlatma tamamlandı:** Ürün sahibi yeniden başlattığını bildirdi ve Sandbox çalıştırılarak doğrulandı. Agent otomatik yeniden başlatma yapmadı.
2. **Temiz Windows kabulünün kalan kapsamı:** Temel kurulum/kaldırma/geri kurma yukarıdaki raporla geçti. Kalıcı yeniden başlatma, dış setup/UAC, imzalı ticari paket ve Server kabulü ayrıca tamamlanmalıdır. Sandbox kapanınca silinir; Azure'daki mevcut sunucu test için silinmez.
3. **Güvenilir kod imzalama sertifikası:** Makinede henüz yok; satın alma veya kimlik doğrulaması yapılmadı. Türkiye için ticari CA yolu hazırlandı. Bireysel/şirket başvuru ve donanım/bulut anahtar seçeneği sağlayıcıyla teyit edilmelidir. Ücretli hizmet açılmadı.
4. **Sözleşme/satış koşulları:** Satıcı bilgileriyle inceleme taslağı üretildi; satıcı adresi/ticari bilgiler, destek kapsamı ve satış şartları kesinleşmeli. Nihai sözleşme veya üçüncü taraf lisans incelemesi adına otomatik onay üretilmedi.
5. **Üretim lisans anahtarı:** Anahtar oluşturma/dağıtım aracı hazır; üretim özel anahtarı henüz oluşturulmadı. QA özel anahtarı yalnızca test belleğinde üretildi ve kalıcı kaydedilmedi.

Windows özelliğini etkinleştirme ve test hazırlığı, ürünün Microsoft tarafından onaylandığı veya hukuki uygunluğun doğrulandığı anlamına gelmez. Gerçek imza, aynı ikili için temiz kabul ve nihai satıcı onayı tamamlanmadan 1.0 ticari sürüm yayımlanmaz.
