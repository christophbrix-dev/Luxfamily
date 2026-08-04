# Verifies the personalization-bug seed additions:
# 1. MIGO is present (Wiltz canton, image from migo.lu, published)
# 2. Park Sënnesräich is present (Clervaux canton)
# 3. At least 4 northern-region events (Wiltz/Clervaux/Vianden/Diekirch)
import requests
from conftest import BASE_URL


def _fetch_events():
    r = requests.get(f"{BASE_URL}/api/events", params={"upcoming": "false"}, timeout=20)
    assert r.status_code == 200, f"GET /api/events failed: {r.status_code} {r.text[:200]}"
    data = r.json()
    assert isinstance(data, list) and len(data) > 0
    return data


def test_migo_present_in_wiltz_with_migo_lu_image():
    events = _fetch_events()
    migo = [e for e in events if "MIGO" in (e.get("title") or {}).get("en", "")]
    assert len(migo) >= 1, "MIGO not found in /api/events response"
    m = migo[0]
    assert m["canton"] == "Wiltz", f"MIGO canton wrong: {m['canton']}"
    assert m["published"] is True
    assert (m.get("image") or "").startswith("https://www.migo.lu"), (
        f"MIGO image should be scraped from migo.lu, got: {m.get('image')}"
    )
    # sanity: no leaked mongo _id
    assert "_id" not in m


def test_park_sennesraich_present_in_clervaux():
    events = _fetch_events()
    sen = [
        e for e in events
        if "Sënnesräich" in (e.get("title") or {}).get("en", "")
        and e.get("source_name") == "deep-dive-seed"
    ]
    assert len(sen) >= 1, "Park Sënnesräich (deep-dive-seed) not found"
    assert sen[0]["canton"] == "Clervaux", (
        f"Park Sënnesräich should be in Clervaux, got: {sen[0]['canton']}"
    )
    assert sen[0]["published"] is True


def test_at_least_four_northern_canton_events():
    events = _fetch_events()
    northern = {"Wiltz", "Clervaux", "Vianden", "Diekirch"}
    north_events = [e for e in events if e.get("canton") in northern]
    assert len(north_events) >= 4, (
        f"Expected >=4 events in northern cantons, got {len(north_events)}: "
        f"{[(e.get('canton'), e.get('title', {}).get('en')) for e in north_events]}"
    )
    # Confirm coverage of at least three of the four northern cantons
    cantons_present = {e["canton"] for e in north_events}
    assert len(cantons_present & northern) >= 3, (
        f"Coverage too narrow — only {cantons_present} present"
    )
