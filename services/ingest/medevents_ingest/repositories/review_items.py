"""review_items table access."""

from __future__ import annotations

import json
from typing import Any, cast
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session


def insert_review_item(
    session: Session,
    *,
    kind: str,
    source_id: UUID | None,
    source_page_id: UUID | None,
    event_id: UUID | None,
    details: dict[str, Any],
) -> UUID:
    """Insert one review_items row. Caller is responsible for passing a valid `kind`.

    `kind` must be one of: duplicate_candidate | parser_failure | suspicious_data | source_blocked.
    The DB check constraint raises IntegrityError for anything else.
    """
    row = (
        session.execute(
            text(
                """
                INSERT INTO review_items (
                    kind, source_id, source_page_id, event_id, details_json
                )
                VALUES (:kind, :source_id, :source_page_id, :event_id, CAST(:details AS jsonb))
                RETURNING id
                """
            ),
            {
                "kind": kind,
                "source_id": str(source_id) if source_id else None,
                "source_page_id": str(source_page_id) if source_page_id else None,
                "event_id": str(event_id) if event_id else None,
                "details": json.dumps(details),
            },
        )
        .mappings()
        .one()
    )
    return cast(UUID, row["id"])
