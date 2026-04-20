"""create event_sources table with partial unique indexes

Revision ID: 0005_event_sources
Revises: 0004_events
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0005_event_sources"
down_revision: str | None = "0004_events"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE event_sources (
            id              uuid          PRIMARY KEY DEFAULT gen_random_uuid(),
            event_id        uuid          NOT NULL REFERENCES events(id) ON DELETE CASCADE,
            source_id       uuid          NOT NULL REFERENCES sources(id),
            source_page_id  uuid          NULL REFERENCES source_pages(id),
            source_url      text          NOT NULL,
            first_seen_at   timestamptz   NOT NULL DEFAULT now(),
            last_seen_at    timestamptz   NOT NULL DEFAULT now(),
            is_primary      boolean       NOT NULL DEFAULT false,
            raw_title       text          NULL,
            raw_date_text   text          NULL,
            created_at      timestamptz   NOT NULL DEFAULT now()
        );
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX event_sources_event_page_uniq
            ON event_sources(event_id, source_page_id)
            WHERE source_page_id IS NOT NULL;
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX event_sources_event_url_uniq
            ON event_sources(event_id, source_url)
            WHERE source_page_id IS NULL;
        """
    )


def downgrade() -> None:
    raise NotImplementedError("Forward-only migrations.")
