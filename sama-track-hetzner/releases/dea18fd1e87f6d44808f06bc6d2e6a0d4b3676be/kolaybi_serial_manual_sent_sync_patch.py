import time
from fastapi import HTTPException

# In manual-snapshot mode a successful SAMA send must be written into the local
# serial snapshot immediately. Otherwise the just-created invoice would remain
# invisible until the operator presses SERIAL DB YENILE again, allowing duplicates.
import kolaybi_serial_manual_cache_patch as base
import kolaybi_remote_sent_backend_safe_patch as sentmod
import kolaybi_invoice_metadata_serial_patch as serial

app = base.app
core = base.core
kdb = sentmod.kdb


def _txt(v):
    return str(v or '').strip()


_original_save_sent = sentmod.workflow._save_sent


def _save_sent_and_snapshot(scna, kind, did, endpoint, payload, result, tag_result):
    # Preserve the existing local audit/upsert first.
    _original_save_sent(scna, kind, did, endpoint, payload, result, tag_result)

    meta = serial._meta(scna, kind)
    row = {
        'id': _txt(did),
        'document_id': _txt(did),
        'document_no': _txt((payload or {}).get('document_no')) or _txt(meta.get('document_no')),
        'serial_no': _txt((payload or {}).get('serial_no')) or _txt(meta.get('serial_no')),
        'invoice_number': _txt((payload or {}).get('invoice_number')) or _txt(meta.get('invoice_number')),
        'description': _txt((payload or {}).get('description')) or _txt(meta.get('description')),
        'type': 'sale_invoice' if _txt(kind).upper() == 'SALE' else 'purchase_invoice',
    }
    terms = serial._row_terms(row)
    c = kdb()
    try:
        already = c.execute(
            'SELECT 1 FROM remote_invoice_serial_terms WHERE document_id=? AND UPPER(doc_kind)=UPPER(?) LIMIT 1',
            (_txt(did), _txt(kind)),
        ).fetchone()
        c.execute(
            'DELETE FROM remote_invoice_serial_terms WHERE document_id=? AND UPPER(doc_kind)=UPPER(?)',
            (_txt(did), _txt(kind)),
        )
        for term in terms:
            c.execute('''INSERT INTO remote_invoice_serial_terms(
                           term,doc_kind,document_id,document_no,serial_no,invoice_number,
                           description,raw_type,updated_at
                         ) VALUES(?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)''',
                      (
                          term, _txt(kind).upper(), _txt(did), row['document_no'], row['serial_no'],
                          row['invoice_number'], row['description'], row['type'],
                      ))

        # Keep snapshot counters sensible without pretending a new full API refresh happened.
        if not already:
            state = {str(r['key']): str(r['value'] or '') for r in c.execute(
                'SELECT key,value FROM remote_invoice_serial_state'
            ).fetchall()}
            try:
                docs = int(state.get('document_count') or 0) + 1
            except Exception:
                docs = 1
            try:
                term_count = int(state.get('term_count') or 0) + len(terms)
            except Exception:
                term_count = len(terms)
            for key, value in (('document_count', str(docs)), ('term_count', str(term_count))):
                c.execute('''INSERT INTO remote_invoice_serial_state(key,value,updated_at)
                             VALUES(?,?,CURRENT_TIMESTAMP)
                             ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_at=CURRENT_TIMESTAMP''',
                          (key, value))
        c.commit()
    finally:
        c.close()


sentmod.workflow._save_sent = _save_sent_and_snapshot


# Guard the manual refresh endpoint so every backend failure returns FastAPI JSON.
# The cache builder fetches the replacement list before deleting the old snapshot,
# so a 429/5xx/network error keeps the previous SERIAL DB intact.
def kb_serial_cache_manual_refresh_safe():
    base.sync.base._admin_required()
    if not base._REFRESH_LOCK.acquire(blocking=False):
        raise HTTPException(status_code=409, detail='SERIAL DB yenileme zaten devam ediyor.')
    try:
        try:
            result = serial._refresh_remote_serial_cache()
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=502,
                detail='SERIAL DB yenileme başarısız; eski snapshot korundu: ' + _txt(e),
            )

        warnings = result.get('warnings') or []
        if warnings:
            raise HTTPException(
                status_code=502,
                detail='SERIAL DB tam yenilenemedi; eski snapshot korunuyor: ' +
                       ' | '.join(str(x) for x in warnings[-3:]),
            )

        state = base._state()
        if not state.get('ready'):
            raise HTTPException(
                status_code=502,
                detail='SERIAL DB yenileme tamamlandı ancak yeni snapshot doğrulanamadı.',
            )

        return {
            'ok': True,
            'message': 'KolayBi SERIAL DB yenilendi; önceki snapshot yeni snapshot ile değiştirildi.',
            'document_count': int(state.get('document_count') or 0),
            'term_count': int(state.get('term_count') or 0),
            'last_refresh': _txt(state.get('last_refresh')),
            'mode': 'MANUAL SNAPSHOT',
        }
    finally:
        base._REFRESH_LOCK.release()


for route in app.routes:
    if getattr(route, 'path', None) == '/api/kolaybi/serial-cache/manual-refresh' and 'POST' in (getattr(route, 'methods', set()) or set()):
        route.endpoint = kb_serial_cache_manual_refresh_safe
        if getattr(route, 'dependant', None) is not None:
            route.dependant.call = kb_serial_cache_manual_refresh_safe
        break


# The main api() helper previously assumed every error body was JSON. Uvicorn may
# return plain text "Internal Server Error", which caused the browser-side
# "Unexpected token 'I' ... is not valid JSON" message. Parse text safely instead.
html = core.HTML
old_api = """const api=async(u,o={})=>{
  let r=await fetch(u,o);
  if(!r.ok){
    let e=await r.json();
    throw new Error(e.detail||'Hata');
  }
  return r.json();
};"""
new_api = """const api=async(u,o={})=>{
  const r=await fetch(u,o);
  const text=await r.text();
  let d={};
  if(text){
    try{d=JSON.parse(text);}catch(e){d={detail:text.slice(0,800)};}
  }
  if(!r.ok)throw new Error(d.detail||d.message||('HTTP '+r.status));
  return d;
};"""
if old_api in html:
    html = html.replace(old_api, new_api, 1)

html = html.replace(
    'Yeni liste KolayBi /invoices üzerinden bir kez indirilecek ve önceki snapshot yeni listeyle değiştirilecek.',
    'Yeni liste KolayBi /invoices üzerinden bir kez indirilecek. Tarama tamamlanınca eski snapshot tek işlemde yenisiyle değiştirilecek; hata olursa eski snapshot korunacak.',
    1,
)

core.HTML = html

print('[SAMA] Manual SERIAL DB send sync + JSON-safe refresh active: no automatic scans, snapshot preserved on refresh errors')
