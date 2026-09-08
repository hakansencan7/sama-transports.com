import time
from fastapi import HTTPException

# Final manual serial refresh strategy.
# One operator button downloads PURCHASE and SALE separately and merges them into
# one persistent snapshot. Normal SCNA checks still make ZERO /invoices requests.
import kolaybi_return_extra_description_final_patch as base
import kolaybi_serial_manual_cache_patch as manual
import kolaybi_serial_rate_limit_patch as rate
import kolaybi_serial_live_check_patch as live

app = base.app
core = base.core
serial = live.serial
sync = live.sync
kdb = live.kdb
html = core.HTML

PAGE_SIZE = 100
MAX_PAGES_PER_STREAM = 250
PAGE_DELAY_SECONDS = 0.55


def _txt(v):
    return str(v or '').strip()


def _raw_kind(row):
    if not isinstance(row, dict):
        return ''
    raw = ' '.join([
        serial._kind_text(row.get('commercial_doc_type')),
        serial._kind_text(row.get('type')),
        serial._kind_text(row.get('document_type')),
        serial._kind_text(row.get('type_group')),
        serial._kind_text(row.get('type_key')),
    ]).lower()
    n = (raw.replace('ı','i').replace('ş','s').replace('ğ','g')
            .replace('ü','u').replace('ö','o').replace('ç','c'))
    if any(x in n for x in ('sale_invoice','sales_invoice','sale','sales','satis')):
        return 'SALE'
    if any(x in n for x in ('purchase_invoice','purchase','purchases','alis','expense','gider','supplier')):
        return 'PURCHASE'
    # Proven old KolayBi behavior: a plain type=invoice row is PURCHASE.
    words = {x for x in n.replace('-', '_').replace('/', ' ').split() if x}
    if 'invoice' in words or n.strip() in ('invoice','invoices'):
        return 'PURCHASE'
    return ''


def _wide_value(row, keys):
    """Read serial/document values across old and new KolayBi response shapes."""
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
    for child in ('data','header','invoice','commercial_document','commercialDoc','document','attributes'):
        v = row.get(child)
        if isinstance(v, dict):
            got = _wide_value(v, keys)
            if got:
                return got
    return ''


def _normalize_row(raw, hint):
    row = dict(raw)
    # A frequent source of false YOK was API field naming. Normalize broader serial
    # aliases into the fields the existing snapshot index already understands.
    sr = _wide_value(row, (
        'serial_no','serial_number','serial','invoice_serial','document_serial',
        'commercial_doc_serial','full_number','number'
    ))
    dn = _wide_value(row, (
        'document_no','document_number','commercial_document_no','commercial_doc_no',
        'commercial_doc_number','doc_no'
    ))
    inv = _wide_value(row, ('invoice_number','invoice_no','invoice_num'))
    if sr:
        row['serial_no'] = sr
    if dn:
        row['document_no'] = dn
    if inv:
        row['invoice_number'] = inv
    row['_sama_kind_hint'] = hint
    return row


def _row_key(row, hint=''):
    did = serial._row_value(row, ('id','document_id','commercial_doc_id'))
    sr = _wide_value(row, ('serial_no','serial_number','serial','invoice_serial','document_serial','full_number','number'))
    dn = _wide_value(row, ('document_no','document_number','commercial_document_no','commercial_doc_no','commercial_doc_number','doc_no'))
    inv = _wide_value(row, ('invoice_number','invoice_no','invoice_num'))
    return did or f'{hint}|{sr}|{dn}|{inv}'


def _scan_variant(params, hint, label):
    """Exhaust one explicit KolayBi document stream.

    A page error after data started is fatal because accepting a partial list could
    falsely say a serial does not exist. 429 handling is inherited from rate._one_get.
    """
    out, seen = [], set()
    for page in range(1, MAX_PAGES_PER_STREAM + 1):
        p = {**params, 'page': page, 'per_page': PAGE_SIZE}
        try:
            rows = rate._one_get(p)
        except Exception as e:
            raise RuntimeError(f'{label} serial taraması sayfa {page} tamamlanamadı: {e}') from e
        if not rows:
            return out

        new_count = 0
        for raw in rows:
            if not isinstance(raw, dict):
                continue
            explicit = _raw_kind(raw)
            # Never force a clearly opposite document into the wrong bucket even if
            # KolayBi ignores a query filter.
            if explicit and explicit != hint:
                continue
            row = _normalize_row(raw, hint)
            key = _row_key(row, hint)
            if not key or key in seen:
                continue
            seen.add(key)
            out.append(row)
            new_count += 1

        if len(rows) < PAGE_SIZE:
            return out
        if new_count == 0:
            raise RuntimeError(
                f'{label} serial taramasında sayfalama aynı kayıtları tekrar döndürdü; '
                'eksik snapshot güvenli kabul edilmedi.'
            )
        if page >= MAX_PAGES_PER_STREAM:
            raise RuntimeError(
                f'{label} serial taraması {MAX_PAGES_PER_STREAM * PAGE_SIZE} belge sınırına ulaştı; '
                'liste tamamlanmadığı için eski snapshot korundu.'
            )
        time.sleep(PAGE_DELAY_SECONDS)
    return out


def _scan_first_working(variants, hint, label):
    """Use the first filter shape that actually returns this document family."""
    errors = []
    for params, variant_name in variants:
        try:
            rows = _scan_variant(params, hint, f'{label} ({variant_name})')
        except Exception as e:
            errors.append(str(e))
            # A failed pagination after data began is not safely replaceable by another
            # query shape; but retrying a different first-page filter can recover API-shape differences.
            continue
        if rows:
            return rows, errors
    if errors:
        raise RuntimeError(f'{label} serial listesi alınamadı: ' + ' | '.join(errors[-3:]))
    return [], []


def _fetch_remote_serials_dual(max_pages=None, page_size=None):
    """Download PURCHASE and SALE independently with one manual refresh action.

    PURCHASE deliberately includes both generic type=invoice and purchase_invoice,
    because historical KolayBi data can expose purchase documents as plain `invoice`.
    SALE is fetched from its own sale_invoice stream. Everything is merged only after
    both sides complete successfully.
    """
    all_rows, seen = [], set()

    def merge(rows):
        for row in rows:
            hint = _txt(row.get('_sama_kind_hint')).upper()
            key = _row_key(row, hint)
            if key and key not in seen:
                seen.add(key)
                all_rows.append(row)

    # PURCHASE stream A: historical/plain INVOICE documents.
    purchase_invoice, e1 = _scan_first_working([
        ({'type':'invoice'}, 'type=invoice'),
        ({'group':'purchase'}, 'group=purchase'),
    ], 'PURCHASE', 'SATIN ALMA / INVOICE')
    merge(purchase_invoice)

    time.sleep(PAGE_DELAY_SECONDS)

    # PURCHASE stream B: explicit purchase_invoice documents. This is merged even
    # when stream A had rows so older and newer KolayBi schemas are both covered.
    purchase_explicit, e2 = _scan_first_working([
        ({'commercial_doc_type':'purchase_invoice'}, 'commercial_doc_type=purchase_invoice'),
        ({'type':'purchase_invoice'}, 'type=purchase_invoice'),
        ({'group':'purchase'}, 'group=purchase'),
    ], 'PURCHASE', 'SATIN ALMA / PURCHASE_INVOICE')
    merge(purchase_explicit)

    time.sleep(PAGE_DELAY_SECONDS)

    # SALE is always its own stream. We no longer infer that the global invoice list
    # happened to contain all sales just because it contained one SALE row.
    sale_rows, e3 = _scan_first_working([
        ({'commercial_doc_type':'sale_invoice'}, 'commercial_doc_type=sale_invoice'),
        ({'type':'sale_invoice'}, 'type=sale_invoice'),
        ({'group':'sale'}, 'group=sale'),
    ], 'SALE', 'SATIŞ / SALE_INVOICE')
    merge(sale_rows)

    # Successful alternate-filter fallbacks are diagnostics, not reasons to reject a
    # complete snapshot. Only hard failures above abort the refresh.
    return all_rows, []


# serial._refresh_remote_serial_cache resolves this function dynamically.
serial._fetch_remote_serials = _fetch_remote_serials_dual

_original_refresh = serial._refresh_remote_serial_cache


def _snapshot_counts():
    c = kdb()
    try:
        rows = c.execute('''
            SELECT UPPER(doc_kind) kind,
                   COUNT(DISTINCT CASE
                       WHEN COALESCE(document_id,'')<>'' THEN document_id
                       ELSE COALESCE(document_no,'')||'|'||COALESCE(serial_no,'')||'|'||COALESCE(invoice_number,'')
                   END) cnt
            FROM remote_invoice_serial_terms
            WHERE UPPER(doc_kind) IN ('PURCHASE','SALE')
            GROUP BY UPPER(doc_kind)
        ''').fetchall()
        d = {str(r['kind']): int(r['cnt'] or 0) for r in rows}
        return d.get('PURCHASE',0), d.get('SALE',0)
    finally:
        c.close()


def _refresh_with_kind_counts():
    result = _original_refresh()
    purchase_count, sale_count = _snapshot_counts()
    c = kdb()
    try:
        for key, value in (
            ('purchase_count', str(purchase_count)),
            ('sale_count', str(sale_count)),
            ('refresh_mode', 'PURCHASE+SALE DUAL SNAPSHOT'),
        ):
            c.execute('''INSERT INTO remote_invoice_serial_state(key,value,updated_at)
                         VALUES(?,?,CURRENT_TIMESTAMP)
                         ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_at=CURRENT_TIMESTAMP''',
                      (key, value))
        c.commit()
    finally:
        c.close()
    return {**result, 'purchase_count': purchase_count, 'sale_count': sale_count}


serial._refresh_remote_serial_cache = _refresh_with_kind_counts


def kb_dual_manual_refresh():
    sync.base._admin_required()
    if not manual._REFRESH_LOCK.acquire(blocking=False):
        raise HTTPException(status_code=409, detail='PURCHASE + SALE SERIAL DB yenileme zaten devam ediyor.')
    try:
        try:
            result = serial._refresh_remote_serial_cache()
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=502,
                detail='PURCHASE + SALE serial listesi yenilenemedi; eski snapshot korundu: ' + str(e)
            )
        warnings = result.get('warnings') or []
        if warnings:
            raise HTTPException(status_code=502, detail='Serial snapshot tam doğrulanamadı; eski snapshot korundu: ' + ' | '.join(str(x) for x in warnings[-3:]))
        st = manual._state()
        return {
            'ok': True,
            'message': 'KolayBi PURCHASE + SALE SERIAL DB yenilendi.',
            'document_count': int(st.get('document_count') or 0),
            'purchase_count': int(st.get('purchase_count') or result.get('purchase_count') or 0),
            'sale_count': int(st.get('sale_count') or result.get('sale_count') or 0),
            'term_count': int(st.get('term_count') or 0),
            'last_refresh': st.get('last_refresh') or result.get('last_refresh') or '',
            'mode': 'PURCHASE+SALE DUAL SNAPSHOT',
        }
    finally:
        manual._REFRESH_LOCK.release()


# Replace the existing manual refresh endpoint; the button remains one button.
for route in app.routes:
    if getattr(route, 'path', None) == '/api/kolaybi/serial-cache/manual-refresh' and 'POST' in (getattr(route, 'methods', set()) or set()):
        route.endpoint = kb_dual_manual_refresh
        if getattr(route, 'dependant', None) is not None:
            route.dependant.call = kb_dual_manual_refresh
        break

# Make the one-button behavior explicit in the existing UI. No new <script> block.
html = html.replace('>SERIAL DB YENİLE</button>', '>PURCHASE + SALE SERIAL YENİLE</button>')
html = html.replace('KolayBi fatura serial DB tamamen yenilensin mi?', 'KolayBi SATIN ALMA + SATIŞ serial listeleri tek işlemde tamamen yenilensin mi?')
html = html.replace('Yeni liste KolayBi /invoices üzerinden bir kez indirilecek', 'PURCHASE ve SALE listeleri KolayBi /invoices üzerinden ayrı ayrı tam indirilecek')
html = html.replace("'✓ SERIAL DB YENİLENDİ | '+Number(r.document_count||0).toLocaleString('tr-TR')+' belge | '", "'✓ SERIAL DB YENİLENDİ | PURCHASE: '+Number(r.purchase_count||0).toLocaleString('tr-TR')+' | SALE: '+Number(r.sale_count||0).toLocaleString('tr-TR')+' | TOTAL: '+Number(r.document_count||0).toLocaleString('tr-TR')+' | '")
html = html.replace("'SERIAL DB: '+Number(s.document_count||0).toLocaleString('tr-TR')+' belge | Son yenileme: '", "'SERIAL DB | PURCHASE: '+Number(s.purchase_count||0).toLocaleString('tr-TR')+' | SALE: '+Number(s.sale_count||0).toLocaleString('tr-TR')+' | TOTAL: '+Number(s.document_count||0).toLocaleString('tr-TR')+' | Son yenileme: '")

core.HTML = html
print('[SAMA] KolayBi dual manual serial snapshot active: ONE button fetches PURCHASE plain invoice + purchase_invoice + SALE sale_invoice; no automatic scans')
