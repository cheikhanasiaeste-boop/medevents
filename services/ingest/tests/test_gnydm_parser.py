"""Tests for parsers/gnydm.py using real GNYDM HTML fixtures.

Mirrors the test_ada_parser.py pattern: each test reloads the gnydm parser
module into a fresh registry so test ordering does not matter.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from medevents_ingest.parsers._reset_for_tests import reset_registry
from medevents_ingest.parsers.base import FetchedContent

FIXTURES = Path(__file__).parent / "fixtures" / "gnydm"
LISTING_URL = "https://www.gnydm.com/about/future-meetings/"
HOMEPAGE_URL = "https://www.gnydm.com/"
ABOUT_URL = "https://www.gnydm.com/about/about-gnydm/"


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

    import medevents_ingest.parsers.gnydm as gnydm
    from medevents_ingest.parsers import parser_for

    importlib.reload(gnydm)
    return parser_for("gnydm_listing")


class _FakeSource:
    def __init__(self, seed_urls: list[str]) -> None:
        self.crawl_config = {"seed_urls": seed_urls}


def test_discover_yields_listing_before_detail() -> None:
    parser = _get_parser()
    source = _FakeSource([LISTING_URL, HOMEPAGE_URL])
    discovered = list(parser.discover(source))
    assert [p.url for p in discovered] == [LISTING_URL, HOMEPAGE_URL]
    assert [p.page_kind for p in discovered] == ["listing", "detail"]


def test_discover_forces_listing_first_even_if_seed_order_reversed() -> None:
    """Precedence mechanism: listing MUST be processed before detail so the
    pipeline's last-write-wins update lets the detail candidate win on a
    disagreement. discover() therefore forces the order regardless of how
    seed_urls are listed in sources.yaml."""
    parser = _get_parser()
    source = _FakeSource([HOMEPAGE_URL, LISTING_URL])
    discovered = list(parser.discover(source))
    kinds = [p.page_kind for p in discovered]
    assert kinds.index("listing") < kinds.index("detail"), (
        "listing must appear before detail in discover order"
    )


def test_listing_yields_three_editions_with_correct_dates() -> None:
    parser = _get_parser()
    content = _fetched("future-meetings.html", LISTING_URL)
    events = list(parser.parse(content))
    assert len(events) == 3, f"expected 3 editions, got {len(events)}"
    by_year = {e.starts_on[:4]: e for e in events}
    assert by_year["2026"].starts_on == "2026-11-27"
    assert by_year["2026"].ends_on == "2026-12-01"
    assert by_year["2027"].starts_on == "2027-11-26"
    assert by_year["2027"].ends_on == "2027-11-30"
    assert by_year["2028"].starts_on == "2028-11-24"
    assert by_year["2028"].ends_on == "2028-11-28"


def test_listing_events_have_required_fields_populated() -> None:
    parser = _get_parser()
    content = _fetched("future-meetings.html", LISTING_URL)
    events = list(parser.parse(content))
    for e in events:
        year = e.starts_on[:4]
        assert e.title == f"Greater New York Dental Meeting {year}"
        assert e.city == "New York"
        assert e.country_iso == "US"
        assert e.venue_name == "Jacob K. Javits Convention Center"
        assert e.format == "in_person"
        assert e.event_kind == "conference"
        assert e.lifecycle_status == "active"
        assert e.organizer_name == "Greater New York Dental Meeting"
        assert e.source_url == LISTING_URL
        assert e.summary is None
        assert e.raw_title is not None
        assert e.raw_date_text is not None


def test_homepage_yields_one_event_for_current_edition() -> None:
    parser = _get_parser()
    content = _fetched("homepage.html", HOMEPAGE_URL)
    events = list(parser.parse(content))
    assert len(events) == 1
    e = events[0]
    assert e.title == "Greater New York Dental Meeting 2026"
    assert e.starts_on == "2026-11-27"
    assert e.ends_on == "2026-12-01"
    assert e.source_url == HOMEPAGE_URL
    assert e.summary is None


def test_about_gnydm_fixture_yields_zero_events_at_detail_url() -> None:
    """Detail classifier must reject about-gnydm even if content.url is the
    seeded homepage URL, because `h1.swiper-title` is absent."""
    parser = _get_parser()
    content = _fetched("about-gnydm.html", HOMEPAGE_URL)
    events = list(parser.parse(content))
    assert events == []


def test_about_gnydm_fixture_yields_zero_events_at_about_url() -> None:
    """Detail classifier must reject about-gnydm at its own URL (URL anchor
    fails) AND listing classifier must not recognize it (no year `<strong>`
    headers followed by Meeting Dates siblings)."""
    parser = _get_parser()
    content = _fetched("about-gnydm.html", ABOUT_URL)
    events = list(parser.parse(content))
    assert events == []


def test_homepage_at_wrong_url_yields_zero_events() -> None:
    """URL anchor guard: homepage markup fetched at a non-homepage URL must
    not be classified as detail."""
    parser = _get_parser()
    content = _fetched("homepage.html", "https://www.gnydm.com/some/other/path")
    events = list(parser.parse(content))
    assert events == []


def test_homepage_year_extracted_from_logo_image() -> None:
    """The edition year MUST derive from homepage content (the
    `/images/logo-YYYY.png` asset), not from the system clock. This makes
    parser output deterministic across calendar time. The current fixture
    carries `logo-2026.png`, so the 2026 edition is what we expect.
    Spec §4 detail classifier, condition 5."""
    parser = _get_parser()
    content = _fetched("homepage.html", HOMEPAGE_URL)
    events = list(parser.parse(content))
    assert len(events) == 1
    assert events[0].starts_on == "2026-11-27"
    assert events[0].title == "Greater New York Dental Meeting 2026"


def test_homepage_without_logo_yields_zero_events() -> None:
    """Fifth detail-classifier condition: if no `/images/logo-YYYY.png`
    asset is present on the page, the year cannot be derived and the
    parser must emit zero events rather than guessing from the clock."""
    import re as _re

    parser = _get_parser()
    body = (FIXTURES / "homepage.html").read_bytes()
    # Strip every logo-YYYY.png <img>; leaves the page otherwise intact,
    # so h1.swiper-title + meeting-dates line + venue block still pass.
    stripped = _re.sub(
        rb'<img[^>]*src="[^"]*/images/logo-20\d{2}\.png"[^>]*>',
        b"",
        body,
    )
    content = FetchedContent(
        url=HOMEPAGE_URL,
        status_code=200,
        content_type="text/html; charset=utf-8",
        body=stripped,
        fetched_at=datetime.now(UTC),
        content_hash="fixture-hash-no-logo",
    )
    events = list(parser.parse(content))
    assert events == []
