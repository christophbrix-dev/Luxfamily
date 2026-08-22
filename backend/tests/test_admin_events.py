# Admin event CRUD: create, update, delete, draft toggle
import uuid

from conftest import BASE_URL


def _sample_payload():
    return {
        'title': {'en': f'TEST_Event_{uuid.uuid4().hex[:6]}', 'de': 'TEST DE', 'fr': 'TEST FR'},
        'short': {'en': 'short', 'de': 'kurz', 'fr': 'court'},
        'description': {'en': 'desc', 'de': 'beschr', 'fr': 'descr'},
        'type': 'Event',
        'canton': 'Luxembourg',
        'town': 'Luxembourg City',
        'category': ['family'],
        'age_min': 0,
        'age_max': 12,
        'start_date': '2030-01-15',
        'end_date': None,
        'time': '10:00',
        'price_adult': 0,
        'price_child': 0,
        'price_label': {'en': 'free', 'de': 'frei', 'fr': 'gratuit'},
        'accessibility': {'en': 'yes', 'de': 'ja', 'fr': 'oui'},
        'weather_fit': {'en': 'any', 'de': 'jedes', 'fr': 'tout'},
        'image': 'https://example.com/img.jpg',
        'lat': 49.61,
        'lng': 6.13,
        'bookable': False,
        'published': True,
        'rating': 4.5,
    }


def test_admin_create_requires_auth(api_client):
    r = api_client.post(f'{BASE_URL}/api/admin/events', json=_sample_payload(), timeout=15)
    assert r.status_code == 401


def test_admin_list_requires_auth(api_client):
    r = api_client.get(f'{BASE_URL}/api/admin/events', timeout=15)
    assert r.status_code == 401


def test_admin_create_update_delete_flow(api_client, admin_headers):
    payload = _sample_payload()

    # Create
    r = api_client.post(f'{BASE_URL}/api/admin/events', json=payload, headers=admin_headers, timeout=15)
    assert r.status_code == 201, r.text
    created = r.json()
    assert created['title']['en'] == payload['title']['en']
    assert '_id' not in created
    eid = created['id']

    try:
        # Verify it's in admin list
        r2 = api_client.get(f'{BASE_URL}/api/admin/events', headers=admin_headers, timeout=15)
        assert r2.status_code == 200
        assert any(e['id'] == eid for e in r2.json())

        # Public list includes it (start_date in 2030, upcoming=true by default)
        pub = api_client.get(f'{BASE_URL}/api/events', timeout=15).json()
        assert any(e['id'] == eid for e in pub)

        # PATCH to unpublish
        r3 = api_client.patch(
            f'{BASE_URL}/api/admin/events/{eid}', json={'published': False}, headers=admin_headers, timeout=15
        )
        assert r3.status_code == 200, r3.text
        assert r3.json()['published'] is False

        # Public list now excludes it
        pub2 = api_client.get(f'{BASE_URL}/api/events', timeout=15).json()
        assert not any(e['id'] == eid for e in pub2)

        # Public detail returns 404 when unpublished
        det = api_client.get(f'{BASE_URL}/api/events/{eid}', timeout=15)
        assert det.status_code == 404

        # PATCH back to published
        r4 = api_client.patch(
            f'{BASE_URL}/api/admin/events/{eid}', json={'published': True, 'town': 'Esch'}, headers=admin_headers, timeout=15
        )
        assert r4.status_code == 200
        assert r4.json()['town'] == 'Esch'

        # GET verifies persistence of update
        det2 = api_client.get(f'{BASE_URL}/api/events/{eid}', timeout=15)
        assert det2.status_code == 200
        assert det2.json()['town'] == 'Esch'
    finally:
        # Delete
        rd = api_client.delete(f'{BASE_URL}/api/admin/events/{eid}', headers=admin_headers, timeout=15)
        assert rd.status_code == 204
        # Verify gone
        rget = api_client.get(f'{BASE_URL}/api/events/{eid}', timeout=15)
        assert rget.status_code == 404


def test_admin_update_nonexistent(api_client, admin_headers):
    r = api_client.patch(
        f'{BASE_URL}/api/admin/events/does-not-exist',
        json={'published': False},
        headers=admin_headers,
        timeout=15,
    )
    assert r.status_code == 404


def test_admin_delete_nonexistent(api_client, admin_headers):
    r = api_client.delete(f'{BASE_URL}/api/admin/events/does-not-exist', headers=admin_headers, timeout=15)
    assert r.status_code == 404
