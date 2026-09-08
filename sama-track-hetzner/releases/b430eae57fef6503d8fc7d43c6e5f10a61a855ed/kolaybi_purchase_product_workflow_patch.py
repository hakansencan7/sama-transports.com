from fastapi import Request, HTTPException

# Load after the current Entry/KolayBi UI chain. Reuse the proven SALE product
# search/create helpers so PURCHASE gets the same safe duplicate-first workflow.
import entry_other_edit_unlock_patch as base
import kolaybi_sale_product_workflow_patch as saleprod
import kolaybi_workflow_v2_patch as workflow

app = base.app
core = base.core
kdb = workflow.kdb
sender = workflow.sender
html = core.HTML


def _txt(v):
    return str(v or '').strip()


def _norm(v):
    return workflow._norm(v)


def _required_code(code):
    code = _txt(code).upper()
    if not code or len(code) > 80:
        raise HTTPException(status_code=400, detail='PURCHASE ürün kodu boş veya hatalı.')
    return code


def _mapping_row(code):
    c = kdb()
    try:
        row = c.execute('SELECT * FROM products WHERE UPPER(code)=UPPER(?) AND is_active=1 LIMIT 1', (code,)).fetchone()
        return dict(row) if row else None
    finally:
        c.close()


def _suggested_name(code, row=None):
    row = row or _mapping_row(code) or {}
    tr = _txt(row.get('name_tr'))
    en = _txt(row.get('name_en'))
    if tr and en and _norm(tr) != _norm(en):
        return f'{tr} / {en}'
    return tr or en or code.replace('_', ' ')


def _save_mapping(code, pid, product_name='', unit='ADET', note=''):
    code = _required_code(code)
    pid = _txt(pid)
    if not pid.isdigit():
        raise HTTPException(status_code=400, detail='Product ID sayısal olmalı.')
    existing = _mapping_row(code) or {}
    name_tr = _txt(existing.get('name_tr')) or _txt(product_name) or code
    name_en = _txt(existing.get('name_en')) or _txt(product_name) or code
    mapped_unit = (_txt(existing.get('unit')) or _txt(unit) or 'ADET').upper()
    c = kdb()
    try:
        if existing:
            c.execute('''UPDATE products
                         SET product_id=?, unit=?, is_active=1, note=?, updated_at=CURRENT_TIMESTAMP
                         WHERE UPPER(code)=UPPER(?)''',
                      (pid, mapped_unit, _txt(note), code))
        else:
            c.execute('''INSERT INTO products(code,name_tr,name_en,product_id,unit,is_active,note,updated_at)
                         VALUES(?,?,?,?,?,1,?,CURRENT_TIMESTAMP)''',
                      (code, name_tr, name_en, pid, mapped_unit, _txt(note)))
        c.commit()
    finally:
        c.close()
    return _mapping_row(code) or {'code': code, 'product_id': pid, 'name_tr': name_tr, 'name_en': name_en, 'unit': mapped_unit}


def _candidate_rows(code, term, live=True):
    rows = []
    seen = set()
    searches = []
    for x in (term, code, _suggested_name(code)):
        x = _txt(x)
        if x and _norm(x) not in {_norm(y) for y in searches}:
            searches.append(x)
    for q in searches:
        for row in saleprod._local_candidates(q):
            pid = _txt(row.get('product_id'))
            if pid and pid not in seen:
                rows.append(row)
                seen.add(pid)
        if live:
            try:
                for row in saleprod._live_products(q):
                    pid = _txt(row.get('product_id'))
                    if pid and pid not in seen:
                        rows.append(row)
                        seen.add(pid)
                        if len(rows) >= 40:
                            return rows[:40]
            except Exception:
                pass
    return rows[:40]


@app.get('/api/kolaybi/purchase-product/{code}/candidates')
def kb_purchase_product_candidates(code: str, name: str = '', live: bool = True):
    code = _required_code(code)
    current = _mapping_row(code) or {}
    term = _txt(name) or _suggested_name(code, current)
    return {
        'ok': True,
        'required_code': code,
        'current_product_id': _txt(current.get('product_id')),
        'search_name': term,
        'suggested_name': _suggested_name(code, current),
        'suggested_code': code,
        'suggested_unit': (_txt(current.get('unit')) or 'ADET').upper(),
        'candidates': _candidate_rows(code, term, live=live),
    }


@app.post('/api/kolaybi/purchase-product/{code}/select')
async def kb_purchase_product_select(code: str, request: Request):
    # Central section middleware additionally requires kolaybi.edit for this POST.
    saleprod.sync.base._admin_required()
    code = _required_code(code)
    body = await request.json()
    pid = _txt(body.get('product_id'))
    if not pid.isdigit():
        raise HTTPException(status_code=400, detail='Seçilecek Product ID boş veya hatalı.')
    c = kdb()
    try:
        row = c.execute("SELECT * FROM products WHERE product_id=? AND is_active=1 ORDER BY updated_at DESC LIMIT 1", (pid,)).fetchone()
        product = dict(row) if row else None
    finally:
        c.close()
    if not product:
        raise HTTPException(status_code=404, detail='Seçilen Product ID yerel KolayBi ürün listesinde bulunamadı. Önce DB + KOLAYBI ARA yap.')
    name = saleprod._product_name(product) or _txt(product.get('name_tr') or product.get('name_en')) or code
    unit = saleprod._product_unit(product) or 'ADET'
    mapped = _save_mapping(code, pid, name, unit, 'USER MAP -> ' + name)
    return {
        'ok': True,
        'selected': True,
        'required_code': code,
        'product': {
            'product_id': pid,
            'name': name,
            'unit': _txt(mapped.get('unit')) or unit,
            'source': 'SELECTED FOR PURCHASE',
        },
    }


@app.post('/api/kolaybi/purchase-product/{code}/create')
async def kb_purchase_product_create(code: str, request: Request):
    # Central section middleware additionally requires kolaybi.edit for this POST.
    saleprod.sync.base._admin_required()
    required = _required_code(code)
    current = _mapping_row(required) or {}
    body = await request.json()
    name = _txt(body.get('name')) or _suggested_name(required, current)
    remote_code = _txt(body.get('code')) or required
    vat_rate = _txt(body.get('vat_rate') or '0') or '0'
    unit = (_txt(body.get('unit')) or _txt(current.get('unit')) or 'ADET').upper()
    if not name or not remote_code:
        raise HTTPException(status_code=400, detail='Yeni ürün adı ve kodu boş olamaz.')

    # Do not create duplicates blindly. Search synchronized DB and KolayBi live first.
    wanted_name = _norm(name)
    wanted_code = _norm(remote_code)
    exact = {}
    for row in saleprod._local_product_rows():
        row_name = saleprod._product_name(row)
        row_code = saleprod._product_code(row)
        if (row_name and _norm(row_name) == wanted_name) or (row_code and _norm(row_code) == wanted_code):
            pid = _txt(row.get('product_id'))
            if pid:
                exact[pid] = saleprod._candidate_view(row, 'LOCAL DB')
    if not exact:
        for term in (remote_code, name):
            try:
                live_rows = saleprod._live_products(term)
            except Exception:
                live_rows = []
            for row in live_rows:
                if (_norm(row.get('name')) == wanted_name or (row.get('code') and _norm(row.get('code')) == wanted_code)):
                    pid = _txt(row.get('product_id'))
                    if pid:
                        exact[pid] = row
    if exact:
        vals = list(exact.values())
        if len(vals) == 1:
            x = vals[0]
            raise HTTPException(status_code=409, detail=f"Bu ürün KolayBi'de zaten var. Product ID: {x.get('product_id')} | {x.get('name')}. Yeni oluşturma yerine mevcut ürünü eşleştir.")
        raise HTTPException(status_code=409, detail='Aynı isim/koda uyan birden fazla KolayBi ürünü bulundu. Yeni ürün oluşturulmadı; mevcut ürünlerden birini seç.')

    try:
        result = sender._post_form('products', {'name': name, 'code': remote_code, 'vat_rate': vat_rate})
    except Exception as exc:
        raise HTTPException(status_code=502, detail='KolayBi yeni PURCHASE ürünü oluşturulamadı: ' + str(exc))

    pid = saleprod._product_id(result)
    if not pid:
        matches = []
        try:
            matches = saleprod._live_products(remote_code)
        except Exception:
            matches = []
        uniq = {
            _txt(x.get('product_id')): x for x in matches
            if _txt(x.get('product_id')) and x.get('code') and _norm(x.get('code')) == wanted_code
        }
        if len(uniq) == 1:
            pid = next(iter(uniq))
    if not _txt(pid).isdigit():
        raise HTTPException(status_code=502, detail='KolayBi ürünü oluşturuldu yanıtı geldi ancak Product ID doğrulanamadı. Otomatik eşleştirme yapılmadı.')

    saleprod._cache_product({'id': pid, 'name': name, 'code': remote_code, 'unit': unit})
    mapped = _save_mapping(required, pid, name, unit, 'CREATED FROM SAMA PURCHASE -> ' + remote_code)
    return {
        'ok': True,
        'created': True,
        'required_code': required,
        'product': {
            'product_id': _txt(pid),
            'name': name,
            'code': remote_code,
            'unit': _txt(mapped.get('unit')) or unit,
            'source': 'CREATED FROM SAMA PURCHASE',
        },
    }


# PURCHASE UI resolver. Wrap the established V2 loader instead of rewriting it, so
# every later preview/serial/cari patch remains authoritative. No extra script block.
helper = r'''
async function kbPurchaseProductToolsRefresh(){
  const scna=String(document.getElementById('kbSingleScna')?.value||'').trim();
  const pb=document.getElementById('kbPurchaseBody');if(!scna||!pb)return;
  let old=document.getElementById('kbPurchaseProductTools');if(old)old.remove();
  try{
    const x=await api('/api/kolaybi/transaction/'+encodeURIComponent(scna));
    const p=x.purchase||{},codes=(p.missing_product_codes||[]).filter(Boolean);
    if(!codes.length)return;
    const box=document.createElement('div');box.id='kbPurchaseProductTools';box.className='kb-purchase-product-tools';
    box.innerHTML=`<div class="kb-missing"><b>EKSİK PURCHASE ÜRÜNÜNÜ ÇÖZ</b><br><small>Önce mevcut KolayBi ürününü ara/eşleştir. Gerçekten yoksa yeni ürün oluştur.</small></div>`+
      codes.map(code=>`<div class="kb-roleline"><b>${kbEsc(code)}</b> &nbsp; Product ID eksik<div style="display:flex;gap:7px;flex-wrap:wrap;margin-top:7px"><button class="btn secondary" onclick="kbPurchaseProductOpen('${kbEsc(code)}')">ÜRÜN ARA / EŞLEŞTİR</button><button class="btn primary" onclick="kbPurchaseProductOpen('${kbEsc(code)}',true)">YENİ ÜRÜN OLUŞTUR</button></div></div>`).join('');
    const miss=pb.querySelector('.kb-missing');if(miss)miss.insertAdjacentElement('afterend',box);else pb.prepend(box);
  }catch(_e){}
}
async function kbPurchaseProductOpen(code,focusCreate=false){
  const box=document.getElementById('kbPurchaseProductTools');if(!box)return;
  box.innerHTML='<span class="section-note">PURCHASE ÜRÜNLERİ ARANIYOR...</span>';
  try{const r=await api('/api/kolaybi/purchase-product/'+encodeURIComponent(code)+'/candidates?live=true');kbPurchaseProductRender(code,r,focusCreate);}
  catch(e){box.innerHTML='<span class="kb-missing">'+kbEsc(e.message||e)+'</span>';}
}
function kbPurchaseProductRender(code,r,focusCreate=false){
  const box=document.getElementById('kbPurchaseProductTools');if(!box)return;
  const rows=r.candidates||[];
  const opts=rows.map(x=>`<option value="${kbEsc(x.product_id)}">${kbEsc((x.name||'-')+' | ID:'+(x.product_id||'-')+' | CODE:'+(x.code||'-')+' | '+(x.source||''))}</option>`).join('');
  box.innerHTML=`<div class="kb-roleline"><b>PURCHASE ÜRÜN ÇÖZÜMLEYİCİ:</b> ${kbEsc(code)}</div>
    <div style="display:flex;gap:7px;flex-wrap:wrap;align-items:end;margin-top:7px">
      <div class="field" style="min-width:220px;flex:1"><label>ÜRÜN ADI / KODU ARA</label><input id="kbPurchaseProductName" value="${kbEsc(r.search_name||r.suggested_name||code)}"></div>
      <button class="btn secondary" onclick="kbPurchaseProductSearch('${kbEsc(code)}')">DB + KOLAYBI ARA</button>
    </div>
    <div style="display:flex;gap:7px;flex-wrap:wrap;align-items:end;margin-top:7px">
      <div class="field" style="min-width:300px;flex:1"><label>MEVCUT ÜRÜNÜ SEÇ</label><select id="kbPurchaseProductSelect"><option value="">SEÇİLMEDİ</option>${opts}</select></div>
      <button class="btn primary" onclick="kbPurchaseProductApply('${kbEsc(code)}')">SEÇİLEN ÜRÜNÜ EŞLEŞTİR</button>
    </div>
    <div class="kb-roleline" style="margin-top:10px"><b>YENİ ÜRÜN OLUŞTUR</b>
      <div style="display:flex;gap:7px;flex-wrap:wrap;align-items:end;margin-top:7px">
        <div class="field" style="min-width:220px;flex:1"><label>ÜRÜN ADI</label><input id="kbPurchaseNewProductName" value="${kbEsc(r.suggested_name||code)}"></div>
        <div class="field" style="min-width:150px"><label>ÜRÜN KODU</label><input id="kbPurchaseNewProductCode" value="${kbEsc(r.suggested_code||code)}"></div>
        <div class="field" style="width:90px"><label>KDV %</label><input id="kbPurchaseNewProductVat" value="0"></div>
        <button class="btn primary" id="kbPurchaseCreateBtn" onclick="kbPurchaseProductCreate('${kbEsc(code)}')">KOLAYBI'DE ÜRÜN OLUŞTUR</button>
      </div><small>Yeni ürün ancak onaydan sonra gerçek KolayBi hesabında oluşturulur.</small>
    </div>`;
  if(focusCreate)setTimeout(()=>document.getElementById('kbPurchaseNewProductName')?.focus(),50);
}
async function kbPurchaseProductSearch(code){
  const name=String(document.getElementById('kbPurchaseProductName')?.value||'').trim();
  const box=document.getElementById('kbPurchaseProductTools');if(box)box.innerHTML='<span class="section-note">ÜRÜN ARANIYOR...</span>';
  try{const r=await api('/api/kolaybi/purchase-product/'+encodeURIComponent(code)+'/candidates?live=true&name='+encodeURIComponent(name));kbPurchaseProductRender(code,r,false);}
  catch(e){if(box)box.innerHTML='<span class="kb-missing">'+kbEsc(e.message||e)+'</span>';}
}
async function kbPurchaseProductApply(code){
  const pid=String(document.getElementById('kbPurchaseProductSelect')?.value||'').trim();
  if(!pid){alert('Önce mevcut KolayBi ürününü seç.');return;}
  try{const r=await api('/api/kolaybi/purchase-product/'+encodeURIComponent(code)+'/select',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({product_id:pid})});alert(code+' eşleştirildi. Product ID: '+(r.product?.product_id||pid));await kbLoadSingleV2();}
  catch(e){alert(e.message||e);}
}
async function kbPurchaseProductCreate(code){
  const name=String(document.getElementById('kbPurchaseNewProductName')?.value||'').trim();
  const remoteCode=String(document.getElementById('kbPurchaseNewProductCode')?.value||'').trim();
  const vat=String(document.getElementById('kbPurchaseNewProductVat')?.value||'0').trim()||'0';
  if(!name||!remoteCode){alert('Yeni ürün adı ve kodu boş olamaz.');return;}
  if(!confirm(`KolayBi'de GERÇEK YENİ ÜRÜN oluşturulsun mu?\n\nAd: ${name}\nKod: ${remoteCode}\nPURCHASE eşleştirmesi: ${code}`))return;
  const btn=document.getElementById('kbPurchaseCreateBtn');if(btn)btn.disabled=true;
  try{const r=await api('/api/kolaybi/purchase-product/'+encodeURIComponent(code)+'/create',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:name,code:remoteCode,vat_rate:vat})});alert('Ürün oluşturuldu ve '+code+' eşleştirildi. Product ID: '+(r.product?.product_id||'-'));await kbLoadSingleV2();}
  catch(e){alert(e.message||e);if(btn)btn.disabled=false;}
}
const _kbLoadSingleV2PurchaseBase=kbLoadSingleV2;
kbLoadSingleV2=async function(){await _kbLoadSingleV2PurchaseBase();await kbPurchaseProductToolsRefresh();};
'''

marker = 'async function kbPreview(){'
if marker in html and '_kbLoadSingleV2PurchaseBase' not in html:
    html = html.replace(marker, helper + '\n' + marker, 1)

css = '.kb-purchase-product-tools{margin:8px 0;padding:9px;border:1px solid var(--line);border-radius:10px;background:var(--soft)}'
if '</style>' in html and '.kb-purchase-product-tools{' not in html:
    html = html.replace('</style>', css + '</style>', 1)

core.HTML = html
print('[SAMA] KolayBi PURCHASE missing-product resolver active: search/map/create with duplicate guard')
