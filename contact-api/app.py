"""Private Python service behind the dedicated forms subdomain's HTTPS proxy."""
import hashlib
import hmac
import ipaddress
import json
import os
import re
import secrets
import sqlite3
import unicodedata
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

from email_validator import EmailNotValidError, validate_email
from flask import Flask, jsonify, request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from werkzeug.exceptions import HTTPException
from werkzeug.middleware.proxy_fix import ProxyFix

from attachments import InvalidFile, ScannerUnavailable, prepare_upload, read_upload
from mailer import DeliveryError, send
from store import Limited, Store

SERVICES = (
    "Road Transportation", "Sea Freight", "Air Freight", "Warehousing & Cargo Handling",
    "Customs Clearance", "Project & Heavy Cargo Transportation", "Pipe Transportation",
    "Rail Freight", "Transit Transportation", "Ship Chartering", "Multimodal Transportation",
    "Vehicle Transportation", "Steel Coil Transportation", "General Cargo Transportation",
    "Heavy Equipment Transportation", "Other",
)
FIELDS = ("full_name", "company", "country", "phone", "email", "service", "cargo_type",
          "cargo_description", "cargo_weight", "cargo_quantity", "trucks", "loading_location",
          "delivery_location", "loading_date", "delivery_date", "message")
REQUIRED = {"full_name", "company", "phone", "email", "service", "loading_location", "delivery_location"}
MULTILINE = {"message", "cargo_description"}


class InvalidRequest(Exception):
    def __init__(self, message, code=422):
        self.message, self.code = message, code


def settings_from_environment():
    result = {key: os.environ.get(key, "") for key in
              ("SMTP_HOST", "SMTP_USERNAME", "SMTP_PASSWORD", "CONTACT_SECRET")}
    result.update(
        SMTP_PORT=int(os.environ.get("SMTP_PORT", "587")),
        SMTP_SECURITY=os.environ.get("SMTP_SECURITY", "starttls"),
        ALLOWED_ORIGINS=tuple(os.environ.get("ALLOWED_ORIGINS",
            "https://sama-transports.com,https://www.sama-transports.com").split(",")),
        TRUSTED_HOSTS=[os.environ.get("API_HOST", "forms.sama-transports.com")],
        STATE_PATH=os.environ.get("STATE_PATH", "/var/lib/sama-contact/state.sqlite3"),
        CLAMAV_SOCKET=os.environ.get("CLAMAV_SOCKET", "/run/clamav/clamd.ctl"),
    )
    return result


def check_settings(config):
    for key in ("SMTP_HOST", "SMTP_USERNAME", "SMTP_PASSWORD", "CONTACT_SECRET"):
        if not config.get(key) or config[key].startswith("CHANGE_ME"):
            raise RuntimeError("Configure " + key + " before starting the service")
    if len(config["CONTACT_SECRET"].encode()) < 32:
        raise RuntimeError("CONTACT_SECRET must contain at least 32 random bytes")
    if not re.fullmatch(r"[A-Za-z0-9.-]+", config["SMTP_HOST"]):
        raise RuntimeError("SMTP_HOST must be the certificate-matching Natro hostname")
    if (config["SMTP_SECURITY"], config["SMTP_PORT"]) not in {("starttls", 587), ("ssl", 465)}:
        raise RuntimeError("Use STARTTLS/587 or implicit TLS/465 only")
    try:
        account = validate_email(config["SMTP_USERNAME"], check_deliverability=False,
                                 allow_smtputf8=False)
    except EmailNotValidError as exc:
        raise RuntimeError("SMTP_USERNAME must be a valid mailbox") from exc
    if account.domain.lower() != "sama-transports.com":
        raise RuntimeError("Use a same-domain Natro mailbox for the sender")
    config["SMTP_USERNAME"] = account.ascii_email
    for origin in config["ALLOWED_ORIGINS"]:
        parsed = urlsplit(origin)
        if parsed.scheme != "https" or not parsed.hostname or parsed.path or parsed.query or parsed.fragment or parsed.username:
            raise RuntimeError("ALLOWED_ORIGINS must contain exact HTTPS origins")
    if not config["ALLOWED_ORIGINS"]:
        raise RuntimeError("At least one allowed origin is required")
    if not Path(config["STATE_PATH"]).is_absolute():
        raise RuntimeError("STATE_PATH must be an absolute path outside the public site")


def validate_fields(form):
    if set(form) - set(FIELDS) - {"website"}:
        raise InvalidRequest("The form contains unsupported fields.")
    if any(len(form.getlist(key)) != 1 for key in form):
        raise InvalidRequest("Duplicate form fields are not accepted.")
    if form.get("website", ""):
        raise InvalidRequest("The request could not be accepted.")
    result = {}
    for key in FIELDS:
        value = unicodedata.normalize("NFC", form.get(key, "")).strip()
        maximum = 4000 if key in MULTILINE else (254 if key == "email" else 200)
        if len(value) > maximum or (key in REQUIRED and not value):
            raise InvalidRequest("Please check the " + key.replace("_", " ") + " field.")
        if any((unicodedata.category(c) == "Cc" and not (key in MULTILINE and c in "\n\r\t"))
               or c in "\u2028\u2029" for c in value):
            raise InvalidRequest("A form field contains invalid characters.")
        result[key] = value
    try:
        result["email"] = validate_email(result["email"], check_deliverability=False,
                                          allow_smtputf8=False).ascii_email
    except EmailNotValidError as exc:
        raise InvalidRequest("Please enter a valid email address.") from exc
    if result["service"] not in SERVICES:
        raise InvalidRequest("Please select a service from the list.")
    for key in ("cargo_quantity", "trucks"):
        if result[key] and (not re.fullmatch(r"[0-9]{1,7}", result[key]) or not 1 <= int(result[key]) <= 1000000):
            raise InvalidRequest("Please enter a whole number between 1 and 1000000.")
    for key in ("loading_date", "delivery_date"):
        if result[key]:
            try:
                if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", result[key]):
                    raise ValueError()
                date.fromisoformat(result[key])
            except ValueError as exc:
                raise InvalidRequest("Please enter a valid date.") from exc
    if result["loading_date"] and result["delivery_date"] and result["delivery_date"] < result["loading_date"]:
        raise InvalidRequest("Delivery date cannot be earlier than loading date.")
    return result


def create_app(overrides=None):
    app = Flask(__name__, static_folder=None)
    app.config.update(settings_from_environment())
    if overrides:
        app.config.update(overrides)
    check_settings(app.config)
    app.config.update(MAX_CONTENT_LENGTH=6 * 1024 * 1024, MAX_FORM_MEMORY_SIZE=64 * 1024,
                      MAX_FORM_PARTS=24)
    # Exactly one trusted proxy; Gunicorn listens only on loopback.
    # The edge proxy MUST strip client-supplied forwarding headers and provide the real IP.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=0, x_port=0, x_prefix=0)
    store = Store(app.config["STATE_PATH"])
    signer = URLSafeTimedSerializer(app.config["CONTACT_SECRET"], salt="sama-contact-v1")

    def digest(value):
        return hmac.new(app.config["CONTACT_SECRET"].encode(), value, hashlib.sha256).hexdigest()

    def client_key():
        try:
            address = ipaddress.ip_address(request.remote_addr)
            if address.version == 6:
                address = ipaddress.ip_network(str(address) + "/64", strict=False)
            return digest(str(address).encode())
        except ValueError as exc:
            raise InvalidRequest("The request could not be verified.", 400) from exc

    @app.before_request
    def check_request():
        if request.path == "/healthz":
            return None
        if request.headers.get("Origin") not in app.config["ALLOWED_ORIGINS"]:
            raise InvalidRequest("This website is not allowed to submit requests.", 403)
        if not request.is_secure:
            raise InvalidRequest("HTTPS is required.", 403)
        if request.method == "OPTIONS":
            wanted = {h.strip().lower() for h in request.headers.get("Access-Control-Request-Headers", "").split(",") if h.strip()}
            if request.headers.get("Access-Control-Request-Method") not in {"GET", "POST"} or wanted - {"x-form-token", "content-type"}:
                raise InvalidRequest("Unsupported preflight request.", 403)
            return "", 204

    @app.after_request
    def response_headers(response):
        origin = request.headers.get("Origin")
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
        response.vary.add("Origin")
        if origin in app.config["ALLOWED_ORIGINS"]:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-Form-Token"
            response.headers["Access-Control-Expose-Headers"] = "Retry-After"
        return response

    @app.errorhandler(InvalidRequest)
    def invalid(exc):
        return jsonify(ok=False, message=exc.message), exc.code

    @app.errorhandler(Limited)
    def limited(_exc):
        return jsonify(ok=False, message="Too many requests. Please contact operations by email or try again later."), 429, {"Retry-After": "600"}

    @app.errorhandler(HTTPException)
    def http_error(exc):
        message = "The request is too large (maximum document size: 5 MB)." if exc.code == 413 else "The request could not be accepted."
        return jsonify(ok=False, message=message), exc.code

    @app.errorhandler(Exception)
    def unexpected(exc):
        # Never log submitted fields, credentials, filenames or SMTP response text.
        app.logger.error("contact_service_error type=%s", type(exc).__name__)
        return jsonify(ok=False, message="The service is temporarily unavailable. Please contact operations by email."), 503

    @app.get("/healthz")
    def health():
        return jsonify(ok=True)

    @app.get("/v1/contact/token")
    def token():
        key = client_key()
        store.limit([("token:" + key, 20, 600), ("token:global", 500, 600)])
        value = signer.dumps({"id": secrets.token_hex(16), "ip": key,
                              "origin": request.headers["Origin"]})
        return jsonify(ok=True, token=value, expires_in=3600)

    @app.post("/v1/contact")
    def contact():
        key = client_key()
        store.limit([("post:" + key, 30, 600), ("post:global", 600, 600)])
        if request.mimetype != "multipart/form-data":
            raise InvalidRequest("Use multipart form data.", 415)
        token_value = request.headers.get("X-Form-Token", "")
        if len(token_value) > 1024:
            raise InvalidRequest("Please reload the form.", 403)
        try:
            payload = signer.loads(token_value, max_age=3600)
        except (BadSignature, SignatureExpired) as exc:
            raise InvalidRequest("Your form session expired. Reload this page before submitting.", 403) from exc
        if (not isinstance(payload, dict) or payload.get("ip") != key
                or payload.get("origin") != request.headers["Origin"]
                or not re.fullmatch(r"[0-9a-f]{32}", str(payload.get("id", "")))):
            raise InvalidRequest("Please reload the form.", 403)
        request_id = payload["id"]
        fields = validate_fields(request.form)
        if set(request.files) - {"document"} or len(request.files.getlist("document")) > 1:
            raise InvalidRequest("Upload one document only.")
        try:
            raw = read_upload(request.files.get("document"))
        except InvalidFile as exc:
            raise InvalidRequest(str(exc)) from exc
        fingerprint = digest(json.dumps(fields, sort_keys=True).encode() + b"\0" +
                             (raw[1].encode() + b"\0" + raw[0] if raw else b""))
        state = store.claim(request_id, fingerprint, key)
        if state == "sent":
            return jsonify(ok=True, reference=request_id)
        if state != "claimed":
            return jsonify(ok=False, code="status_unknown" if state in {"pending", "uncertain"} else "changed",
                           reference=request_id, message="This request is already being processed or its status needs checking. Please contact operations with this reference before submitting again."), 409
        try:
            attachment = prepare_upload(raw, app.config["CLAMAV_SOCKET"])
        except InvalidFile as exc:
            # No SMTP attempt; release this token so the visitor can choose a valid file.
            with store.connect() as db:
                db.execute("DELETE FROM submissions WHERE id=?", (request_id,))
            raise InvalidRequest(str(exc)) from exc
        except ScannerUnavailable:
            store.finish(request_id, "retryable")
            return jsonify(ok=False, message="Document scanning is temporarily unavailable. Try again later or email operations directly."), 503
        try:
            send(app.config, fields, attachment, request_id)
        except DeliveryError as exc:
            store.finish(request_id, "uncertain" if exc.uncertain else "retryable")
            app.logger.warning("contact_delivery_failed reference=%s uncertain=%s", request_id, exc.uncertain)
            if exc.uncertain:
                return jsonify(ok=False, code="status_unknown", reference=request_id,
                               message="We could not confirm the delivery status. Please contact operations with this reference before submitting again."), 409
            return jsonify(ok=False, message="The email server could not accept your request. Your form has not been cleared. Please try again later or email operations."), 502
        try:
            store.finish(request_id, "sent")
        except sqlite3.Error:
            # SMTP accepted the message, but recording success failed. Block auto-retry.
            return jsonify(ok=False, code="status_unknown", reference=request_id,
                           message="The email server accepted your request, but confirmation could not be saved. Please contact operations with this reference."), 409
        app.logger.info("contact_accepted reference=%s", request_id)
        return jsonify(ok=True, reference=request_id)

    return app
