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
