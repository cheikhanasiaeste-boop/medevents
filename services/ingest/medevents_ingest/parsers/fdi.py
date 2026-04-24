"""FDI World Dental Congress source parser (`parser_name: fdi_wdc`).

Handles two page shapes via one parse() entry point:

    1. Hub page (`/fdi-world-dental-congress`)         -> 1 event
    2. 2026 detail page (`/fdi-world-dental-congress-2026`) -> 1 event
    3. Anything else (2025 canary, arbitrary URL)      -> 0 events

The parser is intentionally edition-specific for 2026, matching the curated
seed discipline already used for `aap_annual_meeting`. When the 2027 congress
page becomes the current event-of-record, the seed URL and year gate should be
updated together.

FDI serves byte-stable HTML per docs/runbooks/fdi-fixtures.md, so the default
fetch.fetch_url + raw sha-256 content_hash are sufficient. No normalization
hook is required.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from datetime import datetime
from typing import Any

from bs4 import BeautifulSoup, Tag

from . import register_parser
from .base import DiscoveredPage, FetchedContent, ParsedEvent, SourcePageRef

HUB_URL = "https://www.fdiworlddental.org/fdi-world-dental-congress"
DETAIL_URL = "https://www.fdiworlddental.org/fdi-world-dental-congress-2026"

_TITLE = "FDI World Dental Congress 2026"
_HUB_PAGE_TITLE = "FDI World Dental Congress | FDI"
_DETAIL_PAGE_TITLE = "FDI World Dental Congress 2026 | FDI"
_ORGANIZER = "FDI World Dental Federation"
_CITY = "Prague"
_COUNTRY_ISO = "CZ"
_REGISTRATION_URL = "https://2026.world-dental-congress.org/"
_HUB_DATE_RE = re.compile(
    r"FDI World Dental Congress 2026 is scheduled to take place in Prague, "
    r"Czech Republic, from (?P<start>\d{1,2}) to (?P<end>\d{1,2}) "
    r"(?P<month>[A-Za-z]+) (?P<year>20\d{2})"
)


def _url_matches(actual: str, expected: str) -> bool:
    return actual.rstrip("/") == expected.rstrip("/")


@register_parser("fdi_wdc")
class FdiWdcParser:
    name = "fdi_wdc"

    def discover(self, source: Any) -> Iterator[DiscoveredPage]:
        """Yield hub first, detail second to keep enrichment deterministic."""
        urls: set[str] = set(source.crawl_config.get("seed_urls", []))
        if HUB_URL in urls:
            yield DiscoveredPage(url=HUB_URL, page_kind="detail")
        if DETAIL_URL in urls:
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
            event = _parse_hub(content, soup)
            if event is not None:
                yield event
            return

        if _url_matches(content.url, DETAIL_URL):
            event = _parse_detail(content, soup)
            if event is not None:
                yield event
            return

        return


def _page_title(soup: BeautifulSoup) -> str | None:
    title_tag = soup.find("title")
    if not isinstance(title_tag, Tag):
        return None
    text = title_tag.get_text(strip=True)
    return text if text else None


def _heading_text(soup: BeautifulSoup) -> str | None:
    heading_tag = soup.select_one("div.node__content h1 span.field--name-title")
    if not isinstance(heading_tag, Tag):
        fallback = soup.find("h1")
        if not isinstance(fallback, Tag):
            return None
        heading_tag = fallback
    text = heading_tag.get_text(strip=True)
    return text if text else None


def _registration_url(soup: BeautifulSoup, *, link_text: str) -> str | None:
    for anchor in soup.find_all("a"):
        if not isinstance(anchor, Tag):
            continue
        if anchor.get_text(strip=True) != link_text:
            continue
        href = anchor.get("href")
        if isinstance(href, str) and href:
            return href
    return None


def _parse_hub_date(text: str) -> tuple[str, str, str] | None:
    match = _HUB_DATE_RE.search(text)
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


def _parse_hub(content: FetchedContent, soup: BeautifulSoup) -> ParsedEvent | None:
    if _page_title(soup) != _HUB_PAGE_TITLE:
        return None

    body_text = soup.get_text("\n", strip=True)
    parsed_date = _parse_hub_date(body_text)
    if parsed_date is None:
        return None
    raw_date, starts_on, ends_on = parsed_date

    if _TITLE not in body_text or _CITY not in body_text:
        return None

    registration_url = _registration_url(soup, link_text="Visit the website")
    if registration_url != _REGISTRATION_URL:
        return None

    return ParsedEvent(
        title=_TITLE,
        summary=None,
        starts_on=starts_on,
        ends_on=ends_on,
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
        registration_url=registration_url,
        raw_title=_TITLE,
        raw_date_text=raw_date,
    )


def _parse_detail(content: FetchedContent, soup: BeautifulSoup) -> ParsedEvent | None:
    if _page_title(soup) != _DETAIL_PAGE_TITLE:
        return None

    heading = _heading_text(soup)
    if heading != _TITLE:
        return None

    body_text = soup.get_text("\n", strip=True)
    if _CITY not in body_text:
        return None

    time_tags = soup.select("div.field--name-field-n-date-range time.datetime")
    if len(time_tags) != 2:
        return None

    start_attr = time_tags[0].get("datetime")
    end_attr = time_tags[1].get("datetime")
    if not isinstance(start_attr, str) or not isinstance(end_attr, str):
        return None

    try:
        starts_on = start_attr[:10]
        ends_on = end_attr[:10]
        datetime.strptime(starts_on, "%Y-%m-%d")
        datetime.strptime(ends_on, "%Y-%m-%d")
    except ValueError:
        return None

    if not starts_on.startswith("2026-09-04") or not ends_on.startswith("2026-09-07"):
        return None

    registration_url = _registration_url(soup, link_text="Congress Website")
    if registration_url != _REGISTRATION_URL:
        return None

    raw_date = f"{time_tags[0].get_text(strip=True)} - {time_tags[1].get_text(strip=True)}"
    return ParsedEvent(
        title=_TITLE,
        summary=None,
        starts_on=starts_on,
        ends_on=ends_on,
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
        registration_url=registration_url,
        raw_title=heading,
        raw_date_text=raw_date,
    )
