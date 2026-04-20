"""create sources table

Revision ID: 0002_sources
Revises: 0001_extensions
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0002_sources"
down_revision: str | None = "0001_extensions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE sources (
            id                 uuid          PRIMARY KEY DEFAULT gen_random_uuid(),
            name               text          NOT NULL,
            code               citext        UNIQUE NOT NULL,
            homepage_url       text          NOT NULL,
            source_type        text          NOT NULL CHECK (source_type IN
                                              ('society','sponsor','aggregator','venue','government','other')),
            country_iso        char(2)       NULL,
            is_active          boolean       NOT NULL DEFAULT true,
            parser_name        text          NULL,
            crawl_frequency    text          NOT NULL CHECK (crawl_frequency IN
                                              ('daily','weekly','biweekly','monthly')),
            crawl_config       jsonb         NOT NULL DEFAULT '{}'::jsonb,
            last_crawled_at    timestamptz   NULL,
            last_success_at    timestamptz   NULL,
            last_error_at      timestamptz   NULL,
            last_error_message text          NULL,
            notes              text          NULL,
            created_at         timestamptz   NOT NULL DEFAULT now(),
            updated_at         timestamptz   NOT NULL DEFAULT now()
        );
        """
    )


def downgrade() -> None:
    raise NotImplementedError("Forward-only migrations.")
