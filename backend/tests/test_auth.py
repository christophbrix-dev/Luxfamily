# Auth: login, /auth/me, wrong password
import requests
from conftest import BASE_URL, ADMIN_EMAIL, ADMIN_PASSWORD


def test_login_success(api_client):
    r = api_client.post(f'{BASE_URL}/api/auth/login', json={'email': ADMIN_EMAIL, 'password': ADMIN_PASSWORD}, timeout=15)
    assert r.status_code == 200, r.text
    data = r.json()
    assert 'access_token' in data and data['access_token']
    assert data.get('token_type') == 'bearer'
    assert data['user']['email'] == ADMIN_EMAIL
    assert data['user']['role'] == 'admin'
    assert 'id' in data['user']


def test_login_wrong_password(api_client):
    r = api_client.post(f'{BASE_URL}/api/auth/login', json={'email': ADMIN_EMAIL, 'password': 'wrong-pass'}, timeout=15)
    assert r.status_code == 401


def test_login_unknown_email(api_client):
    r = api_client.post(f'{BASE_URL}/api/auth/login', json={'email': 'nope@example.com', 'password': 'whatever'}, timeout=15)
    assert r.status_code == 401


def test_me_no_token(api_client):
    r = api_client.get(f'{BASE_URL}/api/auth/me', timeout=15)
    assert r.status_code == 401


def test_me_invalid_token(api_client):
    r = api_client.get(f'{BASE_URL}/api/auth/me', headers={'Authorization': 'Bearer not-a-jwt'}, timeout=15)
    assert r.status_code == 401


def test_me_valid_token(api_client, admin_headers):
    r = api_client.get(f'{BASE_URL}/api/auth/me', headers=admin_headers, timeout=15)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body['email'] == ADMIN_EMAIL
    assert body['role'] == 'admin'
    assert 'id' in body
