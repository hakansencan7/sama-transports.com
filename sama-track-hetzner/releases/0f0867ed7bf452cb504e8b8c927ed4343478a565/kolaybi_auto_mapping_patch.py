import re
import kolaybi_connection_settings_patch as base

app = base.app
core = base.core
sync = base.sync
kdb = base.kdb
html = core.HTML


def _norm(v):
    s = str(v or '').upper()
    s = s.replace('İ','I').replace('Ş','S').replace('Ğ','G').replace('Ü','U').replace('Ö','O').replace('Ç','C')
    return re.sub(r'[^A-Z0-9]+', '', s)


# Strong aliases only. We auto-link only when exactly one API product matches.
FIXED_PRODUCT_ALIASES = {
    'WEIGHBRIDGE': ['WEIGHBRIDGE', 'WEIGHTBRIDGE', 'WEIGHTBRIGE', 'KANTAR', 'JISRALOZN'],
    'PARKING': ['PARKING', 'PARK', 'OTOPARK'],
    'WAITING': ['WAITING', 'BEKLEME'],
    'OTHER': ['OTHER', 'DIGER', 'DIGGER'],
    'ROAD_FUEL': ['ROADFUEL', 'YOLDA MAZOT', 'YOLMAZOT', 'DIESEL', 'MAZOT'],
}


def auto_map_fixed_products():
    c = kdb()
    mapped = []
    ambiguous = []
    missing = []
    try:
        api_rows = [dict(r) for r in c.execute("SELECT * FROM products WHERE product_id<>'' AND code LIKE 'API_%'").fetchall()]
        for fixed_code, aliases in FIXED_PRODUCT_ALIASES.items():
            current = c.execute('SELECT * FROM products WHERE UPPER(code)=UPPER(?)', (fixed_code,)).fetchone()
            if current and str(current['product_id'] or '').strip():
                continue
            alias_norms = [_norm(x) for x in aliases if _norm(x)]
            candidates = []
            for row in api_rows:
                hay = _norm(' '.join([str(row.get('name_tr') or ''), str(row.get('name_en') or ''), str(row.get('note') or '')]))
                if any(a and a in hay for a in alias_norms):
                    candidates.append(row)
            # dedupe by product id
            uniq = {}
            for row in candidates:
                uniq[str(row.get('product_id') or '')] = row
            candidates = [x for k, x in uniq.items() if k]
            if len(candidates) == 1:
                row = candidates[0]
                c.execute('''UPDATE products SET product_id=?, note=?, updated_at=CURRENT_TIMESTAMP
                             WHERE UPPER(code)=UPPER(?)''',
                          (str(row.get('product_id') or ''),
                           'AUTO MAP -> ' + str(row.get('name_tr') or row.get('name_en') or row.get('code') or ''),
                           fixed_code))
                mapped.append({'code': fixed_code, 'product_id': str(row.get('product_id') or ''), 'name': str(row.get('name_tr') or row.get('name_en') or '')})
            elif len(candidates) > 1:
                ambiguous.append({'code': fixed_code, 'matches': [{'product_id': str(x.get('product_id') or ''), 'name': str(x.get('name_tr') or x.get('name_en') or '')} for x in candidates[:10]]})
            else:
                missing.append(fixed_code)
        c.commit()
    finally:
        c.close()
    return {'mapped': mapped, 'ambiguous': ambiguous, 'missing': missing}


# Run once on startup so already-synced products (like WEIGHT BRIGE) are linked immediately.
try:
    STARTUP_MAP = auto_map_fixed_products()
except Exception as e:
    STARTUP_MAP = {'mapped': [], 'ambiguous': [], 'missing': [], 'error': str(e)}


# Wrap product sync so every future sync also refreshes fixed mappings.
_original_sync_products = sync._sync_products

def _sync_products_with_mapping():
    count, errors = _original_sync_products()
    result = auto_map_fixed_products()
    if result.get('ambiguous'):
        errors = list(errors or []) + ['Auto-map belirsiz: ' + ', '.join(x['code'] for x in result['ambiguous'])]
    return count, errors

sync._sync_products = _sync_products_with_mapping


@app.post('/api/kolaybi/auto-map-products')
def kb_auto_map_products():
    sync.base._admin_required()
    return {'ok': True, **auto_map_fixed_products()}


# Add a manual re-run button near product sync controls; no new script block.
old = '<button class="btn secondary" onclick="kbSync(\'products\')">ÜRÜNLERİ ÇEK</button>'
new = old + '<button class="btn secondary" onclick="kbAutoMapProducts()">SABİT ÜRÜNLERİ EŞLEŞTİR</button>'
if old in html and 'kbAutoMapProducts()' not in html:
    html = html.replace(old, new, 1)

helper = r'''
async function kbAutoMapProducts(){
  const s=document.getElementById('kbSyncState');if(s)s.textContent='EŞLEŞTİRİLİYOR...';
  try{
    const r=await api('/api/kolaybi/auto-map-products',{method:'POST'});
    await loadKolaybiMaster();
    const m=(r.mapped||[]).map(x=>x.code+' → '+x.product_id).join(', ');
    const a=(r.ambiguous||[]).map(x=>x.code).join(', ');
    if(s)s.innerHTML='<span class="kb-ready">'+kbEsc(m||'Yeni eşleşme yok')+'</span>'+(a?' <span class="kb-missing">Belirsiz: '+kbEsc(a)+'</span>':'');
  }catch(e){if(s)s.innerHTML='<span class="kb-missing">'+kbEsc(e.message||e)+'</span>';}
}
'''
marker = 'async function kbSyncAll(){'
if marker in html and 'async function kbAutoMapProducts' not in html:
    html = html.replace(marker, helper + '\n' + marker, 1)

core.HTML = html
print(f"[SAMA] KolayBi fixed product auto-map active: mapped={len(STARTUP_MAP.get('mapped',[]))}, ambiguous={len(STARTUP_MAP.get('ambiguous',[]))}")
