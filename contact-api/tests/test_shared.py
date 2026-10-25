import json

import pytest
from werkzeug.test import Client
from werkzeug.wrappers import Response

from shared_wsgi import create_shared_app, load_settings
from shared_smtp import prepare, verify


def private_config(tmp_path, **extra):
    path = tmp_path / 'settings.json'
    path.write_text(json.dumps({'enabled': False, **extra}))
    path.chmod(0o600)
    return path


def test_unconfigured_service_cannot_accept_or_issue_form_token(tmp_path):
    client = Client(create_shared_app(private_config(tmp_path)), Response)
    for method, path in [('GET', '/v1/contact/token'), ('POST', '/v1/contact')]:
        result = client.open(path, method=method, headers={'Origin': 'https://sama-transports.com'})
        assert result.status_code == 503
        assert result.json['ok'] is False
        assert 'token' not in result.json
        assert result.headers['Access-Control-Allow-Origin'] == 'https://sama-transports.com'
    assert client.get('/healthz').json == dict(ok=True, ready=False)


def test_config_with_other_user_read_permission_is_rejected(tmp_path):
    path = private_config(tmp_path)
    path.chmod(0o644)
    with pytest.raises(RuntimeError, match='private'):
        create_shared_app(path)


def test_config_symlink_is_rejected(tmp_path):
    path = private_config(tmp_path)
    link = tmp_path / 'link.json'
    link.symlink_to(path)
    with pytest.raises(RuntimeError, match='private'):
        create_shared_app(link)


def test_untrusted_origin_not_granted_cors_in_maintenance(tmp_path):
    client = Client(create_shared_app(private_config(tmp_path)), Response)
    result = client.get('/v1/contact/token', headers={'Origin': 'https://evil.example'})
    assert 'Access-Control-Allow-Origin' not in result.headers


def test_active_service_accepts_apache_backend_host_and_rejects_other_hosts(tmp_path):
    path = private_config(tmp_path, enabled=True, SMTP_HOST='smtp.example.com',
                          SMTP_USERNAME='operations@sama-transports.com', SMTP_PASSWORD='test-only',
                          CONTACT_SECRET='a' * 64, STATE_PATH=str(tmp_path / 'state.sqlite3'))
    client = Client(create_shared_app(path), Response)
    headers = {'Origin': 'https://sama-transports.com', 'X-Forwarded-Proto': 'https',
               'X-Forwarded-For': '192.0.2.8'}
    response = client.get('/v1/contact/token', base_url='http://127.0.0.1:18091', headers=headers)
    assert response.status_code == 200 and response.json['token']
    assert client.get('/v1/contact/token', base_url='https://evil.example', headers=headers).status_code == 400


@pytest.mark.parametrize('host,port,security', [('mail.kurumsaleposta.com', 465, 'ssl'),
                                              ('smtp.example.com', 587, 'starttls')])
def test_prepare_keeps_service_disabled_and_password_out_of_json(tmp_path, host, port, security):
    path = private_config(tmp_path, CONTACT_SECRET='a' * 64, STATE_PATH=str(tmp_path / 'state.sqlite3'))
    prepare(tmp_path, 'sender@sama-transports.com', host, port)
    settings = json.loads(path.read_text())
    assert settings['enabled'] is False
    assert settings['SMTP_PASSWORD'] == ''
    assert (settings['SMTP_HOST'], settings['SMTP_PORT'], settings['SMTP_SECURITY']) == (host, port, security)
    password = tmp_path / 'smtp-password.txt'
    assert password.stat().st_mode & 0o777 == 0o600
    password.write_text('test-only\n')
    assert load_settings(path)['SMTP_PASSWORD'] == 'test-only'
    assert 'test-only' not in path.read_text()


def test_empty_password_cannot_attempt_smtp_authentication(tmp_path, monkeypatch):
    private_config(tmp_path, CONTACT_SECRET='a' * 64, STATE_PATH=str(tmp_path / 'state.sqlite3'))
    prepare(tmp_path, 'sender@sama-transports.com')
    monkeypatch.setattr('shared_smtp.connect', lambda _: pytest.fail('Must not attempt SMTP'))
    with pytest.raises(RuntimeError, match='SMTP_PASSWORD'):
        verify(tmp_path)


@pytest.mark.parametrize('unsafe', ['public', 'symlink'])
def test_password_file_must_be_private_and_not_symlink(tmp_path, unsafe):
    path = private_config(tmp_path, CONTACT_SECRET='a' * 64, STATE_PATH=str(tmp_path / 'state.sqlite3'))
    prepare(tmp_path, 'sender@sama-transports.com')
    password = tmp_path / 'smtp-password.txt'
    if unsafe == 'public':
        password.chmod(0o644)
    else:
        target = tmp_path / 'other.txt'
        target.write_text('test-only')
        target.chmod(0o600)
        password.unlink()
        password.symlink_to(target)
    with pytest.raises(RuntimeError, match='private'):
        load_settings(path)
