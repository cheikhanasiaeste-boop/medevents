"""Tests for parsers/forum_officine.py using real source fixtures."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from medevents_ingest.parsers._reset_for_tests import reset_registry
from medevents_ingest.parsers.base import FetchedContent, ParsedEvent, Parser

FIXTURES = Path(__file__).parent / "fixtures" / "forum_officine_tn"
HOMEPAGE_URL = "https://www.forumdelofficine.tn/l_officine/accueil-forum-officine.php"
INFO_URL = "https://www.forumdelofficine.tn/l_officine/infos-pratiques-forum-officine.php"
REGISTRATION_URL = (
    "https://main.d17j5ouws4ciim.amplifyapp.com/formulaires/congressiste/"
    "3f6d7b9c1a2e4f5g6h7j8k9m0n1p2q3r"  # pragma: allowlist secret
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

    import medevents_ingest.parsers.forum_officine as forum_officine
    from medevents_ingest.parsers import parser_for

    importlib.reload(forum_officine)
    return parser_for("forum_officine_tn")


class _FakeSource:
    def __init__(self, seed_urls: list[str]) -> None:
        self.crawl_config = {"seed_urls": seed_urls}


def test_discover_yields_homepage_before_info_page() -> None:
    parser = _get_parser()
    source = _FakeSource([HOMEPAGE_URL, INFO_URL])
    discovered = list(parser.discover(source))
    assert [page.url for page in discovered] == [HOMEPAGE_URL, INFO_URL]
    assert [page.page_kind for page in discovered] == ["detail", "detail"]


def test_discover_forces_homepage_first_even_if_seed_order_reversed() -> None:
    parser = _get_parser()
    source = _FakeSource([INFO_URL, HOMEPAGE_URL])
    discovered = list(parser.discover(source))
    assert [page.url for page in discovered] == [HOMEPAGE_URL, INFO_URL]


def test_homepage_yields_one_event_with_required_fields() -> None:
    parser = _get_parser()
    content = _fetched("home.html", HOMEPAGE_URL)
    events = [event for event in parser.parse(content) if isinstance(event, ParsedEvent)]
    assert len(events) == 1, f"expected 1 event from homepage, got {len(events)}"

    event = events[0]
    assert event.title == "Forum de l'Officine 2026"
    assert event.starts_on == "2026-05-15"
    assert event.ends_on == "2026-05-16"
    assert event.timezone is None
    assert event.city == "Tunis"
    assert event.country_iso == "TN"
    assert event.venue_name == "Palais des Congres de Tunis"
    assert event.registration_url == REGISTRATION_URL
    assert event.source_url == HOMEPAGE_URL
    assert event.raw_title == "Forum de l'Officine 2026"
    assert event.raw_date_text == "15 et 16 Mai 2026"


def test_info_page_yields_one_event_with_same_canonical_source_url() -> None:
    parser = _get_parser()
    content = _fetched("infos-pratiques.html", INFO_URL)
    events = [event for event in parser.parse(content) if isinstance(event, ParsedEvent)]
    assert len(events) == 1, f"expected 1 event from info page, got {len(events)}"

    event = events[0]
    assert event.title == "Forum de l'Officine 2026"
    assert event.starts_on == "2026-05-15"
    assert event.ends_on == "2026-05-16"
    assert event.timezone is None
    assert event.city == "Tunis"
    assert event.country_iso == "TN"
    assert event.venue_name == "Palais des Congres de Tunis"
    assert event.registration_url == REGISTRATION_URL
    assert event.source_url == HOMEPAGE_URL
    assert event.raw_title == "Forum de l'Officine 2026 - Infos Pratiques"
    assert event.raw_date_text == "15-16 Mai 2026"


def test_homepage_fixture_at_wrong_url_yields_zero_events() -> None:
    parser = _get_parser()
    content = _fetched("home.html", "https://www.forumdelofficine.tn/l_officine/programme.php")
    events = [event for event in parser.parse(content) if isinstance(event, ParsedEvent)]
    assert events == [], f"expected 0 events at wrong homepage url, got {len(events)}"


def test_info_page_fixture_at_wrong_url_yields_zero_events() -> None:
    parser = _get_parser()
    content = _fetched(
        "infos-pratiques.html",
        "https://www.forumdelofficine.tn/l_officine/participer-forum-officine.php",
    )
    events = [event for event in parser.parse(content) if isinstance(event, ParsedEvent)]
    assert events == [], f"expected 0 events at wrong info-page url, got {len(events)}"
