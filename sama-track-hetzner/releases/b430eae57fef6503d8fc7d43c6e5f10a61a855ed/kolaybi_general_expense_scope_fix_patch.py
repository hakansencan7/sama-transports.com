import os
import time
from fastapi import Request, HTTPException

# Final backend/UI correction for GENERAL EXPENSE reads.
# The Office web /api/commercial_docs endpoint does NOT accept the classic KolayBi
# API token in every account; it can return 403 Invalid scope(s). Old proven SAMA
# code already documented that this endpoint needs the KolayBi Office web Bearer token.
# We first try the official v1 /invoices API (no extra credential). Only when that
# cannot produce verifiable general_expense rows do we use the separately saved web token.
import kolaybi_bulk_accounting_audit_patch as audit
import kolaybi_serial_dual_kind_snapshot_patch as dual

app = audit.app
core = audit.core
kdb = audit.kdb
sync = audit.sync
html = core.HTML

PAGE_SIZE = audit.AUDIT_PAGE_SIZE
MAX_PAGES = audit.AUDIT_MAX_PAGES
PAGE_DELAY = audit.AUDIT_PAGE_DELAY
OFFICE_TOKEN_ENV = 'KOLAYBI_OFFICE_BEARER_TOKEN'
OFFICE_TOKEN_KEY = 'office_web_bearer_token'


def _txt(v):
    return str(v or '').strip()


def _clean_token(v):
    token = _txt(v)
    if token.lower().startswith('bearer '):
        token = token.split(' ', 1)[1].strip()
    return token


def _saved_office_token():
    env_token = _clean_token(os.getenv(OFFICE_TOKEN_ENV) or '')
    if env_token:
        return env_token, 'ENV'
    c = kdb()
    try:
        row = c.execute("SELECT value FROM connection_settings WHERE key=?", (OFFICE_TOKEN_KEY,)).fetchone()
        token = _clean_token(row['value'] if row else '')
        return (token, 'DB') if token else ('', '')
    finally:
        c.close()


def _office_headers():
    token, _source = _saved_office_token()
    if not token:
        raise RuntimeError(
            'GENERAL EXPENSE için KolayBi Office Web Bearer Token gerekli. '
            'KolayBi web sitesinde F12 > Network > commercial_docs isteği > Request Headers > '
            'authorization: Bearer ... değerini SAMA içindeki OFFICE WEB TOKEN alanına kaydet.'
        )
    return {
        'Authorization': f'Bearer {token}',
        'Accept': 'application/json, text/plain, */*',
        'Content-Type': 'application/json',
        'X-Requested-With': 'XMLHttpRequest',
    }


def _office_get(params):
    url = audit._commercial_docs_url()
    try:
        r = sync.SESSION.get(
            url,
            headers=_office_headers(),
            params={**(params or {}), 'company_id': audit.GENERAL_EXPENSE_COMPANY_ID},
            timeout=40,
        )
        body = (r.text or '')[:900]
        if r.status_code == 403 and ('Invalid scope' in body or 'scope' in body.lower()):
            raise RuntimeError(
                'KolayBi Office Web Token bu endpoint için yetkili değil veya süresi dolmuş (403 Invalid scope). '
                'KolayBi web sitesinden güncel commercial_docs Bearer tokenini tekrar kaydet.'
            )
        if r.status_code == 401:
            raise RuntimeError('KolayBi Office Web Token geçersiz/süresi dolmuş (401). Güncel tokeni tekrar kaydet.')
        if r.status_code == 429:
            raise RuntimeError('KolayBi Office General Expense API 429 / Çok fazla deneme. Yenileme durduruldu.')
        r.raise_for_status()
        try:
            return r.json()
        except Exception as e:
            raise RuntimeError('KolayBi Office commercial_docs JSON dönmedi: ' + str(e))
    except RuntimeError:
        raise
    except Exception as e:
        raise RuntimeError(f'GET /api/commercial_docs: {e} {body if "body" in locals() else ""}') from e


def _scan_v1_general_variant(base_params, label):
    """Try official /kolaybi/v1/invoices with the normal API token.

    We only accept rows that explicitly identify themselves as general_expense. If
    KolayBi ignores the filter and returns ordinary invoices, the variant is rejected
    instead of polluting the accountant audit DB.
    """
    out, seen = [], set()
    for page in range(1, MAX_PAGES + 1):
        params = {**base_params, 'page': page, 'per_page': PAGE_SIZE}
        try:
            rows = dual.rate._one_get(params)
        except Exception as e:
            # A first-page unsupported query is allowed to fall through to another
            # verified filter shape. Any later page failure means the stream is partial.
            if page == 1:
                return [], f'{label}: {e}'
            raise RuntimeError(f'{label} sayfa {page} tamamlanamadı: {e}') from e
        if not rows:
            return out, ''

        explicit_rows = [r for r in rows if isinstance(r, dict) and audit._general_expense_explicit(r)]
        if page == 1 and rows and not explicit_rows:
            return [], f'{label}: filtre general_expense listesi döndürmedi/filtre yok sayıldı.'

        new_count = 0
        for raw in explicit_rows:
            rec = audit._doc_record(raw, 'GENERAL EXPENSE', 'INVOICES/V1')
            key = rec['document_id'] or '|'.join((rec['serial_no'], rec['document_no'], rec['invoice_number'], str(rec['amount'])))
            if not key or key in seen:
                continue
            seen.add(key)
            out.append(rec)
            new_count += 1

        if len(rows) < PAGE_SIZE:
            return out, ''
        if explicit_rows and new_count == 0:
            raise RuntimeError(f'{label}: sayfalama aynı general_expense kayıtlarını tekrar döndürdü.')
        if page >= MAX_PAGES:
            raise RuntimeError(f'{label}: {MAX_PAGES * PAGE_SIZE} belge sınırına ulaştı; eksik liste kabul edilmedi.')
        time.sleep(PAGE_DELAY)
    return out, ''


def _fetch_general_v1():
    errors = []
    variants = [
        ({'commercial_doc_type': 'general_expense'}, 'v1 commercial_doc_type=general_expense'),
        ({'type': 'general_expense'}, 'v1 type=general_expense'),
        ({'document_type': 'general_expense'}, 'v1 document_type=general_expense'),
    ]
    for params, label in variants:
        rows, err = _scan_v1_general_variant(params, label)
        if rows:
            return rows, errors
        if err:
            errors.append(err)
        time.sleep(PAGE_DELAY)
    return [], errors


def _scan_office_general():
    out, seen = [], set()
    for page in range(1, MAX_PAGES + 1):
        # commercial_doc_type is the field proven by the old panel payload.
        params = {
            'commercial_doc_type': 'general_expense',
            'page': page,
            'per_page': PAGE_SIZE,
        }
        try:
            resp = _office_get(params)
        except Exception as e:
            if page == 1:
                # Some panel endpoints use limit rather than per_page. Retry ONE
                # alternate pagination shape, not a spray of query variants.
                params.pop('per_page', None)
                params['limit'] = PAGE_SIZE
                resp = _office_get(params)
            else:
                raise RuntimeError(f'Office General Expense sayfa {page} tamamlanamadı: {e}') from e

        rows = audit._deep_rows(resp)
        if not rows:
            return out
        accepted = 0
        for raw in rows:
            if not isinstance(raw, dict):
                continue
            # With the Office web endpoint a verified general_expense filter is used.
            # Still prefer explicit type; if the panel omits it, the query itself is the
            # type authority and the record is accepted as GENERAL EXPENSE.
            rec = audit._doc_record(raw, 'GENERAL EXPENSE', 'COMMERCIAL_DOCS/WEB')
            key = rec['document_id'] or '|'.join((rec['serial_no'], rec['document_no'], rec['invoice_number'], str(rec['amount'])))
            if not key or key in seen:
                continue
            seen.add(key)
            out.append(rec)
            accepted += 1
        if len(rows) < PAGE_SIZE:
            return out
        if accepted == 0:
            raise RuntimeError('Office General Expense sayfalaması kayıt döndürdü ancak belge kimliği/serial okunamadı; eksik snapshot kabul edilmedi.')
        if page >= MAX_PAGES:
            raise RuntimeError(f'Office General Expense {MAX_PAGES * PAGE_SIZE} belge sınırına ulaştı; eksik liste kabul edilmedi.')
        time.sleep(PAGE_DELAY)
    return out


def _fetch_general_expenses_scope_safe():
    # First preference: official API token already configured in SAMA.
    v1_rows, v1_errors = _fetch_general_v1()
    if v1_rows:
        return v1_rows, v1_errors

    # Second preference: exact Office web endpoint using its own web-scope token.
    token, source = _saved_office_token()
    if not token:
        detail = ' | '.join(v1_errors[-3:]) if v1_errors else 'v1 /invoices general_expense listesi doğrulanamadı.'
        raise RuntimeError(
            detail + ' | /api/commercial_docs klasik API tokeniyle 403 Invalid scope veriyor. '
            'OFFICE WEB BEARER TOKEN kaydet; bu token yalnız General Expense okumasında kullanılacak.'
        )
    rows = _scan_office_general()
    if not rows:
        raise RuntimeError(f'Office Web Token ({source}) çalıştı ancak General Expense listesi boş döndü; eski snapshot korundu.')
    return rows, v1_errors


# Existing refresh handler resolves audit._fetch_general_expenses dynamically.
audit._fetch_general_expenses = _fetch_general_expenses_scope_safe


@app.get('/api/kolaybi/accounting-audit/office-token')
def kb_office_token_status():
    token, source = _saved_office_token()
    masked = ''
    if token:
        masked = token[:5] + '••••••' + token[-4:] if len(token) >= 12 else '••••••'
    return {'ok': True, 'configured': bool(token), 'source': source, 'masked': masked}


@app.post('/api/kolaybi/accounting-audit/office-token')
async def kb_office_token_save(request: Request):
    sync.base._admin_required()
    body = await request.json()
    token = _clean_token(body.get('token') or '')
    if not token:
        raise HTTPException(status_code=400, detail='Office Web Bearer Token boş olamaz.')
    c = kdb()
    try:
        c.execute('''INSERT INTO connection_settings(key,value,updated_at)
                     VALUES(?,?,CURRENT_TIMESTAMP)
                     ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_at=CURRENT_TIMESTAMP''',
                  (OFFICE_TOKEN_KEY, token))
        c.commit()
    finally:
        c.close()
    return {'ok': True, 'configured': True, 'source': 'DB'}


@app.delete('/api/kolaybi/accounting-audit/office-token')
def kb_office_token_delete():
    sync.base._admin_required()
    c = kdb()
    try:
        c.execute('DELETE FROM connection_settings WHERE key=?', (OFFICE_TOKEN_KEY,))
        c.commit()
    finally:
        c.close()
    return {'ok': True}


@app.post('/api/kolaybi/accounting-audit/office-token/test')
def kb_office_token_test():
    sync.base._admin_required()
    try:
        resp = _office_get({'commercial_doc_type': 'general_expense', 'page': 1, 'per_page': 5})
        rows = audit._deep_rows(resp)
        return {'ok': True, 'sample_count': len(rows), 'message': 'Office Web Token commercial_docs erişimi OK.'}
    except Exception as e:
        raise HTTPException(status_code=502, detail='Office Web Token testi başarısız: ' + str(e))


# Add token controls only inside the existing KolayBi audit HTML. No extra script block.
token_card = r'''
<div class="calc" id="kbOfficeTokenCard" style="margin:10px 0;padding:10px">
  <b>GENERAL EXPENSE OKUMA YETKİSİ</b><br>
  <small>/api/commercial_docs klasik API tokeninde 403 Invalid scope verirse KolayBi web panelindeki authorization Bearer tokeni burada kullanılır.</small>
  <div style="display:flex;gap:7px;flex-wrap:wrap;align-items:end;margin-top:8px">
    <div class="field" style="min-width:320px;flex:1"><label>OFFICE WEB BEARER TOKEN</label><input id="kbOfficeWebToken" type="password" placeholder="Bearer ey... veya yalnız token"></div>
    <button class="btn secondary" onclick="kbOfficeTokenSave()">TOKEN KAYDET</button>
    <button class="btn secondary" onclick="kbOfficeTokenTest()">TOKEN TEST ET</button>
    <button class="btn danger" onclick="kbOfficeTokenDelete()">TOKEN SİL</button>
  </div>
  <div id="kbOfficeTokenState" class="section-note" style="margin-top:6px"></div>
</div>
'''
textarea_anchor = '<textarea id="kbAuditInput"'
if textarea_anchor in html and 'id="kbOfficeTokenCard"' not in html:
    html = html.replace(textarea_anchor, token_card + '\n    ' + textarea_anchor, 1)

helper = r'''
async function kbOfficeTokenStatus(){
  const el=document.getElementById('kbOfficeTokenState');if(!el)return;
  try{
    const r=await api('/api/kolaybi/accounting-audit/office-token');
    el.innerHTML=r.configured?'<span class="kb-ready">✓ OFFICE WEB TOKEN HAZIR ['+kbEsc(r.source||'-')+'] '+kbEsc(r.masked||'')+'</span>':'<span class="section-note">Office token kayıtlı değil. Önce normal v1 General Expense listesi denenir; o desteklenmiyorsa bu token gerekir.</span>';
  }catch(e){el.innerHTML='<span class="kb-missing">TOKEN DURUMU OKUNAMADI</span>';}
}
async function kbOfficeTokenSave(){
  const input=document.getElementById('kbOfficeWebToken'),el=document.getElementById('kbOfficeTokenState');
  const token=String(input?.value||'').trim();if(!token){alert('Office Web Bearer Token gir.');return;}
  try{
    await api('/api/kolaybi/accounting-audit/office-token',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({token})});
    if(input)input.value='';if(el)el.innerHTML='<span class="kb-ready">✓ TOKEN KAYDEDİLDİ</span>';await kbOfficeTokenStatus();
  }catch(e){if(el)el.innerHTML='<span class="kb-missing">'+kbEsc(e.message||e)+'</span>';}
}
async function kbOfficeTokenTest(){
  const el=document.getElementById('kbOfficeTokenState');if(el)el.textContent='OFFICE TOKEN TEST EDİLİYOR...';
  try{const r=await api('/api/kolaybi/accounting-audit/office-token/test',{method:'POST'});if(el)el.innerHTML='<span class="kb-ready">✓ '+kbEsc(r.message||'TOKEN OK')+' | Örnek kayıt: '+Number(r.sample_count||0).toLocaleString('tr-TR')+'</span>';}
  catch(e){if(el)el.innerHTML='<span class="kb-missing">'+kbEsc(e.message||e)+'</span>';}
}
async function kbOfficeTokenDelete(){
  if(!confirm('Kaydedilmiş Office Web Token silinsin mi?'))return;
  const el=document.getElementById('kbOfficeTokenState');
  try{await api('/api/kolaybi/accounting-audit/office-token',{method:'DELETE'});if(el)el.innerHTML='<span class="section-note">TOKEN SİLİNDİ</span>';await kbOfficeTokenStatus();}catch(e){if(el)el.innerHTML='<span class="kb-missing">'+kbEsc(e.message||e)+'</span>';}
}
'''
marker = 'async function kbAuditStatus(){'
if marker in html and 'async function kbOfficeTokenStatus' not in html:
    html = html.replace(marker, helper + '\n' + marker, 1)

# When the accounting-audit tab opens, also display token readiness.
old = "if(audit)audit.style.display='';kbAuditStatus();return;"
new = "if(audit)audit.style.display='';kbAuditStatus();kbOfficeTokenStatus();return;"
html = html.replace(old, new, 1)

core.HTML = html
print('[SAMA] General Expense scope fix active: official v1 first, Office Web Bearer token fallback for /api/commercial_docs; no repeated 403 spray')
