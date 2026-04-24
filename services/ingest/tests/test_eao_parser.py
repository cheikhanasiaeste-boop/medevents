"""Tests for parsers/eao.py using real EAO HTML fixtures."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

import pytest
from medevents_ingest.parsers._reset_for_tests import reset_registry
from medevents_ingest.parsers.base import FetchedContent, ParsedEvent, Parser

FIXTURES = Path(__file__).parent / "fixtures" / "eao"
HUB_URL = "https://eao.org/congress/"
DETAIL_URL = "https://congress.eao.org/en/"


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

    import medevents_ingest.parsers.eao as eao
    from medevents_ingest.parsers import parser_for

    importlib.reload(eao)
    return parser_for("eao_congress")


class _FakeSource:
    def __init__(self, seed_urls: list[str]) -> None:
        self.crawl_config = {"seed_urls": seed_urls}


def test_discover_yields_hub_before_detail() -> None:
    parser = _get_parser()
    source = _FakeSource([HUB_URL, DETAIL_URL])
    discovered = list(parser.discover(source))
    assert [p.url for p in discovered] == [HUB_URL, DETAIL_URL]
    assert [p.page_kind for p in discovered] == ["listing", "detail"]


def test_discover_forces_hub_first_even_if_seed_order_reversed() -> None:
    parser = _get_parser()
    source = _FakeSource([DETAIL_URL, HUB_URL])
    discovered = list(parser.discover(source))
    assert [p.url for p in discovered] == [HUB_URL, DETAIL_URL]


def test_hub_yields_three_upcoming_events() -> None:
    parser = _get_parser()
    content = _fetched("hub.html", HUB_URL)
    events = [e for e in parser.parse(content) if isinstance(e, ParsedEvent)]
    assert len(events) == 3, f"expected 3 events from hub, got {len(events)}"

    by_title = {event.title: event for event in events}
    assert sorted(by_title) == ["EAO Congress 2026", "EAO Congress 2027", "EAO Congress 2028"]

    current = by_title["EAO Congress 2026"]
    assert current.starts_on == "2026-09-24"
    assert current.ends_on == "2026-09-26"
    assert current.city == "Lisbon"
    assert current.country_iso == "PT"
    assert current.registration_url == "https://congress.eao.org/en/congress/registration"
    assert current.raw_title == "EAO Congress: Lisbon 26"
    assert current.raw_date_text == "24th - 26th September 2026"

    madrid = by_title["EAO Congress 2027"]
    assert madrid.starts_on == "2027-09-23"
    assert madrid.ends_on == "2027-09-25"
    assert madrid.city == "Madrid"
    assert madrid.country_iso == "ES"
    assert madrid.registration_url is None

    amsterdam = by_title["EAO Congress 2028"]
    assert amsterdam.starts_on == "2028-10-19"
    assert amsterdam.ends_on == "2028-10-21"
    assert amsterdam.city == "Amsterdam"
    assert amsterdam.country_iso == "NL"
    assert amsterdam.registration_url is None


def test_detail_yields_one_event_with_registration_url() -> None:
    parser = _get_parser()
    content = _fetched("homepage.html", DETAIL_URL)
    events = [e for e in parser.parse(content) if isinstance(e, ParsedEvent)]
    assert len(events) == 1, f"expected 1 event from detail page, got {len(events)}"

    event = events[0]
    assert event.title == "EAO Congress 2026"
    assert event.starts_on == "2026-09-24"
    assert event.ends_on == "2026-09-26"
    assert event.city == "Lisbon"
    assert event.country_iso == "PT"
    assert event.registration_url == "https://congress.eao.org/en/congress/registration"
    assert event.raw_title == "Homepage | Eaocongress 2026"
    assert event.raw_date_text == "24 to 26 September 2026"


def test_programme_canary_served_at_detail_url_yields_zero_events() -> None:
    parser = _get_parser()
    content = _fetched("programme-detail.html", DETAIL_URL)
    events = [e for e in parser.parse(content) if isinstance(e, ParsedEvent)]
    assert events == [], f"expected 0 events from programme canary, got {len(events)}"


def test_normalize_strips_rotating_hub_banner_dates() -> None:
    from medevents_ingest.parsers.eao import _normalize_body_for_hashing

    body_a = (
        b'const simpleBannerScriptParams={"current_date":{"date":"2026-04-24 07:23:27.089203",'
        b'"timezone_type":3,"timezone":"UTC"},"start_date":{"date":"2026-04-24 07:23:27.089208",'
        b'"timezone_type":3,"timezone":"UTC"},"end_date":{"date":"2026-04-24 07:23:27.089211",'
        b'"timezone_type":3,"timezone":"UTC"}};'
        b"<!-- Page supported by LiteSpeed Cache 7.8.1 on 2026-04-24 08:23:27 -->"
    )
    body_b = (
        b'const simpleBannerScriptParams={"current_date":{"date":"2026-04-24 07:23:27.099947",'
        b'"timezone_type":3,"timezone":"UTC"},"start_date":{"date":"2026-04-24 07:23:27.099952",'
        b'"timezone_type":3,"timezone":"UTC"},"end_date":{"date":"2026-04-24 07:23:27.099956",'
        b'"timezone_type":3,"timezone":"UTC"}};'
        b"<!-- Page supported by LiteSpeed Cache 7.8.1 on 2026-04-24 08:29:12 -->"
    )

    norm_a = _normalize_body_for_hashing(HUB_URL, body_a)
    norm_b = _normalize_body_for_hashing(HUB_URL, body_b)
    assert norm_a == norm_b, "normalized hub bodies must be identical across banner rotations"
    assert hashlib.sha256(norm_a).hexdigest() == hashlib.sha256(norm_b).hexdigest()
