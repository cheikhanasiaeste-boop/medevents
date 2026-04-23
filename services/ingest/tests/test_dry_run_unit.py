"""Unit tests for `--dry-run` write-bypass behavior in pipeline.py.

These tests are pure unit tests: no DB, no HTTP. The SQLAlchemy Session is a
`unittest.mock.MagicMock`, and every write helper that `pipeline` imports at
module scope is replaced via `monkeypatch.setattr(pipeline, "<name>", stub)`
so we can assert (not) called and control return values.

Scope: W3.2f Task 1. Covers the six write sites that must be bypassed under
`dry_run=True`:
  1. `update_source_run_status` (success + error paths in `run_source`)
  2. `_record_error_bookkeeping_fresh_session` in `run_source`
  3. `upsert_source_page` in `_run_source_inner`
  4. `record_fetch` in `_run_source_inner`
  5. `insert_event` / `update_event_fields` / `upsert_event_source` in
     `_persist_event`
  6. `insert_review_item` in `_run_source_inner`
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest
from medevents_ingest import pipeline
from medevents_ingest.models import Source
from medevents_ingest.parsers.base import (
    DiscoveredPage,
    FetchedContent,
    ParsedEvent,
    SourcePageRef,
)

_SOURCE_ID = UUID("11111111-1111-1111-1111-111111111111")
_SOURCE_PAGE_ID = UUID("22222222-2222-2222-2222-222222222222")
_EVENT_ID = UUID("33333333-3333-3333-3333-333333333333")
_ZERO_UUID = UUID("00000000-0000-0000-0000-000000000000")


def _make_source(code: str = "test", parser_name: str = "test_parser") -> Source:
    now = datetime(2026, 4, 23, tzinfo=UTC)
    return Source(
        id=_SOURCE_ID,
        code=code,
        name="Test",
        homepage_url="https://example.test/",
        source_type="society",
        country_iso="US",
        is_active=True,
        parser_name=parser_name,
        crawl_frequency="weekly",
        crawl_config={},
        last_crawled_at=None,
        last_success_at=None,
        last_error_at=None,
        last_error_message=None,
        notes=None,
        created_at=now,
        updated_at=now,
    )


def _make_parsed_event(title: str = "Example Event") -> ParsedEvent:
    return ParsedEvent(
        title=title,
        starts_on="2026-10-01",
        city="Somewhere",
        country_iso="US",
        venue_name="Test Venue",
        source_url="https://example.test/event/1",
    )


def _make_fetched_content(url: str, content_hash: str = "h1") -> FetchedContent:
    return FetchedContent(
        url=url,
        status_code=200,
        content_type="text/html; charset=utf-8",
        body=b"<html></html>",
        fetched_at=datetime(2026, 4, 23, 12, 0, tzinfo=UTC),
        content_hash=content_hash,
    )


class _FakeParser:
    """Minimal parser test double. Callers set `.pages`, `.fetch_result`, `.parsed`."""

    name = "test_parser"

    def __init__(
        self,
        *,
        pages: list[DiscoveredPage],
        fetch_result: FetchedContent | None = None,
        fetch_exc: Exception | None = None,
        parsed: list[ParsedEvent] | None = None,
    ) -> None:
        self.pages = pages
        self.fetch_result = fetch_result
        self.fetch_exc = fetch_exc
        self.parsed = parsed or []

    def discover(self, source: Any) -> Iterator[DiscoveredPage]:
        yield from self.pages

    def fetch(self, page: SourcePageRef) -> FetchedContent:
        if self.fetch_exc is not None:
            raise self.fetch_exc
        assert self.fetch_result is not None
        return self.fetch_result

    def parse(self, content: FetchedContent) -> Iterator[ParsedEvent]:
        yield from self.parsed


@pytest.fixture
def stub_writes(monkeypatch: pytest.MonkeyPatch) -> dict[str, MagicMock]:
    """Replace every write helper (and a few reads) at the `pipeline` import site.

    Returns a dict of stub MagicMocks keyed by helper name so individual tests
    can assert called/not-called.
    """
    stubs: dict[str, MagicMock] = {
        # Writes.
        "update_source_run_status": MagicMock(return_value=None),
        "_record_error_bookkeeping_fresh_session": MagicMock(return_value=None),
        "upsert_source_page": MagicMock(return_value=_SOURCE_PAGE_ID),
        "record_fetch": MagicMock(return_value=None),
        "insert_review_item": MagicMock(return_value=uuid4()),
        "insert_event": MagicMock(return_value=_EVENT_ID),
        "update_event_fields": MagicMock(return_value=None),
        "upsert_event_source": MagicMock(return_value=None),
        # Reads we need to control to avoid the real DB.
        "get_last_content_hash": MagicMock(return_value=None),
        "find_event_by_source_local_match": MagicMock(return_value=None),
        "find_event_by_registration_url": MagicMock(return_value=None),
    }
    for name, stub in stubs.items():
        monkeypatch.setattr(pipeline, name, stub, raising=True)
    return stubs


# ---------------------------------------------------------------------------
# run_source: bookkeeping bypass
# ---------------------------------------------------------------------------


def test_run_source_dry_run_skips_bookkeeping_on_success(
    monkeypatch: pytest.MonkeyPatch,
    stub_writes: dict[str, MagicMock],
) -> None:
    source = _make_source()
    monkeypatch.setattr(pipeline, "get_source_by_code", lambda _s, _c: source)
    monkeypatch.setattr(
        pipeline,
        "_run_source_inner",
        lambda _s, *, source, dry_run=False: pipeline.PipelineResult(
            source_code=source.code,
            pages_fetched=0,
            pages_skipped_unchanged=0,
            events_created=0,
            events_updated=0,
            review_items_created=0,
        ),
    )

    session = MagicMock()
    result = pipeline.run_source(session, source_code="test", dry_run=True)

    assert result.source_code == "test"
    stub_writes["update_source_run_status"].assert_not_called()


def test_run_source_dry_run_skips_bookkeeping_on_error(
    monkeypatch: pytest.MonkeyPatch,
    stub_writes: dict[str, MagicMock],
) -> None:
    source = _make_source()
    monkeypatch.setattr(pipeline, "get_source_by_code", lambda _s, _c: source)

    def _boom(_s: Any, *, source: Source, dry_run: bool = False) -> Any:
        raise RuntimeError("kaboom")

    monkeypatch.setattr(pipeline, "_run_source_inner", _boom)

    session = MagicMock()
    with pytest.raises(RuntimeError, match="kaboom"):
        pipeline.run_source(session, source_code="test", dry_run=True)

    stub_writes["_record_error_bookkeeping_fresh_session"].assert_not_called()
    stub_writes["update_source_run_status"].assert_not_called()


# ---------------------------------------------------------------------------
# _run_source_inner: page + fetch + review-item bypass
# ---------------------------------------------------------------------------


def test_run_source_inner_dry_run_skips_upsert_source_page(
    monkeypatch: pytest.MonkeyPatch,
    stub_writes: dict[str, MagicMock],
) -> None:
    source = _make_source()
    page = DiscoveredPage(url="https://example.test/listing", page_kind="listing")
    parser = _FakeParser(
        pages=[page],
        fetch_result=_make_fetched_content(page.url),
        parsed=[_make_parsed_event()],
    )
    monkeypatch.setattr(pipeline, "parser_for", lambda _name: parser)

    session = MagicMock()
    result = pipeline._run_source_inner(session, source=source, dry_run=True)

    stub_writes["upsert_source_page"].assert_not_called()
    assert result.pages_fetched == 1


def test_run_source_inner_dry_run_skips_record_fetch(
    monkeypatch: pytest.MonkeyPatch,
    stub_writes: dict[str, MagicMock],
) -> None:
    source = _make_source()
    page = DiscoveredPage(url="https://example.test/listing", page_kind="listing")
    parser = _FakeParser(
        pages=[page],
        fetch_result=_make_fetched_content(page.url),
        parsed=[_make_parsed_event()],
    )
    monkeypatch.setattr(pipeline, "parser_for", lambda _name: parser)

    session = MagicMock()
    pipeline._run_source_inner(session, source=source, dry_run=True)

    stub_writes["record_fetch"].assert_not_called()


def test_run_source_inner_dry_run_skips_insert_review_item_on_fetch_error(
    monkeypatch: pytest.MonkeyPatch,
    stub_writes: dict[str, MagicMock],
) -> None:
    source = _make_source()
    page = DiscoveredPage(url="https://example.test/listing", page_kind="listing")
    parser = _FakeParser(
        pages=[page],
        fetch_exc=RuntimeError("blocked by cloudflare"),
    )
    monkeypatch.setattr(pipeline, "parser_for", lambda _name: parser)

    session = MagicMock()
    result = pipeline._run_source_inner(session, source=source, dry_run=True)

    stub_writes["insert_review_item"].assert_not_called()
    stub_writes["record_fetch"].assert_not_called()
    # Still bumps the review-item counter under dry-run.
    assert result.review_items_created == 1


def test_run_source_inner_dry_run_skips_insert_review_item_on_zero_events(
    monkeypatch: pytest.MonkeyPatch,
    stub_writes: dict[str, MagicMock],
) -> None:
    source = _make_source()
    page = DiscoveredPage(url="https://example.test/listing", page_kind="listing")
    parser = _FakeParser(
        pages=[page],
        fetch_result=_make_fetched_content(page.url),
        parsed=[],  # zero events -> parser_failure branch
    )
    monkeypatch.setattr(pipeline, "parser_for", lambda _name: parser)

    session = MagicMock()
    result = pipeline._run_source_inner(session, source=source, dry_run=True)

    stub_writes["insert_review_item"].assert_not_called()
    assert result.review_items_created == 1


# ---------------------------------------------------------------------------
# _persist_event: insert/update/upsert bypass
# ---------------------------------------------------------------------------


def test_persist_event_dry_run_skips_insert_event_when_no_match(
    stub_writes: dict[str, MagicMock],
) -> None:
    stub_writes["find_event_by_source_local_match"].return_value = None
    session = MagicMock()
    candidate = _make_parsed_event()

    created, updated = pipeline._persist_event(
        session,
        source_id=_SOURCE_ID,
        source_page_id=_SOURCE_PAGE_ID,
        candidate=candidate,
        source_code="test",
        dry_run=True,
    )

    stub_writes["insert_event"].assert_not_called()
    assert (created, updated) == (1, 0)


def test_persist_event_dry_run_skips_update_event_fields_when_match(
    stub_writes: dict[str, MagicMock],
) -> None:
    stub_writes["find_event_by_source_local_match"].return_value = _EVENT_ID
    session = MagicMock()
    candidate = _make_parsed_event()

    created, updated = pipeline._persist_event(
        session,
        source_id=_SOURCE_ID,
        source_page_id=_SOURCE_PAGE_ID,
        candidate=candidate,
        source_code="test",
        dry_run=True,
    )

    stub_writes["update_event_fields"].assert_not_called()
    assert (created, updated) == (0, 1)


def test_persist_event_dry_run_skips_upsert_event_source(
    stub_writes: dict[str, MagicMock],
) -> None:
    # Exercise the no-match branch to prove upsert_event_source is skipped there.
    stub_writes["find_event_by_source_local_match"].return_value = None
    session = MagicMock()
    candidate = _make_parsed_event()

    pipeline._persist_event(
        session,
        source_id=_SOURCE_ID,
        source_page_id=_SOURCE_PAGE_ID,
        candidate=candidate,
        source_code="test",
        dry_run=True,
    )

    stub_writes["upsert_event_source"].assert_not_called()


# ---------------------------------------------------------------------------
# run_all: per-source failure does not trigger error bookkeeping under dry-run
# ---------------------------------------------------------------------------


def test_run_all_dry_run_skips_error_bookkeeping_on_per_source_failure(
    monkeypatch: pytest.MonkeyPatch,
    stub_writes: dict[str, MagicMock],
) -> None:
    source = _make_source(code="test")
    monkeypatch.setattr(pipeline, "get_active_sources", lambda _s: [source])
    monkeypatch.setattr(
        pipeline,
        "get_active_due_sources",
        lambda _s, *, now: [source],
    )

    def _boom(
        _s: Any,
        *,
        source_code: str,
        force: bool = False,
        dry_run: bool = False,
    ) -> Any:
        raise RuntimeError("per-source kaboom")

    monkeypatch.setattr(pipeline, "run_source", _boom)

    session = MagicMock()
    now = datetime(2026, 4, 23, tzinfo=UTC)
    result = pipeline.run_all(session, force=False, now=now, dry_run=True)

    stub_writes["_record_error_bookkeeping_fresh_session"].assert_not_called()
    assert result.failed == 1
    assert result.succeeded == 0
