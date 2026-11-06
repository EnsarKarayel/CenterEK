# CenterEK Windows kurulum önizlemesi

Bu paket başka bir temiz Windows bilgisayarda kurulum denemesi içindir. Ticari son sürüm değildir. Python ve pip hedef bilgisayarda gerekmez; çalışma zamanı paket içindedir. Paket Windows x64 üzerinde üretilir. İlk kabul hedefleri Windows 10/11 ve Windows Server 2019+; Server 2012 R2 bu paketle doğrulanmış değildir.

## Başlatma

1. ZIP'in tamamını bir klasöre çıkarın. EXE'yi ZIP içinden çalıştırmayın; `_internal` klasörünü ayırmayın.
2. `CenterEK-Setup.exe` dosyasını açın. Windows yönetici izni gerekir.
3. Dil, boş bir hedef klasör, ilk yönetici kullanıcı/parolası ve portu girin.
4. Varsayılan “yalnızca bu bilgisayar” modudur. LAN istenirse bu bilgisayara ait özel IPv4 adresini ve isteğe bağlı firewall iznini seçin.
5. HTTPS sertifikası otomatik oluşturulur. Kurulumda görünen CA güven seçimi, yalnızca seçilen panel adı/IP'lerine daraltılan yeni CA'yı Windows makine kök deposuna ekler. Bu güvenin kurulmasını istemiyorsanız önizlemenin otomatik kurulumunu tamamlamayın.
6. İsteğe bağlı yerel ölçüm ajanını seçin. AD/DNS ajanı yalnızca bu bilgisayarda AD modülü ve okuma yetkisi varsa seçilmelidir. AD'de yeni kullanıcı oluşturulmaz.
   “Bağlı yerel ağları otomatik bul” seçiliyse Ethernet/Wi-Fi IP/mask/gateway verisinden ağlar algılanır. Aynı subnet bir kez taranır. Public, loopback, link-local, VPN/sanal adaptörler ve toplam 1024 adres sınırını aşan aralıklar otomatik taramaya alınmaz. Geniş aralıklar Ağ keşfi ekranında belirtilir.
7. Kurulum sonrası “Paneli aç” düğmesine basın. İlk yönetici hesabınızla giriş yapın.

## Otomatik yapılanlar

- Program ve kendi Python/SDK çalışma zamanı özel hedef klasöre kopyalanır; sistem Python'una veya PATH'e ekleme yapılmaz.
- HTTPS sertifikası, ilk hesap/veritabanı, loopback/LAN ayarı ve seçilen yerel ajan kimlikleri oluşturulur.
- Arka plan SYSTEM zamanlanmış görevleri açılışta ve Windows oturumu kapalıyken çalışır. Konsol pencereleri gerekmez.
- Paketlenen yerel PowerShell betikleri yalnızca ilgili süreçlerde RemoteSigned ilkesiyle çağrılır. Makine/grup ilkesi kalıcı değiştirilmez; kurumsal GPO kısıtlaması kaldırılmaz. Kurum politikası engellerse kurulum hata bildirir.
- LAN kuralı yalnızca seçilirse, seçilen IP/port ve LocalSubnet için Private/Domain profillerinde açılır. Public profil ve modem/NAT/harici firewall değiştirilmez.
- Kurulum günlüğü `data/logs/install.log`, uygulama günlükleri `data/logs/` içindedir. Parolalar kurulum dosyasına veya günlüğe yazılmaz.
- Otomatik keşif ICMP ve TCP 22/80/443/445/3389/4443 erişimini kontrol eder; bulunan özel IP'leri marka/tür uydurmadan erişim izlemeye ekler. İlk /22 taraması birkaç dakika sürebilir. Ağ keşfi ekranında ilerleme ve atlanan aralıklar görünür. Tarama saatte bir yenilenir; tüm 65535 port veya tüm UDP servisleri taranmaz.
- Diğer bilgisayarların RAM/disk/oturum bilgileri için uç ajanı veya yetkili kaynak bağlantısı ayrıca gerekir. Bu paket başka bilgisayara habersiz ajan yüklemez ve erişim parolalarını tahmin etmez.

## Deneme kabul listesi

- [ ] Python olmayan temiz Windows'ta kurulum tamamlandı.
- [ ] Panel HTTPS ile açıldı, girilen ilk hesapla giriş yapıldı.
- [ ] Yerel ajan seçildiyse oturum, RAM, disk ve MAC raporu güncellendi.
- [ ] CMD/PowerShell kapalıyken ve Windows oturumu kapatılıp açılınca veri akışı sürdü.
- [ ] Bilgisayar yeniden başlatılınca SYSTEM görevleri çalıştı.
- [ ] Yerel mod diğer bilgisayardan erişilemedi; LAN modu yalnızca seçilen kapsamdan erişildi.
- [ ] SNMP/ESXi/API profili hedef cihazla ayrıca test edildi.

## Sınırlar

Bu ilk kurulum paketi imzasızdır; güvenlik uyarıları/kurum politikaları oluşabilir. Güvenlik ürünlerini kapatmayın. İmzalı MSI/tek dosya dağıtım ve temiz makine/yeniden başlatma kabulü tamamlanmadan ticari yayın yapılmamalıdır. ZIP hash dosyası iletim bütünlüğünü kontrol eder, yayıncı kimliği doğrulaması değildir.

Önizleme yalnızca boş hedef klasöre kurulur. Mevcut CenterEK kurulumu, veritabanı ve sertifikaları üzerine yükseltme yapmaz. Tam yükseltme/geri alma ve kaldırma sihirbazı henüz tamamlanmadı. Hata durumunda tanı için kurulum klasörü korunur; kurulum bazı görevleri/sertifika güvenini oluşturmuş olabilir. Hata ekranından sonra tekrar denemeden önce günlükleri inceleyin. Paket mevcut uygulama klasörü/C sürücüsü kökü/Windows klasörü üzerine kurulmaz.

Sunucu için başlangıçta yalnızca bu makinenin erişim hedefi eklenir. Diğer sunucular, switchler, firewall ve AP'ler panelin Kurulum / Bağlantılar bölümünden tanımlanır. Otomatik AP keşfi, disk seri/WWN ve fiziksel RAID sağlığı bu paketle eklenmiş sayılmaz.
# Sonradan uzaktan erişim

Kurulumdan sonra yönetici hesabıyla **Kurulum / Bağlantılar → Uzaktan erişim** ekranından yerel, VPN/LAN veya HTTPS ters proxy modu seçilebilir. Ayarlar yeniden başlatmada uygulanır. VPN/proxy altyapısı ayrıca kurulmalıdır; program WAN portlarını otomatik açmaz. Ayrıntılar `REMOTE-ACCESS.md` dosyasındadır.
