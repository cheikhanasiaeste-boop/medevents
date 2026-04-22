"""DB-gated integration tests for pipeline.run_all() (spec §5 tests 1-4)."""

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
from medevents_ingest.pipeline import BatchResult, run_all
from medevents_ingest.repositories.sources import upsert_source_seed
from sqlalchemy import text

pytestmark = pytest.mark.skipif(
    "TEST_DATABASE_URL" not in os.environ,
    reason="TEST_DATABASE_URL not set; skipping integration tests",
)

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def _alias_test_database_url(
    _no_env_pollution: None,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[None]:
    monkeypatch.setenv("DATABASE_URL", os.environ["TEST_DATABASE_URL"])
    _db._engine = None
    _db._SessionLocal = None
    try:
        yield
    finally:
        _db._engine = None
        _db._SessionLocal = None


@pytest.fixture(autouse=True)
def _ensure_parsers_registered() -> None:
    import importlib

    if "ada_listing" not in registered_parser_names():
        import medevents_ingest.parsers.ada as _ada_mod

        importlib.reload(_ada_mod)
    if "gnydm_listing" not in registered_parser_names():
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


def _seed_source(
    session: Any,
    *,
    code: str,
    parser_name: str,
    homepage: str,
    seed_urls: list[str],
    is_active: bool = True,
) -> None:
    upsert_source_seed(
        session,
        SourceSeed(
            code=code,
            name=code.upper(),
            homepage_url=homepage,
            source_type="society",
            country_iso="US",
            parser_name=parser_name,
            crawl_frequency="weekly",
            crawl_config={"seed_urls": seed_urls},
            is_active=is_active,
        ),
    )


def _backdate_last_crawled(source_code: str, days_ago: float) -> None:
    with session_scope() as s:
        s.execute(
            text("UPDATE sources SET last_crawled_at = :ts WHERE code = :c"),
            {
                "ts": datetime.now(UTC) - timedelta(days=days_ago),
                "c": source_code,
            },
        )


def _gnydm_fixture_fetch(page: SourcePageRef) -> FetchedContent:
    name = {
        "https://www.gnydm.com/about/future-meetings/": "future-meetings.html",
        "https://www.gnydm.com/": "homepage.html",
    }[page.url]
    body = (FIXTURES / "gnydm" / name).read_bytes()
    return FetchedContent(
        url=page.url,
        status_code=200,
        content_type="text/html; charset=utf-8",
        body=body,
        fetched_at=datetime.now(UTC),
        content_hash=f"hash-{name}",
    )


def test_run_all_runs_only_due_sources(monkeypatch: pytest.MonkeyPatch) -> None:
    gnydm_parser = parser_for("gnydm_listing")
    monkeypatch.setattr(gnydm_parser, "fetch", _gnydm_fixture_fetch, raising=False)

    with session_scope() as s:
        _seed_source(
            s,
            code="gnydm",
            parser_name="gnydm_listing",
            homepage="https://www.gnydm.com/",
            seed_urls=[
                "https://www.gnydm.com/about/future-meetings/",
                "https://www.gnydm.com/",
            ],
        )
        # ADA-shaped source but we won't give it a fetch mock — if it runs,
        # it would make a real network call. Instead it should be "not due".
        _seed_source(
            s,
            code="ada",
            parser_name="ada_listing",
            homepage="https://www.ada.org/",
            seed_urls=["https://www.ada.org/education/continuing-education/ada-ce-live-workshops"],
        )
    # gnydm is due (never crawled); ada is NOT due (backdate to 2 days ago, weekly window = 7d).
    _backdate_last_crawled("ada", days_ago=2)

    now = datetime.now(UTC)
    with session_scope() as s:
        result: BatchResult = run_all(s, force=False, now=now)

    # Exactly one source ran: gnydm.
    assert result.sources_selected == 1
    assert result.succeeded == 1
    assert result.failed == 0
    assert result.skipped_not_due == 1, "ada should have been skipped"

    with session_scope() as s:
        gnydm_success = s.execute(
            text("SELECT last_success_at FROM sources WHERE code = 'gnydm'")
        ).scalar_one()
        ada_success = s.execute(
            text("SELECT last_success_at FROM sources WHERE code = 'ada'")
        ).scalar_one()
    assert gnydm_success is not None, "gnydm ran, must have last_success_at"
    assert ada_success is None, "ada was not due and never ran; last_success_at stays null"


def test_run_all_force_runs_all_active_sources_even_if_fresh(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gnydm_parser = parser_for("gnydm_listing")
    monkeypatch.setattr(gnydm_parser, "fetch", _gnydm_fixture_fetch, raising=False)

    # ADA would need a real network call; monkeypatch its fetch to a stub
    # that emits a minimal FetchedContent whose body yields no events
    # (so the run succeeds with zero events created — we only care that it ran).
    ada_parser = parser_for("ada_listing")

    def _ada_empty_fetch(page: SourcePageRef) -> FetchedContent:
        return FetchedContent(
            url=page.url,
            status_code=200,
            content_type="text/html; charset=utf-8",
            body=b"<html><body>no events</body></html>",
            fetched_at=datetime.now(UTC),
            content_hash=f"empty-{page.url}",
        )

    monkeypatch.setattr(ada_parser, "fetch", _ada_empty_fetch, raising=False)

    with session_scope() as s:
        _seed_source(
            s,
            code="gnydm",
            parser_name="gnydm_listing",
            homepage="https://www.gnydm.com/",
            seed_urls=[
                "https://www.gnydm.com/about/future-meetings/",
                "https://www.gnydm.com/",
            ],
        )
        _seed_source(
            s,
            code="ada",
            parser_name="ada_listing",
            homepage="https://www.ada.org/",
            seed_urls=["https://www.ada.org/education/continuing-education/ada-ce-live-workshops"],
        )
    # Both sources fresh — would NOT be due without --force.
    _backdate_last_crawled("gnydm", days_ago=1)
    _backdate_last_crawled("ada", days_ago=1)

    now = datetime.now(UTC)
    with session_scope() as s:
        result = run_all(s, force=True, now=now)

    assert result.sources_selected == 2
    assert result.skipped_not_due == 0, "force must bypass due-check"
    # Both may either fully succeed or surface a parser_failure review_item
    # (ADA's empty body will trigger the listing-failure review item).
    # What matters: both sources RAN (i.e. either succeeded or failed at the
    # pipeline level, not skipped).
    assert result.succeeded + result.failed == 2


def test_run_all_continues_after_single_source_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gnydm_parser = parser_for("gnydm_listing")
    monkeypatch.setattr(gnydm_parser, "fetch", _gnydm_fixture_fetch, raising=False)

    ada_parser = parser_for("ada_listing")

    def _boom(_source: Any) -> Iterator[Any]:
        raise RuntimeError("boom: ada discover failure")
        yield  # pragma: no cover

    monkeypatch.setattr(ada_parser, "discover", _boom, raising=False)

    with session_scope() as s:
        _seed_source(
            s,
            code="gnydm",
            parser_name="gnydm_listing",
            homepage="https://www.gnydm.com/",
            seed_urls=[
                "https://www.gnydm.com/about/future-meetings/",
                "https://www.gnydm.com/",
            ],
        )
        _seed_source(
            s,
            code="ada",
            parser_name="ada_listing",
            homepage="https://www.ada.org/",
            seed_urls=["https://www.ada.org/education/continuing-education/ada-ce-live-workshops"],
        )

    now = datetime.now(UTC)
    with session_scope() as s:
        result = run_all(s, force=True, now=now)

    assert result.sources_selected == 2
    assert result.succeeded == 1, "gnydm must still succeed"
    assert result.failed == 1, "ada failure counted"
    assert result.skipped_not_due == 0

    with session_scope() as s:
        gnydm_success = s.execute(
            text("SELECT last_success_at FROM sources WHERE code = 'gnydm'")
        ).scalar_one()
        ada_error = s.execute(
            text("SELECT last_error_message FROM sources WHERE code = 'ada'")
        ).scalar_one()
    assert gnydm_success is not None, "batch must not have short-circuited on ada's failure"
    assert ada_error is not None and "boom" in ada_error, (
        "ada's failure must land in last_error_message"
    )


def test_run_all_skips_inactive_sources_even_under_force(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gnydm_parser = parser_for("gnydm_listing")
    monkeypatch.setattr(gnydm_parser, "fetch", _gnydm_fixture_fetch, raising=False)

    with session_scope() as s:
        _seed_source(
            s,
            code="gnydm",
            parser_name="gnydm_listing",
            homepage="https://www.gnydm.com/",
            seed_urls=[
                "https://www.gnydm.com/about/future-meetings/",
                "https://www.gnydm.com/",
            ],
        )
        _seed_source(
            s,
            code="ada",
            parser_name="ada_listing",
            homepage="https://www.ada.org/",
            seed_urls=["https://www.ada.org/education/continuing-education/ada-ce-live-workshops"],
            is_active=False,
        )

    now = datetime.now(UTC)
    with session_scope() as s:
        result = run_all(s, force=True, now=now)

    assert result.sources_selected == 1, "inactive source excluded from selection"
    assert result.succeeded == 1

    with session_scope() as s:
        ada_crawled = s.execute(
            text("SELECT last_crawled_at FROM sources WHERE code = 'ada'")
        ).scalar_one()
    assert ada_crawled is None, "inactive source must not be touched even under --force"
