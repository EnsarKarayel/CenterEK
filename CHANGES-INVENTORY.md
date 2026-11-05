# Donanım ve operasyon görünümü geliştirmesi

- Bilgisayar tablosu: açık ve güncel Windows oturumları, IP adresleri, toplam/kullanılan RAM ve disk birimi kapasiteleri.
- Durum ve oturum filtreleri; bilgisayar adı, RAM kullanımı ve disk doluluğu sıralaması. Arama kullanıcı adını da kapsar.
- Dashboard: cihaz erişim kutuları ve güncel ajan RAM kullanım sıralaması. Kutular fiziksel topoloji değildir.
- Windows ajanı sabit yerel disk birimlerini .NET üzerinden okur. Fiziksel disk modeli, RAM modül özellikleri ve Linux donanım okuyucusu bu değişiklikte yoktur.
- Sunucu disk listesi boyutunu, kapasite sınırlarını ve sayısal değerleri doğrular; izin verilmeyen alanlar saklanmaz.

## Güncelleme

Panel sunucusundaki uygulama dosyalarıyla birlikte, uç bilgisayarlardaki Collect-EndpointSessions.ps1 betiği de güncellenmelidir. Eski raporlar kabul edilir, ancak disk alanları boş görünür. AD dizin ajanı tek başına uç bilgisayarların disklerini ve açık oturumlarını toplamaz.

## Doğrulama

32 Python testi geçti. Disk testi negatif, kapasiteyi aşan, NaN/sonsuz ve boolean değerleri reddetmeyi ve alan izin listesini kapsar. JavaScript ve PowerShell sözdizimi kontrolleri geçti. Gerçek uç bilgisayardan yeni disk raporu ve görsel tarayıcı kabulü henüz doğrulanmadı. Müşteri sunucusuna dağıtım yapılmadı.
