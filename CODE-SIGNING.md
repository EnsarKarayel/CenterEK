# Üretim kod imzası

Mevcut makine sertifika depolarında kullanılabilir kod imzalama sertifikası ve PATH üzerinde SignTool bulunamadı. Panelin yerel HTTPS CA'sı kod imzalama sertifikası değildir. Kendi kendine imzalı test sertifikası müşteri dağıtımı için güvenilir yayıncı kimliği olarak kullanılmaz.

## Sertifika edinme yolu

Ürün sahibinin verdiği profil `legal/publisher.json`: **Ensar Karayel, Türkiye; karayelensar@gmail.com**. E-posta daha sonra bu tek dosyadan değiştirilebilir; bu kayıt sertifika otoritesinin kimlik doğrulaması yerine geçmez.

Türkiye için incelenecek somut başvuru yolu: [Certum ticari Code Signing](https://www.certum.eu/en/code-signing-certificates/) bireysel veya şirket başvurusunu desteklediğini belirtir. Başvurmadan önce Türkiye'den başvuru, donanım/bulut anahtar seçeneği ve toplam ücret sağlayıcıdan teyit edilmelidir. [Open Source sertifika koşulları](https://support.certum.eu/en/code-signing-required-documents/) ticari yazılımda kullanılmasına izin vermediğinden bu ürün için o seçenek kullanılmaz. Satın alma yapılmadı; kimlik belgesi veya ödeme bilgisi sohbet üzerinden istenmez.

1. Satıcının gerçek ticari unvanı/bireysel statüsü ve ülkesi kesinleşir. Sertifikadaki yayıncı kimliği bu bilgiyle uyumlu olmalıdır; Microsoft veya CA kimlik doğrulaması sahibi tarafından tamamlanır.
2. [Azure Artifact Signing Public Trust uygunluğu](https://learn.microsoft.com/en-us/azure/artifact-signing/quickstart) ülkeye ve bireysel/kurumsal başvuruya bağlıdır. Türkiye listede değildir; Türkiye'de kayıtlı satıcı için uygunluğu doğrulanmış bir ticari CA'nın OV kod imzalama hizmeti değerlendirilmelidir. Private Trust müşteri bilgisayarlarında genel güven sağlamaz.
3. [Microsoft'un imzalama seçenekleri](https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/code-signing-options) donanım tokenı/HSM veya sağlayıcının bulut anahtar hizmeti kullanan OV seçeneklerini açıklar. EV satın almak tek başına SmartScreen uyarılarının kalkacağını garanti etmez. Satın alma ve kimlik doğrulaması bu geliştirme kapsamında otomatik yapılmaz.
4. Sağlayıcının desteklediği Windows sertifika sağlayıcısı/istemcisi kurulur. Özel anahtar donanımda veya sağlayıcının HSM hizmetinde kalır; GitHub'a PFX, parola veya özel anahtar konmaz. Windows SDK SignTool ayrıca kurulur.
5. Sertifika CurrentUser/My deposunda özel anahtarıyla görünür olduğunda thumbprint ve sağlayıcının HTTPS zaman damgası adresiyle üretim derlemesi yapılır.

## Hazırlanan teknik akış

```powershell
python build_windows.py --license-policy C:\ReleaseSecrets\policy.json --eula-file C:\ReleaseApproval\EULA.txt --sign-thumbprint CERTIFICATE_THUMBPRINT --signtool 'C:\WindowsSDK\signtool.exe' --timestamp-url https://PROVIDER-TIMESTAMP-ENDPOINT
```

Bu bir şablondur; henüz gerçek sertifikayla çalıştırılmamıştır. `release_signing.py`, iç uygulamayı ZIP/tek dosya paket oluşturulmadan önce, dış setup'ı paketlemeden sonra imzalar. Yerel PowerShell betikleri de imzalanır. [SignTool akışı](https://learn.microsoft.com/en-us/windows/win32/seccrypto/signtool) SHA256 dosya imzası ve RFC3161 SHA256 zaman damgası kullanır; PowerShell betikleri sağlayıcının Authenticode zaman damgası desteğini gerektirir. Gerçek sağlayıcıyla bu uyumluluk ayrıca doğrulanmalıdır.

Her sonuç Windows Authenticode ile `Valid`, aynı yayıncı thumbprint'i ve zaman damgası açısından doğrulanır. İmza hatası, güvenilmeyen zincir veya eksik zaman damgası üretimi durdurur. Hash değerleri imzalamadan sonra hesaplanır. Üçüncü taraf DLL'lerine CenterEK imzası atılmaz; kurumsal WDAC/catalog ihtiyacı ayrı kabul konusudur.

İmza edinilmiş olsa da SmartScreen uyarısızlık, güvenlik incelemesi veya Microsoft tarafından ürün onayı iddiası yapılmaz.
