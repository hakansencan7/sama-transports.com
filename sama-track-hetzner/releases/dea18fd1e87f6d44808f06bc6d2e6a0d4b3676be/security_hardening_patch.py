import threading
import time

from fastapi import Request
from fastapi.responses import JSONResponse

import app as core

app = core.app

# Production hardening that is intentionally conservative: it does not alter
# user records, passwords, shipment rows or accounting rows.
_LOGIN_WINDOW_SECONDS = 10 * 60
_LOGIN_MAX_FAILURES = 10
_LOGIN_BLOCK_SECONDS = 15 * 60
_rate_lock = threading.Lock()
_login_failures = {}
_login_blocked_until = {}


# SQLite remains in the existing DELETE journal mode so current backups and
# Railway/Hetzner copy workflows keep seeing a self-contained .db file. Increase
# lock tolerance instead of enabling WAL without redesigning those backups.
_original_db = core.db


def _resilient_db():
    c = _original_db()
    try:
        c.execute("PRAGMA busy_timeout=30000")
    except Exception:
        pass
    return c


core.db = _resilient_db


# The original permission mapper predates a number of later patch endpoints.
# Keep its rules, then close only the known gaps. Unknown endpoints are not
# globally denied here because several driver/self-service routes perform their
# own ownership checks and a blanket rule would break legitimate operations.
_original_required_permission = core._required_permission


def _hardened_required_permission(path: str, method: str):
    existing = _original_required_permission(path, method)
    if existing:
        return existing

    m = str(method or "GET").upper()

    # Bulk/Excel correction tools can mutate many shipment rows at once.
    if path == "/api/bulk-fix":
        return "shipment.edit"
    if path in {
        "/api/export-import-errors",
        "/api/compare-excel-db",
        "/api/repair-remain-from-excel",
        "/api/repair-freight-from-excel",
        "/api/check-entry-dates-from-excel",
        "/api/repair-entry-dates-from-excel",
    }:
        return "excel.import"

    # The legacy standalone fuel delete route was outside /api/trips/*.
    if path.startswith("/api/fuel/") and m == "DELETE":
        return "shipment.edit"

    # Driver self-service still performs its own driver/plate ownership checks;
    # these permission checks add role/override enforcement on top.
    if path.startswith("/api/driver/my-trips"):
        if m == "GET":
            return "shipment.view"
        if path.endswith("/fuel"):
            return "shipment.edit"
        return "shipment.create"

    # Creating a new driver from the advances screen changes driver master data.
    if path == "/api/advances/driver-create":
        return "driver.edit"

    # Return-expense labels are shipment data, even though stored in a side table.
    if path.startswith("/api/entry-expense-labels/"):
        return "shipment.view" if m == "GET" else "shipment.edit"

    # QR reports are operational signals. Viewing needs operation access; approving
    # or rejecting them changes the live vehicle operation state.
    if path.startswith("/api/driver-status/reports"):
        return "operation.view" if m == "GET" else "operation.edit"
    if path.startswith("/api/driver-status/link/") or path.startswith("/api/driver-status/qr/"):
        return "shipment.view"

    # Accounting audit check is read-only but can reveal accounting document data.
    if path == "/api/kolaybi/accounting-audit/check":
        return "report.view"

    return None


core._required_permission = _hardened_required_permission


def _client_key(request: Request) -> str:
    # A proxy appends the real peer to the right side of an existing X-Forwarded-For
    # chain. Using the left-most value lets a client-supplied spoof bypass throttling.
    # The public Hetzner app is reachable only through the local Apache proxy now.
    forwarded = [x.strip() for x in (request.headers.get("x-forwarded-for") or "").split(",") if x.strip()]
    if forwarded:
        return forwarded[-1][:80]
    if request.client and request.client.host:
        return str(request.client.host)[:80]
    return "unknown"


def _https_request(request: Request) -> bool:
    forwarded = (request.headers.get("x-forwarded-proto") or "").split(",", 1)[0].strip().lower()
    return forwarded == "https" or request.url.scheme == "https"


def _login_precheck(client_key: str):
    now = time.time()
    with _rate_lock:
        blocked_until = float(_login_blocked_until.get(client_key, 0) or 0)
        if blocked_until > now:
            return int(max(1, blocked_until - now))
        if blocked_until:
            _login_blocked_until.pop(client_key, None)
        old = _login_failures.get(client_key, [])
        fresh = [x for x in old if now - x <= _LOGIN_WINDOW_SECONDS]
        if fresh:
            _login_failures[client_key] = fresh
        else:
            _login_failures.pop(client_key, None)
    return 0


def _record_login_result(client_key: str, success: bool):
    now = time.time()
    with _rate_lock:
        if success:
            _login_failures.pop(client_key, None)
            _login_blocked_until.pop(client_key, None)
            return
        failures = [x for x in _login_failures.get(client_key, []) if now - x <= _LOGIN_WINDOW_SECONDS]
        failures.append(now)
        if len(failures) >= _LOGIN_MAX_FAILURES:
            _login_blocked_until[client_key] = now + _LOGIN_BLOCK_SECONDS
            _login_failures.pop(client_key, None)
        else:
            _login_failures[client_key] = failures


def _harden_session_cookie(response):
    hardened = []
    for name, value in response.raw_headers:
        if name.lower() == b"set-cookie" and b"sama_session=" in value.lower():
            text = value.decode("latin-1")
            low = text.lower()
            if "; secure" not in low:
                text += "; Secure"
            if "; httponly" not in low:
                text += "; HttpOnly"
            if "samesite=" not in low:
                text += "; SameSite=Lax"
            value = text.encode("latin-1")
        hardened.append((name, value))
    response.raw_headers = hardened
    return response


@app.middleware("http")
async def sama_security_hardening(request: Request, call_next):
    path = request.url.path
    method = request.method.upper()

    # Do not expose FastAPI's automatic API explorer/schema in production.
    if path in {"/docs", "/redoc", "/openapi.json"}:
        return JSONResponse({"detail": "Not Found"}, status_code=404)

    # TRACE/CONNECT are unnecessary for this application.
    if method in {"TRACE", "CONNECT"}:
        return JSONResponse({"detail": "Method Not Allowed"}, status_code=405)

    client_key = _client_key(request)
    is_login = path == "/api/auth/login" and method == "POST"
    if is_login:
        retry_after = _login_precheck(client_key)
        if retry_after:
            response = JSONResponse(
                {"detail": "Çok fazla başarısız giriş denemesi. Bir süre sonra tekrar deneyin."},
                status_code=429,
            )
            response.headers["Retry-After"] = str(retry_after)
            return response

    response = await call_next(request)

    if is_login:
        _record_login_result(client_key, 200 <= response.status_code < 400)

    # Public health checks need only an up/down signal. Filesystem/database paths
    # are useful to SSH diagnostics, not to anonymous internet clients.
    if path == "/api/health" and 200 <= response.status_code < 300:
        response = JSONResponse({"ok": True, "service": "SAMA TRACK"}, status_code=200)

    _harden_session_cookie(response)

    # Safe headers that do not interfere with the existing inline-heavy UI.
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["X-Permitted-Cross-Domain-Policies"] = "none"
    response.headers["Permissions-Policy"] = "geolocation=(self), camera=(), microphone=(), payment=(), usb=()"
    response.headers["Content-Security-Policy"] = "frame-ancestors 'none'; base-uri 'self'; form-action 'self'"

    if path == "/" or path.startswith("/api/") or path.startswith("/driver-status/"):
        response.headers["Cache-Control"] = "no-store, max-age=0"
        response.headers["Pragma"] = "no-cache"

    if _https_request(request):
        response.headers["Strict-Transport-Security"] = "max-age=31536000"

    return response


print("[SAMA] Security hardening active: authz gaps closed, SQLite busy timeout, docs hidden, login throttling, secure cookies, security headers")
