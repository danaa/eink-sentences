"""Fetch sentences from a remote URL with a small in-memory cache.

Supports multiple named sources (e.g. the main sentence list and a separate
morning-routine list), each with its own URL and cache entry.
"""
from __future__ import annotations

import os
import time
import logging

import requests

from server.parser import parse_sentences

log = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 60
HTTP_TIMEOUT_SECONDS = 10

# Per-URL cache. Each entry: {"sentences": list[str], "expires_at": float}.
# We keep the original `_cache` name as the default for the main list so
# existing tests that touch the module's internal state keep working.
_cache: dict = {"sentences": [], "expires_at": 0.0}
_morning_cache: dict = {"sentences": [], "expires_at": 0.0}


def _fetch_to_cache(url: str | None, cache: dict) -> list[str]:
    """Generic fetch with cache. Falls back to cached list on failure."""
    now = time.time()
    if cache["expires_at"] > now and cache["sentences"]:
        return cache["sentences"]

    if not url:
        log.error("URL is empty")
        return cache["sentences"]

    try:
        resp = requests.get(url, timeout=HTTP_TIMEOUT_SECONDS)
        resp.raise_for_status()
        parsed = parse_sentences(resp.text)
        cache["sentences"] = parsed
        cache["expires_at"] = now + CACHE_TTL_SECONDS
        return parsed
    except Exception as e:
        log.warning("Fetch failed for %s, returning cached list: %s", url, e)
        return cache["sentences"]


def fetch_sentences() -> list[str]:
    return _fetch_to_cache(os.environ.get("SENTENCES_URL"), _cache)


def _morning_url() -> str:
    """Derive the morning.md URL by swapping the filename in SENTENCES_URL.

    Avoids requiring a second env var on Render. If SENTENCES_URL points at
    `…/sentences.md`, the morning list is fetched from `…/morning.md`
    alongside it.
    """
    s = os.environ.get("SENTENCES_URL", "")
    if s.endswith("sentences.md"):
        return s[: -len("sentences.md")] + "morning.md"
    return ""


def fetch_morning_sentences() -> list[str]:
    return _fetch_to_cache(_morning_url(), _morning_cache)
