# 0.5 — penceresiz, oturumdan bağımsız işletim

## Kurulumun sonucu

CenterEK sunucusu ve AD/endpoint göndericileri Windows Görev Zamanlayıcı altında SYSTEM hesabıyla çalışır. Bunlar Windows servis kayıtları değil, açılışta başlayan ve sürekli çalışan SYSTEM görevleridir. CMD/PowerShell penceresi açılmaz; kullanıcı Windows'tan çıkış yapabilir. Program kapanırsa sarmalayıcı 15 saniye sonra yeniden dener. Görevin kendisi sonlanırsa Görev Zamanlayıcı hata yeniden başlatma ve beş dakikalık kurtarma tetikleyicisini kullanır. Aynı görevden ikinci örnek açılmaz.

Bilgisayar açık, Windows/Görev Zamanlayıcı sağlıklı ve gerekli ağ/hizmetler erişilebilir olduğu sürece çalışır. Elektrik/ağ/işletim sistemi arızası veya uygulama hatası sıfır kesinti garantisiyle ortadan kalkmaz. Sunucu sanal makinesinin fiziksel hostu kapanırsa izleme de durur.

Mevcut panel hesapları, veritabanı, TLS ve cihaz ayarları korunur. AD'de kullanıcı oluşturulmaz. SYSTEM yalnızca bu bilgisayarda var olan Windows sistem hesabıdır.

## A. İzleme sunucusu

0.5 kaynak dosyalarının tamamını mevcut C:\CenterEK üzerine kopyalayın. data, certs, config.local.json, server.local.json dosyalarını koruyun. Çalışan start.py penceresini Ctrl+C ile durdurun.

Yönetici CMD'de:

```cmd
cd /d C:\CenterEK
"C:\Program Files\Python311\python.exe" service_secrets.py
```

FortiGate tokenı ve diğer yapılandırılmış bağlantıların kimlik bilgileri bir kez sorulur. Bunları yalnızca terminale girin. Makine kapsamlı DPAPI ile data/secure/service-secrets.local.json içine şifrelenir. Başka bilgisayara taşınan dosya çözülemez. SYSTEM aynı makinede okuyabilir. Şifreli dosyanın erişimi de korunur; makine kapsamlı DPAPI tek başına dosya erişim denetiminin yerini tutmaz.

```cmd
powershell.exe -NoProfile -File "C:\CenterEK\Install-SystemTask.ps1" -Mode Server
```

Kurulan görev: **CenterEK-Server-System**. Program hemen başlatılır ve sonraki Windows açılışında da başlar. Panelin HTTPS adresi aynı kalır. İlk çalışmada paneli başka bilgisayardan açıp FortiGate ölçümlerinin geldiğini doğrulayın.

## B. AD sunucusu

VOLO'daki mevcut AD toplayıcısı klasörüne güncel şu dosyaları kopyalayın:

- Install-SystemTask.ps1, Run-SystemTask.ps1
- Send-Report.ps1, Send-DirectoryInventory.ps1, Export-DirectoryInventory.ps1

Mevcut agent.local.json ve panel-ca.pem korunur. Elle çalışan START-DIRECTORY penceresini Ctrl+C ile durdurun. Kullanıcı kapsamlı anahtarı oluşturduğunuz aynı Windows hesabıyla yönetici CMD'de:

```cmd
powershell.exe -NoProfile -File "C:\CenterEK-AD\Install-SystemTask.ps1" -Mode Directory -AgentConfig "C:\CenterEK-AD\agent.local.json" -CACertificate "C:\CenterEK-AD\panel-ca.pem"
```

Kurulan görev: **CenterEK-Directory-System**. Kurucu mevcut kullanıcı kapsamlı anahtarı çözüp ayrı data/secure/agent.system.local.json dosyasına makine kapsamlı DPAPI ile kaydeder. Orijinal ayar dosyasını değiştirmez. Belirttiğiniz CA'yı yerel makinenin güvenilir kök deposuna ekler; böylece SYSTEM de HTTPS'i doğrular. Mevcut CenterEK-directory görevi aynı klasöre bağlıysa XML yedeği alınarak durdurulur ve devre dışı bırakılır. Başka görevlere müdahale edilmez.

SYSTEM bağlamındaki AD/DNS modül sorguları gerçek VOLO sunucusunda ayrıca doğrulanmalıdır. Yerel DC sistem hesabının okuma erişimi veya ADWS/DNS hizmeti sorunluysa günlükte bölüm hatası görünür. Başarı doğrulanmadan pencere kapatarak testin tamamlandığı varsayılmamalıdır.

## C. Uç bilgisayarlar

Endpoint klasöründeki kodları güncelleyin ve mevcut kullanıcı kapsamlı agent.local.json ile aynı Windows hesabında yönetici CMD'de:

```cmd
powershell.exe -NoProfile -File "C:\CenterEK-Agent\Install-SystemTask.ps1" -Mode Endpoint -AgentConfig "C:\CenterEK-Agent\agent.local.json" -CACertificate "C:\CenterEK-Agent\panel-ca.pem"
```

Kurulan görev: **CenterEK-Endpoint-System**. Kullanıcı oturumu yokken de rapor gönderir; bu durumda oturum listesi boş olabilir, bilgisayar kaynakları gönderilmeye devam eder. Yeni ajan varsayılan aralığı **15 saniyedir**. AD aralığı 300 saniye, firewall kaynak aralığı yaklaşık 60 saniyedir. Eski ajanlar güncellenmeden aralıkları değişmez.

## Görev ve günlük kontrolü

```cmd
schtasks /query /tn "CenterEK-Server-System" /v /fo list
schtasks /query /tn "CenterEK-Directory-System" /v /fo list
```

İlk komut izleme sunucusunda, ikinci komut AD sunucusunda çalıştırılır. Çalışan uzun görev için son çalıştırma sonucu 'running' kodu gösterebilir; gönderimin başarılı olduğunun asıl kanıtı panelde ilerleyen son alım zamanı ve günlük satırlarıdır.

```cmd
powershell.exe -NoProfile -Command "Get-Content -LiteralPath 'C:\CenterEK\data\logs\server.log' -Tail 30"
powershell.exe -NoProfile -Command "Get-Content -LiteralPath 'C:\CenterEK-AD\data\logs\directory.log' -Tail 30"
```

Günlükler UTF-8, yaklaşık 5 MiB'de bir .1 yedeğine döner. API anahtarları bilerek loglanmaz. Yedek ve anahtar dosyaları Git'e eklenmez.

## Test sırası

1. SYSTEM görevi kurulur ve başlatılır.
2. Panel erişimi / FortiGate verisi / AD gönderimi ayrı ayrı doğrulanır.
3. Eski elle çalışan CMD/PS pencereleri kapatılır. Görevler görünür pencere açmamalıdır.
4. Windows oturumu kapatılır. Başka bilgisayardan panel ve son AD alımı kontrol edilir.
5. Uygun bakım zamanında yeniden başlatma testi yapılır. Oturum açmadan panel gelmeli, sonra AD alım zamanı ilerlemelidir.

Geliştirme ortamında 31 Python/HTTP/DPAPI testi geçti; SYSTEM tetikleyici/ana hesap/kurtarma görev tanımı Windows üzerinde oluşturularak doğrulandı, PowerShell/Python makine DPAPI uyumu test edildi. Kullanıcının sunucularında gerçek görev kaydı, Windows oturum kapatma ve yeniden başlatma doğrulaması hâlâ kurulum aşamasının parçasıdır.

## Bakım, durdurma ve geri dönüş

Kasıtlı durdurmada önce görevi devre dışı bırakın; yalnızca sonlandırırsanız kurtarma tetikleyicisi yeniden başlatabilir:

```cmd
schtasks /change /tn "CenterEK-Server-System" /disable
schtasks /end /tn "CenterEK-Server-System"
```

Kod güncellemesini bu şekilde durdurduktan sonra uygulayın; ardından:

```cmd
schtasks /change /tn "CenterEK-Server-System" /enable
schtasks /run /tn "CenterEK-Server-System"
```

AD için görev adı CenterEK-Directory-System'dir. Eski etkileşimli görevin XML yedeği data/task-backups içindedir. Orijinal agent.local.json korunur; sistem görevini devre dışı bırakıp START-DIRECTORY.cmd ile elle çalışmaya geri dönebilirsiniz. Bu betik dosya izinlerini sıkılaştırdığı için bakım/kopyalama yönetici hesabıyla yapılmalıdır.

Kurucu SYSTEM'in çalıştıracağı program klasörünü yerel yöneticiler ve SYSTEM ile sınırlar; çocuk dosyaların ACL'lerini buna göre sıfırlar. Bu nedenle uygulama için ayrılmış klasörde çalıştırılmalıdır, paylaşımlı belge klasöründe değil. Sembolik bağlantı içeren veya sürücü/Windows kökü olan klasörlerde işlem reddedilir. Eski veya ilgisiz aynı adlı görevler denetlenmeden değiştirilmez.
