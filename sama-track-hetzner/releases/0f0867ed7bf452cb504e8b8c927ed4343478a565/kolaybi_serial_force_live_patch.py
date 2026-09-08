import time
from fastapi import HTTPException

import shipment_scna_rename_patch as base
import kolaybi_serial_live_check_patch as live

app = base.app
core = base.core
serial = live.serial
html = core.HTML


def _txt(v):
    return str(v or '').strip()


def _force_live_refresh():
    """Always hit KolayBi /invoices now. Never use cache age as evidence of absence."""
    result = serial._refresh_remote_serial_cache()
    warnings = result.get('warnings') or []
    document_count = int(result.get('document_count') or 0)

    # A zero-row result accompanied by API warnings is not a valid 'YOK'. Fail closed
    # and leave the UI in KONTROL EDİLEMEDİ state instead of trusting old memory.
    if document_count == 0 and warnings:
        raise RuntimeError('KolayBi /invoices canlı taraması sonuç vermedi: ' + ' | '.join(str(x) for x in warnings[-5:]))
    return result


def _fresh_matches(scna, kind, meta):
    return serial._remote_matches(meta.get('serial_no'), kind) or serial._remote_matches(scna, kind)


def kb_invoice_metadata_force_live(scna: str):
    p = serial._meta(scna, 'PURCHASE')
    s = serial._meta(scna, 'SALE')
    checked_at = time.strftime('%Y-%m-%d %H:%M:%S')

    try:
        refresh = _force_live_refresh()
        verified = True
        error = ''
        p_matches = _fresh_matches(scna, 'PURCHASE', p)
        s_matches = _fresh_matches(scna, 'SALE', s)
    except Exception as e:
        # Deliberately do NOT read remote_invoice_serial_terms here. They may be stale
        # from an older check, exactly the behaviour the user reported.
        refresh = {'document_count': 0, 'term_count': 0, 'warnings': [str(e)]}
        verified = False
        error = str(e)
        p_matches = []
        s_matches = []

    common = {
        'verified': verified,
        'source': 'KOLAYBI LIVE /invoices - FORCED SCAN',
        'checked_at': checked_at,
        'live_scan': True,
        'refreshed': verified,
        'scan_document_count': int(refresh.get('document_count') or 0),
        'error': error,
        'warnings': refresh.get('warnings') or [],
    }
    p['remote_matches'] = p_matches
    s['remote_matches'] = s_matches
    p['serial_check'] = {**common, 'exists': bool(p_matches), 'matches': p_matches, 'serial_no': p.get('serial_no'), 'kind': 'PURCHASE'}
    s['serial_check'] = {**common, 'exists': bool(s_matches), 'matches': s_matches, 'serial_no': s.get('serial_no'), 'kind': 'SALE'}
    return {
        'ok': True,
        'purchase': p,
        'sale': s,
        'serial_cache': serial._remote_state(),
        'live_scan': {
            'verified': verified,
            'checked_at': checked_at,
            'document_count': int(refresh.get('document_count') or 0),
            'warnings': refresh.get('warnings') or [],
            'error': error,
        },
    }


# Every SCNA Get/Preview now forces a fresh KolayBi scan because kbLoadDocMeta calls
# this endpoint after the transaction preview is built.
for route in app.routes:
    if getattr(route, 'path', None) == '/api/kolaybi/transaction/{scna}/metadata' and 'GET' in (getattr(route, 'methods', set()) or set()):
        route.endpoint = kb_invoice_metadata_force_live
        if getattr(route, 'dependant', None) is not None:
            route.dependant.call = kb_invoice_metadata_force_live
        break


def _assert_remote_not_duplicate_force_live(scna, kind, meta):
    """Real-send duplicate guard also scans KolayBi every single time."""
    try:
        _force_live_refresh()
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail='KolayBi CANLI serial kontrolü yapılamadı; fatura GÖNDERİLMEDİ: ' + str(e)
        )

    matches = _fresh_matches(scna, kind, meta)
    if matches:
        m = matches[0]
        raise HTTPException(
            status_code=409,
            detail=(
                f'KOLAYBI’DE AYNI {kind} SERIAL ZATEN VAR. '
                f'Serial: {_txt(m.get("serial_no")) or _txt(meta.get("serial_no")) or "-"} | '
                f'Document ID: {_txt(m.get("document_id")) or "-"} | '
                f'Document No: {_txt(m.get("document_no")) or "-"}'
            )
        )


# The metadata send wrappers resolve this module-global from the serial module at call time.
serial._assert_remote_not_duplicate = _assert_remote_not_duplicate_force_live

# Also remove the old 10-minute/5-minute freshness shortcut for any code that still
# calls live._ensure_remote_serials_fresh directly.
def _always_refresh(_max_age_seconds=0, **_kwargs):
    r = _force_live_refresh()
    return {'refreshed': True, **r}

live._ensure_remote_serials_fresh = _always_refresh


# Browser side: cache-bust the metadata GET and make it obvious that a live KolayBi
# request is happening. This is inserted into the existing script, never a new script tag.
forced_ui = r'''
kbLoadDocMeta=async function(scna){
  const state=document.getElementById('kbSingleState');
  if(state)state.innerHTML='<span class="section-note">KOLAYBI SERIAL CANLI TARANIYOR...</span>';
  try{
    const m=await api('/api/kolaybi/transaction/'+encodeURIComponent(scna)+'/metadata?live=1&ts='+Date.now());
    const pb=document.getElementById('kbPurchaseBody'),sb=document.getElementById('kbSaleBody');
    if(pb)pb.insertAdjacentHTML('afterbegin',kbMetaBox(scna,'PURCHASE',m.purchase||{},m.serial_cache||{}));
    if(sb)sb.insertAdjacentHTML('afterbegin',kbMetaBox(scna,'SALE',m.sale||{},m.serial_cache||{}));
    const pc=m.purchase?.serial_check||{},sc=m.sale?.serial_check||{};
    const ps=document.getElementById('kbPurchaseStatus'),ss=document.getElementById('kbSaleStatus');
    if(pc.verified===false&&ps)ps.innerHTML='<span class="kb-missing">CANLI SERIAL KONTROL EDİLEMEDİ</span>';
    else if(pc.exists&&ps)ps.innerHTML='<span class="kb-missing">⚠ SERIAL VAR</span>';
    if(sc.verified===false&&ss)ss.innerHTML='<span class="kb-missing">CANLI SERIAL KONTROL EDİLEMEDİ</span>';
    else if(sc.exists&&ss)ss.innerHTML='<span class="kb-missing">⚠ SERIAL VAR</span>';
    if(state){
      const live=m.live_scan||{};
      state.innerHTML=live.verified
        ?'<span class="kb-ready">✓ KOLAYBI CANLI TARANDI | '+Number(live.document_count||0)+' belge | '+kbEsc(live.checked_at||'-')+'</span>'
        :'<span class="kb-missing">KOLAYBI CANLI TARAMA BAŞARISIZ | '+kbEsc(live.error||'Kontrol edilemedi')+'</span>';
    }
  }catch(e){
    const ps=document.getElementById('kbPurchaseStatus'),ss=document.getElementById('kbSaleStatus');
    if(ps)ps.innerHTML='<span class="kb-missing">CANLI SERIAL KONTROL EDİLEMEDİ</span>';
    if(ss)ss.innerHTML='<span class="kb-missing">CANLI SERIAL KONTROL EDİLEMEDİ</span>';
    if(state)state.innerHTML='<span class="kb-missing">KOLAYBI CANLI TARAMA BAŞARISIZ | '+kbEsc(e.message||e)+'</span>';
  }
};
'''
marker = 'async function kbLoadSingleV2(){'
if marker in html and 'KOLAYBI SERIAL CANLI TARANIYOR' not in html:
    html = html.replace(marker, forced_ui + '\n' + marker, 1)

# Remove misleading wording from the document card. The DB remains only a temporary
# index of the scan that just completed; it is no longer used as the decision source.
html = html.replace(
    '| Serial cache: ${kbEsc(last)}',
    '| Son canlı API taraması: ${kbEsc(m.serial_check?.checked_at||last)}'
)

core.HTML = html
print('[SAMA] KolayBi FORCE-LIVE serial check active: every SCNA preview and every send scans /invoices now; stale memory cannot answer VAR/YOK')
