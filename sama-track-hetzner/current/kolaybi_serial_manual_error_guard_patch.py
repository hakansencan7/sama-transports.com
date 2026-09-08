from fastapi import HTTPException

# Final guard for manual SERIAL DB mode. Keep the working login/auth chain untouched.
import kolaybi_serial_manual_sent_sync_patch as base
import kolaybi_serial_manual_cache_patch as manual

app = base.app
core = base.core
serial = manual.serial
sync = manual.sync
html = core.HTML


def _txt(v):
    return str(v or '').strip()


def kb_serial_cache_manual_refresh_safe():
    """Explicit refresh with a JSON error response for every failure.

    The underlying cache builder downloads the new invoice list before opening the
    replacement transaction. Therefore the old snapshot remains usable if KolayBi
    returns 429/5xx or the scan otherwise fails.
    """
    sync.base._admin_required()
    if not manual._REFRESH_LOCK.acquire(blocking=False):
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

        state = manual._state()
        if not state.get('ready'):
            raise HTTPException(
                status_code=502,
                detail='SERIAL DB yenileme tamamlandı ancak yeni snapshot doğrulanamadı; eski kayıt kullanılmaya devam edecek.',
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
        manual._REFRESH_LOCK.release()


# Replace the existing manual-refresh handler instead of registering another route.
for route in app.routes:
    if getattr(route, 'path', None) == '/api/kolaybi/serial-cache/manual-refresh' and 'POST' in (getattr(route, 'methods', set()) or set()):
        route.endpoint = kb_serial_cache_manual_refresh_safe
        if getattr(route, 'dependant', None) is not None:
            route.dependant.call = kb_serial_cache_manual_refresh_safe
        break


# The main app's generic api() helper used to call r.json() blindly on errors.
# Starlette/Uvicorn can return plain text "Internal Server Error" for an uncaught 500,
# which produced the browser error: Unexpected token 'I' ... is not valid JSON.
# Make the existing helper tolerant of JSON and plain-text responses. No new script tag.
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

# Make the refresh UI message explicit about atomic replacement.
html = html.replace(
    'Yeni liste KolayBi /invoices üzerinden bir kez indirilecek ve önceki snapshot yeni listeyle değiştirilecek.',
    'Yeni liste KolayBi /invoices üzerinden bir kez indirilecek. Tarama başarıyla tamamlanınca eski snapshot tek işlemde silinip yenisiyle değiştirilecek; tarama hata verirse eski snapshot korunacak.',
    1,
)

core.HTML = html
print('[SAMA] Manual SERIAL DB error guard active: JSON-safe errors + atomic snapshot replacement + no blind response.json()')
