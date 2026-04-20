"""audit_log table access."""

from __future__ import annotations

import json
from typing import cast
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from ..models import AuditLogEntry


def write_audit_entry(session: Session, entry: AuditLogEntry) -> UUID:
    """Insert one audit_log row. Returns the row id."""
    row = (
        session.execute(
            text(
                """
                INSERT INTO audit_log (actor, action, target_kind, target_id, details_json)
                VALUES (:actor, :action, :target_kind, :target_id, CAST(:details_json AS jsonb))
                RETURNING id
                """
            ),
            {
                "actor": entry.actor,
                "action": entry.action,
                "target_kind": entry.target_kind,
                "target_id": str(entry.target_id) if entry.target_id else None,
                "details_json": json.dumps(entry.details_json),
            },
        )
        .mappings()
        .one()
    )
    return cast(UUID, row["id"])
