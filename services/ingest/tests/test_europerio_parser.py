"""Tests for parsers/europerio.py using real EFP HTML fixtures."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from medevents_ingest.parsers._reset_for_tests import reset_registry
from medevents_ingest.parsers.base import FetchedContent, ParsedEvent, Parser

FIXTURES = Path(__file__).parent / "fixtures" / "europerio"
HUB_URL = "https://www.efp.org/europerio/"
DETAIL_URL = "https://www.efp.org/europerio/europerio12/"


def _fetched(name: str, url: str) -> FetchedContent:
    body = (FIXTURES / name).read_bytes()
    return FetchedContent(
        url=url,
        status_code=200,
        content_type="text/html; charset=utf-8",
        body=body,
        fetched_at=datetime.now(UTC),
        content_hash="fixture-hash",
    )


@pytest.fixture(autouse=True)
def _reset_registry() -> None:
    reset_registry()


def _get_parser() -> Parser:
    import importlib

    import medevents_ingest.parsers.europerio as europerio
    from medevents_ingest.parsers import parser_for

    importlib.reload(europerio)
    return parser_for("europerio")


class _FakeSource:
    def __init__(self, seed_urls: list[str]) -> None:
        self.crawl_config = {"seed_urls": seed_urls}


def test_discover_yields_hub_before_detail() -> None:
    parser = _get_parser()
    source = _FakeSource([HUB_URL, DETAIL_URL])
    discovered = list(parser.discover(source))
    assert [page.url for page in discovered] == [HUB_URL, DETAIL_URL]
    assert [page.page_kind for page in discovered] == ["detail", "detail"]


def test_discover_forces_hub_first_even_if_seed_order_reversed() -> None:
    parser = _get_parser()
    source = _FakeSource([DETAIL_URL, HUB_URL])
    discovered = list(parser.discover(source))
    assert [page.url for page in discovered] == [HUB_URL, DETAIL_URL]


def test_hub_yields_one_event_with_required_fields() -> None:
    parser = _get_parser()
    content = _fetched("hub.html", HUB_URL)
    events = [event for event in parser.parse(content) if isinstance(event, ParsedEvent)]
    assert len(events) == 1, f"expected 1 event from hub, got {len(events)}"

    event = events[0]
    assert event.title == "EuroPerio12"
    assert event.starts_on == "2028-05-10"
    assert event.ends_on == "2028-05-13"
    assert event.city == "Munich"
    assert event.country_iso == "DE"
    assert event.venue_name is None
    assert event.registration_url is None
    assert event.source_url == DETAIL_URL
    assert event.raw_title == (
        "EuroPerio, the world's leading congress in periodontology and implant dentistry"
    )
    assert event.raw_date_text == "10 -13 May, 2028"


def test_detail_yields_one_event_with_required_fields() -> None:
    parser = _get_parser()
    content = _fetched("europerio12.html", DETAIL_URL)
    events = [event for event in parser.parse(content) if isinstance(event, ParsedEvent)]
    assert len(events) == 1, f"expected 1 event from detail page, got {len(events)}"

    event = events[0]
    assert event.title == "EuroPerio12"
    assert event.starts_on == "2028-05-10"
    assert event.ends_on == "2028-05-13"
    assert event.city == "Munich"
    assert event.country_iso == "DE"
    assert event.venue_name is None
    assert event.registration_url is None
    assert event.source_url == DETAIL_URL
    assert event.raw_title == "EuroPerio12"
    assert event.raw_date_text == "May 10-13, 2028"


def test_hub_fixture_at_wrong_url_yields_zero_events() -> None:
    parser = _get_parser()
    content = _fetched("hub.html", "https://www.efp.org/europerio/archive/")
    events = [event for event in parser.parse(content) if isinstance(event, ParsedEvent)]
    assert events == [], f"expected 0 events at wrong hub url, got {len(events)}"


def test_detail_fixture_at_wrong_url_yields_zero_events() -> None:
    parser = _get_parser()
    content = _fetched("europerio12.html", "https://www.efp.org/europerio/europerio11/")
    events = [event for event in parser.parse(content) if isinstance(event, ParsedEvent)]
    assert events == [], f"expected 0 events at wrong detail url, got {len(events)}"
