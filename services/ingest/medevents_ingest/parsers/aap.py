"""AAP Annual Meeting source parser (`parser_name: aap_annual_meeting`).

Handles two page shapes via one parse() entry point:

    1. Homepage (`https://am2026.perio.org/`)                -> 1 event (title, dates, city)
    2. General-information (`…/general-information/`)         -> 1 event (+ venue_name)
    3. Anything else (housing canary, schedule, arbitrary URL) -> 0 events

The detail classifier for the homepage requires ALL of:
  - content.url matches HOMEPAGE_URL (trailing-slash-normalized)
  - og:title equals the canonical homepage og:title exactly
  - meta description contains 'AAP 112th Annual Meeting' (edition signal)
  - meta description contains a parseable date range

The detail classifier for general-information requires:
  - content.url matches GENERAL_INFO_URL (trailing-slash-normalized)
  - body contains the venue phrase 'Seattle Convention Center, Arch Building'
  - meta description contains a parseable date range

Edition-year tripwire (D7): if the homepage <title> does not contain
'Annual Meeting 2026', parse returns zero events.  When am2027.perio.org
launches with 'Annual Meeting 2027' the stale seed triggers zero events and
the W3.2c canary fires.

`_normalize_body_for_hashing` strips Cloudflare email-obfuscation attributes
and data-dbsrc base64 attrs before sha-256.  fetch() applies this before
computing content_hash, identical to parsers/ada.py::fetch.

See docs/superpowers/specs/2026-04-23-medevents-w3-2e-aap-annual-meeting.md
and docs/runbooks/aap-fixtures.md.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterator
from typing import Any

from bs4 import BeautifulSoup, Tag

from ..normalize import parse_date_range
from . import register_parser
from .base import DiscoveredPage, FetchedContent, ParsedEvent, SourcePageRef

HOMEPAGE_URL = "https://am2026.perio.org/"
GENERAL_INFO_URL = "https://am2026.perio.org/general-information/"

_TITLE_CANONICAL = "AAP 2026 Annual Meeting"
_RAW_TITLE = "American Academy of Periodontology - Annual Meeting 2026"
# The exact og:title on the homepage; used to reject same-template non-event pages.
_HOMEPAGE_OG_TITLE = "American Academy of Periodontology - Annual Meeting 2026"
# Edition signal in the meta description -- stable for the 2026 microsite.
_EDITION_SIGNAL = "AAP 112th Annual Meeting"
# Venue phrase extracted from /general-information/.
_VENUE_NAME = "Seattle Convention Center, Arch Building"
_CITY = "Seattle"
_COUNTRY_ISO = "US"
_ORGANIZER = "American Academy of Periodontology"
# Hardcoded year for the D7 tripwire.
_EDITION_YEAR = 2026
_EDITION_YEAR_STR = "Annual Meeting 2026"

# ---------------------------------------------------------------------------
# Normalisation regexes (spec §4, prep §5.2)
# ---------------------------------------------------------------------------
_CFEMAIL_ATTR_RE = re.compile(rb'\s*data-cfemail="[0-9a-f]+"')
_CFEMAIL_HREF_RE = re.compile(rb"/cdn-cgi/l/email-protection#[0-9a-f]+")
_DBSRC_ATTR_RE = re.compile(rb'\s*data-dbsrc="[A-Za-z0-9+/=]+"')

# Date-range pattern extracted from the meta description.
# Accepts en-dash (\u2013), em-dash (\u2014), and ASCII hyphen as separators --
# same set as normalize.py's _DASH.  Using \u escapes (not literal Unicode
# characters) avoids RUF001/RUF003 ruff violations.
_DATE_RANGE_RE = re.compile(
    r"((?:[A-Za-z]+\.?\s+\d{1,2}[\u2013\u2014\-](?:[A-Za-z]+\.?\s+)?\d{1,2}(?:,\s*\d{4})?))"
)


def _normalize_body_for_hashing(body: bytes) -> bytes:
    """Strip per-request rotating content so content_hash reflects only the
    data we care about.

    See docs/runbooks/aap-fixtures.md §5.2 for the root-cause analysis of
    Cloudflare's email-obfuscation rotation and the base64 data-dbsrc
    attribute on the homepage. Same class of problem as ADA's Sitecore
    attribute rotation (parsers/ada.py::_normalize_body_for_hashing).
    """
    body = _CFEMAIL_ATTR_RE.sub(b"", body)
    body = _CFEMAIL_HREF_RE.sub(b"/cdn-cgi/l/email-protection", body)
    body = _DBSRC_ATTR_RE.sub(b"", body)
    return body


@register_parser("aap_annual_meeting")
class AapAnnualMeetingParser:
    name = "aap_annual_meeting"

    def discover(self, source: Any) -> Iterator[DiscoveredPage]:
        """Yield homepage first, general-information second (spec §3 D6).

        Both pages are page_kind='detail'; there is no listing/detail hierarchy.
        Deterministic order ensures last-write-wins semantics produce the
        correct venue_name from the general-information page.
        """
        urls: set[str] = set(source.crawl_config.get("seed_urls", []))
        if HOMEPAGE_URL in urls:
            yield DiscoveredPage(url=HOMEPAGE_URL, page_kind="detail")
        if GENERAL_INFO_URL in urls:
            yield DiscoveredPage(url=GENERAL_INFO_URL, page_kind="detail")

    def fetch(self, page: SourcePageRef) -> FetchedContent:  # pragma: no cover - wired by pipeline
        from ..fetch import fetch_url, make_default_client

        with make_default_client() as client:
            fc = fetch_url(
                page.url,
                client=client,
                user_agent=(
                    "MedEvents-crawler "
                    "(https://github.com/cheikhanasiaeste-boop/medevents; "
                    "contact: cheikhanas.iaeste@gmail.com)"
                ),
            )
        stable_hash = hashlib.sha256(_normalize_body_for_hashing(fc.body)).hexdigest()
        return FetchedContent(
            url=fc.url,
            status_code=fc.status_code,
            content_type=fc.content_type,
            body=fc.body,
            fetched_at=fc.fetched_at,
            content_hash=stable_hash,
        )

    def parse(self, content: FetchedContent) -> Iterator[ParsedEvent]:
        soup = BeautifulSoup(content.body, "lxml")

        if content.url.rstrip("/") == HOMEPAGE_URL.rstrip("/"):
            ev = _parse_homepage(content, soup)
            if ev is not None:
                yield ev
            return

        if content.url.rstrip("/") == GENERAL_INFO_URL.rstrip("/"):
            ev = _parse_general_info(content, soup)
            if ev is not None:
                yield ev
            return

        return  # canary / unrecognized URL


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _get_og_title(soup: BeautifulSoup) -> str | None:
    """Return the og:title meta content, or None."""
    tag = soup.find("meta", attrs={"property": "og:title"})
    if not isinstance(tag, Tag):
        return None
    val = tag.get("content")
    return val if isinstance(val, str) else None


def _get_meta_description(soup: BeautifulSoup) -> str | None:
    """Return the meta description content, or None."""
    tag = soup.find("meta", attrs={"name": "description"})
    if not isinstance(tag, Tag):
        return None
    val = tag.get("content")
    return val if isinstance(val, str) else None


def _get_page_title(soup: BeautifulSoup) -> str | None:
    """Return the text of the <title> element, or None."""
    title_tag = soup.find("title")
    if not isinstance(title_tag, Tag):
        return None
    text = title_tag.get_text(strip=True)
    return text if text else None


def _parse_homepage(content: FetchedContent, soup: BeautifulSoup) -> ParsedEvent | None:
    """Extract event data from the AAP 2026 homepage.

    Classifier requires:
      1. <title> contains _EDITION_YEAR_STR (D7 tripwire).
      2. og:title equals _HOMEPAGE_OG_TITLE exactly.
      3. meta description contains _EDITION_SIGNAL.
      4. meta description contains a parseable date range.
    """
    # D7: hardcoded year tripwire
    page_title = _get_page_title(soup)
    if page_title is None or _EDITION_YEAR_STR not in page_title:
        return None

    # og:title must match the canonical homepage og:title exactly
    og_title = _get_og_title(soup)
    if og_title != _HOMEPAGE_OG_TITLE:
        return None

    # meta description must contain the edition signal
    desc = _get_meta_description(soup)
    if desc is None or _EDITION_SIGNAL not in desc:
        return None

    # Parse the date range from meta description.
    # Meta description contains dates like "Oct. 29-Nov. 1, 2026" (any dash variant).
    date_match = _DATE_RANGE_RE.search(desc)
    if not date_match:
        return None
    raw_date = date_match.group(1).strip()
    d = parse_date_range(raw_date, page_year=_EDITION_YEAR)
    if d is None:
        return None

    return ParsedEvent(
        title=_TITLE_CANONICAL,
        summary=None,
        starts_on=d.starts_on.isoformat(),
        ends_on=d.ends_on.isoformat() if d.ends_on else None,
        timezone=None,
        city=_CITY,
        country_iso=_COUNTRY_ISO,
        venue_name=None,
        format="in_person",
        event_kind="conference",
        lifecycle_status="active",
        specialty_codes=[],
        organizer_name=_ORGANIZER,
        source_url=content.url,
        registration_url=None,
        raw_title=_RAW_TITLE,
        raw_date_text=raw_date,
    )


def _parse_general_info(content: FetchedContent, soup: BeautifulSoup) -> ParsedEvent | None:
    """Extract event data (including venue) from the general-information page.

    Classifier requires:
      1. Body contains _VENUE_NAME.
      2. meta description contains a parseable date range.
    """
    body_text = soup.get_text(" ", strip=True)
    if _VENUE_NAME not in body_text:
        return None

    desc = _get_meta_description(soup)
    if desc is None:
        return None

    date_match = _DATE_RANGE_RE.search(desc)
    if not date_match:
        return None
    raw_date = date_match.group(1).strip()
    d = parse_date_range(raw_date, page_year=_EDITION_YEAR)
    if d is None:
        return None

    return ParsedEvent(
        title=_TITLE_CANONICAL,
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
        raw_title=_RAW_TITLE,
        raw_date_text=raw_date,
    )
