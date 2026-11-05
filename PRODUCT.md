# CenterEK ürün planı

## Ürün kararı

Hedef: 1–5 lokasyonu olan, ayrı bir izleme ekibi bulunmayan işletmeler ve bu işletmelere hizmet veren BT firmaları. İlk açılışta “Hangi sorun öncelikli, hangi cihazlar etkileniyor, önce neyi kontrol etmeliyim?” sorularına yanıt veren Türkçe, yerinde çalışan altyapı izleme ürünü.

Bu konumlandırma ticari bir hipotezdir; satış kolaylığı veya pazar talebi doğrulanmış değildir. İlk müşteri pilotlarıyla kurulum süresi, sorun tespit süresi, yanlış alarm oranı ve ödeme isteği ölçülmelidir.

## Referans ürünlerden alınan kararlar

| Ürün | Referans özellik | CenterEK kararı |
|---|---|---|
| [PRTG](https://www.paessler.com/manuals/prtg/auto-discovery) | Keşif ve cihaz şablonlarından sensör oluşturma | Keşif sonuçları, takip edilen cihazlar ve kaynak sensörleri ayrı tutulur; cihaz profilleri hazırlanır. |
| [PRTG bağımlılıklar](https://www.paessler.com/manuals/prtg/dependencies) | Üst sensör arızasında bağlı kontrolleri yönetme | Önce kullanıcı tanımlı ilişkilerle etki açıklaması; ileride doğrulanmış ilişkiler ve alarm bastırma. |
| [OpManager](https://www.manageengine.com/tr/network-monitoring/) | Ağ ve sunucu izleme; topoloji görünürlüğü | Cihaz ayrıntılarında portlar ve sunucu kaynakları; fiziksel topoloji yalnızca LLDP/CDP/FDB kanıtıyla. |
| [Zabbix](https://www.zabbix.com/features) | Şablonlar, geçmiş, keşif ve uyarılar | Modüler okuyucular, kalıcı zaman serileri, ölçüm yaşı ve ayrı hata durumları. |
| [NinjaOne](https://www.ninjaone.com/rmm/snmp-monitoring/) | Uç nokta ve SNMP altyapısını ortak yönetimden izleme | İleride müşteri başına yerel toplayıcı; ilk pilot tek müşteri ve tek lokasyon. |
| [SolarWinds NetPath](https://www.solarwinds.com/network-performance-monitor/use-cases/netpath) | Yol boyunca görünürlük ve sorun yerini daraltma | İnternet teşhisinde gateway, dış erişim ve DNS ayrı kontroller olacak. Traceroute tek başına NetPath eşdeğeri sayılmayacak. |
| [Auvik](https://www.auvik.com/network-management-software/network-mapping-software/) | Güncellenen ağ haritası ve cihaz bağlamı | Harita, portlar, trafik ve olaylar aynı cihaz ayrıntısında birleşecek. Konfigürasyon yedeği sonraki aşama. |

Arayüzler, logolar ve ürün kodları kopyalanmaz; genel iş akışlarından yararlanılır.

## Ekran düzeni

1. Genel durum: Öncelikli sorun, etkilenen cihaz, kanıt, önerilen kontrol ve ölçüm zamanı.
2. Cihazlar: IP/isim araması; erişim ve kaynak sağlığı birbirinden ayrı; ayrıntıda geçmiş, depolama ve port tablosu.
3. Ağ keşfi: Bulunan IP ve yanıt veren servisler. Kimliği doğrulanmayan cihaz işletim sistemi veya üretici olarak etiketlenmez.
4. Kesintiler: Başlangıç, doğrulama, geri dönüş ve süre.
5. Sonraki aşama: doğrulanmış ağ haritası, bildirim kuralları, müşteri/lokasyon seçimi, kurulum sihirbazı.

## 0.5 uygulama durumu

Kullanıcı oturumundan bağımsız SYSTEM görev kurulumu, açılış/kurtarma tetikleyicileri, işlem sarmalayıcısı, dönen günlükler ve arka plan kimlik saklama eklendi. Yeni modern canlı görünüm gerçek ölçüm zamanlarını gösterir; uç ajan varsayılanı 15 saniyedir. Bunlar kod ve yerel test kapsamındadır; hedef sunucuların SYSTEM görevleri ve yeniden başlatma testleri kurulumda tamamlanmalıdır. UNATTENDED.md bu dönüşümü açıklar.

## 0.4 uygulama durumu

HTTPS ajan alımı, bilgisayara/kaynak türüne bağlı iptal edilebilir anahtarlar, DPAPI istemci ayarı, yerel IP/CPU/RAM raporları ve kaynak geçmişi eklendi. AD raporlaması aynı protokol üzerinden ayrıca çalışabilir. Mevcut kullanıcı oturumuna bağlı zamanlanmış görev betiği hazırlandı; sistem servisi/çok kullanıcılı ajan dağıtımı tamamlanmış değildir. Bu sürümün gerçek ağ dağıtımı ayrıca yapılmalıdır. Kurulum AGENT-SETUP.md içindedir.

## 0.3 uygulama durumu

0.3 ile yerel panel hesapları, korumalı API/raporlar, sol menü ve kategori tabloları, FortiGate kaynak/envanter sorguları, AD/DHCP/DNS dışa aktarımı ve Windows WTS oturum sorgulama/paneli eklendi. Bu veri kaynaklarının gerçek müşteri ortamında bağlantı doğrulaması ayrı bir pilot adımıdır. Güncel kurulum ve sınırlar OPERATIONS.md içindedir. Otomatik dağıtım, SNMPv3, fiziksel topoloji, bildirim ve ticari yayın doğrulaması aşağıdaki yol haritasında kalır.

## Sürümler ve kabul ölçütleri

### 0.2 — Bu geliştirme

- Aralığı kullanıcı tarafından belirtilen, en fazla 1024 adreslik keşif. Aktif yapılandırmayı değiştirmez.
- 24 saatlik erişim ve kaynak grafikleri; 30 günlük ölçüm saklama.
- Başarılı kontrol oranı, ölçüm sayısıyla gösterilir. Kesintisiz SLA yüzdesi iddiası yoktur.
- ESXi okuyucusu: CPU, RAM, uptime, donanım özeti, datastore.
- FortiGate deneysel okuyucusu: sistem kimliği ve arayüz sayaçları; FortiOS yanıtıyla pilot doğrulama gerekir.
- SNMPv2c okuyucusu: IF-MIB port durumu, 64-bit trafik sayaçları ve hata sayaçları; 128 port sınırı. SNMPv3 henüz yoktur.
- Ölçülen uyarılar, cihaz araması, CSV durum raporu ve yerel bağlantı sihirbazı.
- Okuma parolaları/API tokenları API çıktısına, dosyaya veya Git'e yazılmaz. Başlangıçta yerel terminalden girilir.

Kabul: önceki veritabanı korunarak açılış; eşik/geri dönüş/sayaç sıfırlanması/gizli veri sızıntısı testleri; gerçek ortamda ayrı bağlantı doğrulaması.

### 0.3 — İşletme pilotu

- SNMPv3, Dell iDRAC Redfish sensörleri, Linux ve Windows kaynak toplayıcıları.
- LLDP/CDP, bridge FDB ve ARP verilerini birleştiren doğrulanmış switch-port eşleştirmesi. Keşif dışındaki ağlar ve VLAN'lar ayrıca tanımlanır.
- Kullanıcı onaylı dependency ağacı, bakım aralıkları, ardışık ölçüm tabanlı kaynak alarmları, SMTP ve webhook bildirimleri, alarm teyidi.
- Windows servis kurulumu, servis sağlığı, yeniden başlatma, yedekleme ve veri geçişi.
- İnternet için gateway/dış erişim/DNS ayrımı. WAN kullanımı kapasite hız testinden ayrı gösterilir.

Kabul: elektrik/ağ/servis kesintisi denemeleri; bildirim ve geri dönüş teslimi; yerel toplayıcı durduğunda harici gözlemci alarmı.

### 1.0 — Ticari yayın

- Kimlik doğrulama, roller, TLS, denetim kaydı, işletim sistemi destek matrisi, şifreli secrets deposu.
- İmzalı kurulum, güvenli güncelleme/geri alma, otomatik yedekleme, saklama politikası, lisans/abonelik ve üçüncü taraf lisans bildirimleri.
- Müşteri izolasyonu kanıtlanmadan çok müşterili barındırma sunulmaz.
- Gerçekçi cihaz sayısında yük testi, güvenlik incelemesi, destek ve kurtarma belgeleri.

Mevcut Python 3.11.9 / Windows Server 2012 R2 kurulumu kullanıcı tarafından çalışır olarak gösterildi. Bu, satış için desteklenen platform matrisi veya güvenlik onayı değildir.

## Satış ve paketleme hipotezi

İlk teklif: ücretli kurulum + yıllık yazılım ve destek; sunucu/ağ cihazı ve lokasyon sayısı üzerinden anlaşılır paket. Erişim, kesinti geçmişi ve temel raporlar tüm paketlerde bulunur. Port başına ücretin müşteri açısından karmaşıklığı pilotta değerlendirilir. Fiyatlar, müşteri görüşmeleri ve destek maliyeti ölçülmeden belirlenmez.

İlk demo senaryosu: cihazları bul → bir Dell ve bir switch bağla → kesinti oluştur → öncelikli sorunu göster → port/kaynak geçmişiyle incele → raporu indir. Yalnızca gerçek bağlantıyla doğrulanmış özellikler satılır.
