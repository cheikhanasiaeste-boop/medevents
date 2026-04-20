"""create audit_log table

Revision ID: 0007_audit_log
Revises: 0006_review_items
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0007_audit_log"
down_revision: str | None = "0006_review_items"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE audit_log (
            id           uuid          PRIMARY KEY DEFAULT gen_random_uuid(),
            actor        text          NOT NULL,
            action       text          NOT NULL,
            target_kind  text          NULL,
            target_id    uuid          NULL,
            details_json jsonb         NOT NULL DEFAULT '{}'::jsonb,
            occurred_at  timestamptz   NOT NULL DEFAULT now()
        );
        """
    )


def downgrade() -> None:
    raise NotImplementedError("Forward-only migrations.")
