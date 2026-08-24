# Every admin route must refuse an unauthenticated caller.
#
# This enumerates the routes from the running app rather than listing them by
# hand, so a route added next year is covered the day it is added — which is
# the only way this kind of check keeps working. Reading the source with a
# regex does not: a signature spanning several lines hides the dependency, and
# the false alarms train you to ignore the result.

# Sample values for path parameters. The id never has to exist: an
# unauthenticated request must be rejected before anything is looked up, and a
# 404 here would mean the handler ran first.
PARAM_SAMPLE = {
    "event_id": "00000000-0000-0000-0000-000000000000",
    "source_id": "00000000-0000-0000-0000-000000000000",
    "partner_id": "00000000-0000-0000-0000-000000000000",
}

REJECTED = {401, 403}


def admin_routes(app):
    """(method, concrete path) for every /api/admin route the app serves."""
    out = []
    for route in app.routes:
        path = getattr(route, "path", "")
        methods = getattr(route, "methods", None)
        if not methods or not path.startswith("/api/admin"):
            continue
        concrete = path
        for name, value in PARAM_SAMPLE.items():
            concrete = concrete.replace("{" + name + "}", value)
        for method in methods:
            if method in ("HEAD", "OPTIONS"):
                continue
            out.append((method, concrete, path))
    return sorted(out)


def test_the_app_actually_has_admin_routes(app_module):
    """Guards the guard: an empty list would make every test below vacuous."""
    assert len(admin_routes(app_module.app)) >= 10


def test_no_admin_route_answers_without_a_token(app_module, client, run):
    """The one that matters. Any 2xx here is an open door."""
    unguarded = []

    async def check():
        async with client as c:
            for method, concrete, template in admin_routes(app_module.app):
                res = await c.request(method, concrete, json={})
                if res.status_code not in REJECTED:
                    unguarded.append(f"{method} {template} -> {res.status_code}")

    run(check())
    assert not unguarded, (
        "these admin routes answered an unauthenticated request:\n  "
        + "\n  ".join(unguarded)
    )


def test_a_made_up_token_is_not_enough(app_module, client, run):
    """A signature check that accepts anything shaped like a token is no check."""
    unguarded = []

    async def check():
        headers = {"Authorization": "Bearer not.a.real.token"}
        async with client as c:
            for method, concrete, template in admin_routes(app_module.app):
                res = await c.request(method, concrete, headers=headers, json={})
                if res.status_code not in REJECTED:
                    unguarded.append(f"{method} {template} -> {res.status_code}")

    run(check())
    assert not unguarded, (
        "these admin routes accepted a forged token:\n  " + "\n  ".join(unguarded)
    )
