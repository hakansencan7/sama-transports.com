import kolaybi_auto_mapping_patch as base

app = base.app
core = base.core
kdb = base.kdb
html = core.HTML
sync = base.sync
webmod = sync.base

# Complete the fixed KolayBi expense catalogue. These are mappings only;
# actual KolayBi identity is always the product_id selected/mapped in master data.
c = kdb()
try:
    for row in [
        ('PORT_FEE', 'PORT FEE', 'PORT FEE', 'ADET'),
        ('DOCK_FEE', 'DOCK FEE', 'DOCK FEE', 'ADET'),
        ('SONAR', 'SONAR', 'SONAR', 'ADET'),
    ]:
        c.execute('''INSERT OR IGNORE INTO products(code,name_tr,name_en,unit,is_active)
                     VALUES(?,?,?,?,1)''', row)
    c.commit()
finally:
    c.close()

# Strong aliases for the newly completed expense types.
base.FIXED_PRODUCT_ALIASES.update({
    'PORT_FEE': ['PORTFEE', 'PORT FEE', 'LIMAN', 'LIMANUCRETI'],
    'DOCK_FEE': ['DOCKFEE', 'DOCK FEE', 'DOCK', 'RIHTIM', 'RIHTIMUCRETI'],
    'SONAR': ['SONAR'],
})

_original_preview = webmod.kolaybi_preview


def _fixed_product(code):
    c = kdb()
    try:
        r = c.execute('SELECT * FROM products WHERE UPPER(code)=UPPER(?) AND is_active=1', (code,)).fetchone()
        return dict(r) if r else {}
    finally:
        c.close()


def _extra_item(code, amount, description=''):
    p = _fixed_product(code)
    return {
        'code': code,
        'name': (p.get('name_tr') or code) + ' / ' + (p.get('name_en') or code),
        'product_id': p.get('product_id', ''),
        'quantity': 1,
        'unit_price': float(amount or 0),
        'total': float(amount or 0),
        'description': description,
    }


def _preview_complete(scna: str):
    pv = _original_preview(scna)
    c = core.db()
    try:
        tr = c.execute('''SELECT port_fee,dock_fee,sonar,exit_other
                          FROM trips WHERE UPPER(TRIM(scna))=UPPER(TRIM(?))''',
                       (str(scna or '').strip(),)).fetchone()
    finally:
        c.close()

    if tr:
        existing = pv.setdefault('items', [])
        if float(tr['port_fee'] or 0) > 0:
            existing.append(_extra_item('PORT_FEE', tr['port_fee'], 'PORT FEE'))
        if float(tr['dock_fee'] or 0) > 0:
            existing.append(_extra_item('DOCK_FEE', tr['dock_fee'], 'DOCK FEE'))
        if float(tr['sonar'] or 0) > 0:
            existing.append(_extra_item('SONAR', tr['sonar'], 'SONAR'))
        # Exit OTHER uses the same generic OTHER product card as Entry OTHER rows;
        # its description keeps the business meaning visible on the document.
        if float(tr['exit_other'] or 0) > 0:
            p = _fixed_product('OTHER')
            existing.append({
                'code': 'OTHER',
                'name': (p.get('name_tr') or 'DİĞER') + ' / ' + (p.get('name_en') or 'OTHER'),
                'product_id': p.get('product_id', ''),
                'quantity': 1,
                'unit_price': float(tr['exit_other'] or 0),
                'total': float(tr['exit_other'] or 0),
                'description': 'ÇIKIŞ DİĞER GİDER / EXIT OTHER EXPENSE',
            })

    missing = sorted({str(x.get('code') or '') for x in pv.get('items', [])
                      if not str(x.get('product_id') or '').strip()})
    pv['missing_product_codes'] = missing
    contact = pv.get('contact') or {}
    project = pv.get('project') or {}
    pv['ready'] = bool(pv.get('items')) and not missing \
        and bool(str(contact.get('contact_id') or '').strip()) \
        and bool(str(project.get('project_id') or '').strip())
    return pv


# Replace the callable used both by the API preview route and by the real-send engine.
webmod.kolaybi_preview = _preview_complete
for route in app.routes:
    if getattr(route, 'path', None) == '/api/kolaybi/preview/{scna}' and 'GET' in (getattr(route, 'methods', set()) or set()):
        route.endpoint = _preview_complete
        if getattr(route, 'dependant', None) is not None:
            route.dependant.call = _preview_complete
        break

# Try safe auto-mapping against already synchronized KolayBi products.
try:
    COMPLETE_MAP = base.auto_map_fixed_products()
except Exception as e:
    COMPLETE_MAP = {'mapped': [], 'ambiguous': [], 'missing': [], 'error': str(e)}

core.HTML = html
print('[SAMA] KolayBi complete expense mapping active: PORT_FEE + DOCK_FEE + SONAR + EXIT_OTHER')
