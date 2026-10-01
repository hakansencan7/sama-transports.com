# Natro destek talebi — gönderildi

24 Eylül 2026 tarihinde Natro müşteri panelinden **#3233738** numarasıyla gönderildi.
Gönderim sonrasında panel durumu **Yeni** olarak doğrulandı. Sonraki destek yanıtı henüz kontrol edilemedi.
Aşağıdaki metin, gönderilen talebin kaynak taslağıdır.

**Konu:** sama-transports.com XMail SMTP için geçerli TLS uç noktası

Merhaba,

sama-transports.com alan adımızın web formunu, Hetzner üzerindeki Python servisten Natro SMTP ile göndermek istiyoruz.
22 Eylül 2026 tarihinde, kaynak sunucu IP'si 167.235.125.52 üzerinden yaptığımız testlerde:

- Belgelerinizde verilen `mail.kurumsaleposta.com:465` bağlantıyı reddediyor.
- `mail.kurumsaleposta.com:587` STARTTLS sunuyor ancak sertifikanın SAN alanı yalnızca `*.natrohost.com` ve `natrohost.com` içeriyor. Hostname doğrulaması hata kodu 62 ile başarısız oluyor.
- Bu bağlantı `94.73.187.200` IP'sine gidiyor ve banner `vsp-in3.natrohost.com ESMTP` gösteriyor.
- Banner'daki `vsp-in3.natrohost.com` adresi ise `89.19.13.6` IP'sine çözümleniyor; 587 bağlantısı reddediliyor.

XMail Standart posta hesabımız için dış sunucudan erişilebilen, sertifikası hostname ile eşleşen SMTP adresini ve TLS portunu teyit edebilir misiniz? Gerekirse sertifika/servis yapılandırmasını düzeltmenizi rica ederiz.

Sertifika doğrulamasını kapatmadan STARTTLS/587 veya implicit TLS/465 kullanacağız. Henüz AUTH veya mesaj gönderimi yapılmadı. Parola paylaşımı gerekmiyor.

Teşekkürler.
