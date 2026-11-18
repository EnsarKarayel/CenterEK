# Yıllık abonelik

Ticari politika: yeni ölçümler yalnızca geçerli yıllık abonelikle alınır. Süre dolunca cihaz sorguları, keşif ve ajan raporu kabulü durur. Panel girişi, mevcut hesapların güvenlik işlemleri, geçmiş verileri okuma ve CSV dışa aktarma sürer. Süre doldu diye veri silinmez; saklama temizliği de ölçüm işçisiyle birlikte durur. Geçerli yenileme dosyası yüklenince ölçümler yeniden başlar.

## İmzalı lisans

Lisans müşteri adı, rastgele kurulum kimliği, lisans kimliği, UTC başlangıç/bitiş ve Ed25519 imzası içerir. Kurulum kimliği yeni setup'ta oluşturulur; yükseltmede korunur. Süre en fazla 366 gündür. Uygulamaya yalnızca açık doğrulama anahtarı verilir. Dosyada süre/kurulum kimliği değişirse veya bilinmeyen anahtarla imzalanırsa kabul edilmez. Lisans kontrolü dış sunucuya müşteri verisi göndermez. Çevrimdışı kontrol işletim sisteminin saatine ve yönetici tarafından korunan uygulamaya güvenir; yönetici düzeyinde saat/kod değişikliğine karşı kusursuz DRM iddiası yoktur.

Yayıncı bilgisayarında ayrı, boş ve korumalı bir `license-signing` klasöründe:

```powershell
python license_issuer.py generate-key --private-key C:\ReleaseSecrets\license-signing\publisher.pem --output C:\ReleasePublic\license-key.json --key-id publisher-1
```

Parola terminalden gizli istenir; komut satırına yazılmaz. Oluşan parola korumalı özel anahtarın çevrimdışı yedeğini tutun; müşteri, GitHub, destek kaydı veya sohbetle paylaşmayın. Bu anahtar ürün aboneliği içindir; Authenticode sertifikasından ayrıdır.

Yalnızca açık anahtarı içeren ticari derleme politikası:

```json
{"mode":"commercial","public_keys":{"publisher-1":"BASE64_PUBLIC_KEY"}}
```

Müşteri yönetici hesabıyla Kurulum/Abonelik alanındaki kurulum kimliğini bildirir. Sipariş doğrulandıktan sonra yayıncı `customer`, `installation_id`, `days:365` içeren yerel bir JSON istek dosyasıyla:

```powershell
python license_issuer.py issue --private-key C:\ReleaseSecrets\license-signing\publisher.pem --request C:\Orders\request.json --output C:\Orders\customer-license.json --key-id publisher-1
```

Müşteri imzalı JSON dosyasını panelden etkinleştirir. Bu teknik akış ödeme alma, fatura veya otomatik yenileme hizmeti değildir. Müşteri adı lisans dosyasında açık metindir; yalnızca gerekli müşteri bilgisini kullanın.

## Ticari sözleşme ve ön sürüm

`legal/EULA-DRAFT.tr.txt` satıcı unvanı, destek kapsamı ve pazar şartları kesinleşmeden doldurulmuş sayılmaz; ticari paketlemeye alınmaz. Nihai onaylı metin `--eula-file` ile verilir. Ticari kurulum bu metnin açık kabulünü gerektirir; kabul edilen dosyanın SHA256 değeri ve kabul zamanı kurulum kaydına yazılır. Yeni sözleşmeli yükseltmede tekrar kabul gerekir.

Ön sürüm paketleri `mode:preview` taşır, ücretli abonelik iddiası olmadan eski demo kurulumlarının çalışmasını korur. Eksik/bozuk politika dosyası içeren paket ölçümü açmaz. Ön sürüm/ücretsiz politika satışa hazır kontrolünden geçemez.
