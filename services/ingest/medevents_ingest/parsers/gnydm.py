"""GNYDM source parser (`parser_name: gnydm_listing`).

Handles two page shapes via one parse() entry point:

    1. Future-meetings listing (`/about/future-meetings/`) -> N events (one per year edition)
    2. Homepage detail (`/`)                               -> 1 event (current edition)
    3. Anything else (about-gnydm canary, arbitrary URL)   -> 0 events

The detail classifier requires ALL of:
  - content.url matches the seeded homepage URL (trailing-slash-normalized)
  - `h1.swiper-title` element present (hero-carousel signal)
  - Meeting Dates line parseable
  - Venue block present
  - Edition year extractable from a `/images/logo-YYYY.png` asset
    (content-derived year; avoids clock-dependent fallback)

See docs/superpowers/specs/2026-04-21-medevents-w3-1-second-source-gnydm.md §4.

GNYDM serves byte-stable HTML per the byte-stability review in
docs/runbooks/gnydm-fixtures.md, so the default fetch.fetch_url + plain
sha-256 content_hash are sufficient. No Sitecore-style normalization hook.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from typing import Any

from bs4 import BeautifulSoup, Tag

from ..normalize import parse_date_range
from . import register_parser
from .base import DiscoveredPage, FetchedContent, ParsedEvent, SourcePageRef

LISTING_URL = "https://www.gnydm.com/about/future-meetings/"
HOMEPAGE_URL = "https://www.gnydm.com/"

_VENUE_NAME = "Jacob K. Javits Convention Center"
_VENUE_UPPER = "JACOB K. JAVITS CONVENTION CENTER"
_ORGANIZER = "Greater New York Dental Meeting"
_CITY = "New York"
_COUNTRY_ISO = "US"


def _url_matches_homepage(url: str) -> bool:
    """Trailing-slash-normalized equality against HOMEPAGE_URL."""
    return url.rstrip("/") == HOMEPAGE_URL.rstrip("/")


@register_parser("gnydm_listing")
class GnydmListingParser:
    name = "gnydm_listing"

    def discover(self, source: Any) -> Iterator[DiscoveredPage]:
        """Yield listing first, detail second — order matters for precedence.

        The pipeline's `_diff_event_fields` merges new candidates onto an
        existing event via last-write-wins. Yielding listing first guarantees
        the detail candidate is processed second, so detail-over-listing
        precedence holds without any new branching in pipeline.py.
        """
        urls: set[str] = set(source.crawl_config.get("seed_urls", []))
        if LISTING_URL in urls:
            yield DiscoveredPage(url=LISTING_URL, page_kind="listing")
        if HOMEPAGE_URL in urls:
            yield DiscoveredPage(url=HOMEPAGE_URL, page_kind="detail")

    def fetch(self, page: SourcePageRef) -> FetchedContent:  # pragma: no cover - wired by pipeline
        from ..fetch import fetch_url, make_default_client

        with make_default_client() as client:
            return fetch_url(
                page.url,
                client=client,
                user_agent=(
                    "MedEvents-crawler "
                    "(https://github.com/cheikhanasiaeste-boop/medevents; "
                    "contact: cheikhanas.iaeste@gmail.com)"
                ),
            )

    def parse(self, content: FetchedContent) -> Iterator[ParsedEvent]:
        soup = BeautifulSoup(content.body, "lxml")

        if content.url.rstrip("/") == LISTING_URL.rstrip("/"):
            yield from _parse_listing(content, soup)
            return

        if _url_matches_homepage(content.url) and _looks_like_homepage(soup):
            ev = _parse_homepage(content, soup)
            if ev is not None:
                yield ev
            return

        return  # canary / unrecognized URL


def _looks_like_homepage(soup: BeautifulSoup) -> bool:
    """True only when an `h1.swiper-title` hero element is present."""
    return soup.select_one("h1.swiper-title") is not None


def _parse_listing(content: FetchedContent, soup: BeautifulSoup) -> Iterator[ParsedEvent]:
    """Walk `<p><strong>{year}</strong></p>` headers + sibling Meeting-Dates paragraphs."""
    for strong in soup.find_all("strong"):
        if not isinstance(strong, Tag):
            continue
        year_text = strong.get_text(strip=True)
        if not re.fullmatch(r"20\d{2}", year_text):
            continue

        # The <strong> wraps the year inside a <p>. The Meeting-Dates paragraph
        # is the next <p> sibling of that wrapping <p>.
        header_p = strong.find_parent("p")
        if not isinstance(header_p, Tag):
            continue
        sibling_p = header_p.find_next_sibling("p")
        if not isinstance(sibling_p, Tag):
            continue

        # The sibling <p> contains "Meeting Dates: ...<br>Exhibit Dates: ..."
        # Extract with "\n" as the line separator so we can discard the Exhibit line.
        sibling_text = sibling_p.get_text("\n", strip=True)
        meeting_line = next(
            (ln for ln in sibling_text.split("\n") if ln.startswith("Meeting Dates:")),
            None,
        )
        if meeting_line is None:
            continue
        raw_date = meeting_line[len("Meeting Dates:") :].strip()

        year = int(year_text)
        d = parse_date_range(raw_date, page_year=year)
        if d is None:
            continue

        yield ParsedEvent(
            title=f"{_ORGANIZER} {year}",
            summary=None,
            starts_on=d.starts_on.isoformat(),
            ends_on=d.ends_on.isoformat() if d.ends_on else None,
            timezone=None,
            city=_CITY,
            country_iso=_COUNTRY_ISO,
            venue_name=_VENUE_NAME,
            format="in_person",
            event_kind="conference",
            lifecycle_status="active",
            specialty_codes=[],
            organizer_name=_ORGANIZER,
            source_url=content.url,
            registration_url=None,
            raw_title=f"{year_text} · {meeting_line}",
            raw_date_text=raw_date,
        )


def _extract_year_from_logo(soup: BeautifulSoup) -> int | None:
    """Homepage carries the edition year in the logo asset's filename
    (e.g. `/images/logo-2026.png`). Verified present on the current fixture
    at lines 293, 679, 680, 685 of tests/fixtures/gnydm/homepage.html.

    Content-derived and clock-independent. If the pattern ever disappears
    this returns None -> zero events, which the canary / template-drift
    tests will surface as parser maintenance rather than a silent mis-year.
    """
    for img in soup.find_all("img"):
        if not isinstance(img, Tag):
            continue
        src = img.get("src") or ""
        if not isinstance(src, str):
            continue
        m = re.search(r"/images/logo-(20\d{2})\.png", src)
        if m:
            return int(m.group(1))
    return None


def _swiper_title_text(soup: BeautifulSoup) -> str | None:
    """Return the text content of the ``h1.swiper-title`` element, or None if empty.

    The detail classifier already requires this element to be present, so by
    the time ``_parse_homepage`` is called the element is guaranteed to exist.
    We still guard against an empty text node so the caller can fall back to
    the synthesised title rather than storing an empty string as provenance.
    """
    el = soup.select_one("h1.swiper-title")
    if el is None:
        return None
    text = el.get_text(strip=True)
    return text if text else None


def _parse_homepage(content: FetchedContent, soup: BeautifulSoup) -> ParsedEvent | None:
    """Extract the current edition from the homepage Meeting-Dates line.

    Preconditions already checked by the caller (`parse`): content.url
    matches the seeded homepage URL AND `h1.swiper-title` is present. This
    function additionally requires — all must hold — the Meeting-Dates line,
    the venue block, and a content-derived year extracted from an
    `<img src=".../images/logo-YYYY.png">` asset. If any signal is missing
    the function returns None (emitting zero events). No wall-clock fallback:
    the year comes from the page or not at all.
    """
    # Locate the text node "Meeting Dates: …" and extract the full date string
    # via get_text("") on its parent element. Using get_text("\n", strip=True)
    # on the whole soup breaks ordinal-suffix superscripts (e.g. <sup>th</sup>)
    # onto separate lines, yielding "November 27" instead of
    # "November 27th - December 1st".
    meeting_node = soup.find(string=lambda t: t and "Meeting Dates:" in t)
    if meeting_node is None or not isinstance(meeting_node.parent, Tag):
        return None
    raw_date = (
        meeting_node.parent.get_text("").split("Meeting Dates:", 1)[1].split("Exhibit")[0].strip()
    )

    body_text = soup.get_text("\n", strip=True)
    if _VENUE_UPPER not in body_text.upper():
        return None

    year = _extract_year_from_logo(soup)
    if year is None:
        return None

    d = parse_date_range(raw_date, page_year=year)
    if d is None:
        return None

    return ParsedEvent(
        title=f"{_ORGANIZER} {year}",
        summary=None,
        starts_on=d.starts_on.isoformat(),
        ends_on=d.ends_on.isoformat() if d.ends_on else None,
        timezone=None,
        city=_CITY,
        country_iso=_COUNTRY_ISO,
        venue_name=_VENUE_NAME,
        format="in_person",
        event_kind="conference",
        lifecycle_status="active",
        specialty_codes=[],
        organizer_name=_ORGANIZER,
        source_url=content.url,
        registration_url=None,
        raw_title=_swiper_title_text(soup) or f"{_ORGANIZER} {year}",
        raw_date_text=raw_date,
    )
