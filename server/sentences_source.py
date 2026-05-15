"""Fetch sentences.md from a remote URL with a small in-memory cache."""
from __future__ import annotations

import os
import time
import logging

import requests

from server.parser import parse_sentences

log = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 60
HTTP_TIMEOUT_SECONDS = 10

_cache: dict = {
    "sentences": [],
    "expires_at": 0.0,
}


def fetch_sentences() -> list[str]:
    now = time.time()
    if _cache["expires_at"] > now and _cache["sentences"]:
        return _cache["sentences"]

    url = os.environ.get("SENTENCES_URL")
    if not url:
        log.error("SENTENCES_URL env var is not set")
        return _cache["sentences"]

    try:
        resp = requests.get(url, timeout=HTTP_TIMEOUT_SECONDS)
        resp.raise_for_status()
        parsed = parse_sentences(resp.text)
        _cache["sentences"] = parsed
        _cache["expires_at"] = now + CACHE_TTL_SECONDS
        return parsed
    except Exception as e:
        log.warning("Failed to fetch sentences, returning cached list: %s", e)
        return _cache["sentences"]
