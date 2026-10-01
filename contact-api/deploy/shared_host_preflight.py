#!/usr/bin/env python3
"""Read-only hosting checks; write a private report next to this script.

Run with Python 3 as the hosting user, outside public_html. No credentials,
environment values, customer data, or mail content are read or reported.
An existing report makes subsequent runs a no-op.
"""

import ctypes.util
import datetime
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


PROBE = r'''
import importlib.util, json, sqlite3, ssl, sys
try:
    from importlib import metadata
except ImportError:
    metadata = None
packages = {}
for package in ('Flask', 'Werkzeug', 'gunicorn', 'pillow', 'python-magic',
                'email-validator', 'itsdangerous', 'uvicorn'):
    try:
        packages[package] = metadata.version(package) if metadata else None
    except metadata.PackageNotFoundError:
        packages[package] = None
print(json.dumps({
    'python': sys.version.split()[0],
    'sqlite': sqlite3.sqlite_version,
    'ssl': ssl.OPENSSL_VERSION,
    'venv_available': importlib.util.find_spec('venv') is not None,
    'pip_available': importlib.util.find_spec('pip') is not None,
    'packages': packages,
}))
'''


def main():
    os.umask(0o077)
    report_path = Path(__file__).resolve().with_name('sama_contact_preflight.json')
    if report_path.exists():
        return
    home = Path.home()
    candidates = (
        Path(sys.executable), Path('/usr/bin/python3'),
        home / 'samaenv/bin/python',
        home / 'sama-track-hetzner/venv/bin/python',
    )
    runtimes = {}
    for executable in candidates:
        if str(executable) in runtimes or not executable.exists():
            continue
        try:
            result = subprocess.run(
                [str(executable), '-c', PROBE], capture_output=True,
                text=True, timeout=15, check=True,
            )
            runtimes[str(executable)] = json.loads(result.stdout)
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            runtimes[str(executable)] = {'error': type(error).__name__}
    sockets = {}
    for name in ('/run/clamav/clamd.ctl', '/var/run/clamav/clamd.ctl',
                 '/run/clamd.scan/clamd.sock', '/tmp/clamd.socket'):
        path = Path(name)
        try:
            sockets[name] = {
                'exists': path.exists(),
                'socket': path.is_socket(),
                'writable': os.access(name, os.W_OK),
            }
        except OSError:
            sockets[name] = {'accessible': False}
    report = {
        'checked_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'runtimes': runtimes,
        'libmagic': ctypes.util.find_library('magic'),
        'clamav': {name: shutil.which(name) for name in
                   ('clamscan', 'clamdscan', 'clamd', 'freshclam')},
        'clamav_sockets': sockets,
        'openssl': shutil.which('openssl'),
        'curl': shutil.which('curl'),
    }
    data = json.dumps(report, indent=2) + '\n'
    descriptor = os.open(report_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'w') as stream:
        stream.write(data)
    print(data, end='')


if __name__ == '__main__':
    main()
