"""Two different refusals that used to read as the same one.

A crawl is refused both when robots.txt says no and when robots.txt could not
be read at all. Refusing in the second case is deliberate and correct — RFC
9309 says an unreadable robots.txt means "stay out", and assuming otherwise
would be exactly backwards for a server already returning errors.

But both raised "robots.txt disallows <url>", and for utopolis.lu and
kulturkanner.lu that was untrue: those domains no longer resolve, so there is
no robots.txt and no rule. The message sent a reader looking for a rule that
does not exist, in a file that cannot be fetched.

The two need different answers. A site that forbids us has to be dropped from
the source list. A domain that no longer resolves has to be corrected.
"""
import pytest

from crawler_utils import RobotsBlocked, _build_entry, _check_allowed


def entry_for_unreachable(error):
    return _build_entry("https://dead.lu", None, None, error)


class TestUnreadable:
    def test_dns_failure_does_not_claim_a_rule_exists(self):
        e = entry_for_unreachable(OSError(8, "nodename nor servname provided"))
        with pytest.raises(RobotsBlocked) as exc:
            _check_allowed(e, "https://dead.lu/sitemap.xml")
        message = str(exc.value)
        assert "could not read robots.txt" in message
        assert "disallows" not in message

    def test_it_carries_the_underlying_cause(self):
        e = entry_for_unreachable(OSError(8, "nodename nor servname provided"))
        with pytest.raises(RobotsBlocked, match="nodename"):
            _check_allowed(e, "https://dead.lu/x")

    def test_it_says_the_site_may_be_fine(self):
        """So the reader checks the address instead of accepting a refusal."""
        e = entry_for_unreachable(OSError("boom"))
        with pytest.raises(RobotsBlocked, match="check the address"):
            _check_allowed(e, "https://dead.lu/x")

    def test_a_server_error_is_also_unreadable(self):
        e = _build_entry("https://broken.lu", 503, None, None)
        with pytest.raises(RobotsBlocked, match="could not read robots.txt"):
            _check_allowed(e, "https://broken.lu/x")

    def test_an_empty_error_still_gives_a_cause(self):
        """mnha.lu logged an empty reason, which explains nothing."""
        e = entry_for_unreachable(OSError())
        with pytest.raises(RobotsBlocked) as exc:
            _check_allowed(e, "https://dead.lu/x")
        assert "()" not in str(exc.value)
        assert "OSError" in str(exc.value)


class TestActuallyForbidden:
    def test_a_real_rule_still_reads_as_one(self):
        e = _build_entry("https://x.lu", 200, "User-agent: *\nDisallow: /\n", None)
        with pytest.raises(RobotsBlocked, match="robots.txt disallows"):
            _check_allowed(e, "https://x.lu/anything")

    def test_an_allowed_path_passes(self):
        e = _build_entry("https://x.lu", 200, "User-agent: *\nDisallow: /admin\n", None)
        _check_allowed(e, "https://x.lu/events")     # must not raise

    def test_a_missing_robots_txt_allows_everything(self):
        """404 means no rules exist — that is not the same as unreadable."""
        e = _build_entry("https://x.lu", 404, "", None)
        _check_allowed(e, "https://x.lu/anything")   # must not raise
