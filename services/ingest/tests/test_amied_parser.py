"""Tests for parsers/amied.py using real source fixtures."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from medevents_ingest.parsers._reset_for_tests import reset_registry
from medevents_ingest.parsers.base import FetchedContent, ParsedEvent, Parser

FIXTURES = Path(__file__).parent / "fixtures" / "amied"
HOMEPAGE_URL = "https://amied.ma/"
INSCRIPTIONS_URL = "https://amied.ma/inscriptions/"
REGISTRATION_URL = (
    "https://docs.google.com/forms/d/e/1FAIpQLSd3x-i-F-pC42oIUyNEJ9qXvJYKqhZTKrrztW5hkYJQ5WC7_w/"
    "viewform?embedded=true"
)


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

    import medevents_ingest.parsers.amied as amied
    from medevents_ingest.parsers import parser_for

    importlib.reload(amied)
    return parser_for("amied_congress")


class _FakeSource:
    def __init__(self, seed_urls: list[str]) -> None:
        self.crawl_config = {"seed_urls": seed_urls}


def test_discover_yields_homepage_before_inscriptions_page() -> None:
    parser = _get_parser()
    source = _FakeSource([HOMEPAGE_URL, INSCRIPTIONS_URL])
    discovered = list(parser.discover(source))
    assert [page.url for page in discovered] == [HOMEPAGE_URL, INSCRIPTIONS_URL]
    assert [page.page_kind for page in discovered] == ["detail", "detail"]


def test_discover_forces_homepage_first_even_if_seed_order_reversed() -> None:
    parser = _get_parser()
    source = _FakeSource([INSCRIPTIONS_URL, HOMEPAGE_URL])
    discovered = list(parser.discover(source))
    assert [page.url for page in discovered] == [HOMEPAGE_URL, INSCRIPTIONS_URL]


def test_homepage_yields_one_event_with_registration_url() -> None:
    parser = _get_parser()
    content = _fetched("home.html", HOMEPAGE_URL)
    events = [event for event in parser.parse(content) if isinstance(event, ParsedEvent)]
    assert len(events) == 1, f"expected 1 event from homepage, got {len(events)}"

    event = events[0]
    assert event.title == "AMIED International Congress 2026"
    assert event.starts_on == "2026-06-19"
    assert event.ends_on == "2026-06-20"
    assert event.timezone is None
    assert event.city == "Marrakech"
    assert event.country_iso == "MA"
    assert event.venue_name == "Barcelo Palmeraie Oasis Resort"
    assert event.registration_url == REGISTRATION_URL
    assert event.source_url == HOMEPAGE_URL
    assert event.raw_title == "Congr\u00e8s international"
    assert event.raw_date_text == "Vendredi 19 Juin Samedi 20 Juin 2026"


def test_inscriptions_page_yields_one_event_with_same_canonical_source_url() -> None:
    parser = _get_parser()
    content = _fetched("inscriptions.html", INSCRIPTIONS_URL)
    events = [event for event in parser.parse(content) if isinstance(event, ParsedEvent)]
    assert len(events) == 1, f"expected 1 event from inscriptions page, got {len(events)}"

    event = events[0]
    assert event.title == "AMIED International Congress 2026"
    assert event.starts_on == "2026-06-19"
    assert event.ends_on == "2026-06-20"
    assert event.timezone is None
    assert event.city == "Marrakech"
    assert event.country_iso == "MA"
    assert event.venue_name == "Barcelo Palmeraie Oasis Resort"
    assert event.registration_url == REGISTRATION_URL
    assert event.source_url == HOMEPAGE_URL
    assert event.raw_title == (
        "Participez au Congr\u00e8s International d\u2019Implantologie et d\u2019Esth\u00e9tique "
        "Dentaire"
    )
    assert event.raw_date_text == "19-20 Juin 2026"


def test_homepage_fixture_at_wrong_url_yields_zero_events() -> None:
    parser = _get_parser()
    content = _fetched("home.html", "https://amied.ma/programme/")
    events = [event for event in parser.parse(content) if isinstance(event, ParsedEvent)]
    assert events == [], f"expected 0 events at wrong homepage url, got {len(events)}"


def test_inscriptions_fixture_at_wrong_url_yields_zero_events() -> None:
    parser = _get_parser()
    content = _fetched("inscriptions.html", "https://amied.ma/contact/")
    events = [event for event in parser.parse(content) if isinstance(event, ParsedEvent)]
    assert events == [], f"expected 0 events at wrong inscriptions url, got {len(events)}"
