"""source_pages table access."""

from __future__ import annotations

from datetime import datetime
from typing import cast
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session


def upsert_source_page(
    session: Session, *, source_id: UUID, url: str, page_kind: str, parser_name: str | None = None
) -> UUID:
    """Insert a source_page row or return the existing id for (source_id, url).

    Does NOT touch content_hash or timestamps — record_fetch() owns those.
    """
    row = (
        session.execute(
            text(
                """
                INSERT INTO source_pages (source_id, url, page_kind, parser_name)
                VALUES (:source_id, :url, :page_kind, :parser_name)
                ON CONFLICT (source_id, url) DO UPDATE SET
                    page_kind   = EXCLUDED.page_kind,
                    parser_name = EXCLUDED.parser_name
                RETURNING id
                """
            ),
            {
                "source_id": str(source_id),
                "url": url,
                "page_kind": page_kind,
                "parser_name": parser_name,
            },
        )
        .mappings()
        .one()
    )
    return cast(UUID, row["id"])


def record_fetch(
    session: Session,
    *,
    source_page_id: UUID,
    content_hash: str | None,
    fetched_at: datetime,
    fetch_status: str,
) -> None:
    """Write the outcome of one fetch attempt onto the source_pages row."""
    session.execute(
        text(
            """
            UPDATE source_pages
               SET content_hash    = :content_hash,
                   last_fetched_at = :fetched_at,
                   last_seen_at    = :fetched_at,
                   fetch_status    = :fetch_status
             WHERE id = :id
            """
        ),
        {
            "id": str(source_page_id),
            "content_hash": content_hash,
            "fetched_at": fetched_at,
            "fetch_status": fetch_status,
        },
    )


def get_last_content_hash(session: Session, source_page_id: UUID) -> str | None:
    row = (
        session.execute(
            text("SELECT content_hash FROM source_pages WHERE id = :id"),
            {"id": str(source_page_id)},
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        return None
    hash_ = row["content_hash"]
    return hash_ if hash_ is not None else None


def get_last_content_hash_by_url(
    session: Session,
    *,
    source_id: UUID,
    url: str,
) -> str | None:
    """Read the most recent fetch's content_hash for (source_id, url).

    Used by the dry-run content-hash gate (spec §4 D5): unlike
    `get_last_content_hash`, which looks up by `source_pages.id`, this
    variant does NOT require a source_pages row to have been upserted by
    the current run, so dry-run can stay read-only at every DB boundary.

    Returns None when no source_page exists for (source_id, url), or when
    the row exists but no fetch has recorded a hash yet.

    Note: the live schema stores `content_hash` directly on `source_pages`
    (one row per (source_id, url), updated in place by `record_fetch`), so
    the "most recent" hash is just the column value — no separate fetch
    history table to join through.
    """
    row = (
        session.execute(
            text(
                "SELECT content_hash FROM source_pages WHERE source_id = :source_id AND url = :url"
            ),
            {"source_id": str(source_id), "url": url},
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        return None
    hash_ = row["content_hash"]
    return hash_ if hash_ is not None else None
