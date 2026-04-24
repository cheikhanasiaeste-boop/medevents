"""AMIED congress source parser (`parser_name: amied_congress`).

Handles two public source surfaces via one parse() entry point:

    1. Homepage (`https://amied.ma/`)                      -> 1 event
    2. Inscriptions page (`https://amied.ma/inscriptions/`) -> 1 event
    3. Anything else                                       -> 0 events

The onboarding is intentionally edition-specific for 2026. Prep verification
showed both chosen pages are byte-stable, so the default raw-body content hash
is sufficient here.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterator
from typing import Any

from bs4 import BeautifulSoup, Tag

from . import register_parser
from .base import DiscoveredPage, FetchedContent, ParsedEvent, SourcePageRef

HOMEPAGE_URL = "https://amied.ma/"
INSCRIPTIONS_URL = "https://amied.ma/inscriptions/"
REGISTRATION_URL = (
    "https://docs.google.com/forms/d/e/1FAIpQLSd3x-i-F-pC42oIUyNEJ9qXvJYKqhZTKrrztW5hkYJQ5WC7_w/"
    "viewform?embedded=true"
)

_TITLE = "AMIED International Congress 2026"
_RAW_TITLE_HOMEPAGE = "Congr\u00e8s international"
_RAW_TITLE_INSCRIPTIONS = "Participez au Congr\u00e8s International d\u2019Implantologie et d\u2019Esth\u00e9tique Dentaire"
_HOMEPAGE_PAGE_TITLE = "AMIED"
_INSCRIPTIONS_PAGE_TITLE = "Inscriptions - AMIED"
_HOMEPAGE_HEADING = "Congres international"
_HOMEPAGE_TAGLINE = "Modern Dentistry When Art meets science"
_HOMEPAGE_EDITION = "2eme edition"
_INSCRIPTIONS_SUMMARY = (
    "Participez au Congres International d'Implantologie et d'Esthetique Dentaire"
)
_INSCRIPTIONS_HEADING = "Comment s'inscrire au congres ?"
_VENUE_NAME = "Barcelo Palmeraie Oasis Resort"
_CITY = "Marrakech"
_COUNTRY_ISO = "MA"
_ORGANIZER = "L'Amicale Marocaine d'Implantologie et d'Esthetique dentaire (AMIED)"
_STARTS_ON = "2026-06-19"
_ENDS_ON = "2026-06-20"
_RAW_DATE_HOMEPAGE = "Vendredi 19 Juin Samedi 20 Juin 2026"
_RAW_DATE_INSCRIPTIONS = "19-20 Juin 2026"


def _url_matches(actual: str, expected: str) -> bool:
    return actual.rstrip("/") == expected.rstrip("/")


def _clean_text(text: str) -> str:
    text = text.replace("\u2019", "'")
    text = text.replace("\u2013", "-")
    text = text.replace("\u2014", "-")
    return re.sub(r"\s+", " ", text).strip()


def _ascii_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", _clean_text(text))
    return normalized.encode("ascii", "ignore").decode("ascii")


def _page_title(soup: BeautifulSoup) -> str | None:
    title_tag = soup.find("title")
    if not isinstance(title_tag, Tag):
        return None
    text = title_tag.get_text(strip=True)
    return _ascii_text(text) if text else None


def _selector_text(soup: BeautifulSoup, selector: str) -> str | None:
    tag = soup.select_one(selector)
    if not isinstance(tag, Tag):
        return None
    text = tag.get_text(" ", strip=True)
    return _ascii_text(text) if text else None


def _registration_url(soup: BeautifulSoup) -> str | None:
    for iframe in soup.find_all("iframe"):
        if not isinstance(iframe, Tag):
            continue
        src = iframe.get("src")
        if src == REGISTRATION_URL:
            return src
    return None


def _build_event(*, raw_title: str, raw_date_text: str) -> ParsedEvent:
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
        registration_url=REGISTRATION_URL,
        raw_title=raw_title,
        raw_date_text=raw_date_text,
    )


def _parse_homepage(soup: BeautifulSoup) -> ParsedEvent | None:
    if _page_title(soup) != _HOMEPAGE_PAGE_TITLE:
        return None

    heading = _selector_text(soup, "div.xb-hero-heading h2.title")
    if heading != _HOMEPAGE_HEADING:
        return None

    body_text = _ascii_text(soup.get_text(" ", strip=True))
    required_signals = (
        _HOMEPAGE_TAGLINE,
        _HOMEPAGE_EDITION,
        "Barcelo Palmeraie Oasis Resort - Marrakech",
        _RAW_DATE_HOMEPAGE,
        "Inscriptions ouvertes",
    )
    if any(signal not in body_text for signal in required_signals):
        return None

    if _registration_url(soup) != REGISTRATION_URL:
        return None

    return _build_event(raw_title=_RAW_TITLE_HOMEPAGE, raw_date_text=_RAW_DATE_HOMEPAGE)


def _parse_inscriptions_page(soup: BeautifulSoup) -> ParsedEvent | None:
    if _page_title(soup) != _INSCRIPTIONS_PAGE_TITLE:
        return None

    body_text = _ascii_text(soup.get_text(" ", strip=True))
    required_signals = (
        _INSCRIPTIONS_SUMMARY,
        _INSCRIPTIONS_HEADING,
        _VENUE_NAME,
        _RAW_DATE_INSCRIPTIONS,
    )
    if any(signal not in body_text for signal in required_signals):
        return None

    if _registration_url(soup) != REGISTRATION_URL:
        return None

    return _build_event(
        raw_title=_RAW_TITLE_INSCRIPTIONS,
        raw_date_text=_RAW_DATE_INSCRIPTIONS,
    )


@register_parser("amied_congress")
class AmiedCongressParser:
    name = "amied_congress"

    def discover(self, source: Any) -> Iterator[DiscoveredPage]:
        urls = {str(url).rstrip("/") for url in source.crawl_config.get("seed_urls", [])}
        if HOMEPAGE_URL.rstrip("/") in urls:
            yield DiscoveredPage(url=HOMEPAGE_URL, page_kind="detail")
        if INSCRIPTIONS_URL.rstrip("/") in urls:
            yield DiscoveredPage(url=INSCRIPTIONS_URL, page_kind="detail")

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
            event = _parse_homepage(soup)
            if event is not None:
                yield event
            return

        if _url_matches(content.url, INSCRIPTIONS_URL):
            event = _parse_inscriptions_page(soup)
            if event is not None:
                yield event
            return

        return
