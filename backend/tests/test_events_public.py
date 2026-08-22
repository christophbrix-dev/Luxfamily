# Public events listing & detail
from conftest import BASE_URL


def test_events_list_default_upcoming(api_client):
    r = api_client.get(f'{BASE_URL}/api/events', timeout=15)
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    # All must be published; no _id leaked
    for ev in data:
        assert ev.get('published') is True
        assert '_id' not in ev
        assert 'id' in ev
        assert 'title' in ev and 'en' in ev['title']


def test_events_list_upcoming_false(api_client):
    r = api_client.get(f'{BASE_URL}/api/events', params={'upcoming': 'false'}, timeout=15)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_event_detail_404(api_client):
    r = api_client.get(f'{BASE_URL}/api/events/does-not-exist', timeout=15)
    assert r.status_code == 404


def test_event_detail_existing(api_client):
    listing = api_client.get(f'{BASE_URL}/api/events', params={'upcoming': 'false'}, timeout=15).json()
    if not listing:
        return  # nothing to test against
    target = listing[0]
    r = api_client.get(f'{BASE_URL}/api/events/{target["id"]}', timeout=15)
    assert r.status_code == 200
    body = r.json()
    assert body['id'] == target['id']
    assert body['published'] is True
