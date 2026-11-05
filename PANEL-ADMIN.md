# Panelden hesap yönetimi ve bağlantı hazırlığı

Panel kullanıcıları ekranında yönetici hesap oluşturabilir, parolasını yenileyebilir veya devre dışı bırakabilir. Bu işlemler AD hesaplarını değiştirmez.

Her işlem mevcut yöneticinin parolasıyla yeniden doğrulanır. Başarısız doğrulamalar giriş deneme sınırına tabidir. Yeni parolalar 12–256 karakter olmalıdır. Son aktif yönetici kapatılamaz. Parolası değiştirilen veya kapatılan hesabın mevcut oturumları sonraki istekte reddedilir. Başarılı işlemlerde account_audit tablosuna zaman, aktör, işlem ve hedef yazılır; parolalar kayda alınmaz. Kapsamlı değiştirilemez denetim sistemi bu sürümün kapsamı değildir.

Kurulum / Bağlantılar ekranı yalnızca yöneticilere açıktır. Mevcut HTTPS bağlantısını, kaynak ölçümlerini, AD/dizin verisini ve uç ajan güncelliğini gösterir. Kaynak bağlantıları için gereken bilgiler açıklanır. Bu ekran henüz cihaz ekleyen sihirbaz değildir ve ağ/erişim ayarlarını değiştirmez. HTTPS göstergesi bu bağlantının TLS kullandığını belirtir; sertifika dağıtımı veya internet yayın güvenliği sertifikasyonu değildir.

API uçları aynı Origin kontrolü ve mevcut oturum yetkisiyle korunur. POST /api/accounts işlemlerinde parola tekrar doğrulaması da gerekir. Setup.exe/MSI, dört dil, kaynak bağlantı editörü, MFA ve tam kurulum sihirbazı PRODUCT-BACKLOG.md içinde açık işlerdir.

## Cihaz erişim kontrolleri

Kurulum ekranındaki cihaz formu ICMP/TCP erişim hedefi ekler veya aynı cihaz kodunun ayarlarını günceller. Yeni cihaz kodu benzersiz seçilmeli; mevcut cihaz düzenlemek için listeden seçilmelidir. İşlem mevcut yönetici parolasıyla doğrulanır. Bağlantı testi yalnızca erişim kontrolüdür; uygulama sağlığı, API hesabı veya SNMP kimliği doğrulaması değildir.

Kaydetme önce config.backup.local.json yedeğini alır, yeni ayarı atomik olarak kaydeder ve sonraki toplama turuna aktarır. Kimlik bilgisi bağlı kaynaklarda host değişikliği bu formdan engellenir; mevcut collector ayarları korunur. API/SNMP kimlik bilgisi formu henüz yoktur. Cihaz silme bu ekranda uygulanmamıştır.
