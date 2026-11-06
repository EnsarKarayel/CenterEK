# Kolon filtreleri, dil seçimi ve bağlantı görünürlüğü

## Son güncelleme

Widget başlığının sağındaki büyütme düğmesi aynı kutuyu büyük bir görünümde açar; veri yenilenmesi devam eder. Kapat düğmesi, Escape veya arka plan tıklamasıyla kapanır; klavye odağı açan düğmeye döner. Görünüm değişince açık kutu kapanır. TR/EN/FR/DE seçimi SVG bayrak düğmeleriyle yapılır; cihaz adları, kullanıcı kimlikleri ve adresler korunur. Dashboard açıklamaları, durumlar ve dinamik kayıt sayaçları da çevrilir; yardım/üretici metinlerinin tamamı henüz kapsanmış değildir.

Tema paletteki HEX değerlerini kullanır: Iguana Green #73B682, Blue-Gray #62A8CB, Deep Saffron #FF9933, Dark Slate Gray #2A4954, Raisin Black #272626. Kritik durum kırmızısı anlam ayrımını korumak için ayrıca kullanılır.

Sunucu sağlık ve kapasite widget’ında erişim ve kaynak sağlıkları ayrıdır. RAM boşluğu yalnızca geçerli toplam/kullanılan değerlerinden hesaplanır. ESXi datastore veya işletim sistemi birimleri kaynak etiketiyle gösterilir. Ajan eşleştirmesi yalnızca güncel, aynı IP'yi tekil raporlayan bilgisayar varsa yapılır; bunun fiziksel sunucu olduğu varsayılmaz. ESXi’de NIC MAC bilgisi okunabilir; disklerin MAC adresi yoktur. Fiziksel disk seri/WWN/RAID okuyucusu henüz uygulanmadı.

Dashboard ayrı bir modüldür ve varsayılan giriş görünümüdür. Sekiz widget gerçek kaynak ölçümlerini gösterir: erişim sağlığı, uyarılar, altyapı tür özeti, CPU, RAM, disk, portlar ve oturumlar. CPU/RAM sıralaması yalnızca güncel sayısal ölçümleri kullanır. Uyarı halkası mevcut kuralların sonucudur, tüm güvenlik/donanım sorunlarının taraması değildir. Widget seçimi tarayıcıda saklanır; sunucuya veya farklı kullanıcı/tarayıcılara otomatik eşitlenmez. Cihaz sıralamaları son gözlenen ölçümlerdir, min/max/ortalama olarak sunulmaz. Radardaki uç bilgisayarlar fiziksel switch ilişkisi doğrulanana kadar ayrı gruptadır.

Giriş ve panelde Language seçimi: Türkçe, English, Français ve Deutsch. Tercih tarayıcıda saklanır. Ana menüler, temel durumlar, birçok tablo başlığı ve ana kontroller çevrilmiştir. Tüm yardım metinleri, dinamik mesajlar ve hata açıklamaları henüz çevrilmemiştir; tam dört dil kabulü tamamlanmadı. Tarih/sayı biçimleri panel yardımcılarında seçilen dile uyar; canlı akışın bazı tarih alanları hâlâ Türkçe biçim kullanır.

Tablo başlıklarının altında her kolon için metin filtresi vardır. Filtreler AND ilişkisiyle uygulanır, aynı başlıklı tablo yenilendiğinde korunur. Switchlerde üst arama/durum filtresi tüm portlara, kolon filtreleri mevcut sayfaya uygulanır; bu kapsam ürün kabulünde ayrıca genişletilecektir.

Kablosuz cihazlar ekranı ajanların aktif ağ kartlarını listeler. Filtreyle tüm bağlantılar, Wi-Fi, Ethernet veya diğer türler seçilebilir. Her satır adaptör adı, IP, MAC, rapor yaşı ve bilgisayarı gösterir. Ethernet türü sanal adaptörleri içerebilir. Aynı bilgisayarın kablolu ve kablosuz adresleri ayrı satırlardır. Birincil trafik yolu ve fiziksel switch portu bu veriden çıkarılmaz.

Eski ajan betikleri MAC veya bağlantı türü göndermez; yeni Collect-EndpointSessions.ps1 sürümü uç bilgisayarda çalışmalıdır. Güncel olmayan rapordan açık kullanıcı gösterilmez; stale etiketi korunur. Radar uç bilgisayarları ve güncel oturumları ayrı grupta gösterir. Fiziksel üst bağlantı ancak LLDP/FDB gibi kaynaklarla doğrulanınca eklenecektir.

Switch kurulum rehberi Kurulum / Bağlantılar ekranındadır. Önce cihaz türü Switch, yönetim IP'si ve isteğe bağlı marka/model; ardından ölçüm profili seçilir. Kullanıcının marka/modeli sağlanmadan switche yönelik aktif test veya cihaz yapılandırma değişikliği yapılmadı.

AP/controller entegrasyonu ve otomatik AP keşfi henüz yoktur; ekrandaki AP listesi yalnızca tanımlı cihazları içerir. Ajan Wi-Fi listesi tüm kablosuz istemcileri kapsamaz.
