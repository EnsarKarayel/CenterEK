# CenterEK Monitor

Yerel ağ için ilk çalışan erişim ve kesinti izleme sürümü. Python standart kütüphanesi dışında bağımlılık yoktur.

## Çalıştırma

Python 3.11 veya üzeri bulunan bir makinede:

```powershell
Copy-Item config.example.json config.local.json
# config.local.json içindeki cihazları kendi ortamınıza göre düzenleyin.
python monitor.py --check-config
python monitor.py
```

Tarayıcı: http://127.0.0.1:8765 . Uygulama yalnızca yerel arayüzü dinler. Başka bilgisayarlara açmak için kimlik doğrulama ve TLS katmanı eklenmelidir.

Windows Server 2012 R2 üzerinde çalışma henüz doğrulanmadı. Yerelde Python 3.12 ile test edildi; bu hedef işletim sisteminde kurulum/runtime doğrulaması yapılmadan uyumluluk garantisi yoktur. Python belgeleri ve gerçek sunucu testiyle uygun runtime seçilmelidir. İlk pilot için güncel Windows veya Linux üzerinde çalıştırılabilir; hedef cihazlarda Python gerekmez.

## Ölçümler

- ICMP veya belirli bir TCP portuna bağlantı kontrolü; tam port taraması yapmaz.
- Varsayılan 30 saniye, 3 ardışık başarısızlık sonrası kesinti.
- SQLite üzerinde kalıcı güncel durum ve kesinti geçmişi; yeniden başlatmada korunur.
- İlk başarısız kontrol zamanı ve doğrulama zamanı ayrı tutulur.
- Eski ölçümler panelde güncel olmayan veri olarak gösterilir.
- ICMP yanıtı engellenmiş olabilir; başarısızlık güç kesintisi kanıtı değildir.
- TCP bağlantısı servis içeriğinin doğru çalıştığını kanıtlamaz.
- ICMP milisaniye değeri ping komutunun başlatılma süresini de içerir; kesin RTT değildir.
- Servisin kapalı kaldığı aralıkta gerçekleşen olaylar ölçülemez. Devam eden bir olayın kapanışı ilk başarılı ölçümde tespit edilir.
- Veritabanını yedeklemek için uygulamayı durdurup data klasörünü kopyalayın. Otomatik saklama süresi/temizleme henüz yoktur.

## Henüz yapılmayanlar

ESXi CPU/RAM/datastore, Linux kaynak ajanı, Dell iDRAC/Redfish, FortiGate SNMP/API, switch portları, DNS/paket kaybı ölçümü, gerçek hız testi, bildirim gönderimi ve Windows servisi kurulumu bu sürümde yoktur. Bunların değerleri taklit edilmez. Oturum kapalıyken otomatik çalışma için servis/görev kurulumu sonraki adımdır.

## Test

```powershell
python -m unittest discover -s tests -v
```

## Ticari ürün yolu

Bu sürüm pilot prototiptir. Satış öncesi kimlik doğrulama ve roller, TLS, müşteri ayarları/secrets yönetimi, alarm bağımlılıkları, harici gözlemci, yedekleme/saklama politikası, kurulum/güncelleme, yük ve güvenlik testleri tamamlanmalıdır. Lisans ve ticari şartlar ürün sahibi tarafından belirlenecek; açık kaynak lisansı atanmadı.

Müşteriye özel config.local.json, data ve kimlik bilgileri Git'e eklenmez. Örnek IP, dokümantasyon için ayrılmış adres aralığındadır.
