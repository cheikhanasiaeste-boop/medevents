"""ADA source parser (`parser_name: ada_listing`).

Handles three page shapes via one parse() entry point:

    1. ADA CE live-workshops schedule   -> N events per page (listing)
    2. ADA Scientific Session landing   -> 1 event per page (detail)
    3. Anything else (hub, non-event)   -> 0 events

The discover() entrypoint yields a fixed seed set from source.crawl_config.seed_urls;
no recursive crawling in W2 per spec §3.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterator
from typing import Any

from bs4 import BeautifulSoup, Tag

from ..normalize import infer_event_kind, infer_format, parse_date_range, parse_location
from . import register_parser
from .base import DiscoveredPage, FetchedContent, ParsedEvent, SourcePageRef

_ADA_HOST = "www.ada.org"
_ENGAGE_HOST = "engage.ada.org"

# ADA is a Sitecore site that embeds rotating per-request tracking attributes
# (featured-story carousel, item versions) into every page. Those attributes have
# nothing to do with the event content, so stripping them before hashing is what
# makes the pipeline's content-hash skip gate actually fire on unchanged pages.
_SITECORE_DYNAMIC_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"data-sc-page-name(?:-full-path)?='[^']*'"),
    re.compile(r"data-sc-item-(?:uri|id)='[^']*'"),
    re.compile(r'itemUri:\s*"sitecore://[^"]*"'),
)


def _normalize_body_for_hashing(body: bytes) -> bytes:
    """Strip ADA/Sitecore per-request tracking attributes before hashing.

    The body itself is passed to the parser unchanged — this only affects the
    content_hash used by the pipeline's skip gate.
    """
    text_val = body.decode("utf-8", errors="replace")
    for pat in _SITECORE_DYNAMIC_PATTERNS:
        text_val = pat.sub("", text_val)
    return text_val.encode("utf-8")


@register_parser("ada_listing")
class AdaListingParser:
    name = "ada_listing"

    def discover(self, source: Any) -> Iterator[DiscoveredPage]:
        """Yield the seed pages configured on the source.

        `source.crawl_config["seed_urls"]` is a list of absolute URLs.
          - workshops schedule page -> page_kind='listing'
          - scientific-session landing / any other ADA-hosted page -> page_kind='detail'
        """
        for url in source.crawl_config.get("seed_urls", []):
            kind = "listing" if "ada-ce-live-workshops" in url else "detail"
            yield DiscoveredPage(url=url, page_kind=kind)

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

        if self._is_scientific_session_landing(content.url, soup):
            yield from self._parse_scientific_session(content, soup)
            return

        if self._looks_like_workshops_schedule(soup):
            yield from self._parse_workshops_schedule(content, soup)
            return

        return  # hub / non-event pages

    # ----- page classifiers -----

    @staticmethod
    def _is_scientific_session_landing(url: str, soup: BeautifulSoup) -> bool:
        if "/education/scientific-session" not in url:
            return False
        # Exclude the CE-offering sub-page /scientific-session/continuing-education
        # which also matches the substring — only the landing page itself qualifies.
        if url.rstrip("/").endswith("/continuing-education"):
            return False
        meta = soup.find("meta", attrs={"name": "description"})
        if not isinstance(meta, Tag):
            return False
        content_val = meta.get("content")
        content_str = content_val if isinstance(content_val, str) else ""
        return "scientific session" in content_str.lower()

    @staticmethod
    def _looks_like_workshops_schedule(soup: BeautifulSoup) -> bool:
        return soup.find("td", class_="cel22airwaves-left") is not None

    # ----- page parsers -----

    def _parse_scientific_session(
        self, content: FetchedContent, soup: BeautifulSoup
    ) -> Iterator[ParsedEvent]:
        meta = soup.find("meta", attrs={"name": "description"})
        desc = ""
        if isinstance(meta, Tag):
            raw_desc = meta.get("content")
            desc = (raw_desc if isinstance(raw_desc, str) else "").strip()
        og_title = soup.find("meta", attrs={"property": "og:title"})
        title = "ADA Scientific Session"
        if isinstance(og_title, Tag):
            raw_og = og_title.get("content")
            title = (raw_og if isinstance(raw_og, str) else title).strip()

        # Expected shape: "...Oct. 8-10, 2026 in Indianapolis." — supports hyphen OR en-dash.
        m = re.search(
            r"(?P<month>[A-Za-z]+\.?)\s+(?P<d1>\d{1,2})[\u2013\u2014\-]"
            r"(?P<d2>\d{1,2}),\s*(?P<year>\d{4})\s+in\s+(?P<city>[A-Za-z ]+)",
            desc,
        )
        if not m:
            return
        year = int(m.group("year"))
        d = parse_date_range(
            f"{m.group('month')} {m.group('d1')}\u2013{m.group('d2')}",
            page_year=year,
        )
        if d is None:
            return

        title_match = re.search(
            r"ADA\s+\d{4}\s+Scientific\s+Session", desc + " " + title, flags=re.IGNORECASE
        )
        resolved_title = title_match.group(0) if title_match else f"ADA {year} Scientific Session"
        city = m.group("city").strip()

        yield ParsedEvent(
            title=resolved_title,
            summary=desc or None,
            starts_on=d.starts_on.isoformat(),
            ends_on=d.ends_on.isoformat() if d.ends_on else None,
            timezone=None,
            city=city,
            country_iso="US",
            venue_name=None,
            format="in_person",
            event_kind="conference",
            lifecycle_status="active",
            specialty_codes=[],
            organizer_name="American Dental Association",
            source_url=content.url,
            registration_url=None,
            raw_title=title,
            raw_date_text=m.group(0),
        )

    def _parse_workshops_schedule(
        self, content: FetchedContent, soup: BeautifulSoup
    ) -> Iterator[ParsedEvent]:
        page_year = self._infer_page_year(soup)

        for left in soup.find_all("td", class_="cel22airwaves-left"):
            right = left.find_next_sibling("td", class_="cel22airwaves-right")
            if not isinstance(right, Tag):
                continue
            raw_date = left.get_text(" ", strip=True)
            ev = self._row_to_event(
                raw_date=raw_date,
                right=right,
                page_year=page_year,
                content=content,
                listing_url=content.url,
            )
            if ev is not None:
                yield ev

    @staticmethod
    def _infer_page_year(soup: BeautifulSoup) -> int | None:
        for sel_name, sel_attrs in [
            ("meta", {"property": "og:title"}),
            ("title", {}),
            ("h1", {}),
        ]:
            el = soup.find(sel_name, attrs=sel_attrs or {})
            if isinstance(el, Tag):
                if sel_name == "meta":
                    raw_val = el.get("content")
                    text_val: str = raw_val if isinstance(raw_val, str) else ""
                else:
                    text_val = el.get_text(" ", strip=True)
                m = re.search(r"(20\d{2})", text_val)
                if m:
                    return int(m.group(1))
        first_kb = soup.get_text(" ", strip=True)[:1024]
        m = re.search(r"\b(20\d{2})\b", first_kb)
        return int(m.group(1)) if m else None

    def _row_to_event(
        self,
        *,
        raw_date: str,
        right: Tag,
        page_year: int | None,
        content: FetchedContent,
        listing_url: str,
    ) -> ParsedEvent | None:
        anchor = right.find("a")
        if not isinstance(anchor, Tag):
            return None
        href = str(anchor.get("href", "")).strip()
        if not href:
            return None

        title = anchor.get_text(" ", strip=True)
        if not title:
            return None

        location_tag = right.find("strong")
        raw_location = (
            location_tag.get_text(" ", strip=True) if isinstance(location_tag, Tag) else ""
        )
        loc = parse_location(raw_location, default_country_iso="US")

        d = parse_date_range(raw_date, page_year=page_year)
        if d is None:
            return None

        if _ENGAGE_HOST in href or (href.startswith("http") and _ADA_HOST not in href):
            # External registration URL (e.g. engage.ada.org): listing page is source,
            # external URL is the registration link.
            source_url = listing_url
            registration_url: str | None = href
        elif href.startswith("/"):
            # ADA-relative path: the listing page is the canonical source for these events.
            source_url = listing_url
            registration_url = None
        elif href.startswith(f"https://{_ADA_HOST}"):
            source_url = listing_url
            registration_url = None
        else:
            return None

        # All rows on the live-workshops schedule page are in-person events.
        # Fallback to infer_format / infer_event_kind for rows with explicit keywords;
        # otherwise default to in_person / workshop since this is the workshops schedule.
        fmt = infer_format(title)
        if fmt == "unknown":
            fmt = "in_person"
        kind = infer_event_kind(title)
        if kind == "other":
            kind = "workshop"

        return ParsedEvent(
            title=title,
            summary=None,
            starts_on=d.starts_on.isoformat(),
            ends_on=d.ends_on.isoformat() if d.ends_on else None,
            timezone=None,
            city=loc.city,
            country_iso=loc.country_iso or "US",
            venue_name=loc.venue_name,
            format=fmt,
            event_kind=kind,
            lifecycle_status="active",
            specialty_codes=[],
            organizer_name="American Dental Association",
            source_url=source_url,
            registration_url=registration_url,
            raw_title=title,
            raw_date_text=raw_date,
        )
