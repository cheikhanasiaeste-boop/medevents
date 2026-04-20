"""Tests for fetch.fetch_url against httpx's MockTransport."""

from __future__ import annotations

import hashlib

import httpx
import pytest
from medevents_ingest.fetch import FetchError, fetch_url


def _make_client(
    body: bytes, status: int = 200, ctype: str = "text/html; charset=utf-8"
) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, headers={"content-type": ctype}, content=body)

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_fetch_url_returns_content_and_sha256_hash() -> None:
    body = b"<html><body>hello</body></html>"
    expected_hash = hashlib.sha256(body).hexdigest()
    with _make_client(body) as client:
        result = fetch_url("https://ex.test/a", client=client, user_agent="ua")
    assert result.status_code == 200
    assert result.body == body
    assert result.content_hash == expected_hash
    assert result.content_type.startswith("text/html")


def test_fetch_url_raises_on_non_2xx() -> None:
    with _make_client(b"oops", status=500) as client, pytest.raises(FetchError, match="500"):
        fetch_url("https://ex.test/a", client=client, user_agent="ua")


def test_fetch_url_passes_user_agent() -> None:
    captured: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request.headers.get("user-agent", ""))
        return httpx.Response(200, headers={"content-type": "text/html"}, content=b"ok")

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        fetch_url("https://ex.test/a", client=client, user_agent="medevents/0.1")
    assert "medevents/0.1" in captured[0]
