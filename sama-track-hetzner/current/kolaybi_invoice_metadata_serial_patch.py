import contextvars
import json
import re
import time
from fastapi import Request, HTTPException

import kolaybi_transaction_preview_final_patch as final

app = final.app
core = final.core
legacy = final.legacy
v3 = final.v3
workflow = final.workflow
kdb = legacy.kdb
sync = workflow.sync
sender = workflow.sender
html = core.HTML


def _txt(v):
    return str(v or '').strip()


def _norm(v):
    s = _txt(v).upper().replace(' ', '')
    return re.sub(r'[^A-Z0-9]+', '', s)


def _serial_default(scna):
    full_no, _num = workflow._numbers(scna)
    return full_no


def _serial_clean(v, default=''):
    s = _txt(v).upper().replace(' ', '')
    if not s:
        return _txt(default)
    if s.isdigit():
        return 'SNCA' + s
    if s.startswith('SCNA'):
        return 'SNCA' + s[4:]
    return s


def _default_description(scna):
    trip = workflow._trip(scna)
    full_no, _num = workflow._numbers(scna)
    parts = [full_no]
    driver = _txt(trip.get('driver_name'))
    plate = _txt(trip.get('plate'))
    weight = float(trip.get('net_kg') or 0)
    if driver:
        parts.append('DRIVER: ' + driver)
    if plate:
        parts.append('PLATE: ' + plate)
    if weight > 0:
        parts.append('WEIGHT: ' + final._fmt(weight) + ' KG')
    return '\n'.join(parts)


# Persistent invoice metadata, plus the old program's remote invoice-serial cache idea.
c = kdb()
try:
    c.executescript('''
    CREATE TABLE IF NOT EXISTS invoice_metadata_overrides(
      scna TEXT NOT NULL COLLATE NOCASE,
      doc_kind TEXT NOT NULL COLLATE NOCASE,
      serial_no TEXT DEFAULT '',
      description TEXT DEFAULT '',
      updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      PRIMARY KEY(scna,doc_kind)
    );
    CREATE TABLE IF NOT EXISTS remote_invoice_serial_terms(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      term TEXT NOT NULL COLLATE NOCASE,
      doc_kind TEXT DEFAULT '' COLLATE NOCASE,
      document_id TEXT DEFAULT '',
      document_no TEXT DEFAULT '',
      serial_no TEXT DEFAULT '',
      invoice_number TEXT DEFAULT '',
      description TEXT DEFAULT '',
      raw_type TEXT DEFAULT '',
      updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS idx_remote_invoice_serial_term_kind
      ON remote_invoice_serial_terms(term,doc_kind);
    CREATE TABLE IF NOT EXISTS remote_invoice_serial_state(
      key TEXT PRIMARY KEY,
      value TEXT DEFAULT '',
      updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    ''')
    c.commit()
finally:
    c.close()


def _saved_meta(scna, kind):
    c = kdb()
    try:
        r = c.execute('''SELECT * FROM invoice_metadata_overrides
                         WHERE UPPER(scna)=UPPER(?) AND UPPER(doc_kind)=UPPER(?)''',
                      (_txt(scna), _txt(kind))).fetchone()
        return dict(r) if r else None
    finally:
        c.close()


def _meta(scna, kind):
    default_serial = _serial_default(scna)
    default_desc = _default_description(scna)
    saved = _saved_meta(scna, kind) or {}
    serial = _serial_clean(saved.get('serial_no'), default_serial)
    description = _txt(saved.get('description')) or default_desc
    full_no, invoice_no = workflow._numbers(scna)
    return {
        'scna': _txt(scna),
        'doc_kind': _txt(kind).upper(),
        'document_no': full_no,
        'invoice_number': invoice_no,
        'default_serial_no': default_serial,
        'serial_no': serial,
        'default_description': default_desc,
        'description': description,
        'custom_serial': bool(_txt(saved.get('serial_no'))),
        'custom_description': bool(_txt(saved.get('description'))),
        'updated_at': _txt(saved.get('updated_at')),
    }


def _kind_text(obj):
    if isinstance(obj, dict):
        vals=[]
        for k in ('value','key','group','name','title','description','type'):
            if obj.get(k) not in (None,''):
                vals.append(_kind_text(obj.get(k)))
        return ' '.join(x for x in vals if x)
    if isinstance(obj, list):
        return ' '.join(_kind_text(x) for x in obj)
    return _txt(obj)


def _doc_kind(row):
    if not isinstance(row, dict):
        return ''
    raw = ' '.join([
        _kind_text(row.get('commercial_doc_type')),
        _kind_text(row.get('type')),
        _kind_text(row.get('document_type')),
        _kind_text(row.get('type_group')),
        _kind_text(row.get('type_key')),
    ]).lower()
    n = raw.replace('ı','i').replace('ş','s')
    if any(x in n for x in ('purchase','purchas','buy','alis','gider','expense','supplier')):
        return 'PURCHASE'
    if any(x in n for x in ('sale','sales','sell','satis','gelir','customer invoice')):
        return 'SALE'
    return ''


def _row_value(row, keys):
    if not isinstance(row, dict):
        return ''
    for key in keys:
        v = row.get(key)
        if isinstance(v, dict):
            got = _row_value(v, keys)
            if got:
                return got
        elif v not in (None,''):
            return _txt(v)
    for child in ('data','header','invoice','commercial_document','commercialDoc','document'):
        v = row.get(child)
        if isinstance(v, dict):
            got = _row_value(v, keys)
            if got:
                return got
    return ''


def _terms_from_value(value):
    raw = _txt(value).upper().replace(' ', '')
    if not raw:
        return []
    out=[]
    def add(x):
        x=_txt(x).upper().replace(' ','')
        if x and x not in out:
            out.append(x)
    add(raw)
    stripped = raw
    if stripped.startswith('SNCA') or stripped.startswith('SCNA'):
        stripped = stripped[4:]
    if stripped:
        add(stripped)
        add('SNCA'+stripped)
        add('SCNA'+stripped)
    return out


def _row_terms(row):
    values=[]
    for keys in [
        ('document_no','document_number','commercial_document_no','commercial_doc_no','doc_no'),
        ('serial_no','full_number','number'),
        ('invoice_number',),
        ('description','note'),
    ]:
        v=_row_value(row,keys)
        if v:
            values.append(v)
    terms=[]
    for v in values:
        for t in _terms_from_value(v):
            if t not in terms:
                terms.append(t)
    return terms


def _remote_state():
    c=kdb()
    try:
        rows=c.execute('SELECT key,value,updated_at FROM remote_invoice_serial_state').fetchall()
        out={str(r['key']):str(r['value'] or '') for r in rows}
        if rows:
            out['updated_at']=max(str(r['updated_at'] or '') for r in rows)
        return out
    finally:
        c.close()


def _remote_matches(value, kind):
    terms=_terms_from_value(value)
    if not terms:
        return []
    placeholders=','.join('?' for _ in terms)
    c=kdb()
    try:
        rows=c.execute(f'''SELECT * FROM remote_invoice_serial_terms
                           WHERE UPPER(term) IN ({placeholders}) AND UPPER(doc_kind)=UPPER(?)
                           ORDER BY id DESC LIMIT 10''', (*[t.upper() for t in terms], _txt(kind))).fetchall()
        uniq={}
        for r in rows:
            x=dict(r)
            key=_txt(x.get('document_id')) or (_txt(x.get('document_no'))+'|'+_txt(x.get('serial_no'))+'|'+_txt(x.get('doc_kind')))
            uniq[key]=x
        return list(uniq.values())
    finally:
        c.close()


def _fetch_remote_serials(max_pages=20, page_size=100):
    rows=[]; seen=set(); errors=[]
    for page in range(1,max_pages+1):
        page_rows=[]
        for params in ({'page':page,'per_page':page_size},{'page':page,'limit':page_size}):
            try:
                page_rows=sync._rows(sync._get('invoices',params))
                if page_rows:
                    break
            except Exception as e:
                errors.append(str(e))
        if not page_rows:
            if page==1:
                try:
                    page_rows=sync._rows(sync._get('invoices',{}))
                except Exception as e:
                    errors.append(str(e))
            if not page_rows:
                break
        new=0
        for row in page_rows:
            did=_row_value(row,('id','document_id','commercial_doc_id'))
            serial=_row_value(row,('serial_no','full_number','number'))
            docno=_row_value(row,('document_no','document_number','commercial_document_no','commercial_doc_no','doc_no'))
            invno=_row_value(row,('invoice_number',))
            typ=_kind_text(row.get('commercial_doc_type') or row.get('type') or row.get('document_type'))
            key=did or (serial+'|'+docno+'|'+invno+'|'+typ)
            if not key or key in seen:
                continue
            seen.add(key); rows.append(row); new+=1
        if new==0 or len(page_rows)<page_size:
            break
    return rows, errors[-12:]


def _refresh_remote_serial_cache():
    rows, errors = _fetch_remote_serials()
    c=kdb(); terms_count=0
    try:
        c.execute('DELETE FROM remote_invoice_serial_terms')
        for row in rows:
            did=_row_value(row,('id','document_id','commercial_doc_id'))
            docno=_row_value(row,('document_no','document_number','commercial_document_no','commercial_doc_no','doc_no'))
            serial=_row_value(row,('serial_no','full_number','number'))
            invno=_row_value(row,('invoice_number',))
            desc=_row_value(row,('description','note'))
            raw_type=_kind_text(row.get('commercial_doc_type') or row.get('type') or row.get('document_type'))
            kind=_doc_kind(row)
            for term in _row_terms(row):
                c.execute('''INSERT INTO remote_invoice_serial_terms(term,doc_kind,document_id,document_no,serial_no,invoice_number,description,raw_type,updated_at)
                             VALUES(?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)''',
                          (term,kind,did,docno,serial,invno,desc,raw_type))
                terms_count+=1
        now=time.strftime('%Y-%m-%d %H:%M:%S')
        for key,value in [('last_refresh',now),('document_count',str(len(rows))),('term_count',str(terms_count)),('errors',json.dumps(errors,ensure_ascii=False))]:
            c.execute('''INSERT INTO remote_invoice_serial_state(key,value,updated_at) VALUES(?,?,CURRENT_TIMESTAMP)
                         ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_at=CURRENT_TIMESTAMP''',(key,value))
        c.commit()
    finally:
        c.close()
    return {'ok':True,'document_count':len(rows),'term_count':terms_count,'warnings':errors,'last_refresh':time.strftime('%Y-%m-%d %H:%M:%S')}


@app.get('/api/kolaybi/transaction/{scna}/metadata')
def kb_invoice_metadata(scna:str):
    p=_meta(scna,'PURCHASE'); s=_meta(scna,'SALE')
    p['remote_matches']=_remote_matches(p['serial_no'],'PURCHASE') or _remote_matches(scna,'PURCHASE')
    s['remote_matches']=_remote_matches(s['serial_no'],'SALE') or _remote_matches(scna,'SALE')
    return {'ok':True,'purchase':p,'sale':s,'serial_cache':_remote_state()}


@app.post('/api/kolaybi/transaction/{scna}/metadata/{kind}')
async def kb_invoice_metadata_save(scna:str, kind:str, request:Request):
    sync.base._admin_required()
    kind=_txt(kind).upper()
    if kind not in ('PURCHASE','SALE'):
        raise HTTPException(status_code=400,detail='Belge türü PURCHASE veya SALE olmalı.')
    b=await request.json()
    default_serial=_serial_default(scna)
    serial=_serial_clean(b.get('serial_no'),default_serial)
    desc=_txt(b.get('description'))
    # Empty description means reset to the proven automatic format.
    if desc == _default_description(scna):
        desc=''
    if serial == default_serial:
        stored_serial=''
    else:
        stored_serial=serial
    c=kdb()
    try:
        c.execute('''INSERT INTO invoice_metadata_overrides(scna,doc_kind,serial_no,description,updated_at)
                     VALUES(?,?,?,?,CURRENT_TIMESTAMP)
                     ON CONFLICT(scna,doc_kind) DO UPDATE SET serial_no=excluded.serial_no,description=excluded.description,updated_at=CURRENT_TIMESTAMP''',
                  (_txt(scna),kind,stored_serial,desc))
        c.commit()
    finally:
        c.close()
    return {'ok':True,**_meta(scna,kind)}


@app.post('/api/kolaybi/serial-cache/refresh')
def kb_invoice_serial_refresh():
    sync.base._admin_required()
    try:
        return _refresh_remote_serial_cache()
    except Exception as e:
        raise HTTPException(status_code=502,detail='KolayBi fatura serial listesi yenilenemedi: '+str(e))


# Both PURCHASE and SALE already carried serial_no in V2; this context wrapper makes
# the explicit UI metadata authoritative without rewriting the proven send engine.
_SEND_META=contextvars.ContextVar('kolaybi_send_meta',default=None)
_original_post_form=sender._post_form


def _post_form_with_invoice_meta(path,payload):
    ctx=_SEND_META.get()
    if ctx and isinstance(payload,dict):
        payload['serial_no']=_txt(ctx.get('serial_no'))
        payload['description']=_txt(ctx.get('description'))
    return _original_post_form(path,payload)


sender._post_form=_post_form_with_invoice_meta


def _assert_remote_not_duplicate(scna,kind,meta):
    matches=_remote_matches(meta.get('serial_no'),kind) or _remote_matches(scna,kind)
    if matches:
        m=matches[0]
        raise HTTPException(status_code=409,detail=(
            f'KolayBi serial cache içinde aynı {kind} belgesi zaten var. '
            f'Document ID: {_txt(m.get("document_id")) or "-"} | '
            f'Document No: {_txt(m.get("document_no")) or "-"} | Serial: {_txt(m.get("serial_no")) or "-"}'
        ))


def kb_purchase_send_metadata(scna:str):
    meta=_meta(scna,'PURCHASE')
    _assert_remote_not_duplicate(scna,'PURCHASE',meta)
    tok=_SEND_META.set(meta)
    try:
        return workflow.kb_purchase_send_v2(scna)
    finally:
        _SEND_META.reset(tok)


def kb_sale_send_metadata(scna:str):
    meta=_meta(scna,'SALE')
    _assert_remote_not_duplicate(scna,'SALE',meta)
    tok=_SEND_META.set(meta)
    try:
        return workflow.kb_sale_send_v2(scna)
    finally:
        _SEND_META.reset(tok)


for route in app.routes:
    path=getattr(route,'path',None)
    methods=getattr(route,'methods',set()) or set()
    if path=='/api/kolaybi/transaction/{scna}/purchase/send' and 'POST' in methods:
        route.endpoint=kb_purchase_send_metadata
        if getattr(route,'dependant',None) is not None:
            route.dependant.call=kb_purchase_send_metadata
    elif path=='/api/kolaybi/transaction/{scna}/sale/send' and 'POST' in methods:
        route.endpoint=kb_sale_send_metadata
        if getattr(route,'dependant',None) is not None:
            route.dependant.call=kb_sale_send_metadata


# Surface the fields on the single-SCNA screen instead of hiding them inside the payload.
serial_button='<button class="btn secondary" onclick="kbSyncReferenceV2()">CARİ / ÜRÜN VERİSİNİ YENİLE</button>'
if serial_button in html and 'kbRefreshInvoiceSerials()' not in html:
    html=html.replace(serial_button,serial_button+'<button class="btn secondary" onclick="kbRefreshInvoiceSerials()">FATURA SERIAL LİSTESİNİ YENİLE</button>',1)

helper=r'''
function kbMetaBox(scna,kind,m,cache){
  const low=kind==='PURCHASE'?'Purchase':'Sale';
  const dup=(m.remote_matches||[]).length;
  const last=cache?.last_refresh||'-';
  return `<div class="calc" style="margin:8px 0;background:rgba(127,127,127,.04)">
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px">
      <div><small>DOCUMENT NO</small><br><b>${kbEsc(m.document_no||'-')}</b></div>
      <div><small>INVOICE NUMBER</small><br><b>${kbEsc(m.invoice_number||'-')}</b></div>
    </div>
    <div class="field" style="margin-top:8px"><label>SERIAL NO</label><input id="kb${low}Serial" value="${kbEsc(m.serial_no||'')}"></div>
    <div class="field" style="margin-top:8px"><label>FATURA AÇIKLAMASI / DESCRIPTION</label><textarea id="kb${low}Description" rows="5" style="width:100%">${kbEsc(m.description||'')}</textarea></div>
    <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-top:8px">
      <button class="btn secondary" onclick="kbSaveDocMeta('${kbEsc(scna)}','${kind}')">BELGE BİLGİLERİNİ KAYDET</button>
      <small>Varsayılan serial: ${kbEsc(m.default_serial_no||'-')} | Serial cache: ${kbEsc(last)}</small>
      ${dup?'<span class="kb-missing">⚠ KOLAYBI\'DE AYNI '+kind+' SERIAL KAYDI VAR</span>':''}
    </div>
  </div>`;
}
async function kbLoadDocMeta(scna){
  try{
    const m=await api('/api/kolaybi/transaction/'+encodeURIComponent(scna)+'/metadata');
    const pb=document.getElementById('kbPurchaseBody'),sb=document.getElementById('kbSaleBody');
    if(pb)pb.insertAdjacentHTML('afterbegin',kbMetaBox(scna,'PURCHASE',m.purchase||{},m.serial_cache||{}));
    if(sb)sb.insertAdjacentHTML('afterbegin',kbMetaBox(scna,'SALE',m.sale||{},m.serial_cache||{}));
  }catch(e){console.error(e);}
}
async function kbSaveDocMeta(scna,kind){
  const low=kind==='PURCHASE'?'Purchase':'Sale';
  const serial=document.getElementById('kb'+low+'Serial')?.value||'';
  const description=document.getElementById('kb'+low+'Description')?.value||'';
  const state=document.getElementById('kbSingleState');
  try{
    const r=await api('/api/kolaybi/transaction/'+encodeURIComponent(scna)+'/metadata/'+kind,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({serial_no:serial,description:description})});
    if(state)state.innerHTML='<span class="kb-ready">✓ '+kind+' BELGE BİLGİLERİ KAYDEDİLDİ | SERIAL '+kbEsc(r.serial_no||'-')+'</span>';
  }catch(e){if(state)state.innerHTML='<span class="kb-missing">'+kbEsc(e.message||e)+'</span>';}
}
async function kbRefreshInvoiceSerials(){
  const state=document.getElementById('kbSingleState');if(state)state.textContent='KOLAYBI FATURA SERIAL LİSTESİ YENİLENİYOR...';
  try{
    const r=await api('/api/kolaybi/serial-cache/refresh',{method:'POST'});
    if(state)state.innerHTML='<span class="kb-ready">✓ SERIAL CACHE YENİLENDİ | Belge '+(r.document_count||0)+' | Index '+(r.term_count||0)+'</span>';
    const scna=String(document.getElementById('kbSingleScna')?.value||'').trim();if(scna)await kbLoadSingleV2();
  }catch(e){if(state)state.innerHTML='<span class="kb-missing">'+kbEsc(e.message||e)+'</span>';}
}
'''
marker='async function kbLoadSingleV2(){'
if marker in html and 'async function kbLoadDocMeta' not in html:
    html=html.replace(marker,helper+'\n'+marker,1)

ready_line="if(state)state.innerHTML='<span class=\"kb-ready\">SCNA HAZIRLANDI</span>';"
if ready_line in html and 'await kbLoadDocMeta(scna);' not in html:
    html=html.replace(ready_line,'await kbLoadDocMeta(scna);'+ready_line,1)

core.HTML=html
print('[SAMA] KolayBi invoice metadata active: visible serial/document numbers + editable descriptions + remote serial duplicate cache')
