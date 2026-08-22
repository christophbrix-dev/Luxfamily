# Sources API, robots-check, single-source run, family-fields on events
import pytest
from conftest import BASE_URL


ALLOWED_KINDS = {"ical", "data_public_lu", "html_scraper", "json_ld", "sitemap"}


# --- Events: family fields on public listing ---------------------------------
def test_events_list_has_family_fields_and_shape(api_client):
    r = api_client.get(f"{BASE_URL}/api/events?upcoming=false", timeout=20)
    assert r.status_code == 200
    events = r.json()
    assert isinstance(events, list)
    # ~56 events expected (14 deep-dive-seed + ~42 crawled + 3 legacy mock)
    assert len(events) >= 40, f"Expected >=40 events, got {len(events)}"

    required_top = {
        "title", "start_date", "image", "canton", "town", "category",
        "accessibility_wheelchair", "sensory_friendly", "free_parking",
    }
    for ev in events:
        missing = required_top - ev.keys()
        assert not missing, f"Event {ev.get('id')} missing fields: {missing}"
        # LocalizedString shape
        assert isinstance(ev["title"], dict)
        assert set(["en", "de", "fr"]).issubset(ev["title"].keys())
        # ISO date shape
        assert isinstance(ev["start_date"], str)
        assert len(ev["start_date"]) == 10 and ev["start_date"][4] == "-"
        # bool fields
        for b in ("accessibility_wheelchair", "sensory_friendly", "free_parking"):
            assert isinstance(ev[b], bool), f"{b} not bool"
        # image should be a string (URL or empty)
        assert isinstance(ev["image"], str)
        # category is list
        assert isinstance(ev["category"], list)
        # canton/town strings
        assert isinstance(ev["canton"], str) and isinstance(ev["town"], str)
        # no _id leaked
        assert "_id" not in ev


def test_events_source_names_include_deep_dive_and_crawlers(api_client):
    r = api_client.get(f"{BASE_URL}/api/events?upcoming=false", timeout=20)
    assert r.status_code == 200
    events = r.json()
    src_names = {ev.get("source_name") for ev in events if ev.get("source_name")}
    assert "deep-dive-seed" in src_names, f"deep-dive-seed missing; sources seen: {src_names}"
    # at least one crawler source (not deep-dive-seed) should be present
    crawler_names = src_names - {"deep-dive-seed"}
    assert crawler_names, f"No crawler source_name found; only saw {src_names}"


def test_deep_dive_seed_count_and_family_flags(api_client):
    r = api_client.get(f"{BASE_URL}/api/events?upcoming=false", timeout=20)
    assert r.status_code == 200
    events = r.json()
    deep_dive = [e for e in events if e.get("source_name") == "deep-dive-seed"]
    # 14 curated deep-dive family locations expected
    assert len(deep_dive) == 14, f"Expected 14 deep-dive-seed events, got {len(deep_dive)}"
    # at least one of them should have family friendly flags true
    any_wc = any(e["accessibility_wheelchair"] for e in deep_dive)
    any_sensory = any(e["sensory_friendly"] for e in deep_dive)
    any_free_p = any(e["free_parking"] for e in deep_dive)
    assert any_wc, "No deep-dive event has accessibility_wheelchair=True"
    assert any_sensory, "No deep-dive event has sensory_friendly=True"
    assert any_free_p, "No deep-dive event has free_parking=True"


def test_event_detail_localized_family_fields(api_client):
    listing = api_client.get(f"{BASE_URL}/api/events?upcoming=false", timeout=20).json()
    # prefer a deep-dive event because it has rich sensory/parking/prep tips
    target = next((e for e in listing if e.get("source_name") == "deep-dive-seed"), listing[0])
    r = api_client.get(f"{BASE_URL}/api/events/{target['id']}", timeout=15)
    assert r.status_code == 200
    body = r.json()
    for field in ("sensory_notes", "parking", "preparation_tips"):
        assert field in body, f"detail missing {field}"
        assert isinstance(body[field], dict)
        assert set(["en", "de", "fr"]).issubset(body[field].keys()), (
            f"{field} not LocalizedString: {body[field]}"
        )


# --- Admin: sources listing --------------------------------------------------
def test_admin_sources_unauth_401(api_client):
    r = api_client.get(f"{BASE_URL}/api/admin/sources", timeout=15)
    assert r.status_code == 401


def test_admin_sources_list_shape_and_count(api_client, admin_headers):
    r = api_client.get(f"{BASE_URL}/api/admin/sources", headers=admin_headers, timeout=20)
    assert r.status_code == 200
    sources = r.json()
    assert isinstance(sources, list)
    assert len(sources) == 53, f"Expected 53 sources, got {len(sources)}"
    for s in sources:
        assert "id" in s and isinstance(s["id"], str)
        assert "name" in s and s["name"]
        assert "url" in s and s["url"].startswith("http")
        assert s["kind"] in ALLOWED_KINDS, f"Unexpected kind {s['kind']} for {s['name']}"
        # status metadata fields present (may be None until run)
        for f in ("last_run_at", "last_status", "last_imported_count"):
            assert f in s, f"Source {s['name']} missing {f}"


def test_admin_sources_kinds_diversity(api_client, admin_headers):
    r = api_client.get(f"{BASE_URL}/api/admin/sources", headers=admin_headers, timeout=20)
    assert r.status_code == 200
    kinds = {s["kind"] for s in r.json()}
    # all present kinds must be within allowed set
    assert kinds.issubset(ALLOWED_KINDS)
    # sitemap and at least one other type should exist
    assert "sitemap" in kinds, f"No sitemap sources; kinds seen: {kinds}"
    assert len(kinds) >= 2, f"Only one kind of source present: {kinds}"


# --- Admin: robots-check -----------------------------------------------------
def test_robots_check_mudam_allowed(api_client, admin_headers):
    r = api_client.post(
        f"{BASE_URL}/api/admin/sources/robots-check",
        headers=admin_headers,
        json={"url": "https://www.mudam.com/programme"},
        timeout=30,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("allowed") is True, f"Mudam should be allowed: {body}"
    assert "crawl_delay_seconds" in body
    assert isinstance(body["crawl_delay_seconds"], (int, float))
    assert body.get("host") == "https://www.mudam.com"
    assert "user_agent" in body and "FamilyLuxembourgBot" in body["user_agent"]


def test_robots_check_invalid_url_returns_400(api_client, admin_headers):
    r = api_client.post(
        f"{BASE_URL}/api/admin/sources/robots-check",
        headers=admin_headers,
        json={"url": "not-a-url"},
        timeout=15,
    )
    # Non-http URL should raise inside robots_check (no scheme/netloc) => 400
    assert r.status_code == 400, f"Expected 400 for invalid URL, got {r.status_code} {r.text}"


def test_robots_check_unauth_401(api_client):
    r = api_client.post(
        f"{BASE_URL}/api/admin/sources/robots-check",
        json={"url": "https://www.mudam.com/programme"},
        timeout=15,
    )
    assert r.status_code == 401


# --- Admin: run a single small source ----------------------------------------
def _find_source(api_client, admin_headers, name_needle: str):
    sources = api_client.get(
        f"{BASE_URL}/api/admin/sources", headers=admin_headers, timeout=15
    ).json()
    for s in sources:
        if name_needle.lower() in s["name"].lower():
            return s
    return None


def test_admin_run_single_source(api_client, admin_headers):
    src = _find_source(api_client, admin_headers, "Kulturhaus Niederanven")
    # prefer the sitemap variant
    if src is None:
        pytest.skip("No Kulturhaus Niederanven source seeded")
    # get most specific: the "Sitemap" one
    sources = api_client.get(
        f"{BASE_URL}/api/admin/sources", headers=admin_headers, timeout=15
    ).json()
    sitemap_variants = [
        s for s in sources
        if "kulturhaus niederanven" in s["name"].lower() and s["kind"] == "sitemap"
    ]
    if sitemap_variants:
        src = sitemap_variants[0]

    r = api_client.post(
        f"{BASE_URL}/api/admin/sources/{src['id']}/run",
        headers=admin_headers,
        timeout=120,
    )
    assert r.status_code == 200, f"Run failed: {r.status_code} {r.text}"
    body = r.json()
    # status must be either 'ok' or 'error' — never a "stuck"/pending state
    status = body.get("last_status") or body.get("status")
    assert status in ("ok", "error"), f"Unexpected run status: {body}"

    # Verify status persisted on the source record
    updated = api_client.get(
        f"{BASE_URL}/api/admin/sources", headers=admin_headers, timeout=15
    ).json()
    updated_src = next(s for s in updated if s["id"] == src["id"])
    assert updated_src["last_status"] in ("ok", "error")
    assert updated_src["last_run_at"] is not None


def test_admin_run_missing_source_404(api_client, admin_headers):
    r = api_client.post(
        f"{BASE_URL}/api/admin/sources/does-not-exist/run",
        headers=admin_headers,
        timeout=15,
    )
    assert r.status_code == 404
