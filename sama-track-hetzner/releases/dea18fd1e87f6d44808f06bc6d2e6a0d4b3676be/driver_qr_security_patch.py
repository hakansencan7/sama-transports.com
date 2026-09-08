import os
import secrets

from fastapi import HTTPException

import driver_qr_status_patch as base

app = base.app
core = base.core

# Keep existing persistent QR links valid. Only the exceptional read-only-storage
# fallback changes: never fall back to a public, predictable hard-coded signing key.
_EPHEMERAL_SECRET = secrets.token_hex(32).encode('utf-8')


def _safe_secret() -> bytes:
    env = os.environ.get('SAMA_DRIVER_QR_SECRET', '').strip()
    if env:
        return env.encode('utf-8')
    try:
        if base.SECRET_FILE.exists():
            value = base.SECRET_FILE.read_text(encoding='utf-8').strip()
            if value:
                return value.encode('utf-8')
        value = secrets.token_hex(32)
        base.SECRET_FILE.write_text(value, encoding='utf-8')
        try:
            os.chmod(base.SECRET_FILE, 0o600)
        except Exception:
            pass
        return value.encode('utf-8')
    except Exception:
        return _EPHEMERAL_SECRET


base._secret = _safe_secret


def _require_open_trip_from_token(token: str) -> str:
    scna = base._token_scna(token)
    c = core.db()
    try:
        cols = {str(r['name']) for r in c.execute('PRAGMA table_info(trips)').fetchall()}
        deleted_expr = 'COALESCE(is_deleted,0)' if 'is_deleted' in cols else '0'
        row = c.execute(
            f'''SELECT scna,COALESCE(entry_done,0) entry_done,{deleted_expr} is_deleted
                FROM trips WHERE UPPER(TRIM(scna))=? LIMIT 1''',
            (str(scna).strip().upper(),),
        ).fetchone()
    finally:
        c.close()
    if not row:
        raise HTTPException(404, 'Sevkiyat bulunamadı.')
    if int(row['is_deleted'] or 0) == 1:
        raise HTTPException(410, 'Bu sevkiyat artık aktif değil.')
    if int(row['entry_done'] or 0) == 1:
        raise HTTPException(410, 'Bu sevkiyat tamamlandı. QR bağlantısı kapatıldı.')
    return str(row['scna'] or scna).strip().upper()


# Wrap the already-registered public QR routes instead of registering duplicates.
# The original handlers continue to render/submit exactly as before for active trips.
for route in app.routes:
    path = getattr(route, 'path', None)
    methods = getattr(route, 'methods', set()) or set()
    if path == '/driver-status/{token}' and 'GET' in methods:
        original_page = route.endpoint

        def guarded_driver_status_page(token: str, _original=original_page):
            _require_open_trip_from_token(token)
            return _original(token)

        route.endpoint = guarded_driver_status_page
        if getattr(route, 'dependant', None) is not None:
            route.dependant.call = guarded_driver_status_page

    elif path == '/driver-status/{token}/submit' and 'POST' in methods:
        original_submit = route.endpoint

        def guarded_driver_status_submit(token: str, body: base.DriverStatusIn, _original=original_submit):
            _require_open_trip_from_token(token)
            return _original(token, body)

        route.endpoint = guarded_driver_status_submit
        if getattr(route, 'dependant', None) is not None:
            route.dependant.call = guarded_driver_status_submit

print('[SAMA] Driver QR security active: predictable fallback removed, completed/deleted trips blocked')
