"""Dentex Algeria source parser (`parser_name: dentex_algeria`).

Handles two public source surfaces via one parse() entry point:

    1. Homepage (`https://www.dentex.dz/en/`)         -> 1 event
    2. Visit page (`https://www.dentex.dz/en/visit/`) -> 1 event
    3. Anything else                                  -> 0 events

The onboarding is intentionally edition-specific for 2026, matching the
curated-source discipline already used for AAP/FDI/EAO/CDS. Both captured
pages are byte-stable, so the default raw-body content hash is sufficient.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from datetime import datetime
from typing import Any

from bs4 import BeautifulSoup, Tag

from . import register_parser
from .base import DiscoveredPage, FetchedContent, ParsedEvent, SourcePageRef

HOMEPAGE_URL = "https://www.dentex.dz/en/"
VISIT_URL = "https://www.dentex.dz/en/visit/"

_TITLE = "DENTEX Algeria 2026"
_RAW_TITLE = "DENTEX Alg\u00e9rie 2026"
_HOMEPAGE_PAGE_TITLE = "DENTEX Algeria 2026 | Dentistry Tradeshow"
_VISIT_PAGE_TITLE = "Visit | The First trade fair in Algeria dedicated to the dental sector"
_RAW_DATE_TEXT = "2 - 5 June 2026"
_ORGANIZER = "Dentex Algeria"
_CITY = "Algiers"
_COUNTRY_ISO = "DZ"
_VENUE_NAME = "Algiers Exhibition Center - SAFEX (Palestine hall)"
_STARTS_ON = "2026-06-02"
_ENDS_ON = "2026-06-05"
_REGISTRATION_LABELS = {
    "free registration",
    "inscription visiteurs",
    "visitor registration",
    "register now",
    "your free ticket",
}
_VISITCLOUD_PREFIX = "https://register.visitcloud.com/survey/"


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


def _hidden_input_value(soup: BeautifulSoup, name: str) -> str | None:
    tag = soup.select_one(f'input[name="{name}"]')
    if not isinstance(tag, Tag):
        return None
    value = tag.get("value")
    if not isinstance(value, str):
        return None
    value = _clean_text(value)
    return value if value else None


def _primary_registration_url(soup: BeautifulSoup) -> str | None:
    for anchor in soup.find_all("a"):
        if not isinstance(anchor, Tag):
            continue
        href = anchor.get("href")
        if not isinstance(href, str) or not href.startswith(_VISITCLOUD_PREFIX):
            continue
        label = _clean_text(anchor.get_text(" ", strip=True)).lower()
        if label in _REGISTRATION_LABELS:
            return href
    return None


def _has_required_header_signals(soup: BeautifulSoup) -> bool:
    values = {
        _clean_text(tag.get_text(" ", strip=True))
        for tag in soup.select("span.elementor-icon-list-text")
        if isinstance(tag, Tag)
    }
    return _RAW_DATE_TEXT in values and _VENUE_NAME in values


def _parse_date_inputs(soup: BeautifulSoup) -> tuple[str, str] | None:
    start_value = _hidden_input_value(soup, "event_date_start")
    end_value = _hidden_input_value(soup, "event_date_end")
    if start_value is None or end_value is None:
        return None
    starts_on = start_value[:10]
    ends_on = end_value[:10]
    try:
        datetime.strptime(starts_on, "%Y-%m-%d")
        datetime.strptime(ends_on, "%Y-%m-%d")
    except ValueError:
        return None
    if starts_on != _STARTS_ON or ends_on != _ENDS_ON:
        return None
    return starts_on, ends_on


def _build_event(*, registration_url: str) -> ParsedEvent:
    return ParsedEvent(
        title=_TITLE,
        summary=None,
        starts_on=_STARTS_ON,
        ends_on=_ENDS_ON,
        timezone=None,
        city=_CITY,
        country_iso=_COUNTRY_ISO,
        venue_name=_VENUE_NAME,
        format="in_person",
        event_kind="conference",
        lifecycle_status="active",
        specialty_codes=[],
        organizer_name=_ORGANIZER,
        source_url=HOMEPAGE_URL,
        registration_url=registration_url,
        raw_title=_RAW_TITLE,
        raw_date_text=_RAW_DATE_TEXT,
    )


def _parse_page(soup: BeautifulSoup, *, expected_title: str) -> ParsedEvent | None:
    if _page_title(soup) != expected_title:
        return None
    if not _has_required_header_signals(soup):
        return None

    raw_title = _hidden_input_value(soup, "event_title")
    if raw_title != _RAW_TITLE:
        return None

    if _hidden_input_value(soup, "event_url") != HOMEPAGE_URL:
        return None

    if _parse_date_inputs(soup) is None:
        return None

    registration_url = _primary_registration_url(soup)
    if registration_url is None:
        return None

    return _build_event(registration_url=registration_url)


@register_parser("dentex_algeria")
class DentexAlgeriaParser:
    name = "dentex_algeria"

    def discover(self, source: Any) -> Iterator[DiscoveredPage]:
        urls = {str(url).rstrip("/") for url in source.crawl_config.get("seed_urls", [])}
        if HOMEPAGE_URL.rstrip("/") in urls:
            yield DiscoveredPage(url=HOMEPAGE_URL, page_kind="detail")
        if VISIT_URL.rstrip("/") in urls:
            yield DiscoveredPage(url=VISIT_URL, page_kind="detail")

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

        if _url_matches(content.url, HOMEPAGE_URL):
            event = _parse_page(soup, expected_title=_HOMEPAGE_PAGE_TITLE)
            if event is not None:
                yield event
            return

        if _url_matches(content.url, VISIT_URL):
            event = _parse_page(soup, expected_title=_VISIT_PAGE_TITLE)
            if event is not None:
                yield event
            return

        return
