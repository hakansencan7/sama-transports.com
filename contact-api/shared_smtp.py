"""Private SMTP setup/check/activation. Never accepts or prints a password."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from app import check_settings, settings_from_environment
from attachments import scan
from mailer import connect
from shared_wsgi import load_settings, read_private

ROOT = Path(__file__).resolve().parent.parent


def save_settings(path, settings):
    descriptor, temporary = tempfile.mkstemp(prefix='.settings-', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'w') as stream:
            json.dump(settings, stream, indent=2)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def prepare(root, username, host='mail.kurumsaleposta.com', port=465):
    path = root / 'settings.json'
    settings = json.loads(read_private(path))
    if settings.get('enabled') is True or settings.get('SMTP_PASSWORD'):
        raise RuntimeError('Refusing to replace an active or configured SMTP account')
    candidate = settings_from_environment()
    security = 'ssl' if port == 465 else 'starttls'
    candidate.update(settings, SMTP_HOST=host, SMTP_PORT=port,
                     SMTP_SECURITY=security, SMTP_USERNAME=username, SMTP_PASSWORD='validation-only')
    check_settings(candidate)
    password_path = root / 'smtp-password.txt'
    if password_path.exists():
        read_private(password_path)
    else:
        descriptor = os.open(password_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.close(descriptor)
    settings.update(SMTP_HOST=candidate['SMTP_HOST'], SMTP_PORT=port, SMTP_SECURITY=security,
                    SMTP_USERNAME=candidate['SMTP_USERNAME'], SMTP_PASSWORD='',
                    SMTP_PASSWORD_FILE=str(password_path), enabled=False)
    save_settings(path, settings)


def verify(root):
    settings = settings_from_environment()
    settings.update(load_settings(root / 'settings.json'))
    check_settings(settings)
    client = connect(settings)
    try:
        if client.noop()[0] != 250:
            raise RuntimeError('SMTP NOOP rejected')
    finally:
        client.close()
    scan(b'SAMA contact readiness check\n', settings['CLAMAV_SOCKET'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'check', 'enable'))
    parser.add_argument('--username')
    parser.add_argument('--host', default='mail.kurumsaleposta.com')
    parser.add_argument('--port', type=int, choices=(465, 587), default=465)
    args = parser.parse_args()
    os.umask(0o077)
    if args.action == 'prepare':
        if not args.username:
            parser.error('--username is required for prepare')
        prepare(ROOT, args.username, args.host, args.port)
        print('smtp_settings_prepared; service_disabled; password_entry_required')
        return
    verify(ROOT)
    print('smtp_tls_login_noop_and_clamav_ok; no_email_sent')
    if args.action == 'enable':
        path = ROOT / 'settings.json'
        settings = json.loads(read_private(path))
        settings['enabled'] = True
        save_settings(path, settings)
        subprocess.run([sys.executable, str(ROOT / 'app/shared_manage.py'), 'reload'],
                       check=True, timeout=20)
        print('service_enabled; reload_requested')


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print('smtp_setup_failed:' + type(error).__name__)
        sys.exit(1)
