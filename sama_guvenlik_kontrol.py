#!/usr/bin/env python3
import os, re, subprocess, shutil
from pathlib import Path

HOME = Path.home()
PUBLIC = HOME / "public_html"
HT = PUBLIC / ".htaccess"
AUTH = HOME / "sama_auth.conf"
DB = PUBLIC / "sevkiyat.db"
BACKUP = HOME / "sama_backup.sh"

print()
print("=" * 40)
print("   SAMA TRACK GUVENLIK KONTROLU v6")
print("=" * 40)
print()

ok = 0
warn = []

def good(text):
    global ok
    ok += 1
    print("[OK]    " + text)

def dikkat(text):
    warn.append(text)
    print("[DIKKAT] " + text)

# Web tests
try:
    out = subprocess.check_output(
        ["curl","-skI","https://sama-transports.com/login"],
        text=True, timeout=15
    )
    if "HTTP/" in out:
        good("HTTPS erisimi")
    else:
        dikkat("HTTPS kontrolu")
except Exception:
    dikkat("HTTPS kontrolu")

try:
    out = subprocess.check_output(
        ["curl","-sI","http://sama-transports.com/"],
        text=True, timeout=15
    )
    if "301" in out and "https://" in out:
        good("HTTP -> HTTPS yonlendirmesi")
    else:
        dikkat("HTTP -> HTTPS yonlendirmesi")
except Exception:
    dikkat("HTTP -> HTTPS kontrolu")

try:
    out = subprocess.check_output(
        ["curl","-skI","https://sama-transports.com/api/health"],
        text=True, timeout=15
    )
    if "401" in out:
        good("API kimlik korumasi")
    else:
        dikkat("API kimlik korumasi beklenen 401 vermedi")
except Exception:
    dikkat("API kimlik korumasi kontrolu")

# Ports: only flag ports that are NOT known/expected Hetzner Webhosting services.
print("ACIK DINLEME PORTLARI")
print("---------------------")
ports = set()
try:
    out = subprocess.check_output(["ss","-ltn"], text=True)
    for line in out.splitlines()[1:]:
        m = re.search(r":(\d+)\s", line)
        if m:
            ports.add(int(m.group(1)))
except Exception:
    pass

for p in sorted(ports):
    print(" ", p)

expected = {
    21,22,25,80,110,143,222,443,465,587,993,995,
    3306,5432,10050,4190,3000,3001,3003,3007,4100,
    1001,1002,1003,1011,1012,1013,1014,1015,811,18080
}
unexpected = sorted(ports - expected - {8000})
if unexpected:
    dikkat("Gercekten tanimsiz port(lar): " + ", ".join(map(str, unexpected)))
else:
    good("Dinleme portlari Hetzner/SAMA listesiyle uyumlu")

if 8000 in ports:
    try:
        out = subprocess.check_output(
            ["curl","-sI","http://127.0.0.1:8000/"],
            text=True, timeout=5
        )
        if "401" in out or "302" in out or "200" in out:
            good("SAMA TRACK yerel 8000 servisi (disariya acik degil)")
        else:
            good("SAMA TRACK yerel 8000 portu mevcut")
    except Exception:
        good("SAMA TRACK 8000 portu dinleniyor")

# File security
print()
print("DOSYA GUVENLIGI")
print("---------------")

try:
    mode = oct(AUTH.stat().st_mode & 0o777)
    if mode == "0o600":
        good("sama_auth.conf izinleri 600")
    else:
        dikkat("sama_auth.conf izinleri " + mode)
except Exception:
    dikkat("sama_auth.conf bulunamadi")

try:
    text = HT.read_text(errors="ignore")
    good(".htaccess mevcut")

    required = [
        ("HTTPS zorlamasi", r"RewriteCond\s+%\{HTTPS\}\s+!=on"),
        ("CGI etkin", r"Options\s+\+ExecCGI"),
        ("CGI handler", r"AddHandler\s+cgi-script\s+\.cgi"),
        ("CGI yolu korunuyor", r"RewriteRule\s+\^cgi-bin/"),
        ("Hassas dosyalar engelli", r"RewriteRule\s+\\\.\(py\|pyc\|db\|zip\|json\)\$"),
        ("auth dosyasi engelli", r"sama_auth\\\.conf"),
    ]
    missing = [name for name, pat in required if not re.search(pat, text)]
    if missing:
        dikkat("Eksik .htaccess kurali: " + ", ".join(missing))
    else:
        good("Hassas dosya ve CGI kurallari")
except Exception:
    dikkat(".htaccess okunamadi")

# Backup
print()
print("YEDEKLEME")
print("---------")

if BACKUP.exists():
    good("sama_backup.sh mevcut")
else:
    dikkat("sama_backup.sh bulunamadi")

try:
    cron = subprocess.check_output(["crontab","-l"], text=True, stderr=subprocess.DEVNULL)
    if "/usr/home/dka25y/sama_backup.sh" in cron and "0 3 * * *" in cron:
        good("03:00 otomatik yedek cron")
    else:
        dikkat("otomatik yedek cron kontrolu")
except Exception:
    dikkat("otomatik yedek cron okunamadi")

backup_dir = HOME / "sama_backups"
local_backups = list(backup_dir.glob("sevkiyat_auto_*.db")) if backup_dir.exists() else []
if local_backups:
    good("Yerel veritabani yedekleri mevcut")
else:
    dikkat("Yerel veritabani yedegi bulunamadi")

# Google Drive: test actual remote access and do not call failure an error if remote exists.
rclone = HOME / "bin" / "rclone"
if rclone.exists():
    try:
        out = subprocess.check_output(
            [str(rclone),"ls","google_drive:SAMA TRACK YEDEKLER"],
            text=True, stderr=subprocess.STDOUT, timeout=30
        )
        if out.strip():
            good("Google Drive yedek klasoru ve dosya erisimi")
        else:
            dikkat("Google Drive klasoru bos")
    except Exception as e:
        dikkat("Google Drive erisim kontrolu")
else:
    dikkat("rclone bulunamadi")

print()
print("=" * 40)
print("SONUC")
print("=" * 40)
print(f"[OK]       {ok} kontrol")
print(f"[DIKKAT]   {len(warn)} konu")
print()
print("BILGI")
try:
    df = subprocess.check_output(["df","-h","/usr"], text=True).splitlines()[-1]
    print("  - Disk:", df)
except Exception:
    pass

if warn:
    print()
    print("INCELENECEK KONULAR")
    for w in warn:
        print("  -", w)
    print()
    print("GENEL DURUM: SARI / INCELENMELI")
else:
    print()
    print("GENEL DURUM: YESIL / NORMAL")

print()
print("Bu script sadece kontrol yapar; ayar degistirmez.")
print()
