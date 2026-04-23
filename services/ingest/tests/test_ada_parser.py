"""Tests for parsers/ada.py using real ADA HTML fixtures."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

import pytest
from medevents_ingest.parsers._reset_for_tests import reset_registry
from medevents_ingest.parsers.ada import _normalize_body_for_hashing
from medevents_ingest.parsers.base import (
    FetchedContent,
    ParsedEvent,
    Parser,
    ParserReviewRequest,
)

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


def _get_parser() -> Parser:
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
    events = [e for e in parser.parse(content) if isinstance(e, ParsedEvent)]
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
    events = [e for e in parser.parse(content) if isinstance(e, ParsedEvent)]
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
    events = [e for e in parser.parse(content) if isinstance(e, ParsedEvent)]
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
    events = [e for e in parser.parse(content) if isinstance(e, ParsedEvent)]
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
    # The continuing-education hub page reuses the `cel22airwaves-left` table
    # widget, so `_looks_like_workshops_schedule` admits it. The hub's rows
    # don't carry a page-year inference anchor, so every row's date parse
    # returns None and the parser yields zero ParsedEvents — plus (after
    # W3.2g) a ParserReviewRequest surfacing the silent drops.
    yielded = list(parser.parse(content))
    events = [y for y in yielded if isinstance(y, ParsedEvent)]
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


class TestNormalizeBodyForHashing:
    """ADA serves rotating Sitecore tracking attributes per request.

    These tests pin that _normalize_body_for_hashing collapses two pages that
    differ ONLY in those attributes to the same hash, so the pipeline's
    content-hash skip gate actually fires on unchanged pages.
    """

    def test_identical_bodies_hash_identically(self) -> None:
        body = (FIXTURES / "scientific-session-landing.html").read_bytes()
        h1 = hashlib.sha256(_normalize_body_for_hashing(body)).hexdigest()
        h2 = hashlib.sha256(_normalize_body_for_hashing(body)).hexdigest()
        assert h1 == h2

    def test_bodies_differing_only_in_sitecore_trackers_hash_identically(self) -> None:
        body_a = (
            b"<html><body>"
            b"<div data-sc-page-name='one' data-sc-item-uri='sitecore://web/{AAA}?lang=en&ver=1'>"
            b"  <p>stable content</p>"
            b"</div>"
            b'<script>itemUri: "sitecore://web/{AAA}?lang=en&ver=1",</script>'
            b"</body></html>"
        )
        body_b = (
            b"<html><body>"
            b"<div data-sc-page-name='two' data-sc-item-uri='sitecore://web/{BBB}?lang=en&ver=7'>"
            b"  <p>stable content</p>"
            b"</div>"
            b'<script>itemUri: "sitecore://web/{BBB}?lang=en&ver=7",</script>'
            b"</body></html>"
        )
        assert body_a != body_b  # raw bytes differ
        h_a = hashlib.sha256(_normalize_body_for_hashing(body_a)).hexdigest()
        h_b = hashlib.sha256(_normalize_body_for_hashing(body_b)).hexdigest()
        assert h_a == h_b

    def test_bodies_differing_in_real_content_do_not_collide(self) -> None:
        body_a = b"<html><body><h1>ADA 2026 Scientific Session</h1></body></html>"
        body_b = b"<html><body><h1>ADA 2027 Scientific Session</h1></body></html>"
        h_a = hashlib.sha256(_normalize_body_for_hashing(body_a)).hexdigest()
        h_b = hashlib.sha256(_normalize_body_for_hashing(body_b)).hexdigest()
        assert h_a != h_b


def test_ada_parser_emits_parser_failure_when_row_drops_silently() -> None:
    """Spec §7 drift-observability: when `_row_to_event` returns None for one
    or more rows, the ADA parser yields a `ParserReviewRequest(kind=
    'parser_failure')` at end-of-stream with per-reason counts so the
    pipeline can record the drift as a review_item instead of letting it
    pass silently.
    """
    parser = _get_parser()
    # Two-row fixture: row 1 valid (yields 1 ParsedEvent), row 2 broken
    # (empty href trips `_row_to_event`'s line-237 empty-href guard).
    body = (
        b"<html><head><title>ADA 2026 CE Workshops</title></head><body>"
        b'<table class="cel22airwaves"><tbody>'
        b"<tr>"
        b'<td class="cel22airwaves-left">June 12&ndash;13</td>'
        b'<td class="cel22airwaves-right">'
        b'<a href="/education/continuing-education/ada-ce-live-workshops/botox">'
        b"Botulinum Toxins Workshop</a>"
        b"</td>"
        b"</tr>"
        b"<tr>"
        b'<td class="cel22airwaves-left">Sept. 11&ndash;12</td>'
        b'<td class="cel22airwaves-right">'
        b'<a href="">Broken Row With Empty Href</a>'
        b"</td>"
        b"</tr>"
        b"</tbody></table></body></html>"
    )
    content = FetchedContent(
        url="https://www.ada.org/education/continuing-education/ada-ce-live-workshops",
        status_code=200,
        content_type="text/html; charset=utf-8",
        body=body,
        fetched_at=datetime.now(UTC),
        content_hash="fixture-hash",
    )

    yielded = list(parser.parse(content))
    events = [y for y in yielded if isinstance(y, ParsedEvent)]
    reviews = [y for y in yielded if isinstance(y, ParserReviewRequest)]

    assert len(events) == 1, f"expected 1 valid event, got {len(events)}: {yielded}"
    assert events[0].starts_on == "2026-06-12"

    assert len(reviews) == 1, f"expected 1 ParserReviewRequest, got {len(reviews)}"
    rr = reviews[0]
    assert rr.kind == "parser_failure"
    assert rr.details["rows_seen"] == 2
    assert rr.details["rows_yielded"] == 1
    assert rr.details["reason"] == "silent_drops_detected"
    assert rr.details["drops_by_reason"]["empty_href"] == 1
    # Other reasons must be zero so the signal is unambiguous.
    assert rr.details["drops_by_reason"]["anchor_missing"] == 0
    assert rr.details["drops_by_reason"]["empty_title"] == 0
    assert rr.details["drops_by_reason"]["unsupported_scheme"] == 0
    assert rr.details["drops_by_reason"]["date_parse_fail"] == 0
