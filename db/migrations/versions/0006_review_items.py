"""create review_items table

Revision ID: 0006_review_items
Revises: 0005_event_sources
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0006_review_items"
down_revision: str | None = "0005_event_sources"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE review_items (
            id              uuid          PRIMARY KEY DEFAULT gen_random_uuid(),
            kind            text          NOT NULL CHECK (kind IN
                                              ('duplicate_candidate','parser_failure','suspicious_data','source_blocked')),
            source_id       uuid          NULL REFERENCES sources(id),
            source_page_id  uuid          NULL REFERENCES source_pages(id),
            event_id        uuid          NULL REFERENCES events(id),
            status          text          NOT NULL DEFAULT 'open' CHECK (status IN ('open','resolved','ignored')),
            details_json    jsonb         NOT NULL DEFAULT '{}'::jsonb,
            created_at      timestamptz   NOT NULL DEFAULT now(),
            resolved_at     timestamptz   NULL,
            resolved_by     text          NULL,
            resolution_note text          NULL
        );
        """
    )


def downgrade() -> None:
    raise NotImplementedError("Forward-only migrations.")
