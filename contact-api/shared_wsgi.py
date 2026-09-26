"""Gunicorn entry point for the existing Hetzner shared hosting account."""
import json
import os
from pathlib import Path
import stat

from app import create_app


def read_private(path):
    path = Path(path)
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise RuntimeError('Settings must be a private, owner-only regular file')
    if info.st_size > 65536:
        raise RuntimeError('Invalid settings file')
    return path.read_text()


def load_settings(config_path=None):
    path = Path(config_path) if config_path else Path(__file__).resolve().parent.parent / 'settings.json'
    settings = json.loads(read_private(path))
    if settings.get('SMTP_PASSWORD_FILE'):
        password_path = Path(settings['SMTP_PASSWORD_FILE'])
        if not password_path.is_absolute():
            raise RuntimeError('SMTP password file must use an absolute path')
        settings['SMTP_PASSWORD'] = read_private(password_path).rstrip('\r\n')
    return settings


def create_shared_app(config_path=None):
    settings = load_settings(config_path)
    if settings.get('enabled') is not True:
        # Installed but not accepting requests until SMTP verification is complete.
        def maintenance(environ, start_response):
            healthy = environ.get('PATH_INFO') == '/healthz'
            payload = b'{"ok":true,"ready":false}' if healthy else b'{"ok":false,"message":"The contact service is being configured. Please email operations@sama-transports.com."}'
            headers = [('Content-Type', 'application/json'), ('Cache-Control', 'no-store'),
                       ('X-Content-Type-Options', 'nosniff'), ('Content-Length', str(len(payload))),
                       ('Vary', 'Origin')]
            origin = environ.get('HTTP_ORIGIN')
            if origin in ('https://sama-transports.com', 'https://www.sama-transports.com'):
                headers.append(('Access-Control-Allow-Origin', origin))
            start_response('200 OK' if healthy else '503 Service Unavailable', headers)
            return [payload]
        return maintenance
    allowed = {'SMTP_HOST', 'SMTP_USERNAME', 'SMTP_PASSWORD', 'CONTACT_SECRET',
               'SMTP_PORT', 'SMTP_SECURITY', 'STATE_PATH', 'CLAMAV_SOCKET'}
    config = {key: settings[key] for key in allowed if key in settings}
    # Apache's mod_proxy may replace Host with its loopback backend address.
    # The dedicated .htaccess rejects all public hosts except forms.sama-transports.com.
    config['TRUSTED_HOSTS'] = ['forms.sama-transports.com', '127.0.0.1']
    config['ALLOWED_ORIGINS'] = ('https://sama-transports.com', 'https://www.sama-transports.com')
    return create_app(config)
