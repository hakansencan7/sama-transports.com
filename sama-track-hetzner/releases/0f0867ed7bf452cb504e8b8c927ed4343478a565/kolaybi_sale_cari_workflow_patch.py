import re
from fastapi import Request, HTTPException

import kolaybi_transaction_preview_final_patch as final

app = final.app
core = final.core
workflow = final.workflow
v3 = final.v3
legacy = final.legacy
kdb = legacy.kdb
sync = workflow.sync
sender = workflow.sender
html = core.HTML


def _txt(v):
    return str(v or '').strip()


def _norm(v):
    return v3._norm(v)


def _any_id(obj):
    if isinstance(obj, dict):
        for key in ('id', 'contact_id', 'associate_id', 'address_id'):
            val = _txt(obj.get(key))
            if val:
                return val
        data = obj.get('data')
        if isinstance(data, dict):
            return _any_id(data)
        if isinstance(data, list):
            for row in data:
                got = _any_id(row)
                if got:
                    return got
    if isinstance(obj, list):
        for row in obj:
            got = _any_id(row)
            if got:
                return got
    return ''


c = kdb()
try:
    c.executescript('''
    CREATE TABLE IF NOT EXISTS sale_contact_overrides(
      scna TEXT PRIMARY KEY COLLATE NOCASE,
      original_customer TEXT DEFAULT '',
      selected_name TEXT DEFAULT '',
      contact_id TEXT DEFAULT '',
      address_id TEXT DEFAULT '',
      source TEXT DEFAULT '',
      updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    ''')
    c.commit()
finally:
    c.close()


def _override(scna):
    c = kdb()
    try:
        r = c.execute('SELECT * FROM sale_contact_overrides WHERE UPPER(scna)=UPPER(?)', (_txt(scna),)).fetchone()
        return dict(r) if r else None
    finally:
        c.close()


def _save_override(scna, original_customer, contact, source):
    cid = _txt((contact or {}).get('contact_id') or (contact or {}).get('id'))
    if not cid:
        raise HTTPException(status_code=400, detail='Contact ID boş; SALE cari seçimi kaydedilemez.')
    name = v3._display(contact) or _txt((contact or {}).get('name')) or _txt(original_customer)
    aid = _txt((contact or {}).get('address_id'))
    c = kdb()
    try:
        c.execute('''INSERT INTO sale_contact_overrides(scna,original_customer,selected_name,contact_id,address_id,source,updated_at)
                     VALUES(?,?,?,?,?,?,CURRENT_TIMESTAMP)
                     ON CONFLICT(scna) DO UPDATE SET original_customer=excluded.original_customer,
                     selected_name=excluded.selected_name,contact_id=excluded.contact_id,
                     address_id=excluded.address_id,source=excluded.source,updated_at=CURRENT_TIMESTAMP''',
                  (_txt(scna), _txt(original_customer), name, cid, aid, _txt(source)))
        c.commit()
    finally:
        c.close()
    return _override(scna)


def _trip_customer(scna):
    trip = workflow._trip(scna)
    return trip, _txt(trip.get('customer_name'))


def _local_contact(cid):
    c = kdb()
    try:
        r = c.execute('''SELECT * FROM associates WHERE contact_id=? AND is_active=1
                         ORDER BY updated_at DESC LIMIT 1''', (_txt(cid),)).fetchone()
        return dict(r) if r else None
    finally:
        c.close()


def _resolve_contact_id(cid):
    row = _local_contact(cid)
    if row:
        return v3._enrich_cached(row)
    detail = v3._detail(cid)
    if isinstance(detail, dict):
        cached = v3._cache_live_assoc(detail)
        if cached:
            return v3._enrich_cached(cached)
        detail = dict(detail)
        detail['contact_id'] = _txt(cid)
        detail['address_id'] = v3.base._address_id(detail)
        return detail
    return None


def _candidate_rows(term):
    wanted = _norm(term)
    if not wanted:
        return []
    rows = v3._local_rows()
    exact, contains = [], []
    seen = set()
    for row in rows:
        cid = _txt(row.get('contact_id'))
        if not cid or cid in seen:
            continue
        vals = [
            v3._display(row), row.get('name'), row.get('full_name'),
            row.get('key'), row.get('source_code')
        ]
        norms = [_norm(x) for x in vals if _txt(x)]
        if wanted in norms:
            exact.append(row)
            seen.add(cid)
        elif any(wanted in x for x in norms):
            contains.append(row)
            seen.add(cid)
    return (exact + contains)[:25]


def _candidate_view(row, source='DB'):
    return {
        'name': v3._display(row) or _txt(row.get('name')) or '-',
        'contact_id': _txt(row.get('contact_id') or row.get('id')),
        'address_id': _txt(row.get('address_id') or v3.base._address_id(row)),
        'code': _txt(row.get('source_code') or row.get('key') or row.get('code')),
        'source': source,
    }


def _ensure_address(contact_id):
    cid = _txt(contact_id)
    if not cid:
        raise HTTPException(status_code=400, detail='Contact ID boş.')
    detail = v3._detail(cid)
    if isinstance(detail, dict):
        aid = _txt(v3.base._address_id(detail))
        if aid:
            return aid

    payload_options = [
        {'associate_id': cid, 'address': 'Merkez', 'country': 'Türkiye', 'city': 'İstanbul', 'district': 'Fatih', 'address_type': 'invoice', 'is_abroad': '0'},
        {'associate_id': cid, 'address': 'Merkez', 'country': 'Turkey', 'city': 'Istanbul', 'district': 'Fatih', 'address_type': 'invoice', 'is_abroad': '0'},
        {'associate_id': cid, 'address': 'Umm Qasr / Basra', 'country': 'Irak', 'city': 'Basra', 'district': 'Umm Qasr', 'address_type': 'invoice', 'is_abroad': '1',
         'street': 'Umm Qasr', 'building_name': 'SAMA', 'number': '1', 'postal_code': '00000', 'address_location': 'other'},
        {'associate_id': cid, 'address': 'Umm Qasr / Basra', 'country': 'Iraq', 'city': 'Basra', 'district': 'Umm Qasr', 'address_type': 'invoice', 'is_abroad': '1',
         'street': 'Umm Qasr', 'building_name': 'SAMA', 'number': '1', 'postal_code': '00000', 'address_location': 'other'},
    ]
    errors = []
    for payload in payload_options:
        try:
            resp = sender._post_form('address/create', payload)
            aid = _any_id(resp)
            if aid:
                c = kdb()
                try:
                    c.execute('UPDATE associates SET address_id=?,updated_at=CURRENT_TIMESTAMP WHERE contact_id=?', (aid, cid))
                    c.commit()
                finally:
                    c.close()
                return aid
        except Exception as e:
            errors.append(str(e))
    raise HTTPException(status_code=502, detail='SALE adresi oluşturulamadı: ' + ' | '.join(errors[-3:]))


def _identity(name):
    source = _txt(name)
    digits = ''.join(ch for ch in source if ch.isdigit())
    if len(digits) >= 10:
        return digits[-10:]
    total = sum((i + 1) * ord(ch) for i, ch in enumerate(source))
    suffix = str(total % 100000).zfill(5)
    return (digits + suffix + '0000000000')[:10]


def _create_sale_contact(name):
    name = _txt(name)
    if not name:
        raise HTTPException(status_code=400, detail='Yeni SALE cari adı boş olamaz.')
    identity_no = _identity(name)
    base_payload = {
        'name': name, 'surname': 'Freight', 'identity_no': identity_no,
        'is_corporate': 'true', 'associate_type': 'customer',
        'alias': name, 'code': name, 'tax_office': 'FATİH',
        'phone': '', 'email': '',
        'addresses[address]': 'Umm Qasr', 'addresses[country]': 'Iraq',
        'addresses[city]': 'Basra', 'addresses[district]': 'Umm Qasr',
        'addresses[address_type]': 'invoice', 'addresses[is_abroad]': 'true',
        'addresses[building_name]': '-', 'addresses[number]': '1',
        'addresses[postal_code]': '00000', 'addresses[street]': 'Umm Qasr',
    }
    payloads = [
        base_payload,
        {
            'name': name, 'surname': 'Freight', 'identity_no': identity_no,
            'is_corporate': 'true', 'associate_type': 'customer', 'code': name,
            'tax_office': 'FATİH', 'addresses[address]': 'Umm Qasr',
            'addresses[country]': 'Iraq', 'addresses[city]': 'Basra',
            'addresses[district]': 'Umm Qasr', 'addresses[address_type]': 'invoice',
        },
        {'name': name, 'surname': 'Freight', 'identity_no': identity_no, 'associate_type': 'customer', 'code': name},
    ]
    errors = []
    response = None
    cid = ''
    for payload in payloads:
        try:
            response = sender._post_form('associates', payload)
            cid = _any_id(response)
            if cid:
                break
        except Exception as e:
            errors.append(str(e))
    if not cid:
        live = v3._live_search(name)
        exact = [r for r in live if _norm(v3._display(r)) == _norm(name)]
        if len(exact) == 1:
            cid = v3.base._rid(exact[0])
            response = exact[0]
    if not cid:
        raise HTTPException(status_code=502, detail='SALE cari oluşturulamadı / Contact ID alınamadı: ' + ' | '.join(errors[-3:]))

    detail = v3._detail(cid)
    if isinstance(detail, dict):
        cached = v3._cache_live_assoc(detail)
        contact = cached or detail
    else:
        contact = {'contact_id': cid, 'name': name, 'full_name': name, 'address_id': ''}
    contact = dict(contact)
    contact['contact_id'] = cid
    contact['name'] = v3._display(contact) or name
    aid = _txt(contact.get('address_id') or (v3.base._address_id(detail) if isinstance(detail, dict) else ''))
    if not aid:
        aid = _ensure_address(cid)
    contact['address_id'] = aid
    return contact


_original_sale_preview = workflow._sale_preview


def _sale_preview_with_override(scna, trip=None, purchase=None):
    sale = _original_sale_preview(scna, trip, purchase)
    ov = _override(scna)
    if not ov:
        sale['sale_contact_override'] = None
        return sale

    contact = _resolve_contact_id(ov.get('contact_id'))
    if not contact:
        contact = {
            'name': _txt(ov.get('selected_name')),
            'full_name': _txt(ov.get('selected_name')),
            'contact_id': _txt(ov.get('contact_id')),
            'address_id': _txt(ov.get('address_id')),
        }
    else:
        contact = dict(contact)
        if not _txt(contact.get('address_id')) and _txt(ov.get('address_id')):
            contact['address_id'] = _txt(ov.get('address_id'))

    sale['contact'] = contact
    sale['contact_source'] = 'USER SELECTED / ' + (_txt(ov.get('source')) or 'SALE OVERRIDE')
    sale['sale_contact_override'] = ov
    sale['selected_contact_name'] = v3._display(contact) or _txt(ov.get('selected_name'))

    missing = []
    for reason in sale.get('missing_reasons') or []:
        text = _txt(reason)
        if text.startswith('SALE CARİ:') or text in ('SALE CONTACT ID', 'SALE ADDRESS ID'):
            continue
        missing.append(text)
    if not _txt(contact.get('contact_id')):
        missing.insert(0, 'SALE CONTACT ID')
    if not _txt(contact.get('address_id')):
        missing.insert(0, 'SALE ADDRESS ID')
    sale['missing_reasons'] = missing
    sale['ready'] = not missing
    return sale


workflow._sale_preview = _sale_preview_with_override


@app.get('/api/kolaybi/sale-contact/{scna}/candidates')
def kb_sale_contact_candidates(scna: str, name: str = '', live: bool = True):
    trip, customer = _trip_customer(scna)
    term = _txt(name) or customer
    local = _candidate_rows(term)
    out = [_candidate_view(r, 'LOCAL DB') for r in local]
    seen = {x['contact_id'] for x in out if x['contact_id']}

    if live:
        try:
            for row in v3._live_search(term):
                cid = _txt(v3.base._rid(row))
                if not cid or cid in seen:
                    continue
                out.append(_candidate_view(row, 'KOLAYBI LIVE'))
                seen.add(cid)
                if len(out) >= 25:
                    break
        except Exception:
            pass

    return {
        'ok': True, 'scna': _txt(scna), 'customer': customer, 'search_name': term,
        'override': _override(scna), 'candidates': out[:25],
    }


@app.post('/api/kolaybi/sale-contact/{scna}/select')
async def kb_sale_contact_select(scna: str, request: Request):
    sync.base._admin_required()
    body = await request.json()
    cid = _txt(body.get('contact_id'))
    if not cid:
        raise HTTPException(status_code=400, detail='Seçilecek Contact ID boş.')
    trip, customer = _trip_customer(scna)
    contact = _resolve_contact_id(cid)
    if not contact:
        raise HTTPException(status_code=404, detail='Seçilen Contact ID KolayBi/local DB içinde bulunamadı: ' + cid)
    ov = _save_override(scna, customer, contact, 'MANUAL CANDIDATE')
    return {'ok': True, 'override': ov, 'contact': contact}


@app.post('/api/kolaybi/sale-contact/{scna}/create')
async def kb_sale_contact_create(scna: str, request: Request):
    sync.base._admin_required()
    body = await request.json()
    name = _txt(body.get('name'))
    trip, customer = _trip_customer(scna)
    contact = _create_sale_contact(name)
    ov = _save_override(scna, customer, contact, 'CREATED FROM SAMA')
    return {'ok': True, 'created': True, 'override': ov, 'contact': contact}


@app.post('/api/kolaybi/sale-contact/{scna}/address')
def kb_sale_contact_address(scna: str):
    sync.base._admin_required()
    ov = _override(scna)
    if not ov or not _txt(ov.get('contact_id')):
        raise HTTPException(status_code=400, detail='Önce SALE carisini seç.')
    aid = _ensure_address(ov.get('contact_id'))
    c = kdb()
    try:
        c.execute('UPDATE sale_contact_overrides SET address_id=?,updated_at=CURRENT_TIMESTAMP WHERE UPPER(scna)=UPPER(?)', (aid, _txt(scna)))
        c.commit()
    finally:
        c.close()
    return {'ok': True, 'address_id': aid, 'override': _override(scna)}


@app.delete('/api/kolaybi/sale-contact/{scna}')
def kb_sale_contact_clear(scna: str):
    sync.base._admin_required()
    c = kdb()
    try:
        c.execute('DELETE FROM sale_contact_overrides WHERE UPPER(scna)=UPPER(?)', (_txt(scna),))
        c.commit()
    finally:
        c.close()
    return {'ok': True}


sale_product_anchor = '<div class="kb-roleline"><b>SALE ÜRÜN:</b>'
sale_tools = '''<div class="kb-roleline" id="kbSaleCariTools"><button class="btn secondary" onclick="kbSaleCariOpen('${kbEsc(scna)}')">SALE CARİ DÜZELT / SEÇ</button></div>'''
if sale_product_anchor in html and 'id="kbSaleCariTools"' not in html:
    html = html.replace(sale_product_anchor, sale_tools + sale_product_anchor, 1)

helper = r'''
async function kbSaleCariOpen(scna){
  const box=document.getElementById('kbSaleCariTools');if(!box)return;
  box.innerHTML='<span class="section-note">CARİ ADAYLARI ARANIYOR...</span>';
  try{
    const r=await api('/api/kolaybi/sale-contact/'+encodeURIComponent(scna)+'/candidates');
    kbSaleCariRender(scna,r);
  }catch(e){box.innerHTML='<span class="kb-missing">'+kbEsc(e.message||e)+'</span>';}
}
function kbSaleCariRender(scna,r){
  const box=document.getElementById('kbSaleCariTools');if(!box)return;
  const ov=r.override||{}, rows=r.candidates||[];
  const opts=rows.map(x=>`<option value="${kbEsc(x.contact_id)}">${kbEsc((x.name||'-')+' | ID:'+ (x.contact_id||'-')+' | Address:'+(x.address_id||'-')+' | '+(x.source||''))}</option>`).join('');
  const current=ov.contact_id?`<div class="kb-ready" style="margin-bottom:7px">SEÇİLİ FATURA CARİ: ${kbEsc(ov.selected_name||'-')} | Contact ID: ${kbEsc(ov.contact_id)} | Address ID: ${kbEsc(ov.address_id||'-')}</div>`:'';
  box.innerHTML=`<b>SALE CARİ DÜZELT / SEÇ</b>${current}
    <div style="display:flex;gap:7px;flex-wrap:wrap;align-items:end;margin-top:7px">
      <div class="field" style="min-width:220px;flex:1"><label>CARİ / TACİR ADI</label><input id="kbSaleCariName" value="${kbEsc(r.search_name||r.customer||'')}"></div>
      <button class="btn secondary" onclick="kbSaleCariSearch('${kbEsc(scna)}')">DB + KOLAYBI ARA</button>
    </div>
    <div style="display:flex;gap:7px;flex-wrap:wrap;align-items:end;margin-top:7px">
      <div class="field" style="min-width:280px;flex:1"><label>UYGUN CARİYİ SEÇ</label><select id="kbSaleCariSelect"><option value="">SEÇİLMEDİ</option>${opts}</select></div>
      <button class="btn primary" onclick="kbSaleCariApply('${kbEsc(scna)}')">SEÇİLEN CARİYİ UYGULA</button>
    </div>
    <div style="display:flex;gap:7px;flex-wrap:wrap;margin-top:8px">
      <button class="btn secondary" onclick="kbSaleCariCreate('${kbEsc(scna)}')">YENİ CARİ OLUŞTUR + ADRES</button>
      ${ov.contact_id&&!ov.address_id?`<button class="btn secondary" onclick="kbSaleCariAddress('${kbEsc(scna)}')">ADDRESS ID TAMAMLA</button>`:''}
      ${ov.contact_id?`<button class="btn danger" onclick="kbSaleCariClear('${kbEsc(scna)}')">SEÇİMİ TEMİZLE</button>`:''}
    </div>
    <small>${rows.length?rows.length+' aday bulundu.':'Aday bulunamadı. İsim doğruysa yeni cari oluşturabilirsin.'} Rastgele cari seçilmez.</small>`;
}
async function kbSaleCariSearch(scna){
  const name=String(document.getElementById('kbSaleCariName')?.value||'').trim();
  const box=document.getElementById('kbSaleCariTools');if(box)box.innerHTML='<span class="section-note">ARANIYOR...</span>';
  try{const r=await api('/api/kolaybi/sale-contact/'+encodeURIComponent(scna)+'/candidates?live=true&name='+encodeURIComponent(name));kbSaleCariRender(scna,r);}
  catch(e){if(box)box.innerHTML='<span class="kb-missing">'+kbEsc(e.message||e)+'</span>';}
}
async function kbSaleCariApply(scna){
  const cid=String(document.getElementById('kbSaleCariSelect')?.value||'').trim();
  if(!cid){alert('Önce cari seç.');return;}
  try{await api('/api/kolaybi/sale-contact/'+encodeURIComponent(scna)+'/select',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({contact_id:cid})});await kbLoadSingleV2();}
  catch(e){alert(e.message||e);}
}
async function kbSaleCariCreate(scna){
  const name=String(document.getElementById('kbSaleCariName')?.value||'').trim();
  if(!name){alert('Cari adı boş.');return;}
  if(!confirm('KolayBi’de YENİ SALE carisi oluşturulsun mu?\n\n'+name+'\n\nPlaka ile değil, bu tacir adıyla oluşturulacak.'))return;
  try{const r=await api('/api/kolaybi/sale-contact/'+encodeURIComponent(scna)+'/create',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:name})});alert('Yeni cari oluşturuldu. Contact ID: '+(r.contact?.contact_id||r.override?.contact_id||'-'));await kbLoadSingleV2();}
  catch(e){alert(e.message||e);}
}
async function kbSaleCariAddress(scna){
  try{const r=await api('/api/kolaybi/sale-contact/'+encodeURIComponent(scna)+'/address',{method:'POST'});alert('Address ID hazır: '+(r.address_id||'-'));await kbLoadSingleV2();}
  catch(e){alert(e.message||e);}
}
async function kbSaleCariClear(scna){
  if(!confirm('Bu SCNA için manuel SALE cari seçimi temizlensin mi?'))return;
  try{await api('/api/kolaybi/sale-contact/'+encodeURIComponent(scna),{method:'DELETE'});await kbLoadSingleV2();}
  catch(e){alert(e.message||e);}
}
'''
marker = 'async function kbLoadSingleV2(){'
if marker in html and 'async function kbSaleCariOpen' not in html:
    html = html.replace(marker, helper + '\n' + marker, 1)

core.HTML = html
print('[SAMA] KolayBi SALE cari workflow active: edit/search -> candidate select -> create customer/address when missing')
