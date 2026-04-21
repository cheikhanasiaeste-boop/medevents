"""HTTP fetch + content-hash helper.

Separate from parsers so listing/detail logic stays pure and testable against raw bytes.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

import httpx

from .parsers.base import FetchedContent


class FetchError(RuntimeError):
    """Raised when fetch returns a non-2xx status."""


def fetch_url(url: str, *, client: httpx.Client, user_agent: str) -> FetchedContent:
    """Perform one GET and return its body + sha-256 content hash.

    Raises FetchError on non-2xx responses so the caller can write a fetch_status='error'
    row on source_pages and (optionally) a source_blocked review item.
    """
    resp = client.get(url, headers={"user-agent": user_agent}, follow_redirects=True)
    if resp.status_code < 200 or resp.status_code >= 300:
        raise FetchError(f"GET {url} returned {resp.status_code}")
    body = resp.content
    return FetchedContent(
        url=str(resp.url),
        status_code=resp.status_code,
        content_type=resp.headers.get("content-type", ""),
        body=body,
        fetched_at=datetime.now(UTC),
        content_hash=hashlib.sha256(body).hexdigest(),
    )


def make_default_client(*, timeout_seconds: float = 15.0) -> httpx.Client:
    """Convenience factory used by the pipeline when no injected client is provided."""
    return httpx.Client(timeout=timeout_seconds)
