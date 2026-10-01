#!/usr/bin/env python3
"""Deployment checks with no mail delivery and no credential output."""
import http.client
import json
from pathlib import Path
import smtplib
import socket
import ssl
import sys


def main():
    root = Path.home() / 'sama-contact'
    context = ssl.create_default_context()
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    report = {'tests': [line.strip() for line in (root / 'logs/install.log').read_text().splitlines()
                        if 'passed' in line or 'clamav_live_scan_ok' in line]}
    for port in (465, 587):
        try:
            client = (smtplib.SMTP_SSL('mail.kurumsaleposta.com', port, timeout=10, context=context)
                      if port == 465 else smtplib.SMTP('mail.kurumsaleposta.com', port, timeout=10))
            with client:
                client.ehlo()
                if port == 587:
                    client.starttls(context=context)
                    client.ehlo()
                report['smtp_' + str(port)] = {'tls': client.sock.version(), 'noop': client.noop()[0],
                                              'authentication_attempted': False}
        except Exception as error:
            report['smtp_' + str(port)] = {'error': type(error).__name__}
            if isinstance(error, ssl.SSLCertVerificationError):
                report['smtp_' + str(port)].update(verify_code=error.verify_code,
                                                  verify_message=error.verify_message)
    sys.path.insert(0, str(root / 'app'))
    from attachments import InvalidFile, scan
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as scanner:
            scanner.settimeout(10)
            scanner.connect('/run/clamav/clamd.ctl')
            scanner.sendall(b'zVERSION\0')
            report['clamav_version'] = scanner.recv(512).decode('ascii').strip('\0\n')
        try:
            scan(b'X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*',
                 '/run/clamav/clamd.ctl')
            report['eicar_rejected'] = False
        except InvalidFile:
            report['eicar_rejected'] = True
    except Exception as error:
        report['clamav_error'] = type(error).__name__
    for path in ('/v1/contact/token', '/healthz', '/settings.json', '/app.py'):
        client = http.client.HTTPSConnection('forms.sama-transports.com', context=context, timeout=15)
        try:
            client.request('GET', path, headers={'Origin': 'https://sama-transports.com'})
            response = client.getresponse()
            report[path] = {'status': response.status,
                            'cors': response.getheader('Access-Control-Allow-Origin')}
            response.read(1024)
        except Exception as error:
            report[path] = {'error': type(error).__name__}
        finally:
            client.close()
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
