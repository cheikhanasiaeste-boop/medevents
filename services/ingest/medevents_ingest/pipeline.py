"""Ingestion pipeline orchestration.

Single public entrypoint: run_source(session, source_code) -> PipelineResult.

Flow (mirrors W2 spec §6):
  1. resolve source by code; resolve parser by parser_name
  2. parser.discover(source) → iterate DiscoveredPage
  3. upsert_source_page(source_id, url, page_kind)
  4. parser.fetch(page) → FetchedContent
  5. content-hash gate: if unchanged since last successful fetch, skip parse
  6. parser.parse(content) → iterator of ParsedEvent
  7. for each candidate: find-or-insert with source-local match; bump last_checked_at
     or last_changed_at as appropriate
  8. write event_sources row for each event + source + page triple
  9. emit review_items for ambiguous cases
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from .models import Source
from .parsers import parser_for
from .parsers.base import ParsedEvent, SourcePageRef
from .repositories.event_sources import upsert_event_source
from .repositories.events import (
    find_event_by_registration_url,
    find_event_by_source_local_match,
    insert_event,
    update_event_fields,
)
from .repositories.review_items import insert_review_item
from .repositories.source_pages import (
    get_last_content_hash,
    record_fetch,
    upsert_source_page,
)
from .repositories.sources import get_source_by_code, update_source_run_status


@dataclass(frozen=True)
class PipelineResult:
    source_code: str
    pages_fetched: int
    pages_skipped_unchanged: int
    events_created: int
    events_updated: int
    review_items_created: int


_MATERIAL_FIELDS: frozenset[str] = frozenset(
    {
        "title",
        "starts_on",
        "ends_on",
        "format",
        "lifecycle_status",
        "city",
        "country_iso",
        "venue_name",
        "registration_url",
    }
)


def run_source(
    session: Session,
    *,
    source_code: str,
    force: bool = False,
) -> PipelineResult:
    """Run ingest for a single source.

    `force` is a plumbing-only parameter in W3.2a — it threads through from
    the CLI so W3.2b's due-selection logic can honor it. No behavioral
    effect in this wave. Spec §4 D6 locks the keyword-only shape.

    On completion, writes `sources.last_crawled_at / last_success_at` via
    `update_source_run_status("success")` on the caller's session (commits
    with the main transaction). On error, writes `last_crawled_at /
    last_error_at / last_error_message` via a fresh short-lived session so
    the state survives the main transaction's rollback (spec §4 D3).
    """
    # Force is currently plumbing-only; silence the "unused argument" lint.
    _ = force

    source = get_source_by_code(session, source_code)
    if source is None:
        # Source-not-found is an error from the pipeline's perspective.
        _record_error_bookkeeping_fresh_session(
            source_code=source_code,
            error_message=f"source '{source_code}' not found",
        )
        raise ValueError(f"source '{source_code}' not found")

    try:
        result = _run_source_inner(session, source=source)
    except Exception as exc:
        _record_error_bookkeeping_fresh_session(
            source_id=source.id,
            error_message=str(exc) or exc.__class__.__name__,
        )
        raise

    update_source_run_status(session, source_id=source.id, status="success")
    return result


def _run_source_inner(session: Session, *, source: Source) -> PipelineResult:
    parser = parser_for(source.parser_name)

    pages_fetched = 0
    pages_skipped_unchanged = 0
    events_created = 0
    events_updated = 0
    review_items_created = 0

    for discovered in parser.discover(source):
        source_page_id = upsert_source_page(
            session,
            source_id=source.id,
            url=discovered.url,
            page_kind=discovered.page_kind,
            parser_name=parser.name,
        )
        page_ref = SourcePageRef(
            id=source_page_id,
            source_id=source.id,
            url=discovered.url,
            page_kind=discovered.page_kind,
            parser_name=parser.name,
        )

        try:
            content = parser.fetch(page_ref)
        except Exception as exc:  # all fetch failures become review items
            insert_review_item(
                session,
                kind="source_blocked",
                source_id=source.id,
                source_page_id=source_page_id,
                event_id=None,
                details={"error": str(exc)},
            )
            record_fetch(
                session,
                source_page_id=source_page_id,
                content_hash=None,
                fetched_at=datetime.now(UTC),
                fetch_status="error",
            )
            review_items_created += 1
            continue

        pages_fetched += 1
        previous_hash = get_last_content_hash(session, source_page_id)
        record_fetch(
            session,
            source_page_id=source_page_id,
            content_hash=content.content_hash,
            fetched_at=content.fetched_at,
            fetch_status="ok",
        )
        if previous_hash == content.content_hash:
            pages_skipped_unchanged += 1
            continue

        any_event_emitted = False
        for candidate in parser.parse(content):
            any_event_emitted = True
            created, updated = _persist_event(
                session,
                source_id=source.id,
                source_page_id=source_page_id,
                candidate=candidate,
            )
            events_created += created
            events_updated += updated

        if not any_event_emitted and discovered.page_kind == "listing":
            insert_review_item(
                session,
                kind="parser_failure",
                source_id=source.id,
                source_page_id=source_page_id,
                event_id=None,
                details={"reason": "listing page parsed 0 events; check template drift"},
            )
            review_items_created += 1

    return PipelineResult(
        source_code=source.code,
        pages_fetched=pages_fetched,
        pages_skipped_unchanged=pages_skipped_unchanged,
        events_created=events_created,
        events_updated=events_updated,
        review_items_created=review_items_created,
    )


def _record_error_bookkeeping_fresh_session(
    *,
    source_id: UUID | None = None,
    source_code: str | None = None,
    error_message: str,
) -> None:
    """Write error bookkeeping in a NEW session so rollback of the caller's
    session doesn't take the error state down with it (spec §4 D3).

    Accepts either `source_id` (when the source was successfully resolved)
    OR `source_code` (when the source-not-found branch short-circuited
    before we had an id). If a code is given but the source row doesn't
    exist, silently returns — there's nothing to update.
    """
    from .db import session_scope as _fresh_session_scope

    with _fresh_session_scope() as fresh:
        resolved_id = source_id
        if resolved_id is None and source_code is not None:
            src = get_source_by_code(fresh, source_code)
            if src is None:
                return
            resolved_id = src.id
        if resolved_id is None:
            return
        update_source_run_status(
            fresh,
            source_id=resolved_id,
            status="error",
            error_message=error_message,
        )


def _persist_event(
    session: Session,
    *,
    source_id: UUID,
    source_page_id: UUID,
    candidate: ParsedEvent,
) -> tuple[int, int]:
    """Find or insert the event, link via event_sources. Returns (created, updated) counts."""
    normalized_title = _normalize_title(candidate.title)
    starts_on = date.fromisoformat(candidate.starts_on)

    match_id = find_event_by_source_local_match(
        session,
        source_id=source_id,
        normalized_title=normalized_title,
        starts_on=starts_on,
    )
    if match_id is None and candidate.registration_url:
        url_match_id = find_event_by_registration_url(session, candidate.registration_url)
        if url_match_id is not None:
            # Only use this match if the start date also aligns — prevents collapsing two
            # distinct occurrences of the same recurring course that share a registration URL.
            row = (
                session.execute(
                    text("SELECT starts_on FROM events WHERE id = :id"),
                    {"id": str(url_match_id)},
                )
                .mappings()
                .one()
            )
            if row["starts_on"] == starts_on:
                match_id = url_match_id

    if match_id is None:
        event_id = insert_event(
            session,
            slug=_slugify(candidate.title, starts_on),
            title=candidate.title,
            summary=candidate.summary,
            starts_on=starts_on,
            ends_on=date.fromisoformat(candidate.ends_on) if candidate.ends_on else None,
            timezone=candidate.timezone,
            city=candidate.city,
            country_iso=candidate.country_iso,
            venue_name=candidate.venue_name,
            format=candidate.format,
            event_kind=candidate.event_kind,
            lifecycle_status=candidate.lifecycle_status,
            specialty_codes=candidate.specialty_codes,
            organizer_name=candidate.organizer_name,
            source_url=candidate.source_url,
            registration_url=candidate.registration_url,
        )
        created_delta = 1
        updated_delta = 0
    else:
        event_id = match_id
        changes, material = _diff_event_fields(session, event_id, candidate)
        update_event_fields(session, event_id=event_id, changes=changes, material=material)
        created_delta = 0
        updated_delta = 1

    upsert_event_source(
        session,
        event_id=event_id,
        source_id=source_id,
        source_page_id=source_page_id,
        source_url=candidate.source_url,
        raw_title=candidate.raw_title,
        raw_date_text=candidate.raw_date_text,
        is_primary=True,
    )
    return created_delta, updated_delta


def _diff_event_fields(
    session: Session,
    event_id: UUID,
    candidate: ParsedEvent,
) -> tuple[dict[str, Any], bool]:
    """Compare the live row to the candidate; return (changes, is_material)."""
    row = (
        session.execute(
            text(
                "SELECT title, summary, starts_on, ends_on, timezone, city, country_iso, "
                "venue_name, format, event_kind, lifecycle_status, registration_url "
                "FROM events WHERE id = :id"
            ),
            {"id": str(event_id)},
        )
        .mappings()
        .one()
    )

    changes: dict[str, Any] = {}
    material = False

    def set_if_changed(field: str, new_val: Any) -> None:
        nonlocal material
        old_val = row[field]
        normalized_new = new_val
        if field in {"starts_on", "ends_on"} and isinstance(new_val, str):
            normalized_new = date.fromisoformat(new_val) if new_val else None
        if old_val != normalized_new:
            changes[field] = normalized_new
            if field in _MATERIAL_FIELDS:
                material = True

    set_if_changed("title", candidate.title)
    set_if_changed("summary", candidate.summary)
    set_if_changed("starts_on", candidate.starts_on)
    set_if_changed("ends_on", candidate.ends_on)
    set_if_changed("timezone", candidate.timezone)
    set_if_changed("city", candidate.city)
    set_if_changed("country_iso", candidate.country_iso)
    set_if_changed("venue_name", candidate.venue_name)
    set_if_changed("format", candidate.format)
    set_if_changed("event_kind", candidate.event_kind)
    set_if_changed("lifecycle_status", candidate.lifecycle_status)
    set_if_changed("registration_url", candidate.registration_url)

    return changes, material


def _normalize_title(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()


def _slugify(title: str, starts_on: date) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return f"{base[:60].rstrip('-')}-{starts_on.isoformat()}"
