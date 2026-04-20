"""create source_pages table

Revision ID: 0003_source_pages
Revises: 0002_sources
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0003_source_pages"
down_revision: str | None = "0002_sources"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE source_pages (
            id              uuid          PRIMARY KEY DEFAULT gen_random_uuid(),
            source_id       uuid          NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
            url             text          NOT NULL,
            page_kind       text          NOT NULL CHECK (page_kind IN
                                              ('listing','detail','pdf','unknown')),
            content_hash    text          NULL,
            last_seen_at    timestamptz   NULL,
            last_fetched_at timestamptz   NULL,
            fetch_status    text          NULL,
            parser_name     text          NULL,
            created_at      timestamptz   NOT NULL DEFAULT now(),
            UNIQUE (source_id, url)
        );
        """
    )


def downgrade() -> None:
    raise NotImplementedError("Forward-only migrations.")
