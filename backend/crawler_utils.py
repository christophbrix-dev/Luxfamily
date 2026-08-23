"""Polite-crawling helpers: robots.txt compliance + per-host rate limiting.

Every outgoing HTTP request made by the importers and the hand-written crawlers
goes through :func:`polite_get` (async) or :func:`polite_get_sync` (blocking),
which both:

1. Fetch (and cache) the target host's ``robots.txt`` and ask
   ``urllib.robotparser`` whether our User-Agent may hit the URL.
2. Wait ``max(MIN_DELAY_SECONDS, Crawl-delay)`` between two requests to the same
   host, so we never hammer a small municipal site.

If ``robots.txt`` disallows the URL, :class:`RobotsBlocked` is raised so the
caller marks the source as blocked rather than retrying silently.

Both entry points share one robots cache and one rate-limit clock, so a
synchronous crawler and an async importer hitting the same host still queue
behind each other.
"""
from __future__ import annotations

import asyncio
import logging
import threading
import time
from typing import Dict, Optional
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx

logger = logging.getLogger("lux-backend.crawler")

# One identity for every outgoing request in this project.
#
# The product name comes first on purpose. urllib.robotparser matches a
# robots.txt `User-agent:` line against everything before the first "/" in this
# string: a value starting with "Mozilla/5.0" is only ever seen as "mozilla", so
# any rule addressed to us by name — an Allow, or a Crawl-delay — was silently
# invisible. Nor do we claim to be Chrome; a site that wants to treat bots
# differently is entitled to recognise one.
USER_AGENT = "FamilyLuxembourgBot/1.0 (+https://familyluxembourg.lu/bot)"

MIN_DELAY_SECONDS = 2.0  # baseline politeness delay between hits to the same host
ROBOTS_CACHE_TTL_SECONDS = 60 * 60 * 6  # re-fetch robots.txt every 6h
ROBOTS_ERROR_TTL_SECONDS = 60 * 10  # retry sooner after a failed fetch

ACCEPT_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en,de;q=0.9,fr;q=0.8,lb;q=0.7",
}


class RobotsBlocked(Exception):
    """Raised when robots.txt disallows the target URL, or could not be read."""


class _RobotsEntry:
    __slots__ = ("parser", "crawl_delay", "fetched_at", "ttl")

    def __init__(self, parser: RobotFileParser, crawl_delay: float,
                 fetched_at: float, ttl: float) -> None:
        self.parser = parser
        self.crawl_delay = crawl_delay
        self.fetched_at = fetched_at
        self.ttl = ttl


_robots_cache: Dict[str, _RobotsEntry] = {}
# Next moment a request to a host may start. Reserving a slot under the lock and
# sleeping outside it keeps the async path from blocking the event loop, and
# lets sync and async callers share one queue.
_next_free: Dict[str, float] = {}
_state_lock = threading.Lock()


def _host_of(url: str) -> str:
    p = urlparse(url)
    return f"{p.scheme}://{p.netloc}"


def _cached(host: str) -> Optional[_RobotsEntry]:
    with _state_lock:
        entry = _robots_cache.get(host)
        if entry and (time.monotonic() - entry.fetched_at) < entry.ttl:
            return entry
    return None


def _build_entry(host: str, status: Optional[int], text: Optional[str],
                 error: Optional[BaseException]) -> _RobotsEntry:
    """Turn one robots.txt fetch result into a cache entry.

    Follows RFC 9309 on what a failed fetch means:

    * 2xx with content — obey it.
    * 4xx, including the common 404 — no rules exist, everything is allowed.
    * 5xx or a network error — the rules exist but we could not read them, so
      treat the host as fully disallowed until the next attempt. Assuming
      "allowed" here is exactly backwards: a server returning errors is the
      last one that should be crawled.
    """
    parser = RobotFileParser()
    parser.set_url(host.rstrip("/") + "/robots.txt")
    ttl = ROBOTS_CACHE_TTL_SECONDS

    if error is not None or (status is not None and status >= 500):
        parser.disallow_all = True
        ttl = ROBOTS_ERROR_TTL_SECONDS
        logger.warning(
            "robots.txt unreadable for %s (%s) — treating host as disallowed until retry",
            host, error if error is not None else f"HTTP {status}",
        )
    elif status == 200 and text and text.strip():
        parser.parse(text.splitlines())
        logger.info("robots.txt loaded for %s (%d bytes)", host, len(text))
    else:
        parser.parse([])
        logger.info("no robots.txt for %s (HTTP %s) — everything allowed", host, status)

    delay = parser.crawl_delay(USER_AGENT) or parser.crawl_delay("*") or 0.0
    entry = _RobotsEntry(parser, float(delay), time.monotonic(), ttl)
    with _state_lock:
        _robots_cache[host] = entry
    if delay:
        logger.info("%s asks for a %.0fs crawl delay", host, float(delay))
    return entry


async def _load_robots(host: str) -> _RobotsEntry:
    entry = _cached(host)
    if entry:
        return entry
    robots_url = host.rstrip("/") + "/robots.txt"
    try:
        async with httpx.AsyncClient(
            timeout=10.0, follow_redirects=True, headers={"User-Agent": USER_AGENT}
        ) as cli:
            resp = await cli.get(robots_url)
        return _build_entry(host, resp.status_code, resp.text, None)
    except Exception as exc:
        return _build_entry(host, None, None, exc)


def _load_robots_sync(host: str) -> _RobotsEntry:
    entry = _cached(host)
    if entry:
        return entry
    robots_url = host.rstrip("/") + "/robots.txt"
    try:
        with httpx.Client(
            timeout=10.0, follow_redirects=True, headers={"User-Agent": USER_AGENT}
        ) as cli:
            resp = cli.get(robots_url)
        return _build_entry(host, resp.status_code, resp.text, None)
    except Exception as exc:
        return _build_entry(host, None, None, exc)


def _reserve_slot(host: str, crawl_delay: float) -> float:
    """Claim the next request slot for ``host``; return the seconds to wait.

    The reservation happens under the lock, the waiting outside it. That way an
    async caller never blocks the event loop, and several callers queue in order
    instead of all measuring against the same stale timestamp.
    """
    delay = max(MIN_DELAY_SECONDS, crawl_delay)
    with _state_lock:
        now = time.monotonic()
        start_at = max(now, _next_free.get(host, 0.0))
        _next_free[host] = start_at + delay
        return start_at - now


def _check_allowed(entry: _RobotsEntry, url: str) -> None:
    if not entry.parser.can_fetch(USER_AGENT, url):
        raise RobotsBlocked(f"robots.txt disallows {url} for {USER_AGENT}")


async def polite_get(
    url: str,
    *,
    timeout: float = 30.0,
    extra_headers: Optional[Dict[str, str]] = None,
) -> httpx.Response:
    """GET a URL after checking robots.txt and applying rate limiting."""
    host = _host_of(url)
    entry = await _load_robots(host)
    _check_allowed(entry, url)

    wait = _reserve_slot(host, entry.crawl_delay)
    if wait > 0:
        await asyncio.sleep(wait)

    headers = dict(ACCEPT_HEADERS)
    if extra_headers:
        headers.update(extra_headers)
    async with httpx.AsyncClient(
        timeout=timeout, follow_redirects=True, headers=headers
    ) as cli:
        resp = await cli.get(url)
        resp.raise_for_status()
        return resp


def polite_get_sync(
    url: str,
    *,
    client: Optional[httpx.Client] = None,
    timeout: float = 30.0,
    extra_headers: Optional[Dict[str, str]] = None,
) -> httpx.Response:
    """Blocking counterpart of :func:`polite_get`, for the hand-written crawlers.

    They run as synchronous code inside a worker thread, so they cannot await.
    Sharing the cache and the rate-limit clock with the async path means the two
    still take turns per host.
    """
    host = _host_of(url)
    entry = _load_robots_sync(host)
    _check_allowed(entry, url)

    wait = _reserve_slot(host, entry.crawl_delay)
    if wait > 0:
        time.sleep(wait)

    headers = dict(ACCEPT_HEADERS)
    if extra_headers:
        headers.update(extra_headers)
    if client is not None:
        resp = client.get(url, timeout=timeout, follow_redirects=True, headers=headers)
    else:
        with httpx.Client(timeout=timeout, follow_redirects=True, headers=headers) as own:
            resp = own.get(url)
    resp.raise_for_status()
    return resp


async def robots_check(url: str) -> Dict[str, object]:
    """Diagnostic helper: report whether the URL is allowed and what the delay is."""
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError(f"malformed URL {url!r}: missing scheme or host")
    host = _host_of(url)
    entry = await _load_robots(host)
    return {
        "url": url,
        "host": host,
        "user_agent": USER_AGENT,
        "allowed": entry.parser.can_fetch(USER_AGENT, url),
        "crawl_delay_seconds": entry.crawl_delay,
        "applied_delay_seconds": max(MIN_DELAY_SECONDS, entry.crawl_delay),
    }
