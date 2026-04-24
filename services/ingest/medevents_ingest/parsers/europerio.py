"""EuroPerio source parser (`parser_name: europerio`).

Handles two public EFP page shapes via one parse() entry point:

    1. Hub page (`https://www.efp.org/europerio/`)               -> 1 event
    2. EuroPerio12 page (`https://www.efp.org/europerio/europerio12/`) -> 1 event
    3. Anything else                                             -> 0 events

The onboarding is intentionally edition-specific for EuroPerio12 / 2028.
Prep verification showed both pages are byte-stable as served, so the default
fetch path plus raw sha-256 content hashes are sufficient here.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from datetime import datetime
from typing import Any

from bs4 import BeautifulSoup, Tag

from . import register_parser
from .base import DiscoveredPage, FetchedContent, ParsedEvent, SourcePageRef

HUB_URL = "https://www.efp.org/europerio/"
DETAIL_URL = "https://www.efp.org/europerio/europerio12/"

_TITLE = "EuroPerio12"
_HUB_PAGE_TITLE = "EuroPerio - European Federation of Periodontology"
_DETAIL_PAGE_TITLE = "EuroPerio12 - European Federation of Periodontology"
_HUB_H1 = "EuroPerio, the world's leading congress in periodontology and implant dentistry"
_DETAIL_H1 = "EuroPerio12"
_ORGANIZER = "European Federation of Periodontology"
_CITY = "Munich"
_COUNTRY_ISO = "DE"
_STARTS_ON = "2028-05-10"
_ENDS_ON = "2028-05-13"

_DASH = r"[\u2013\u2014-]"
_HUB_DATE_RE = re.compile(
    rf"the next EuroPerio will happen in Munich, Germany from "
    rf"(?P<start>\d{{1,2}})\s*{_DASH}\s*(?P<end>\d{{1,2}})\s+"
    rf"(?P<month>[A-Za-z]+),\s+(?P<year>20\d{{2}})",
    re.IGNORECASE,
)
_DETAIL_DATE_RE = re.compile(
    rf"Join us from (?P<month>[A-Za-z]+)\s+(?P<start>\d{{1,2}})\s*{_DASH}\s*"
    rf"(?P<end>\d{{1,2}}),\s+(?P<year>20\d{{2}})\s+in Munich, Germany for EuroPerio12!",
    re.IGNORECASE,
)


def _url_matches(actual: str, expected: str) -> bool:
    return actual.rstrip("/") == expected.rstrip("/")


def _page_title(soup: BeautifulSoup) -> str | None:
    title_tag = soup.find("title")
    if not isinstance(title_tag, Tag):
        return None
    text = title_tag.get_text(strip=True)
    return text if text else None


def _heading_text(soup: BeautifulSoup) -> str | None:
    heading_tag = soup.find("h1")
    if not isinstance(heading_tag, Tag):
        return None
    text = heading_tag.get_text(" ", strip=True)
    return _clean_text(text) if text else None


def _clean_text(text: str) -> str:
    text = text.replace("\u2019", "'")
    return re.sub(r"\s+", " ", text).strip()


def _parse_iso_range(
    *,
    start: str,
    end: str,
    month: str,
    year: str,
) -> tuple[str, str] | None:
    try:
        starts_on = datetime.strptime(f"{start} {month} {year}", "%d %B %Y").date().isoformat()
        ends_on = datetime.strptime(f"{end} {month} {year}", "%d %B %Y").date().isoformat()
    except ValueError:
        return None
    return starts_on, ends_on


def _hub_date_range(body_text: str) -> str | None:
    match = _HUB_DATE_RE.search(body_text)
    if match is None:
        return None
    parsed = _parse_iso_range(
        start=match.group("start"),
        end=match.group("end"),
        month=match.group("month"),
        year=match.group("year"),
    )
    if parsed is None:
        return None
    starts_on, ends_on = parsed
    if starts_on != _STARTS_ON or ends_on != _ENDS_ON:
        return None
    return f"{match.group('start')} -{match.group('end')} {match.group('month')}, {match.group('year')}"


def _detail_date_range(body_text: str) -> str | None:
    match = _DETAIL_DATE_RE.search(body_text)
    if match is None:
        return None
    parsed = _parse_iso_range(
        start=match.group("start"),
        end=match.group("end"),
        month=match.group("month"),
        year=match.group("year"),
    )
    if parsed is None:
        return None
    starts_on, ends_on = parsed
    if starts_on != _STARTS_ON or ends_on != _ENDS_ON:
        return None
    return (
        f"{match.group('month')} {match.group('start')}-{match.group('end')}, {match.group('year')}"
    )


def _build_event(*, raw_title: str, raw_date_text: str) -> ParsedEvent:
    return ParsedEvent(
        title=_TITLE,
        summary=None,
        starts_on=_STARTS_ON,
        ends_on=_ENDS_ON,
        timezone=None,
        city=_CITY,
        country_iso=_COUNTRY_ISO,
        venue_name=None,
        format="in_person",
        event_kind="conference",
        lifecycle_status="active",
        specialty_codes=[],
        organizer_name=_ORGANIZER,
        source_url=DETAIL_URL,
        registration_url=None,
        raw_title=raw_title,
        raw_date_text=raw_date_text,
    )


def _parse_hub(soup: BeautifulSoup) -> ParsedEvent | None:
    if _page_title(soup) != _HUB_PAGE_TITLE:
        return None

    heading = _heading_text(soup)
    if heading != _HUB_H1:
        return None

    body_text = _clean_text(soup.get_text(" ", strip=True))
    required_signals = (
        "Save the date:",
        "the next EuroPerio will happen in Munich, Germany",
        "Learn more about EuroPerio12",
    )
    if any(signal not in body_text for signal in required_signals):
        return None

    raw_date_text = _hub_date_range(body_text)
    if raw_date_text is None:
        return None

    return _build_event(raw_title=heading, raw_date_text=raw_date_text)


def _parse_detail(soup: BeautifulSoup) -> ParsedEvent | None:
    if _page_title(soup) != _DETAIL_PAGE_TITLE:
        return None

    heading = _heading_text(soup)
    if heading != _DETAIL_H1:
        return None

    body_text = _clean_text(soup.get_text(" ", strip=True))
    required_signals = (
        "Sponsors & Exhibitors",
        "This was EuroPerio11",
        "Key dates to remember",
    )
    if any(signal not in body_text for signal in required_signals):
        return None

    raw_date_text = _detail_date_range(body_text)
    if raw_date_text is None:
        return None

    return _build_event(raw_title=heading, raw_date_text=raw_date_text)


@register_parser("europerio")
class EuroPerioParser:
    name = "europerio"

    def discover(self, source: Any) -> Iterator[DiscoveredPage]:
        urls = {str(url).rstrip("/") for url in source.crawl_config.get("seed_urls", [])}
        if HUB_URL.rstrip("/") in urls:
            yield DiscoveredPage(url=HUB_URL, page_kind="detail")
        if DETAIL_URL.rstrip("/") in urls:
            yield DiscoveredPage(url=DETAIL_URL, page_kind="detail")

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

        if _url_matches(content.url, HUB_URL):
            event = _parse_hub(soup)
            if event is not None:
                yield event
            return

        if _url_matches(content.url, DETAIL_URL):
            event = _parse_detail(soup)
            if event is not None:
                yield event
            return

        return
