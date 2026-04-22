"""Source-run bookkeeping tests for pipeline.run_source().

Three DB-gated integration tests cover the success path, the error path, and
the error-persists-across-success invariant. One signature smoke test locks
the `force: bool` keyword-only parameter so W3.2b can rely on it.

Uses the same TEST_DATABASE_URL + _alias_test_database_url discipline as
test_gnydm_pipeline.py — never point TEST_DATABASE_URL at the dev DB.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from medevents_ingest import db as _db
from medevents_ingest.db import session_scope
from medevents_ingest.models import SourceSeed
from medevents_ingest.parsers import parser_for, registered_parser_names
from medevents_ingest.parsers.base import FetchedContent, SourcePageRef
from medevents_ingest.pipeline import run_source
from medevents_ingest.repositories.sources import upsert_source_seed
from sqlalchemy import text

pytestmark = pytest.mark.skipif(
    "TEST_DATABASE_URL" not in os.environ,
    reason="TEST_DATABASE_URL not set; skipping integration tests",
)

FIXTURES = Path(__file__).parent / "fixtures" / "gnydm"
LISTING_URL = "https://www.gnydm.com/about/future-meetings/"
HOMEPAGE_URL = "https://www.gnydm.com/"


@pytest.fixture(autouse=True)
def _alias_test_database_url(
    _no_env_pollution: None,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[None]:
    """Same ordering + cache-reset discipline as test_gnydm_pipeline.py.

    See that module's docstring for the rationale — in short: force conftest
    scrubber ordering, reset db._engine/_SessionLocal at setup AND teardown,
    never let a test-DB-bound engine leak to the next test.
    """
    monkeypatch.setenv("DATABASE_URL", os.environ["TEST_DATABASE_URL"])
    _db._engine = None
    _db._SessionLocal = None
    try:
        yield
    finally:
        _db._engine = None
        _db._SessionLocal = None


@pytest.fixture(autouse=True)
def _ensure_gnydm_registered() -> None:
    if "gnydm_listing" not in registered_parser_names():
        import importlib

        import medevents_ingest.parsers.gnydm as _gnydm_mod

        importlib.reload(_gnydm_mod)


@pytest.fixture(autouse=True)
def _clean_db() -> None:
    with session_scope() as s:
        s.execute(
            text(
                "TRUNCATE audit_log, event_sources, review_items, events, "
                "source_pages, sources RESTART IDENTITY CASCADE"
            )
        )


def _seed_gnydm(session: Any) -> None:
    upsert_source_seed(
        session,
        SourceSeed(
            code="gnydm",
            name="Greater New York Dental Meeting",
            homepage_url="https://www.gnydm.com/",
            source_type="society",
            country_iso="US",
            parser_name="gnydm_listing",
            crawl_frequency="weekly",
            crawl_config={"seed_urls": [LISTING_URL, HOMEPAGE_URL]},
        ),
    )


def _fixture_fetch(page: SourcePageRef) -> FetchedContent:
    name = {
        LISTING_URL: "future-meetings.html",
        HOMEPAGE_URL: "homepage.html",
    }[page.url]
    body = (FIXTURES / name).read_bytes()
    return FetchedContent(
        url=page.url,
        status_code=200,
        content_type="text/html; charset=utf-8",
        body=body,
        fetched_at=datetime.now(UTC),
        content_hash=f"hash-{name}",
    )


def _read_bookkeeping(source_code: str) -> dict[str, Any]:
    """Read the four bookkeeping columns via a fresh session so we don't
    accidentally read through a transaction that already rolled back."""
    with session_scope() as s:
        row = s.execute(
            text(
                "SELECT last_crawled_at, last_success_at, last_error_at, "
                "last_error_message FROM sources WHERE code = :c"
            ),
            {"c": source_code},
        ).one()
    return {
        "last_crawled_at": row.last_crawled_at,
        "last_success_at": row.last_success_at,
        "last_error_at": row.last_error_at,
        "last_error_message": row.last_error_message,
    }


def test_successful_run_writes_last_crawled_and_last_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parser = parser_for("gnydm_listing")
    monkeypatch.setattr(parser, "fetch", _fixture_fetch, raising=False)

    with session_scope() as s:
        _seed_gnydm(s)

    before = datetime.now(UTC)
    with session_scope() as s:
        run_source(s, source_code="gnydm")
    after = datetime.now(UTC)

    bk = _read_bookkeeping("gnydm")
    assert bk["last_crawled_at"] is not None
    assert bk["last_success_at"] is not None
    assert before - timedelta(seconds=5) <= bk["last_crawled_at"] <= after + timedelta(seconds=5)
    assert before - timedelta(seconds=5) <= bk["last_success_at"] <= after + timedelta(seconds=5)
    assert bk["last_error_at"] is None
    assert bk["last_error_message"] is None


def test_error_during_run_writes_last_crawled_and_last_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parser = parser_for("gnydm_listing")

    def _boom(_source: Any) -> Iterator[Any]:
        raise RuntimeError("boom: simulated parser explosion")
        yield  # pragma: no cover — makes this a generator so the signature matches

    monkeypatch.setattr(parser, "discover", _boom, raising=False)

    with session_scope() as s:
        _seed_gnydm(s)

    before = datetime.now(UTC)
    with pytest.raises(RuntimeError, match="boom"), session_scope() as s:
        run_source(s, source_code="gnydm")
    after = datetime.now(UTC)

    bk = _read_bookkeeping("gnydm")
    assert bk["last_crawled_at"] is not None, "expected last_crawled_at written even on error"
    assert bk["last_error_at"] is not None, "expected last_error_at written on error"
    assert bk["last_success_at"] is None, "last_success_at must NOT be set on error"
    assert bk["last_error_message"] is not None
    assert "boom" in bk["last_error_message"]
    assert before - timedelta(seconds=5) <= bk["last_crawled_at"] <= after + timedelta(seconds=5)
    assert before - timedelta(seconds=5) <= bk["last_error_at"] <= after + timedelta(seconds=5)


def test_last_error_persists_across_successful_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parser = parser_for("gnydm_listing")
    monkeypatch.setattr(parser, "fetch", _fixture_fetch, raising=False)

    with session_scope() as s:
        _seed_gnydm(s)
        # Pre-populate a stale error state.
        s.execute(
            text(
                "UPDATE sources SET last_error_at = :eat, last_error_message = :emsg "
                "WHERE code = 'gnydm'"
            ),
            {"eat": datetime(2026, 1, 1, tzinfo=UTC), "emsg": "old boom"},
        )

    with session_scope() as s:
        run_source(s, source_code="gnydm")

    bk = _read_bookkeeping("gnydm")
    assert bk["last_success_at"] is not None, "success must write last_success_at"
    # Error fields must be UNCHANGED (see spec §4 D4 — preserve history).
    assert bk["last_error_at"] == datetime(2026, 1, 1, tzinfo=UTC)
    assert bk["last_error_message"] == "old boom"


def test_run_source_accepts_force_keyword() -> None:
    """Signature-lock smoke test. Spec §4 D6 requires `force: bool = False` as
    a keyword-only parameter on `run_source`. Inspect the signature directly
    rather than calling through — calling the function requires a real DB
    and a real source row, both orthogonal to what this test guards against
    (signature drift once W3.2b starts threading `force` into due-selection).
    """
    import inspect

    from medevents_ingest import pipeline as _pipeline

    sig = inspect.signature(_pipeline.run_source)
    assert "force" in sig.parameters, "run_source must accept a `force` parameter"
    force_param = sig.parameters["force"]
    assert force_param.kind == inspect.Parameter.KEYWORD_ONLY, (
        "spec §4 D6 requires force to be keyword-only"
    )
    assert force_param.default is False, "spec §4 D6 requires force default = False"
    # Use typing.get_type_hints to resolve the PEP 563 deferred annotation
    # (the module has `from __future__ import annotations`).
    from typing import get_type_hints

    hints = get_type_hints(_pipeline.run_source)
    assert hints.get("force") is bool, "spec §4 D6 requires force: bool"
