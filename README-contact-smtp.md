# SAMA iletişim / teklif formu — Hetzner + Natro SMTP

## İnceleme ve kapsam

Başlangıç commit'i: `d8e919b882c75db1e74e53b26664450521a3e79b`
(`Publish contact page and service request links; defer email submission`).

- Güncel sayfa kökteki `contact.html`; `contact.js` submit olayını durduruyordu.
- Gönder ve dosya seçme düğmeleri kapalıydı; form `contact.html` adresine yönleniyordu.
- Hizmet sayfaları `contact.html?service=...` bağlantısıyla aynı forma geliyor.
- Canlı `contact.html` yanıtında `server: GitHub.com` görüldü. GitHub Pages yalnızca statik ön yüzü yayınlar.
- `public_html`, `sama-main-site/releases` ve `sama-track-hetzner` güncel formun kaynağı değildir; değiştirilmedi.

22 Eylül 2026 dağıtım kontrolünde mevcut paketin Cloud VPS değil **Hetzner Webhosting L** olduğu doğrulandı.
Python servisi bu pakete kuruldu ve bakım modunda çalışıyor. Natro DNS'inde `forms` A kaydı Hetzner'e eklendi;
konsoleH içinde ayrı `forms` alt alan adı ve mevcut wildcard sertifikası bağlandı.
**SMTP bağlantısı sağlayıcı tarafındaki uç nokta/sertifika sorununda bekliyor; kimlik doğrulaması ve gerçek gönderim yapılmadı. GitHub Pages değişiklikleri taslak PR'dadır.**

Natro'da `operations@sama-transports.com` bir **gruptur**, SMTP oturumu açabilen posta kutusu değildir.
Alıcı bu grup olarak sabit kalır; SMTP_USERNAME için gerçek bir `@sama-transports.com` posta kutusu gerekir.
Natro'nun [XMail kurulum belgesi](https://www.natro.com/hemendestek/bilgibankasi/xmail-standart-veya-profesyonel-e-posta-hesabi-outlooka-nasil-kurulur)
bu hesap türü için `mail.kurumsaleposta.com`, port `465`, SSL/TLS belirtir.

Canlı Hetzner testi: `mail.kurumsaleposta.com:465` bağlantıyı reddetti. `:587` STARTTLS yanıtı verdi,
ancak sertifika yalnızca `*.natrohost.com` / `natrohost.com` için geçerliydi; Python doğru biçimde
hostname uyuşmazlığıyla bağlantıyı kesti. Sunucu banner'ındaki `vsp-in3.natrohost.com:587` adresi de
farklı IP'ye çözümlenip bağlantıyı reddetti. Sertifika doğrulaması kapatılmadı ve hiçbir parola gönderilmedi.
Geçerli sertifikalı SMTP adresi/portu için 24 Eylül 2026 tarihinde Natro'ya **#3233738** numaralı destek talebi gönderildi; panelde **Yeni** durumu doğrulandı. Talebin kaynak metni `contact-api/NATRO-SUPPORT-DRAFT.md` içindedir. Sonraki destek yanıtı henüz kontrol edilemedi.

`forms.sama-transports.com` HTTPS üzerinden beklenen bakım yanıtını (503) ve doğru Origin CORS başlığını verdi.
`/healthz`, `/settings.json`, `/app.py` dışarıdan 404 döndü. ClamAV güncel imzayla EICAR testini reddetti.

## Mevcut Webhosting L dağıtımı

- Uygulama ve sanal ortam: `~/sama-contact/app`, `~/sama-contact/venv`.
- Sunucu ayarları: `~/sama-contact/settings.json`, sadece sahibi okuyabilir/yazabilir (`0600`).
- SQLite ve günlükler: `~/sama-contact/state`, `~/sama-contact/logs`; web kökü dışındadır.
- Gunicorn yalnızca `127.0.0.1:18091` üzerinde çalışır. Apache, `public_html/forms/.htaccess` üzerinden yönlendirir.
- `shared_wsgi.py`, ayar dosyasının sahibi/türünü/izinlerini kontrol eder. `enabled: false` durumunda form token'ı üretmez ve gönderim kabul etmez.
- `shared_manage.py`, cron tarafından her dakika özel dosya kilidiyle çalıştırılır; mevcut süreç varsa ikinci sunucu açmaz.
- Apache, istemciden gelen proxy başlıklarını temizler; mod_proxy'nin eklediği gerçek IP kullanılır. Kamuya açık `healthz` ve kod/ayar yolları kapalıdır.
- Sunucuda Python 3.13, libmagic, sanal ortam desteği ve erişilebilir ClamAV soketi doğrulandı. Kurulum sırasında test paketi ve gerçek temiz içerik taraması geçti.
- `deploy/install_shared_host.py` yalnızca yeni, boş kurulum için hazırlanmıştır. Mevcut dizini bulursa üzerine yazmaz.
- Paket, `install_shared_host.py` içindeki FILES listesini içerir; `contact.html` form alanı uyumluluk testi için repo kökünden alınır.
- `deploy/verify_shared_host.py`, parola kullanmadan Natro TLS/NOOP, HTTPS, CORS, kapalı dosya yolları, ClamAV sürümü ve EICAR reddini kontrol eder; mesaj göndermez.

Gönderimi açma sırası:

```bash
~/sama-contact/venv/bin/python ~/sama-contact/app/shared_smtp.py prepare --username GERCEK_HESAP@sama-transports.com
# smtp-password.txt dosyasına parolayı güvenli editörle girin; komut satırına yazmayın.
~/sama-contact/venv/bin/python ~/sama-contact/app/shared_smtp.py check
~/sama-contact/venv/bin/python ~/sama-contact/app/shared_smtp.py enable
```

Parola `~/sama-contact/smtp-password.txt` içinde (`0600`) tutulur. Sembolik bağlantı veya başkalarının okuyabildiği dosya reddedilir.
`check`, sertifikalı TLS/giriş/NOOP ve ClamAV kontrolü yapar; e-posta göndermez. `enable` aynı kontrollerden sonra servisi açıp yeniden yükler.
Ardından kontrollü gerçek gönderimi ve alıcı teslimini doğrulayın; son olarak taslak PR'ı yayınlayın.
Wildcard sertifikası panelde 5 Aralık 2026'ya kadar geçerlidir; harici Natro DNS kullanıldığı için konsoleH otomatik yenilemesi ayrıca doğrulanmalıdır.
Bu ortamda root, systemd veya ikinci Nginx kurulumu gerekmez. Aşağıdaki VPS talimatları alternatif dağıtım içindir.

## Değişiklikler

| Dosya | İşlev |
|---|---|
| `contact.html`, `contact.js` | Servis hazır olunca açılan form, dosya seçimi, fetch, erişilebilir durum/hata mesajları |
| `contact-api/app.py` | HTTPS/Origin kontrolü, imzalı form token'ı, alan doğrulaması ve API |
| `contact-api/mailer.py` | Natro SMTP, zorunlu TLS, sabit alıcı, güvenli Reply-To |
| `contact-api/attachments.py` | 5 MiB sınırı, uzantı + gerçek MIME, ClamAV, resimleri yeniden kodlama |
| `contact-api/store.py` | SQLite ile süreçler arasında ortak hız sınırı ve tekrar gönderim engeli |
| `contact-api/deploy/` | Webhosting L kurulum/Apache dosyaları; alternatif VPS için systemd/Nginx örnekleri |
| `contact-api/.env.example` | Gerçek parola içermeyen sunucu ayar örneği |
| `contact-api/check_smtp.py` | E-posta göndermeden TLS / giriş kontrolü |

Akış: GitHub Pages formu → HTTPS form API'si → doğrulanan SMTP TLS bağlantısı → Natro → `operations@sama-transports.com`.

## Güvenlik ve davranış

- Alıcı kodda sabittir. Kullanıcı To, Cc, Bcc, From veya SMTP sunucusunu değiştiremez.
- From, Natro'da oturum açılan `@sama-transports.com` hesabıdır. Müşteri adresi doğrulanıp yalnızca Reply-To yapılır.
- SMTP parolası ve rastgele CONTACT_SECRET yalnızca özel sunucu ayarındadır: Webhosting L'de `~/sama-contact/settings.json` ve `smtp-password.txt`, VPS örneğinde `/etc/sama-contact.env`. Frontend'e, GitHub'a, loglara veya dosya paketine gerçek sır girilmez.
- `587 + STARTTLS` ve `465 + implicit TLS` desteklenir; sertifika/hostname kontrolü kapatılamaz. Kullanılan port canlı bağlantı testiyle belirlenir. Düz metin SMTP'ye düşülmez.
- HTTPS Origin allowlist'i yalnızca apex ve www adreslerini kapsar. Çerez kullanılmaz. İmzalı token IP'ye (IPv6'da /64) ve Origin'e bağlıdır; bir saat geçerlidir.
- Origin/CORS ve token, botlara karşı kimlik doğrulama değildir. Honeypot ve kalıcı uygulama hız sınırları birlikte kullanılır; VPS örneğinde Nginx sınırı da vardır. Dağıtık saldırı sürerse CAPTCHA/WAF gerekir.
- Uygulamada IP başına 10 dakikada 3, günde 10 SMTP denemesi; tüm servis için saatte 60 sınırı vardır. Doğrulama ve token uçları ayrıca sınırlandırılır. Natro kotasına göre düşürün.
- Tek dosya: PDF / JPG / JPEG / PNG / UTF-8 TXT, en fazla **5 MiB (5.242.880 bayt)**. Toplam HTTP gövdesi 6 MiB. Form verisi ve parça sayısı da sınırlıdır.
- Tarayıcının MIME beyanına güvenilmez; libmagic gerçek içerik türünü denetler. TXT UTF-8 ve kontrol karakteri; PDF başlık/son işaret; resimler Pillow ile ayrıştırma ve piksel sınırı kontrolünden geçer.
- ClamAV taraması zorunludur. Virüs bulursa veya tarayıcı çalışmıyorsa dosya gönderilmez. Resimler ayrıca yeniden kodlanarak metadata ve sondaki ek veriler kaldırılır.
- Bu kontroller, PDF aktif içeriğinin tümünü kaldıran bir CDR sistemi değildir; antivirüs de mutlak güvence değildir. Ekler alıcı tarafında güvenilmeyen müşteri belgesi olarak açılmalıdır.
- Yüklenen belgeler web köküne veya kalıcı dosya deposuna yazılmaz. Nginx/WSGI geçici dosyaları işlem sonunda siler. SQLite yalnızca HMAC özetleri, rastgele referans, durum ve süreleri tutar; form metni, açık IP, müşteri adresi veya ek tutmaz.
- Aynı token + aynı içerik yeniden gönderilirse önceki başarı döner; ikinci e-posta çıkmaz. SMTP DATA sonrasında bağlantı koparsa sonuç belirsiz sayılır ve otomatik tekrar engellenir. Operasyon ekibi referans/Message-ID ile kontrol eder.
- SMTP kabulü gelen kutusuna kesin teslim değildir; Natro kuyruğu/spam/bounce durumu ayrıca takip edilir. Uygulama kuyruk/outbox tutmaz; SMTP kapalıysa kullanıcı hata görür ve formu korunur.

## Kurulum — Debian/Ubuntu üzerinde mevcut Hetzner sunucusu

Önce mevcut reverse proxy'nin Nginx olduğundan ve 8091'in boş olduğundan emin olun. SAMA TRACK'in 8080 portuna, veri dizinine veya çalışan proxy ayarlarına dokunmayın. Caddy/Traefik kullanılıyorsa aşağıdaki yeni sanal host'u mevcut proxy'ye uyarlayın; ikinci bir proxy ile 80/443'ü ele geçirmeyin.

1. DNS'e yalnızca `forms.sama-transports.com` için Hetzner IP'sine giden A kaydı ekleyin. IPv6 yapılandırılmadıysa AAAA eklemeyin. Ana site, CNAME ve MX kayıtlarını değiştirmeyin. Örnekte API doğrudan Nginx arkasındadır; araya CDN eklenirse güvenilir istemci IP yapılandırması ayrıca yapılmalıdır.
2. Paketleri ve kullanıcıyı hazırlayın (aşağıdaki kurulum komutları root ile):

```bash
apt-get update
apt-get install -y python3-venv libmagic1 clamav clamav-daemon certbot
useradd --system --user-group --home-dir /opt/sama-contact --shell /usr/sbin/nologin sama-contact
install -d -m 0755 /opt/sama-contact
install -d -m 0700 -o sama-contact -g sama-contact /var/lib/sama-contact
install -d -m 0755 /var/www/letsencrypt
```

`contact-api/` içeriğini `/opt/sama-contact/` altına kopyalayın. Tüm repoyu veya eski veritabanı/yedek dosyalarını sunucuya taşımayın. Kod root tarafından sahiplenilmeli; servis hesabına kod yazma izni verilmemelidir.

```bash
python3 -m venv /opt/sama-contact/.venv
/opt/sama-contact/.venv/bin/pip install -r /opt/sama-contact/requirements.txt
install -m 0600 -o root -g root /opt/sama-contact/.env.example /etc/sama-contact.env
```

3. `/etc/sama-contact.env` dosyasını sunucudaki güvenli editörle doldurun:

| Ayar | Değer |
|---|---|
| SMTP_HOST | **Natro panelinin bu hesaba verdiği, TLS sertifikasıyla eşleşen giden posta sunucusu** |
| SMTP_PORT / SMTP_SECURITY | `587` / `starttls`; Natro'nun bu hesapta STARTTLS sunduğunu doğrulayın |
| SMTP_USERNAME | Gerçek bir `@sama-transports.com` posta kutusu; `operations` grup hesabı kullanılamaz |
| SMTP_PASSWORD | Yalnızca sunucuda girilecek hesap parolası |
| CONTACT_SECRET | `python3 -c 'import secrets; print(secrets.token_hex(32))'` ile üretilen değer |

Natro belgesindeki SMTP hostname'i `mail.kurumsaleposta.com` adresidir; bu hesabın canlı TLS doğrulamasını henüz geçmemiştir. Natro'nun teyit edeceği, sertifikasıyla eşleşen uç noktayı kullanın. Parolayı sohbete, PR'a veya komut satırına yazmayın. systemd EnvironmentFile biçiminde gereken özel karakterleri tırnaklayın; bu dosyayı `source` ile çalıştırmayın.

Natro SMTP için SPF/DKIM/DMARC ve gönderici yetkisini panelde doğrulayın; var olan DNS kayıtlarını körlemesine değiştirmeyin. Hetzner Cloud varsayılan olarak 25/465'i engeller, 587'yi engellemez. Natro yalnızca 465 sunuyorsa önce Hetzner hesabında port erişimi açılmalı, ardından `ssl/465` seçilmelidir.

4. ClamAV'ı yapılandırın. Dağıtımın `/etc/clamav/clamd.conf` dosyasındaki mevcut ayarları düzenleyin; dosyanın tamamını değiştirmeyin:

```text
LocalSocket /run/clamav/clamd.ctl
LocalSocketGroup clamav
LocalSocketMode 660
StreamMaxLength 6M
AlertEncrypted yes
AlertExceedsMax yes
```

`clamav-freshclam` imza güncellemelerinin başarılı olduğundan emin olun. Virüs veritabanı yokken servisin hazır sayılmaması gerekir. Daemon `PING`, güncel `VERSION` ve EICAR testinin reddedilmesini Hetzner üzerinde doğrulayın. ClamAV için yeterli RAM ayırın; 512M sınırı sadece Python servisine aittir, ClamAV'a değil.

```bash
systemctl enable --now clamav-freshclam
systemctl restart clamav-daemon
install -m 0644 /opt/sama-contact/deploy/sama-contact.service /etc/systemd/system/sama-contact.service
systemctl daemon-reload
systemctl enable --now sama-contact
curl --fail -H 'Host: forms.sama-transports.com' http://127.0.0.1:8091/healthz
```

5. TLS sertifikası için önce `nginx-bootstrap.conf` içeriğini yeni bir site dosyası olarak mevcut Nginx'e ekleyin. `nginx -t` başarılı olunca reload edin. Örneğin:

```bash
install -m 0644 /opt/sama-contact/deploy/nginx-bootstrap.conf /etc/nginx/sites-available/sama-contact
ln -s /etc/nginx/sites-available/sama-contact /etc/nginx/sites-enabled/sama-contact
nginx -t
systemctl reload nginx
certbot certonly --webroot -w /var/www/letsencrypt -d forms.sama-transports.com
install -m 0644 /opt/sama-contact/deploy/nginx.conf /etc/nginx/sites-available/sama-contact
nginx -t
systemctl reload nginx
```

Sertifika yenilenince Nginx'in reload edilmesini certbot deploy hook ile sağlayın. Güvenlik duvarında yalnızca gerekli SSH/HTTP/HTTPS erişimleri olmalı; **8091 herkese açılmamalıdır**. Gösterilen ProxyFix yalnızca bir güvenilir Nginx proxy'si için geçerlidir; X-Forwarded-For Nginx tarafından gelen değer yerine `$remote_addr` ile yazılır.

6. E-posta göndermeyen SMTP kontrolü:

```bash
systemd-run --wait --pipe --collect --uid=sama-contact \
  --property=EnvironmentFile=/etc/sama-contact.env \
  --working-directory=/opt/sama-contact \
  /opt/sama-contact/.venv/bin/python /opt/sama-contact/check_smtp.py
```

TLS sertifikası hatasını çözmek için doğrulamayı kapatmayın; doğru SMTP hostname'ini veya güven zincirini düzeltin. Bu kontrol mesaj teslimini değil bağlantı, TLS ve oturum açmayı doğrular.

7. API hazır olduğunda `contact.html` ve `contact.js` değişikliklerini GitHub Pages'e yayınlayın. Alt alan adı değiştiyse HTML'deki **action ve data-api-base**, env/API_HOST ve Nginx server_name/sertifika yollarını birlikte değiştirin. Eski HTML ile yeni JS'nin karışmaması için CDN önbelleğini/sert yenilemeyi kontrol edin. Mevcut HTML/CSP kısıtları eklenirse `connect-src` içinde form API adresine izin verin. Repodaki eski `public_html/.htaccess` GitHub Pages üzerinde uygulanmaz.

## Test ve kabul

```bash
cd contact-api
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt pytest
PYTHONPATH=. .venv/bin/pytest -q
node --check ../contact.js
npm install --prefix tests --no-save jsdom@30.1.1
node --test tests/frontend.test.cjs
```

Hazırlama ortamındaki doğrulama sonuçları `contact-api/TEST-RESULTS.md` dosyasındadır. SMTP ve antivirüs testlerinde canlı hesap/daemon kullanılmadığı durumlar orada açıkça belirtilir.

Canlıya alma kabulü: iki Origin'den preflight/token, eksiz test talebi, her izinli türden örnek ek, 5 MiB üstü/yanlış tür/virüs testi reddi, SMTP hatasında formun korunması ve aynı talebin tekrarında tek e-posta. Gerçek test e-postasının operasyon kutusunda görülmesi ayrıca doğrulanmalıdır. `/healthz` yalnızca uygulamanın çalıştığını söyler; SMTP/ClamAV sağlığını kanıtlamaz.

Günlüklerde müşteri verisi bulunmamalı; `journalctl -u sama-contact` sadece referans ve redakte durumları göstermelidir. SQLite yazma hatası, disk doluluğu, tarayıcı arızası ve SMTP retleri izlenmelidir. Veritabanı resetlenirse hız/tekrar koruması kaybolur. Temizlik istek geldikçe çalışır; düşük trafikte süre geçmiş özet kayıtlar bir sonraki isteğe kadar kalabilir.

Geri alma: ön yüzü başlangıç commit'indeki kapalı form sürümüne geri alın, sonra yalnızca `sama-contact` servisini durdurun. SAMA TRACK ve ana site DNS'ini değiştirmeyin. İşlemdeki SMTP talepleri varsa önce durumlarını kontrol edin.

## Kaynaklar

- [GitHub Pages statik barındırma](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages)
- [Hetzner SMTP port politikası](https://docs.hetzner.com/cloud/servers/faq/#why-can-i-not-send-any-mails-from-my-server)
- [Python smtplib ve TLS](https://docs.python.org/3/library/smtplib.html)
- [Flask istek kaynak sınırları](https://flask.palletsprojects.com/en/stable/web-security/)
- [Flask güvenilir reverse proxy yapılandırması](https://flask.palletsprojects.com/en/stable/deploying/proxy_fix/)
- [OWASP dosya yükleme kontrolleri](https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html)
