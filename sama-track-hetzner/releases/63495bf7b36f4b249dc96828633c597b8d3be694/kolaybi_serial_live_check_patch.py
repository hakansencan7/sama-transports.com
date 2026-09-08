import time
from fastapi import HTTPException

import kolaybi_invoice_metadata_serial_patch as serial
import kolaybi_sale_cari_workflow_patch as sale_cari

app = serial.app
core = serial.core
sync = serial.sync
kdb = serial.kdb
html = core.HTML


def _txt(v):
    return str(v or '').strip()


def _doc_kind_v2(row):
    """Match the proven desktop rule: plain `invoice` is PURCHASE; SALE wins first."""
    if not isinstance(row, dict):
        return ''
    hint = _txt(row.get('_sama_kind_hint')).upper()
    if hint in ('PURCHASE', 'SALE'):
        return hint
    raw = ' '.join([
        serial._kind_text(row.get('commercial_doc_type')),
        serial._kind_text(row.get('type')),
        serial._kind_text(row.get('document_type')),
        serial._kind_text(row.get('type_group')),
        serial._kind_text(row.get('type_key')),
    ]).lower()
    norm = (raw.replace('ı','i').replace('ş','s').replace('ğ','g').replace('ü','u').replace('ö','o').replace('ç','c'))
    if any(x in norm for x in ('sale','sales','satis','sales_invoice','sale_invoice')):
        return 'SALE'
    if any(x in norm for x in ('purchase','purchases','alis','purchase_invoice','expense','gider','supplier')):
        return 'PURCHASE'
    # KolayBi generic /invoices rows often return type=invoice for purchase invoices.
    words = {x for x in norm.replace('-', '_').replace('/', ' ').split() if x}
    if 'invoice' in words or norm.strip() in ('invoice','invoices'):
        return 'PURCHASE'
    return ''


serial._doc_kind = _doc_kind_v2


def _fetch_variant(base_params, hint, max_pages=50, page_size=100):
    rows=[]; seen=set(); errors=[]; any_response=False
    for page in range(1, max_pages + 1):
        got=[]
        param_options = [
            {**base_params, 'page':page, 'per_page':page_size},
            {**base_params, 'page':page, 'limit':page_size},
        ] if page == 1 else [{**base_params, 'page':page, 'per_page':page_size}]
        for params in param_options:
            try:
                resp = sync._get('invoices', params)
                any_response=True
                got = sync._rows(resp)
                # A successful request shape is enough; don't repeat the same page with another shape.
                break
            except Exception as e:
                errors.append(f'GET /invoices params={params}: {e}')
        if not got:
            break
        new_count=0
        for raw in got:
            if not isinstance(raw, dict):
                continue
            row=dict(raw)
            if hint:
                row['_sama_kind_hint']=hint
            did=serial._row_value(row,('id','document_id','commercial_doc_id'))
            sr=serial._row_value(row,('serial_no','full_number','number'))
            dn=serial._row_value(row,('document_no','document_number','commercial_document_no','commercial_doc_no','doc_no'))
            inv=serial._row_value(row,('invoice_number',))
            typ=serial._kind_text(row.get('commercial_doc_type') or row.get('type') or row.get('document_type'))
            key=did or f'{sr}|{dn}|{inv}|{typ}|{hint}'
            if not key or key in seen:
                continue
            seen.add(key); rows.append(row); new_count += 1
        if new_count == 0 or len(got) < page_size:
            break
    return rows, errors, any_response


def _fetch_remote_serials_v2(max_pages=50, page_size=100):
    """Fetch real KolayBi invoice serials, adding type-specific passes only when needed."""
    all_rows=[]; all_seen=set(); errors=[]

    def merge(rows):
        for row in rows:
            did=serial._row_value(row,('id','document_id','commercial_doc_id'))
            sr=serial._row_value(row,('serial_no','full_number','number'))
            dn=serial._row_value(row,('document_no','document_number','commercial_document_no','commercial_doc_no','doc_no'))
            inv=serial._row_value(row,('invoice_number',))
            kind=_doc_kind_v2(row)
            key=did or f'{sr}|{dn}|{inv}|{kind}'
            if key and key not in all_seen:
                all_seen.add(key); all_rows.append(row)

    rows, errs, _ = _fetch_variant({}, '', max_pages=max_pages, page_size=page_size)
    merge(rows); errors.extend(errs)

    kinds={_doc_kind_v2(r) for r in all_rows}
    if 'PURCHASE' not in kinds:
        for params in (
            {'commercial_doc_type':'purchase_invoice'},
            {'type':'purchase_invoice'},
            {'group':'purchase'},
        ):
            rows, errs, _ = _fetch_variant(params, 'PURCHASE', max_pages=max_pages, page_size=page_size)
            merge(rows); errors.extend(errs)
            if any(_doc_kind_v2(r)=='PURCHASE' for r in rows):
                break

    kinds={_doc_kind_v2(r) for r in all_rows}
    if 'SALE' not in kinds:
        for params in (
            {'commercial_doc_type':'sale_invoice'},
            {'type':'sale_invoice'},
            {'group':'sale'},
        ):
            rows, errs, _ = _fetch_variant(params, 'SALE', max_pages=max_pages, page_size=page_size)
            merge(rows); errors.extend(errs)
            if any(_doc_kind_v2(r)=='SALE' for r in rows):
                break

    return all_rows, errors[-20:]


serial._fetch_remote_serials = _fetch_remote_serials_v2


def _state_age_seconds():
    state=serial._remote_state()
    raw=_txt(state.get('last_refresh'))
    if not raw:
        return 10**12
    for fmt in ('%Y-%m-%d %H:%M:%S','%Y-%m-%dT%H:%M:%S'):
        try:
            return max(0.0, time.time()-time.mktime(time.strptime(raw[:19],fmt)))
        except Exception:
            pass
    return 10**12


def _ensure_remote_serials_fresh(max_age_seconds=600):
    if _state_age_seconds() <= max_age_seconds:
        return {'refreshed':False, **serial._remote_state()}
    result=serial._refresh_remote_serial_cache()
    return {'refreshed':True, **result}


def _serial_check(scna, kind, meta, refresh_if_stale=True):
    error=''
    verified=True
    refreshed=False
    if refresh_if_stale:
        try:
            r=_ensure_remote_serials_fresh()
            refreshed=bool(r.get('refreshed'))
        except Exception as e:
            verified=False
            error=str(e)
    matches=serial._remote_matches(meta.get('serial_no'),kind) or serial._remote_matches(scna,kind)
    return {
        'verified': verified,
        'exists': bool(matches),
        'matches': matches,
        'serial_no': _txt(meta.get('serial_no')),
        'kind': kind,
        'source': 'KOLAYBI /invoices CACHE' if verified else 'UNVERIFIED',
        'refreshed': refreshed,
        'checked_at': time.strftime('%Y-%m-%d %H:%M:%S'),
        'error': error,
    }


def kb_invoice_metadata_live(scna:str):
    p=serial._meta(scna,'PURCHASE'); s=serial._meta(scna,'SALE')
    # One refresh is enough for both kinds.
    refresh_error=''
    try:
        _ensure_remote_serials_fresh()
        verified=True
    except Exception as e:
        verified=False; refresh_error=str(e)
    p_matches=serial._remote_matches(p.get('serial_no'),'PURCHASE') or serial._remote_matches(scna,'PURCHASE')
    s_matches=serial._remote_matches(s.get('serial_no'),'SALE') or serial._remote_matches(scna,'SALE')
    p['remote_matches']=p_matches; s['remote_matches']=s_matches
    common={'verified':verified,'source':'KOLAYBI /invoices','checked_at':time.strftime('%Y-%m-%d %H:%M:%S'),'error':refresh_error}
    p['serial_check']={**common,'exists':bool(p_matches),'matches':p_matches,'serial_no':p.get('serial_no'),'kind':'PURCHASE'}
    s['serial_check']={**common,'exists':bool(s_matches),'matches':s_matches,'serial_no':s.get('serial_no'),'kind':'SALE'}
    return {'ok':True,'purchase':p,'sale':s,'serial_cache':serial._remote_state()}


# Replace the metadata GET handler with live/fresh KolayBi-backed status.
for route in app.routes:
    if getattr(route,'path',None)=='/api/kolaybi/transaction/{scna}/metadata' and 'GET' in (getattr(route,'methods',set()) or set()):
        route.endpoint=kb_invoice_metadata_live
        if getattr(route,'dependant',None) is not None:
            route.dependant.call=kb_invoice_metadata_live
        break


def _assert_remote_not_duplicate_live(scna, kind, meta):
    # Sending fails closed: if KolayBi cannot be checked, do not create a possibly duplicate invoice.
    try:
        _ensure_remote_serials_fresh(max_age_seconds=300)
    except Exception as e:
        raise HTTPException(status_code=502, detail='KolayBi serial kontrolü yapılamadı; fatura GÖNDERİLMEDİ: '+str(e))
    matches=serial._remote_matches(meta.get('serial_no'),kind) or serial._remote_matches(scna,kind)
    if matches:
        m=matches[0]
        raise HTTPException(status_code=409,detail=(
            f'KOLAYBI’DE AYNI {kind} SERIAL ZATEN VAR. '
            f'Serial: {_txt(m.get("serial_no")) or _txt(meta.get("serial_no")) or "-"} | '
            f'Document ID: {_txt(m.get("document_id")) or "-"} | '
            f'Document No: {_txt(m.get("document_no")) or "-"}'
        ))


serial._assert_remote_not_duplicate = _assert_remote_not_duplicate_live


# The previous UI displayed the number but did not make the KolayBi verification state obvious.
# Override only existing JS functions inside the same script block.
helper=r'''
const kbMetaBoxSerialBase=kbMetaBox;
kbMetaBox=function(scna,kind,m,cache){
  let base=kbMetaBoxSerialBase(scna,kind,m,cache);
  const c=m.serial_check||{};
  let line='';
  if(c.verified===false){
    line=`<div class="kb-missing" style="margin-top:8px"><b>SERIAL KONTROL:</b> KOLAYBI KONTROL EDİLEMEDİ${c.error?' | '+kbEsc(c.error):''}</div>`;
  }else if(c.exists){
    const x=(c.matches||[])[0]||{};
    line=`<div class="kb-missing" style="margin-top:8px"><b>SERIAL KONTROL:</b> ⚠ KOLAYBI'DE VAR | SERIAL: ${kbEsc(x.serial_no||m.serial_no||'-')} | DOCUMENT ID: ${kbEsc(x.document_id||'-')}</div>`;
  }else{
    line=`<div class="kb-ready" style="margin-top:8px"><b>SERIAL KONTROL:</b> ✓ KOLAYBI'DE YOK | ${kbEsc(m.serial_no||'-')} | Kontrol: ${kbEsc(c.checked_at||cache?.last_refresh||'-')}</div>`;
  }
  const pos=base.lastIndexOf('</div>');
  return pos>=0?base.slice(0,pos)+line+base.slice(pos):base+line;
};
kbLoadDocMeta=async function(scna){
  try{
    const m=await api('/api/kolaybi/transaction/'+encodeURIComponent(scna)+'/metadata');
    const pb=document.getElementById('kbPurchaseBody'),sb=document.getElementById('kbSaleBody');
    if(pb)pb.insertAdjacentHTML('afterbegin',kbMetaBox(scna,'PURCHASE',m.purchase||{},m.serial_cache||{}));
    if(sb)sb.insertAdjacentHTML('afterbegin',kbMetaBox(scna,'SALE',m.sale||{},m.serial_cache||{}));
    const pc=m.purchase?.serial_check||{},sc=m.sale?.serial_check||{};
    const ps=document.getElementById('kbPurchaseStatus'),ss=document.getElementById('kbSaleStatus');
    if(pc.verified===false&&ps)ps.innerHTML='<span class="kb-missing">SERIAL KONTROL EDİLEMEDİ</span>';
    else if(pc.exists&&ps)ps.innerHTML='<span class="kb-missing">⚠ SERIAL VAR</span>';
    if(sc.verified===false&&ss)ss.innerHTML='<span class="kb-missing">SERIAL KONTROL EDİLEMEDİ</span>';
    else if(sc.exists&&ss)ss.innerHTML='<span class="kb-missing">⚠ SERIAL VAR</span>';
  }catch(e){
    const ps=document.getElementById('kbPurchaseStatus'),ss=document.getElementById('kbSaleStatus');
    if(ps)ps.innerHTML='<span class="kb-missing">SERIAL KONTROL EDİLEMEDİ</span>';
    if(ss)ss.innerHTML='<span class="kb-missing">SERIAL KONTROL EDİLEMEDİ</span>';
  }
};
'''
marker='async function kbLoadSingleV2(){'
if marker in html and 'kbMetaBoxSerialBase' not in html:
    html=html.replace(marker,helper+'\n'+marker,1)

core.HTML=html
print('[SAMA] KolayBi live serial verification active: real /invoices refresh, PURCHASE/SALE separated, send fails closed on unverified/duplicate serial')
