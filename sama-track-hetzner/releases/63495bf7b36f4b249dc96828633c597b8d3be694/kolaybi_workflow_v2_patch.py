import json
import re
import time
from fastapi import Request, HTTPException

import kolaybi_single_transaction_ui_patch as ui
import kolaybi_sync_patch as sync
import kolaybi_send_patch as sender
import kolaybi_auto_mapping_patch as automap

app = ui.app
core = ui.core
kdb = ui.kdb
html = core.HTML


def _txt(v):
    return str(v or '').strip()


def _norm(v):
    s = _txt(v).upper()
    s = s.replace('İ','I').replace('Ş','S').replace('Ğ','G').replace('Ü','U').replace('Ö','O').replace('Ç','C')
    return re.sub(r'[^A-Z0-9]+', '', s)


def _num(v):
    try:
        return float(v or 0)
    except Exception:
        return 0.0


def _fmt(v):
    s = f'{_num(v):.6f}'.rstrip('0').rstrip('.')
    return s or '0'


def _addcol(c, table, col, definition):
    cols = {str(r['name']) for r in c.execute(f'PRAGMA table_info({table})').fetchall()}
    if col not in cols:
        c.execute(f'ALTER TABLE {table} ADD COLUMN {col} {definition}')


# Keep KolayBi integration data physically separate from shipment/accounting DBs.
c = kdb()
try:
    _addcol(c, 'associates', 'full_name', "TEXT DEFAULT ''")
    _addcol(c, 'associates', 'associate_type', "TEXT DEFAULT ''")
    _addcol(c, 'associates', 'source_code', "TEXT DEFAULT ''")
    c.executescript('''
    CREATE TABLE IF NOT EXISTS sale_product_aliases(
      alias TEXT PRIMARY KEY COLLATE NOCASE,
      alias_key TEXT NOT NULL DEFAULT '',
      product_id TEXT NOT NULL DEFAULT '',
      product_name TEXT NOT NULL DEFAULT '',
      unit TEXT NOT NULL DEFAULT 'KG',
      note TEXT DEFAULT '',
      updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    CREATE UNIQUE INDEX IF NOT EXISTS idx_sale_product_alias_key ON sale_product_aliases(alias_key);
    CREATE TABLE IF NOT EXISTS sent_documents_v2(
      scna TEXT NOT NULL COLLATE NOCASE,
      doc_kind TEXT NOT NULL COLLATE NOCASE,
      document_id TEXT DEFAULT '',
      endpoint TEXT DEFAULT '',
      payload_json TEXT DEFAULT '',
      response_json TEXT DEFAULT '',
      tags_json TEXT DEFAULT '',
      sent_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      PRIMARY KEY(scna,doc_kind)
    );
    ''')
    c.commit()
finally:
    c.close()


def _rid(row):
    if not isinstance(row, dict):
        return ''
    for key in ('id','contact_id','associate_id','product_id','project_id','tag_id'):
        v = _txt(row.get(key))
        if v:
            return v
    return ''


def _display_assoc(row):
    if not isinstance(row, dict):
        return ''
    full = _txt(row.get('full_name') or row.get('display_name'))
    if full:
        return full
    name = _txt(row.get('name') or row.get('title') or row.get('company_name') or row.get('associate_name'))
    surname = _txt(row.get('surname') or row.get('last_name'))
    if name and surname and _norm(surname) not in _norm(name):
        return f'{name} {surname}'.strip()
    return name or surname


def _address_id(row):
    if not isinstance(row, dict):
        return ''
    for key in ('address_id','default_address_id','billing_address_id','invoice_address_id','associate_address_id','contact_address_id'):
        v = _txt(row.get(key))
        if v:
            return v

    def walk(v):
        if isinstance(v, dict):
            direct = _rid(v)
            if direct:
                return direct
            for k in ('address','addresses','default_address','billing_address','invoice_address','associate_address','associate_addresses','contact_address','contact_addresses'):
                if k in v:
                    got = walk(v.get(k))
                    if got:
                        return got
        elif isinstance(v, list):
            preferred, rest = [], []
            for item in v:
                if not isinstance(item, dict):
                    continue
                typ = _txt(item.get('address_type') or item.get('type')).lower()
                (preferred if typ in ('invoice','billing','default','fatura') else rest).append(item)
            for item in preferred + rest:
                got = _rid(item) or walk(item)
                if got:
                    return got
        return ''

    for key in ('address','addresses','default_address','billing_address','invoice_address','associate_address','associate_addresses','contact_address','contact_addresses'):
        got = walk(row.get(key))
        if got:
            return got
    data = row.get('data')
    return _address_id(data) if isinstance(data, dict) else ''


def _plate(row):
    if not isinstance(row, dict):
        return ''
    for key in ('full_name','display_name','name','title','company_name','associate_name','code','associate_code','contact_code','surname'):
        m = re.search(r'\d{2}[A-Z]\d{4,6}', _txt(row.get(key)).upper())
        if m:
            return m.group(0)
    return ''


def _paged(path, max_pages=60, page_size=100):
    out, seen, errors = [], set(), []
    for page in range(1, max_pages + 1):
        rows = []
        for params in ({'page':page,'per_page':page_size},{'page':page,'limit':page_size}):
            try:
                rows = sync._rows(sync._get(path, params))
                if rows:
                    break
            except Exception as e:
                errors.append(str(e))
        if not rows:
            if page == 1:
                try:
                    rows = sync._rows(sync._get(path, {}))
                except Exception as e:
                    errors.append(str(e))
            if not rows:
                break
        new = 0
        for row in rows:
            key = _rid(row) or _norm(_display_assoc(row) + '|' + _txt(row.get('code')))
            if not key or key in seen:
                continue
            seen.add(key)
            out.append(row)
            new += 1
        if new == 0 or len(rows) < page_size:
            break
    return out, errors


def _sync_associates_v2():
    rows, errors = _paged('associates')
    c = kdb()
    count = 0
    try:
        for row in rows:
            cid = _rid(row)
            if not cid:
                continue
            display = _display_assoc(row)
            code = _txt(row.get('code') or row.get('associate_code') or row.get('contact_code'))
            plate = _plate(row)
            aid = _address_id(row)
            assoc_type = _txt(row.get('associate_type') or row.get('type') or row.get('contact_type'))
            key = (code or display or cid).upper()
            if not key:
                continue
            old = c.execute("SELECT key FROM associates WHERE contact_id=? AND note LIKE 'KolayBi API%' LIMIT 1", (cid,)).fetchone()
            if old and _txt(old['key']).upper() != key:
                old_key = _txt(old['key'])
                try:
                    c.execute('''UPDATE associates SET key=?,name=?,full_name=?,plate=?,contact_id=?,address_id=?,associate_type=?,source_code=?,is_active=1,note='KolayBi API sync v2',updated_at=CURRENT_TIMESTAMP WHERE key=?''',
                              (key,display,display,plate,cid,aid,assoc_type,code,old_key))
                except Exception:
                    c.execute('''UPDATE associates SET name=?,full_name=?,plate=CASE WHEN ?<>'' THEN ? ELSE plate END,contact_id=?,address_id=CASE WHEN ?<>'' THEN ? ELSE address_id END,associate_type=?,source_code=?,is_active=1,note='KolayBi API sync v2',updated_at=CURRENT_TIMESTAMP WHERE key=?''',
                              (display,display,plate,plate,cid,aid,aid,assoc_type,code,old_key))
            else:
                c.execute('''INSERT INTO associates(key,name,full_name,plate,contact_id,address_id,associate_type,source_code,is_active,note,updated_at)
                             VALUES(?,?,?,?,?,?,?,?,1,'KolayBi API sync v2',CURRENT_TIMESTAMP)
                             ON CONFLICT(key) DO UPDATE SET name=excluded.name,full_name=excluded.full_name,
                               plate=CASE WHEN excluded.plate<>'' THEN excluded.plate ELSE associates.plate END,
                               contact_id=excluded.contact_id,address_id=CASE WHEN excluded.address_id<>'' THEN excluded.address_id ELSE associates.address_id END,
                               associate_type=excluded.associate_type,source_code=excluded.source_code,is_active=1,note='KolayBi API sync v2',updated_at=CURRENT_TIMESTAMP''',
                          (key,display,display,plate,cid,aid,assoc_type,code))
            count += 1
        c.commit()
    finally:
        c.close()
    return count, errors[-8:]


def _sync_products_v2():
    rows, errors = _paged('products')
    c = kdb()
    count = 0
    try:
        for row in rows:
            pid = _rid(row)
            if not pid:
                continue
            name = _txt(row.get('name') or row.get('product_name') or row.get('item_name') or row.get('title'))
            raw_code = _txt(row.get('code') or row.get('product_code') or row.get('sku'))
            unit = _txt(row.get('unit') or row.get('unit_name') or row.get('unit_code') or row.get('quantity_unit') or row.get('measurement_unit') or row.get('stock_unit') or row.get('purchase_unit') or row.get('sales_unit')) or 'ADET'
            c.execute('''INSERT INTO products(code,name_tr,name_en,product_id,unit,is_active,note,updated_at)
                         VALUES(?,?,?,?,?,1,?,CURRENT_TIMESTAMP)
                         ON CONFLICT(code) DO UPDATE SET name_tr=excluded.name_tr,name_en=excluded.name_en,product_id=excluded.product_id,unit=excluded.unit,is_active=1,note=excluded.note,updated_at=CURRENT_TIMESTAMP''',
                      (('API_'+pid).upper(),name,name,pid,unit.upper(),'KolayBi API: '+raw_code))
            count += 1
        c.commit()
    finally:
        c.close()
    try:
        m = automap.auto_map_fixed_products()
        if m.get('ambiguous'):
            errors.append('Sabit ürün eşleşmesi belirsiz: ' + ', '.join(x.get('code','') for x in m['ambiguous']))
    except Exception as e:
        errors.append('Auto-map: ' + str(e))
    return count, errors[-8:]


# Existing sync routes resolve these module globals when the buttons are clicked.
sync._sync_associates = _sync_associates_v2
sync._sync_products = _sync_products_v2


def _purchase_contact(plate):
    wanted = _norm(plate)
    if not wanted:
        return None, 'NOT FOUND'
    c = kdb()
    try:
        rows = [dict(r) for r in c.execute("SELECT * FROM associates WHERE is_active=1 AND contact_id<>''").fetchall()]
    finally:
        c.close()
    matches = {}
    for row in rows:
        vals = [_norm(row.get('plate')),_norm(row.get('name')),_norm(row.get('full_name')),_norm(row.get('key')),_norm(row.get('source_code'))]
        if any(wanted and wanted in v for v in vals if v):
            matches[_txt(row.get('contact_id'))] = row
    if len(matches) == 1:
        return next(iter(matches.values())), 'PLATE / FREIGHT'
    if len(matches) > 1:
        exact = {cid:r for cid,r in matches.items() if _norm(r.get('plate')) == wanted}
        if len(exact) == 1:
            return next(iter(exact.values())), 'PLATE EXACT'
        return None, 'AMBIGUOUS'
    return None, 'NOT FOUND'


def _sale_contact(customer):
    wanted = _norm(customer)
    if not wanted:
        return None, 'NOT FOUND'
    c = kdb()
    try:
        rows = [dict(r) for r in c.execute("SELECT * FROM associates WHERE is_active=1 AND contact_id<>''").fetchall()]
    finally:
        c.close()
    matches = {}
    for row in rows:
        vals = {_norm(row.get('name')),_norm(row.get('full_name')),_norm(row.get('key'))}
        if wanted in vals:
            matches[_txt(row.get('contact_id'))] = row
    if len(matches) == 1:
        return next(iter(matches.values())), 'CUSTOMER EXACT'
    if len(matches) > 1:
        return None, 'AMBIGUOUS'
    return None, 'NOT FOUND'


def _api_product_exact(name):
    wanted = _norm(name)
    if not wanted:
        return None
    c = kdb()
    try:
        rows = [dict(r) for r in c.execute("SELECT * FROM products WHERE is_active=1 AND product_id<>'' AND code LIKE 'API_%'").fetchall()]
    finally:
        c.close()
    matches = {}
    for row in rows:
        vals = {_norm(row.get('name_tr')),_norm(row.get('name_en'))}
        note = _txt(row.get('note'))
        if note.startswith('KolayBi API:'):
            vals.add(_norm(note.split(':',1)[1]))
        if wanted in vals:
            matches[_txt(row.get('product_id'))] = row
    return next(iter(matches.values())) if len(matches) == 1 else None


def _sale_product(area_name):
    key = _norm(area_name)
    if key:
        c = kdb()
        try:
            row = c.execute('SELECT * FROM sale_product_aliases WHERE alias_key=?',(key,)).fetchone()
        finally:
            c.close()
        if row:
            x = dict(row); x['match_source'] = 'ALIAS'; return x
        direct = _api_product_exact(area_name)
        if direct:
            direct['product_name'] = direct.get('name_tr') or direct.get('name_en') or area_name
            direct['match_source'] = 'DIRECT PRODUCT'
            return direct
    if not key:
        c = kdb()
        try:
            row = c.execute("SELECT * FROM products WHERE UPPER(code)='SALE_FREIGHT' AND is_active=1").fetchone()
        finally:
            c.close()
        if row and _txt(row['product_id']):
            x = dict(row); x['product_name'] = x.get('name_tr') or x.get('name_en') or 'NAKLİYE HİZMETİ'; x['match_source'] = 'DEFAULT'; return x
    return None


def _trip(scna):
    c = core.db()
    try:
        row = c.execute('''SELECT t.*,COALESCE(cu.name,'') customer_name,COALESCE(a.name,'') area_name,COALESCE(d.name,'') driver_name
                           FROM trips t LEFT JOIN customers cu ON cu.id=t.customer_id
                           LEFT JOIN areas a ON a.id=t.area_id LEFT JOIN drivers d ON d.id=t.driver_id
                           WHERE UPPER(TRIM(t.scna))=UPPER(TRIM(?))''',(_txt(scna),)).fetchone()
        if not row:
            raise HTTPException(status_code=404,detail='SCNA bulunamadı.')
        return dict(row)
    finally:
        c.close()


def _purchase_preview(scna, trip=None):
    trip = trip or _trip(scna)
    purchase = ui.base.webmod.kolaybi_preview(scna)
    contact, source = _purchase_contact(trip.get('plate'))
    purchase['contact'] = contact
    purchase['contact_source'] = source
    purchase['customer'] = _txt(trip.get('customer_name'))
    purchase['plate'] = _txt(trip.get('plate'))
    purchase['scna'] = _txt(scna)
    missing_products = sorted({_txt(x.get('code')) for x in purchase.get('items',[]) if not _txt(x.get('product_id'))})
    missing = []
    if missing_products:
        missing.append('PRODUCT ID: '+', '.join(missing_products))
    if not contact:
        missing.append('PURCHASE CARİ: FREIGHT '+_txt(trip.get('plate')))
    elif not _txt(contact.get('contact_id')):
        missing.append('PURCHASE CONTACT ID')
    if contact and not _txt(contact.get('address_id')):
        missing.append('PURCHASE ADDRESS ID')
    project = purchase.get('project') or {}
    if not _txt(project.get('project_id')):
        missing.append('PROJECT ID')
    purchase['missing_product_codes'] = missing_products
    purchase['missing_reasons'] = missing
    purchase['total'] = sum(_num(x.get('total')) for x in purchase.get('items',[]))
    purchase['ready'] = bool(purchase.get('items')) and not missing
    return purchase


def _sale_preview(scna, trip=None, purchase=None):
    trip = trip or _trip(scna)
    purchase = purchase or _purchase_preview(scna,trip)
    customer = _txt(trip.get('customer_name'))
    contact, contact_source = _sale_contact(customer)
    area = _txt(trip.get('area_name'))
    product = _sale_product(area)
    basis = _txt(trip.get('freight_basis') or 'KG').upper()
    qty = _num(trip.get('net_kg')) if basis == 'KG' else 1.0
    rate = _num(trip.get('freight_rate'))
    imported = _num(trip.get('excel_amount'))
    if imported > 0:
        total = imported; unit_price = total/qty if qty > 0 else total; amount_source = 'IMPORTED AMOUNT'
    elif basis == 'KG':
        total = qty*rate; unit_price = rate; amount_source = 'NET KG × FREIGHT RATE'
    else:
        qty = 1.0; total = rate; unit_price = rate; amount_source = 'ADET × FREIGHT RATE'
    pid = _txt((product or {}).get('product_id'))
    pname = _txt((product or {}).get('product_name') or (product or {}).get('name_tr') or (product or {}).get('name_en') or area)
    unit = _txt((product or {}).get('unit')) or ('KG' if basis == 'KG' else 'ADET')
    missing = []
    if not contact:
        missing.append('SALE CARİ: '+(customer or '-'))
    elif not _txt(contact.get('contact_id')):
        missing.append('SALE CONTACT ID')
    if contact and not _txt(contact.get('address_id')):
        missing.append('SALE ADDRESS ID')
    if not pid:
        missing.append('SALE ÜRÜN ALIAS/PRODUCT ID: '+(area or 'NAKLİYE HİZMETİ'))
    project = purchase.get('project') or {}
    if not _txt(project.get('project_id')):
        missing.append('PROJECT ID')
    if qty <= 0:
        missing.append('SALE QUANTITY')
    if total <= 0:
        missing.append('SALE AMOUNT')
    parts = ['SNCA'+re.sub(r'^(SNCA|SCNA)','',_txt(scna).upper())]
    if _txt(trip.get('driver_name')): parts.append('DRIVER: '+_txt(trip.get('driver_name')))
    if _txt(trip.get('plate')): parts.append('PLATE: '+_txt(trip.get('plate')))
    if _num(trip.get('net_kg')) > 0: parts.append('WEIGHT: '+_fmt(_num(trip.get('net_kg')))+' KG')
    return {'scna':_txt(scna),'plate':_txt(trip.get('plate')),'driver':_txt(trip.get('driver_name')),
            'customer':customer,'contact':contact,'contact_source':contact_source,'project':project,
            'area_name':area,'product':product,'product_id':pid,'product_name':pname,
            'product_match_source':_txt((product or {}).get('match_source')),'basis':basis,'quantity':qty,
            'unit_price':unit_price,'total':total,'unit':unit,'amount_source':amount_source,
            'collection':_num(trip.get('entry_collection')),'description':'\n'.join(parts),
            'missing_reasons':missing,'ready':not missing}


@app.get('/api/kolaybi/transaction/{scna}')
def kb_transaction_preview(scna:str):
    trip = _trip(scna)
    purchase = _purchase_preview(scna,trip)
    sale = _sale_preview(scna,trip,purchase)
    return {'ok':True,'summary':{'scna':_txt(scna),'plate':_txt(trip.get('plate')),'driver':_txt(trip.get('driver_name')),
            'customer':_txt(trip.get('customer_name')),'area':_txt(trip.get('area_name')),'date':_txt(trip.get('trip_date')),
            'net_kg':_num(trip.get('net_kg')),'freight_rate':_num(trip.get('freight_rate')),
            'freight_basis':_txt(trip.get('freight_basis') or 'KG'),'collection':_num(trip.get('entry_collection'))},
            'purchase':purchase,'sale':sale}


@app.post('/api/kolaybi/sale-alias')
async def kb_sale_alias_save(request:Request):
    sync.base._admin_required()
    b = await request.json()
    alias = _txt(b.get('alias')); pid = _txt(b.get('product_id')); pname = _txt(b.get('product_name')); unit = _txt(b.get('unit') or 'KG').upper()
    if not alias:
        raise HTTPException(status_code=400,detail='Alias / bölge adı boş olamaz.')
    if not pid or not pid.isdigit():
        raise HTTPException(status_code=400,detail='Product ID sayısal ve dolu olmalı.')
    c = kdb()
    try:
        c.execute('''INSERT INTO sale_product_aliases(alias,alias_key,product_id,product_name,unit,note,updated_at)
                     VALUES(?,?,?,?,?,?,CURRENT_TIMESTAMP)
                     ON CONFLICT(alias) DO UPDATE SET alias_key=excluded.alias_key,product_id=excluded.product_id,product_name=excluded.product_name,unit=excluded.unit,note=excluded.note,updated_at=CURRENT_TIMESTAMP''',
                  (alias,_norm(alias),pid,pname,unit,_txt(b.get('note'))))
        c.commit()
    finally:
        c.close()
    return {'ok':True}


@app.delete('/api/kolaybi/sale-alias/{alias}')
def kb_sale_alias_delete(alias:str):
    sync.base._admin_required()
    c = kdb()
    try:
        c.execute('DELETE FROM sale_product_aliases WHERE alias_key=?',(_norm(alias),)); c.commit()
    finally:
        c.close()
    return {'ok':True}


def _master_v3():
    c = kdb()
    try:
        return {'products':[dict(r) for r in c.execute('SELECT * FROM products ORDER BY is_active DESC,code').fetchall()],
                'associates':[dict(r) for r in c.execute('SELECT * FROM associates ORDER BY is_active DESC,name,key').fetchall()],
                'projects':[dict(r) for r in c.execute('SELECT * FROM projects ORDER BY is_active DESC,code').fetchall()],
                'tags':[dict(r) for r in c.execute('SELECT * FROM tags ORDER BY is_default DESC,name').fetchall()],
                'sale_aliases':[dict(r) for r in c.execute('SELECT * FROM sale_product_aliases ORDER BY alias').fetchall()],
                'sync_log':[dict(r) for r in c.execute('SELECT * FROM sync_log ORDER BY id DESC LIMIT 20').fetchall()]}
    finally:
        c.close()


for route in app.routes:
    if getattr(route,'path',None) == '/api/kolaybi/master' and 'GET' in (getattr(route,'methods',set()) or set()):
        route.endpoint = _master_v3
        if getattr(route,'dependant',None) is not None: route.dependant.call = _master_v3
        break


def _sent(scna,kind):
    c = kdb()
    try:
        r = c.execute('SELECT * FROM sent_documents_v2 WHERE UPPER(scna)=UPPER(?) AND UPPER(doc_kind)=UPPER(?)',(_txt(scna),_txt(kind))).fetchone()
        return dict(r) if r else None
    finally:
        c.close()


def _save_sent(scna,kind,did,endpoint,payload,result,tag_result):
    c = kdb()
    try:
        c.execute('''INSERT INTO sent_documents_v2(scna,doc_kind,document_id,endpoint,payload_json,response_json,tags_json,sent_at)
                     VALUES(?,?,?,?,?,?,?,CURRENT_TIMESTAMP)''',(_txt(scna),_txt(kind).upper(),_txt(did),_txt(endpoint),json.dumps(payload,ensure_ascii=False),json.dumps(result,ensure_ascii=False),json.dumps(tag_result,ensure_ascii=False) if tag_result is not None else ''))
        c.commit()
    finally:
        c.close()


def _apply_tags(did):
    c = kdb()
    try:
        tags = [dict(r) for r in c.execute('SELECT * FROM tags WHERE is_active=1 AND is_default=1 ORDER BY name').fetchall()]
    finally:
        c.close()
    ids = [int(t['tag_id']) for t in tags if _txt(t.get('tag_id')).isdigit()]
    if not did or not ids:
        return None, ids
    return sender._put_json(f'tags/CommercialDoc/{did}',{'relations':{'tags':[{'id':x} for x in ids]}}), ids


def _post(payload):
    errors = []
    for ep in ('invoices','invoice','purchase_invoices','purchase-invoices','purchases','expenses'):
        try:
            return sender._post_form(ep,payload), ep
        except Exception as e:
            errors.append(str(e))
    raise HTTPException(status_code=502,detail='KolayBi belge gönderilemedi: '+' | '.join(errors[-3:]))


def _numbers(scna):
    raw = _txt(scna).upper().replace(' ','')
    for p in ('SNCA','SCNA'):
        if raw.startswith(p): raw = raw[len(p):]; break
    return 'SNCA'+raw, raw


@app.post('/api/kolaybi/transaction/{scna}/purchase/send')
def kb_purchase_send_v2(scna:str):
    sync.base._admin_required()
    old = _sent(scna,'PURCHASE')
    if old:
        raise HTTPException(status_code=409,detail='Bu SCNA satın alma faturası daha önce gönderilmiş. Document ID: '+_txt(old.get('document_id')))
    trip = _trip(scna); pv = _purchase_preview(scna,trip)
    if not pv.get('ready'):
        raise HTTPException(status_code=400,detail='PURCHASE hazır değil: '+' | '.join(pv.get('missing_reasons') or []))
    full_no,num = _numbers(scna); contact = pv.get('contact') or {}; project = pv.get('project') or {}; date = _txt(trip.get('trip_date'))[:10] or time.strftime('%Y-%m-%d')
    payload = {'type':'purchase_invoice','document_no':full_no,'invoice_number':num,'serial_no':full_no,
               'contact_id':_txt(contact.get('contact_id')),'address_id':_txt(contact.get('address_id')),
               'description':full_no+'\nPLATE: '+_txt(trip.get('plate')),'order_date':date,'invoice_date':date,
               'currency':'try','tracking_currency':'try','vat_rate':'0','project_id':_txt(project.get('project_id'))}
    valid = [x for x in pv.get('items',[]) if _num(x.get('quantity')) > 0 and _num(x.get('total')) > 0]
    if not valid:
        raise HTTPException(status_code=400,detail='Gönderilecek PURCHASE kalemi yok.')
    for i,item in enumerate(valid):
        pid = _txt(item.get('product_id')); qty = _num(item.get('quantity')); total = _num(item.get('total'))
        if not pid: raise HTTPException(status_code=400,detail='Product ID eksik: '+_txt(item.get('code')))
        price = total/qty if qty > 0 else _num(item.get('unit_price')); code = _txt(item.get('code')).upper()
        unit = 'LT' if code == 'ROAD_FUEL' else ('GUN' if code in ('PARKING','WAITING') else 'ADET')
        name = _txt(item.get('name') or item.get('code')); desc = _txt(item.get('description')) or name
        payload[f'items[{i}][product_id]'] = pid; payload[f'items[{i}][quantity]'] = _fmt(qty); payload[f'items[{i}][unit_price]'] = _fmt(price); payload[f'items[{i}][vat_rate]'] = '0'
        for k in ('unit','unit_name','unit_code','unit_type','quantity_unit','measurement_unit'): payload[f'items[{i}][{k}]'] = unit
        payload[f'items[{i}][description]'] = desc; payload[f'items[{i}][discount_amount]'] = '0'; payload[f'items[{i}][product_name]'] = name; payload[f'items[{i}][name]'] = name; payload[f'items[{i}][total]'] = _fmt(total); payload[f'items[{i}][amount]'] = _fmt(total)
    result,ep = _post(payload); did = sender._doc_id(result); tag_result,tag_ids = _apply_tags(did); _save_sent(scna,'PURCHASE',did,ep,payload,result,tag_result)
    return {'ok':True,'kind':'PURCHASE','document_id':did,'endpoint':ep,'tags':tag_ids,'result':result}


@app.post('/api/kolaybi/transaction/{scna}/sale/send')
def kb_sale_send_v2(scna:str):
    sync.base._admin_required()
    old = _sent(scna,'SALE')
    if old:
        raise HTTPException(status_code=409,detail='Bu SCNA satış faturası daha önce gönderilmiş. Document ID: '+_txt(old.get('document_id')))
    trip = _trip(scna); purchase = _purchase_preview(scna,trip); sv = _sale_preview(scna,trip,purchase)
    if not sv.get('ready'):
        raise HTTPException(status_code=400,detail='SALE hazır değil: '+' | '.join(sv.get('missing_reasons') or []))
    full_no,num = _numbers(scna); contact = sv.get('contact') or {}; project = sv.get('project') or {}; date = _txt(trip.get('trip_date'))[:10] or time.strftime('%Y-%m-%d')
    payload = {'document_no':full_no,'invoice_number':num,'serial_no':full_no,'contact_id':_txt(contact.get('contact_id')),
               'address_id':_txt(contact.get('address_id')),'description':_txt(sv.get('description')),'order_date':date,'invoice_date':date,
               'currency':'try','tracking_currency':'try','vat_rate':'0','tax_office':'FATİH','contact_tax_office':'FATİH','project_id':_txt(project.get('project_id'))}
    qty = _num(sv.get('quantity')); total = _num(sv.get('total')); price = total/qty if qty > 0 else _num(sv.get('unit_price')); pid = _txt(sv.get('product_id')); name = _txt(sv.get('product_name')); unit = _txt(sv.get('unit')) or 'KG'
    payload['items[0][product_id]'] = pid; payload['items[0][quantity]'] = _fmt(qty); payload['items[0][unit_price]'] = _fmt(price); payload['items[0][vat_rate]'] = '0'; payload['items[0][unit]'] = unit; payload['items[0][unit_name]'] = unit; payload['items[0][unit_code]'] = unit; payload['items[0][product_name]'] = name; payload['items[0][name]'] = name; payload['items[0][description]'] = name; payload['items[0][total]'] = _fmt(total); payload['items[0][amount]'] = _fmt(total); payload['items[0][discount_amount]'] = '0'
    result,ep = _post(payload); did = sender._doc_id(result); tag_result,tag_ids = _apply_tags(did); _save_sent(scna,'SALE',did,ep,payload,result,tag_result)
    return {'ok':True,'kind':'SALE','document_id':did,'endpoint':ep,'tags':tag_ids,'result':result}


@app.get('/api/kolaybi/transaction/{scna}/sent')
def kb_transaction_sent(scna:str):
    return {'purchase':_sent(scna,'PURCHASE'),'sale':_sent(scna,'SALE')}


# Settings: old program's SALE product alias idea, now inside the web panel.
tag_button = '<button class="btn secondary" onclick="kbTab(\'tags\')">ETİKETLER / TAGS</button>'
if tag_button in html and "kbTabV2('salealiases')" not in html:
    html = html.replace(tag_button,tag_button+'\n    <button class="btn secondary" onclick="kbTabV2(\'salealiases\')">SALE ÜRÜN ALIAS</button>',1)

alias_pane = r'''<div id="kbSaleAliases" class="kb-pane" style="display:none"><div class="calc" style="margin-bottom:10px"><b>SALE ÜRÜN ALIAS / BÖLGE → KOLAYBI PRODUCT ID</b><div class="grid" style="margin-top:8px"><div class="field"><label>BÖLGE / ALIAS</label><input id="kbAliasName" placeholder="KERBELA-ERBIL"></div><div class="field wide"><label>KOLAYBI ÜRÜN ARA / SELECT</label><input id="kbAliasProductChoice" list="kbAliasProducts" placeholder="Product ID | Ürün adı"></div><div class="field"><label>BİRİM / UNIT</label><select id="kbAliasUnit"><option>KG</option><option>ADET</option><option>LT</option></select></div><div class="field"><label>NOT</label><input id="kbAliasNote"></div></div><datalist id="kbAliasProducts"></datalist><button class="btn primary" onclick="kbSaveSaleAlias()">ALIAS KAYDET</button></div><div class="table"><table><thead><tr><th>ALIAS</th><th>PRODUCT ID</th><th>ÜRÜN</th><th>BİRİM</th><th>İŞLEM</th></tr></thead><tbody id="kbSaleAliasRows"></tbody></table></div></div>'''
pos = html.find('<section id="kolaybi"')
if pos != -1 and 'id="kbSaleAliases"' not in html:
    end = html.find('</section>',pos)
    if end != -1: html = html[:end]+'  '+alias_pane+'\n'+html[end:]

html = html.replace('onclick="kbLoadSingle()">SCNA KONTROLÜNÜ GETİR</button>','onclick="kbLoadSingleV2()">SCNA KONTROLÜNÜ GETİR</button>',1)

helper = r'''
function kbTabV2(name){if(name!=='salealiases'){kbTab(name);const a=document.getElementById('kbSaleAliases');if(a)a.style.display='none';return;}['Products','Associates','Projects','Tags'].forEach(x=>{const e=document.getElementById('kb'+x);if(e)e.style.display='none';});const a=document.getElementById('kbSaleAliases');if(a)a.style.display='';kbRenderSaleAliases();}
function kbRenderSaleAliases(){const dl=document.getElementById('kbAliasProducts');if(dl)dl.innerHTML=(kbMaster.products||[]).filter(x=>x.product_id).map(x=>`<option value="${kbEsc(x.product_id)} | ${kbEsc(x.name_tr||x.name_en||x.code)}"></option>`).join('');const tb=document.getElementById('kbSaleAliasRows');if(tb)tb.innerHTML=(kbMaster.sale_aliases||[]).map(x=>`<tr><td>${kbEsc(x.alias)}</td><td>${kbEsc(x.product_id)}</td><td>${kbEsc(x.product_name)}</td><td>${kbEsc(x.unit)}</td><td><button class="btn danger" onclick="kbDeleteSaleAlias('${kbEsc(x.alias)}')">SİL</button></td></tr>`).join('');}
async function kbSaveSaleAlias(){const raw=String(document.getElementById('kbAliasProductChoice')?.value||'').trim();const parts=raw.split('|');const pid=String(parts.shift()||'').trim();const pname=parts.join('|').trim();const alias=String(document.getElementById('kbAliasName')?.value||'').trim();try{await api('/api/kolaybi/sale-alias',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({alias:alias,product_id:pid,product_name:pname,unit:document.getElementById('kbAliasUnit')?.value||'KG',note:document.getElementById('kbAliasNote')?.value||''})});await loadKolaybiMaster();kbRenderSaleAliases();alert('SALE ürün alias kaydedildi.');}catch(e){alert(e.message||e);}}
async function kbDeleteSaleAlias(alias){if(!confirm(alias+' alias silinsin mi?'))return;try{await api('/api/kolaybi/sale-alias/'+encodeURIComponent(alias),{method:'DELETE'});await loadKolaybiMaster();kbRenderSaleAliases();}catch(e){alert(e.message||e);}}
async function kbSendTxn(scna,kind){const label=kind==='sale'?'SATIŞ':'SATIN ALMA';if(!confirm(scna+' '+label+' faturası KolayBi’ye GERÇEK olarak gönderilsin mi?'))return;const state=document.getElementById('kbSingleState');if(state)state.textContent=label+' GÖNDERİLİYOR...';try{const r=await api('/api/kolaybi/transaction/'+encodeURIComponent(scna)+'/'+kind+'/send',{method:'POST'});if(state)state.innerHTML='<span class="kb-ready">✓ '+label+' GÖNDERİLDİ | Document ID: '+kbEsc(r.document_id||'-')+'</span>';await kbLoadSingleV2();}catch(e){if(state)state.innerHTML='<span class="kb-missing">'+kbEsc(e.message||e)+'</span>';alert(e.message||e);}}
async function kbLoadSingleV2(){const scna=String(document.getElementById('kbSingleScna')?.value||'').trim();const state=document.getElementById('kbSingleState');if(!scna){if(state)state.innerHTML='<span class="kb-missing">SCNA GİR</span>';return;}if(state)state.textContent='SCNA HAZIRLANIYOR...';try{const x=await api('/api/kolaybi/transaction/'+encodeURIComponent(scna));const sent=await api('/api/kolaybi/transaction/'+encodeURIComponent(scna)+'/sent');const p=x.purchase||{},s=x.sale||{},z=x.summary||{};const result=document.getElementById('kbSingleResult');if(result)result.style.display='grid';const ps=document.getElementById('kbPurchaseStatus'),ss=document.getElementById('kbSaleStatus');if(ps)ps.innerHTML=sent.purchase?'<span class="kb-ready">✓ GÖNDERİLDİ</span>':(p.ready?'<span class="kb-ready">✓ HAZIR</span>':'<span class="kb-missing">EKSİK</span>');if(ss)ss.innerHTML=sent.sale?'<span class="kb-ready">✓ GÖNDERİLDİ</span>':(s.ready?'<span class="kb-ready">✓ HAZIR</span>':'<span class="kb-missing">EKSİK</span>');const summary=`<div class="kb-txn-summary"><b>SCNA:</b> ${kbEsc(z.scna||scna)} &nbsp; <b>PLATE:</b> ${kbEsc(z.plate||'-')} &nbsp; <b>DRIVER:</b> ${kbEsc(z.driver||'-')}<br><b>CUSTOMER:</b> ${kbEsc(z.customer||'-')} &nbsp; <b>ROUTE:</b> ${kbEsc(z.area||'-')} &nbsp; <b>DATE:</b> ${kbEsc(z.date||'-')}</div>`;const pc=p.contact||{};const rows=(p.items||[]).map(i=>`<tr><td><b>${kbEsc(i.name||i.code)}</b>${i.description?'<br><small>'+kbEsc(i.description)+'</small>':''}</td><td>${kbEsc(i.product_id||'-')}</td><td>${Number(i.quantity||0).toLocaleString('tr-TR')}</td><td>${Number(i.unit_price||0).toLocaleString('tr-TR')}</td><td><b>${Number(i.total||0).toLocaleString('tr-TR')}</b></td></tr>`).join('');const pMissing=(p.missing_reasons||[]).length?`<div class="kb-missing" style="margin:8px 0">${kbEsc(p.missing_reasons.join(' | '))}</div>`:'';const pButton=!sent.purchase&&p.ready?`<button class="btn primary" style="margin-top:10px" onclick="kbSendTxn('${kbEsc(scna)}','purchase')">SATIN ALMA FATURASI GÖNDER</button>`:'';const pb=document.getElementById('kbPurchaseBody');if(pb)pb.innerHTML=summary+`<div class="kb-roleline"><b>PURCHASE CARİ:</b> ${kbEsc(pc.name||pc.full_name||'-')}<br><small>Kaynak: ${kbEsc(p.contact_source||'-')} | Contact ID: ${kbEsc(pc.contact_id||'-')} | Address ID: ${kbEsc(pc.address_id||'-')}</small></div>${pMissing}<div class="table"><table><thead><tr><th>GİDER / PRODUCT</th><th>PRODUCT ID</th><th>QTY</th><th>UNIT PRICE</th><th>TOTAL</th></tr></thead><tbody>${rows}</tbody><tfoot><tr><td colspan="4"><b>PURCHASE TOTAL</b></td><td><b>${Number(p.total||0).toLocaleString('tr-TR')}</b></td></tr></tfoot></table></div>${pButton}${sent.purchase?'<div class="kb-ready" style="margin-top:8px">Document ID: '+kbEsc(sent.purchase.document_id||'-')+'</div>':''}`;const sc=s.contact||{};const sMissing=(s.missing_reasons||[]).length?`<div class="kb-missing" style="margin:8px 0">${kbEsc(s.missing_reasons.join(' | '))}</div>`:'';const sButton=!sent.sale&&s.ready?`<button class="btn primary" style="margin-top:10px" onclick="kbSendTxn('${kbEsc(scna)}','sale')">SATIŞ FATURASI GÖNDER</button>`:'';const sb=document.getElementById('kbSaleBody');if(sb)sb.innerHTML=summary+`<div class="kb-roleline"><b>SALE MÜŞTERİ:</b> ${kbEsc(s.customer||'-')}<br><small>Kaynak: ${kbEsc(s.contact_source||'-')} | Contact ID: ${kbEsc(sc.contact_id||'-')} | Address ID: ${kbEsc(sc.address_id||'-')}</small></div><div class="kb-roleline"><b>SALE ÜRÜN:</b> ${kbEsc(s.product_name||s.area_name||'-')}<br><small>Bölge/Alias: ${kbEsc(s.area_name||'-')} | Product ID: ${kbEsc(s.product_id||'-')} | Eşleşme: ${kbEsc(s.product_match_source||'-')}</small></div>${sMissing}<div class="table"><table><thead><tr><th>QTY</th><th>RATE</th><th>SALE TOTAL</th><th>COLLECTION</th></tr></thead><tbody><tr><td>${Number(s.quantity||0).toLocaleString('tr-TR')} ${kbEsc(s.unit||s.basis||'')}</td><td>${Number(s.unit_price||0).toLocaleString('tr-TR')}</td><td><b>${Number(s.total||0).toLocaleString('tr-TR')}</b><br><small>${kbEsc(s.amount_source||'')}</small></td><td>${Number(s.collection||0).toLocaleString('tr-TR')}<br><small>Bilgi amaçlı, SALE tutarı değildir</small></td></tr></tbody></table></div>${sButton}${sent.sale?'<div class="kb-ready" style="margin-top:8px">Document ID: '+kbEsc(sent.sale.document_id||'-')+'</div>':''}`;if(state)state.innerHTML='<span class="kb-ready">SCNA HAZIRLANDI</span>';}catch(e){if(state)state.innerHTML='<span class="kb-missing">'+kbEsc(e.message||e)+'</span>';}}
'''
marker = 'async function kbPreview(){'
if marker in html and 'async function kbLoadSingleV2' not in html:
    html = html.replace(marker,helper+'\n'+marker,1)
html = html.replace("try{kbMaster=await api('/api/kolaybi/master');kbRenderMaster();}","try{kbMaster=await api('/api/kolaybi/master');kbRenderMaster();kbRenderSaleAliases();}",1)
css = '.kb-txn-summary{padding:9px 10px;border:1px solid var(--line);border-radius:10px;margin-bottom:9px;line-height:1.65}.kb-roleline{padding:8px 10px;background:var(--soft);border-radius:9px;margin:7px 0;line-height:1.55}#kbSingleResult .table{overflow:auto;margin-top:8px}#kbSingleResult table{min-width:560px}'
if '</style>' in html and '.kb-txn-summary{' not in html: html = html.replace('</style>',css+'</style>',1)

core.HTML = html
print('[SAMA] KolayBi workflow V2 active: PURCHASE=plate/FREIGHT, SALE=customer+route alias, sync v2, dual send history')
