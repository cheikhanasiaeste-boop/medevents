"""Chicago Dental Society Midwinter Meeting parser (`parser_name: cds_midwinter`).

Handles two public source surfaces via one parse() entry point:

    1. Event page (`/event/2026-midwinter-meeting/`)             -> 1 event
    2. Tribe Events JSON (`/wp-json/tribe/events/v1/events/387532`) -> 1 event
    3. Anything else                                              -> 0 events

The onboarding is intentionally edition-specific for 2026, matching the
curated-source discipline already used for AAP/FDI. Both captured surfaces are
byte-stable, so the default raw-body content hash is sufficient.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import datetime
from typing import Any

from bs4 import BeautifulSoup, Tag

from . import register_parser
from .base import DiscoveredPage, FetchedContent, ParsedEvent, SourcePageRef

DETAIL_URL = "https://www.cds.org/event/2026-midwinter-meeting/"
API_URL = "https://www.cds.org/wp-json/tribe/events/v1/events/387532"
REGISTRATION_URL = "https://midwintermeeting.eventscribe.net/"

_TITLE = "Chicago Dental Society Midwinter Meeting 2026"
_RAW_TITLE = "2026 Midwinter Meeting"
_DETAIL_PAGE_TITLE = "2026 Midwinter Meeting - Chicago Dental Society"
_DETAIL_DATE_TEXT = "February 19, 2026 - February 21, 2026"
_ORGANIZER = "Chicago Dental Society"
_CITY = "Chicago"
_COUNTRY_ISO = "US"
_VENUE_NAME = "McCormick Place West"
_TIMEZONE = "America/Chicago"


def _url_matches(actual: str, expected: str) -> bool:
    return actual.rstrip("/") == expected.rstrip("/")


def _page_title(soup: BeautifulSoup) -> str | None:
    title_tag = soup.find("title")
    if not isinstance(title_tag, Tag):
        return None
    text = title_tag.get_text(strip=True)
    return text if text else None


def _parse_human_date_range(text: str) -> tuple[str, str, str] | None:
    pieces = [piece.strip() for piece in text.split(" - ", 1)]
    if len(pieces) != 2:
        return None
    try:
        starts_on = datetime.strptime(pieces[0], "%B %d, %Y").date()
        ends_on = datetime.strptime(pieces[1], "%B %d, %Y").date()
    except ValueError:
        return None
    return text, starts_on.isoformat(), ends_on.isoformat()


def _build_event(
    *,
    source_url: str,
    timezone: str | None,
    venue_name: str | None,
    raw_title: str,
    raw_date_text: str,
) -> ParsedEvent:
    return ParsedEvent(
        title=_TITLE,
        summary=None,
        starts_on="2026-02-19",
        ends_on="2026-02-21",
        timezone=timezone,
        city=_CITY,
        country_iso=_COUNTRY_ISO,
        venue_name=venue_name,
        format="in_person",
        event_kind="conference",
        lifecycle_status="active",
        specialty_codes=[],
        organizer_name=_ORGANIZER,
        source_url=source_url,
        registration_url=REGISTRATION_URL,
        raw_title=raw_title,
        raw_date_text=raw_date_text,
    )


@register_parser("cds_midwinter")
class CdsMidwinterParser:
    name = "cds_midwinter"

    def discover(self, source: Any) -> Iterator[DiscoveredPage]:
        urls = {str(url).rstrip("/") for url in source.crawl_config.get("seed_urls", [])}
        if DETAIL_URL.rstrip("/") in urls:
            yield DiscoveredPage(url=DETAIL_URL, page_kind="detail")
        if API_URL.rstrip("/") in urls:
            yield DiscoveredPage(url=API_URL, page_kind="detail")

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
        if _url_matches(content.url, DETAIL_URL):
            soup = BeautifulSoup(content.body, "lxml")
            event = _parse_detail_page(soup)
            if event is not None:
                yield event
            return

        if _url_matches(content.url, API_URL):
            event = _parse_api(content.body)
            if event is not None:
                yield event
            return

        return


def _parse_detail_page(soup: BeautifulSoup) -> ParsedEvent | None:
    if _page_title(soup) != _DETAIL_PAGE_TITLE:
        return None

    title_tag = soup.select_one("h4.entry-title a")
    if not isinstance(title_tag, Tag):
        return None
    raw_title = title_tag.get_text(strip=True)
    if raw_title != _RAW_TITLE:
        return None

    date_tag = soup.select_one("span.decm_date")
    if not isinstance(date_tag, Tag):
        return None
    raw_date_text = date_tag.get_text(" ", strip=True)
    parsed_date = _parse_human_date_range(raw_date_text)
    if parsed_date is None:
        return None
    _, starts_on, ends_on = parsed_date
    if starts_on != "2026-02-19" or ends_on != "2026-02-21":
        return None

    location_tag = soup.select_one("span.decm_location")
    if not isinstance(location_tag, Tag):
        return None
    location_text = location_tag.get_text(" ", strip=True)
    if _CITY not in location_text or "Indiana Avenue" not in location_text:
        return None

    link_tag = soup.select_one("p.ecs-weburl a")
    if not isinstance(link_tag, Tag):
        return None
    href = link_tag.get("href")
    if href != REGISTRATION_URL:
        return None

    return _build_event(
        source_url=DETAIL_URL,
        timezone=None,
        venue_name=None,
        raw_title=raw_title,
        raw_date_text=raw_date_text,
    )


def _parse_api(body: bytes) -> ParsedEvent | None:
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return None

    if not isinstance(payload, dict):
        return None

    raw_title = payload.get("title")
    if raw_title != _RAW_TITLE:
        return None

    source_url = payload.get("url")
    if source_url != DETAIL_URL:
        return None

    registration_url = payload.get("website")
    if registration_url != REGISTRATION_URL:
        return None

    if payload.get("all_day") is not True:
        return None

    start_date = payload.get("start_date")
    end_date = payload.get("end_date")
    if not isinstance(start_date, str) or not isinstance(end_date, str):
        return None
    starts_on = start_date[:10]
    ends_on = end_date[:10]
    try:
        datetime.strptime(starts_on, "%Y-%m-%d")
        datetime.strptime(ends_on, "%Y-%m-%d")
    except ValueError:
        return None
    if starts_on != "2026-02-19" or ends_on != "2026-02-21":
        return None

    timezone = payload.get("timezone")
    if timezone != _TIMEZONE:
        return None

    venue = payload.get("venue")
    if not isinstance(venue, dict):
        return None
    venue_name = venue.get("venue")
    city = venue.get("city")
    if venue_name != _VENUE_NAME or city != _CITY:
        return None

    return _build_event(
        source_url=DETAIL_URL,
        timezone=timezone,
        venue_name=venue_name,
        raw_title=raw_title,
        raw_date_text=_DETAIL_DATE_TEXT,
    )
