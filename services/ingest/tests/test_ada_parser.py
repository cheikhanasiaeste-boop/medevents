"""Tests for parsers/ada.py using real ADA HTML fixtures."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from medevents_ingest.parsers._reset_for_tests import reset_registry
from medevents_ingest.parsers.base import FetchedContent

FIXTURES = Path(__file__).parent / "fixtures" / "ada"


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


def _get_parser():
    import importlib

    import medevents_ingest.parsers.ada as ada
    from medevents_ingest.parsers import parser_for

    importlib.reload(ada)
    return parser_for("ada_listing")


def test_parse_workshops_listing_yields_multiple_events() -> None:
    parser = _get_parser()
    content = _fetched(
        "ada-ce-live-workshops.html",
        "https://www.ada.org/education/continuing-education/ada-ce-live-workshops",
    )
    events = list(parser.parse(content))
    assert len(events) >= 3, f"expected >=3 rows, got {len(events)}"
    first = events[0]
    assert first.title
    assert first.starts_on
    assert first.source_url == content.url


def test_parse_workshops_extracts_date_range_for_june_12_13() -> None:
    parser = _get_parser()
    content = _fetched(
        "ada-ce-live-workshops.html",
        "https://www.ada.org/education/continuing-education/ada-ce-live-workshops",
    )
    events = list(parser.parse(content))
    botox = next(
        (e for e in events if "Botulinum" in e.title and e.starts_on == "2026-06-12"), None
    )
    assert botox is not None, (
        f"no June 12 Botulinum match; titles seen: {[e.title for e in events]}"
    )
    assert botox.ends_on == "2026-06-13"
    assert botox.format == "in_person"
    assert botox.event_kind == "workshop"


def test_parse_workshops_extracts_external_registration_and_location() -> None:
    parser = _get_parser()
    content = _fetched(
        "ada-ce-live-workshops.html",
        "https://www.ada.org/education/continuing-education/ada-ce-live-workshops",
    )
    events = list(parser.parse(content))
    umbria = next(
        (e for e in events if "Travel Destination" in e.title and e.starts_on == "2026-09-08"),
        None,
    )
    assert umbria is not None, (
        f"no Umbria Travel Destination match; starts_on seen: {[e.starts_on for e in events]}"
    )
    assert umbria.registration_url and umbria.registration_url.startswith("https://engage.ada.org/")
    assert umbria.city == "Umbria"
    assert umbria.country_iso == "IT"
    assert umbria.event_kind == "training"


def test_parse_scientific_session_landing_yields_single_conference_event() -> None:
    parser = _get_parser()
    content = _fetched(
        "scientific-session-landing.html",
        "https://www.ada.org/education/scientific-session",
    )
    events = list(parser.parse(content))
    assert len(events) == 1
    ev = events[0]
    assert "Scientific Session" in ev.title
    assert ev.starts_on == "2026-10-08"
    assert ev.ends_on == "2026-10-10"
    assert ev.event_kind == "conference"
    assert ev.format == "in_person"
    assert ev.city == "Indianapolis"
    assert ev.country_iso == "US"


def test_parse_non_event_hub_yields_nothing() -> None:
    parser = _get_parser()
    content = _fetched(
        "continuing-education.html",
        "https://www.ada.org/education/continuing-education",
    )
    events = list(parser.parse(content))
    assert events == []


def test_discover_yields_fixed_seed_urls() -> None:
    parser = _get_parser()
    source_stub = type(
        "S",
        (),
        {
            "crawl_config": {
                "seed_urls": [
                    "https://www.ada.org/education/continuing-education/ada-ce-live-workshops",
                    "https://www.ada.org/education/scientific-session",
                ]
            },
            "country_iso": "US",
        },
    )()
    pages = list(parser.discover(source_stub))
    urls = [p.url for p in pages]
    assert "https://www.ada.org/education/continuing-education/ada-ce-live-workshops" in urls
    assert "https://www.ada.org/education/scientific-session" in urls


def test_parse_unknown_page_yields_nothing() -> None:
    parser = _get_parser()
    content = FetchedContent(
        url="https://www.ada.org/",
        status_code=200,
        content_type="text/html",
        body=b"<html><body>no schedule, no meta</body></html>",
        fetched_at=datetime.now(UTC),
        content_hash="x",
    )
    assert list(parser.parse(content)) == []
