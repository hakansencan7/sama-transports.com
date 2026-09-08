import time
from fastapi import HTTPException

import kolaybi_serial_force_live_patch as force
import kolaybi_workflow_v2_patch as workflow
import kolaybi_invoice_metadata_serial_patch as serial

app = force.app
core = force.core
kdb = workflow.kdb
html = core.HTML


def _txt(v):
    return str(v or '').strip()


def _ensure_history_table():
    c = kdb()
    try:
        c.execute('''
        CREATE TABLE IF NOT EXISTS sent_documents_reconcile_history(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          source_table TEXT DEFAULT '',
          scna TEXT DEFAULT '',
          doc_kind TEXT DEFAULT '',
          document_id TEXT DEFAULT '',
          endpoint TEXT DEFAULT '',
          payload_json TEXT DEFAULT '',
          response_json TEXT DEFAULT '',
          tags_json TEXT DEFAULT '',
          original_sent_at TEXT DEFAULT '',
          reason TEXT DEFAULT '',
          reconciled_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        c.commit()
    finally:
        c.close()


_ensure_history_table()


def _archive_and_remove_v2(scna, kind, reason='KOLAYBI LIVE: REMOTE DOCUMENT NOT FOUND'):
    c = kdb()
    try:
        row = c.execute('''SELECT * FROM sent_documents_v2
                           WHERE UPPER(TRIM(scna))=UPPER(TRIM(?))
                             AND UPPER(TRIM(doc_kind))=UPPER(TRIM(?))''',
                        (_txt(scna), _txt(kind))).fetchone()
        if not row:
            return None
        x = dict(row)
        c.execute('''INSERT INTO sent_documents_reconcile_history(
                       source_table,scna,doc_kind,document_id,endpoint,payload_json,response_json,tags_json,
                       original_sent_at,reason,reconciled_at
                     ) VALUES('sent_documents_v2',?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)''',
                  (_txt(x.get('scna')),_txt(x.get('doc_kind')),_txt(x.get('document_id')),
                   _txt(x.get('endpoint')),_txt(x.get('payload_json')),_txt(x.get('response_json')),
                   _txt(x.get('tags_json')),_txt(x.get('sent_at')),reason))
        c.execute('''DELETE FROM sent_documents_v2
                     WHERE UPPER(TRIM(scna))=UPPER(TRIM(?))
                       AND UPPER(TRIM(doc_kind))=UPPER(TRIM(?))''',
                  (_txt(scna), _txt(kind)))
        c.commit()
        return x
    except Exception:
        c.rollback()
        raise
    finally:
        c.close()


def _archive_and_remove_legacy_purchase(scna, reason='KOLAYBI LIVE: REMOTE PURCHASE DOCUMENT NOT FOUND'):
    c = kdb()
    try:
        exists = c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='sent_documents'").fetchone()
        if not exists:
            return None
        row = c.execute('''SELECT * FROM sent_documents WHERE UPPER(TRIM(scna))=UPPER(TRIM(?))''',(_txt(scna),)).fetchone()
        if not row:
            return None
        x = dict(row)
        c.execute('''INSERT INTO sent_documents_reconcile_history(
                       source_table,scna,doc_kind,document_id,endpoint,payload_json,response_json,tags_json,
                       original_sent_at,reason,reconciled_at
                     ) VALUES('sent_documents',?,'PURCHASE',?,?,?,?,?,?,?,CURRENT_TIMESTAMP)''',
                  (_txt(x.get('scna')),_txt(x.get('document_id')),_txt(x.get('endpoint')),
                   _txt(x.get('payload_json')),_txt(x.get('response_json')),_txt(x.get('tags_json')),
                   _txt(x.get('sent_at')),reason))
        c.execute('DELETE FROM sent_documents WHERE UPPER(TRIM(scna))=UPPER(TRIM(?))',(_txt(scna),))
        c.commit()
        return x
    except Exception:
        c.rollback()
        raise
    finally:
        c.close()


def _remote_status_row(scna, kind, matches, local):
    if not matches:
        return None
    m = matches[0]
    out = dict(local or {})
    out.update({
        'scna': _txt(scna),
        'doc_kind': _txt(kind).upper(),
        'document_id': _txt(m.get('document_id')) or _txt(out.get('document_id')),
        'document_no': _txt(m.get('document_no')),
        'serial_no': _txt(m.get('serial_no')),
        'source': 'KOLAYBI LIVE /invoices',
        'remote_verified': True,
        'checked_at': time.strftime('%Y-%m-%d %H:%M:%S'),
    })
    return out


def _reconcile_after_live_scan(scna, kind, matches):
    local = workflow._sent(scna, kind)
    removed = None
    if local and not matches:
        removed = _archive_and_remove_v2(scna, kind)
    if _txt(kind).upper() == 'PURCHASE' and not matches:
        try:
            _archive_and_remove_legacy_purchase(scna)
        except Exception:
            pass
    return _remote_status_row(scna, kind, matches, local), removed


def kb_transaction_sent_remote_authoritative(scna: str):
    """KolayBi API is authoritative. Local send rows are history, not proof that a document still exists."""
    try:
        refresh = force._force_live_refresh()
    except Exception as e:
        raise HTTPException(status_code=502, detail='KolayBi CANLI belge kontrolü yapılamadı: ' + str(e))

    pmeta = serial._meta(scna, 'PURCHASE')
    smeta = serial._meta(scna, 'SALE')
    pmatches = force._fresh_matches(scna, 'PURCHASE', pmeta)
    smatches = force._fresh_matches(scna, 'SALE', smeta)

    purchase, premoved = _reconcile_after_live_scan(scna, 'PURCHASE', pmatches)
    sale, sremoved = _reconcile_after_live_scan(scna, 'SALE', smatches)

    return {
        'purchase': purchase,
        'sale': sale,
        'live_verified': True,
        'checked_at': time.strftime('%Y-%m-%d %H:%M:%S'),
        'document_count': int(refresh.get('document_count') or 0),
        'local_stale_removed': {'purchase': bool(premoved), 'sale': bool(sremoved)},
    }


for route in app.routes:
    if getattr(route, 'path', None) == '/api/kolaybi/transaction/{scna}/sent' and 'GET' in (getattr(route, 'methods', set()) or set()):
        route.endpoint = kb_transaction_sent_remote_authoritative
        if getattr(route, 'dependant', None) is not None:
            route.dependant.call = kb_transaction_sent_remote_authoritative
        break


def _assert_remote_not_duplicate_and_reconcile(scna, kind, meta):
    try:
        force._force_live_refresh()
    except Exception as e:
        raise HTTPException(status_code=502, detail='KolayBi CANLI serial kontrolü yapılamadı; fatura GÖNDERİLMEDİ: ' + str(e))

    matches = force._fresh_matches(scna, kind, meta)
    if matches:
        m = matches[0]
        raise HTTPException(status_code=409, detail=(
            f'KOLAYBI’DE AYNI {kind} SERIAL ZATEN VAR. '
            f'Serial: {_txt(m.get("serial_no")) or _txt(meta.get("serial_no")) or "-"} | '
            f'Document ID: {_txt(m.get("document_id")) or "-"} | '
            f'Document No: {_txt(m.get("document_no")) or "-"}'
        ))

    _archive_and_remove_v2(scna, kind)
    if _txt(kind).upper() == 'PURCHASE':
        try:
            _archive_and_remove_legacy_purchase(scna)
        except Exception:
            pass


serial._assert_remote_not_duplicate = _assert_remote_not_duplicate_and_reconcile

html = html.replace(
    "const sent=await api('/api/kolaybi/transaction/'+encodeURIComponent(scna)+'/sent');",
    "const sent=await api('/api/kolaybi/transaction/'+encodeURIComponent(scna)+'/sent?live=1&ts='+Date.now());",
    1,
)
html = html.replace("✓ GÖNDERİLDİ</span>'", "✓ KOLAYBI'DE VAR</span>'")
html = html.replace("Document ID: '+kbEsc(sent.purchase.document_id||'-')", "KolayBi Document ID: '+kbEsc(sent.purchase.document_id||'-')")
html = html.replace("Document ID: '+kbEsc(sent.sale.document_id||'-')", "KolayBi Document ID: '+kbEsc(sent.sale.document_id||'-')")

core.HTML = html
print('[SAMA] KolayBi sent-status reconciliation active: remote /invoices is authoritative; deleted remote invoices archive stale local flags and become resendable after live verification')
