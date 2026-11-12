"""Free, keyless market data adapters. Standard library only.

Each adapter returns plain dicts and records where the data came from, so a
number can always be traced back to its file.
"""
from __future__ import annotations

import os
import time
import urllib.request
from pathlib import Path

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
)


class DataUnavailable(RuntimeError):
    """The source did not return usable data (holiday, not yet published, blocked)."""


def cache_dir() -> Path:
    root = os.environ.get("MARKET_SKILLS_CACHE") or str(Path.home() / ".cache" / "market-skills")
    path = Path(root)
    path.mkdir(parents=True, exist_ok=True)
    return path


def http_get(url: str, referer: str = "", timeout: int = 30) -> bytes:
    headers = {"User-Agent": USER_AGENT, "Accept": "*/*"}
    if referer:
        headers["Referer"] = referer
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read()
    except Exception as exc:  # urllib raises several unrelated types
        raise DataUnavailable(f"{url}: {exc}") from exc


def cached_get(url: str, cache_name: str, max_age_seconds: float, referer: str = "") -> bytes:
    """Fetch ``url``, reusing a cached copy younger than ``max_age_seconds``."""
    path = cache_dir() / cache_name
    if path.exists() and (time.time() - path.stat().st_mtime) < max_age_seconds:
        return path.read_bytes()
    body = http_get(url, referer)
    path.write_bytes(body)
    return body
