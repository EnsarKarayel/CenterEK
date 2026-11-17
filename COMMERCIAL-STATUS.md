# Ticari yayın durumu — 17 Kasım 2026

**Satışa hazır değil; 0.9.0-preview geliştirme/kabul sürümüdür.**

## Tamamlanan teknik hazırlık

- Ürün sahibi profili: Ensar Karayel, Türkiye, karayelensar@gmail.com. Tek kaynak `legal/publisher.json`; kimlik bilgisi ürün sahibi tarafından verilmiştir, sertifika otoritesi doğrulaması değildir.
- Yıllık, kurulum kimliğine bağlı imzalı abonelik; süre sonunda ölçüm/keşif/ajan alımını durdurma; geçmiş/CSV erişimini koruma; panelden yenileme.
- Gerçek paketli uygulamada geçici QA anahtarıyla doğal süre bitişi, geçmişe erişim ve aynı süreçte yenileme doğrulandı. Bu test temiz Windows kabulü değildir; QA paketi satış kontrolünden geçemez.
- Nihai sözleşmeyi gösterme, açık kabul ve kabul edilen metnin SHA256/tarih kaydı; yeni metinli yükseltmede yeniden kabul.
- EXE ve PowerShell betiklerini sertifika sağlayıcısıyla imzalama/zaman damgası/doğrulama entegrasyonu. Gerçek üretim sertifikasıyla henüz çalıştırılmadı.
- Temiz Windows/Sandbox test üreticisi ve gerçek görev/ajan/kaldırma/geri kurma betiği. Otomatik rapor UAC/dış setup/reboot alanlarını kendiliğinden başarılı yapmaz.
- Ticari yayın kontrolü eksik şartlarda `sale_ready:false` üretir. CI'deki `--report-only` denetimi ön sürüm testlerinin geçmesine izin verir; yayın onayı değildir.

## Bekleyen somut adımlar

1. **Bilgisayarın manuel yeniden başlatılması:** Ürün sahibinin açık onayıyla Windows Sandbox etkinleştirildi. Windows `RestartNeeded=True` döndürdü. Otomatik yeniden başlatma yapılmadı. Sonuç `data/sandbox-enable-result.local.json`, ayrıntı `data/sandbox-enable.local.log` içindedir.
2. **Gerçek temiz Windows testi:** Yeniden başlatmadan sonra test WSB dosyası açılmalı; raporlar değerlendirilmelidir. Kalıcı yeniden başlatma kabulü ayrıca temiz Windows VM gerektirir; Sandbox kapanınca silinir. Azure'daki mevcut sunucu test için silinmez.
3. **Güvenilir kod imzalama sertifikası:** Makinede henüz yok; satın alma veya kimlik doğrulaması yapılmadı. Türkiye için ticari CA yolu hazırlandı. Bireysel/şirket başvuru ve donanım/bulut anahtar seçeneği sağlayıcıyla teyit edilmelidir. Ücretli hizmet açılmadı.
4. **Sözleşme/satış koşulları:** Satıcı bilgileriyle inceleme taslağı üretildi; satıcı adresi/ticari bilgiler, destek kapsamı ve satış şartları kesinleşmeli. Nihai sözleşme veya üçüncü taraf lisans incelemesi adına otomatik onay üretilmedi.
5. **Üretim lisans anahtarı:** Anahtar oluşturma/dağıtım aracı hazır; üretim özel anahtarı henüz oluşturulmadı. QA özel anahtarı yalnızca test belleğinde üretildi ve kalıcı kaydedilmedi.

Windows özelliğini etkinleştirme ve test hazırlığı, ürünün Microsoft tarafından onaylandığı veya hukuki uygunluğun doğrulandığı anlamına gelmez. Gerçek imza, aynı ikili için temiz kabul ve nihai satıcı onayı tamamlanmadan 1.0 ticari sürüm yayımlanmaz.
