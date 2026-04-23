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
from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from .models import Source
from .parsers import parser_for
from .parsers.base import ParsedEvent, ParserReviewRequest, SourcePageRef
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
    get_last_content_hash_by_url,
    record_fetch,
    upsert_source_page,
)
from .repositories.sources import (
    get_active_due_sources,
    get_active_sources,
    get_source_by_code,
    update_source_run_status,
)


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


_FREQUENCY_DELTA: dict[str, timedelta] = {
    "daily": timedelta(days=1),
    "weekly": timedelta(days=7),
    "biweekly": timedelta(days=14),
    "monthly": timedelta(days=30),
}


def is_due(
    frequency: str,
    last_crawled_at: datetime | None,
    *,
    now: datetime,
) -> bool:
    """Return True when a source is due for a re-crawl.

    Spec §4 D1: crawl_frequency is one of the four string literals in
    `_FREQUENCY_DELTA`. A source that has never been crawled
    (`last_crawled_at is None`) is ALWAYS due. Otherwise, due iff
    `last_crawled_at + frequency_delta <= now`.

    Kept as a Python-side pure function for unit testability even
    though the production batch path uses SQL-side filtering in
    `get_active_due_sources()` (spec §4 D2).
    """
    if last_crawled_at is None:
        return True
    delta = _FREQUENCY_DELTA[frequency]
    return last_crawled_at + delta <= now


def run_source(
    session: Session,
    *,
    source_code: str,
    force: bool = False,
    dry_run: bool = False,
) -> PipelineResult:
    """Run ingest for a single source.

    `force` is a plumbing-only parameter in W3.2a — it threads through from
    the CLI so W3.2b's due-selection logic can honor it. No behavioral
    effect in this wave. Spec §4 D6 locks the keyword-only shape.

    When `dry_run=True` (W3.2f), every DB write in this call tree is
    skipped — success/error bookkeeping, source-page upsert, fetch
    recording, event insert/update/link, and review-item creation — while
    reads, discover/fetch/parse, and counters still run. The caller still
    gets a populated PipelineResult and error paths still re-raise so the
    batch-level summary behavior is unchanged.

    On completion (real run only), writes
    `sources.last_crawled_at / last_success_at` via
    `update_source_run_status("success")` on the caller's session (commits
    with the main transaction). On error (real run only), writes
    `last_crawled_at / last_error_at / last_error_message` via a fresh
    short-lived session so the state survives the main transaction's
    rollback (spec §4 D3).
    """
    # Force is currently plumbing-only; silence the "unused argument" lint.
    _ = force

    source = get_source_by_code(session, source_code)
    if source is None:
        # Source-not-found is an error from the pipeline's perspective.
        if not dry_run:
            _record_error_bookkeeping_fresh_session(
                source_code=source_code,
                error_message=f"source '{source_code}' not found",
            )
        raise ValueError(f"source '{source_code}' not found")

    try:
        result = _run_source_inner(session, source=source, dry_run=dry_run)
    except Exception as exc:
        if not dry_run:
            _record_error_bookkeeping_fresh_session(
                source_id=source.id,
                error_message=str(exc) or exc.__class__.__name__,
            )
        raise

    if not dry_run:
        update_source_run_status(session, source_id=source.id, status="success")
    return result


def _run_source_inner(
    session: Session,
    *,
    source: Source,
    dry_run: bool = False,
) -> PipelineResult:
    parser = parser_for(source.parser_name)

    pages_fetched = 0
    pages_skipped_unchanged = 0
    events_created = 0
    events_updated = 0
    review_items_created = 0

    for discovered in parser.discover(source):
        if dry_run:
            source_page_id = UUID("00000000-0000-0000-0000-000000000000")
        else:
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
            if dry_run:
                print(
                    f"dry_run source={source.code} page={discovered.url} "
                    f"kind={discovered.page_kind} "
                    f"status=would_file_review_item_source_blocked"
                )
            else:
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
        # Spec §4 D5: under dry-run we lookup the previous hash by
        # (source_id, url) because the dry-run branch synthesizes a
        # zero-UUID `source_page_id` instead of upserting, so the by-id
        # lookup would always miss. The real path keeps the by-id lookup
        # since it has just upserted the row.
        if dry_run:
            previous_hash = get_last_content_hash_by_url(
                session, source_id=source.id, url=discovered.url
            )
        else:
            previous_hash = get_last_content_hash(session, source_page_id)
        if dry_run:
            status = (
                "would_skip_unchanged"
                if previous_hash == content.content_hash
                else "would_fetch_and_parse"
            )
            print(
                f"dry_run source={source.code} page={discovered.url} "
                f"kind={discovered.page_kind} status={status}"
            )
        else:
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
            if isinstance(candidate, ParserReviewRequest):
                # Parser-requested review_item (e.g., ADA silent-drop drift
                # signal). Route to `insert_review_item` and move on —
                # deliberately do NOT flip `any_event_emitted`: a page that
                # yields ONLY a ParserReviewRequest (every row dropped) still
                # trips the zero-events branch below, producing a second
                # signal. Two review_items is fine; the admin UI separates
                # them by details_json.reason.
                if dry_run:
                    print(
                        f"dry_run source={source.code} page={discovered.url} "
                        f"kind={discovered.page_kind} "
                        f"status=would_file_review_item_{candidate.kind}"
                    )
                else:
                    insert_review_item(
                        session,
                        kind=candidate.kind,
                        source_id=source.id,
                        source_page_id=source_page_id,
                        event_id=None,
                        details=candidate.details,
                    )
                review_items_created += 1
                continue
            any_event_emitted = True
            created, updated = _persist_event(
                session,
                source_id=source.id,
                source_page_id=source_page_id,
                candidate=candidate,
                source_code=source.code,
                dry_run=dry_run,
            )
            events_created += created
            events_updated += updated

        if not any_event_emitted and discovered.page_kind == "listing":
            if dry_run:
                print(
                    f"dry_run source={source.code} page={discovered.url} "
                    f"kind=listing status=would_file_review_item_parser_failure"
                )
            else:
                insert_review_item(
                    session,
                    kind="parser_failure",
                    source_id=source.id,
                    source_page_id=source_page_id,
                    event_id=None,
                    details={
                        "page_url": discovered.url,
                        "page_kind": "listing",
                        "reason": "zero_events",
                    },
                )
            review_items_created += 1
        elif not any_event_emitted and discovered.page_kind == "detail":
            if dry_run:
                print(
                    f"dry_run source={source.code} page={discovered.url} "
                    f"kind=detail status=would_file_review_item_parser_failure"
                )
            else:
                insert_review_item(
                    session,
                    kind="parser_failure",
                    source_id=source.id,
                    source_page_id=source_page_id,
                    event_id=None,
                    details={
                        "page_url": discovered.url,
                        "page_kind": "detail",
                        "reason": "zero_events",
                    },
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
    source_code: str,
    dry_run: bool = False,
) -> tuple[int, int]:
    """Find or insert the event, link via event_sources. Returns (created, updated) counts.

    Under `dry_run=True`, the find-or-match classification still runs (reads
    only), then we emit a single `dry_run source=... action=would_{create,update} ...`
    preview line and return the same (created, updated) tuple the real path
    would have returned. `insert_event`, `update_event_fields`, and
    `upsert_event_source` are all skipped. `source_code` is passed in
    unconditionally so the preview line is meaningful; it's ignored on the
    real path.
    """
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

    if dry_run:
        action = "would_create" if match_id is None else "would_update"
        venue = candidate.venue_name or ""
        print(
            f"dry_run source={source_code} action={action} "
            f'title="{candidate.title}" starts_on={candidate.starts_on} '
            f'city={candidate.city} venue="{venue}"'
        )
        return (1, 0) if match_id is None else (0, 1)

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
        """Record a field change only when the candidate has a concrete value.

        Spec §4 D2 (W3.2c): when ``new_val is None`` and the existing row
        already has a non-None value, the candidate is treated as "no
        contribution" rather than an explicit clear — the existing value is
        preserved.  When both are None, or when ``new_val`` is non-None and
        differs from the persisted value, the existing change-recording
        behaviour applies.

        Rationale: shipped parsers MUST NOT invent filler copy; ``None``
        means "I didn't extract this," not "clear the field."
        """
        nonlocal material
        old_val = row[field]
        normalized_new = new_val
        if field in {"starts_on", "ends_on"} and isinstance(new_val, str):
            normalized_new = date.fromisoformat(new_val) if new_val else None
        # Spec §4 D2: candidate None means "no contribution", not "clear".
        if normalized_new is None and old_val is not None:
            return
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


@dataclass(frozen=True)
class BatchResult:
    """Aggregate outcome of a `run --all` invocation (spec §3)."""

    sources_selected: int
    succeeded: int
    failed: int
    skipped_not_due: int


def run_all(
    session: Session,
    *,
    force: bool,
    now: datetime,
    dry_run: bool = False,
) -> BatchResult:
    """Run every active source that is due (or every active source if `force`).

    Per-source failures are caught and logged to stderr; the batch continues
    (spec §4 D4). Returns an aggregated BatchResult. The caller decides the
    process exit code from the result.

    `now` is captured once and passed in so every source in the batch is
    evaluated against the same moment, and tests can inject a deterministic
    timestamp (spec §4 D5).

    Bookkeeping: each source goes through `run_source()` which already writes
    `last_crawled_at` / `last_success_at` / `last_error_*` via the W3.2a
    fresh-session helper on the error path. Under `dry_run=True` that
    bookkeeping is skipped and the per-source + batch summary lines are
    prefixed with `dry_run=1 ` so operators can spot-check which line came
    from which mode.
    """
    import sys  # local import to keep module-top imports focused

    if force:
        # Under --force we still honor is_active=false (spec §4 D3).
        selected = get_active_sources(session)
        skipped_not_due = 0
    else:
        all_active = get_active_sources(session)
        due = get_active_due_sources(session, now=now)
        due_codes = {s.code for s in due}
        selected = due
        skipped_not_due = sum(1 for s in all_active if s.code not in due_codes)

        # Print skipped-not-due per-source lines for operator visibility.
        for s in all_active:
            if s.code not in due_codes:
                next_due = _next_due_at(s.crawl_frequency, s.last_crawled_at)
                print(
                    f"source={s.code} skipped=not_due "
                    f"(last_crawled_at={s.last_crawled_at}, next_due={next_due})"
                )

    prefix = "dry_run=1 " if dry_run else ""
    succeeded = 0
    failed = 0
    for src in selected:
        try:
            result = run_source(
                session,
                source_code=src.code,
                force=force,
                dry_run=dry_run,
            )
            print(
                f"{prefix}source={result.source_code} "
                f"fetched={result.pages_fetched} "
                f"skipped_unchanged={result.pages_skipped_unchanged} "
                f"created={result.events_created} "
                f"updated={result.events_updated} "
                f"review_items={result.review_items_created}"
            )
            succeeded += 1
        except Exception as exc:
            # `run_source`'s error path already wrote bookkeeping via a fresh
            # session; we just need to log and continue.
            print(
                f"{prefix}source={src.code} error={exc.__class__.__name__}: {exc}",
                file=sys.stderr,
            )
            session.rollback()
            failed += 1

    print(
        f"{prefix}batch=run-all sources={len(selected)} "
        f"succeeded={succeeded} failed={failed} "
        f"skipped_not_due={skipped_not_due}"
    )
    return BatchResult(
        sources_selected=len(selected),
        succeeded=succeeded,
        failed=failed,
        skipped_not_due=skipped_not_due,
    )


def _next_due_at(frequency: str, last_crawled_at: datetime | None) -> str:
    """Format the next-due timestamp for the skipped=not_due output line."""
    if last_crawled_at is None:
        return "now (never crawled)"
    return (last_crawled_at + _FREQUENCY_DELTA[frequency]).isoformat()
