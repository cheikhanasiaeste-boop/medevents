"""event_sources table access."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session


def upsert_event_source(
    session: Session,
    *,
    event_id: UUID,
    source_id: UUID,
    source_page_id: UUID | None,
    source_url: str,
    raw_title: str | None,
    raw_date_text: str | None,
    is_primary: bool,
) -> None:
    """Insert-or-update the event_sources row linking an event to a source.

    The table has two partial unique indexes:
      - (event_id, source_page_id) WHERE source_page_id IS NOT NULL
      - (event_id, source_url)     WHERE source_page_id IS NULL
    The upsert targets whichever is applicable.
    """
    if source_page_id is not None:
        session.execute(
            text(
                """
                INSERT INTO event_sources (
                    event_id, source_id, source_page_id, source_url,
                    raw_title, raw_date_text, is_primary
                )
                VALUES (:event_id, :source_id, :source_page_id, :source_url,
                        :raw_title, :raw_date_text, :is_primary)
                ON CONFLICT (event_id, source_page_id) WHERE source_page_id IS NOT NULL
                DO UPDATE SET
                    source_url    = EXCLUDED.source_url,
                    raw_title     = EXCLUDED.raw_title,
                    raw_date_text = EXCLUDED.raw_date_text,
                    is_primary    = EXCLUDED.is_primary,
                    last_seen_at  = now()
                """
            ),
            {
                "event_id": str(event_id),
                "source_id": str(source_id),
                "source_page_id": str(source_page_id),
                "source_url": source_url,
                "raw_title": raw_title,
                "raw_date_text": raw_date_text,
                "is_primary": is_primary,
            },
        )
    else:
        session.execute(
            text(
                """
                INSERT INTO event_sources (
                    event_id, source_id, source_page_id, source_url,
                    raw_title, raw_date_text, is_primary
                )
                VALUES (:event_id, :source_id, NULL, :source_url,
                        :raw_title, :raw_date_text, :is_primary)
                ON CONFLICT (event_id, source_url) WHERE source_page_id IS NULL
                DO UPDATE SET
                    raw_title     = EXCLUDED.raw_title,
                    raw_date_text = EXCLUDED.raw_date_text,
                    is_primary    = EXCLUDED.is_primary,
                    last_seen_at  = now()
                """
            ),
            {
                "event_id": str(event_id),
                "source_id": str(source_id),
                "source_url": source_url,
                "raw_title": raw_title,
                "raw_date_text": raw_date_text,
                "is_primary": is_primary,
            },
        )
