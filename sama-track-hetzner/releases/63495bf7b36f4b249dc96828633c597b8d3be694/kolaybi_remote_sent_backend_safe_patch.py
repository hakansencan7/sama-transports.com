import json
import time
from fastapi import HTTPException

# IMPORTANT: backend-only patch. Do not touch core.HTML or the login JavaScript.
# The existing force-live serial patch already performs real KolayBi /invoices scans.
import kolaybi_serial_force_live_patch as force
import kolaybi_workflow_v2_patch as workflow
import kolaybi_invoice_metadata_serial_patch as serial

app = force.app
core = force.core
kdb = workflow.kdb


def _txt(v):
    return str(v or '').strip()


def _match_as_sent(scna, kind, matches):
    if not matches:
        return None
    m = matches[0]
    return {
        'scna': _txt(scna),
        'doc_kind': _txt(kind).upper(),
        'document_id': _txt(m.get('document_id') or m.get('id')),
        'document_no': _txt(m.get('document_no')),
        'serial_no': _txt(m.get('serial_no')),
        'invoice_number': _txt(m.get('invoice_number')),
        'source': 'KOLAYBI LIVE /invoices',
        'remote_verified': True,
        'checked_at': time.strftime('%Y-%m-%d %H:%M:%S'),
    }


def _scan_matches(scna, kind):
    # Every call hits KolayBi now. No local sent table is accepted as proof.
    try:
        force._force_live_refresh()
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail='KolayBi CANLI belge kontrolü yapılamadı: ' + str(e)
        )
    meta = serial._meta(scna, kind)
    return force._fresh_matches(scna, kind, meta)


def _remote_sent(scna, kind):
    return _match_as_sent(scna, kind, _scan_matches(scna, kind))


def kb_transaction_sent_remote_safe(scna: str):
    """Return sent state ONLY when the invoice currently exists in KolayBi.

    Local sent_documents_v2 rows are retained merely as historical/audit data and
    never make the UI show GONDERILDI by themselves.
    """
    try:
        refresh = force._force_live_refresh()
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail='KolayBi CANLI belge kontrolü yapılamadı: ' + str(e)
        )

    pmeta = serial._meta(scna, 'PURCHASE')
    smeta = serial._meta(scna, 'SALE')
    pmatches = force._fresh_matches(scna, 'PURCHASE', pmeta)
    smatches = force._fresh_matches(scna, 'SALE', smeta)

    return {
        'purchase': _match_as_sent(scna, 'PURCHASE', pmatches),
        'sale': _match_as_sent(scna, 'SALE', smatches),
        'live_verified': True,
        'checked_at': time.strftime('%Y-%m-%d %H:%M:%S'),
        'document_count': int(refresh.get('document_count') or 0),
        'source': 'KOLAYBI LIVE /invoices',
    }


# Replace only the backend /sent route. No browser HTML/JS mutation.
for route in app.routes:
    if getattr(route, 'path', None) == '/api/kolaybi/transaction/{scna}/sent' and 'GET' in (getattr(route, 'methods', set()) or set()):
        route.endpoint = kb_transaction_sent_remote_safe
        if getattr(route, 'dependant', None) is not None:
            route.dependant.call = kb_transaction_sent_remote_safe
        break


# The proven V2 PURCHASE/SALE send functions call workflow._sent before posting.
# Make that guard remote-authoritative too, so a deleted KolayBi invoice can be re-sent.
workflow._sent = _remote_sent


def _save_sent_upsert(scna, kind, did, endpoint, payload, result, tag_result):
    """Overwrite stale local audit row after a verified new remote send.

    This prevents an old local row (left behind after a KolayBi deletion) from
    causing a UNIQUE constraint error when the document is legitimately re-sent.
    """
    c = kdb()
    try:
        c.execute('''
            INSERT INTO sent_documents_v2(
              scna,doc_kind,document_id,endpoint,payload_json,response_json,tags_json,sent_at
            ) VALUES(?,?,?,?,?,?,?,CURRENT_TIMESTAMP)
            ON CONFLICT(scna,doc_kind) DO UPDATE SET
              document_id=excluded.document_id,
              endpoint=excluded.endpoint,
              payload_json=excluded.payload_json,
              response_json=excluded.response_json,
              tags_json=excluded.tags_json,
              sent_at=CURRENT_TIMESTAMP
        ''',(
            _txt(scna),_txt(kind).upper(),_txt(did),_txt(endpoint),
            json.dumps(payload,ensure_ascii=False),
            json.dumps(result,ensure_ascii=False),
            json.dumps(tag_result,ensure_ascii=False) if tag_result is not None else ''
        ))
        c.commit()
    finally:
        c.close()


workflow._save_sent = _save_sent_upsert

print('[SAMA] KolayBi remote sent-status SAFE backend active: no HTML/login changes; GONDERILDI comes only from live /invoices')
