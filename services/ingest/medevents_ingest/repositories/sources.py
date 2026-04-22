"""sources table access."""

from __future__ import annotations

import json
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from ..models import Source, SourceSeed


def upsert_source_seed(session: Session, seed: SourceSeed) -> Source:
    """Insert or update a source row keyed by `code`. Returns the resulting Source."""
    row = (
        session.execute(
            text(
                """
                INSERT INTO sources (
                    code, name, homepage_url, source_type, country_iso,
                    is_active, parser_name, crawl_frequency, crawl_config, notes,
                    updated_at
                ) VALUES (
                    :code, :name, :homepage_url, :source_type, :country_iso,
                    :is_active, :parser_name, :crawl_frequency, CAST(:crawl_config AS jsonb), :notes,
                    now()
                )
                ON CONFLICT (code) DO UPDATE SET
                    name              = EXCLUDED.name,
                    homepage_url      = EXCLUDED.homepage_url,
                    source_type       = EXCLUDED.source_type,
                    country_iso       = EXCLUDED.country_iso,
                    is_active         = EXCLUDED.is_active,
                    parser_name       = EXCLUDED.parser_name,
                    crawl_frequency   = EXCLUDED.crawl_frequency,
                    crawl_config      = EXCLUDED.crawl_config,
                    notes             = EXCLUDED.notes,
                    updated_at        = now()
                RETURNING id, code, name, homepage_url, source_type, country_iso,
                          is_active, parser_name, crawl_frequency, crawl_config,
                          last_crawled_at, last_success_at, last_error_at, last_error_message,
                          notes, created_at, updated_at;
                """
            ),
            {
                "code": seed.code,
                "name": seed.name,
                "homepage_url": seed.homepage_url,
                "source_type": seed.source_type,
                "country_iso": seed.country_iso,
                "is_active": seed.is_active,
                "parser_name": seed.parser_name,
                "crawl_frequency": seed.crawl_frequency,
                "crawl_config": json.dumps(seed.crawl_config),
                "notes": seed.notes,
            },
        )
        .mappings()
        .one()
    )
    return Source.model_validate(dict(row))


def update_source_run_status(
    session: Session,
    *,
    source_id: UUID,
    status: str,
    error_message: str | None = None,
) -> None:
    """Write W1 §305 bookkeeping fields on `sources` for one completed run.

    Always writes `last_crawled_at = clock_timestamp()` — see spec §4 D1 for
    semantic. Depending on `status`:

    - "success": also sets `last_success_at = clock_timestamp()`.
                 Does NOT touch `last_error_at` or `last_error_message`
                 (see spec §4 D4 — preserve error history).
    - "error":   also sets `last_error_at = clock_timestamp()` and
                 `last_error_message = :error_message`. Does NOT touch
                 `last_success_at`.

    `clock_timestamp()` over `now()` per the W2 convention — statement-time,
    not transaction-time, so long-running pipelines don't silently backdate.
    """
    if status == "success":
        session.execute(
            text(
                "UPDATE sources "
                "SET last_crawled_at = clock_timestamp(), "
                "    last_success_at = clock_timestamp() "
                "WHERE id = :sid"
            ),
            {"sid": str(source_id)},
        )
    elif status == "error":
        if error_message is None:
            raise ValueError("update_source_run_status(status='error') requires error_message")
        session.execute(
            text(
                "UPDATE sources "
                "SET last_crawled_at = clock_timestamp(), "
                "    last_error_at = clock_timestamp(), "
                "    last_error_message = :msg "
                "WHERE id = :sid"
            ),
            {"sid": str(source_id), "msg": error_message},
        )
    else:
        raise ValueError(f"unknown status {status!r}; expected 'success' or 'error'")


def get_source_by_code(session: Session, code: str) -> Source | None:
    row = (
        session.execute(text("SELECT * FROM sources WHERE code = :code"), {"code": code})
        .mappings()
        .one_or_none()
    )
    return Source.model_validate(dict(row)) if row else None
