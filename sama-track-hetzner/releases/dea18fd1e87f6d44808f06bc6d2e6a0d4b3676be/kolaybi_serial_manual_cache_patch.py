import threading
import time
from fastapi import HTTPException

# Final serial strategy: no automatic /invoices scans on SCNA load or send.
# A complete KolayBi serial snapshot lives in kolaybi_master.db and is replaced only
# when the operator explicitly presses SERIAL DB YENILE.
import kolaybi_serial_rate_limit_patch as rate
import kolaybi_serial_force_live_patch as force
import kolaybi_serial_live_check_patch as live
import kolaybi_remote_sent_backend_safe_patch as sentmod

app = rate.app
core = rate.core
serial = live.serial
sync = live.sync
html = core.HTML

_REFRESH_LOCK = threading.Lock()


def _txt(v):
    return str(v or '').strip()


def _state():
    s = serial._remote_state() or {}
    last = _txt(s.get('last_refresh'))
    try:
        docs = int(s.get('document_count') or 0)
    except Exception:
        docs = 0
    try:
        terms = int(s.get('term_count') or 0)
    except Exception:
        terms = 0
    return {
        **s,
        'ready': bool(last),
        'last_refresh': last,
        'document_count': docs,
        'term_count': terms,
        'mode': 'MANUAL SNAPSHOT',
    }


def _cache_gate():
    """Return the current downloaded snapshot without any KolayBi API request."""
    s = _state()
    if not s['ready']:
        raise RuntimeError('SERIAL DB henüz indirilmedi. Önce SERIAL DB YENİLE butonuna bas.')
    return {
        'ok': True,
        'document_count': s['document_count'],
        'term_count': s['term_count'],
        'last_refresh': s['last_refresh'],
        'manual_snapshot': True,
        'warnings': [],
    }


# Kill every automatic refresh path. Existing metadata/sent/send guards resolve these
# module globals dynamically, so they now read only the downloaded serial snapshot.
force._force_live_refresh = _cache_gate


def _manual_no_auto_refresh(_max_age_seconds=0, **_kwargs):
    s = _cache_gate()
    return {'refreshed': False, **s}


live._ensure_remote_serials_fresh = _manual_no_auto_refresh


def kb_serial_cache_status_manual():
    return {'ok': True, **_state()}


@app.get('/api/kolaybi/serial-cache/status-manual')
def kb_serial_cache_status_manual_route():
    return kb_serial_cache_status_manual()


@app.post('/api/kolaybi/serial-cache/manual-refresh')
def kb_serial_cache_manual_refresh():
    """Explicit full download requested by the operator.

    serial._refresh_remote_serial_cache fetches the complete remote list first and then
    replaces remote_invoice_serial_terms in one transaction. This avoids mixing old and
    new snapshots and also avoids leaving a half-empty DB if KolayBi fails mid-scan.
    """
    sync.base._admin_required()
    if not _REFRESH_LOCK.acquire(blocking=False):
        raise HTTPException(status_code=409, detail='SERIAL DB yenileme zaten devam ediyor.')
    try:
        result = serial._refresh_remote_serial_cache()
        warnings = result.get('warnings') or []
        if warnings:
            raise HTTPException(
                status_code=502,
                detail='SERIAL DB tam yenilenemedi; eski snapshot korunuyor: ' + ' | '.join(str(x) for x in warnings[-3:])
            )
        s = _state()
        if not s['ready']:
            raise HTTPException(status_code=502, detail='SERIAL DB yenileme tamamlandı ancak snapshot tarihi doğrulanamadı.')
        return {
            'ok': True,
            'message': 'KolayBi SERIAL DB yenilendi.',
            'document_count': s['document_count'],
            'term_count': s['term_count'],
            'last_refresh': s['last_refresh'],
            'mode': 'MANUAL SNAPSHOT',
        }
    finally:
        _REFRESH_LOCK.release()


def _metadata_from_snapshot(scna: str):
    p = serial._meta(scna, 'PURCHASE')
    s = serial._meta(scna, 'SALE')
    st = _state()
    ready = bool(st['ready'])

    p_matches = serial._remote_matches(p.get('serial_no'), 'PURCHASE') or serial._remote_matches(scna, 'PURCHASE') if ready else []
    s_matches = serial._remote_matches(s.get('serial_no'), 'SALE') or serial._remote_matches(scna, 'SALE') if ready else []

    common = {
        'verified': ready,
        'source': 'KOLAYBI SERIAL DB / MANUAL SNAPSHOT',
        'checked_at': st['last_refresh'],
        'live_scan': False,
        'manual_snapshot': True,
        'refreshed': False,
        'error': '' if ready else 'SERIAL DB henüz indirilmedi. SERIAL DB YENİLE butonuna bas.',
        'warnings': [],
    }
    p['remote_matches'] = p_matches
    s['remote_matches'] = s_matches
    p['serial_check'] = {**common, 'exists': bool(p_matches), 'matches': p_matches, 'serial_no': p.get('serial_no'), 'kind': 'PURCHASE'}
    s['serial_check'] = {**common, 'exists': bool(s_matches), 'matches': s_matches, 'serial_no': s.get('serial_no'), 'kind': 'SALE'}
    return {
        'ok': True,
        'purchase': p,
        'sale': s,
        'serial_cache': st,
        'live_scan': {
            'verified': ready,
            'checked_at': st['last_refresh'],
            'document_count': st['document_count'],
            'manual_snapshot': True,
            'error': common['error'],
            'warnings': [],
        },
    }


for route in app.routes:
    if getattr(route, 'path', None) == '/api/kolaybi/transaction/{scna}/metadata' and 'GET' in (getattr(route, 'methods', set()) or set()):
        route.endpoint = _metadata_from_snapshot
        if getattr(route, 'dependant', None) is not None:
            route.dependant.call = _metadata_from_snapshot
        break


def _sent_from_snapshot(scna: str):
    st = _state()
    if not st['ready']:
        return {
            'purchase': None,
            'sale': None,
            'live_verified': False,
            'manual_snapshot': True,
            'cache_ready': False,
            'checked_at': '',
            'document_count': 0,
            'source': 'KOLAYBI SERIAL DB / NOT LOADED',
        }
    pmeta = serial._meta(scna, 'PURCHASE')
    smeta = serial._meta(scna, 'SALE')
    pmatches = force._fresh_matches(scna, 'PURCHASE', pmeta)
    smatches = force._fresh_matches(scna, 'SALE', smeta)
    return {
        'purchase': sentmod._match_as_sent(scna, 'PURCHASE', pmatches),
        'sale': sentmod._match_as_sent(scna, 'SALE', smatches),
        'live_verified': True,
        'manual_snapshot': True,
        'cache_ready': True,
        'checked_at': st['last_refresh'],
        'document_count': st['document_count'],
        'source': 'KOLAYBI SERIAL DB / MANUAL SNAPSHOT',
    }


for route in app.routes:
    if getattr(route, 'path', None) == '/api/kolaybi/transaction/{scna}/sent' and 'GET' in (getattr(route, 'methods', set()) or set()):
        route.endpoint = _sent_from_snapshot
        if getattr(route, 'dependant', None) is not None:
            route.dependant.call = _sent_from_snapshot
        break


# The remote-sent guard used by PURCHASE/SALE posting must also read only the snapshot.
def _remote_sent_snapshot(scna, kind):
    _cache_gate()
    meta = serial._meta(scna, kind)
    matches = force._fresh_matches(scna, kind, meta)
    return sentmod._match_as_sent(scna, kind, matches)


sentmod.workflow._sent = _remote_sent_snapshot


# UI: add one explicit refresh button next to SCNA GETIR. No new <script> block.
anchor = 'SCNA KONTROLÜNÜ GETİR</button>'
if anchor in html and 'SERIAL DB YENİLE' not in html:
    html = html.replace(
        anchor,
        anchor + '<button class="btn secondary" onclick="kbSerialDbRefresh()">SERIAL DB YENİLE</button><span id="kbSerialDbState" class="section-note"></span>',
        1,
    )

manual_js = r'''
async function kbSerialDbStatus(){
  const el=document.getElementById('kbSerialDbState');if(!el)return;
  try{
    const s=await api('/api/kolaybi/serial-cache/status-manual');
    el.innerHTML=s.ready
      ?'<span class="kb-ready">SERIAL DB: '+Number(s.document_count||0).toLocaleString('tr-TR')+' belge | Son yenileme: '+kbEsc(s.last_refresh||'-')+'</span>'
      :'<span class="kb-missing">SERIAL DB BOŞ | SERIAL DB YENİLE</span>';
  }catch(e){el.innerHTML='<span class="kb-missing">SERIAL DB DURUMU OKUNAMADI</span>';}
}
async function kbSerialDbRefresh(){
  const el=document.getElementById('kbSerialDbState');
  if(!confirm('KolayBi fatura serial DB tamamen yenilensin mi?\n\nYeni liste KolayBi /invoices üzerinden bir kez indirilecek ve önceki snapshot yeni listeyle değiştirilecek.'))return;
  if(el)el.innerHTML='<span class="section-note">SERIAL DB YENİLENİYOR... KolayBi sadece bu işlemde taranıyor.</span>';
  try{
    const r=await api('/api/kolaybi/serial-cache/manual-refresh',{method:'POST'});
    if(el)el.innerHTML='<span class="kb-ready">✓ SERIAL DB YENİLENDİ | '+Number(r.document_count||0).toLocaleString('tr-TR')+' belge | '+kbEsc(r.last_refresh||'-')+'</span>';
    const scna=String(document.getElementById('kbSingleScna')?.value||'').trim();
    if(scna){if(typeof kbLoadSingleV2==='function')await kbLoadSingleV2();else if(typeof kbLoadSingle==='function')await kbLoadSingle();}
  }catch(e){if(el)el.innerHTML='<span class="kb-missing">'+kbEsc(e.message||e)+'</span>';alert(e.message||e);}
}
kbLoadDocMeta=async function(scna){
  const state=document.getElementById('kbSingleState');
  try{
    const m=await api('/api/kolaybi/transaction/'+encodeURIComponent(scna)+'/metadata?mode=manual');
    const pb=document.getElementById('kbPurchaseBody'),sb=document.getElementById('kbSaleBody');
    if(pb)pb.insertAdjacentHTML('afterbegin',kbMetaBox(scna,'PURCHASE',m.purchase||{},m.serial_cache||{}));
    if(sb)sb.insertAdjacentHTML('afterbegin',kbMetaBox(scna,'SALE',m.sale||{},m.serial_cache||{}));
    const pc=m.purchase?.serial_check||{},sc=m.sale?.serial_check||{};
    const ps=document.getElementById('kbPurchaseStatus'),ss=document.getElementById('kbSaleStatus');
    if(pc.verified===false&&ps)ps.innerHTML='<span class="kb-missing">SERIAL DB YÜKLÜ DEĞİL</span>';
    else if(pc.exists&&ps)ps.innerHTML='<span class="kb-missing">⚠ SERIAL VAR</span>';
    if(sc.verified===false&&ss)ss.innerHTML='<span class="kb-missing">SERIAL DB YÜKLÜ DEĞİL</span>';
    else if(sc.exists&&ss)ss.innerHTML='<span class="kb-missing">⚠ SERIAL VAR</span>';
    const snap=m.serial_cache||{};
    if(state)state.innerHTML=snap.ready
      ?'<span class="kb-ready">SERIAL DB KULLANILDI | '+Number(snap.document_count||0).toLocaleString('tr-TR')+' belge | Son yenileme: '+kbEsc(snap.last_refresh||'-')+'</span>'
      :'<span class="kb-missing">SERIAL DB BOŞ | Önce SERIAL DB YENİLE</span>';
    kbSerialDbStatus();
  }catch(e){if(state)state.innerHTML='<span class="kb-missing">SERIAL DB OKUMA HATASI | '+kbEsc(e.message||e)+'</span>';}
};
if(typeof kbMainMode==='function'){
  const kbMainModeManualSerialBase=kbMainMode;
  kbMainMode=function(mode){kbMainModeManualSerialBase(mode);if(mode==='transaction')setTimeout(kbSerialDbStatus,0);};
}
'''
marker = 'async function kbLoadSingleV2(){'
if marker in html and 'async function kbSerialDbRefresh' not in html:
    html = html.replace(marker, manual_js + '\n' + marker, 1)

# Remove obsolete wording from the old FORCE-LIVE presentation if still present.
html = html.replace('KOLAYBI SERIAL CANLI TARANIYOR...', 'SERIAL DB KONTROL EDİLİYOR...')
html = html.replace('KOLAYBI CANLI TARANDI', 'SERIAL DB KULLANILDI')
html = html.replace('KOLAYBI CANLI TARAMA BAŞARISIZ', 'SERIAL DB KONTROL HATASI')

core.HTML = html
print('[SAMA] KolayBi MANUAL SERIAL SNAPSHOT active: no automatic /invoices calls; API scans only when SERIAL DB YENILE is pressed')
