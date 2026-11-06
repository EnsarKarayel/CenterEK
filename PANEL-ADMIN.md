# Panelden hesap yönetimi ve bağlantı hazırlığı

Güncel marka bağımsız destek ve SNMPv3 ayarları için CONNECTION-PROFILES.md dosyasına bakın. SNMPv3 bu güncellemede eklendi; aşağıdaki önceki sürüm notları tarihsel sınırlardır.

Panel kullanıcıları ekranında yönetici hesap oluşturabilir, parolasını yenileyebilir veya devre dışı bırakabilir. Bu işlemler AD hesaplarını değiştirmez.

Her işlem mevcut yöneticinin parolasıyla yeniden doğrulanır. Başarısız doğrulamalar giriş deneme sınırına tabidir. Yeni parolalar 12–256 karakter olmalıdır. Son aktif yönetici kapatılamaz. Parolası değiştirilen veya kapatılan hesabın mevcut oturumları sonraki istekte reddedilir. Başarılı işlemlerde account_audit tablosuna zaman, aktör, işlem ve hedef yazılır; parolalar kayda alınmaz. Kapsamlı değiştirilemez denetim sistemi bu sürümün kapsamı değildir.

Kurulum / Bağlantılar ekranı yalnızca yöneticilere açıktır. Mevcut HTTPS bağlantısını, kaynak ölçümlerini, AD/dizin verisini ve uç ajan güncelliğini gösterir. Kaynak bağlantıları için gereken bilgiler açıklanır. Bu ekran henüz cihaz ekleyen sihirbaz değildir ve ağ/erişim ayarlarını değiştirmez. HTTPS göstergesi bu bağlantının TLS kullandığını belirtir; sertifika dağıtımı veya internet yayın güvenliği sertifikasyonu değildir.

API uçları aynı Origin kontrolü ve mevcut oturum yetkisiyle korunur. POST /api/accounts işlemlerinde parola tekrar doğrulaması da gerekir. Setup.exe/MSI, dört dil, kaynak bağlantı editörü, MFA ve tam kurulum sihirbazı PRODUCT-BACKLOG.md içinde açık işlerdir.

## Cihaz erişim kontrolleri

Kurulum ekranındaki cihaz formu ICMP/TCP erişim hedefi ekler veya aynı cihaz kodunun ayarlarını günceller. Yeni cihaz kodu benzersiz seçilmeli; mevcut cihaz düzenlemek için listeden seçilmelidir. İşlem mevcut yönetici parolasıyla doğrulanır. Bağlantı testi yalnızca erişim kontrolüdür; uygulama sağlığı, API hesabı veya SNMP kimliği doğrulaması değildir.

Kaydetme önce config.backup.local.json yedeğini alır, yeni ayarı atomik olarak kaydeder ve sonraki toplama turuna aktarır. Kimlik bilgisi bağlı kaynaklarda host değişikliği bu formdan engellenir; mevcut collector ayarları korunur. API/SNMP kimlik bilgisi formu henüz yoktur. Cihaz silme bu ekranda uygulanmamıştır.

## API / SNMP bağlantı formu — 6 Kasım 2026

Kurulum / Bağlantılar bölümüne mevcut cihaz için ölçüm bağlantısı ekleme formu eklendi. Önce erişim cihazını ekleyin; liste yenilendikten sonra cihazı ve bağlantı türünü seçin. ESXi kullanıcı/parolası, FortiGate API tokenı veya SNMPv2c salt okunur community girilebilir. HTTPS bağlantılarında sistem güveni veya sunucuda bulunan CA PEM dosyası kullanılır; doğrulama kapatılmaz.

Test yalnızca salt okunur kaynak sorgularını çalıştırır, kalıcı kayıt veya ortam değişkeni değişikliği yapmaz. Test bittikten sonra gizli alanlar temizlenir; kaydetmek için yeniden girilmelidir. Kaydetme gizli değerleri makineye bağlı Windows DPAPI ile korur, kısıtlı izinli data/secure/service-secrets.local.json dosyasında saklar. Cihaz ayarında yalnızca rastgele ortam değişkeni isimleri bulunur. Makine kapsamındaki DPAPI, bu dosyanın erişim izinlerinin korunmasını gerektirir.

İşlemler yönetici yetkisi, aynı Origin ve mevcut yönetici parolası gerektirir. Uzak bağlantı için TLS zorunludur; loopback yerel denemede HTTP kabul edilir. Başarılı kayıt sonrası ölçümler bir sonraki turda yeni bağlantıyı kullanır. Önceki şifreli kayıtlar başarısız geçişte eski bağlantının çalışmasını korumak için silinmez; anahtar temizleme/rotasyon arayüzü sonraki iştir. Bu uygulama SNMPv3 desteği sağlamaz.

Önceki sürüm açıklamalarındaki “kimlik formu yoktur” notları tarihsel sınırlardır; bu bölüm güncel durumu açıklar. Tam kurulum sihirbazı/Setup.exe henüz tamamlanmamıştır.
