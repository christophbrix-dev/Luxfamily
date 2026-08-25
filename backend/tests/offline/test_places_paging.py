# Paging the places list.
#
# There are 8,354 places in the collection and this endpoint could return at
# most 200 of them, with no way to ask for the next ones. Nothing errored: the
# app showed a first page and there was simply no more to be had, which reads
# like "that is all there is".

import pytest


@pytest.fixture
def seeded(app_module, run):
    """40 places with deliberately repeated scores.

    The repeats are the point: with a single-key sort, equally scored rows have
    no defined order, and paging then drops some and repeats others.
    """
    async def fill():
        await app_module.db.places.delete_many({})
        await app_module.db.places.insert_many([
            {
                "id": f"node/{i}",
                "name": f"Plaz {i:03d}",
                "kind": "playground",
                "group": "play",
                "lat": 49.6 + i / 1000,
                "lng": 6.1 + i / 1000,
                "family_score": 50 + (i % 4) * 10,   # only four distinct scores
                "tags_raw": {"leisure": "playground"},
            }
            for i in range(40)
        ])
    run(fill())
    return app_module


def fetch(client, run, *queries):
    """All the requests a test needs, in one client session.

    The client fixture is handed over un-entered and a closed httpx client
    cannot be reopened, so a helper that entered it per call worked only for
    tests making exactly one request.
    """
    async def call():
        out = []
        async with client as c:
            for q in queries:
                out.append(await c.get(f"/api/places?{q}"))
        return out
    return run(call())


def get(client, run, query):
    return fetch(client, run, query)[0]


def ids(res):
    return [r["id"] for r in res.json()]


class TestPaging:
    def test_a_second_page_exists(self, seeded, client, run):
        second = get(client, run, "limit=10&skip=10")
        assert second.status_code == 200
        assert len(second.json()) == 10

    def test_pages_do_not_overlap(self, seeded, client, run):
        a, b = fetch(client, run, "limit=10&skip=0", "limit=10&skip=10")
        first, second = ids(a), ids(b)
        assert not set(first) & set(second)

    def test_paging_reaches_every_place(self, seeded, client, run):
        """The failure this is really about: 40 rows, all of them reachable."""
        pages = fetch(client, run, *[f"limit=10&skip={s}" for s in range(0, 40, 10)])
        seen = [i for page in pages for i in ids(page)]
        assert len(seen) == 40
        assert len(set(seen)) == 40

    def test_past_the_end_is_empty_not_an_error(self, seeded, client, run):
        res = get(client, run, "limit=10&skip=999")
        assert res.status_code == 200
        assert res.json() == []

    def test_a_negative_skip_is_treated_as_none(self, seeded, client, run):
        a, b = fetch(client, run, "limit=5&skip=-5", "limit=5")
        assert ids(a) == ids(b)


class TestOrderIsStable:
    def test_the_same_page_twice_is_the_same_page(self, seeded, client, run):
        a, b = fetch(client, run, "limit=10&skip=10", "limit=10&skip=10")
        assert ids(a) == ids(b)

    def test_higher_scores_still_come_first(self, seeded, client, run):
        scores = [r["family_score"] for r in get(client, run, "limit=40").json()]
        assert scores == sorted(scores, reverse=True)


class TestFiltersStillApply:
    def test_group_filter_survives_paging(self, seeded, client, run):
        async def add():
            await seeded.db.places.insert_one({
                "id": "node/999", "name": "Séi", "kind": "lake", "group": "nature",
                "lat": 49.8, "lng": 6.4, "family_score": 99,
            })
        run(add())
        rows = get(client, run, "group=nature&limit=10").json()
        assert [r["id"] for r in rows] == ["node/999"]
