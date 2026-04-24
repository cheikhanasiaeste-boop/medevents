"""EAO Congress source parser (`parser_name: eao_congress`).

Handles two page shapes via one parse() entry point:

    1. EAO hub (`https://eao.org/congress/`)            -> 3 events today
       (2026 Lisbon + 2027 Madrid + 2028 Amsterdam)
    2. 2026 microsite homepage (`https://congress.eao.org/en/`) -> 1 event
       (2026 Lisbon detail/enrichment)
    3. Anything else                                    -> 0 events

The hub page is not byte-stable as served: WordPress Simple Banner injects
per-request `current_date`, `start_date`, and `end_date` timestamps into
inline JavaScript. fetch() normalizes those values before computing the
content hash so unchanged hub content still hits the pipeline's
`skipped_unchanged` gate. The linked congress microsite homepage is
byte-stable and does not need normalization.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterator
from datetime import datetime
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

from . import register_parser
from .base import DiscoveredPage, FetchedContent, ParsedEvent, SourcePageRef

HUB_URL = "https://eao.org/congress/"
DETAIL_URL = "https://congress.eao.org/en/"
REGISTRATION_URL = "https://congress.eao.org/en/congress/registration"

_HUB_PAGE_TITLE = (
    "EAO Congress - The European Association for Osseointegration"
    "The European Association for Osseointegration"
)
_DETAIL_PAGE_TITLE = "Homepage | Eaocongress 2026"
_ORGANIZER = "European Association for Osseointegration"

_HUB_CURRENT_MARKER = "EAO Congress: Lisbon 26"
_HUB_CURRENT_CITY_SIGNAL = "We invite you to join us in Lisbon"
_DETAIL_CITY_SIGNAL = "Welcome to Lisbon"
_DETAIL_THEME_SIGNAL = "Delivering Health and Predictability: Shaping the Future of Patient Care"

_DASH = r"[\u2013\u2014\-]"
_HUB_BANNER_DATE_RE = re.compile(rb'("(?:current|start|end)_date":\{"date":")[^"]+(")')
_HUB_LITESPEED_COMMENT_RE = re.compile(rb"<!-- Page supported by LiteSpeed Cache[^>]+-->")
_DATE_RANGE_RE = re.compile(
    rf"(?P<start>\d{{1,2}})(?:st|nd|rd|th)?\s*{_DASH}\s*"
    rf"(?P<end>\d{{1,2}})(?:st|nd|rd|th)?\s+(?P<month>[A-Za-z]+)\s+(?P<year>20\d{{2}})"
)
_DETAIL_WELCOME_RE = re.compile(
    r"33\s*(?:st|nd|rd|th)? annual congress will take place in Lisbon from "
    r"(?P<start>\d{1,2}) to (?P<end>\d{1,2}) (?P<month>[A-Za-z]+) (?P<year>20\d{2})",
    re.IGNORECASE,
)

_HUB_FUTURE_EVENTS: tuple[tuple[str, str, str], ...] = (
    ("EAO Congress 2027 in Madrid", "Madrid", "ES"),
    ("EAO Congress 2028 in Amsterdam", "Amsterdam", "NL"),
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


def _normalize_body_for_hashing(url: str, body: bytes) -> bytes:
    if not _url_matches(url, HUB_URL):
        return body
    body = _HUB_BANNER_DATE_RE.sub(rb"\1normalized-datetime\2", body)
    body = _HUB_LITESPEED_COMMENT_RE.sub(b"<!-- normalized-litespeed-cache-comment -->", body)
    return body


def _stable_content_hash(url: str, body: bytes) -> str:
    return hashlib.sha256(_normalize_body_for_hashing(url, body)).hexdigest()


def _extract_date_after(body_text: str, marker: str) -> tuple[str, str, str] | None:
    index = body_text.find(marker)
    if index == -1:
        return None
    snippet = body_text[index : index + 200]
    match = _DATE_RANGE_RE.search(snippet)
    if match is None:
        return None
    raw_date = re.sub(_DASH, "-", match.group(0))
    try:
        starts_on = datetime.strptime(
            f"{match.group('start')} {match.group('month')} {match.group('year')}",
            "%d %B %Y",
        ).date()
        ends_on = datetime.strptime(
            f"{match.group('end')} {match.group('month')} {match.group('year')}",
            "%d %B %Y",
        ).date()
    except ValueError:
        return None
    return raw_date, starts_on.isoformat(), ends_on.isoformat()


def _detail_date_range(body_text: str) -> tuple[str, str, str] | None:
    match = _DETAIL_WELCOME_RE.search(body_text)
    if match is None:
        return None
    raw_date = (
        f"{match.group('start')} to {match.group('end')} "
        f"{match.group('month')} {match.group('year')}"
    )
    try:
        starts_on = datetime.strptime(
            f"{match.group('start')} {match.group('month')} {match.group('year')}",
            "%d %B %Y",
        ).date()
        ends_on = datetime.strptime(
            f"{match.group('end')} {match.group('month')} {match.group('year')}",
            "%d %B %Y",
        ).date()
    except ValueError:
        return None
    return raw_date, starts_on.isoformat(), ends_on.isoformat()


def _document_base_url(soup: BeautifulSoup, fallback_url: str) -> str:
    base_tag = soup.find("base")
    if not isinstance(base_tag, Tag):
        return fallback_url
    href = base_tag.get("href")
    if not isinstance(href, str) or not href:
        return fallback_url
    return href


def _find_link(soup: BeautifulSoup, *, base_url: str, exact_url: str) -> str | None:
    document_base = _document_base_url(soup, base_url)
    for anchor in soup.find_all("a"):
        if not isinstance(anchor, Tag):
            continue
        href = anchor.get("href")
        if not isinstance(href, str) or not href:
            continue
        resolved = urljoin(document_base, href)
        if resolved == exact_url:
            return resolved
    return None


def _build_event(
    *,
    year: int,
    city: str,
    country_iso: str,
    starts_on: str,
    ends_on: str,
    source_url: str,
    raw_title: str,
    raw_date_text: str,
    registration_url: str | None,
) -> ParsedEvent:
    return ParsedEvent(
        title=f"EAO Congress {year}",
        summary=None,
        starts_on=starts_on,
        ends_on=ends_on,
        timezone=None,
        city=city,
        country_iso=country_iso,
        venue_name=None,
        format="in_person",
        event_kind="conference",
        lifecycle_status="active",
        specialty_codes=[],
        organizer_name=_ORGANIZER,
        source_url=source_url,
        registration_url=registration_url,
        raw_title=raw_title,
        raw_date_text=raw_date_text,
    )


@register_parser("eao_congress")
class EaoCongressParser:
    name = "eao_congress"

    def discover(self, source: Any) -> Iterator[DiscoveredPage]:
        urls = {str(url).rstrip("/") for url in source.crawl_config.get("seed_urls", [])}
        if HUB_URL.rstrip("/") in urls:
            yield DiscoveredPage(url=HUB_URL, page_kind="listing")
        if DETAIL_URL.rstrip("/") in urls:
            yield DiscoveredPage(url=DETAIL_URL, page_kind="detail")

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
            content_hash=_stable_content_hash(fetched.url, fetched.body),
        )

    def parse(self, content: FetchedContent) -> Iterator[ParsedEvent]:
        soup = BeautifulSoup(content.body, "lxml")

        if _url_matches(content.url, HUB_URL):
            yield from _parse_hub(content, soup)
            return

        if _url_matches(content.url, DETAIL_URL):
            event = _parse_detail(content, soup)
            if event is not None:
                yield event
            return

        return


def _parse_hub(content: FetchedContent, soup: BeautifulSoup) -> Iterator[ParsedEvent]:
    if _page_title(soup) != _HUB_PAGE_TITLE:
        return

    body_text = _clean_text(soup.get_text(" ", strip=True))
    registration_url = _find_link(soup, base_url=content.url, exact_url=REGISTRATION_URL)

    if _HUB_CURRENT_MARKER in body_text and _HUB_CURRENT_CITY_SIGNAL in body_text:
        current_date = _extract_date_after(body_text, _HUB_CURRENT_MARKER)
        if current_date is not None:
            raw_date, starts_on, ends_on = current_date
            yield _build_event(
                year=2026,
                city="Lisbon",
                country_iso="PT",
                starts_on=starts_on,
                ends_on=ends_on,
                source_url=content.url,
                raw_title=_HUB_CURRENT_MARKER,
                raw_date_text=raw_date,
                registration_url=registration_url,
            )

    for raw_title, city, country_iso in _HUB_FUTURE_EVENTS:
        if raw_title not in body_text:
            continue
        parsed_date = _extract_date_after(body_text, raw_title)
        if parsed_date is None:
            continue
        raw_date, starts_on, ends_on = parsed_date
        year = int(starts_on[:4])
        yield _build_event(
            year=year,
            city=city,
            country_iso=country_iso,
            starts_on=starts_on,
            ends_on=ends_on,
            source_url=content.url,
            raw_title=raw_title,
            raw_date_text=raw_date,
            registration_url=None,
        )


def _parse_detail(content: FetchedContent, soup: BeautifulSoup) -> ParsedEvent | None:
    if _page_title(soup) != _DETAIL_PAGE_TITLE:
        return None

    body_text = _clean_text(soup.get_text(" ", strip=True))
    if _DETAIL_CITY_SIGNAL not in body_text:
        return None

    date_range = _detail_date_range(body_text)
    if date_range is None:
        return None

    registration_url = _find_link(soup, base_url=content.url, exact_url=REGISTRATION_URL)
    if registration_url != REGISTRATION_URL:
        return None

    raw_date, starts_on, ends_on = date_range
    return _build_event(
        year=2026,
        city="Lisbon",
        country_iso="PT",
        starts_on=starts_on,
        ends_on=ends_on,
        source_url=content.url,
        raw_title=_DETAIL_PAGE_TITLE,
        raw_date_text=raw_date,
        registration_url=registration_url,
    )


__all__ = [
    "DETAIL_URL",
    "HUB_URL",
    "REGISTRATION_URL",
    "_normalize_body_for_hashing",
    "_stable_content_hash",
]
