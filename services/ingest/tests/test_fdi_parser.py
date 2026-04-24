"""Tests for parsers/fdi.py using real FDI HTML fixtures."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from medevents_ingest.parsers._reset_for_tests import reset_registry
from medevents_ingest.parsers.base import FetchedContent, ParsedEvent, Parser

FIXTURES = Path(__file__).parent / "fixtures" / "fdi"
HUB_URL = "https://www.fdiworlddental.org/fdi-world-dental-congress"
DETAIL_URL = "https://www.fdiworlddental.org/fdi-world-dental-congress-2026"


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

    import medevents_ingest.parsers.fdi as fdi
    from medevents_ingest.parsers import parser_for

    importlib.reload(fdi)
    return parser_for("fdi_wdc")


class _FakeSource:
    def __init__(self, seed_urls: list[str]) -> None:
        self.crawl_config = {"seed_urls": seed_urls}


def test_discover_yields_hub_before_detail() -> None:
    parser = _get_parser()
    source = _FakeSource([HUB_URL, DETAIL_URL])
    discovered = list(parser.discover(source))
    assert [p.url for p in discovered] == [HUB_URL, DETAIL_URL]
    assert [p.page_kind for p in discovered] == ["detail", "detail"]


def test_discover_forces_hub_first_even_if_seed_order_reversed() -> None:
    parser = _get_parser()
    source = _FakeSource([DETAIL_URL, HUB_URL])
    discovered = list(parser.discover(source))
    assert [p.url for p in discovered] == [HUB_URL, DETAIL_URL]


def test_hub_yields_one_event_with_required_fields() -> None:
    parser = _get_parser()
    content = _fetched("hub.html", HUB_URL)
    events = [e for e in parser.parse(content) if isinstance(e, ParsedEvent)]
    assert len(events) == 1, f"expected 1 event from hub, got {len(events)}"
    e = events[0]
    assert e.title == "FDI World Dental Congress 2026"
    assert e.starts_on == "2026-09-04"
    assert e.ends_on == "2026-09-07"
    assert e.city == "Prague"
    assert e.country_iso == "CZ"
    assert e.venue_name is None
    assert e.format == "in_person"
    assert e.event_kind == "conference"
    assert e.lifecycle_status == "active"
    assert e.organizer_name == "FDI World Dental Federation"
    assert e.registration_url == "https://2026.world-dental-congress.org/"
    assert e.raw_title == "FDI World Dental Congress 2026"
    assert e.raw_date_text == "4 to 7 September 2026"


def test_detail_yields_one_event_with_required_fields() -> None:
    parser = _get_parser()
    content = _fetched("wdc-2026.html", DETAIL_URL)
    events = [e for e in parser.parse(content) if isinstance(e, ParsedEvent)]
    assert len(events) == 1, f"expected 1 event from detail page, got {len(events)}"
    e = events[0]
    assert e.title == "FDI World Dental Congress 2026"
    assert e.starts_on == "2026-09-04"
    assert e.ends_on == "2026-09-07"
    assert e.city == "Prague"
    assert e.country_iso == "CZ"
    assert e.venue_name is None
    assert e.registration_url == "https://2026.world-dental-congress.org/"
    assert e.raw_title == "FDI World Dental Congress 2026"
    assert e.raw_date_text == "4 September 2026 - 7 September 2026"


def test_2025_canary_served_at_detail_url_yields_zero_events() -> None:
    parser = _get_parser()
    content = _fetched("wdc-2025.html", DETAIL_URL)
    events = [e for e in parser.parse(content) if isinstance(e, ParsedEvent)]
    assert events == [], f"expected 0 events from 2025 canary, got {len(events)}"


def test_detail_fixture_at_wrong_url_yields_zero_events() -> None:
    parser = _get_parser()
    content = _fetched("wdc-2026.html", "https://www.fdiworlddental.org/some-other-page")
    events = [e for e in parser.parse(content) if isinstance(e, ParsedEvent)]
    assert events == [], f"expected 0 events at wrong URL, got {len(events)}"
