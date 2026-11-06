# Azure test ortamı ve CI/CD

## Kapsam

GitHub kaynak deposu `EnsarKarayel/CenterEK` kalır. GitHub Actions her dal push'unda ve PR'da Windows/Python 3.11–3.12 testlerini, arayüz/dil davranışlarını, PowerShell sözdizimini ve Bicep derlemesini çalıştırır. Fork PR'ları Azure sırrı/kimliği almaz. `pull_request_target` kullanılmaz.

`main` başarılıysa bağımsız Windows kurulum ZIP'i üretilir. Paket içinde HTTPS oturumu/API, DPAPI, ESXi ve SNMPv3 kontrol edilir; SHA-256 ve müşteri verisi dışlama kontrolünden sonra 14 gün GitHub artifact olarak saklanır. Sonuçlar Actions ve iş özeti ekranındadır. GitHub bildirim tercihleri kullanıcının hesabından yönetilir; bu kurulum kimseye ayrıca e-posta göndermez.

Azure dağıtımı varsayılan kapalıdır. `AZURE_DEPLOY_ENABLED=true` yalnızca ortam hazırlandıktan sonra ayarlanmalıdır. Üretime otomatik dağıtım yoktur. `azure-staging` GitHub Environment'ını yalnızca `main` dalına sınırlandırın; gerekiyorsa required reviewer ekleyin. Ana dalın zorunlu kontrolleri `Verify Windows / Python 3.11`, `Verify Windows / Python 3.12`, `Validate Azure infrastructure` olmalıdır. Bu kontroller için strict/up-to-date ve PR zorunluluğu önerilir; mevcut korumaları silmeyin.

## Altyapı tercihi

Mevcut DPAPI ve SYSTEM görevleri Windows'a bağlıdır. İlk sürüm tek Windows Server 2022 VM'de çalışır; SQLite aynı VM'dedir ve yatay ölçekleme/HA sağlamaz. VM'nin genel IP'si yoktur, RDP/SSH Internet'e açılmaz. Uygulama belirli özel IP'de HTTPS dinler. NAT Gateway yalnızca çıkış içindir. Bu şablon ücretsiz hizmet garantisi değildir: VM, disk, NAT, IP, depolama, Key Vault ve uyarı kaynakları deneme kredisini tüketebilir. Kaynak oluşturmadan önce bölge, kota ve maliyet incelenmelidir; ücretsiz abonelik otomatik ücretliye yükseltilmez.

Azure VNet `10.42.0.0/16`, VM `10.42.1.4`. Bu aralık mevcut ağla çakışmamalıdır. `clientCidr` yalnızca seçilen özel VPN/ofis ağı olmalıdır. VPN Gateway/site-to-site bağlantısı şablona dahil değildir. Özel ofis IP'leri Azure'dan kendiliğinden erişilebilir olmaz. Mevcut AD/endpoint ajanları HTTPS hedefini Azure adresine yönlendirebilmek için VPN ve sertifika güveni ister. FortiGate/SNMP/ESXi okuma için de ağ yolu gerekir. Ayrı şubelerin verisini ileten genel bir collector ajanı henüz tamamlanmadı. Azure'da otomatik ağ taraması varsayılan kapalıdır.

## Kurulum sırası

Bağlantı önce ücretli uygulama altyapısı olmadan da sınanabilir: boş test kaynak grubuna `infra/azure/identity.bicep` yalnızca OIDC managed identity ve o gruba Reader rolü kurar. GitHub `azure-staging` ortamına kimlikler/ kaynak grubu girildikten sonra **Azure connection check** elle çalıştırılır. Bu işlem VM/NAT/depolama oluşturmaz. Tam şablon daha sonra aynı kimliği kullanıp yalnızca gereken VM ve artifact container yetkilerini ekler.

1. Azure ücretsiz abonelik başvurusunu kullanıcı tamamlar; teklif/harcama koruması doğrulanır. Bölge ve maliyet seçilir.
2. Azure CLI ile kullanıcı oturumu açılır. `az deployment group what-if` sonucuyla şablon incelenir; şifreler komut satırına veya Git'e yazılmaz. Yeni kaynak grubu/şablon uygulaması için abonelikte rol atama hakkı gerekir.
3. `infra/azure/main.bicep`: özel VM, çıkış NAT'ı, özel release container'ı, Key Vault ilk panel parolası, VM managed identity, GitHub OIDC managed identity ve CPU uyarısı oluşturur. `alertEmail` alıcısı kullanıcı tarafından belirlenmelidir. Şablon tek başına uygulamayı kurmaz.
4. `azure-staging` Environment secrets: `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`. Bunlar şablon çıktılarından alınır; Azure client secret oluşturulmaz. Federation subject tam olarak `repo:EnsarKarayel/CenterEK:environment:azure-staging` olur.
5. Environment variables: `AZURE_RESOURCE_GROUP`, `AZURE_VM_NAME`, `AZURE_STORAGE_ACCOUNT`, `AZURE_KEY_VAULT`, `AZURE_CLIENT_CIDR`. Repository variable `AZURE_DEPLOY_ENABLED=true` son adımda açılır.
6. `main` CI akışı yeniden çalıştırılır. GitHub OIDC kimliği yalnızca bu VM'yi yönetebilir ve release container'ına paket yazabilir; abonelik Owner/Contributor verilmez. VM kendi managed identity'siyle paketi ve yalnızca ilk panel parolasını okur. Uzun ömürlü SAS veya VM parolası pipeline'a verilmez.
7. VPN üzerinden panel, ofis ajanları ve salt okunur cihaz bağlantıları kabul testinden geçirilir. İlk panel hesabı `azure-admin`; parolası Key Vault'ta kullanıcı tarafından belirlenen değerdir. Örnek veya sabit parola yoktur.

## Dağıtım ve geri dönüş

CI paketinin commit ve SHA-256 değeri kontrol edilir, private Blob Storage'a yüklenir. Azure VM Run Command ile SYSTEM bağlamında `Deploy-Guest.ps1` çalışır. İlk kurulum sessiz kurucuyu kullanır. Güncellemede görevler durdurulur ve uygulama/veritabanı/ayarlar aynı VM'deki korumalı klasöre yedeklenir. Yalnızca uygulama dosyaları yenilenir; yerel kullanıcılar, ajan kayıtları, cihaz ayarları ve sertifikalar korunur. Başarısız HTTPS/veritabanı/worker kontrolünde önceki tam yedek geri yüklenir. İlk kurulum başarısızsa tanı dosyaları korunur; otomatik silme veya tekrar üstüne kurma yoktur.

Dağıtım geçmişi `C:\CenterEK-deploy\deployments.jsonl`, çalışan commit `C:\CenterEK\data\release.local.json`, günlükler `C:\CenterEK\data\logs` içindedir. `/healthz` yalnızca ok/unavailable döndürür; kullanıcı/cihaz/ayar bilgisi döndürmez. Bu kontrol süreç ve veritabanı sağlığını gösterir; tüm izlenen cihazların erişilebilir olduğunu garanti etmez.

VM CPU uyarısı Bicep'te vardır; uygulama için dışarıdan sürekli uptime denetimi, Azure Backup ile VM dışı yedek, restore tatbikatı ve Log Analytics/AMA aktarımı sonraki kabul işleridir. Yerel deployment yedeği felaket kurtarma değildir. Disk/yedek saklama ve temizlik politikası ayrıca belirlenmelidir. Şema değişikliği gelen sürümlerde geriye dönüş uyumluluğu ayrıca test edilmelidir.

## Resmi başvurular

- [GitHub Actions → Azure OIDC](https://learn.microsoft.com/en-us/azure/developer/github/connect-from-azure-openid-connect)
- [Azure VM Run Command](https://learn.microsoft.com/en-us/azure/virtual-machines/windows/run-command)
- [Azure ücretsiz hesap](https://azure.microsoft.com/en-us/pricing/purchase-options/azure-account)
