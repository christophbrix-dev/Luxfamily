"""robots.txt handling — the rules a polite crawler has to get right."""
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

import crawler_utils as cu  # noqa: E402

# The real rules kids-in-lux.com serves.
KIDS_IN_LUX = """User-agent: *
Disallow: /app/
Disallow: /j/
Crawl-Delay: 5
"""

# A site addressing our bot by name, while shutting everyone else out.
ADDRESSED_TO_US = """User-agent: FamilyLuxembourgBot
Crawl-Delay: 30
Allow: /

User-agent: *
Disallow: /
"""


def entry(status=200, text="", error=None, host="https://example.lu"):
    return cu._build_entry(host, status, text, error)


def test_user_agent_can_be_addressed_by_name():
    """robotparser only sees the token before the first slash.

    While the agent string began with "Mozilla/5.0" it was read as "mozilla",
    so an Allow or a Crawl-delay written for our bot never applied.
    """
    assert cu.USER_AGENT.split("/")[0].lower() == "familyluxembourgbot"


def test_rules_addressed_to_us_are_obeyed():
    e = entry(text=ADDRESSED_TO_US)
    assert e.parser.can_fetch(cu.USER_AGENT, "https://example.lu/events") is True
    assert e.crawl_delay == 30.0


def test_disallowed_paths_are_refused():
    e = entry(text=KIDS_IN_LUX)
    assert e.parser.can_fetch(cu.USER_AGENT, "https://example.lu/spielplaetze/") is True
    assert e.parser.can_fetch(cu.USER_AGENT, "https://example.lu/app/x") is False


def test_crawl_delay_is_honoured():
    assert entry(text=KIDS_IN_LUX).crawl_delay == 5.0


def test_missing_robots_allows_everything():
    """404 means no rules exist, which by convention permits crawling."""
    e = entry(status=404, text="")
    assert e.parser.can_fetch(cu.USER_AGENT, "https://example.lu/a") is True


def test_server_error_disallows_everything():
    """RFC 9309: a 5xx means the rules exist but could not be read.

    Assuming "allowed" is backwards — a host returning errors is the last one
    that should be crawled.
    """
    e = entry(status=503, text=None, host="https://broken.lu")
    assert e.parser.can_fetch(cu.USER_AGENT, "https://broken.lu/a") is False


def test_network_failure_disallows_everything():
    e = entry(status=None, text=None, error=OSError("timeout"), host="https://gone.lu")
    assert e.parser.can_fetch(cu.USER_AGENT, "https://gone.lu/a") is False


def test_failed_fetch_is_retried_sooner_than_a_good_one():
    good = entry(text=KIDS_IN_LUX, host="https://ok.lu")
    bad = entry(status=503, text=None, host="https://bad.lu")
    assert bad.ttl < good.ttl


def test_requests_to_one_host_queue_behind_each_other():
    """Slots are reserved under the lock and waited on outside it.

    The previous version measured every caller against the same timestamp while
    holding a lock across the sleep.
    """
    cu._next_free.pop("https://queue.lu", None)
    waits = [cu._reserve_slot("https://queue.lu", 5.0) for _ in range(3)]
    assert waits[0] == 0
    assert round(waits[1]) == 5
    assert round(waits[2]) == 10


def test_baseline_delay_applies_when_the_site_asks_for_none():
    cu._next_free.pop("https://nodelay.lu", None)
    cu._reserve_slot("https://nodelay.lu", 0.0)
    assert round(cu._reserve_slot("https://nodelay.lu", 0.0)) == round(cu.MIN_DELAY_SECONDS)


def test_the_crawlers_go_through_the_politeness_layer():
    """Both hand-written crawlers claimed to respect robots.txt but never read it."""
    for name in ("kids_in_lux", "visit_luxembourg"):
        src = (BACKEND / "crawlers" / f"{name}.py").read_text()
        assert "polite_get_sync" in src, f"{name} bypasses the politeness layer"
        assert "client.get(url" not in src, f"{name} still fetches directly"


def test_one_identity_for_every_outgoing_request():
    """Three different bot names with three different contact domains meant a
    site operator could not tell who was calling, nor reach anyone."""
    offenders = []
    for path in BACKEND.rglob("*.py"):
        if path.name == "crawler_utils.py" or "tests" in path.parts:
            continue
        for line in path.read_text().splitlines():
            if line.startswith("USER_AGENT") and "crawler_utils" not in line:
                offenders.append(f"{path.name}: {line.strip()}")
    assert not offenders, "define the agent once in crawler_utils: " + "; ".join(offenders)
