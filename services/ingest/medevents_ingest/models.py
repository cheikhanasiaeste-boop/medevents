"""Pydantic DTOs that travel between layers in the ingest service.

These are NOT the database tables (those are reflected via SQLAlchemy Core).
They are the typed shape the CLI / parsers / repositories pass around.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

SourceType = Literal["society", "sponsor", "aggregator", "venue", "government", "other"]
CrawlFrequency = Literal["daily", "weekly", "biweekly", "monthly"]


class SourceSeed(BaseModel):
    """A row in config/sources.yaml."""

    model_config = ConfigDict(extra="forbid")

    code: str
    name: str
    homepage_url: str
    source_type: SourceType
    country_iso: str | None = None
    is_active: bool = True
    parser_name: str | None = None
    crawl_frequency: CrawlFrequency
    crawl_config: dict[str, Any] = Field(default_factory=dict)
    notes: str | None = None


class Source(BaseModel):
    """A row from the `sources` table."""

    model_config = ConfigDict(extra="ignore")

    id: UUID
    code: str
    name: str
    homepage_url: str
    source_type: SourceType
    country_iso: str | None
    is_active: bool
    parser_name: str | None
    crawl_frequency: CrawlFrequency
    crawl_config: dict[str, Any]
    last_crawled_at: datetime | None
    last_success_at: datetime | None
    last_error_at: datetime | None
    last_error_message: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


class AuditLogEntry(BaseModel):
    """One row destined for the audit_log table."""

    model_config = ConfigDict(extra="forbid")

    actor: str
    action: str
    target_kind: str | None = None
    target_id: UUID | None = None
    details_json: dict[str, Any] = Field(default_factory=dict)
