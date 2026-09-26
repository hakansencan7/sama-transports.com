#!/usr/bin/env python3
"""Install the reviewed package under the hosting user's home, without root."""
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import zipfile

FILES = ('app.py', 'attachments.py', 'mailer.py', 'store.py', 'check_smtp.py',
         'requirements.txt', 'shared_wsgi.py', 'shared_manage.py', 'shared_smtp.py',
         'deploy/shared-host.htaccess', 'tests/test_contact.py', 'tests/test_shared.py',
         'contact.html')


def write_private(path, text):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'w') as stream:
        stream.write(text)


def main():
    os.umask(0o077)
    home = Path.home()
    root = home / 'sama-contact'
    if root.exists():
        raise RuntimeError('Existing install detected; do not overwrite without review')
    public = home / 'public_html/forms'
    if public.exists():
        raise RuntimeError('Existing forms directory detected; do not overwrite')
    with zipfile.ZipFile(home / 'sama-contact-package.zip') as package:
        if set(package.namelist()) != set(FILES) or len(package.namelist()) != len(FILES):
            raise RuntimeError('Unexpected package contents')
        root.mkdir(mode=0o700)
        for folder in ('app', 'run', 'state', 'logs'):
            (root / folder).mkdir(mode=0o700)
        for name in FILES:
            target = root / name if name == 'contact.html' else root / 'app' / name
            target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            target.write_bytes(package.read(name))
    settings = dict(enabled=False, SMTP_HOST='mail.kurumsaleposta.com', SMTP_PORT=465, SMTP_SECURITY='ssl',
                    SMTP_USERNAME='CHANGE_ME_MAILBOX@sama-transports.com', SMTP_PASSWORD='',
                    CONTACT_SECRET=secrets.token_hex(32),
                    STATE_PATH=str(root / 'state/state.sqlite3'),
                    CLAMAV_SOCKET='/run/clamav/clamd.ctl')
    write_private(root / 'settings.json', json.dumps(settings, indent=2) + '\n')
    with (root / 'logs/install.log').open('w') as log:
        subprocess.run([sys.executable, '-m', 'venv', str(root / 'venv')],
                       check=True, timeout=120, stdout=log, stderr=log)
        subprocess.run([str(root / 'venv/bin/python'), '-m', 'pip', '--isolated',
                        '--disable-pip-version-check', 'install', '--no-input',
                        '--index-url', 'https://pypi.org/simple',
                        '-r', str(root / 'app/requirements.txt'), 'pytest==8.4.2'],
                       check=True, timeout=300, stdout=log, stderr=log)
        subprocess.run([str(root / 'venv/bin/python'), '-m', 'pytest', '-q', 'tests'],
                       cwd=root / 'app', check=True, timeout=120, stdout=log, stderr=log)
        subprocess.run([str(root / 'venv/bin/python'), '-c',
                        "from attachments import scan; scan(b'SAMA contact deployment check\\n', '/run/clamav/clamd.ctl'); print('clamav_live_scan_ok')"],
                       cwd=root / 'app', check=True, timeout=30, stdout=log, stderr=log)
    # The public directory contains only routing rules, never Python code or secrets.
    public.mkdir(mode=0o755)
    public.chmod(0o755)
    (public / '.htaccess').write_bytes((root / 'app/deploy/shared-host.htaccess').read_bytes())
    (public / '.htaccess').chmod(0o644)
    write_private(root / 'service.enabled', 'installed in maintenance mode\n')
    subprocess.run([str(root / 'venv/bin/python'), str(root / 'app/shared_manage.py')],
                   check=True, timeout=30)
    print('install_complete; smtp_disabled; private_config_ready')


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        # No credentials or environment values are printed to the cron manager.
        print('install_failed:' + type(error).__name__)
        sys.exit(1)
