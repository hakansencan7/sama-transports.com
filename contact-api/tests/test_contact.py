import io
import json
import smtplib
import ssl
import threading
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from itsdangerous import URLSafeTimedSerializer
from PIL import Image
from werkzeug.datastructures import MultiDict

import app as api
import attachments
import mailer
from store import Store

ORIGIN = 'https://sama-transports.com'
BASE = 'https://forms.sama-transports.com'
VALID = dict(full_name='Hakan Şencan', company='SAMA', phone='+964 12345',
             email='customer@example.com', service='Road Transportation',
             loading_location='Umm Qasr', delivery_location='Basra', website='',
             message='مرحبا — quotation request')

@pytest.fixture
def setup(tmp_path, monkeypatch):
    sent = Mock()
    monkeypatch.setattr(api, 'send', sent)
    config = dict(TESTING=True, SMTP_HOST='smtp.example.com', SMTP_PORT=587,
                  SMTP_SECURITY='starttls', SMTP_USERNAME='operations@sama-transports.com',
                  SMTP_PASSWORD='test-only', CONTACT_SECRET='a'*64,
                  STATE_PATH=str(tmp_path/'state.sqlite3'),
                  ALLOWED_ORIGINS=(ORIGIN, 'https://www.sama-transports.com'))
    app = api.create_app(config)
    return app, app.test_client(), sent


def get_token(client, **kwargs):
    return client.get('/v1/contact/token', base_url=BASE,
                      headers={'Origin': ORIGIN}, **kwargs).json['token']


def post(client, token, data=None, **kwargs):
    return client.post('/v1/contact', base_url=BASE, data=VALID.copy() if data is None else data,
                       content_type='multipart/form-data',
                       headers={'Origin': ORIGIN, 'X-Form-Token': token}, **kwargs)


def test_success_and_idempotent_retry(setup):
    app, client, sent = setup
    token = get_token(client)
    first, second = post(client, token), post(client, token)
    assert first.status_code == second.status_code == 200
    assert first.json == second.json
    assert sent.call_count == 1
    assert sent.call_args.args[1]['message'].startswith('مرحبا')
    data = Path(app.config['STATE_PATH']).read_bytes()
    assert b'customer@example.com' not in data and b'Umm Qasr' not in data


def test_changed_payload_cannot_reuse_sent_token(setup):
    _, client, sent = setup
    token = get_token(client)
    assert post(client, token).status_code == 200
    assert post(client, token, dict(VALID, message='different')).status_code == 409
    assert sent.call_count == 1


@pytest.mark.parametrize('origin', ['', 'null', 'https://evil.example', 'https://sama-transports.com.evil.example'])
def test_origin_gate(setup, origin):
    _, client, sent = setup
    result = client.get('/v1/contact/token', base_url=BASE, headers={'Origin': origin})
    assert result.status_code == 403 and 'Access-Control-Allow-Origin' not in result.headers
    sent.assert_not_called()


def test_cors_preflight_and_error_headers(setup):
    _, client, _ = setup
    response = client.options('/v1/contact', base_url=BASE, headers={
        'Origin': ORIGIN, 'Access-Control-Request-Method': 'POST',
        'Access-Control-Request-Headers': 'x-form-token,content-type'})
    assert response.status_code == 204
    assert response.headers['Access-Control-Allow-Origin'] == ORIGIN
    assert 'Access-Control-Allow-Credentials' not in response.headers
    invalid = post(client, 'bad')
    assert invalid.status_code == 403
    assert invalid.headers['Access-Control-Allow-Origin'] == ORIGIN


def test_missing_expired_and_wrong_client_tokens(setup):
    app, client, sent = setup
    assert post(client, '').status_code == 403
    with patch('time.time', return_value=1000000000):
        old = get_token(client)
    assert post(client, old).status_code == 403
    token = get_token(client)
    assert post(client, token, environ_overrides={'REMOTE_ADDR': '192.0.2.8'}).status_code == 403
    sent.assert_not_called()


@pytest.mark.parametrize('key,value', [
    ('full_name',''), ('company','x'*201), ('email','foo'),
    ('email','customer@example.com\r\nBcc: attacker@example.com'),
    ('company','abc\r\nInjected'), ('message','a\x00b'),
    ('service','Invented'), ('trucks','1.2'), ('cargo_quantity','0'),
    ('trucks','1000001'), ('loading_date','2026-02-30'),
    ('loading_date','20260101'), ('website','https://spam.example'),
    ('message','a'*4001), ('to','attacker@example.com')])
def test_reject_bad_fields(setup, key, value):
    _, client, sent = setup
    assert post(client, get_token(client), dict(VALID, **{key:value})).status_code == 422
    sent.assert_not_called()


def test_duplicate_fields_and_dates(setup):
    _, client, sent = setup
    token = get_token(client)
    fields = MultiDict(VALID)
    fields.add('email', 'attacker@example.com')
    assert post(client, token, fields).status_code == 422
    assert post(client, token, dict(VALID, loading_date='2026-10-10', delivery_date='2026-10-09')).status_code == 422
    sent.assert_not_called()


def test_rate_limit_survives_app_restart(setup):
    app, client, sent = setup
    for _ in range(3):
        assert post(client, get_token(client)).status_code == 200
    restarted = api.create_app(dict(app.config)).test_client()
    assert post(restarted, get_token(restarted)).status_code == 429
    assert sent.call_count == 3


def test_store_atomic_claim(tmp_path):
    store = Store(str(tmp_path/'state.sqlite3'))
    def claim(_):
        return store.claim('a'*32, 'fingerprint', 'client')
    with ThreadPoolExecutor(max_workers=5) as pool:
        results = list(pool.map(claim, range(5)))
    assert results.count('claimed') == 1
    assert results.count('pending') == 4


def test_smtp_failure_is_not_success_and_can_retry(setup):
    _, client, sent = setup
    token = get_token(client)
    sent.side_effect = mailer.DeliveryError()
    result = post(client, token)
    assert result.status_code == 502 and result.json['ok'] is False
    sent.side_effect = None
    assert post(client, token, dict(VALID, message='corrected')).status_code == 200


def test_uncertain_smtp_result_blocks_resend(setup):
    _, client, sent = setup
    token = get_token(client)
    sent.side_effect = mailer.DeliveryError(uncertain=True)
    first, second = post(client, token), post(client, token)
    assert first.status_code == second.status_code == 409
    assert first.json['code'] == 'status_unknown'
    assert sent.call_count == 1


def test_unexpected_error_is_redacted(setup):
    _, client, sent = setup
    sent.side_effect = RuntimeError('password-and-private-message')
    result = post(client, get_token(client))
    assert result.status_code == 503
    assert b'password-and-private-message' not in result.data


def image_bytes(format):
    stream = io.BytesIO()
    Image.new('RGB', (3, 3), 'blue').save(stream, format=format)
    return stream.getvalue()


@pytest.mark.parametrize('extension,data', [
    ('txt',b'Cargo notes for the transport operation.\n'),
    ('pdf',b'%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF\n'),
    ('png',image_bytes('PNG')), ('jpg',image_bytes('JPEG'))])
def test_allowed_files_scanned_and_attached(setup, monkeypatch, extension, data):
    _, client, sent = setup
    scanner = Mock()
    monkeypatch.setattr(attachments, 'scan', scanner)
    fields = dict(VALID, document=(io.BytesIO(data),'../../user-name.'+extension))
    assert post(client, get_token(client), fields).status_code == 200
    scanner.assert_called_once()
    attached = sent.call_args.args[2]
    assert attached[1] == 'cargo-document.'+extension
    if extension in {'jpg','png'}:
        Image.open(io.BytesIO(attached[0])).verify()


@pytest.mark.parametrize('name,data', [('file.exe',b'MZbad'), ('fake.pdf',b'plain text'),
    ('fake.png',b'plain text'), ('empty.txt',b''), ('bad.txt',b'hello\x00world'),
    ('huge.txt',b'x'*(5*1024*1024+1))])
def test_bad_file_content_or_size(setup, name, data):
    _, client, sent = setup
    response = post(client, get_token(client), dict(VALID,document=(io.BytesIO(data),name)))
    assert response.status_code == 422
    sent.assert_not_called()


def test_total_body_size(setup):
    _, client, sent = setup
    response = post(client, get_token(client), dict(VALID, document=(io.BytesIO(b'x'*(6*1024*1024)), 'a.txt')))
    assert response.status_code == 413
    sent.assert_not_called()


def test_multiple_files(setup):
    _, client, sent = setup
    data = MultiDict(VALID)
    data.add('document',(io.BytesIO(b'first document text'), 'a.txt'))
    data.add('document',(io.BytesIO(b'second document text'), 'b.txt'))
    assert post(client, get_token(client), data).status_code == 422
    sent.assert_not_called()


@pytest.mark.parametrize('failure,code', [(attachments.ScannerUnavailable(),503),
                                       (attachments.InvalidFile('Unsafe file'),422)])
def test_scanner_fails_closed(setup, monkeypatch, failure, code):
    _, client, sent = setup
    monkeypatch.setattr(attachments,'scan',Mock(side_effect=failure))
    result = post(client, get_token(client), dict(VALID, document=(io.BytesIO(b'cargo document text'), 'a.txt')))
    assert result.status_code == code
    sent.assert_not_called()


def test_real_clamav_protocol_with_local_stub(tmp_path):
    import socket
    import struct
    path = str(tmp_path/'clamav.sock')
    try:
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    except PermissionError:
        pytest.skip('AF_UNIX sockets are not permitted in this execution environment')
    server.bind(path)
    server.listen(1)
    captured = []
    def receive():
        with server, server.accept()[0] as conn:
            stream = conn.makefile('rb')
            assert stream.read(10) == b'zINSTREAM\0'
            while True:
                size = struct.unpack('!I',stream.read(4))[0]
                if not size: break
                captured.append(stream.read(size))
            conn.sendall(b'stream: OK\0')
    worker = threading.Thread(target=receive)
    worker.start()
    attachments.scan(b'test document',path)
    worker.join(timeout=3)
    assert b''.join(captured) == b'test document'


@pytest.mark.parametrize('reply,exception', [(b'stream: OK\0', None),
    (b'stream: Eicar-Test-Signature FOUND\0', attachments.InvalidFile),
    (b'INSTREAM size limit exceeded. ERROR\0', attachments.ScannerUnavailable)])
def test_clamav_protocol_responses(reply, exception):
    client = Mock()
    client.recv.return_value = reply
    manager = Mock()
    manager.__enter__ = Mock(return_value=client)
    manager.__exit__ = Mock(return_value=False)
    with patch('attachments.socket.socket', return_value=manager):
        if exception:
            with pytest.raises(exception): attachments.scan(b'text','/run/clamav/test')
        else:
            attachments.scan(b'text','/run/clamav/test')
    assert client.sendall.call_args_list[0].args[0] == b'zINSTREAM\0'
    assert client.sendall.call_args_list[1].args[0] == b'\0\0\0\x04text'


def smtp_settings():
    return dict(SMTP_HOST='smtp.example.com', SMTP_PORT=587, SMTP_SECURITY='starttls',
                SMTP_USERNAME='operations@sama-transports.com', SMTP_PASSWORD='test-only')


def test_tls_login_order_and_fixed_headers():
    smtp = Mock()
    with patch('mailer.smtplib.SMTP',return_value=smtp):
        smtp.send_message.return_value = {}
        mailer.send(smtp_settings(),api.validate_fields(MultiDict(VALID)),None,'a'*32)
    assert [c[0] for c in smtp.method_calls] == ['ehlo','starttls','ehlo','login','send_message','close']
    ctx = smtp.starttls.call_args.kwargs['context']
    assert ctx.check_hostname and ctx.verify_mode == ssl.CERT_REQUIRED
    assert ctx.minimum_version == ssl.TLSVersion.TLSv1_2
    mail = smtp.send_message.call_args.args[0]
    assert str(mail['To']) == 'operations@sama-transports.com'
    assert str(mail['Reply-To']) == 'customer@example.com'
    assert smtp.send_message.call_args.kwargs['to_addrs'] == ['operations@sama-transports.com']
    assert mail['Bcc'] is None


def test_starttls_failure_never_authenticates():
    smtp = Mock()
    smtp.starttls.side_effect = smtplib.SMTPNotSupportedError('no TLS')
    with patch('mailer.smtplib.SMTP',return_value=smtp), pytest.raises(mailer.DeliveryError) as exc:
        mailer.send(smtp_settings(),api.validate_fields(MultiDict(VALID)),None,'b'*32)
    assert not exc.value.uncertain
    smtp.login.assert_not_called()
    smtp.send_message.assert_not_called()


def test_disconnect_during_data_is_uncertain():
    smtp = Mock()
    smtp.send_message.side_effect = smtplib.SMTPServerDisconnected('lost acknowledgement')
    with patch('mailer.smtplib.SMTP',return_value=smtp), pytest.raises(mailer.DeliveryError) as exc:
        mailer.send(smtp_settings(),api.validate_fields(MultiDict(VALID)),None,'c'*32)
    assert exc.value.uncertain


def test_service_names_match_frontend():
    class Parser(HTMLParser):
        def __init__(self): super().__init__(); self.collect=False; self.options=[]
        def handle_starttag(self,tag,attrs):
            if tag=='option': self.collect=True
        def handle_endtag(self,tag):
            if tag=='option': self.collect=False
        def handle_data(self,data):
            if self.collect: self.options.append(data)
    parser=Parser()
    parser.feed((Path(__file__).parents[2]/'contact.html').read_text())
    assert tuple(parser.options[1:]) == api.SERVICES


def test_http_and_untrusted_host_rejected(setup):
    _, client, _ = setup
    assert client.get('/v1/contact/token', base_url='http://forms.sama-transports.com', headers={'Origin':ORIGIN}).status_code == 403
    assert client.get('/v1/contact/token', base_url='https://attacker.example', headers={'Origin':ORIGIN}).status_code == 400


def test_ssl_465_keeps_certificate_verification():
    smtp = Mock()
    config = dict(smtp_settings(), SMTP_SECURITY='ssl',SMTP_PORT=465)
    with patch('mailer.smtplib.SMTP_SSL',return_value=smtp) as factory:
        assert mailer.connect(config) is smtp
    context = factory.call_args.kwargs['context']
    assert context.check_hostname and context.verify_mode == ssl.CERT_REQUIRED
    smtp.starttls.assert_not_called()
    smtp.login.assert_called_once()


@pytest.mark.parametrize('override',[{'SMTP_SECURITY':'none'}, {'SMTP_PORT':25},
    {'SMTP_PASSWORD':''}, {'CONTACT_SECRET':'short'}, {'SMTP_USERNAME':'attacker@example.com'}])
def test_insecure_configuration_rejected(setup,override):
    app,_,_=setup
    config=dict(app.config)
    config.update(override)
    with pytest.raises(RuntimeError): api.check_settings(config)


def test_image_pixel_bomb_is_rejected(monkeypatch):
    monkeypatch.setattr(attachments,'scan',Mock())
    monkeypatch.setattr(attachments.Image,'MAX_IMAGE_PIXELS',1)
    with pytest.raises(attachments.InvalidFile):
        attachments.prepare_upload((image_bytes('PNG'),'.png'),'/run/clamav/test')
