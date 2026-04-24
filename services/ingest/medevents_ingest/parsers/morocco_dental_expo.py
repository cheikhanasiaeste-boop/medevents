"""Morocco Dental Expo source parser (`parser_name: morocco_dental_expo`).

Handles two public source surfaces via one parse() entry point:

    1. English homepage (`https://www.mdentalexpo.ma/lang/en`) -> 1 event
    2. Exhibitor list (`https://www.mdentalexpo.ma/ExhibitorList`) -> 1 event
    3. Anything else                                             -> 0 events

The onboarding is intentionally edition-specific for 2026. Both captured pages
rotate ASP.NET hidden-field values (`__VIEWSTATE`, `__EVENTVALIDATION`, and
homepage-only `hfac`) on every request, so fetch() normalizes those values
before computing `content_hash`. The parser itself ignores those fields.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterator
from datetime import datetime
from typing import Any

from bs4 import BeautifulSoup, Tag

from . import register_parser
from .base import DiscoveredPage, FetchedContent, ParsedEvent, SourcePageRef

HOMEPAGE_URL = "https://www.mdentalexpo.ma/lang/en"
EXHIBITORS_URL = "https://www.mdentalexpo.ma/ExhibitorList"
REGISTRATION_URL = "https://www.mdentalexpo.ma/form/2749?cat=VISITOR"

_TITLE = "Morocco Dental Expo 2026"
_RAW_TITLE_HOMEPAGE = "DENTAL EXPO 2026"
_RAW_TITLE_EXHIBITORS = "Exposants MOROCCO DENTAL EXPO 2026"
_HOMEPAGE_PAGE_TITLE = "Dental Expo  - Home Page - DENTAL EXPO 2026"
_EXHIBITORS_PAGE_TITLE = "Exposants MOROCCO DENTAL EXPO 2026"
_HOMEPAGE_SECTION_TITLE = "PROFESSIONAL EXHIBITION AND SCIENTIFIC FORUM"
_HOMEPAGE_DATE_TEXT = "07 to 10 May 2026"
_ORGANIZER = "ATELIER VITA MAROC"
_CITY = "Casablanca"
_COUNTRY_ISO = "MA"
_VENUE_NAME = "ICEC AIN SEBAA"
_STARTS_ON = "2026-05-07"
_ENDS_ON = "2026-05-10"

_VIEWSTATE_RE = re.compile(
    rb'(?P<prefix>name="__VIEWSTATE" id="__VIEWSTATE" value=")[^"]+(?P<suffix>")'
)
_EVENTVALIDATION_RE = re.compile(
    rb'(?P<prefix>name="__EVENTVALIDATION" id="__EVENTVALIDATION" value=")[^"]+(?P<suffix>")'
)
_HFAC_RE = re.compile(
    rb'(?P<prefix>name="ctl00\$LogFormTop\$hfac" id="hfac" value=")[^"]+(?P<suffix>")'
)


def _url_matches(actual: str, expected: str) -> bool:
    return actual.rstrip("/") == expected.rstrip("/")


def _page_title(soup: BeautifulSoup) -> str | None:
    title_tag = soup.find("title")
    if not isinstance(title_tag, Tag):
        return None
    text = title_tag.get_text(strip=True)
    return text if text else None


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _normalize_body_for_hashing(body: bytes) -> bytes:
    body = _VIEWSTATE_RE.sub(rb"\g<prefix>normalized-viewstate\g<suffix>", body)
    body = _EVENTVALIDATION_RE.sub(rb"\g<prefix>normalized-eventvalidation\g<suffix>", body)
    body = _HFAC_RE.sub(rb"\g<prefix>normalized-hfac\g<suffix>", body)
    return body


def _stable_content_hash(body: bytes) -> str:
    return hashlib.sha256(_normalize_body_for_hashing(body)).hexdigest()


def _find_exact_href(soup: BeautifulSoup, expected: str) -> str | None:
    for anchor in soup.find_all("a"):
        if not isinstance(anchor, Tag):
            continue
        href = anchor.get("href")
        if href == expected:
            return href
    return None


def _parse_day_first_date(text: str) -> str | None:
    try:
        return datetime.strptime(text, "%d/%m/%Y").date().isoformat()
    except ValueError:
        return None


def _build_event(
    *,
    venue_name: str | None,
    registration_url: str | None,
    raw_title: str,
    raw_date_text: str,
) -> ParsedEvent:
    return ParsedEvent(
        title=_TITLE,
        summary=None,
        starts_on=_STARTS_ON,
        ends_on=_ENDS_ON,
        timezone=None,
        city=_CITY,
        country_iso=_COUNTRY_ISO,
        venue_name=venue_name,
        format="in_person",
        event_kind="conference",
        lifecycle_status="active",
        specialty_codes=[],
        organizer_name=_ORGANIZER,
        source_url=HOMEPAGE_URL,
        registration_url=registration_url,
        raw_title=raw_title,
        raw_date_text=raw_date_text,
    )


def _parse_homepage(soup: BeautifulSoup) -> ParsedEvent | None:
    if _page_title(soup) != _HOMEPAGE_PAGE_TITLE:
        return None

    body_text = _clean_text(soup.get_text(" ", strip=True))
    required_signals = (
        _HOMEPAGE_SECTION_TITLE,
        "Casablanca hosts the",
        _RAW_TITLE_HOMEPAGE,
        _HOMEPAGE_DATE_TEXT,
        "ATELIER VITA",
    )
    if any(signal not in body_text for signal in required_signals):
        return None

    registration_url = _find_exact_href(soup, REGISTRATION_URL)
    if registration_url != REGISTRATION_URL:
        return None

    return _build_event(
        venue_name=None,
        registration_url=registration_url,
        raw_title=_RAW_TITLE_HOMEPAGE,
        raw_date_text=_HOMEPAGE_DATE_TEXT,
    )


def _parse_exhibitors_page(soup: BeautifulSoup) -> ParsedEvent | None:
    if _page_title(soup) != _EXHIBITORS_PAGE_TITLE:
        return None

    title_tag = soup.select_one("div.PageTitle h1[itemprop='name']")
    if not isinstance(title_tag, Tag):
        return None
    raw_title = _clean_text(title_tag.get_text(" ", strip=True))
    if raw_title != _RAW_TITLE_EXHIBITORS:
        return None

    start_tag = soup.select_one("span[itemprop='startDate']")
    end_tag = soup.select_one("span[itemprop='endDate']")
    if not isinstance(start_tag, Tag) or not isinstance(end_tag, Tag):
        return None
    start_text = _clean_text(start_tag.get_text(" ", strip=True))
    end_text = _clean_text(end_tag.get_text(" ", strip=True))
    if _parse_day_first_date(start_text) != _STARTS_ON:
        return None
    if _parse_day_first_date(end_text) != _ENDS_ON:
        return None

    venue_tag = soup.select_one("#spanVenueName")
    if not isinstance(venue_tag, Tag):
        return None
    venue_name = _clean_text(venue_tag.get_text(" ", strip=True))
    if venue_name != _VENUE_NAME:
        return None

    return _build_event(
        venue_name=venue_name,
        registration_url=None,
        raw_title=raw_title,
        raw_date_text=f"Du {start_text} au {end_text}",
    )


@register_parser("morocco_dental_expo")
class MoroccoDentalExpoParser:
    name = "morocco_dental_expo"

    def discover(self, source: Any) -> Iterator[DiscoveredPage]:
        urls = {str(url).rstrip("/") for url in source.crawl_config.get("seed_urls", [])}
        if HOMEPAGE_URL.rstrip("/") in urls:
            yield DiscoveredPage(url=HOMEPAGE_URL, page_kind="detail")
        if EXHIBITORS_URL.rstrip("/") in urls:
            yield DiscoveredPage(url=EXHIBITORS_URL, page_kind="detail")

    def fetch(self, page: SourcePageRef) -> FetchedContent:  # pragma: no cover - wired by pipeline
        from ..fetch import fetch_url, make_default_client

        with make_default_client() as client:
            fetched = fetch_url(
                page.url,
                client=client,
                user_agent=(
                    "MedEvents-crawler "
                    "(https://github.com/cheikhanasiaeste-boop/medevents; "
                    "contact: cheikhanas.iaeste@gmail.com)"
                ),
            )
        return FetchedContent(
            url=fetched.url,
            status_code=fetched.status_code,
            content_type=fetched.content_type,
            body=fetched.body,
            fetched_at=fetched.fetched_at,
            content_hash=_stable_content_hash(fetched.body),
        )

    def parse(self, content: FetchedContent) -> Iterator[ParsedEvent]:
        soup = BeautifulSoup(content.body, "lxml")

        if _url_matches(content.url, HOMEPAGE_URL):
            event = _parse_homepage(soup)
            if event is not None:
                yield event
            return

        if _url_matches(content.url, EXHIBITORS_URL):
            event = _parse_exhibitors_page(soup)
            if event is not None:
                yield event
            return

        return
