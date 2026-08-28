"""A failed source has to say what failed, not which category the failure is in.

Four sources failed in Emergent's environment and worked from here, and all
anyone had to go on was the single word "ConnectError". That is not a
diagnosis: a refused connection, an expired certificate and a DNS failure all
arrive under that name and have three different fixes.

The reason is that httpx wraps everything below the HTTP layer, and creates the
wrapper with an empty message — `str(exc)` returns "". The actual cause sits one
or two links down the `__cause__` chain, where `raise ... from` put it.

`last_error` on the source record is usually the only thing anyone ever reads
about a broken source, so it is worth the few lines.
"""
import ssl

import pytest

from crawler_utils import MAX_CAUSE_DEPTH, _build_entry, describe_exception


def _chain(*exceptions):
    """Link exceptions the way `raise ... from` does, outermost returned."""
    outer = exceptions[0]
    current = outer
    for nxt in exceptions[1:]:
        current.__cause__ = nxt
        current = nxt
    return outer


class TestTheEmptyWrapper:
    def test_the_case_that_started_this(self):
        """httpx.ConnectError carrying nothing, over a real reason."""
        import httpx

        exc = _chain(
            httpx.ConnectError(""),
            ConnectionResetError(104, "Connection reset by peer"),
        )
        described = describe_exception(exc)
        assert described.startswith("ConnectError")
        assert "Connection reset by peer" in described

    def test_a_certificate_problem_is_named_as_one(self):
        import httpx

        exc = _chain(
            httpx.ConnectError(""),
            ssl.SSLCertVerificationError("certificate verify failed"),
        )
        assert "certificate verify failed" in describe_exception(exc)

    def test_a_name_lookup_failure_is_named_as_one(self):
        import httpx

        exc = _chain(httpx.ConnectError(""), OSError("Name or service not known"))
        assert "Name or service not known" in describe_exception(exc)

    def test_the_three_do_not_read_alike(self):
        """The whole point: three causes, three different lines."""
        import httpx

        lines = {
            describe_exception(_chain(httpx.ConnectError(""), cause))
            for cause in (
                ConnectionResetError(104, "Connection reset by peer"),
                ssl.SSLCertVerificationError("certificate verify failed"),
                OSError("Name or service not known"),
            )
        }
        assert len(lines) == 3


class TestTheOrdinaryCases:
    def test_an_exception_with_a_message_keeps_it(self):
        assert describe_exception(ValueError("bad date")) == "ValueError: bad date"

    def test_an_exception_without_one_still_names_its_type(self):
        assert describe_exception(RuntimeError()) == "RuntimeError"

    def test_a_long_chain_is_cut_off(self):
        exc = _chain(*[ValueError(f"level {i}") for i in range(10)])
        assert describe_exception(exc).count("→") == MAX_CAUSE_DEPTH - 1

    def test_a_loop_does_not_hang(self):
        a, b = ValueError("a"), ValueError("b")
        a.__cause__, b.__cause__ = b, a
        assert "ValueError: a" in describe_exception(a)


class TestWhatTheSourceRecordEndsUpSaying:
    def test_an_unreadable_robots_txt_carries_the_reason(self):
        import httpx

        exc = _chain(
            httpx.ConnectError(""),
            ConnectionResetError(104, "Connection reset by peer"),
        )
        entry = _build_entry("https://example.invalid", None, None, exc)
        assert entry.unreadable is not None
        assert "Connection reset by peer" in entry.unreadable

    def test_it_is_still_the_distinction_that_matters(self):
        """Unreadable and disallowed stay two different things.

        A 5xx or a network error means the rules exist and we could not read
        them, so the host is treated as disallowed — but the message has to say
        which of the two it was, because one is the site's decision and the
        other is our problem.
        """
        unreadable = _build_entry("https://example.invalid", 503, None, None)
        assert unreadable.unreadable == "HTTP 503"

        missing = _build_entry("https://example.invalid", 404, None, None)
        assert missing.unreadable is None, "404 means no rules, not a failure"

    @pytest.mark.parametrize("status", [200, 404, 410])
    def test_a_readable_answer_is_never_marked_unreadable(self, status):
        entry = _build_entry("https://example.invalid", status, "User-agent: *\n", None)
        assert entry.unreadable is None
