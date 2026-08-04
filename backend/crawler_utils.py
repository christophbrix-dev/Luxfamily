"""Polite-crawling helpers: robots.txt compliance + per-host rate limiting.

Every outgoing HTTP request made by the importers goes through :func:`polite_get`
which:

1. Fetches (and caches) the target host's ``robots.txt`` and asks
   ``urllib.robotparser`` whether our User-Agent is allowed to hit the URL.
2. Waits ``max(Crawl-delay, MIN_DELAY_SECONDS)`` between two requests to the
   same host so we never hammer a small municipal site.

If ``robots.txt`` disallows the URL, a :class:`RobotsBlocked` exception is
raised so the importer marks the source as blocked (never retries silently).
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Dict, Optional
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx

logger = logging.getLogger("lux-backend.crawler")

USER_AGENT = (
    "Mozilla/5.0 (compatible; FamilyLuxembourgBot/1.0; "
    "+https://familyluxembourg.lu/bot) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)
MIN_DELAY_SECONDS = 2.0  # baseline politeness delay between hits to the same host
ROBOTS_CACHE_TTL_SECONDS = 60 * 60 * 6  # re-fetch robots.txt every 6h


class RobotsBlocked(Exception):
    """Raised when robots.txt disallows the target URL."""


class _RobotsEntry:
    __slots__ = ("parser", "crawl_delay", "fetched_at")

    def __init__(self, parser: RobotFileParser, crawl_delay: float, fetched_at: float) -> None:
        self.parser = parser
        self.crawl_delay = crawl_delay
        self.fetched_at = fetched_at


_robots_cache: Dict[str, _RobotsEntry] = {}
_last_hit: Dict[str, float] = {}
_host_locks: Dict[str, asyncio.Lock] = {}


def _host_of(url: str) -> str:
    p = urlparse(url)
    return f"{p.scheme}://{p.netloc}"


async def _load_robots(host: str) -> _RobotsEntry:
    now = time.monotonic()
    entry = _robots_cache.get(host)
    if entry and (now - entry.fetched_at) < ROBOTS_CACHE_TTL_SECONDS:
        return entry

    robots_url = host.rstrip("/") + "/robots.txt"
    parser = RobotFileParser()
    parser.set_url(robots_url)

    try:
        async with httpx.AsyncClient(
            timeout=10.0, follow_redirects=True, headers={"User-Agent": USER_AGENT}
        ) as cli:
            resp = await cli.get(robots_url)
        if resp.status_code == 200 and resp.text.strip():
            parser.parse(resp.text.splitlines())
            logger.info("robots.txt loaded for %s (%d bytes)", host, len(resp.text))
        else:
            # No robots.txt => everything allowed by convention.
            parser.parse([])
            logger.info("robots.txt not present for %s (status %s) — assuming allow-all",
                        host, resp.status_code)
    except Exception as exc:
        logger.warning("robots.txt fetch failed for %s (%s) — assuming allow-all",
                       host, exc)
        parser.parse([])

    # `crawl_delay` returns None if not specified.
    delay = parser.crawl_delay(USER_AGENT) or parser.crawl_delay("*") or 0.0
    entry = _RobotsEntry(parser=parser, crawl_delay=float(delay), fetched_at=now)
    _robots_cache[host] = entry
    return entry


async def _throttle(host: str, crawl_delay: float) -> None:
    """Sleep until at least ``max(MIN_DELAY_SECONDS, crawl_delay)`` has passed
    since the previous request to ``host``."""
    delay = max(MIN_DELAY_SECONDS, crawl_delay)
    lock = _host_locks.setdefault(host, asyncio.Lock())
    async with lock:
        last = _last_hit.get(host, 0.0)
        now = time.monotonic()
        wait = (last + delay) - now
        if wait > 0:
            await asyncio.sleep(wait)
        _last_hit[host] = time.monotonic()


async def polite_get(
    url: str,
    *,
    timeout: float = 30.0,
    extra_headers: Optional[Dict[str, str]] = None,
) -> httpx.Response:
    """GET a URL after checking robots.txt and applying rate limiting.

    Raises :class:`RobotsBlocked` if the URL is disallowed.
    """
    host = _host_of(url)
    entry = await _load_robots(host)

    if not entry.parser.can_fetch(USER_AGENT, url):
        raise RobotsBlocked(f"robots.txt disallows {url} for {USER_AGENT}")

    await _throttle(host, entry.crawl_delay)

    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en,de;q=0.9,fr;q=0.8,lb;q=0.7",
    }
    if extra_headers:
        headers.update(extra_headers)

    async with httpx.AsyncClient(
        timeout=timeout, follow_redirects=True, headers=headers
    ) as cli:
        resp = await cli.get(url)
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
        "applied_min_delay_seconds": MIN_DELAY_SECONDS,
    }
