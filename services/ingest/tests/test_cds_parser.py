"""Tests for parsers/cds.py using real CDS fixtures."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from medevents_ingest.parsers._reset_for_tests import reset_registry
from medevents_ingest.parsers.base import FetchedContent, ParsedEvent, Parser

FIXTURES = Path(__file__).parent / "fixtures" / "cds"
DETAIL_URL = "https://www.cds.org/event/2026-midwinter-meeting/"
API_URL = "https://www.cds.org/wp-json/tribe/events/v1/events/387532"


def _fetched(name: str, url: str, *, content_type: str) -> FetchedContent:
    body = (FIXTURES / name).read_bytes()
    return FetchedContent(
        url=url,
        status_code=200,
        content_type=content_type,
        body=body,
        fetched_at=datetime.now(UTC),
        content_hash="fixture-hash",
    )


@pytest.fixture(autouse=True)
def _reset_registry() -> None:
    reset_registry()


def _get_parser() -> Parser:
    import importlib

    import medevents_ingest.parsers.cds as cds
    from medevents_ingest.parsers import parser_for

    importlib.reload(cds)
    return parser_for("cds_midwinter")


class _FakeSource:
    def __init__(self, seed_urls: list[str]) -> None:
        self.crawl_config = {"seed_urls": seed_urls}


def test_discover_yields_event_page_before_api() -> None:
    parser = _get_parser()
    source = _FakeSource([DETAIL_URL, API_URL])
    discovered = list(parser.discover(source))
    assert [page.url for page in discovered] == [DETAIL_URL, API_URL]
    assert [page.page_kind for page in discovered] == ["detail", "detail"]


def test_discover_forces_event_page_first_even_if_seed_order_reversed() -> None:
    parser = _get_parser()
    source = _FakeSource([API_URL, DETAIL_URL])
    discovered = list(parser.discover(source))
    assert [page.url for page in discovered] == [DETAIL_URL, API_URL]


def test_event_page_yields_one_event_with_public_url() -> None:
    parser = _get_parser()
    content = _fetched("event.html", DETAIL_URL, content_type="text/html; charset=utf-8")
    events = [event for event in parser.parse(content) if isinstance(event, ParsedEvent)]
    assert len(events) == 1, f"expected 1 event from event page, got {len(events)}"

    event = events[0]
    assert event.title == "Chicago Dental Society Midwinter Meeting 2026"
    assert event.starts_on == "2026-02-19"
    assert event.ends_on == "2026-02-21"
    assert event.timezone is None
    assert event.city == "Chicago"
    assert event.country_iso == "US"
    assert event.venue_name is None
    assert event.registration_url == "https://midwintermeeting.eventscribe.net/"
    assert event.source_url == DETAIL_URL
    assert event.raw_title == "2026 Midwinter Meeting"
    assert event.raw_date_text == "February 19, 2026 - February 21, 2026"


def test_api_yields_one_event_with_venue_and_timezone_enrichment() -> None:
    parser = _get_parser()
    content = _fetched("event.json", API_URL, content_type="application/json; charset=utf-8")
    events = [event for event in parser.parse(content) if isinstance(event, ParsedEvent)]
    assert len(events) == 1, f"expected 1 event from api page, got {len(events)}"

    event = events[0]
    assert event.title == "Chicago Dental Society Midwinter Meeting 2026"
    assert event.starts_on == "2026-02-19"
    assert event.ends_on == "2026-02-21"
    assert event.timezone == "America/Chicago"
    assert event.city == "Chicago"
    assert event.country_iso == "US"
    assert event.venue_name == "McCormick Place West"
    assert event.registration_url == "https://midwintermeeting.eventscribe.net/"
    assert event.source_url == DETAIL_URL
    assert event.raw_title == "2026 Midwinter Meeting"
    assert event.raw_date_text == "February 19, 2026 - February 21, 2026"


def test_event_fixture_at_wrong_url_yields_zero_events() -> None:
    parser = _get_parser()
    content = _fetched(
        "event.html",
        "https://www.cds.org/some-other-page",
        content_type="text/html; charset=utf-8",
    )
    events = [event for event in parser.parse(content) if isinstance(event, ParsedEvent)]
    assert events == [], f"expected 0 events at wrong url, got {len(events)}"


def test_api_fixture_at_wrong_url_yields_zero_events() -> None:
    parser = _get_parser()
    content = _fetched(
        "event.json",
        "https://www.cds.org/wp-json/tribe/events/v1/events/999999",
        content_type="application/json; charset=utf-8",
    )
    events = [event for event in parser.parse(content) if isinstance(event, ParsedEvent)]
    assert events == [], f"expected 0 events at wrong api url, got {len(events)}"
