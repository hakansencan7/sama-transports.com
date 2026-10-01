"""Run with the service environment via systemd-run. Does not send an email."""
import sys
from app import check_settings, settings_from_environment
from mailer import connect

settings = settings_from_environment()
try:
    check_settings(settings)
    client = connect(settings)
    try:
        code, _ = client.noop()
        if code != 250:
            raise RuntimeError('SMTP NOOP rejected')
    finally:
        client.close()
except Exception as exc:
    # Provider errors can contain addresses or secrets; emit only the exception type.
    print('SMTP check failed: ' + type(exc).__name__, file=sys.stderr)
    sys.exit(1)
print('TLS certificate, SMTP authentication and NOOP succeeded. No email was sent.')
