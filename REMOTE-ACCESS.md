# Uzaktan erişim

Yönetici → Kurulum / Bağlantılar → Uzaktan erişim ekranında üç seçenek vardır:

- **Yalnızca bu bilgisayar:** 127.0.0.1. Varsayılan kurulum.
- **VPN / yerel ağ:** Sunucunun belirli özel IPv4 adresi ve HTTPS. Uzak kullanıcı önce kurum VPN bağlantısını kurar. VPN kurulumu bu programın dışındadır.
- **HTTPS ters proxy:** Genel DNS adı, dış ağ geçidinde geçerli HTTPS sertifikası, MFA, hız sınırlama ve yalnızca proxy tarafından erişilebilen HTTPS arka uç gerekir. Proxy arka uç sertifikasını doğrulamalıdır. WAN’dan uygulama portuna doğrudan yönlendirme yapılmamalıdır.

Ekran mevcut yönetici parolasını yeniden ister. Kaydetmek çalışan dinleyiciyi değiştirmez; sonraki uygulama/SYSTEM görevi yeniden başlatmasında uygulanır. Yeni IP mevcut sunucu sertifikasının SAN alanında bulunmalıdır. Gerekirse önce eşleşen kurum sertifikası sağlanmalıdır. IP değişince ajanların hedef URL’leri de güncellenmelidir.

Başlangıçta sertifika ve port bağlama kontrolü başarısızsa eski ayarlar korunur; `server.failed.local.json` oluşur. Başarılı değişiklik önceki ayarları `server.backup.local.json` içine yedekler. Kontrol ile gerçek dinleyicinin açılması arasında başka süreç portu alırsa uygulama başlatılamayabilir; bu durumda yerel yönetici yedek ayarları geri yüklemelidir.

Program DNS, VPN, proxy, modem/NAT veya WAN güvenlik duvarı kurallarını kendiliğinden oluşturmaz. Ekrandaki onay bir dış güvenlik kontrolünün yapıldığını teknik olarak doğrulamaz. Uygulamada yerleşik MFA henüz yoktur; genel erişim için MFA ağ geçidinde sağlanmalıdır. X-Forwarded-* başlıklarına otomatik güvenilmez. Proxy arkasında uygulamanın IP bazlı giriş sınırı ortak proxy IP’sine uygulanır; ağ geçidinde ayrıca gerçek istemci bazlı sınır gerekir.

Bu önizleme için Internet dağıtımı güvenlik kabul testi gerektirir. DDoS’a karşı mutlak koruma veya ISO 27001 sertifikası iddiası yoktur. İlk tercih kurum VPN’i ile erişimdir.
