# Health probe
import os
import requests

BASE_URL = (os.environ.get('EXPO_BACKEND_URL') or 'https://kids-adventure-hub-4.preview.emergentagent.com').rstrip('/')


def test_health():
    r = requests.get(f'{BASE_URL}/api/health', timeout=15)
    assert r.status_code == 200
    body = r.json()
    assert body.get('status') == 'ok'


def test_root():
    r = requests.get(f'{BASE_URL}/api/', timeout=15)
    assert r.status_code == 200
    assert 'service' in r.json()
