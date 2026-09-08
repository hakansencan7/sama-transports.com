import threading
import time

# Final backend-only protection for KolayBi invoice serial checks.
# The previous FORCE-LIVE implementation was correct about not trusting stale DB data,
# but it could fire dozens of /invoices requests back-to-back (and more than once per
# single SCNA screen load), which triggers KolayBi code 10429 / HTTP 429.
import kolaybi_sale_product_workflow_patch as base
import kolaybi_serial_force_live_patch as force
import kolaybi_serial_live_check_patch as live

app = base.app
core = base.core
serial = live.serial
sync = live.sync

_SCAN_LOCK = threading.Lock()
_LAST_SCAN_AT = 0.0
_LAST_SCAN_RESULT = None
_RATE_LIMIT_UNTIL = 0.0
BURST_REUSE_SECONDS = 3.0
RATE_LIMIT_COOLDOWN_SECONDS = 30.0
PAGE_DELAY_SECONDS = 0.40
PAGE_SIZE = 100
# KolayBi account already exceeds 3,000 invoice rows. Manual snapshot refresh is now
# allowed to continue until the real end of the list, with a generous safety ceiling.
# 200 x 100 = 20,000 documents. At the current throttle this is still bounded and
# avoids accepting a truncated snapshot as proof that a serial is absent.
MAX_PAGES = 200


def _txt(v):
    return str(v or '').strip()


def _is_429(exc):
    s = _txt(exc).lower()
    return '429' in s or 'too many requests' in s or '10429' in s or 'çok fazla deneme' in s


def _one_get(params):
    global _RATE_LIMIT_UNTIL
    if time.time() < _RATE_LIMIT_UNTIL:
        wait = max(1, int(_RATE_LIMIT_UNTIL - time.time()))
        raise RuntimeError(f'KolayBi API hız limiti aktif (429). {wait} sn sonra yeniden dene.')
    try:
        return sync._rows(sync._get('invoices', params))
    except Exception as e:
        if _is_429(e):
            _RATE_LIMIT_UNTIL = time.time() + RATE_LIMIT_COOLDOWN_SECONDS
            raise RuntimeError(
                'KolayBi API 429 / Çok fazla deneme. Sistem yeni istek yağdırmayı durdurdu; '
                f'{RATE_LIMIT_COOLDOWN_SECONDS:.0f} sn bekleme uygulanıyor.'
            ) from e
        raise


def _row_key(row, hint=''):
    did = serial._row_value(row, ('id','document_id','commercial_doc_id'))
    sr = serial._row_value(row, ('serial_no','full_number','number'))
    dn = serial._row_value(row, ('document_no','document_number','commercial_document_no','commercial_doc_no','doc_no'))
    inv = serial._row_value(row, ('invoice_number',))
    typ = serial._kind_text(row.get('commercial_doc_type') or row.get('type') or row.get('document_type')) if isinstance(row, dict) else ''
    return did or f'{sr}|{dn}|{inv}|{typ}|{hint}'


def _fetch_pages(base_params, hint=''):
    """Use ONE canonical pagination shape and throttle requests.

    Crucially, a 429 immediately stops the scan. We never respond to a rate limit by
    trying five more query variants, which was the source of the request storm.
    """
    out, seen = [], set()
    for page in range(1, MAX_PAGES + 1):
        params = {**base_params, 'page': page, 'per_page': PAGE_SIZE}
        rows = _one_get(params)
        if not rows:
            return out
        new = 0
        for raw in rows:
            if not isinstance(raw, dict):
                continue
            row = dict(raw)
            if hint:
                row['_sama_kind_hint'] = hint
            key = _row_key(row, hint)
            if not key or key in seen:
                continue
            seen.add(key)
            out.append(row)
            new += 1
        if len(rows) < PAGE_SIZE or new == 0:
            return out
        if page >= MAX_PAGES:
            # Never say YOK from a truncated list.
            raise RuntimeError(
                f'KolayBi /invoices taraması {MAX_PAGES * PAGE_SIZE} belgede sınırı doldurdu; '
                'liste tamamlanamadığı için serial sonucu güvenli kabul edilmedi.'
            )
        time.sleep(PAGE_DELAY_SECONDS)
    return out


def _fetch_remote_serials_rate_safe(max_pages=None, page_size=None):
    """Rate-safe replacement for the broad legacy scanner.

    1) One unfiltered pass.
    2) Only if a document kind is absent, one canonical type-specific pass.
    No per_page/limit duplication, no 6-7 filter fallbacks.
    """
    all_rows, seen = [], set()

    def merge(rows):
        for row in rows:
            key = _row_key(row, live._doc_kind_v2(row))
            if key and key not in seen:
                seen.add(key)
                all_rows.append(row)

    merge(_fetch_pages({}, ''))
    kinds = {live._doc_kind_v2(r) for r in all_rows}

    if 'PURCHASE' not in kinds:
        time.sleep(PAGE_DELAY_SECONDS)
        merge(_fetch_pages({'commercial_doc_type': 'purchase_invoice'}, 'PURCHASE'))

    kinds = {live._doc_kind_v2(r) for r in all_rows}
    if 'SALE' not in kinds:
        time.sleep(PAGE_DELAY_SECONDS)
        merge(_fetch_pages({'commercial_doc_type': 'sale_invoice'}, 'SALE'))

    return all_rows, []


# serial._refresh_remote_serial_cache resolves this global dynamically.
serial._fetch_remote_serials = _fetch_remote_serials_rate_safe


def _rate_safe_force_live_refresh():
    """One real API scan per UI burst, not one scan per backend sub-request.

    kbLoadSingleV2 calls transaction/sent/metadata endpoints in the same user action.
    Reusing a scan for only 3 seconds is request coalescing, not stale-history logic.
    A later user action performs a new live scan.
    """
    global _LAST_SCAN_AT, _LAST_SCAN_RESULT
    now = time.time()
    if _LAST_SCAN_RESULT is not None and now - _LAST_SCAN_AT <= BURST_REUSE_SECONDS:
        return {**_LAST_SCAN_RESULT, 'coalesced': True}

    with _SCAN_LOCK:
        now = time.time()
        if _LAST_SCAN_RESULT is not None and now - _LAST_SCAN_AT <= BURST_REUSE_SECONDS:
            return {**_LAST_SCAN_RESULT, 'coalesced': True}
        if now < _RATE_LIMIT_UNTIL:
            wait = max(1, int(_RATE_LIMIT_UNTIL - now))
            raise RuntimeError(f'KolayBi API hız limiti aktif (429). {wait} sn sonra yeniden dene.')

        result = serial._refresh_remote_serial_cache()
        warnings = result.get('warnings') or []
        if warnings:
            # A partially successful scan must never be used as proof that a serial is absent.
            raise RuntimeError('KolayBi canlı serial taraması tam doğrulanamadı: ' + ' | '.join(str(x) for x in warnings[-3:]))
        _LAST_SCAN_RESULT = dict(result)
        _LAST_SCAN_AT = time.time()
        return dict(result)


# All later modules (metadata, sent-state reconciliation and pre-send duplicate guard)
# call force._force_live_refresh dynamically, so one assignment fixes the whole chain.
force._force_live_refresh = _rate_safe_force_live_refresh

# The force-live module also installed this helper into the live module. Keep it routed
# through our coalesced/rate-safe scanner.
def _rate_safe_always_refresh(_max_age_seconds=0, **_kwargs):
    r = _rate_safe_force_live_refresh()
    return {'refreshed': not bool(r.get('coalesced')), **r}

live._ensure_remote_serials_fresh = _rate_safe_always_refresh

print('[SAMA] KolayBi serial 429 protection active: throttled pagination + 20,000-doc safety ceiling + 30s 429 cooldown; no stale DB verdicts')
