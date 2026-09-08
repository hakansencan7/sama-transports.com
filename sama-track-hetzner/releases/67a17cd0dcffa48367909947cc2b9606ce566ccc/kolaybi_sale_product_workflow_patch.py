import re
from fastapi import Request, HTTPException

# Keep the latest backend chain, including live sent-state and OTHER descriptions.
import kolaybi_other_description_patch as base
import kolaybi_workflow_v2_patch as workflow

app = base.app
core = base.core
kdb = workflow.kdb
sync = workflow.sync
sender = workflow.sender
html = core.HTML


def _txt(v):
    return str(v or '').strip()


def _norm(v):
    return workflow._norm(v)


def _product_id(obj):
    if isinstance(obj, dict):
        for key in ('id', 'product_id', 'item_id'):
            val = _txt(obj.get(key))
            if val:
                return val
        for key in ('data', 'product', 'item', 'result'):
            got = _product_id(obj.get(key))
            if got:
                return got
    elif isinstance(obj, list):
        for row in obj:
            got = _product_id(row)
            if got:
                return got
    return ''


def _product_name(row):
    if not isinstance(row, dict):
        return ''
    return _txt(row.get('name') or row.get('product_name') or row.get('item_name') or row.get('title') or row.get('name_tr') or row.get('name_en'))


def _product_code(row):
    if not isinstance(row, dict):
        return ''
    code = _txt(row.get('code') or row.get('product_code') or row.get('sku'))
    if not code and _txt(row.get('note')).startswith('KolayBi API:'):
        code = _txt(row.get('note')).split(':', 1)[1].strip()
    return code


def _product_unit(row):
    if not isinstance(row, dict):
        return 'KG'
    return (_txt(row.get('unit') or row.get('unit_name') or row.get('unit_code') or row.get('quantity_unit') or row.get('measurement_unit') or row.get('sales_unit')) or 'KG').upper()


def _cache_product(row):
    if not isinstance(row, dict):
        return None
    pid = _product_id(row)
    if not pid:
        return None
    name = _product_name(row) or ('PRODUCT ' + pid)
    code = _product_code(row)
    unit = _product_unit(row)
    c = kdb()
    try:
        c.execute('''INSERT INTO products(code,name_tr,name_en,product_id,unit,is_active,note,updated_at)
                     VALUES(?,?,?,?,?,1,?,CURRENT_TIMESTAMP)
                     ON CONFLICT(code) DO UPDATE SET name_tr=excluded.name_tr,name_en=excluded.name_en,
                     product_id=excluded.product_id,unit=excluded.unit,is_active=1,note=excluded.note,
                     updated_at=CURRENT_TIMESTAMP''',
                  (('API_' + pid).upper(), name, name, pid, unit, 'KolayBi API: ' + code))
        c.commit()
        out = c.execute("SELECT * FROM products WHERE code=?", (('API_' + pid).upper(),)).fetchone()
        return dict(out) if out else None
    finally:
        c.close()


def _local_product_rows():
    c = kdb()
    try:
        return [dict(r) for r in c.execute("SELECT * FROM products WHERE is_active=1 AND product_id<>'' AND code LIKE 'API_%' ORDER BY name_tr,name_en,code").fetchall()]
    finally:
        c.close()


def _candidate_view(row, source='LOCAL DB'):
    return {
        'product_id': _txt(row.get('product_id') or row.get('id')),
        'name': _product_name(row) or _txt(row.get('name_tr') or row.get('name_en')) or '-',
        'code': _product_code(row),
        'unit': _product_unit(row),
        'source': source,
    }


def _local_candidates(term):
    wanted = _norm(term)
    if not wanted:
        return []
    exact, contains, seen = [], [], set()
    for row in _local_product_rows():
        pid = _txt(row.get('product_id'))
        if not pid or pid in seen:
            continue
        vals = [_product_name(row), row.get('name_tr'), row.get('name_en'), _product_code(row), row.get('note')]
        norms = [_norm(x) for x in vals if _txt(x)]
        if wanted in norms:
            exact.append(_candidate_view(row, 'LOCAL DB'))
            seen.add(pid)
        elif any(wanted in n or n in wanted for n in norms if n):
            contains.append(_candidate_view(row, 'LOCAL DB'))
            seen.add(pid)
    return (exact + contains)[:25]


def _live_products(term):
    term = _txt(term)
    if not term:
        return []
    found, seen = [], set()
    for params in ({'q': term}, {'search': term}, {'name': term}, {'code': term}):
        try:
            rows = sync._rows(sync._get('products', params))
        except Exception:
            rows = []
        for row in rows:
            pid = _product_id(row)
            if not pid or pid in seen:
                continue
            seen.add(pid)
            cached = _cache_product(row) or row
            found.append(_candidate_view(cached, 'KOLAYBI LIVE'))
            if len(found) >= 25:
                return found
    return found


def _trip_area(scna):
    trip = workflow._trip(scna)
    area = _txt(trip.get('area_name'))
    if not area:
        raise HTTPException(status_code=400, detail='SALE ürününü belirlemek için sevkiyat bölgesi boş olamaz.')
    return trip, area


def _suggested_code(area):
    key = _norm(area) or 'FREIGHT'
    return ('FREIGHT_' + key)[:60]


def _save_alias(area, pid, name, unit, note):
    if not _txt(pid).isdigit():
        raise HTTPException(status_code=400, detail='Product ID sayısal olmalı.')
    c = kdb()
    try:
        c.execute('''INSERT INTO sale_product_aliases(alias,alias_key,product_id,product_name,unit,note,updated_at)
                     VALUES(?,?,?,?,?,?,CURRENT_TIMESTAMP)
                     ON CONFLICT(alias_key) DO UPDATE SET alias=excluded.alias,product_id=excluded.product_id,
                     product_name=excluded.product_name,unit=excluded.unit,note=excluded.note,
                     updated_at=CURRENT_TIMESTAMP''',
                  (_txt(area), _norm(area), _txt(pid), _txt(name), (_txt(unit) or 'KG').upper(), _txt(note)))
        c.commit()
    finally:
        c.close()


@app.get('/api/kolaybi/sale-product/{scna}/candidates')
def kb_sale_product_candidates(scna: str, name: str = '', live: bool = True):
    _trip, area = _trip_area(scna)
    term = _txt(name) or area
    rows = _local_candidates(term)
    seen = {x['product_id'] for x in rows if x.get('product_id')}
    if live:
        try:
            for row in _live_products(term):
                if row['product_id'] in seen:
                    continue
                rows.append(row)
                seen.add(row['product_id'])
                if len(rows) >= 25:
                    break
        except Exception:
            pass
    return {
        'ok': True,
        'scna': _txt(scna),
        'area': area,
        'search_name': term,
        'suggested_name': area,
        'suggested_code': _suggested_code(area),
        'candidates': rows[:25],
    }


@app.post('/api/kolaybi/sale-product/{scna}/select')
async def kb_sale_product_select(scna: str, request: Request):
    sync.base._admin_required()
    body = await request.json()
    pid = _txt(body.get('product_id'))
    if not pid or not pid.isdigit():
        raise HTTPException(status_code=400, detail='Seçilecek Product ID boş veya hatalı.')
    _trip, area = _trip_area(scna)
    c = kdb()
    try:
        row = c.execute("SELECT * FROM products WHERE product_id=? AND is_active=1 ORDER BY updated_at DESC LIMIT 1", (pid,)).fetchone()
        product = dict(row) if row else None
    finally:
        c.close()
    if not product:
        raise HTTPException(status_code=404, detail='Seçilen Product ID yerel KolayBi ürün listesinde bulunamadı. Önce ürün aramasını yenile.')
    name = _product_name(product) or _txt(product.get('name_tr') or product.get('name_en')) or area
    unit = _product_unit(product)
    _save_alias(area, pid, name, unit, 'USER SELECTED FROM SALE PRODUCT RESOLVER')
    return {'ok': True, 'selected': True, 'area': area, 'product': _candidate_view(product, 'SELECTED')}


@app.post('/api/kolaybi/sale-product/{scna}/create')
async def kb_sale_product_create(scna: str, request: Request):
    sync.base._admin_required()
    body = await request.json()
    _trip, area = _trip_area(scna)
    name = _txt(body.get('name')) or area
    code = _txt(body.get('code')) or _suggested_code(area)
    vat_rate = _txt(body.get('vat_rate') or '0')
    if not name:
        raise HTTPException(status_code=400, detail='Yeni ürün adı boş olamaz.')
    if not code:
        raise HTTPException(status_code=400, detail='Yeni ürün kodu boş olamaz.')

    # Never create blindly. First check the synchronized/local catalogue and then KolayBi live.
    exact = []
    wanted_name, wanted_code = _norm(name), _norm(code)
    for row in _local_product_rows():
        if _norm(_product_name(row)) == wanted_name or (_product_code(row) and _norm(_product_code(row)) == wanted_code):
            exact.append(_candidate_view(row, 'LOCAL DB'))
    if not exact:
        for term in (code, name):
            for row in _live_products(term):
                if _norm(row.get('name')) == wanted_name or (row.get('code') and _norm(row.get('code')) == wanted_code):
                    if row['product_id'] not in {x['product_id'] for x in exact}:
                        exact.append(row)
    if exact:
        if len(exact) == 1:
            x = exact[0]
            raise HTTPException(status_code=409, detail=f"Bu ürün KolayBi'de zaten var. Product ID: {x['product_id']} | {x['name']}. Yeni ürün oluşturma yerine mevcut ürünü eşleştir.")
        raise HTTPException(status_code=409, detail='Aynı isim/koda benzeyen birden fazla KolayBi ürünü bulundu. Yeni ürün oluşturulmadı; mevcut ürünlerden birini seç.')

    # Proven old KolayBi flow creates a product with name + code + vat_rate.
    try:
        result = sender._post_form('products', {'name': name, 'code': code, 'vat_rate': vat_rate})
    except Exception as e:
        raise HTTPException(status_code=502, detail='KolayBi yeni SALE ürünü oluşturulamadı: ' + str(e))

    pid = _product_id(result)
    if not pid:
        # Some API responses omit the created id; resolve it by the unique code before giving up.
        matches = []
        for row in _live_products(code):
            if row.get('code') and _norm(row.get('code')) == wanted_code:
                matches.append(row)
        uniq = {x['product_id']: x for x in matches if x.get('product_id')}
        if len(uniq) == 1:
            pid = next(iter(uniq))
    if not pid:
        raise HTTPException(status_code=502, detail='KolayBi ürünü oluşturuldu yanıtı geldi ancak Product ID doğrulanamadı. Otomatik eşleştirme yapılmadı.')

    local = _cache_product({'id': pid, 'name': name, 'code': code, 'unit': 'KG'})
    unit = _product_unit(local or {'unit': 'KG'})
    _save_alias(area, pid, name, unit, 'CREATED FROM SAMA SALE PRODUCT RESOLVER')
    return {
        'ok': True, 'created': True, 'area': area,
        'product': {'product_id': pid, 'name': name, 'code': code, 'unit': unit, 'source': 'CREATED FROM SAMA'},
    }


# UI: when SALE product is missing, explain it and offer search/map/create.
# No extra <script> block. Helpers are inserted into the app's existing JavaScript.
sale_product_anchor = '<div class="kb-roleline"><b>SALE ÜRÜN:</b>'
ui_inserted = 0
if sale_product_anchor in html and 'id="kbSaleProductTools"' not in html:
    html = html.replace(sale_product_anchor, '<div class="kb-roleline" id="kbSaleProductTools"></div>' + sale_product_anchor, 1)
    ui_inserted = 1

helper = r'''
function kbSaleProductStatus(scna,s){
  const box=document.getElementById('kbSaleProductTools');if(!box)return;
  const area=String((s&&s.area_name)||'').trim();
  if(s&&s.product_id){
    box.innerHTML=`<div class="kb-ready"><b>SALE ÜRÜN EŞLEŞTİ</b> &nbsp; ${kbEsc(s.product_name||area||'-')} | Product ID: ${kbEsc(s.product_id)} <button class="btn secondary" style="margin-left:8px" onclick="kbSaleProductOpen('${kbEsc(scna)}')">DEĞİŞTİR / KONTROL ET</button></div>`;
    return;
  }
  box.innerHTML=`<div class="kb-sale-product-alert"><b>SATIŞ ÜRÜNÜ BULUNAMADI / EŞLEŞMEDİ</b><br><span>Bölge / ürün adı: <strong>${kbEsc(area||'-')}</strong></span><br><small>Satış faturası gönderimi durduruldu. Önce KolayBi'de mevcut ürünü ara ve eşleştir. Gerçekten yoksa yeni ürünü buradan oluştur.</small><div style="display:flex;gap:7px;flex-wrap:wrap;margin-top:8px"><button class="btn secondary" onclick="kbSaleProductOpen('${kbEsc(scna)}')">ÜRÜN ARA / EŞLEŞTİR</button><button class="btn primary" onclick="kbSaleProductOpen('${kbEsc(scna)}',true)">YENİ ÜRÜN OLUŞTUR</button></div></div>`;
}
async function kbSaleProductOpen(scna,focusCreate=false){
  const box=document.getElementById('kbSaleProductTools');if(!box)return;
  box.innerHTML='<span class="section-note">SALE ÜRÜNLERİ ARANIYOR...</span>';
  try{const r=await api('/api/kolaybi/sale-product/'+encodeURIComponent(scna)+'/candidates?live=true');kbSaleProductRender(scna,r,focusCreate);}
  catch(e){box.innerHTML='<span class="kb-missing">'+kbEsc(e.message||e)+'</span>';}
}
function kbSaleProductRender(scna,r,focusCreate=false){
  const box=document.getElementById('kbSaleProductTools');if(!box)return;
  const rows=r.candidates||[];
  const opts=rows.map(x=>`<option value="${kbEsc(x.product_id)}">${kbEsc((x.name||'-')+' | ID:'+ (x.product_id||'-')+' | CODE:'+(x.code||'-')+' | '+(x.source||''))}</option>`).join('');
  box.innerHTML=`<b>SALE ÜRÜN BUL / EŞLEŞTİR</b>
    <div style="display:flex;gap:7px;flex-wrap:wrap;align-items:end;margin-top:7px">
      <div class="field" style="min-width:220px;flex:1"><label>ÜRÜN / BÖLGE ADI</label><input id="kbSaleProductName" value="${kbEsc(r.search_name||r.area||'')}"></div>
      <button class="btn secondary" onclick="kbSaleProductSearch('${kbEsc(scna)}')">DB + KOLAYBI ARA</button>
    </div>
    <div style="display:flex;gap:7px;flex-wrap:wrap;align-items:end;margin-top:7px">
      <div class="field" style="min-width:300px;flex:1"><label>MEVCUT ÜRÜNÜ SEÇ</label><select id="kbSaleProductSelect"><option value="">SEÇİLMEDİ</option>${opts}</select></div>
      <button class="btn primary" onclick="kbSaleProductApply('${kbEsc(scna)}')">SEÇİLEN ÜRÜNÜ EŞLEŞTİR</button>
    </div>
    <div class="kb-sale-create-box" style="margin-top:10px">
      <b>YENİ ÜRÜN OLUŞTUR</b>
      <div style="display:flex;gap:7px;flex-wrap:wrap;align-items:end;margin-top:7px">
        <div class="field" style="min-width:220px;flex:1"><label>ÜRÜN ADI</label><input id="kbSaleNewProductName" value="${kbEsc(r.suggested_name||r.area||'')}"></div>
        <div class="field" style="min-width:220px;flex:1"><label>ÜRÜN KODU</label><input id="kbSaleNewProductCode" value="${kbEsc(r.suggested_code||'')}"></div>
        <div class="field" style="width:110px"><label>KDV / VAT</label><input id="kbSaleNewProductVat" value="0"></div>
        <button class="btn primary" onclick="kbSaleProductCreate('${kbEsc(scna)}')">KOLAYBI'DE YENİ ÜRÜN OLUŞTUR</button>
      </div>
      <small>${rows.length?rows.length+' aday bulundu. Önce mevcut ürünü kontrol et.':'Uygun aday bulunamadı. Ürün gerçekten yoksa yeni oluşturabilirsin.'} Sistem rastgele ürün seçmez ve otomatik yeni ürün oluşturmaz.</small>
    </div>`;
  if(focusCreate){setTimeout(()=>document.getElementById('kbSaleNewProductName')?.focus(),50);}
}
async function kbSaleProductSearch(scna){
  const name=String(document.getElementById('kbSaleProductName')?.value||'').trim();
  const box=document.getElementById('kbSaleProductTools');if(box)box.innerHTML='<span class="section-note">ÜRÜN ARANIYOR...</span>';
  try{const r=await api('/api/kolaybi/sale-product/'+encodeURIComponent(scna)+'/candidates?live=true&name='+encodeURIComponent(name));kbSaleProductRender(scna,r,false);}
  catch(e){if(box)box.innerHTML='<span class="kb-missing">'+kbEsc(e.message||e)+'</span>';}
}
async function kbSaleProductApply(scna){
  const pid=String(document.getElementById('kbSaleProductSelect')?.value||'').trim();
  if(!pid){alert('Önce mevcut KolayBi ürününü seç.');return;}
  try{const r=await api('/api/kolaybi/sale-product/'+encodeURIComponent(scna)+'/select',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({product_id:pid})});alert('SALE ürünü eşleştirildi. Product ID: '+(r.product?.product_id||pid));await kbLoadSingleV2();}
  catch(e){alert(e.message||e);}
}
async function kbSaleProductCreate(scna){
  const name=String(document.getElementById('kbSaleNewProductName')?.value||'').trim();
  const code=String(document.getElementById('kbSaleNewProductCode')?.value||'').trim();
  const vat=String(document.getElementById('kbSaleNewProductVat')?.value||'0').trim()||'0';
  if(!name||!code){alert('Yeni ürün adı ve kodu boş olamaz.');return;}
  if(!confirm(`KolayBi'de GERÇEK YENİ ÜRÜN oluşturulsun mu?\n\nÜRÜN: ${name}\nKOD: ${code}\nKDV: ${vat}\n\nSistem önce aynı ürünün mevcut olup olmadığını tekrar kontrol edecek.`))return;
  try{const r=await api('/api/kolaybi/sale-product/'+encodeURIComponent(scna)+'/create',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:name,code:code,vat_rate:vat})});alert('Yeni SALE ürünü oluşturuldu ve bu bölgeye eşleştirildi. Product ID: '+(r.product?.product_id||'-'));await kbLoadSingleV2();}
  catch(e){alert(e.message||e);}
}
'''
marker = 'async function kbLoadSingleV2(){'
js_inserted = 0
if marker in html and 'function kbSaleProductStatus' not in html:
    html = html.replace(marker, helper + '\n' + marker, 1)
    js_inserted = 1

status_anchor = "if(state)state.innerHTML='<span class=\"kb-ready\">SCNA HAZIRLANDI</span>';"
status_inserted = 0
if status_anchor in html and "kbSaleProductStatus(scna,s)" not in html:
    html = html.replace(status_anchor, "if(typeof kbSaleProductStatus==='function')kbSaleProductStatus(scna,s);" + status_anchor, 1)
    status_inserted = 1

css = '.kb-sale-product-alert{border:2px solid #c43b2f;background:#fff4f2;color:#7e1f18;border-radius:10px;padding:10px;line-height:1.55}.kb-sale-create-box{border:1px dashed var(--line);border-radius:9px;padding:9px;background:var(--soft)}'
if '</style>' in html and '.kb-sale-product-alert{' not in html:
    html = html.replace('</style>', css + '</style>', 1)

core.HTML = html
print(f'[SAMA] KolayBi SALE product resolver active: ui={ui_inserted}, js={js_inserted}, status={status_inserted}; missing product -> search/map/create with confirmation')
