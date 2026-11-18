# CenterEK

CenterEK; bilgisayar, sunucu ve ağ cihazlarının erişilebilirliğini, kaynak kullanımını ve kullanıcı oturumlarını tek panelde izlemek için geliştirilen bir üründür. Sunucu müşterinin ortamına kurulur; panel tarayıcıdan veya bilgisayara yüklenebilen PWA üzerinden açılır.

**Güncel paket: 0.9.2-preview. Henüz satışa hazır son sürüm değildir.** Windows 11 üzerinde temiz kurulum, yükseltme, geri alma ve verileri saklayarak kaldırma testleri geçti. Üretim kod imzası, nihai lisans/sözleşme onayı, dış setup/UAC, kalıcı yeniden başlatma ve Windows Server kabulü açık. Ayrıntılar: [ticari yayın durumu](COMMERCIAL-STATUS.md) ve [test kanıtları](docs/acceptance/0.9.2-preview/README.md).

## Hangi bileşeni kurmalıyım?

| İhtiyaç | Bileşen |
| --- | --- |
| İzleme sistemini kendi ortamınızda çalıştırmak | Windows sunucu setup'ı |
| Hazır bir CenterEK panelini uygulama gibi açmak | PWA paneli |
| Diğer bilgisayarların RAM, disk ve açık kullanıcılarını görmek | Her bilgisayara kayıtlı uç ajanı |
| AD hesaplarını, bilgisayar ve DNS envanterini almak | Yetkili Windows sunucusunda dizin toplayıcısı |
| ESXi, firewall veya switch ölçümlerini almak | Yetkili ESXi/API/SNMP bağlantısı |

PWA kurulumu sunucu veya ajan kurmaz. Ağ keşfi de diğer bilgisayarların kaynak ve oturum bilgilerini tek başına getirmez.

## 1. Windows sunucusunu kurun

### Ön sürümü edinme

Henüz onaylanmış ticari GitHub Release indirmesi sunulmuyor. Test paketi için [GitHub Actions → CI](https://github.com/EnsarKarayel/CenterEK/actions/workflows/ci.yml) sayfasında ilgili commit'in başarılı çalışmasını açın. **Artifacts → `centerek-windows-<commit>`** paketini indirin ve arşivi çıkarın. GitHub oturumu gerekir; bu test çıktıları 14 gün saklanır. Başarılı CI, ticari yayın onayı değildir.

Arşivdeki `CenterEK-Setup-0.9.2-preview-win-x64.exe` tek dosya yükleyicidir. Yanındaki SHA256 dosyasıyla bütünlüğünü kontrol edebilirsiniz. Mevcut ön sürüm imzasızdır; hash yayıncı kimliğini doğrulamaz. Güvenlik yazılımını veya kurum politikalarını kapatmayın.

### Kurulum adımları

1. Windows x64 bilgisayarda setup'ı açın ve yönetici iznini verin. **Hedef bilgisayara Python veya pip kurmanız gerekmez.** Windows 11 temiz Sandbox testi geçti; Windows 10 ve Server 2019+ hedeflerinin ayrı kabulü tamamlanmalıdır. Server 2012 R2 bu setup için doğrulanmış hedef değildir.
2. Dili ve yeni, boş bir kurulum klasörünü seçin. İlk CenterEK yönetici hesabını ve parolasını oluşturun.
3. Erişimi seçin: yalnızca bu bilgisayar veya özel LAN adresi. LAN firewall izni isteğe bağlıdır ve Private/Domain profillerine sınırlıdır. Program internet/modem portlarını otomatik açmaz.
4. Otomatik HTTPS sertifikası ve Windows CA güveni seçimini inceleyin. Ön sürümün otomatik kurulum akışı seçilen panel adları/IP'leri için makine sertifika deposuna güven ekler.
5. İsterseniz bu bilgisayarın ölçüm ajanını ve bağlı yerel ağ keşfini seçin. AD toplayıcısını yalnızca AD modülü ve gerekli okuma yetkileri bulunan bilgisayarda seçin.
6. Kurulum sonunda **Paneli aç** düğmesine basın ve oluşturduğunuz CenterEK hesabıyla giriş yapın. Sunucu ve seçilen yerel ajanlar SYSTEM zamanlanmış görevleriyle arka planda çalışır.
7. Panelin **Kurulum / Bağlantılar** bölümünden cihazları ve yetkili kaynak bağlantılarını ekleyin. Her kaynakta son ölçüm zamanını kontrol edin.

Tam seçenekler ve günlükler: [Windows kurulumu](INSTALLATION.md). LAN/VPN/HTTPS ters proxy seçenekleri: [uzaktan erişim](REMOTE-ACCESS.md).

## 2. Paneli bilgisayarınıza uygulama olarak yükleyin

1. PWA dosyaları yayınlanmış CenterEK sunucunuzun `https://PANEL-ADRESINIZ/panel/` adresini Edge'de açın. HTTPS sertifikasının tarayıcı tarafından güvenilir olması gerekir.
2. **Panel uygulamasını yükle** düğmesini veya adres çubuğundaki yükleme simgesini kullanın. Menüde **Bu siteyi uygulama olarak yükle** seçeneğini de kullanabilirsiniz; menü konumu tarayıcı sürümüne göre değişebilir.
3. Uygulamayı Başlat menüsünden açın, **Paneli aç** düğmesini seçin ve CenterEK hesabınızla giriş yapın. Ortamınız Microsoft/kurum girişi kullanıyorsa önce o giriş görünür.

Mevcut yetkili pilot ortam: [Azure PWA paneli](https://centerek-browser.wonderfulocean-51ea5b45.swedencentral.azurecontainerapps.io/panel/). Bu adres genel müşteri barındırma veya herkese açık demo hizmeti değildir; erişim yetkisi gerekir.

PWA aynı sunucunun panelini açar. Çevrimdışıyken yalnızca bağlantı hata ekranı gösterilir; kullanıcı, cihaz, rapor ve oturum verileri çevrimdışı önbelleğe alınmaz. Microsoft Store kaydı PWA'yı tarayıcıdan yüklemek için gerekmez.

**Paket sürümü ayrımı:** PWA kaynakları güncel derlemeye dahil edilir; daha önce üretilmiş 0.9.2 ön sürüm EXE'sine geriye dönük eklenmez. Azure pilotunda PWA ayrı HTTPS geçidi üzerinden yayınlanmıştır. Yayın ve dağıtım ayrıntıları: [PWA paneli](STORE-PANEL.md).

## 3. Bilgisayar ve cihaz verilerini bağlayın

- **Windows bilgisayarlar:** [Ajan kurulum rehberi](AGENT-SETUP.md) ile her bilgisayarı ayrı kaydedip uç ajanını kurun. Güncel RAM, disk ve açık kullanıcı oturumları bu raporlardan gelir.
- **Linux sunucular:** [Linux ajanı](LINUX-AGENT.md) ile yerel ölçümleri gönderin.
- **AD ortamı:** Dizin toplayıcısı hesap/bilgisayar envanteri sağlar. AD son oturum bilgisi, o anda açık kullanıcı veya çevrimiçi bilgisayar kanıtı değildir. [İşletim rehberi](OPERATIONS.md) ve [yönetici için domain dağıtım araçları](DOMAIN-ROLLOUT.md) ayrıca incelenmelidir. Domain rehberindeki ofis IP/adları pilot örnekleridir; müşteriye özel hazırlık gerekir.
- **ESXi, FortiGate ve switch:** İlgili bağlantıya okuma yetkili hesap/API/SNMP bilgilerini ve güvenilen sertifikayı tanımlayın. Canlı cihaz uyumluluğu ayrıca doğrulanmalıdır.

Başarılı kurulumdan sonra panelde bilgisayar adı, rapor zamanı, RAM/disk ve beklenen kullanıcı oturumunu karşılaştırın. Eski rapor güncel ölçüm sayılmaz. Erişilebilir cihaz, bütün donanım ölçümleri alınmış cihaz anlamına gelmez.

## Yükseltme, geri alma ve kaldırma

Yeni setup'taki **Yükselt / Geri al / Kaldır** ekranından mevcut paket kurulumunu seçin. Yükseltme öncesinde uygulama, veritabanı, ayar, sertifika ve görev yedekleri doğrulanır. **Geri alma, aktif veritabanını yedek tarihine döndürür; sonraki ölçüm ve değişiklikler geri alınır.**

**Kaldır · verileri sakla** seçeneği müşteri verilerini ve yedekleri korur. Diğer bilgisayarlardaki ajanlar ayrıca yönetilir. Kaynak kodla çalışan eski kurulumlar otomatik olarak bu bakım akışına dönüşmez. Kurtarma ve veri koruma ayrıntıları: [bakım rehberi](MAINTENANCE.md).

## Abonelik ve satış durumu

Planlanan satış modeli yıllık aboneliktir. Ticari lisans uygulaması, süre dolunca yeni ölçüm/keşif ve ajan raporu kabulünü durdurur; geçmiş verileri okumayı ve CSV dışa aktarmayı korur. Yenileme, kurulum kimliğine bağlı imzalı lisans dosyasıyla yapılır. **Mevcut ön sürüm ücretli ticari lisansla yayımlanmış ürün değildir.**

[Lisans mekanizması](LICENSING.md), [kod imzalama hazırlığı](CODE-SIGNING.md) ve [satış öncesi kalan işler](COMMERCIAL-STATUS.md) ayrı belgelenmiştir. PWA'nın yayınlanması, bağımsız sunucu/ajan setup'ının imzalanması veya satış kabulünün tamamlanması anlamına gelmez.

Destek: **karayelensar@gmail.com**. Kurulum ve ekran sorunlarını sürüm, hata metni ve kişisel verilerden arındırılmış ekran görüntüsüyle iletebilirsiniz. Parola, ajan anahtarı, sertifika özel anahtarı veya tam yedek göndermeyin. Sürekli sistem yönetimi ve SLA taahhüdü bulunmaz.

## Geliştiriciler ve mevcut kaynak kurulumları

Yukarıdaki müşteri setup'ı kaynak kod kurulumundan ayrıdır. Kaynaktan çalıştırma için Python 3.11+, [bağımlılıklar](requirements.txt), ilk panel hesabı ve HTTPS/yerel ayarlar gerekir. Ayrıntılı komutlar [OPERATIONS.md](OPERATIONS.md), kalıcı görev dönüşümü [UNATTENDED.md](UNATTENDED.md) içindedir. Yerel config, data, sertifikalar ve ajan kimlikleri Git'e alınmamalıdır.

Windows paket üreticisi [build_windows.py](build_windows.py), ürün kapsamı [PRODUCT.md](PRODUCT.md) ve otomatik doğrulamalar [CI](.github/workflows/ci.yml) içindedir. Gerçek müşteri ortamı kabulü otomatik testlerden ayrı tutulur. Bu depoya açık kaynak lisansı atanmış değildir; üçüncü taraf bileşenlerin lisansları ayrıca geçerlidir.
