# Switch izleme

Switchler / Portlar ekranı, adı veya türü Switch içeren yapılandırılmış cihazların SNMP arayüz verilerini gösterir. Yeni ekran tek başına cihaz keşfetmez veya SNMP kimlik bilgisi oluşturmaz.

## Mevcut bağlantıya ekleme

Sunucudaki mevcut cihaz listesine aşağıdaki örnek yapıyla cihaz eklenebilir. Adres belgeleme adresidir; gerçek switch yönetim IP'siyle değiştirilmeli. İlgili kimlik bilgisi configure.py / service_secrets.py akışıyla korunmalıdır; community değerini JSON'a veya Git'e yazmayın.

```json
{
  "id": "switch-core",
  "name": "Core Switch",
  "host": "192.0.2.2",
  "kind": "Switch",
  "method": "icmp",
  "collector": {
    "type": "snmp",
    "port": 161,
    "community_env": "CENTEREK_SWITCH_CORE_COMMUNITY"
  }
}
```

Bu sürümde SNMPv2c kullanılır. Salt okunur erişim, yönetim ağı ve toplayıcı adresi kısıtlaması kullanılmalı. SNMPv3 ve arayüzden cihaz ekleme backlog kapsamındadır. ICMP engelliyse erişim kontrolü ayrıca uygun yöntemle yapılandırılmalıdır; port ölçümü ve erişim kontrolü ayrı kaynaklardır.

## Gösterilenler

- Mantıksal port kutuları; cihaz/IP, port adı ve açıklaması.
- Operasyon/yönetim durumu; yüksek hız alanı varsa Mbps, yoksa ifSpeed dönüşümü.
- Sayaç farkından alım/gönderim Mbps ve toplam hata sayaçları.
- Arama, cihaz/durum filtreleri, trafik/hata sıralaması ve 50 satır sayfalama.
- Ölçüm eski veya başarısızsa port durumu bilinmiyor olarak gösterilir; trafik ve kapasite gizlenir.

IF-MIB alanları [RFC 2863](https://www.rfc-editor.org/rfc/rfc2863.html) esas alınarak okunur. Okuyucu cihaz başına en fazla 128 arayüzle sınırlıdır. Hata sayacı artış hızı değildir; toplam sayaç sıfır dışı diye yeni alarm üretilmez.

## Henüz olmayanlar

LLDP/CDP komşuları, VLAN bağlamlı FDB, uç cihaz–port eşleştirmesi, PoE ve fiziksel kasa çizimi bu sürümde yoktur. Port kutuları kablolama haritası olarak yorumlanmamalıdır. Gerçek switch marka/model ve yönetim erişimiyle kabul testi gereklidir.

## Kontroller

`node tests/test_switch_ui.cjs`: durum filtreleri, sayfalama, eski veri gizleme ve boş arama için DOM davranış kontrolü. Bu kontrol gerçek tarayıcı görsel testi değildir.
