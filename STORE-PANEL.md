# CenterEK Panel — Microsoft Store hazırlığı

Panel uygulaması mevcut CenterEK HTTPS sunucusundaki arayüze bağlanan PWA'dır. Sunucu/ajan kurmaz, SYSTEM görevi veya firewall kuralı oluşturmaz; bu bileşenler mevcut bağımsız setup'ta kalır. Sunucudaki yetkiler mevcut CenterEK hesabıyla belirlenir; panelin PWA olarak açılması kullanıcının rolünü değiştirmez.

## Geliştirilen ilk sürüm

- `/panel/`: kurulum düğmesi destekleyen tarayıcılarda PWA yükleme, mevcut panele geçiş ve yardım bağlantıları.
- Web app manifesti; 192/512 PNG ve SVG ürün simgeleri; kullanıcının verdiği renk paleti.
- `/panel-worker.js`: yalnızca genel bağlantı-hata ekranını önbelleğe alır. Panel, login, API, rapor, parola veya oturum yanıtları Cache Storage'a yazılmaz. API/kimlik sağlayıcısı istekleri ve POST istekleri ele alınmaz. Başka uygulamaların önbellekleri silinmez.
- Teknik gizlilik açıklaması ve e-posta destek sayfası. Gizlilik metni nihai satış/yayın onayı değildir.
- Sunucudaki sabit dosya listesi yalnızca bu genel PWA dosyalarını anonim sunar; mevcut API/oturum kontrolleri korunur. Azure Entra ağ geçidinin erişim kapsamı değiştirilmedi.

İlk kapsam aynı origin'dir: `https://MUSTERI-PANELI/panel/` içinden `https://MUSTERI-PANELI/` açılır. Tarayıcıda sertifika zincirine güvenilmiş olmalıdır. Tek bir Store paketi otomatik olarak bütün müşteri sunucularına bağlanacak bir bağlantı yöneticisi değildir. Farklı origin'e yönlendirmelerde Windows/PWA güvenlik arayüzü görülebilir; kimlik sağlayıcısı ekranlarını iframe içine alma veya sertifika kontrollerini atlatma yoktur.

## Kaynak ve web dağıtım çıktısı

Kaynak sunucunun yeni sürümünde `/panel/` açılabilir. Windows build'i `web/panel` dosyalarını pakete alır. Eski 0.9.2 ikilisine bu dosyalar geriye dönük eklenmiş değildir; canlı Azure/ofis sunucusu bu geliştirmeyle yükseltilmedi.

Yalnızca genel web dosyalarını üretmek için:

```powershell
python scripts/store/build_panel.py --output data/store-panel/YENI-KLASOR --origin https://PANEL-ADRESI
```

Çıktı `public/` altındaki sabit dosyalar, SHA256 listeli `preparation-report.json` ve `CenterEK-Panel-Web.zip` içerir. ZIP bir Windows kurulum veya MSIX paketi değildir. Komut ağ isteği veya dağıtım yapmaz, mevcut klasörü ezmez ve `store_ready:false` kaydeder. Genel dosyalar aynı HTTPS origin'inde yayınlanır; ana `/` yolu mevcut CenterEK paneline gider. Salt statik hosting tek başına çalışan bir CenterEK backend'i oluşturmaz. Manifest MIME türü `application/manifest+json`, worker JavaScript MIME türü olmalı; worker root konumundan sunulmalıdır. Panel ve API yanıtlarında `no-store` korunur.

## Azure ve Store'a geçişte kalanlar

1. Partner Center Windows geliştirici hesabı açılır; ürün adı rezerve edilir. `Package ID`, `Publisher ID` ve `Publisher display name` buradan alınır; uydurulmaz.
2. Üretim/review HTTPS ortamında genel PWA dosyalarının erişimi hazırlanır. Mevcut staging tüm yolları Entra arkasında tutuyor; PWABuilder bu korumalı manifesti anonim okuyamayabilir. Sadece gerekli sabit dosyalar için sınırlı bir yayın planı ayrıca uygulanıp doğrulanmalı; `/api`, dashboard veya Entra genel olarak anonim açılmamalı. Mevcut gateway yayın kontrolü istisnasız auth kapsamı bekler; bu kontrol gevşetilmedi.
3. Üretim verisinden ayrı inceleme ortamı ve test hesabı hazırlanır. Mevcut yalnızca ürün sahibine açık staging, Microsoft inceleme erişimi yerine geçmez. Microsoft/Entra ve CenterEK oturum açma/çıkma, CSV indirme, pencere boyutları ve bağlantı kesilmesi gerçek paketle test edilir.
4. Veri sorumlusu ve tam iletişim bilgileriyle nihai gizlilik ve destek URL'leri belirlenir; mevcut açıklamadaki ön sürüm uyarısı nihai metin onayı olmadan kaldırılmaz. Mağaza açıklaması ayrı sunucu/ajan ihtiyacını başta belirtir.
5. [Microsoft'un PWA yayın akışı](https://learn.microsoft.com/en-us/microsoft-edge/progressive-web-apps/how-to/microsoft-store) izlenir: yayınlanan URL PWABuilder ile değerlendirilir, gerçek Partner Center kimlikleriyle Windows paketi üretilir. Bu geliştirmede PWABuilder'a gönderim veya MSIX üretimi yapılmadı.
6. WACK ve gerçek Windows kurulum/giriş testleri geçtikten sonra paket ve mağaza bilgileri incelemeye gönderilir. Microsoft kabulünden önce Store'da yayınlanmış veya ücretsiz imzalanmış ürün iddiası yoktur. İmza bu Store paketine aittir; bağımsız sunucu/ajan EXE'lerine aktarılmaz.

## Doğrulama

`tests/test_panel_app.py` anonim sabit dosyaları/MIME türlerini, API korumasını, dosya sınırını, PNG boyutlarını ve web dağıtım çıktısını kontrol eder. `node tests/test_panel_worker.cjs` canlı özel navigasyonun önbelleğe yazılmadığını, offline dönüşünü ve auth/API/cross-origin istisnalarını çalıştırır. Bu testler gerçek Entra giriş veya Store kabulü değildir.
