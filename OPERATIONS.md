# CenterEK 0.3 işletim ve pilot bağlantıları

## İlk panel hesabı ve başlatma

Panel artık oturum açmadan erişim sağlamaz. AD ile oturum açılmaz; AD'de kullanıcı oluşturulmaz. CenterEK hesapları mevcut data/monitor.sqlite3 veritabanında tutulur. İzleme cihazları, API anahtarı akışı ve eski kayıtlar korunur.

Programı durdurun ve kaynakları güncelleyin. C:\CenterEK içinde:

```cmd
"C:\Program Files\Python311\python.exe" users.py add --role admin
```

Kullanıcı adı ve en az 12 karakterli parola terminalde sorulur; parola komut satırına argüman olarak yazılmaz. Varsayılan kullanıcı/parola yoktur. Başka bir izleyici hesabı için aynı komutta --role viewer kullanın.

```cmd
"C:\Program Files\Python311\python.exe" start.py
```

Önce FortiGate API anahtarı yerel terminalde girilir, sonra tarayıcıda /login üzerinden CenterEK hesabıyla giriş yapılır. Bu iki kimlik bilgisi ayrıdır. Web oturumu 8 saat geçerlidir; uygulama yeniden başlatılınca sona erer. Parolalar PBKDF2-HMAC-SHA256, rastgele salt ve 600.000 yineleme ile saklanır. IP başına 5 başarısız girişten sonra 5 dakika bekleme uygulanır. Cookie HttpOnly ve SameSite=Strict'tir; HTTPS kullanıldığında Secure eklenir. API, raporlar ve envanter de giriş gerektirir.

Hesap listesi/yerel yönetim:

```cmd
python users.py list
python users.py reset-password
python users.py disable
```

Devre dışı bırakılan veya parolası değiştirilen kullanıcının eski oturumları bir sonraki istekte reddedilir. Yönetici panel kullanıcı listesini görebilir; izleyici bu listeye erişemez. Web üzerinden kullanıcı oluşturma/değiştirme henüz yoktur. AD kullanıcılarını görüntülemek panel hesabı oluşturmaktan farklıdır.

## FortiGate verileri

Mevcut salt okunur API hesabı ve CA dosyası korunur. Yeni okuyucu sistem kimliği, arayüzler, CPU/RAM ve cihaz envanterini ister. İlgili uç noktalar:

- /api/v2/monitor/system/status
- /api/v2/monitor/system/interface
- /api/v2/monitor/system/resource/usage?interval=1-min
- /api/v2/monitor/user/device/query

Kaynak biçimi cpu/mem alanlarındaki ilk current değeridir. İlgili erişim 403 dönerse o bölüm hata gösterir; çalışan trafik verisi kaybolmaz. Envanter ilk 2000 kaydı gösterir. FortiOS sürümü/VDOM/cihaz tanıma ayarları yüzünden bazı cihazlar görünmeyebilir. FortiGate'teki is_online durumu kaynakta gözlenen durum olarak etiketlenir; fiziksel port topolojisi iddiası yoktur.

## AD, DHCP ve DNS: ilk veri aktarımı

Export-DirectoryInventory.ps1 dosyasını AD/DHCP/DNS sunucusuna kopyalayın. Mevcut yetkili Windows oturumuyla çalıştırın:

```powershell
.\Export-DirectoryInventory.ps1
```

Betik AD kullanıcılarının hesap adı, görünen adı, etkinlik durumu ve AD son giriş tarihini; bilgisayar adlarını/işletim sistemlerini; varsa DHCP IPv4 kiralarını ve DNS A kayıtlarını okur. Parola, hash, token veya kişisel iletişim bilgilerini istemez. Hiçbir AD nesnesini, DNS/DHCP kaydını veya firewall ayarını değiştirmez. Yeni AD kullanıcısı oluşturmaz. ActiveDirectory/DhcpServer/DnsServer modülleri ve ilgili okuma yetkileri mevcut olmalıdır. Eksik bölüm dosyanın errors alanında bildirilir.

Masaüstünde oluşan directory-inventory.json dosyasını izleme sunucusundaki C:\CenterEK\data\directory-inventory.json konumuna kopyalayın. Panel en geç 30 saniyede yeniler. 15 dakikadan eski dosya eski veri olarak gösterilir. Bu yöntem canlı LDAP bağlantısı değildir; otomatik dosya aktarımı/zamanlama ayrıca kurulmalıdır. AD lastLogonDate çoğaltmaya tabidir; açık oturum kanıtı değildir. DNS A kaydı ve DHCP kirası da çevrimiçi olma kanıtı değildir. Aynı IP'deki farklı kaynaklar ayrı satırlarda ve kaynak adıyla korunur.

## Uç bilgisayardan hangi kullanıcı açık verisi

Toplayıcı Windows WTS API ile interaktif oturumları okur. DNS sadece bilgisayar adına IP ekler; kullanıcı-IP ilişkisi WTS bilgisayar sorgusuyla doğrulanır. Rapor Active ile Disconnected oturumları ayırır. Active kullanıcının fiziksel olarak bilgisayar başında bulunduğu veya ekranın kilitsiz olduğu anlamına gelmez.

Önce tek bilgisayarda pilot yapın. İzleme sunucusunda mevcut Windows hesabıyla:

```powershell
.\Collect-EndpointSessions.ps1 -ComputerName PC01.example.local -Watch
```

Örnekteki adı gerçek bilgisayar adı/FQDN ile değiştirin. Birden fazla cihaz:

```powershell
.\Collect-EndpointSessions.ps1 -ComputerName PC01.example.local,PC02.example.local -Watch
```

Veri data/endpoint-sessions içine yazılır; panel 30 saniyede yeniler. Betik açık kaldıkça her turdan sonra 60 saniye bekler. Ağ/RPC zaman aşımı turu uzatabilir. 150 saniyeden eski rapor aktif oturum sayısına katılmaz. Sorgu başarısızsa eski kullanıcı oturumu aktif gösterilmez.

Remote WTS için hedefte hizmet, RPC erişimi ve mevcut Windows hesabının oturum sorgulama yetkisi gerekir; ping tek başına yeterli değildir. Betik bunları açmaz, policy değiştirmez veya parola saklamaz. Yetki yoksa önce aynı betiği hedef bilgisayarda yerel olarak çalıştırıp raporu test edin; yerel betik de sorgulama yetkisi gerektirebilir. Hedefte yerel kullanım:

```powershell
.\Collect-EndpointSessions.ps1 -OutputDirectory C:\CenterEK-Reports
```

Üretilen JSON raporu izleme sunucusundaki data/endpoint-sessions klasörüne aktarılabilir. Sürekli dağıtım/GPO/görev ve rapor aktarımı bu sürümde otomatik kurulmaz. Bir hesabın AD kullanıcısıyla eşleşmesi için hem hesap adı hem AD DNS/NetBIOS domain adı eşleşmelidir; aynı adlı yerel hesap domain kullanıcısı sayılmaz.

## Ağdan güvenli panel erişimi

Varsayılan localhost erişimi korunur. Kullanıcı girişi tek başına HTTP trafiğini şifrelemez. Başka bilgisayardan erişim için güvenilen, kullanılan ad/IP'yi kapsayan TLS sertifikası ve anahtar gerekir:

```cmd
python start.py --bind 192.0.2.15 --tls-cert certs/panel-chain.pem --tls-key certs/panel-key.pem
```

Örnek IP'yi gerçek izleme sunucusu adresiyle değiştirin. Loopback dışı HTTP başlatma reddedilir; TLS 1.2 veya üstü gerekir. Dinleme için belirli yerel IP kullanın; Windows firewall erişimini yalnızca yetkili LAN/VPN adresleriyle sınırlandırın. İnternete NAT/port yönlendirme açılmaz. Bunlar program tarafından otomatik değiştirilmez. IIS/kurum reverse proxy alternatifi ayrıca uygun origin ve TLS yapılandırması gerektirir; bu sürümde forwarding başlıkları güvenilir kabul edilmez.

## Doğrulama kapsamı

Python birim/HTTP testleri giriş, çıkış, yetki, kilitleme, API koruması, partial FortiGate yanıtı ve AD/oturum eşleştirmesini kapsar. Windows PowerShell sözdizimi doğrulandı; WTS betiği geliştirme bilgisayarında yerel olarak bir oturum okuyabildi. Gerçek FortiOS 7.4.13 CPU/RAM/envanter, AD/DHCP/DNS modülleri, uzak WTS/RPC ve hedef Windows Server 2012 R2 üzerindeki yeni sürüm için pilot doğrulama hâlâ gerekir. Var olmayan veri üretilmez.
