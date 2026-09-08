from pathlib import Path
import re

src=Path('app.py').read_text(encoding='utf-8')
# Capture user-facing Turkish-ish strings from HTML/JS/Python literals.
# This is intentionally broad. We will translate only inventory items, not code identifiers/data.
items=set()
patterns=[
    r'>([^<>\n]{2,180})<',
    r'placeholder=["\']([^"\']{2,180})["\']',
    r'title=["\']([^"\']{2,180})["\']',
    r'aria-label=["\']([^"\']{2,180})["\']',
    r'(["\'])([^"\'\n]{2,180})\1',
]
for pat in patterns:
    for m in re.finditer(pat, src, flags=re.S):
        val=m.group(2) if len(m.groups())>1 else m.group(1)
        val=re.sub(r'\s+',' ',val).strip()
        if not val or len(val)>180:
            continue
        if re.search(r'[çğıöşüÇĞİÖŞÜ]', val) or re.search(r'\b(Araç|Şoför|Sevkiyat|Çıkış|Giriş|Bakım|Kasa|Avans|Rapor|Kullanıcı|Yetki|Gemi|Yükleme|Mazot|Yakıt|Müşteri|Bölge|Tarih|Tutar|Açıklama|Durum|Kaydet|Sil|Düzenle|Bekle|Toplam|Eksik|Fazla|Hata|Uyarı|Başarılı|İşlem|Göster|Ekle|Kaldır|Seç|Arama|Filtre|Gün|Saat|Nakit|Fatura|Fiş)\b', val, flags=re.I):
            # Skip obvious source/code noise.
            if val.startswith(('SELECT ','INSERT ','UPDATE ','DELETE ','CREATE TABLE','ALTER TABLE','PRAGMA ','http://','https://','/api/')):
                continue
            if any(x in val for x in ['{','}','=>','===','&&','||','function ','const ','let ','var ','class=','style=']):
                continue
            items.add(val)

out=Path('tools/i18n_inventory_v6.txt')
out.write_text('\n'.join(sorted(items, key=lambda x:(x.casefold(),x)))+'\n',encoding='utf-8')
print('inventory_count',len(items))
