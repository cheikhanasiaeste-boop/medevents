"""Tests for parsers/dentex.py using real Dentex Algeria fixtures."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from medevents_ingest.parsers._reset_for_tests import reset_registry
from medevents_ingest.parsers.base import FetchedContent, ParsedEvent, Parser

FIXTURES = Path(__file__).parent / "fixtures" / "dentex"
HOMEPAGE_URL = "https://www.dentex.dz/en/"
VISIT_URL = "https://www.dentex.dz/en/visit/"


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

    import medevents_ingest.parsers.dentex as dentex
    from medevents_ingest.parsers import parser_for

    importlib.reload(dentex)
    return parser_for("dentex_algeria")


class _FakeSource:
    def __init__(self, seed_urls: list[str]) -> None:
        self.crawl_config = {"seed_urls": seed_urls}


def test_discover_yields_homepage_before_visit() -> None:
    parser = _get_parser()
    source = _FakeSource([HOMEPAGE_URL, VISIT_URL])
    discovered = list(parser.discover(source))
    assert [page.url for page in discovered] == [HOMEPAGE_URL, VISIT_URL]
    assert [page.page_kind for page in discovered] == ["detail", "detail"]


def test_discover_forces_homepage_first_even_if_seed_order_reversed() -> None:
    parser = _get_parser()
    source = _FakeSource([VISIT_URL, HOMEPAGE_URL])
    discovered = list(parser.discover(source))
    assert [page.url for page in discovered] == [HOMEPAGE_URL, VISIT_URL]


def test_homepage_yields_one_event_with_public_url() -> None:
    parser = _get_parser()
    content = _fetched("homepage.html", HOMEPAGE_URL)
    events = [event for event in parser.parse(content) if isinstance(event, ParsedEvent)]
    assert len(events) == 1, f"expected 1 event from homepage, got {len(events)}"

    event = events[0]
    assert event.title == "DENTEX Algeria 2026"
    assert event.starts_on == "2026-06-02"
    assert event.ends_on == "2026-06-05"
    assert event.timezone is None
    assert event.city == "Algiers"
    assert event.country_iso == "DZ"
    assert event.venue_name == "Algiers Exhibition Center - SAFEX (Palestine hall)"
    assert event.registration_url == "https://register.visitcloud.com/survey/2r84lirzg9l1b"
    assert event.source_url == HOMEPAGE_URL
    assert event.raw_title == "DENTEX Alg\u00e9rie 2026"
    assert event.raw_date_text == "2 - 5 June 2026"


def test_visit_page_yields_one_event_with_same_canonical_source_url() -> None:
    parser = _get_parser()
    content = _fetched("visit.html", VISIT_URL)
    events = [event for event in parser.parse(content) if isinstance(event, ParsedEvent)]
    assert len(events) == 1, f"expected 1 event from visit page, got {len(events)}"

    event = events[0]
    assert event.title == "DENTEX Algeria 2026"
    assert event.starts_on == "2026-06-02"
    assert event.ends_on == "2026-06-05"
    assert event.timezone is None
    assert event.city == "Algiers"
    assert event.country_iso == "DZ"
    assert event.venue_name == "Algiers Exhibition Center - SAFEX (Palestine hall)"
    assert event.registration_url == "https://register.visitcloud.com/survey/2r84lirzg9l1b"
    assert event.source_url == HOMEPAGE_URL
    assert event.raw_title == "DENTEX Alg\u00e9rie 2026"
    assert event.raw_date_text == "2 - 5 June 2026"


def test_homepage_fixture_at_wrong_url_yields_zero_events() -> None:
    parser = _get_parser()
    content = _fetched("homepage.html", "https://www.dentex.dz/en/some-other-page/")
    events = [event for event in parser.parse(content) if isinstance(event, ParsedEvent)]
    assert events == [], f"expected 0 events at wrong homepage url, got {len(events)}"


def test_visit_fixture_at_wrong_url_yields_zero_events() -> None:
    parser = _get_parser()
    content = _fetched("visit.html", "https://www.dentex.dz/en/visit/why-visit/")
    events = [event for event in parser.parse(content) if isinstance(event, ParsedEvent)]
    assert events == [], f"expected 0 events at wrong visit url, got {len(events)}"
