"""Security and correctness regressions on the API surface."""
FORGED_WEBHOOK = {
    "type": "checkout.session.completed",
    "data": {
        "object": {
            "id": "cs_forged",
            "payment_status": "paid",
            "metadata": {"event_id": "ev-1", "plan": "6months"},
            "amount_total": 22900,
        }
    },
}


def test_webhook_refuses_unsigned_payloads(app_module, client, run, monkeypatch):
    """Without a signing secret this must refuse, not trust the body.

    It once fell back to json.loads() on the raw payload, so anyone who knew the
    URL could POST themselves a paid featured slot.
    """
    monkeypatch.setattr(app_module, "STRIPE_WEBHOOK_SECRET", "")

    async def _go():
        await app_module.db.events.insert_one(
            {"id": "ev-1", "featured": False, "title": {"en": "x"}}
        )
        r = await client.post("/api/sponsor/webhook", json=FORGED_WEBHOOK)
        return r, await app_module.db.events.find_one({"id": "ev-1"})

    r, doc = run(_go())
    assert r.status_code == 503
    assert doc["featured"] is False


def test_webhook_refuses_a_bad_signature(app_module, client, run, monkeypatch):
    monkeypatch.setattr(app_module, "STRIPE_WEBHOOK_SECRET", "whsec_test")
    r = run(client.post(
        "/api/sponsor/webhook",
        json=FORGED_WEBHOOK,
        headers={"stripe-signature": "t=1,v1=deadbeef"},
    ))
    assert r.status_code == 400


def test_cors_never_pairs_wildcard_origin_with_credentials(app_module):
    """Browsers reject that pairing outright, so it was permissive and useless."""
    from starlette.middleware.cors import CORSMiddleware

    cors = [m for m in app_module.app.user_middleware if m.cls is CORSMiddleware]
    assert cors, "CORS middleware missing"
    opts = cors[0].kwargs
    assert opts["allow_credentials"] is False
    if opts["allow_origins"] == ["*"]:
        assert opts["allow_credentials"] is False
    assert "Authorization" in opts["allow_headers"]


def test_sponsor_checkout_is_rate_limited(app_module, client, run):
    """Unauthenticated and unlimited, it let anyone spam Stripe session creation.

    An invalid plan short-circuits before Stripe is contacted, but the limiter
    still counts the request — so this exercises the limit, not the payment path.
    """

    async def _go():
        codes = []
        for _ in range(12):
            r = await client.post(
                "/api/sponsor/checkout", json={"event_id": "x", "plan": "nope"}
            )
            codes.append(r.status_code)
        return codes

    codes = run(_go())
    assert 429 in codes, f"no rate limit hit in 12 requests: {sorted(set(codes))}"


def test_a_non_admin_token_is_rejected(app_module, client, run):
    async def _go():
        await app_module.db.users.insert_one(
            {"id": "u1", "email": "u@example.com", "role": "user"}
        )
        token = app_module.create_access_token("u1", "user")
        return await client.get(
            "/api/admin/events", headers={"Authorization": f"Bearer {token}"}
        )

    assert run(_go()).status_code == 403


def test_patch_can_clear_nullable_fields(app_module, client, run, admin_headers):
    """end_date and featured_until must be un-settable, not only settable."""
    now = "2026-01-01T00:00:00+00:00"

    async def _go():
        await app_module.db.events.insert_one({
            "id": "ev-1", "title": {"en": "t", "de": "t", "fr": "t"},
            "short": {"en": "s", "de": "s", "fr": "s"},
            "description": {"en": "d", "de": "d", "fr": "d"},
            "price_label": {"en": "p", "de": "p", "fr": "p"},
            "accessibility": {"en": "a", "de": "a", "fr": "a"},
            "weather_fit": {"en": "w", "de": "w", "fr": "w"},
            "canton": "Luxembourg", "town": "Lux", "start_date": "2030-01-01",
            "end_date": "2030-01-05", "featured_until": "2030-02-01",
            "lat": 49.6, "lng": 6.1, "created_at": now, "updated_at": now,
        })
        return await client.patch(
            "/api/admin/events/ev-1",
            json={"end_date": None, "featured_until": None},
            headers=admin_headers,
        )

    r = run(_go())
    assert r.status_code == 200, r.text
    assert r.json()["end_date"] is None
    assert r.json()["featured_until"] is None


def test_patch_still_rejects_an_empty_body(app_module, client, run, admin_headers):
    r = run(client.patch("/api/admin/events/whatever", json={}, headers=admin_headers))
    assert r.status_code == 400
