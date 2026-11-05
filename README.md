# CenterEK Monitor 0.3

Yerel ağ, fiziksel sunucu ve ağ cihazları için geliştirilmekte olan izleme uygulaması. Ürün yönü ve ticari yayın kabul ölçütleri [PRODUCT.md](PRODUCT.md) dosyasındadır. Bu sürüm pilot içindir.

## 0.3 yenilikleri ve ilk giriş

Sol menü, okunabilir tablolar, FortiGate CPU/RAM ve IP/MAC envanteri; AD kullanıcılarını içe aktarma ve uç bilgisayardan kullanıcı-oturum sorgulama eklendi. AD oturum açma entegrasyonu veya AD'de hesap oluşturma yoktur.

**Panel artık kullanıcı girişi gerektirir.** Güncellemeden sonra önce yerel hesabı oluşturun, ardından start.py çalıştırın:

```cmd
"C:\Program Files\Python311\python.exe" users.py add --role admin
"C:\Program Files\Python311\python.exe" start.py
```

Kurulum, AD/DHCP/DNS aktarımı, uç bilgisayar oturum sorgulama, kullanıcı rolleri ve TLS erişimi: **[OPERATIONS.md](OPERATIONS.md)**.

Güncelleme yardımcısı update.py, uygulama durdurulmuşken kaynakları indirir; önce klasörü yedekler, yerel ayar/verileri korur. GitHub'dan yeni dosyaların tamamını almak gerekir; eski bir dosya listesiyle kısmi güncelleme yapmayın.

## Neler var?

- ICMP veya seçilmiş TCP portu ile erişim ve kesinti takibi.
- Genel durum ekranında öncelikli sorunlar ve önerilen ilk kontroller.
- Cihaz araması, son 24 saatlik erişim/CPU/RAM grafikleri, datastore ve port ayrıntıları.
- Yapılandırılırsa ESXi CPU/RAM/uptime/datastore okuyucusu.
- Yapılandırılırsa SNMPv2c IF-MIB port durumu, 64-bit trafik ve hata sayaçları (en fazla 128 port).
- FortiGate sistem/arayüz, CPU/RAM ve IP/MAC envanteri okuyucusu (ek uç noktalar için FortiOS sürümünde doğrulama gerekli).
- Belirtilen özel IP aralığında ICMP ve altı TCP servisi keşfi. Otomatik cihaz kimliği tespiti veya tam port taraması değildir.
- SQLite kalıcı kayıt; ölçümler 30 gün saklanır, panel son 24 saati gösterir. Kesinti olayları korunur.
- Durum ve başarılı kontrol oranını içeren CSV raporu.

## Kurulum

Python 3.11+ gerekir. Temel erişim/keşif için ek paket gerekmez; ESXi ve SNMP için:

```cmd
cd /d C:\CenterEK
"C:\Program Files\Python311\python.exe" -m pip install -r requirements.txt
```

Yeni kurulumda örneği kopyalayıp cihazları düzenleyin. Mevcut kurulumda config.local.json dosyanızı koruyun:

```cmd
copy config.example.json config.local.json
"C:\Program Files\Python311\python.exe" monitor.py --check-config
"C:\Program Files\Python311\python.exe" monitor.py
```

Panel: http://127.0.0.1:8765 . Panel yalnızca çalıştığı bilgisayardan erişilir. Kimlik doğrulama zorunludur. Ağ erişimi için --bind ile birlikte --tls-cert ve --tls-key gerekir; ayrıntılar OPERATIONS.md içindedir.

Kullanıcı Windows Server 2012 R2 / Python 3.11.9 üzerinde 0.1 panelini çalıştırdı. 0.3 ve ek paketlerin aynı makinede doğrulanması gerekir. Ticari sürüm için güncel, desteklenen platform matrisi ayrıca belirlenecek.

## Mevcut sürümü güncelleme

1. Çalışan terminalde Ctrl+C ile uygulamayı durdurun.
2. C:\CenterEK klasörünün tamamını ayrı bir konuma yedekleyin.
3. Yeni GitHub ZIP'indeki kaynak dosyalarını C:\CenterEK üzerine kopyalayın. config.local.json, config.backup.local.json, certs ve data klasörünü koruyun. .git klasörünü sunucuya taşımak gerekmez.
4. Yukarıdaki pip komutunu çalıştırın. --check-config ile ayarları doğrulayın.
5. İlk panel hesabını users.py add --role admin ile oluşturun. API bilgilerini sorarak başlatmak için start.py çalıştırın.

Veritabanı tabloları açılışta eklenir; önceki durum ve kesinti kayıtları silinmez. Eski tarihler için yeni ölçüm grafikleri geriye dönük oluşmaz.

## Ağ keşfi

Yalnızca yönettiğiniz ağda, izleme sunucusunda çalıştırın. Yerel aralığı açıkça belirtin:

```cmd
"C:\Program Files\Python311\python.exe" discover.py --start 192.168.1.1 --end 192.168.3.255
```

En fazla 1024 adres, 24 paralel iş; ICMP ve TCP 22/80/443/445/3389/4443 kontrol edilir. Birkaç dakika sürebilir. Diğer portları kullanan veya bu kontrollere yanıt vermeyen cihazlar kaçabilir. Sonuç data/discovery.json içine yazılır ve panelde Ağ keşfi sekmesinde görünür. Aktif izleme listesi değiştirilmez. Tek dış IP, VLAN veya subnet maskesini belirlemez; fiziksel topoloji keşfi ayrı bir iştir.

## Kaynak bağlantılarını yapılandırma

```cmd
"C:\Program Files\Python311\python.exe" configure.py
```

Bir cihaz ve bağlantı türü seçilir. ESXi/FortiGate için port ve güvenilen CA PEM yolu sorulur. Parola veya token bu adımda kaydedilmez. Sonra:

```cmd
"C:\Program Files\Python311\python.exe" start.py
```

Terminal yalnızca yapılandırılan bağlantıların kullanıcı/parola/community/token değerlerini sorar. Parolalar ekranda gösterilmez; işlem belleği ve ortam değişkenlerinde tutulur, dosyaya yazılmaz. İsterseniz ilgili ortam değişkenlerini servis hesabı ortamından sağlayabilirsiniz. Mevcut yapılandırma config.backup.local.json olarak yedeklenir.

ESXi için her hostta okuma yetkili hesap; FortiGate için izleme sunucusu IP'sine sınırlı ve gereken monitor uç noktalarına okuma yetkili REST API hesabı gerekir. SNMPv2c cihazda etkin olmalı, community yalnızca okuma ve izleme sunucusu IP'siyle kısıtlanmalıdır. SNMPv2c şifrelenmez; SNMPv3 henüz uygulanmadı. Switch, AP veya firewall IF-MIB sağlıyorsa aynı SNMP okuyucusu kullanılabilir.

HTTPS doğrulaması varsayılan olarak açıktır. Cihazın sertifikası güvenilen CA'dan gelmeli ve kullanılan IP ile eşleşmelidir. Özel CA için collector.ca_file kullanılır. Geçersiz sertifika veya kimlik bilgisi durumunda erişim kontrolü yeşil olsa bile kaynak ölçümü hata gösterir. FortiGate API yolları/alanları sürüme göre değişebilir; 401/403/404 yanıtları gerçek cihaz üzerinde incelenmelidir.

Yerel collector örneği (mevcut cihaz kaydına eklenir):

```json
{
  "collector": {
    "type": "esxi",
    "port": 443,
    "username_env": "CENTEREK_SERVER1_USERNAME",
    "password_env": "CENTEREK_SERVER1_PASSWORD",
    "ca_file": "C:/CenterEK/certs/site-ca.pem"
  }
}
```

SNMP için type=snmp ve community_env; FortiGate için type=fortigate ve token_env kullanılır. Parola/token/community değerini config içine yazmayın. Yerel config, certs, data ve yedek config dosyaları Git dışında tutulur.

## Ölçümleri yorumlama

Varsayılan 30 saniye, 3 ardışık başarısızlık sonrası olay; ilk başarısızlık ve doğrulama zamanı ayrıdır. Kaynak okuyucuları bağımsız iş parçacığında yaklaşık 60 saniyede bir çalışır; uzun sorgular aralığı uzatabilir. Eski veri sağlıklı sayılmaz. CPU/RAM yüzde 90 ve üzerindeki tek güncel ölçüm uyarı üretir; süreklilik garantisi yoktur.

24 saatlik oran başarılı kontroller / toplam kontrollerdir; zaman ağırlıklı SLA değildir. Uygulama kapalıyken ölçülmeyen aralıklar oran hesabında yoktur. Trafik Mbps sayaç farkıdır; internet hattının azami kapasitesi veya hız testi değildir. İlk sayaç ölçümü, sıfırlanma, discontinuity değişimi ve 180 saniyeyi aşan aralıkta hız boş kalır. IF-MIB desteklenmeyen alanlar boş kalır; yönetimsel olarak kapalı portun oper down olması tek başına kablo arızası kanıtı değildir.

ICMP süresi ping komutunun başlatılma süresini içerir; kesin RTT değildir. TCP erişimi uygulamanın işlevini veya donanımın tamamen sağlıklı olduğunu kanıtlamaz. Fiziksel kablo haritası, MAC eşleme, sıcaklık ve fan için ilgili okuyucular gerekir.

İsteğe bağlı depends_on cihaz ID listesi manuel ilişkiyi gösterir; otomatik fiziksel topoloji veya kesin kök neden iddiası yoktur. Bağımlılık döngüleri reddedilir. Bildirim bastırma henüz yoktur.

## Henüz olmayanlar

Linux/Windows kaynak ajanı, WMI, Dell iDRAC sıcaklık/fan, SNMPv3, LLDP/CDP/FDB topolojisi, NetFlow/sFlow, DNS ve paket kaybı ölçümleri, gerçek hız testi, dışarı bildirim, Windows servisi, web üzerinden kullanıcı yönetimi ve çok müşteri izolasyonu. Panel kullanıcı girişi/rol ayrımı eklendi; uç oturum ve AD veri akışı OPERATIONS.md içinde açıklanır. Ürünün bu işlevleri varmış gibi satılması uygun değildir; ayrıntılı sıra PRODUCT.md içindedir.

## Test ve yedekleme

```cmd
python -m unittest discover -s tests -v
```

Uygulamayı durdurup data ve yerel config dosyalarını yedekleyin. Ölçümlerin 30 günlük temizliği erişim döngüsü sonrasında yapılır; olay geçmişi temizlenmez. Yerel testler gerçek ESXi/FortiGate/switch entegrasyon doğrulamasının yerine geçmez.

## Ticari durum

Açık kaynak lisansı atanmadı; ticari lisans ve şartlar ürün sahibi tarafından belirlenecek. Üçüncü taraf paketlerin lisansları ayrıca geçerlidir. Satış öncesi güvenlik, kurulum/güncelleme, servis çalışma şekli, yedekleme, destek ve yük testleri tamamlanmalıdır.
