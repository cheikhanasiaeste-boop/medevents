"""Parser protocol + shared types.

A parser is anything implementing this Protocol, registered via @register_parser
under a string code that matches `sources.parser_name`.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime
from typing import Any, Protocol, runtime_checkable
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DiscoveredPage(BaseModel):
    """A URL surfaced by Parser.discover()."""

    model_config = ConfigDict(extra="forbid")

    url: str
    page_kind: str  # 'listing' | 'detail' | 'pdf' | 'unknown'


class FetchedContent(BaseModel):
    """Raw fetch result. Parser.parse() consumes this."""

    model_config = ConfigDict(extra="forbid")

    url: str
    status_code: int
    content_type: str
    body: bytes
    fetched_at: datetime
    content_hash: str


class ParsedEvent(BaseModel):
    """Output of Parser.parse(): the event fields the pipeline will write to `events`."""

    model_config = ConfigDict(extra="forbid")

    title: str
    summary: str | None = None
    starts_on: str  # ISO date YYYY-MM-DD
    ends_on: str | None = None
    timezone: str | None = None
    city: str | None = None
    country_iso: str | None = None
    venue_name: str | None = None
    format: str = "unknown"
    event_kind: str = "other"
    lifecycle_status: str = "active"
    specialty_codes: list[str] = []
    organizer_name: str | None = None
    source_url: str
    registration_url: str | None = None
    raw_title: str | None = None
    raw_date_text: str | None = None


class SourcePageRef(BaseModel):
    """Minimal `source_pages` row passed to Parser.fetch()."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    source_id: UUID
    url: str
    page_kind: str
    parser_name: str | None = None


@runtime_checkable
class Parser(Protocol):
    """Per-source parser interface. Implementations live in services/ingest/medevents_ingest/parsers/{source_code}.py"""

    name: str

    def discover(self, source: Any) -> Iterator[DiscoveredPage]:
        """Yield candidate URLs for this source."""

    def fetch(self, page: SourcePageRef) -> FetchedContent:
        """Fetch a single page. Default impl typically uses httpx; override for Playwright."""

    def parse(self, content: FetchedContent) -> Iterator[ParsedEvent]:
        """Yield 0, 1, or N events extracted from the fetched content.

        Listing pages yield one event per schedule row. Detail pages typically yield
        one event. Non-event pages yield nothing.
        """
