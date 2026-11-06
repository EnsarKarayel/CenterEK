# Ürünleştirme ve geliştirme işleri

Güncelleme: 2026-11-05. Bu dosya sonraki çalışmaların başlangıç noktasıdır.
İşaretlenmemiş maddeler talep/plan durumundadır; uygulanmış veya sunucuya kurulmuş sayılmaz.

## Hedef ve tasarım

Global pazara yönelik, yerinde çalışan altyapı izleme ve operasyon ürünü. Mevcut teknik ad CenterEK; yeni marka için isim, alan adı ve marka araştırması yapılacak. Türkçe, İngilizce, Fransızca ve Almanca zorunlu.

Görsel referans: kullanıcının paylaştığı OpManager ekranları ve [IT operations management](https://www.manageengine.com/network-monitoring/it-operations-management.html). Özgün arayüz üretilecek; ürünün kodu, markası ve görselleri kopyalanmayacak.

Sol gezinme: Genel durum, Ağ haritası, Sunucular, Switchler, Firewall, Access pointler, Bilgisayarlar, AD kullanıcıları, Kullanıcı–bilgisayar, Alarmlar, Raporlar, Güvenlik bulguları, Kurulum ve Ayarlar.

Dashboard: okunabilir kartlar, ağ görünümü, sağlık ısı haritası, CPU/RAM/disk sıralamaları, zaman serileri, alarm halkası ve olay akışı. NOC/tam ekran ve koyu/açık tema. Sinematik hareketli bağlantılar gerçek ölçümle ilişkilendirilecek; dekoratif hareket canlı paket yakalama olarak sunulmayacak. Ölçüm zamanı ve veri kaynağı görünür olacak. Hareket azaltma seçeneği bulunacak.

## Mevcut temel

- [x] Erişim kontrolleri, kesinti geçmişi ve SQLite saklama.
- [x] ESXi, FortiGate ve temel SNMP arayüz okuyucuları.
- [x] Yerel panel hesapları ve HTTPS ajan rapor alımı.
- [x] AD/DNS dışa aktarımı, Windows oturum raporları ve temel CPU/RAM ölçümü.
- [x] SYSTEM zamanlanmış görev kurulumu ve arka plan günlükleri.
- [x] Temel canlı panel ve ölçüm yaşı gösterimi.

Bunlar kapsamlı ürün kabulü anlamına gelmez. Kod, yerel test ve müşteri ortamındaki doğrulamalar ayrı kaydedilecek.

## P0 — Güvenilir veri ve cihaz görünürlüğü

- [ ] Birleşik cihaz kimliği: hostname/FQDN, ajan kimliği, MAC, IP geçmişi ve kaynak ilişkileri. Aynı IP birden fazla rol barındırabilir; IP tek başına kalıcı kimlik değildir.
- [ ] FortiGate DHCP kiraları, ARP ve cihaz envanteri: sayfalama, yetki hatası ve gerçekten boş yanıtı ayrı göster. Başarılı HTTP yanıtını veri varmış gibi sunma.
- [ ] AD kullanıcı ve bilgisayar kayıtlarının otomatik yenilenmesini doğrula; domain/kullanıcı üzerinden ajan oturumlarıyla eşleştir. AD kaydı tek başına açık oturum kanıtı değildir.
- [ ] Windows ajanı: cihaz adı, üretici/model, işletim sistemi/sürüm, toplam/kullanılan RAM, RAM modülü kapasitesi/hızı/türü, fiziksel disk kapasitesi/modeli, birim toplam/boş alanı ve aktif/bağlantısı kesilmiş AD oturumları.
- [ ] Linux ajanı/toplayıcısı: isim, donanım, RAM, disk/birimler ve kullanıcı oturumları. AD üyeliği varsa kaynak belirt; Windows WTS gibi yorumlama.
- [ ] Dell iDRAC/Redfish: sıcaklık, fan, güç kaynağı, fiziksel disk/RAID ve donanım sağlığı; yetki ve model desteğini doğrula.
- [ ] Desteklenmeyen, yetkisiz, eski veya eksik alanları sıfır yerine açık durum etiketiyle göster.

Kabul: iki IP taşıyan tek bilgisayar çoğalmaz; aynı IP'yi sonradan alan cihaz yanlış kullanıcıyla eşleşmez; eski rapor aktif sayılmaz; RAM ve disk toplamları örnek cihazlarda işletim sistemiyle karşılaştırılır.

## P0 — Akıllı switchler ve topoloji

- [ ] Otomatik AP keşfi: izin verilen ağlardan DHCP/ARP, SNMP kimliği ve LLDP verisini birleştir; desteklenen model kimliği doğrulanmayan cihazı “AP adayı” olarak tut. Port yanıtı veya üretici adı tek başına AP kanıtı sayılmasın. Toplu izlemeye eklemeden önce sonuç/kimlik bilgisi eşleştirmesi gösterilsin.
- [ ] Wi-Fi controller/AP entegrasyonu: tüm kablosuz istemciler, SSID, bağlı AP, sinyal ve son görülme. Ajan ağ kartı listesi tüm Wi-Fi ağı envanteri diye sunulmasın.

Kullanıcı tüm switchlerin yönetilebilir olduğunu belirtti. Marka/model, yönetim IP'si ve desteklenen protokoller henüz envanterlenmedi.

- [ ] Arayüzden switch ekleme ve bağlantı testi; SNMPv3 öncelikli, gerektiğinde açıkça seçilen salt okunur SNMPv2c.
- [ ] Port adı/açıklaması, yönetim/operasyon durumu, hız, duplex, alım/gönderim, hata/discard ve sayaç sıfırlanması.
- [ ] Desteklenen cihazlarda VLAN, trunk/access, LAG, PoE tüketimi/bütçesi, CPU/RAM/sıcaklık ve uptime.
- [ ] LLDP, gerektiğinde CDP, bridge FDB ve ARP üzerinden switch–switch, switch–AP ve switch–uç cihaz ilişkileri.
- [ ] VLAN/FDB bağlamını koru; uplink arkasındaki MAC'i doğrudan o porta takılı PC diye işaretleme. Yönetilmeyen ara cihaz ve eksik komşuluklarda belirsizlik göster.
- [ ] Tıklanabilir switch ön paneli, port tablosu ve topoloji haritası; bağlantı kaynağı ve son gözlem zamanı.
- [ ] Beklenen uplink düşmesi, port flapping, hata artışı ve PoE kapasitesi alarmları. Kullanılmayan kapalı port alarm üretmemeli.

Kabul: en az iki gerçek switch ve bir uç cihaz bağlantısı kablolamayla karşılaştırılır; LLDP/FDB destek veya yetki eksikliği düzgün gösterilir.

## P0 — Kurulum ve erişim

### Erişim modları — kullanıcı tercihi

- [ ] Varsayılan: yalnızca bu bilgisayar; panel tarayıcıda localhost/loopback adresiyle açılsın. Kurulum kendiliğinden genel ağ dinlemesi veya internet port yönlendirmesi oluşturmasın.
- [ ] İsteğe bağlı yerel ağ: yönetici dinlenecek ağ adresini/portu ve erişim kapsamını seçsin; panel HTTPS ve kullanıcı oturumuyla erişilsin. Windows güvenlik duvarı kuralı gerekiyorsa kapsamı gösterilsin ve seçilen kurulum adımıyla uygulansın.
- [ ] İsteğe bağlı internet erişimi: alan adı, geçerli TLS sertifikası, ters proxy/VPN seçenekleri ve gerekli ağ yönlendirmesi açıklansın. IP değiştirmek tek başına internet yayını sayılmaz; NAT/CGNAT ve DNS koşulları kontrol edilsin.
- [ ] İnternet modu: MFA, giriş/istek hız sınırları, güvenli oturumlar, proxy güven sınırı ve denetim kayıtları yayın ön kontrolünde doğrulansın. Uygulama internet erişimine hazır diye işaretlenmeden bu kontroller tamamlanmalı.
- [ ] Erişim ayarları arayüzden sonradan değiştirilebilsin; mevcut kullanıcıyı dışarıda bırakmayan ön kontrol, uygulama/geri alma ve yeni adres gösterimi olsun.
- [ ] Kurulum sonrası seçilen erişim moduna göre doğru panel adresini aç/göster. Sertifikanın IP/hostname kapsamı adres değişikliğinde tekrar doğrulansın.

Kabul: varsayılan kurulum başka bilgisayardan erişilemez; LAN modu yalnızca seçilen kapsamdan HTTPS ile erişilir; internet modu ayrı test ortamında doğrulanır. Kullanıcının yönlendiricisi veya firewall'u açık yetkilendirme olmadan otomatik değiştirilmez.

Kullanıcı tarafından ayrıca teyit edilen dağıtım akışı: **İndir → kurulum sihirbazı → gerekli bilgileri gir → bağlantıları doğrula → kur → otomatik çalıştır.** ZIP içinden betik çalıştırmak nihai ürün kurulumu değildir.

- [ ] İndirilebilir Windows Setup.exe/MSI; imzalı, sürümlü ve bütünlüğü doğrulanabilir paket.
- [ ] Kurulum öncesi ekranlar: TR/EN/FR/DE dil, lisans, hedef klasör, port/hostname, veri saklama ve ilk yönetici bilgileri.
- [ ] Kaynak seçimi: AD, firewall, ESXi, switch ve uç ajan rolleri; aynı sunucu/IP üzerinde birden fazla rol seçilebilsin.
- [ ] Her kaynak için gerekli adres, protokol, port, yetki ve sertifika alanlarını açıklayan form; parola/token gizleme ve sırların güvenli saklanması.
- [ ] Ön kontrol: işletim sistemi, disk, port çakışması, yetki ve bağlantı testi. Hata varsa anlaşılır düzeltme adımı; eksik kaynağı daha sonra ekleme seçeneği.
- [ ] Kurulum tamamlandığında HTTPS panelini aç; kaynak ve ajan kurulum durumlarını göster. Başarısız kurulum yarım yapılandırmayı çalışan sistem diye sunmasın.
- [ ] Kabul: temiz desteklenen Windows'ta Python/CMD/JSON düzenlemesi gerekmeden kurulum ve yeniden başlatma sonrası çalışma. Gerçek paket üretilip temiz makinede denenmeden tamamlandı sayılmaz.

- [ ] Tek Windows kurulum paketi: Python çalışma zamanını paketle; kullanıcıdan Python ve CMD işlemleri isteme.
- [ ] Sihirbaz: dil, klasör, panel adresi, ilk yönetici, roller, veri kaynağı bağlantıları ve bağlantı testleri.
- [ ] AD, panel ve toplayıcı aynı sunucuda çalışabilsin; tek IP ve birden fazla rol desteklensin. Ayrı sunucu seçeneği korunsun.
- [ ] Sertifika üretimi, anahtar izinleri, istemci güven dağıtımı, yenileme ve süresi dolma uyarıları. Özel CA ve kurumsal sertifika seçenekleri.
- [ ] Açılışta ve Windows oturumu kapalıyken otomatik çalışma; tekrar kurulum, yükseltme, geri alma ve kaldırma akışları.
- [ ] Mevcut konfigürasyon, raporlar, sertifikalar ve veritabanını koruyan yedekli geçiş.
- [ ] Aynı makinede farklı ajan rollerinin dosya/görev adları çakışmasın.
- [ ] Desteklenen Windows/Linux sürümleri matrisi; eski Windows pilotu ile ticari destek tabanını ayır.

Kabul: temiz makinede kurulum; yeniden başlatma ve kullanıcı oturumu kapatma sonrası veri; veri kaybı olmadan yükseltme ve geri alma.

## P1 — Modern dashboard ve filtreler

- [ ] Yukarıdaki görsel tasarıma göre modüler, yeniden düzenlenebilir dashboard.
- [ ] Gerçek bağlantı kanıtlı fiziksel harita ve ayrı etiketli mantıksal bağımlılık haritası.
- [ ] Canlı trafik eğrileri, sağlık ısı haritası, alarm akışı ve kullanıcı–bilgisayar kartları; boş veri için dürüst boş durum.
- [ ] Filtre çubuğu: arama, cihaz türü, lokasyon, subnet/VLAN, kaynak, durum, kullanıcı ve tarih aralığı.
- [ ] Sıralama, sayfalama, kayıtlı görünümler, filtre temizleme ve filtrelenmiş dışa aktarım.
- [ ] Cihaz ayrıntıları: Genel, Donanım, Diskler, Oturumlar, Portlar, Geçmiş, Alarmlar ve Güvenlik.
- [ ] TR/EN/FR/DE çeviri kataloğu, dil seçimi, yerel tarih/sayı biçimleri ve metin taşma testleri.

Kabul: telefon ve NOC ekranında okunabilirlik; klavye kullanımı; dört dilde temel akışlar; eski veri ve bağlantı kaybı görünür; ölçüm gelmeden grafik yeni veri üretmez.

## P1 — Panel yönetimi, alarmlar ve raporlar

- [ ] Arayüzden panel kullanıcısı oluşturma, rol atama, parola sıfırlama/devre dışı bırakma; son yönetici korunması.
- [ ] Yerel panel hesabı varsayılan; AD'de yeni kullanıcı oluşturmak zorunlu olmayacak. AD giriş entegrasyonu isteğe bağlı sonraki özellik.
- [ ] Eşik/süre/ardışık başarısızlık tabanlı kural editörü; bakım penceresi, teyit, çözülme ve bağımlı alarm bastırma.
- [ ] SMTP/TLS, alıcı grupları, şablonlar, test gönderimi, kuyruk/yeniden deneme ve yinelenen bildirim engelleme.
- [ ] CSV/PDF raporlar: envanter, kesintiler, kapasite, kullanıcı–bilgisayar ve güvenlik; zamanlanmış raporlar ve erişim kontrolü.

## P1 — Güvenlik doğrulaması ve ISO 27001 hazırlığı

- [ ] Tehdit modeli, varlık/veri sınıflaması ve risk kaydı; kontrol–uygulama–test–kanıt matrisi.
- [ ] Giriş testleri: parola denemeleri, kullanıcı keşfi, oturum sabitleme, CSRF, XSS, SQL enjeksiyonu, rol aşımı ve yetkisiz rapor erişimi.
- [ ] MFA, oturum boşta kalma sınırı, yeniden kimlik doğrulama ve rol/parola değişince oturum iptali.
- [ ] Denetim günlüğü: girişler, yetki/ayar değişimleri, dışa aktarma ve ilerideki yazma işlemleri; sır/parola maskeleme.
- [ ] İstek boyutu, eşzamanlılık, zaman aşımı ve hız sınırları; ters proxy/WAF ve ağ katmanı koruma rehberi. DDoS'a karşı mutlak korunma vaat edilmez.
- [ ] Bağımlılık taraması, SBOM, imzalı paketler, güncelleme bütünlüğü, yedek geri yükleme ve güvenlik olay müdahale rehberi.
- [ ] Veri saklama/silme, oturum verilerinin mahremiyeti ve müşteri erişim sınırları.

ISO/IEC 27001 uyumu yalnızca yazılımla veya bu listeyle sağlanmış sayılmaz; kuruluşun ISMS süreçleri ve bağımsız değerlendirme gerekir. Tamamlanmamış testler yapılmış gibi raporlanmayacak.

## P2 — Olası güvenlik açıkları görünürlüğü

- [ ] Önce pasif/salt okunur kontrol: işletim sistemi/firmware sürümü, güncelleme durumu, sertifika süresi ve güvenli olmayan protokol yapılandırmaları.
- [ ] Üretici duyurusu/CVE eşleştirme: ürün, sürüm, önkoşul ve güncel kaynak; sürüm eşleşmesini doğrulanmış istismar diye sunma.
- [ ] Bulgu: etkilenen cihaz, önem, kanıt, güven düzeyi, son kontrol, düzeltme önerisi, sorumlu ve kapanma doğrulaması.
- [ ] Kanıt yetersizse “olası açık”; veri yoksa “değerlendirilemedi”. Yanlış pozitif istisnası süreli ve denetlenebilir olsun.
- [ ] Aktif tarama ayrı izinli kapsam, hız ve bakım penceresiyle tasarlansın; varsayılan akışta istismar denemesi yapılmasın.

## P2 — İsteğe bağlı yazma API'leri

- [ ] AD ve firewall için okuma/yazma kimliklerini ayır; varsayılan salt okunur.
- [ ] İşlem bazlı yetkiler, etki önizlemesi, yeniden kimlik doğrulama, gerektiğinde ikinci onay ve değişiklik kaydı.
- [ ] Önce laboratuvar: izin verilen komut listesi, tekrar çalıştırma güvenliği, hata/geri alma planı ve kilitlenmeyi önleme.
- [ ] İlk sürümde uzaktan keyfi komut çalıştırma yerine sınırlı, belgelenmiş işlemler. Gerçek müşteri değişikliği ayrıca açıkça yetkilendirilecek.

## P2 — Ölçek ve ticari yayın

- [ ] SQLite pilot yükünü ölç: cihaz/port/ajan sayısı, yazma hızı, sorgu gecikmesi, disk büyümesi ve saklama süresi.
- [ ] PostgreSQL geçiş tasarımı: şema göçleri, indeksler, geçmiş bölümlendirme, yedekleme ve geri dönüş. SQL Server gereksinimini müşteri ihtiyacına göre değerlendir.
- [ ] Zaman serisi saklama/özetleme, rapor kuyruğu, toplayıcı ayrıştırma ve bağlantı kesilince yerel tampon.
- [ ] Çok lokasyon; sonraki aşamada müşteri izolasyonlu MSP mimarisi ve yetki testleri.
- [ ] NetFlow/sFlow/IPFIX trafik modülü; yalnızca port sayaçlarından uygulama/kullanıcı trafiği çıkarma.
- [ ] Marka/alan adı araştırması, lisanslama, üçüncü taraf lisans incelemesi, fiyatlandırma pilotu ve destek dokümanları.
- [ ] Ticari yayın kapısı: kurulum/yükseltme, performans, güvenlik, dört dil ve gerçek cihaz kabul raporları.

## Devam etme sırası ve kayıt kuralı

1. Bu dosyayı, PRODUCT.md ve UNATTENDED.md dosyalarını oku; git durumunu kontrol et. Gizli yerel ayarları çıktıya yazma.
2. P0 veri hattı: FortiGate envanter/DHCP ve AD/ajan otomatik raporlarını doğrula; birleşik kimlik ve donanım şemasını tamamla.
3. Switch marka/model desteğini ve bir pilot bağlantıyı doğrula; ardından topoloji görselleştirmesini gerçek veriye bağla.
4. Filtreli dashboard ve cihaz ayrıntılarını uygula; kurulum/panel yönetimiyle manuel adımları kaldır.
5. Güvenlik, uluslararasılaştırma ve ticari yayın kapılarını tamamla.

Her çalışma sonunda değişen dosyalar, test sonucu, kalan sorunlar ve dağıtım durumunu aşağıya ekle. Maddeleri yalnızca kabul ölçütü doğrulanınca işaretle. Kodun GitHub'a gönderilmesi müşteri sunucusuna dağıtım anlamına gelmez. Bu dosya otomatik çalışma veya zamanlama oluşturmaz; sonraki oturumda devam bağlamı sağlar.

### Çalışma kaydı

- 2026-11-06: Kullanıcının #73B682/#62A8CB/#FF9933/#2A4954/#272626 paletiyle theme.css eklendi; seçili alanlarda gradyanlar, hata durumlarında ayırt edici kırmızı korundu. SVG bayraklı dil düğmeleri; dashboard gövdeleri, durum/sayaç/boş mesaj çevirileri ve tekrar dil değiştirme düzeltildi. Uzun yardım ve üreticiye özgü açıklamalar için çeviri tamamlanma işi sürüyor. Widget sağ üst büyütme/kapatma, Escape, odak dönüşü ve canlı veri korunması eklendi. Tarayıcıda EN/FR/DE içerik değişimi, büyütme ve Escape kapatma doğrulandı. Yenilemede tablo gövdesinin kaybolması hatası düzeltildi. Sunucu sağlık/kapasite widget’ı RAM toplam/kullanılan/boş, datastore/birim kapasitesi ve ağ kartı MAC alanlarını gösteriyor; eski veri gizleniyor. ESXi fiziksel NIC MAC okuması eklendi; gerçek ESXi bağlantısında doğrulama bekliyor. Disk seri/WWN ve fiziksel RAID sağlığı henüz yok. 43 Python testi ve genişletilmiş UI/dil testleri geçti. Yerel 8767 dosyaları güncel.

- 2026-11-06: Kullanıcının OpManager referansları doğrultusunda ayrı Dashboard modülü: sağlık halkası/ısı haritası, alarm listesi, altyapı özeti, CPU/RAM/disk sıralamaları, port noktaları ve kullanıcı oturumları eklendi. Widget görünürlüğü tarayıcıda saklanıyor. Daha yoğun, düz kurumsal panel stili uygulandı; eski radar ayrı görünümde korundu. 43 Python testi, JS sözdizimi, filtre/dil/dashboard DOM testleri geçti. Yerel 8767 portunda dashboard/i18n HTTP 200 ve 1 güncel açık oturum doğrulandı. Tarayıcı görsel kabulü, tüm metinlerin çevirisi ve otomatik AP keşfi hâlâ eksik. Eski 8766 deneme işlemiyle karışmaması için yeni yerel önizleme adresi http://127.0.0.1:8767/.

- 2026-11-06: Ortak tablolara yenilemede korunan kolon filtreleri eklendi. TR/EN/FR/DE dil seçimi ve ana menü/başlık/temel kontrol katalogları eklendi; tüm uzun yardım/hata metinleri henüz çevrilmedi. Switch kurulum rehberi ve marka/model alanları eklendi. Radar uç bilgisayar/oturum raporlarını ayrı mantıksal grupta gösteriyor; fiziksel ilişki uydurulmuyor. Ajan Ethernet/Wi-Fi türü ve MAC/IP raporluyor; Kablosuz cihazlar bölümünde tüm adaptörler filtrelenebiliyor. Otomatik AP keşfi uygulanmadı. Yerel ajan gerçek bilgisayardan 1 oturum ve hem wired hem wireless adaptör/MAC raporu verdi. 43 Python testi, dil kataloğu ve kolon filtresi dahil DOM kontrolleri geçti. Görsel tarayıcı kabulü bekliyor. Switch kolon filtreleri mevcut sayfa verisi üzerinde çalışır; tüm sayfalara ortak filtre kapsamı sonraki düzeltmedir.

- 2026-11-06: Marka bağımsız profil/destek matrisi ve genel SNMPv3 authPriv okuyucusu/formu eklendi. SHA-256/AES-128; SHA-1 uyumluluk seçeneği; v2c geriye uyumluluk. 42 Python testi ve switch DOM kontrolü geçti. Gerçek cihazla v3 kabulü bekliyor. CONNECTION-PROFILES.md güncel kapsamı açıklar; önceki kayıtlardaki “SNMPv3 henüz yok” notu artık tarihsel durumdur. Linux/iDRAC ve diğer firewall özel API adaptörleri uygulanmış sayılmaz.

- 2026-11-06: Mevcut cihazlar için ESXi/FortiGate/SNMP bağlantı formu, kalıcı kayıtsız salt okunur test ve makine DPAPI korumalı kimlik kaydı eklendi. Yönetici parolası/Origin kontrolü zorunlu; uzak HTTP üzerinden kimlik yapılandırması reddedilir. Başlangıçta korumalı depo yüklenir; yeni ayarlar sonraki kaynak turuna aktarılır. 40 Python testi ve switch DOM kontrolü geçti. Yerel deneme dosyaları güncellendi; gerçek cihaz kimliğiyle ve tarayıcıda form kabulü bekliyor. SNMPv3, ilk kurulum paketi ve sertifika yenileme hâlâ açık işler.

- 2026-11-05: Kurulum ekranına yönetici parolasıyla korunan cihaz ekleme/düzenleme ve ICMP/TCP erişim testi eklendi. Yapılandırma yedeği, atomik kayıt ve canlı toplamada tur başına sabit cihaz listesi uygulandı. Mevcut collector ayarları korunuyor; kimlik bağlı cihazın host değişikliği reddediliyor. 36 Python testi ve switch UI davranış kontrolü geçti. Yerel deneme kopyasına aktarıldı. API/SNMP kimlik formu, tam kurulum paketi ve fiziksel topoloji hâlâ açık işler.

- 2026-11-05: Operasyon ön yüzünde koyu mantıksal izleme radarı, kaynak durumuna bağlı hareketli çizgiler ve tıklanabilir cihaz kartları eklendi. Kart/menü/tablo görsel hiyerarşisi düzenlendi, hareket azaltma ve klavye odak görünürlüğü korundu. Yerel deneme kurulumunun web dosyalarına aktarıldı. JS sözdizimi ve switch DOM testleri geçti; bu değişiklik için görsel tarayıcı kabulü tamamlanmadı. Sonraki iş: kaynak bağlantı düzenleme ve kurulum akışı.

- 2026-11-05: Yönetici panelinde hesap oluşturma, parola yenileme ve devre dışı bırakma; mevcut yönetici parolasıyla yeniden doğrulama, son aktif yönetici koruması ve hesap işlem günlüğü eklendi. Yöneticiye özel Kurulum / Bağlantılar ekranı HTTPS, kaynak ölçümleri, dizin ve uç ajan hazırlığını ve bağlantı gereksinimlerini gösteriyor. Bu ekran yapılandırma değiştiren tam sihirbaz veya Setup.exe değildir. Güvenlik/işlev testleri tests/test_auth_inventory.py içinde. Gerçek tarayıcı kabulü ve müşteri dağıtımı bekliyor.

- 2026-11-05: Ayrı switch ekranı, mantıksal port kutuları, filtre/arama/sıralama/sayfalama; SNMP port açıklaması, yönetim durumu ve yüksek hız alanları eklendi. Node DOM davranış kontrolü geçti. Gerçek switch bağlantısı ve görsel kabul bekliyor. LLDP/FDB, PoE ve SNMPv3 henüz uygulanmadı. SWITCH-MONITORING.md kullanım/sınırları açıklar.

- 2026-11-05: Disk birimi kapasitesi ajan/veri hattı, bilgisayar tablosunda güncel açık kullanıcı ve RAM/disk özetleri, durum/oturum filtreleri, sıralama ve erişim/RAM dashboard bileşenleri uygulandı. 32 Python testi ve JS/PS sözdizimi kontrolleri geçti. Gerçek cihaz ve görsel kabul bekliyor; P0 maddelerinin bütünü tamamlanmadı. Ayrıntılar CHANGES-INVENTORY.md.

- 2026-11-05: Kullanıcının ürünleştirme, global dil, güvenlik, akıllı switch, donanım/oturum envanteri ve dashboard görsel talepleri bu dosyada toplandı. Bu kayıtta yeni uygulama özelliği devreye alınmadı.
