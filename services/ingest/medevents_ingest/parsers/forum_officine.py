"""Forum de l'Officine parser (`parser_name: forum_officine_tn`).

Handles two public source surfaces via one parse() entry point:

    1. Homepage (`/l_officine/accueil-forum-officine.php`)              -> 1 event
    2. Practical-info page (`/l_officine/infos-pratiques-forum-officine.php`) -> 1 event
    3. Anything else                                                    -> 0 events

The onboarding is intentionally edition-specific for 2026. Prep verification
showed both chosen pages are byte-stable, so the default raw-body content hash
is sufficient here.
"""

from __future__ import annotations

import json
import re
import unicodedata
from collections.abc import Iterator
from typing import Any

from bs4 import BeautifulSoup, Tag

from . import register_parser
from .base import DiscoveredPage, FetchedContent, ParsedEvent, SourcePageRef

HOMEPAGE_URL = "https://www.forumdelofficine.tn/l_officine/accueil-forum-officine.php"
INFO_URL = "https://www.forumdelofficine.tn/l_officine/infos-pratiques-forum-officine.php"
REGISTRATION_URL = (
    "https://main.d17j5ouws4ciim.amplifyapp.com/formulaires/congressiste/"
    "3f6d7b9c1a2e4f5g6h7j8k9m0n1p2q3r"  # pragma: allowlist secret
)

_TITLE = "Forum de l'Officine 2026"
_RAW_TITLE_HOMEPAGE = "Forum de l'Officine 2026"
_RAW_TITLE_INFO = "Forum de l'Officine 2026 - Infos Pratiques"
_HOMEPAGE_PAGE_TITLE = (
    "Forum de l'Officine 2026 - Evenement Pharmaceutique Tunisie | 15-16 Mai Tunis"
)
_INFO_PAGE_TITLE = "Infos Pratiques - Forum de l'Officine 2026 Tunisie"
_HOMEPAGE_META_DESCRIPTION = (
    "Le Forum de l'Officine 2026 est l'evenement incontournable de la pharmacie en "
    "Tunisie. Programme, exposants, workshops - 15 et 16 Mai 2026 au Palais des "
    "Congres de Tunis."
)
_INFO_META_DESCRIPTION = (
    "Tout ce qu'il faut savoir pour le Forum de l'Officine 2026 : badge, application "
    "mobile, foodcourt, parking - 15-16 Mai 2026 au Palais des Congres de Tunis."
)
_HOMEPAGE_OG_DESCRIPTION = (
    "L'evenement incontournable de la pharmacie en Tunisie. 15-16 Mai 2026 au "
    "Palais des Congres de Tunis."
)
_INFO_OG_DESCRIPTION = (
    "Badge, application mobile, foodcourt, parking - tout ce qu'il faut savoir pour "
    "le Forum de l'Officine 2026."
)
_JSONLD_DESCRIPTION_HOMEPAGE = "L'evenement incontournable de la pharmacie en Tunisie"
_JSONLD_DESCRIPTION_INFO = (
    "Informations pratiques pour participer au Forum de l'Officine 2026 a Tunis"
)
_VENUE_NAME = "Palais des Congres de Tunis"
_CITY = "Tunis"
_COUNTRY_ISO = "TN"
_ORGANIZER = "Forum de l'Officine"
_STARTS_ON = "2026-05-15"
_ENDS_ON = "2026-05-16"
_RAW_DATE_HOMEPAGE = "15 et 16 Mai 2026"
_RAW_DATE_INFO = "15-16 Mai 2026"


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


def _meta_content(
    soup: BeautifulSoup,
    *,
    name: str | None = None,
    prop: str | None = None,
) -> str | None:
    attrs: dict[str, str] = {}
    if name is not None:
        attrs["name"] = name
    if prop is not None:
        attrs["property"] = prop
    tag = soup.find("meta", attrs=attrs)
    if not isinstance(tag, Tag):
        return None
    content = tag.get("content")
    if not isinstance(content, str):
        return None
    return _ascii_text(content)


def _find_exact_href(soup: BeautifulSoup, expected: str) -> str | None:
    for link in soup.find_all("a"):
        if not isinstance(link, Tag):
            continue
        href = link.get("href")
        if href == expected:
            return href
    return None


def _iter_json_ld_candidates(payload: Any) -> Iterator[dict[str, Any]]:
    if isinstance(payload, dict):
        yield payload
        graph = payload.get("@graph")
        if isinstance(graph, list):
            for item in graph:
                yield from _iter_json_ld_candidates(item)
        return

    if isinstance(payload, list):
        for item in payload:
            yield from _iter_json_ld_candidates(item)


def _is_event_type(value: Any) -> bool:
    if isinstance(value, str):
        return value == "Event"
    if isinstance(value, list):
        return any(item == "Event" for item in value)
    return False


def _json_ld_event(soup: BeautifulSoup) -> dict[str, Any] | None:
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        if not isinstance(script, Tag):
            continue
        raw_payload = script.get_text(strip=True)
        if not raw_payload:
            continue
        try:
            payload = json.loads(raw_payload)
        except json.JSONDecodeError:
            continue

        for candidate in _iter_json_ld_candidates(payload):
            if _is_event_type(candidate.get("@type")):
                return candidate
    return None


def _validate_json_ld_event(
    payload: dict[str, Any],
    *,
    expected_name: str,
    expected_description: str,
) -> str | None:
    raw_title = payload.get("name")
    if not isinstance(raw_title, str):
        return None
    if _ascii_text(raw_title) != expected_name:
        return None

    description = payload.get("description")
    if not isinstance(description, str):
        return None
    if _ascii_text(description) != expected_description:
        return None

    start_date = payload.get("startDate")
    end_date = payload.get("endDate")
    if not isinstance(start_date, str) or not isinstance(end_date, str):
        return None
    if start_date[:10] != _STARTS_ON or end_date[:10] != _ENDS_ON:
        return None

    location = payload.get("location")
    if not isinstance(location, dict):
        return None
    venue_name = location.get("name")
    if not isinstance(venue_name, str) or _ascii_text(venue_name) != _VENUE_NAME:
        return None

    address = location.get("address")
    if not isinstance(address, dict):
        return None
    locality = address.get("addressLocality")
    country = address.get("addressCountry")
    if not isinstance(locality, str) or _ascii_text(locality) != _CITY:
        return None
    if country != _COUNTRY_ISO:
        return None

    organizer = payload.get("organizer")
    if not isinstance(organizer, dict):
        return None
    organizer_name = organizer.get("name")
    if not isinstance(organizer_name, str) or _ascii_text(organizer_name) != _ORGANIZER:
        return None

    return _ascii_text(raw_title)


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

    if _meta_content(soup, name="description") != _HOMEPAGE_META_DESCRIPTION:
        return None

    if _meta_content(soup, prop="og:description") != _HOMEPAGE_OG_DESCRIPTION:
        return None

    if _find_exact_href(soup, REGISTRATION_URL) != REGISTRATION_URL:
        return None

    # The page also embeds a large assistant-widget session blob with stale
    # May 1-2 dates; only the explicit Schema.org Event contract is trusted.
    payload = _json_ld_event(soup)
    if payload is None:
        return None
    raw_title = _validate_json_ld_event(
        payload,
        expected_name=_RAW_TITLE_HOMEPAGE,
        expected_description=_JSONLD_DESCRIPTION_HOMEPAGE,
    )
    if raw_title is None:
        return None

    return _build_event(raw_title=raw_title, raw_date_text=_RAW_DATE_HOMEPAGE)


def _parse_info_page(soup: BeautifulSoup) -> ParsedEvent | None:
    if _page_title(soup) != _INFO_PAGE_TITLE:
        return None

    if _meta_content(soup, name="description") != _INFO_META_DESCRIPTION:
        return None

    if _meta_content(soup, prop="og:description") != _INFO_OG_DESCRIPTION:
        return None

    if _find_exact_href(soup, REGISTRATION_URL) != REGISTRATION_URL:
        return None

    payload = _json_ld_event(soup)
    if payload is None:
        return None
    raw_title = _validate_json_ld_event(
        payload,
        expected_name=_RAW_TITLE_INFO,
        expected_description=_JSONLD_DESCRIPTION_INFO,
    )
    if raw_title is None:
        return None

    return _build_event(raw_title=raw_title, raw_date_text=_RAW_DATE_INFO)


@register_parser("forum_officine_tn")
class ForumOfficineParser:
    name = "forum_officine_tn"

    def discover(self, source: Any) -> Iterator[DiscoveredPage]:
        urls = {str(url).rstrip("/") for url in source.crawl_config.get("seed_urls", [])}
        if HOMEPAGE_URL.rstrip("/") in urls:
            yield DiscoveredPage(url=HOMEPAGE_URL, page_kind="detail")
        if INFO_URL.rstrip("/") in urls:
            yield DiscoveredPage(url=INFO_URL, page_kind="detail")

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

        if _url_matches(content.url, INFO_URL):
            event = _parse_info_page(soup)
            if event is not None:
                yield event
            return

        return
