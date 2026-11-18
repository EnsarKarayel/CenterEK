# CenterEK bakım işlemleri

Windows x64 paket sürümü 0.9.2-preview; yükseltme, geri alma ve veri saklayan kaldırma içerir. Windows 11 temiz Sandbox ortamında 0.9.1 → 0.9.2 yükseltme, geri alma, kaldırma ve aynı hesapla geri kurma geçti; [kabul kanıtları](docs/acceptance/0.9.2-preview/README.md) paylaşılmıştır. Kaynak koddan çalıştırılan eski ofis kurulumu bu akışa otomatik alınmaz. Kalıcı yeniden başlatma, dış setup/UAC ve Windows Server kabulü henüz tamamlanmadı.

## Kullanım

Yeni setup dosyasını açın; **Yükselt / Geri al / Kaldır** düğmesine basıp mevcut kurulum klasörünü seçin. 0.8.0 ile yeni kurulan ürün Windows **Yüklü uygulamalar → CenterEK → Kaldır** üzerinden de bakım ekranını açar. Yönetici izni gerekir. Geri alınan eski sürüm bakım özelliğini içermese de korumalı alanda saklanan bakım aracı kullanılabilir.

- **Yükselt:** Yalnızca daha yeni paket kabul edilir. CenterEK görevleri durdurulur; uygulama, veritabanı, sertifikalar, ayarlar, ajan kimlikleri ve görev tanımları yedeklenir. Yedek veritabanının `quick_check` sonucu ve dosya SHA256 değerleri doğrulanır. Program dosyaları değiştirilir; hesaplar ve ayarlar yeniden oluşturulmaz. Görevler önceki etkinlik durumlarıyla geri kaydedilir. HTTPS giriş ekranı hazır olmazsa eski program ve veritabanı geri yüklenir.
- **Geri al:** Son yükseltmeden önceki yedeğe döner. Önce mevcut durum da yedeklenir. **Yedek tarihinden sonraki ölçümler, yeni hesaplar ve ayar değişiklikleri geri alınır.** Başarısız geri almada işlem öncesi durum geri yüklenir.
- **Yarım kalanı kurtar:** İşlem kapanma/elektrik kesintisi nedeniyle yarıda kalmışsa yeni setup'tan bu seçeneği kullanın. Başka bakım işlemleri, bekleyen kurtarma kaydı çözülene kadar engellenir. Henüz dosya değişikliği başlamadıysa görevler yeniden açılır; değişiklik başladıysa doğrulanmış yedek geri yüklenir. Yeni ölçümler yedek tarihine dönebilir.
- **Kaldırılanı geri kur:** Veri saklanarak kaldırılmış kurulum, kaldırma öncesi yedekten geri yüklenir. Hesaplar yeniden oluşturulmaz. Saklanan klasörde sonradan yapılan değişiklikler yedek tarihindeki duruma döner; yerinden alınan dosyalar ayrıca korunur.
- **Kaldır · verileri sakla:** Bu klasöre ait üç SYSTEM görevi ve yönetilen program dosyaları kaldırılır. Veritabanı, `data/`, `certs/`, yerel ayarlar ve yedekler saklanır. Windows uygulama kaydı ve eşleşen panel kısayolu kaldırılır. Diğer bilgisayarlardaki ajanlar bu işlemle kaldırılmaz. Güvenilen CA sertifikası ve mevcut firewall kuralı korunur; kurum yöneticisi başka ajanların kullanmadığını doğruladıktan sonra ayrıca temizlemelidir. Kalıcı müşteri verisi silme bu sürümde sunulmaz.

## Koruma ve kurtarma

Yedekler `%ProgramData%\CenterEK-Maintenance\<kurulum-kimliği>\<yedek-kimliği>` altında mevcut yönetici, SYSTEM ve yerel yöneticilere sınırlı izinlerle tutulur. Yedekler parola özeti, sertifika anahtarı ve makineye bağlı şifreli ajan ayarları içerebilir; destek kaydına veya GitHub'a yüklemeyin. Bu yedekler aynı Windows makinesinde kurtarma içindir; DPAPI verileri başka makineye taşınarak kullanılamaz.

İşlem yalnızca seçilen klasöre ait doğrulanmış görev/işlemleri durdurur. SQL Server, başka Python süreçleri ve başka klasöre ait CenterEK görevleri değiştirilmez. Junction/symlink, başka kuruluma ait görev, yetersiz boş alan, bozuk veritabanı veya değiştirilmiş yedek tespit edilirse işlem durur. Eşzamanlı iki bakım işlemi engellenir. Yer değiştiren dosyalar `displaced-*` klasörlerinde saklanır; otomatik yedek silme yoktur. Disk kullanımını yönetici takip etmelidir.

## Yayın kabul listesi

- [ ] Python olmayan Windows 11 / Server 2019+ temiz kurulum ve Windows Kaldır ekranı.
- [ ] 0.7 → 0.8 yükseltme; aynı yöneticiyle giriş, cihaz/ajan anahtarları ve geçmiş ölçümler.
- [ ] Gerçek SYSTEM görevleriyle oturum kapalıyken yükseltme ve sonraki yeniden başlatma.
- [ ] HTTPS başlangıcı başarısız sürümde otomatik eski sürüme dönüş.
- [ ] Geri alma ve yedek tarihinin kullanıcıya gösterilmesi.
- [ ] Setup kapatılması/elektrik kesintisi ardından yeni setup ile kurtarma.
- [ ] Veri saklayan kaldırma; görevlerin kalkması ve diğer uygulamaların etkilenmemesi.
- [ ] Kod imzalama, bağımsız güvenlik incelemesi ve üçüncü taraf lisans kontrolü.

Otomatik testler bu listeyi gerçek müşteri ortamında tamamlanmış saymaz. Ön sürüm satışa hazır sürüm olarak etiketlenmez.
