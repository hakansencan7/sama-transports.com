import base64
import hmac
import os
from fastapi import Request
from fastapi.responses import Response

from app import app


def _credentials():
    # Railway variables varsa onları kullan. Yoksa test ortamını yine de kilitli tut.
    user = os.environ.get("SAMA_USER") or "sama"
    password = os.environ.get("SAMA_PASSWORD") or ("sama" + "-test-" + "2026")
    return user, password


@app.middleware("http")
async def sama_track_auth(request: Request, call_next):
    # Railway healthcheck parola istememeli.
    if request.url.path == "/health":
        return Response(content="OK", status_code=200, media_type="text/plain")

    auth_user, auth_password = _credentials()
    auth = request.headers.get("authorization", "")

    if auth.lower().startswith("basic "):
        try:
            decoded = base64.b64decode(auth.split(" ", 1)[1]).decode("utf-8")
            username, password = decoded.split(":", 1)
            if hmac.compare_digest(username, auth_user) and hmac.compare_digest(password, auth_password):
                return await call_next(request)
        except Exception:
            pass

    return Response(
        content="SAMA TRACK - Kullanici adi ve sifre gerekli.",
        status_code=401,
        headers={
            "WWW-Authenticate": 'Basic realm="SAMA TRACK", charset="UTF-8"',
            "Cache-Control": "no-store",
        },
        media_type="text/plain; charset=utf-8",
    )
