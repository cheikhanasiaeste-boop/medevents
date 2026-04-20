"""events table access."""

from __future__ import annotations

from datetime import date
from typing import Any, cast
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session


def insert_event(
    session: Session,
    *,
    slug: str,
    title: str,
    summary: str | None,
    starts_on: date,
    ends_on: date | None,
    timezone: str | None,
    city: str | None,
    country_iso: str | None,
    venue_name: str | None,
    format: str,
    event_kind: str,
    lifecycle_status: str,
    specialty_codes: list[str],
    organizer_name: str | None,
    source_url: str,
    registration_url: str | None,
) -> UUID:
    """Insert a fresh events row and return its id."""
    row = (
        session.execute(
            text(
                """
                INSERT INTO events (
                    slug, title, summary, starts_on, ends_on, timezone,
                    city, country_iso, venue_name, format, event_kind, lifecycle_status,
                    specialty_codes, organizer_name, source_url, registration_url
                ) VALUES (
                    :slug, :title, :summary, :starts_on, :ends_on, :timezone,
                    :city, :country_iso, :venue_name, :format, :event_kind, :lifecycle_status,
                    :specialty_codes, :organizer_name, :source_url, :registration_url
                )
                RETURNING id
                """
            ),
            {
                "slug": slug,
                "title": title,
                "summary": summary,
                "starts_on": starts_on,
                "ends_on": ends_on,
                "timezone": timezone,
                "city": city,
                "country_iso": country_iso,
                "venue_name": venue_name,
                "format": format,
                "event_kind": event_kind,
                "lifecycle_status": lifecycle_status,
                "specialty_codes": specialty_codes,
                "organizer_name": organizer_name,
                "source_url": source_url,
                "registration_url": registration_url,
            },
        )
        .mappings()
        .one()
    )
    return cast(UUID, row["id"])


def find_event_by_source_local_match(
    session: Session,
    *,
    source_id: UUID,
    normalized_title: str,
    starts_on: date,
) -> UUID | None:
    """Return an event id that matches this source's candidate by (normalized title, start date)."""
    row = (
        session.execute(
            text(
                """
            SELECT e.id
              FROM events e
              JOIN event_sources es ON es.event_id = e.id
             WHERE es.source_id = :source_id
               AND e.starts_on = :starts_on
               AND lower(regexp_replace(e.title, '[^a-z0-9]+', ' ', 'gi')) = :normalized_title
             LIMIT 1
            """
            ),
            {
                "source_id": str(source_id),
                "starts_on": starts_on,
                "normalized_title": normalized_title,
            },
        )
        .mappings()
        .one_or_none()
    )
    return cast(UUID, row["id"]) if row else None


def find_event_by_registration_url(session: Session, registration_url: str) -> UUID | None:
    row = (
        session.execute(
            text("SELECT id FROM events WHERE registration_url = :url LIMIT 1"),
            {"url": registration_url},
        )
        .mappings()
        .one_or_none()
    )
    return cast(UUID, row["id"]) if row else None


_ALLOWED_FIELDS: set[str] = {
    "title",
    "summary",
    "starts_on",
    "ends_on",
    "timezone",
    "city",
    "country_iso",
    "venue_name",
    "format",
    "event_kind",
    "lifecycle_status",
    "specialty_codes",
    "organizer_name",
    "source_url",
    "registration_url",
}


def update_event_fields(
    session: Session,
    *,
    event_id: UUID,
    changes: dict[str, Any],
    material: bool,
) -> None:
    """Patch an existing event. Always bumps last_checked_at; bumps last_changed_at iff material."""
    for k in changes:
        if k not in _ALLOWED_FIELDS:
            raise ValueError(f"{k!r} is not an updatable event column")
    if not changes:
        session.execute(
            text("UPDATE events SET last_checked_at = now() WHERE id = :id"),
            {"id": str(event_id)},
        )
        return

    assignments = ", ".join(f"{k} = :{k}" for k in changes)
    ts_columns = "last_checked_at = now()"
    if material:
        ts_columns += ", last_changed_at = now()"
    params: dict[str, Any] = dict(changes)
    params["id"] = str(event_id)
    session.execute(
        text(f"UPDATE events SET {assignments}, {ts_columns}, updated_at = now() WHERE id = :id"),
        params,
    )
