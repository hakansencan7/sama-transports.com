"""Start/check the dedicated service; intended for the hosting cron manager."""
import fcntl
import http.client
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent


def health():
    client = http.client.HTTPConnection('127.0.0.1', 18091, timeout=3)
    try:
        client.request('GET', '/healthz', headers={'Host': 'forms.sama-transports.com'})
        result = client.getresponse()
        return result.status == 200 and json.loads(result.read(1024)).get('ok') is True
    except (OSError, ValueError, http.client.HTTPException):
        return False
    finally:
        client.close()


def own_process():
    try:
        pid = int((ROOT / 'run/gunicorn.pid').read_text().strip())
        if pid < 2:
            return None
        command = Path('/proc', str(pid), 'cmdline').read_bytes()
        if b'gunicorn' in command and b'sama-contact' in command:
            return pid
    except (OSError, ValueError):
        pass
    return None


def main():
    os.umask(0o077)
    if not (ROOT / 'service.enabled').is_file():
        print('service_disabled')
        return
    with (ROOT / 'run/manager.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        pid = own_process()
        if len(sys.argv) > 1 and sys.argv[1] == 'reload':
            if pid is None:
                raise RuntimeError('No verified service process to reload')
            import signal
            os.kill(pid, signal.SIGHUP)
            print('reload_requested')
            return
        if pid:
            print('service_healthy' if health() else 'service_process_present_health_failed')
            return
        if health():
            raise RuntimeError('Port is occupied by an unverified service')
        subprocess.run([
            str(ROOT / 'venv/bin/gunicorn'), '--daemon', '--name', 'sama-contact',
            '--chdir', str(ROOT / 'app'), '--bind', '127.0.0.1:18091',
            '--workers', '2', '--timeout', '120', '--graceful-timeout', '130',
            '--max-requests', '200', '--max-requests-jitter', '25',
            '--pid', str(ROOT / 'run/gunicorn.pid'),
            '--error-logfile', str(ROOT / 'logs/gunicorn.log'),
            '--capture-output', 'shared_wsgi:create_shared_app()',
        ], check=True, timeout=20)
        print('service_start_requested')


if __name__ == '__main__':
    main()
