import json
import os
import re
import threading
import time
from fastapi import Request, HTTPException

# Final KolayBi chain. This module is intentionally last and stays inside the existing
# HTML/JS block. It adds a separate accounting-control snapshot; normal SCNA screens
# do not trigger any new KolayBi requests.
import kolaybi_serial_dual_kind_snapshot_patch as base
import kolaybi_serial_dual_kind_snapshot_patch as dual
import kolaybi_sync_patch as sync

app = base.app
core = base.core
kdb = base.kdb
html = core.HTML

AUDIT_PAGE_SIZE = 100
AUDIT_MAX_PAGES = 250
AUDIT_PAGE_DELAY = 0.55
GENERAL_EXPENSE_COMPANY_ID = (os.getenv('KOLAYBI_COMPANY_ID') or '122077').strip()
_AUDIT_REFRESH_LOCK = threading.Lock()


def _txt(v):
    return str(v or '').strip()


def _norm_term(v):
    return re.sub(r'\s+', '', _txt(v).upper())


def _term_variants(v):
    raw = _norm_term(v)
    if not raw:
        return []
    out = []

    def add(x):
        x = _norm_term(x)
        if x and x not in out:
            out.append(x)

    add(raw)
    compact = re.sub(r'[^A-Z0-9]+', '', raw)
    add(compact)
    bare = compact
    if bare.startswith('SNCA') or bare.startswith('SCNA'):
        bare = bare[4:]
    if bare:
        add(bare)
        add('SNCA' + bare)
        add('SCNA' + bare)
    return out


def _wide_value(row, keys):
    if not isinstance(row, dict):
        return ''
    for key in keys:
        v = row.get(key)
        if isinstance(v, dict):
            got = _wide_value(v, keys)
            if got:
                return got
        elif v not in (None, ''):
            return _txt(v)
    for child in ('data', 'header', 'invoice', 'commercial_document', 'commercialDoc',
                  'document', 'attributes', 'totals', 'total', 'relations'):
        v = row.get(child)
        if isinstance(v, dict):
            got = _wide_value(v, keys)
            if got:
                return got
    return ''


def _to_float(v):
    if isinstance(v, bool) or v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, dict):
        for key in ('grand_total', 'total', 'numeric', 'value', 'amount', 'subtotal', 'temporary_subtotal'):
            if key in v:
                got = _to_float(v.get(key))
                if got is not None:
                    return got
        return None
    s = _txt(v)
    if not s:
        return None
    s = s.replace('\u00a0', '').replace(' ', '')
    # API values are commonly plain decimals. Also tolerate Turkish display strings.
    if ',' in s and '.' in s:
        if s.rfind(',') > s.rfind('.'):
            s = s.replace('.', '').replace(',', '.')
        else:
            s = s.replace(',', '')
    elif ',' in s:
        right = s.split(',')[-1]
        s = s.replace('.', '')
        s = s.replace(',', '.' if len(right) <= 2 else '')
    elif s.count('.') > 1:
        s = s.replace('.', '')
    try:
        return float(s)
    except Exception:
        return None


def _amount_from_row(row):
    if not isinstance(row, dict):
        return 0.0
    # Direct scalar fields first.
    for key in ('grand_total', 'total_amount', 'payable_amount', 'amount', 'net_total', 'invoice_total'):
        if key in row:
            got = _to_float(row.get(key))
            if got is not None:
                return got
    # KolayBi commercial_docs uses a nested total object; invoices can too.
    for key in ('total', 'totals', 'summary', 'amounts'):
        if key in row:
            got = _to_float(row.get(key))
            if got is not None:
                return got
    data = row.get('data')
    if isinstance(data, dict):
        got = _amount_from_row(data)
        if got:
            return got
    return 0.0


def _currency_from_row(row):
    v = row.get('currency') if isinstance(row, dict) else ''
    if isinstance(v, dict):
        return _txt(v.get('code') or v.get('name') or v.get('value') or v.get('key'))
    return _txt(v or _wide_value(row, ('currency_code', 'currency_name', 'tracking_currency')))


def _contact_from_row(row):
    if not isinstance(row, dict):
        return ''
    for key in ('contact_name', 'associate_name', 'customer_name', 'supplier_name', 'company_name'):
        if _txt(row.get(key)):
            return _txt(row.get(key))
    for key in ('contact', 'associate', 'customer', 'supplier'):
        v = row.get(key)
        if isinstance(v, dict):
            name = _txt(v.get('full_name') or v.get('name') or v.get('title') or v.get('company_name'))
            if name:
                return name
    return ''


def _doc_record(row, forced_kind='', source='INVOICES'):
    kind = _txt(forced_kind).upper()
    did = _wide_value(row, ('id', 'document_id', 'commercial_doc_id'))
    serial_no = _wide_value(row, (
        'serial_no', 'serial_number', 'serial', 'invoice_serial', 'document_serial',
        'commercial_doc_serial', 'full_number', 'number'
    ))
    document_no = _wide_value(row, (
        'document_no', 'document_number', 'commercial_document_no', 'commercial_doc_no',
        'commercial_doc_number', 'doc_no'
    ))
    invoice_number = _wide_value(row, ('invoice_number', 'invoice_no', 'invoice_num'))
    desc = _wide_value(row, ('description', 'note', 'notes'))
    issue_date = _wide_value(row, ('issue_date', 'invoice_date', 'document_date', 'date', 'created_at'))
    raw_type = _wide_value(row, ('commercial_doc_type', 'document_type', 'type', 'type_key', 'type_group'))
    return {
        'source': source,
        'document_id': did,
        'serial_no': serial_no,
        'document_no': document_no,
        'invoice_number': invoice_number,
        'doc_type': kind or _txt(raw_type).upper(),
        'raw_type': raw_type,
        'amount': float(_amount_from_row(row) or 0),
        'currency': _currency_from_row(row),
        'issue_date': issue_date[:32],
        'contact_name': _contact_from_row(row),
        'description': desc[:600],
    }


def _deep_rows(resp):
    seen = set()
    out = []

    def walk(v, depth=0):
        if depth > 5:
            return
        if isinstance(v, list):
            if v and all(isinstance(x, dict) for x in v):
                for x in v:
                    marker = id(x)
                    if marker not in seen:
                        seen.add(marker)
                        out.append(x)
                return
            for x in v:
                walk(x, depth + 1)
        elif isinstance(v, dict):
            # Prefer known collection keys before recursively walking everything.
            for key in ('data', 'items', 'records', 'results', 'commercial_docs', 'commercialDocuments', 'documents'):
                if key in v:
                    walk(v.get(key), depth + 1)
            if not out:
                for x in v.values():
                    if isinstance(x, (list, dict)):
                        walk(x, depth + 1)

    walk(resp)
    return out


def _general_expense_explicit(row):
    raw = ' '.join([
        _wide_value(row, ('commercial_doc_type',)),
        _wide_value(row, ('document_type',)),
        _wide_value(row, ('type',)),
        _wide_value(row, ('type_key',)),
        _wide_value(row, ('type_group',)),
    ]).lower()
    n = raw.replace('-', '_').replace(' ', '_')
    return 'general_expense' in n or ('general' in n and 'expense' in n)


def _commercial_docs_url():
    base_url = _txt(sync.BASE_URL).rstrip('/')
    if '/kolaybi/v1' in base_url:
        root = base_url.split('/kolaybi/v1', 1)[0].rstrip('/')
    else:
        root = re.sub(r'/kolaybi/v1/?$', '', base_url).rstrip('/')
    if not root:
        raise RuntimeError('KolayBi BASE URL boş; General Expense listesi alınamaz.')
    return root + '/api/commercial_docs'


def _commercial_docs_get(params):
    url = _commercial_docs_url()
    try:
        r = sync.SESSION.get(
            url,
            headers={
                'Authorization': f'Bearer {sync._token()}',
                'Channel': sync.CHANNEL,
                'Accept': 'application/json',
            },
            params={**(params or {}), 'company_id': GENERAL_EXPENSE_COMPANY_ID},
            timeout=40,
        )
        if r.status_code == 429:
            raise RuntimeError('KolayBi General Expense API 429 / Çok fazla deneme. Yenileme durduruldu.')
        r.raise_for_status()
        try:
            return r.json()
        except Exception as e:
            raise RuntimeError('General Expense listesi JSON dönmedi: ' + str(e))
    except RuntimeError:
        raise
    except Exception as e:
        body = ''
        try:
            body = (r.text or '')[:600]
        except Exception:
            pass
        raise RuntimeError(f'GET /api/commercial_docs: {e} {body}')


def _scan_general_variant(filter_params, label, allow_untyped=False):
    out = []
    seen = set()
    for page in range(1, AUDIT_MAX_PAGES + 1):
        params = {**filter_params, 'page': page, 'per_page': AUDIT_PAGE_SIZE}
        try:
            resp = _commercial_docs_get(params)
        except Exception as e:
            # Some panel endpoints use limit rather than per_page. Only try that alternate
            # shape on the first page, so one bad parameter never becomes a request storm.
            if page == 1:
                params = {**filter_params, 'page': page, 'limit': AUDIT_PAGE_SIZE}
                resp = _commercial_docs_get(params)
            else:
                raise RuntimeError(f'{label} sayfa {page} alınamadı: {e}') from e
        rows = _deep_rows(resp)
        if not rows:
            return out
        accepted = 0
        for raw in rows:
            explicit = _general_expense_explicit(raw)
            if not explicit and not allow_untyped:
                continue
            rec = _doc_record(raw, 'GENERAL EXPENSE', 'COMMERCIAL_DOCS')
            key = rec['document_id'] or '|'.join((rec['serial_no'], rec['document_no'], rec['invoice_number'], str(rec['amount'])))
            if not key or key in seen:
                continue
            seen.add(key)
            out.append(rec)
            accepted += 1
        if len(rows) < AUDIT_PAGE_SIZE:
            return out
        if page >= AUDIT_MAX_PAGES:
            raise RuntimeError(f'{label} {AUDIT_MAX_PAGES * AUDIT_PAGE_SIZE} belge sınırına ulaştı; eksik liste kabul edilmedi.')
        # If a supposedly filtered endpoint returns full pages but no general expenses,
        # continue a few pages only through the API's own pagination. Do not claim success
        # from an empty/ignored filter; the caller will try the next verified shape.
        time.sleep(AUDIT_PAGE_DELAY)
    return out


def _fetch_general_expenses():
    errors = []
    variants = [
        ({'commercial_doc_type': 'general_expense'}, 'commercial_doc_type=general_expense', True),
        ({'type': 'general_expense'}, 'type=general_expense', True),
        ({'document_type': 'general_expense'}, 'document_type=general_expense', True),
        ({}, 'unfiltered commercial_docs', False),
    ]
    for params, label, allow_untyped in variants:
        try:
            rows = _scan_general_variant(params, label, allow_untyped=allow_untyped)
            if rows:
                return rows, errors
        except Exception as e:
            errors.append(str(e))
            if '429' in str(e):
                raise
    raise RuntimeError(
        'General Expense listesi doğrulanamadı. Eski muhasebe DB korundu. ' +
        (' | '.join(errors[-3:]) if errors else 'commercial_docs hiçbir General Expense kaydı döndürmedi.')
    )


def _init_audit_tables():
    c = kdb()
    try:
        c.executescript('''
        CREATE TABLE IF NOT EXISTS accounting_audit_documents(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          source TEXT DEFAULT '',
          document_id TEXT DEFAULT '',
          serial_no TEXT DEFAULT '',
          document_no TEXT DEFAULT '',
          invoice_number TEXT DEFAULT '',
          doc_type TEXT DEFAULT '',
          raw_type TEXT DEFAULT '',
          amount REAL DEFAULT 0,
          currency TEXT DEFAULT '',
          issue_date TEXT DEFAULT '',
          contact_name TEXT DEFAULT '',
          description TEXT DEFAULT '',
          refreshed_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_accounting_audit_doc_id ON accounting_audit_documents(document_id);
        CREATE INDEX IF NOT EXISTS idx_accounting_audit_type ON accounting_audit_documents(doc_type);
        CREATE TABLE IF NOT EXISTS accounting_audit_terms(
          term TEXT NOT NULL COLLATE NOCASE,
          audit_id INTEGER NOT NULL,
          PRIMARY KEY(term,audit_id)
        );
        CREATE INDEX IF NOT EXISTS idx_accounting_audit_term ON accounting_audit_terms(term);
        CREATE TABLE IF NOT EXISTS accounting_audit_state(
          key TEXT PRIMARY KEY,
          value TEXT DEFAULT '',
          updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        ''')
        c.commit()
    finally:
        c.close()


_init_audit_tables()


def _record_terms(rec):
    out = []
    for v in (rec.get('serial_no'), rec.get('document_no'), rec.get('invoice_number')):
        for term in _term_variants(v):
            if term not in out:
                out.append(term)
    return out


def _replace_audit_snapshot(records):
    c = kdb()
    try:
        c.execute('BEGIN IMMEDIATE')
        c.execute('DELETE FROM accounting_audit_terms')
        c.execute('DELETE FROM accounting_audit_documents')
        counts = {'PURCHASE': 0, 'SALE': 0, 'GENERAL EXPENSE': 0}
        term_count = 0
        for rec in records:
            cur = c.execute('''INSERT INTO accounting_audit_documents(
                source,document_id,serial_no,document_no,invoice_number,doc_type,raw_type,
                amount,currency,issue_date,contact_name,description,refreshed_at
              ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)''', (
                rec.get('source',''), rec.get('document_id',''), rec.get('serial_no',''),
                rec.get('document_no',''), rec.get('invoice_number',''), rec.get('doc_type',''),
                rec.get('raw_type',''), float(rec.get('amount') or 0), rec.get('currency',''),
                rec.get('issue_date',''), rec.get('contact_name',''), rec.get('description',''),
            ))
            audit_id = int(cur.lastrowid)
            kind = _txt(rec.get('doc_type')).upper()
            if kind in counts:
                counts[kind] += 1
            for term in _record_terms(rec):
                c.execute('INSERT OR IGNORE INTO accounting_audit_terms(term,audit_id) VALUES(?,?)', (term, audit_id))
                term_count += 1
        now = time.strftime('%Y-%m-%d %H:%M:%S')
        state = {
            'last_refresh': now,
            'document_count': str(len(records)),
            'purchase_count': str(counts['PURCHASE']),
            'sale_count': str(counts['SALE']),
            'general_expense_count': str(counts['GENERAL EXPENSE']),
            'term_count': str(term_count),
            'mode': 'ACCOUNTING AUDIT SNAPSHOT',
        }
        for key, value in state.items():
            c.execute('''INSERT INTO accounting_audit_state(key,value,updated_at)
                         VALUES(?,?,CURRENT_TIMESTAMP)
                         ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_at=CURRENT_TIMESTAMP''',
                      (key, value))
        c.commit()
        return state
    except Exception:
        c.rollback()
        raise
    finally:
        c.close()


def _audit_state():
    c = kdb()
    try:
        rows = c.execute('SELECT key,value,updated_at FROM accounting_audit_state').fetchall()
        out = {str(r['key']): str(r['value'] or '') for r in rows}
        out['ready'] = bool(out.get('last_refresh'))
        for key in ('document_count','purchase_count','sale_count','general_expense_count','term_count'):
            try:
                out[key] = int(out.get(key) or 0)
            except Exception:
                out[key] = 0
        return out
    finally:
        c.close()


@app.get('/api/kolaybi/accounting-audit/status')
def kb_accounting_audit_status():
    return {'ok': True, **_audit_state()}


@app.post('/api/kolaybi/accounting-audit/refresh')
def kb_accounting_audit_refresh():
    sync.base._admin_required()
    if not _AUDIT_REFRESH_LOCK.acquire(blocking=False):
        raise HTTPException(status_code=409, detail='MUHASEBE DB yenileme zaten devam ediyor.')
    try:
        # Reuse the proven dual scanner: PURCHASE includes historical type=invoice,
        # PURCHASE_INVOICE and SALE is fetched independently. We keep the raw rows here
        # because accounting audit also needs the amounts.
        try:
            invoice_rows, warnings = dual._fetch_remote_serials_dual()
            if warnings:
                raise RuntimeError(' | '.join(str(x) for x in warnings[-3:]))
            general_rows, _general_warnings = _fetch_general_expenses()
        except Exception as e:
            raise HTTPException(
                status_code=502,
                detail='MUHASEBE FATURA DB tam yenilenemedi; eski snapshot korundu: ' + str(e)
            )

        records = []
        seen = set()
        for raw in invoice_rows:
            kind = _txt(raw.get('_sama_kind_hint')).upper() or dual._raw_kind(raw)
            if kind not in ('PURCHASE', 'SALE'):
                continue
            rec = _doc_record(raw, kind, 'INVOICES')
            key = (rec['source'], rec['document_id'] or '|'.join((rec['serial_no'], rec['document_no'], rec['invoice_number'], kind)))
            if key in seen:
                continue
            seen.add(key)
            records.append(rec)
        for rec in general_rows:
            key = (rec['source'], rec['document_id'] or '|'.join((rec['serial_no'], rec['document_no'], rec['invoice_number'], rec['doc_type'], str(rec['amount']))))
            if key in seen:
                continue
            seen.add(key)
            records.append(rec)

        if not records:
            raise HTTPException(status_code=502, detail='KolayBi muhasebe listesi boş döndü; eski snapshot korundu.')
        state = _replace_audit_snapshot(records)
        return {
            'ok': True,
            'message': 'MUHASEBE FATURA DB yenilendi.',
            **_audit_state(),
        }
    finally:
        _AUDIT_REFRESH_LOCK.release()


def _parse_expected_amount(v):
    s = _txt(v)
    if not s:
        return None
    s = s.replace('\u00a0', '').replace(' ', '')
    # User/Excel usually uses Turkish grouping. 10.000 => 10000, 10,50 => 10.50.
    if ',' in s and '.' in s:
        if s.rfind(',') > s.rfind('.'):
            s = s.replace('.', '').replace(',', '.')
        else:
            s = s.replace(',', '')
    elif ',' in s:
        right = s.rsplit(',', 1)[1]
        s = s.replace('.', '')
        s = s.replace(',', '.' if len(right) <= 2 else '')
    elif '.' in s:
        parts = s.split('.')
        if len(parts) > 2 or (len(parts) == 2 and len(parts[1]) == 3):
            s = ''.join(parts)
    s = re.sub(r'[^0-9.\-]+', '', s)
    try:
        return float(s)
    except Exception:
        return None


def _parse_bulk_input(text):
    out = []
    for line_no, raw in enumerate(str(text or '').splitlines(), 1):
        line = raw.strip()
        if not line:
            continue
        serial = line
        amount_text = ''
        if '\t' in line:
            parts = [x.strip() for x in line.split('\t')]
            serial = parts[0]
            amount_text = parts[1] if len(parts) > 1 else ''
        elif ';' in line:
            serial, amount_text = [x.strip() for x in line.split(';', 1)]
        else:
            m = re.match(r'^(.+?)\s{2,}([\-0-9.,]+)$', line)
            if not m:
                m = re.match(r'^(\S+)\s+([\-0-9.,]+)$', line)
            if m:
                serial, amount_text = m.group(1).strip(), m.group(2).strip()
        serial = _txt(serial)
        if not serial:
            continue
        out.append({
            'line_no': line_no,
            'serial': serial,
            'expected_amount': _parse_expected_amount(amount_text),
            'expected_text': amount_text,
        })
    return out


def _find_audit_matches(serial_value):
    terms = _term_variants(serial_value)
    if not terms:
        return []
    ph = ','.join('?' for _ in terms)
    c = kdb()
    try:
        rows = c.execute(f'''
            SELECT DISTINCT d.*
            FROM accounting_audit_terms t
            JOIN accounting_audit_documents d ON d.id=t.audit_id
            WHERE UPPER(t.term) IN ({ph})
            ORDER BY d.issue_date DESC,d.id DESC
        ''', tuple(x.upper() for x in terms)).fetchall()
        return [dict(r) for r in rows]
    finally:
        c.close()


@app.post('/api/kolaybi/accounting-audit/check')
async def kb_accounting_audit_check(request: Request):
    state = _audit_state()
    if not state.get('ready'):
        raise HTTPException(status_code=409, detail='MUHASEBE DB henüz indirilmedi. Önce MUHASEBE DB YENİLE.')
    body = await request.json()
    entries = _parse_bulk_input(body.get('text') or '')
    if not entries:
        raise HTTPException(status_code=400, detail='Kontrol edilecek serial listesi boş.')
    if len(entries) > 5000:
        raise HTTPException(status_code=400, detail='Tek kontrolde en fazla 5000 satır kullan.')

    results = []
    found_inputs = missing_inputs = duplicate_inputs = mismatch_inputs = 0
    match_type_counts = {'PURCHASE': 0, 'SALE': 0, 'GENERAL EXPENSE': 0}

    for ent in entries:
        matches = _find_audit_matches(ent['serial'])
        expected = ent['expected_amount']
        if matches:
            found_inputs += 1
        else:
            missing_inputs += 1
        if len(matches) > 1:
            duplicate_inputs += 1

        any_price_match = expected is None
        out_matches = []
        for m in matches:
            amount = float(m.get('amount') or 0)
            difference = None if expected is None else amount - expected
            price_match = None if expected is None else abs(difference) <= 0.01
            if price_match:
                any_price_match = True
            kind = _txt(m.get('doc_type')).upper()
            if kind in match_type_counts:
                match_type_counts[kind] += 1
            out_matches.append({
                'document_id': m.get('document_id') or '',
                'serial_no': m.get('serial_no') or '',
                'document_no': m.get('document_no') or '',
                'invoice_number': m.get('invoice_number') or '',
                'doc_type': m.get('doc_type') or '',
                'amount': amount,
                'currency': m.get('currency') or '',
                'issue_date': m.get('issue_date') or '',
                'contact_name': m.get('contact_name') or '',
                'description': m.get('description') or '',
                'source': m.get('source') or '',
                'difference': difference,
                'price_match': price_match,
            })
        if expected is not None and matches and not any_price_match:
            mismatch_inputs += 1

        if not matches:
            status = 'YOK'
        elif expected is not None and not any_price_match:
            status = 'FIYAT FARKLI' if len(matches) == 1 else 'MÜKERRER / FIYAT FARKLI'
        elif len(matches) > 1:
            status = 'MÜKERRER / VAR'
        else:
            status = 'VAR'

        results.append({
            **ent,
            'status': status,
            'match_count': len(matches),
            'matches': out_matches,
            'price_ok': any_price_match if expected is not None and bool(matches) else None,
        })

    return {
        'ok': True,
        'snapshot': state,
        'summary': {
            'input_count': len(entries),
            'found_count': found_inputs,
            'missing_count': missing_inputs,
            'duplicate_count': duplicate_inputs,
            'price_mismatch_count': mismatch_inputs,
            'purchase_matches': match_type_counts['PURCHASE'],
            'sale_matches': match_type_counts['SALE'],
            'general_expense_matches': match_type_counts['GENERAL EXPENSE'],
        },
        'results': results,
    }


# UI: a third top-level KolayBi mode next to single-SCNA and settings.
settings_button = '<button class="btn secondary" onclick="kbMainMode(\'settings\')">AYARLAR / EŞLEŞTİRMELER</button>'
if settings_button in html and 'MUHASEBE FATURA KONTROL' not in html:
    html = html.replace(
        settings_button,
        settings_button + '\n    <button class="btn secondary" onclick="kbMainMode(\'audit\')">MUHASEBE FATURA KONTROL</button>',
        1,
    )

audit_area = r'''
<div id="kbAccountingAuditArea" style="display:none">
  <div class="calc" style="margin:0 0 12px 0">
    <div style="display:flex;justify-content:space-between;gap:10px;align-items:center;flex-wrap:wrap">
      <div><b>TOPLU MUHASEBE FATURA KONTROL</b><br><small>Serial veya Excel'den SERIAL + TUTAR sütunlarını yapıştır. Aynı seriale ait bütün belgeler ayrı satır gösterilir.</small></div>
      <div style="display:flex;gap:7px;flex-wrap:wrap">
        <button class="btn secondary" onclick="kbAuditRefresh()">MUHASEBE DB YENİLE</button>
        <button class="btn primary" onclick="kbAuditCheck()">TOPLU KONTROL ET</button>
      </div>
    </div>
    <div id="kbAuditDbState" class="section-note" style="margin-top:8px"></div>
    <textarea id="kbAuditInput" rows="10" style="width:100%;margin-top:10px" placeholder="Örnek:\nSNCA956160\nSNCA956161    420.480\nABC123        10.000"></textarea>
  </div>
  <div id="kbAuditSummary" class="calc" style="display:none;margin:0 0 12px 0"></div>
  <div id="kbAuditResult" class="table" style="display:none;overflow:auto;max-height:650px">
    <table>
      <thead><tr><th>INPUT SERIAL</th><th>DURUM</th><th>KAYIT</th><th>TÜR</th><th>KOLAYBI SERIAL / DOC</th><th>TUTAR</th><th>BEKLENEN</th><th>FARK</th><th>TARİH</th><th>DOCUMENT ID</th><th>CARİ / AÇIKLAMA</th></tr></thead>
      <tbody id="kbAuditRows"></tbody>
    </table>
  </div>
</div>
'''
trans_anchor = '<div id="kbTransactionArea">'
if trans_anchor in html and 'id="kbAccountingAuditArea"' not in html:
    html = html.replace(trans_anchor, audit_area + '\n  ' + trans_anchor, 1)

helper = r'''
function kbAuditMoney(v){return Number(v||0).toLocaleString('tr-TR',{maximumFractionDigits:2});}
async function kbAuditStatus(){
  const el=document.getElementById('kbAuditDbState');if(!el)return;
  try{
    const s=await api('/api/kolaybi/accounting-audit/status');
    el.innerHTML=s.ready
      ?'<span class="kb-ready">MUHASEBE DB | PURCHASE: '+Number(s.purchase_count||0).toLocaleString('tr-TR')+' | SALE: '+Number(s.sale_count||0).toLocaleString('tr-TR')+' | GENERAL EXPENSE: '+Number(s.general_expense_count||0).toLocaleString('tr-TR')+' | TOTAL: '+Number(s.document_count||0).toLocaleString('tr-TR')+' | '+kbEsc(s.last_refresh||'-')+'</span>'
      :'<span class="kb-missing">MUHASEBE DB BOŞ | Önce MUHASEBE DB YENİLE</span>';
  }catch(e){el.innerHTML='<span class="kb-missing">MUHASEBE DB DURUMU OKUNAMADI | '+kbEsc(e.message||e)+'</span>';}
}
async function kbAuditRefresh(){
  const el=document.getElementById('kbAuditDbState');
  if(!confirm('KolayBi PURCHASE + SALE + GENERAL EXPENSE muhasebe DB tamamen yenilensin mi?\n\nMevcut snapshot, yeni liste eksiksiz tamamlanmadan silinmez.'))return;
  if(el)el.innerHTML='<span class="section-note">MUHASEBE DB YENİLENİYOR... PURCHASE + SALE + GENERAL EXPENSE indiriliyor.</span>';
  try{
    const r=await api('/api/kolaybi/accounting-audit/refresh',{method:'POST'});
    if(el)el.innerHTML='<span class="kb-ready">✓ MUHASEBE DB YENİLENDİ | PURCHASE: '+Number(r.purchase_count||0).toLocaleString('tr-TR')+' | SALE: '+Number(r.sale_count||0).toLocaleString('tr-TR')+' | GENERAL EXPENSE: '+Number(r.general_expense_count||0).toLocaleString('tr-TR')+' | TOTAL: '+Number(r.document_count||0).toLocaleString('tr-TR')+'</span>';
  }catch(e){if(el)el.innerHTML='<span class="kb-missing">'+kbEsc(e.message||e)+'</span>';alert(e.message||e);}
}
async function kbAuditCheck(){
  const text=String(document.getElementById('kbAuditInput')?.value||'');
  const sum=document.getElementById('kbAuditSummary'),box=document.getElementById('kbAuditResult'),tb=document.getElementById('kbAuditRows');
  if(!text.trim()){alert('Serial listesini yapıştır.');return;}
  if(sum){sum.style.display='block';sum.textContent='KONTROL EDİLİYOR...';}
  try{
    const r=await api('/api/kolaybi/accounting-audit/check',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text})});
    const s=r.summary||{};
    if(sum)sum.innerHTML='<b>ÖZET</b> &nbsp; SORGULANAN: '+Number(s.input_count||0).toLocaleString('tr-TR')+
      ' | <span class="kb-ready">BULUNAN: '+Number(s.found_count||0).toLocaleString('tr-TR')+'</span>'+
      ' | <span class="kb-missing">BULUNAMAYAN: '+Number(s.missing_count||0).toLocaleString('tr-TR')+'</span>'+
      ' | MÜKERRER: '+Number(s.duplicate_count||0).toLocaleString('tr-TR')+
      ' | FİYAT UYUŞMAYAN: '+Number(s.price_mismatch_count||0).toLocaleString('tr-TR')+
      '<br><small>PURCHASE eşleşme: '+Number(s.purchase_matches||0).toLocaleString('tr-TR')+' | SALE: '+Number(s.sale_matches||0).toLocaleString('tr-TR')+' | GENERAL EXPENSE: '+Number(s.general_expense_matches||0).toLocaleString('tr-TR')+'</small>';
    let rows=[];
    (r.results||[]).forEach(x=>{
      const ms=x.matches||[];
      if(!ms.length){
        rows.push(`<tr><td><b>${kbEsc(x.serial||'')}</b></td><td><span class="kb-missing">YOK</span></td><td>0</td><td>-</td><td>-</td><td>-</td><td>${x.expected_amount==null?'-':kbAuditMoney(x.expected_amount)}</td><td>-</td><td>-</td><td>-</td><td>-</td></tr>`);
        return;
      }
      ms.forEach((m,idx)=>{
        const diff=m.difference==null?'-':kbAuditMoney(m.difference);
        const st=x.status.includes('FIYAT FARKLI')?'<span class="kb-missing">'+kbEsc(x.status)+'</span>':(x.match_count>1?'<b>'+kbEsc(x.status)+'</b>':'<span class="kb-ready">VAR</span>');
        rows.push(`<tr><td><b>${kbEsc(x.serial||'')}</b></td><td>${idx===0?st:''}</td><td>${idx===0?Number(x.match_count||0):''}</td><td><b>${kbEsc(m.doc_type||'-')}</b></td><td>${kbEsc(m.serial_no||'-')}<br><small>${kbEsc(m.document_no||m.invoice_number||'')}</small></td><td><b>${kbAuditMoney(m.amount)}</b> ${kbEsc(m.currency||'')}</td><td>${x.expected_amount==null?'-':kbAuditMoney(x.expected_amount)}</td><td>${diff}</td><td>${kbEsc(m.issue_date||'-')}</td><td>${kbEsc(m.document_id||'-')}</td><td>${kbEsc(m.contact_name||'-')}<br><small>${kbEsc(m.description||'')}</small></td></tr>`);
      });
    });
    if(tb)tb.innerHTML=rows.join('');if(box)box.style.display='block';kbAuditStatus();
  }catch(e){if(sum)sum.innerHTML='<span class="kb-missing">'+kbEsc(e.message||e)+'</span>';if(box)box.style.display='none';}
}
if(typeof kbMainMode==='function'){
  const kbMainModeAuditBase=kbMainMode;
  kbMainMode=function(mode){
    const audit=document.getElementById('kbAccountingAuditArea');
    if(mode==='audit'){
      kbMainModeAuditBase('transaction');
      const trans=document.getElementById('kbTransactionArea');if(trans)trans.style.display='none';
      if(audit)audit.style.display='';kbAuditStatus();return;
    }
    if(audit)audit.style.display='none';
    kbMainModeAuditBase(mode);
  };
}
'''
marker = 'async function kbLoadSingleV2(){'
if marker in html and 'async function kbAuditCheck' not in html:
    html = html.replace(marker, helper + '\n' + marker, 1)

core.HTML = html
print('[SAMA] KolayBi bulk accounting audit active: local PURCHASE+SALE+GENERAL EXPENSE snapshot, duplicate serials preserved, amount comparison enabled')
