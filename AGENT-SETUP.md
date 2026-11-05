# 0.4 — otomatik uç bilgisayar ve dizin raporları

## Bu sürümde çalışan akış

Windows bilgisayar kendi etkileşimli oturumlarını, yerel IPv4 kart adreslerini ve CPU/RAM ölçümlerini okur. Rapor 60 saniyede bir HTTPS üzerinden CenterEK'e gönderilir. AD sunucusundaki ayrı toplayıcı AD kullanıcıları/bilgisayarları, varsa DHCP kiraları ve DNS A kayıtlarını 300 saniyede bir gönderebilir. Yeni AD hesabı oluşturulmaz; AD oturum açma eklenmez.

Her bilgisayar/kaynak için ayrı anahtar kullanılır. Anahtar veritabanında SHA-256 özetiyle tutulur; yalnızca kayıtlı bilgisayar ve kaynak türü adına yazabilir. Panel parolası veya FortiGate anahtarı ajanlara verilmez. Gönderim anahtarı Windows kullanıcısına bağlı DPAPI ile korunur. Veri alımı panel oturumu açmaz veya paneli okuma hakkı vermez.

Kurulum otomatik olarak ağ portu/NAT, Windows güvenlik duvarı, GPO veya AD nesnesi değiştirmez. Aşağıdaki örneklerdeki IP, DNS ve bilgisayar adlarını gerçek ortamınızla değiştirin.

## 1. Sunucuyu HTTPS ile açma

Kaynakları güncelleyin; mevcut data, certs, config.local.json, server.local.json ve kullanıcı hesaplarını koruyun. Uygulama durdurulmuş olmalı.

Kurumunuzun kullanılan DNS/IP'yi kapsayan sertifikası varsa onu kullanın. Pilot için tls_setup.py isteğe bağlı cryptography paketiyle dar kapsamlı bir CA ve 180 günlük sunucu sertifikası oluşturabilir:

```cmd
cd /d C:\CenterEK
"C:\Program Files\Python311\python.exe" -m pip install -r requirements-tls.txt
"C:\Program Files\Python311\python.exe" tls_setup.py --hostname centerek.example.local --ip 192.0.2.15 --configure-server
```

Bu yardımcı certs/panel altında panel-ca.pem, panel-cert.pem ve panel-key.pem oluşturur. server.local.json içine dinleme IP/port/sertifika yolları yazılır. Mevcut sertifika klasörü veya server.local.json üzerine yazılmaz. CA özel anahtarı saklanmaz; yenileme için yeni pilot CA dağıtımı veya kurum CA sertifikası gerekir. Özel anahtar dosyaları oluşturan kullanıcı/SYSTEM/yerel yöneticilere kısıtlanır.

Eski sunucuda cryptography paketi çalışmazsa sertifikayı güncel yönetici bilgisayarında üretip sertifika/özel anahtarı güvenli şekilde sunucuya taşıyın; özel anahtarı uç bilgisayarlara dağıtmayın. Bu helper'ın hedef Server 2012 R2 üzerinde doğrulanması ayrıca gerekir.

```cmd
"C:\Program Files\Python311\python.exe" start.py
```

Başlangıç adresi artık https://GERCEK-SUNUCU-IP:8765 olmalıdır. İstemci bilgisayar/AD sunucusu yalnızca panel-ca.pem dosyasını alır. Bu CA'nın SHA-256 parmak izini sunucudaki kopyayla doğruladıktan sonra, toplayıcıyı çalıştıracak Windows kullanıcısının güven deposuna kurun:

```cmd
certutil -hashfile panel-ca.pem SHA256
certutil -user -addstore Root panel-ca.pem
```

Root ekleme yalnızca ilgili pilot CA'yı güvenilir yapar; şirket politikanıza uygunsa uygulayın. TLS doğrulamasını kapatan seçenek yoktur. Sunucunun güvenlik duvarında yalnızca gerekli özel ağ bilgisayarları için TCP 8765 erişimi sağlanmalıdır; internete yönlendirme açılmaz. Sunucuda FortiGate API'si için kullanılan CA farklıdır ve değiştirilmez.

## 2. Uç bilgisayar kaydı: sunucuda

Yönetici CMD'de bir bilgisayar için kayıt oluşturun. Yerel kısa bilgisayar adı kullanılması önerilir:

```cmd
"C:\Program Files\Python311\python.exe" agents.py register --computer PC01 --kind endpoint --url https://192.0.2.15:8765 --output data\PC01-enrollment.local.json
```

Çıktı anahtar içerir; aynı bilgisayar/tür için ikinci kayıt otomatik oluşturulmaz. Dosyayı yalnızca o bilgisayara güvenli olarak aktarın. Kod veya GitHub paketine eklemeyin. Kayıt listesi ve iptal:

```cmd
python agents.py list
python agents.py revoke --id AJAN_KIMLIGI
```

İptalden sonra sonraki gönderim reddedilir. Mevcut son rapor 150 saniyelik güncellik süresi dolana kadar gösterilebilir; oturum tablosu fiziksel çevrimiçi durum garantisi değildir. Anahtar yenilemesi için şimdilik kayıt/veritabanı bakım prosedürü gerekir; otomatik anahtar dönüşümü eklenmedi.

## 3. Uç bilgisayarda kurulum

Aynı klasöre Collect-EndpointSessions.ps1, Send-Report.ps1, Setup-Agent.ps1 ve START-AGENT.cmd dosyalarını koyun. Kayıt dosyası bu bilgisayara ait olmalı. Toplayıcıyı çalıştıracak mevcut Windows hesabınızla CMD'de:

```cmd
cd /d C:\CenterEK-Agent
powershell.exe -NoProfile -File Setup-Agent.ps1 -EnrollmentFile PC01-enrollment.local.json
START-AGENT.cmd
```

Setup-Agent.ps1 anahtarı mevcut kullanıcı/makineye bağlı DPAPI ile şifreler ve agent.local.json dosyasının izinlerini kısıtlar. Düz anahtarlı enrollment dosyasını işlem tamamlandıktan sonra güvenli aktarım yerinden ve hedef bilgisayardan kaldırın. Başka Windows hesabıyla çalıştırırsanız şifre çözülmez. Parola/anahtar komut satırına yazılmaz. Kurumsal script politikası imza istiyorsa imzalı dağıtım gerekir; ExecutionPolicy bypass kullanılmaz.

Rapor alınırsa konsolda 'Rapor HTTPS ile alındı.' yazısı görünür. Hatalı sertifika/anahtar/ağ durumunda yerel son rapor korunur ve sonraki turda yeni raporla denenir. Geçmiş çevrimdışı raporlar kuyruklanmaz. İlk CPU raporu boştur; ikinci turdan itibaren GetSystemTimes farkıyla ortalama CPU yüzdesi hesaplanır. 64'ten fazla mantıksal işlemcili makinelerde Windows işlemci grubu kapsamı ayrıca değerlendirilmelidir. RAM GlobalMemoryStatusEx ile alınır.

Birden fazla IP varsa kart adları gösterilir. Ağ geçidi bulunan ilk kartın adresi primary_ip alanında yardımcı aday olarak yer alır; işletim sisteminin her hedef için seçeceği güzergâhın kesin ölçümü değildir. DNS kaynaklı eski raporlar yerel kart kaydı gibi etiketlenmez.

## 4. Kullanıcı oturum açınca otomatik başlatma

İlk başarılı gönderimden sonra Install-AgentTask.ps1 dosyasını aynı klasöre koyup aynı Windows hesabıyla çalıştırabilirsiniz:

```cmd
powershell.exe -NoProfile -File Install-AgentTask.ps1 -AgentConfig C:\CenterEK-Agent\agent.local.json
```

Görev yalnızca mevcut kullanıcı oturum açmışken, aynı kullanıcı ve sınırlı yetkiyle çalışır. Kullanıcı oturumu kapalıyken çalışan sistem servisi değildir. Kullanıcı çıkınca rapor kesilir; panel 150 saniye sonra 'güncel değil' gösterir. Tüm kullanıcıları ve oturum kapalı cihazları sürekli izleyen servis/kurumsal dağıtım sonraki aşamadır. Aynı adlı mevcut görev üzerine yazılmaz. Kurulum test makinesinde görev oluşturularak çalıştırılmadı; yalnızca sözdizimi doğrulandı.

## 5. AD/DHCP/DNS otomatik gönderimi

Sunucuda --computer DC01 --kind directory kullanarak ayrı kayıt oluşturun. Kayıt dosyasını ilgili AD sunucusuna aktarın. Export-DirectoryInventory.ps1, Send-DirectoryInventory.ps1, Send-Report.ps1, Setup-Agent.ps1 ve START-DIRECTORY.cmd aynı klasörde olmalı. Mevcut yetkili Windows oturumuyla:

```cmd
powershell.exe -NoProfile -File Setup-Agent.ps1 -EnrollmentFile DC01-enrollment.local.json
START-DIRECTORY.cmd
```

Gerekli AD/DHCP/DNS PowerShell modülleri ve okuma yetkileri yine gerekir. Eksik bölüm hata olarak gösterilir; olmayan kayıtlar üretilmez. Dizin dosyası otomatik alındığında AD ekranında 'Otomatik HTTPS aktarımı' görünür. Dizin kaydı ilk 20.000 kullanıcı/bilgisayar/kira/DNS sınırlarına tabidir; bu sınırın üzerindeki raporlar reddedilir. Directory gönderim gövdesi en fazla 5 MiB'dir; büyük kurumlar için sayfalama gerekir. Uç rapor sınırı 256 KiB, 100 oturum ve 64 IP'dir.

## Güven sınırı ve izleme anlamı

Kimliği doğrulanmış rapor, kayıtlı ajan anahtarıyla gönderildiği anlamına gelir; bilgisayarın donanım kimliğine karşı kriptografik attestation değildir. Bir anahtarı ele geçiren kişi o bilgisayar adına veri gönderebilir; anahtarları koruyun ve iptal edin. Replay/eski/gelecek tarihli raporlar ve aşırı sık gönderim reddedilir. Saatlerin senkron olması gerekir. Kaynak makinedeki oturum 'Active' durumu ekranın kilitsiz veya kişinin bilgisayar başında olduğunu kanıtlamaz. Uygulama ekran/tuş/içerik kaydı yapmaz.

Bilgisayarların CPU/RAM geçmişi sadece kimliği doğrulanmış raporların kabul edildiği anlardan oluşur; veri yokken çizgiyle doldurulmaz. Manuel JSON raporları desteklenir fakat ayrı kaynak etiketiyle görünür. AD eşleşmesi için aynı domain (DNS veya NetBIOS) ve hesap adı gerekir; IP veya kısa kullanıcı adı tek başına yeterli değildir.
