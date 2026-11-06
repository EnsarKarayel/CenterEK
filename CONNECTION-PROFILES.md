# Marka bağımsız bağlantı profilleri

## Uygulanan bağlantılar

| Profil | Bağlantı | Ölçüm kapsamı |
|---|---|---|
| Genel switch/router/firewall/AP | SNMPv3 authPriv veya SNMPv2c | IF-MIB arayüz adı, açıklama, yönetim/operasyon durumu, hız, trafik, toplam hata sayaçları |
| VMware ESXi | HTTPS + kullanıcı/parola | CPU, RAM, datastore |
| FortiGate | HTTPS REST API + token | Kaynak ve arayüz ölçümleri, API yanıtı/yetkisine bağlı envanter |
| Windows uç ajanı | Yerel ölçüm + HTTPS raporu | CPU/RAM, IP, disk birimleri, Windows oturumları |
| AD/DNS ajanı | Mevcut Windows yetkisi + HTTPS raporu | Kullanıcı/bilgisayar/DNS envanteri |

Genel SNMP, belirli bir üreticinin API'sine bağımlı değildir. Desteklenen MIB nesnelerinin cihaz ve hesap tarafından sunulması gerekir; tüm üretici/model aileleri test edilmiş değildir. Başarılı arayüz okuması üreticiye özel VPN, PoE, sıcaklık veya oturum ölçümlerinin desteklendiği anlamına gelmez.

## SNMP güvenlik profili

Yeni formda SNMP için varsayılan v3 authPriv seçeneği sunulur. Kullanıcı adı, kimlik parolası ve şifreleme parolası gerekir. SHA-256 kimlik doğrulama ve AES-128 gizlilik kullanılır; destekleyen eski cihazlarda SHA-1 seçilebilir. Parolalar en az 8 karakterdir. MD5/DES veya kimliksiz SNMPv3 modları bu arayüzde yoktur. Cihazın kullanıcı/algoritma ayarlarıyla eşleşmelidir.

Eski yapılandırmada sürüm alanı yoksa SNMPv2c davranışı korunur. v2c şifrelenmez; salt okunur community, yönetim ağı ve toplayıcı kaynak adresi kısıtlaması gerektirir. Kullanıcının cihazında SNMP ayarları otomatik değiştirilmez.

## Kullanım

1. Kurulum / Bağlantılar ekranında cihaz erişim hedefini ekleyin.
2. Ekranı yeniden açıp mevcut cihaz ve bağlantı profilini seçin.
3. Cihazda tanımlı salt okunur kimlikleri, portu ve gerekiyorsa HTTPS CA yolunu girin.
4. Kimlik ve bağlantı testini çalıştırın. Test kalıcı ayar yazmaz; gizli alanlar sonuçtan sonra temizlenir.
5. Kaydetmek için bilgileri yeniden girin. Kaydedilen sırlar Windows DPAPI ve dosya erişim izinleriyle korunur.

AD ve Windows ajanları henüz bu collector formuyla kurulmaz; ayrı ajan kayıt/dağıtım akışına sahiptir. Tablo ve rehberler bunu belirtir. Linux kaynak ajanı, Redfish/iDRAC, LLDP/FDB ve diğer üreticilerin özel API adaptörleri açık işlerdir.

## Doğrulama

42 Python testi ve switch DOM davranış kontrolü geçti. SNMPv3 SDK nesnesinde authPriv seviyesi, sürüm/algoritma doğrulaması ve eski v2c uyumluluğu test edildi. Gerçek SNMPv3 cihaz bağlantısı ve yeni formun görsel kabulü henüz tamamlanmadı. Bu metin ürün sertifikasyonu veya tüm cihazlarla uyumluluk iddiası değildir.
