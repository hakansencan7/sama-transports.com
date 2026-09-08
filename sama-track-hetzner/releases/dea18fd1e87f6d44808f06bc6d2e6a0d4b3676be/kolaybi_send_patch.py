import json
import time
import requests
from fastapi import HTTPException
import kolaybi_sync_patch as base

app = base.app
core = base.core
kdb = base.kdb
html = core.HTML


def _num(v):
    try: return float(v or 0)
    except Exception: return 0.0


def _fmt(v):
    n=_num(v)
    s=f'{n:.6f}'.rstrip('0').rstrip('.')
    return s or '0'


def _snca_parts(v):
    raw=str(v or '').strip().upper().replace(' ','')
    for p in ('SNCA','SCNA'):
        if raw.startswith(p): raw=raw[len(p):]; break
    return 'SNCA'+raw, raw


def _post_form(path,payload):
    token=base._token()
    r=base.SESSION.post(
        f'{base.BASE_URL}/{path.lstrip("/")}',
        headers={'Authorization':f'Bearer {token}','Channel':base.CHANNEL,'Content-Type':'application/x-www-form-urlencoded'},
        data=payload, timeout=35,
    )
    if not r.ok:
        raise RuntimeError(f'POST /{path} HTTP {r.status_code}: {(r.text or "")[:1200]}')
    try:return r.json()
    except Exception:return {'success':True,'raw_text':r.text}


def _put_json(path,payload):
    token=base._token()
    r=base.SESSION.put(
        f'{base.BASE_URL}/{path.lstrip("/")}',
        headers={'Authorization':f'Bearer {token}','Channel':base.CHANNEL,'Content-Type':'application/json'},
        json=payload, timeout=35,
    )
    if not r.ok:
        raise RuntimeError(f'PUT /{path} HTTP {r.status_code}: {(r.text or "")[:1000]}')
    try:return r.json()
    except Exception:return {'success':True,'raw_text':r.text}


def _doc_id(obj):
    if isinstance(obj,dict):
        for k in ('id','document_id','commercial_doc_id'):
            v=obj.get(k)
            if v not in (None,''): return str(v)
        d=obj.get('data')
        if isinstance(d,dict): return _doc_id(d)
    return ''


def _preview_data(scna):
    return base.base.kolaybi_preview(scna)


c=kdb()
try:
    c.executescript('''
    CREATE TABLE IF NOT EXISTS sent_documents(
      scna TEXT PRIMARY KEY COLLATE NOCASE,
      document_id TEXT DEFAULT '',
      endpoint TEXT DEFAULT '',
      payload_json TEXT DEFAULT '',
      response_json TEXT DEFAULT '',
      tags_json TEXT DEFAULT '',
      sent_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    ''')
    c.commit()
finally:c.close()


@app.get('/api/kolaybi/sent/{scna}')
def kb_sent_status(scna:str):
    c=kdb()
    try:
        r=c.execute('SELECT * FROM sent_documents WHERE UPPER(scna)=UPPER(?)',(str(scna).strip(),)).fetchone()
        return {'sent':bool(r),'row':dict(r) if r else None}
    finally:c.close()


@app.post('/api/kolaybi/send/{scna}')
def kb_send(scna:str):
    base.base._admin_required()
    pv=_preview_data(scna)
    if not pv.get('ready'):
        raise HTTPException(status_code=400,detail='SCNA gönderime hazır değil. Eksik cari/proje/ürün eşleştirmelerini tamamlayın.')
    c=kdb()
    try:
        old=c.execute('SELECT * FROM sent_documents WHERE UPPER(scna)=UPPER(?)',(str(scna).strip(),)).fetchone()
        if old:
            raise HTTPException(status_code=409,detail=f'Bu SCNA daha önce KolayBi’ye gönderilmiş. Document ID: {old["document_id"] or "-"}')
        tags=[dict(r) for r in c.execute('SELECT * FROM tags WHERE is_active=1 AND is_default=1 ORDER BY name').fetchall()]
    finally:c.close()

    full_no,num=_snca_parts(scna)
    # Entry date first, trip date fallback.
    dbc=core.db()
    try:
        tr=dbc.execute('SELECT trip_date,entry_at,plate FROM trips WHERE UPPER(TRIM(scna))=UPPER(TRIM(?))',(str(scna).strip(),)).fetchone()
    finally:dbc.close()
    date=(str((tr['entry_at'] if tr else '') or '')[:10] or str((tr['trip_date'] if tr else '') or '')[:10] or time.strftime('%Y-%m-%d'))
    contact=pv['contact']; project=pv['project']; items=pv['items']
    payload={
      'type':'purchase_invoice','document_no':full_no,'invoice_number':num,'serial_no':full_no,
      'contact_id':str(contact.get('contact_id') or ''),'description':f'{full_no}\nPLATE: {pv.get("plate","")}',
      'order_date':date,'invoice_date':date,'currency':'try','tracking_currency':'try','vat_rate':'0',
      'project_id':str(project.get('project_id') or ''),
    }
    if str(contact.get('address_id') or '').strip(): payload['address_id']=str(contact.get('address_id'))
    valid=[]
    for item in items:
        if _num(item.get('quantity'))>0 and _num(item.get('total'))>0:
            valid.append(item)
    if not valid: raise HTTPException(status_code=400,detail='Gönderilecek gider kalemi yok.')
    for i,item in enumerate(valid):
        pid=str(item.get('product_id') or '').strip()
        if not pid: raise HTTPException(status_code=400,detail=f'Product ID eksik: {item.get("code")}')
        qty=_num(item.get('quantity')); price=_num(item.get('unit_price')); total=_num(item.get('total'))
        unit='LT' if item.get('code')=='ROAD_FUEL' else ('GUN' if item.get('code') in ('PARKING','WAITING') else 'ADET')
        name=str(item.get('name') or item.get('code') or '')
        desc=str(item.get('description') or '').strip() or name
        payload[f'items[{i}][product_id]']=pid
        payload[f'items[{i}][quantity]']=_fmt(qty)
        payload[f'items[{i}][unit_price]']=_fmt(price)
        payload[f'items[{i}][vat_rate]']='0'
        for k in ('unit','unit_name','unit_code','unit_type','quantity_unit','measurement_unit'):
            payload[f'items[{i}][{k}]']=unit
        payload[f'items[{i}][description]']=desc
        payload[f'items[{i}][discount_amount]']='0'
        payload[f'items[{i}][product_name]']=name
        payload[f'items[{i}][name]']=name
        payload[f'items[{i}][total]']=_fmt(total)
        payload[f'items[{i}][amount]']=_fmt(total)

    errors=[]; result=None; used=''
    for ep in ('invoices','invoice','purchase_invoices','purchase-invoices','purchases','expenses'):
        try:
            result=_post_form(ep,payload); used=ep; break
        except Exception as e:
            errors.append(str(e))
    if result is None:
        raise HTTPException(status_code=502,detail='KolayBi fatura gönderilemedi: '+' | '.join(errors[-3:]))
    did=_doc_id(result)
    tag_result=None
    if tags and did:
        ids=[int(t['tag_id']) for t in tags if str(t['tag_id']).isdigit()]
        if ids:
            tag_result=_put_json(f'tags/CommercialDoc/{did}',{'relations':{'tags':[{'id':x} for x in ids]}})
    c=kdb()
    try:
        c.execute('''INSERT INTO sent_documents(scna,document_id,endpoint,payload_json,response_json,tags_json)
                     VALUES(?,?,?,?,?,?)''',(str(scna).strip(),did,used,json.dumps(payload,ensure_ascii=False),json.dumps(result,ensure_ascii=False),json.dumps(tag_result,ensure_ascii=False) if tag_result is not None else ''))
        c.commit()
    finally:c.close()
    return {'ok':True,'scna':str(scna).strip(),'document_id':did,'endpoint':used,'tags':[t['tag_id'] for t in tags],'result':result,'tag_result':tag_result}


# UI: add send button to preview only. No new script block.
old="box.innerHTML=`<b>SCNA ${kbEsc(x.scna)} | ${kbEsc(x.plate)}</b><div style=\"margin:6px 0\">Cari: ${kbEsc(x.contact?.name||x.customer||'-')} | Contact ID: ${kbEsc(x.contact?.contact_id||'-')} | Address ID: ${kbEsc(x.contact?.address_id||'-')} | Project ID: ${kbEsc(x.project?.project_id||'-')}</div>`+"
new="box.innerHTML=`<b>SCNA ${kbEsc(x.scna)} | ${kbEsc(x.plate)}</b><div style=\"margin:6px 0\">Cari: ${kbEsc(x.contact?.name||x.customer||'-')} | Contact ID: ${kbEsc(x.contact?.contact_id||'-')} | Address ID: ${kbEsc(x.contact?.address_id||'-')} | Project ID: ${kbEsc(x.project?.project_id||'-')}</div>${x.ready?`<button class=\"btn primary\" style=\"margin:8px 0\" onclick=\"kbSendScna('${kbEsc(x.scna)}')\">KOLAYBI'YE GÖNDER</button>`:''}`+"
html=html.replace(old,new,1)
helper="""
async function kbSendScna(scna){if(!confirm(scna+' KolayBi’ye gerçek fatura olarak gönderilsin mi?'))return;const state=document.getElementById('kbPreviewState');if(state)state.textContent='GÖNDERİLİYOR...';try{const r=await api('/api/kolaybi/send/'+encodeURIComponent(scna),{method:'POST'});if(state)state.innerHTML='<span class=\"kb-ready\">✓ GÖNDERİLDİ | Document ID: '+kbEsc(r.document_id||'-')+'</span>';alert('KolayBi gönderimi başarılı. Document ID: '+(r.document_id||'-'));}catch(e){if(state)state.innerHTML='<span class=\"kb-missing\">'+kbEsc(e.message||e)+'</span>';alert(e.message||e);}}
"""
marker='async function kbPreview(){'
if marker in html and 'async function kbSendScna' not in html:
    html=html.replace(marker,helper+'\n'+marker,1)

core.HTML=html
print('[SAMA] KolayBi send engine active: purchase invoice + default tags + duplicate protection')
