"""Tests for parsers/morocco_dental_expo.py using real source fixtures."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

import pytest
from medevents_ingest.parsers._reset_for_tests import reset_registry
from medevents_ingest.parsers.base import FetchedContent, ParsedEvent, Parser

FIXTURES = Path(__file__).parent / "fixtures" / "morocco_dental_expo"
HOMEPAGE_URL = "https://www.mdentalexpo.ma/lang/en"
EXHIBITORS_URL = "https://www.mdentalexpo.ma/ExhibitorList"


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

    import medevents_ingest.parsers.morocco_dental_expo as morocco_dental_expo
    from medevents_ingest.parsers import parser_for

    importlib.reload(morocco_dental_expo)
    return parser_for("morocco_dental_expo")


class _FakeSource:
    def __init__(self, seed_urls: list[str]) -> None:
        self.crawl_config = {"seed_urls": seed_urls}


def test_discover_yields_homepage_before_exhibitors_page() -> None:
    parser = _get_parser()
    source = _FakeSource([HOMEPAGE_URL, EXHIBITORS_URL])
    discovered = list(parser.discover(source))
    assert [page.url for page in discovered] == [HOMEPAGE_URL, EXHIBITORS_URL]
    assert [page.page_kind for page in discovered] == ["detail", "detail"]


def test_discover_forces_homepage_first_even_if_seed_order_reversed() -> None:
    parser = _get_parser()
    source = _FakeSource([EXHIBITORS_URL, HOMEPAGE_URL])
    discovered = list(parser.discover(source))
    assert [page.url for page in discovered] == [HOMEPAGE_URL, EXHIBITORS_URL]


def test_homepage_yields_one_event_with_registration_url() -> None:
    parser = _get_parser()
    content = _fetched("homepage.html", HOMEPAGE_URL)
    events = [event for event in parser.parse(content) if isinstance(event, ParsedEvent)]
    assert len(events) == 1, f"expected 1 event from homepage, got {len(events)}"

    event = events[0]
    assert event.title == "Morocco Dental Expo 2026"
    assert event.starts_on == "2026-05-07"
    assert event.ends_on == "2026-05-10"
    assert event.timezone is None
    assert event.city == "Casablanca"
    assert event.country_iso == "MA"
    assert event.venue_name is None
    assert event.registration_url == "https://www.mdentalexpo.ma/form/2749?cat=VISITOR"
    assert event.source_url == HOMEPAGE_URL
    assert event.raw_title == "DENTAL EXPO 2026"
    assert event.raw_date_text == "07 to 10 May 2026"


def test_exhibitors_page_yields_one_event_with_same_canonical_source_url() -> None:
    parser = _get_parser()
    content = _fetched("exhibitor-list.html", EXHIBITORS_URL)
    events = [event for event in parser.parse(content) if isinstance(event, ParsedEvent)]
    assert len(events) == 1, f"expected 1 event from exhibitors page, got {len(events)}"

    event = events[0]
    assert event.title == "Morocco Dental Expo 2026"
    assert event.starts_on == "2026-05-07"
    assert event.ends_on == "2026-05-10"
    assert event.timezone is None
    assert event.city == "Casablanca"
    assert event.country_iso == "MA"
    assert event.venue_name == "ICEC AIN SEBAA"
    assert event.registration_url is None
    assert event.source_url == HOMEPAGE_URL
    assert event.raw_title == "Exposants MOROCCO DENTAL EXPO 2026"
    assert event.raw_date_text == "Du 07/05/2026 au 10/05/2026"


def test_homepage_fixture_at_wrong_url_yields_zero_events() -> None:
    parser = _get_parser()
    content = _fetched("homepage.html", "https://www.mdentalexpo.ma/lang/en/other-page")
    events = [event for event in parser.parse(content) if isinstance(event, ParsedEvent)]
    assert events == [], f"expected 0 events at wrong homepage url, got {len(events)}"


def test_exhibitors_fixture_at_wrong_url_yields_zero_events() -> None:
    parser = _get_parser()
    content = _fetched("exhibitor-list.html", "https://www.mdentalexpo.ma/Page/9332/exposants-2026")
    events = [event for event in parser.parse(content) if isinstance(event, ParsedEvent)]
    assert events == [], f"expected 0 events at wrong exhibitors url, got {len(events)}"


def test_normalize_strips_rotating_aspnet_hidden_fields() -> None:
    from medevents_ingest.parsers.morocco_dental_expo import _normalize_body_for_hashing

    body_a = (
        b'<input type="hidden" name="__VIEWSTATE" id="__VIEWSTATE" value="aaa" />'
        b'<input type="hidden" name="__EVENTVALIDATION" id="__EVENTVALIDATION" value="bbb" />'
        b'<input type="hidden" name="ctl00$LogFormTop$hfac" id="hfac" value="ccc" />'
    )
    body_b = (
        b'<input type="hidden" name="__VIEWSTATE" id="__VIEWSTATE" value="xxx" />'
        b'<input type="hidden" name="__EVENTVALIDATION" id="__EVENTVALIDATION" value="yyy" />'
        b'<input type="hidden" name="ctl00$LogFormTop$hfac" id="hfac" value="zzz" />'
    )

    norm_a = _normalize_body_for_hashing(body_a)
    norm_b = _normalize_body_for_hashing(body_b)
    assert norm_a == norm_b
    assert hashlib.sha256(norm_a).hexdigest() == hashlib.sha256(norm_b).hexdigest()
