"""create MVP indexes

Revision ID: 0008_indexes
Revises: 0007_audit_log
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0008_indexes"
down_revision: str | None = "0007_audit_log"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # events
    op.execute("CREATE INDEX events_published_starts_on ON events(is_published, starts_on);")
    op.execute("CREATE INDEX events_country_starts_on   ON events(country_iso, starts_on);")
    op.execute("CREATE INDEX events_lifecycle           ON events(lifecycle_status);")
    op.execute("CREATE INDEX events_specialty_codes_gin ON events USING GIN(specialty_codes);")
    op.execute("CREATE INDEX events_title_trgm          ON events USING GIN(title gin_trgm_ops);")

    # source_pages
    op.execute("CREATE INDEX source_pages_source_kind  ON source_pages(source_id, page_kind);")
    op.execute("CREATE INDEX source_pages_content_hash ON source_pages(content_hash);")

    # event_sources
    op.execute("CREATE INDEX event_sources_event  ON event_sources(event_id);")
    op.execute("CREATE INDEX event_sources_source ON event_sources(source_id);")
    op.execute("CREATE INDEX event_sources_page   ON event_sources(source_page_id);")

    # review_items
    op.execute("CREATE INDEX review_items_status_kind ON review_items(status, kind, created_at);")

    # sources
    op.execute("CREATE INDEX sources_active_crawled ON sources(is_active, last_crawled_at);")

    # audit_log
    op.execute(
        "CREATE INDEX audit_log_target     ON audit_log(target_kind, target_id, occurred_at);"
    )
    op.execute("CREATE INDEX audit_log_actor_time ON audit_log(actor, occurred_at);")


def downgrade() -> None:
    raise NotImplementedError("Forward-only migrations.")
