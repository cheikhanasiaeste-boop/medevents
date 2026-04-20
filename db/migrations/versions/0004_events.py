"""create events table

Revision ID: 0004_events
Revises: 0003_source_pages
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0004_events"
down_revision: str | None = "0003_source_pages"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE events (
            id                uuid          PRIMARY KEY DEFAULT gen_random_uuid(),
            slug              text          UNIQUE NOT NULL,
            title             text          NOT NULL,
            summary           text          NULL,
            starts_on         date          NOT NULL,
            ends_on           date          NULL,
            timezone          text          NULL,
            city              text          NULL,
            country_iso       char(2)       NULL,
            venue_name        text          NULL,
            format            text          NOT NULL DEFAULT 'unknown' CHECK (format IN
                                              ('in_person','virtual','hybrid','unknown')),
            event_kind        text          NOT NULL DEFAULT 'other' CHECK (event_kind IN
                                              ('fair','seminar','congress','workshop','webinar','conference','training','other')),
            lifecycle_status  text          NOT NULL DEFAULT 'active' CHECK (lifecycle_status IN
                                              ('active','postponed','cancelled','completed','tentative')),
            specialty_codes   text[]        NOT NULL DEFAULT '{}',
            organizer_name    text          NULL,
            source_url        text          NOT NULL,
            registration_url  text          NULL,
            source_count      int           NOT NULL DEFAULT 1,
            last_checked_at   timestamptz   NOT NULL DEFAULT now(),
            last_changed_at   timestamptz   NOT NULL DEFAULT now(),
            is_published      boolean       NOT NULL DEFAULT true,
            created_at        timestamptz   NOT NULL DEFAULT now(),
            updated_at        timestamptz   NOT NULL DEFAULT now()
        );
        """
    )


def downgrade() -> None:
    raise NotImplementedError("Forward-only migrations.")
