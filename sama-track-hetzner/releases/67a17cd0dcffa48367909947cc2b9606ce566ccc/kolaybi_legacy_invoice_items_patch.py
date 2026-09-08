import kolaybi_contact_resolution_v3_perf_fix_patch as perf
import kolaybi_auto_mapping_patch as automap

app = perf.app
core = perf.core
kdb = perf.kdb
v3 = perf.v3
webmod = v3.base.ui.base.webmod


def _txt(v):
    return str(v or '').strip()


def _num(v):
    try:
        return float(v or 0)
    except Exception:
        return 0.0


# These codes/aliases are copied from the proven desktop/Streamlit INVOICE logic.
# Local names are labels only; the real KolayBi identity remains product_id.
c = kdb()
try:
    for row in [
        ('PREMIUM','PREMIUM / HARCIRAH','PREMIUM / ALLOWANCE','ADET'),
        ('BASRA_RESMI','BASRA MAZOT RESMİ','BASRA OFFICIAL FUEL','LT'),
        ('BASRA_TICARI','BASRA MAZOT TİCARİ','BASRA COMMERCIAL FUEL','LT'),
        ('BAGHDAD_RESMI','BAGHDAD MAZOT RESMİ','BAGHDAD OFFICIAL FUEL','LT'),
    ]:
        c.execute('''INSERT OR IGNORE INTO products(code,name_tr,name_en,unit,is_active)
                     VALUES(?,?,?,?,1)''',row)
    c.commit()
finally:
    c.close()

automap.FIXED_PRODUCT_ALIASES.update({
    'PREMIUM':['PREMIUM','HARCIRAH','HARCIIRAH','PRIM','PRIMVEHARCIRAH','PREMIUMANDSUBSISTENCE'],
    'BASRA_RESMI':['BASRARESMI','BASRAMAZOTRESMI','DIZELYAKITRESMIBASRA','RESMIBASRA'],
    'BASRA_TICARI':['BASRATICARI','BASRAMAZOTTICARI','DIZELYAKITTICARI','TICARI'],
    'BAGHDAD_RESMI':['BAGHDADRESMI','BAGDATRESMI','BAGHDADMAZOTRESMI','DIZELYAKITRESMIBAGDAT'],
})


def _product(code):
    c = kdb()
    try:
        row = c.execute('SELECT * FROM products WHERE UPPER(code)=UPPER(?) AND is_active=1',(code,)).fetchone()
        return dict(row) if row else {}
    finally:
        c.close()


def _money_item(code, amount, description):
    p = _product(code)
    return {
        'code':code,
        'name':(_txt(p.get('name_tr')) or code)+' / '+(_txt(p.get('name_en')) or code),
        'product_id':_txt(p.get('product_id')),
        'quantity':1,
        'unit_price':_num(amount),
        'total':_num(amount),
        'description':description,
    }


def _fuel_item(code, liters, total, description):
    p = _product(code)
    liters = _num(liters); total = _num(total)
    qty = liters if liters > 0 else 1
    return {
        'code':code,
        'name':(_txt(p.get('name_tr')) or code)+' / '+(_txt(p.get('name_en')) or code),
        'product_id':_txt(p.get('product_id')),
        'quantity':qty,
        'unit_price':(total/qty if qty else total),
        'total':total,
        'description':description,
    }


_original_preview = webmod.kolaybi_preview


def _preview_with_legacy_invoice_items(scna):
    pv = _original_preview(scna)
    c = core.db()
    try:
        tr = c.execute('''SELECT exit_allowance,exit_premium,
                                 exit_official_fuel_liters,exit_official_fuel_total,
                                 exit_commercial_fuel_liters,exit_commercial_fuel_total,
                                 exit_baghdad_fuel_liters,exit_baghdad_fuel_total
                          FROM trips WHERE UPPER(TRIM(scna))=UPPER(TRIM(?))''',(_txt(scna),)).fetchone()
    finally:
        c.close()
    if tr:
        items = pv.setdefault('items',[])
        # Old INVOICE E/F columns both used the PREMIUM product ID but stayed as separate lines.
        if _num(tr['exit_allowance']) > 0:
            items.append(_money_item('PREMIUM',tr['exit_allowance'],'HARCIRAH / ALLOWANCE'))
        if _num(tr['exit_premium']) > 0:
            items.append(_money_item('PREMIUM',tr['exit_premium'],'PREMIUM / PRIM'))
        if _num(tr['exit_official_fuel_total']) > 0:
            items.append(_fuel_item('BASRA_RESMI',tr['exit_official_fuel_liters'],tr['exit_official_fuel_total'],'BASRA RESMİ MAZOT / OFFICIAL FUEL'))
        if _num(tr['exit_commercial_fuel_total']) > 0:
            items.append(_fuel_item('BASRA_TICARI',tr['exit_commercial_fuel_liters'],tr['exit_commercial_fuel_total'],'BASRA TİCARİ MAZOT / COMMERCIAL FUEL'))
        if _num(tr['exit_baghdad_fuel_total']) > 0:
            items.append(_fuel_item('BAGHDAD_RESMI',tr['exit_baghdad_fuel_liters'],tr['exit_baghdad_fuel_total'],'BAGHDAD RESMİ MAZOT / OFFICIAL FUEL'))
    missing = sorted({_txt(x.get('code')) for x in pv.get('items',[]) if not _txt(x.get('product_id'))})
    pv['missing_product_codes'] = missing
    return pv


webmod.kolaybi_preview = _preview_with_legacy_invoice_items
for route in app.routes:
    if getattr(route,'path',None) == '/api/kolaybi/preview/{scna}' and 'GET' in (getattr(route,'methods',set()) or set()):
        route.endpoint = _preview_with_legacy_invoice_items
        if getattr(route,'dependant',None) is not None:
            route.dependant.call = _preview_with_legacy_invoice_items
        break

# Try mapping immediately against products already in the persistent master DB.
try:
    LEGACY_MAP = automap.auto_map_fixed_products()
except Exception as e:
    LEGACY_MAP = {'mapped':[],'ambiguous':[],'missing':[],'error':str(e)}

print('[SAMA] KolayBi legacy INVOICE items active: allowance + premium + Basra official/commercial + Baghdad official fuel')
