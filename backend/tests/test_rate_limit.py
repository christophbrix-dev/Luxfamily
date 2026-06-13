# Slowapi rate limit on /api/auth/login: more than 10/min should 429
import requests
import pytest
from conftest import BASE_URL


@pytest.mark.order(after='test_admin_events.py')
def test_login_rate_limit(api_client):
    # Hit with wrong credentials so we never lock ourselves out
    last = None
    saw_429 = False
    for i in range(15):
        r = api_client.post(
            f'{BASE_URL}/api/auth/login',
            json={'email': f'ratelimit_{i}@example.com', 'password': 'x'},
            timeout=15,
        )
        last = r.status_code
        if r.status_code == 429:
            saw_429 = True
            break
    assert saw_429, f'Expected 429 within 15 requests, last status was {last}'
