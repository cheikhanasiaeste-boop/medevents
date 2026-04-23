"""End-to-end pipeline tests for AAP Annual Meeting driven by fixture HTML.

Mirrors the test_gnydm_pipeline.py pattern: stubs fetch, truncates tables
before every test. Uses the _alias_test_database_url fixture pattern verbatim.

Two DB-gated tests covering spec §5.2:
  7. test_first_run_creates_one_event_two_event_sources
  8. test_second_run_with_cfemail_rotation_still_skips
"""

from __future__ import annotations

import hashlib
import os
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from medevents_ingest import db as _db
from medevents_ingest.db import session_scope
from medevents_ingest.models import SourceSeed
from medevents_ingest.parsers import parser_for, registered_parser_names
from medevents_ingest.parsers.aap import _normalize_body_for_hashing
from medevents_ingest.parsers.base import FetchedContent, SourcePageRef
from medevents_ingest.pipeline import PipelineResult, run_source
from medevents_ingest.repositories.sources import upsert_source_seed
from sqlalchemy import text
from sqlalchemy.orm import Session

# DB-gated: TRUNCATE on every test.  Never point TEST_DATABASE_URL at the dev DB.
pytestmark = pytest.mark.skipif(
    "TEST_DATABASE_URL" not in os.environ,
    reason="TEST_DATABASE_URL not set; skipping integration tests",
)

FIXTURES = Path(__file__).parent / "fixtures" / "aap"
HOMEPAGE_URL = "https://am2026.perio.org/"
GENERAL_INFO_URL = "https://am2026.perio.org/general-information/"


@pytest.fixture(autouse=True)
def _alias_test_database_url(
    _no_env_pollution: None,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[None]:
    """Re-point DATABASE_URL at TEST_DATABASE_URL after conftest strips it.

    The `_no_env_pollution` parameter is a DELIBERATE FIXTURE DEPENDENCY
    on conftest.py's scrubber — NOT unused. pytest does NOT guarantee any
    ordering between two independent same-scope autouse fixtures, so the
    conftest scrubber could otherwise run AFTER this alias and delete
    DATABASE_URL at test time. When that happens `config.Settings` falls
    back to its default DSN (`postgresql://medevents:...@.../medevents`
    — the DEV DB), and the `_clean_db` TRUNCATE would wipe the dev
    database. Making `_no_env_pollution` a parameter forces pytest to
    resolve it first, so the alias below is the last write to
    DATABASE_URL before the test runs.

    Engine-cache discipline: reset `medevents_ingest.db._engine` /
    `_SessionLocal` at BOTH setup AND teardown.
    * Setup reset — a prior test may have populated the global cache
      against a different DSN; we need a fresh engine bound to the
      test DB.
    * Teardown reset — this test just populated the cache against the
      test DB; if we leave it, a subsequent pipeline test (which also
      caches globally and reads DATABASE_URL = dev DB) would inherit a
      stale test-DB-bound engine and silently operate on the wrong database.
    Explicit assignment (not `monkeypatch.setattr`) because we want to
    set to None at teardown unconditionally, not restore whatever stale
    value was there at setup time.
    """
    monkeypatch.setenv("DATABASE_URL", os.environ["TEST_DATABASE_URL"])
    _db._engine = None
    _db._SessionLocal = None
    try:
        yield
    finally:
        _db._engine = None
        _db._SessionLocal = None


@pytest.fixture(autouse=True)
def _ensure_aap_registered() -> None:
    if "aap_annual_meeting" not in registered_parser_names():
        import importlib

        import medevents_ingest.parsers.aap as _aap_mod

        importlib.reload(_aap_mod)


@pytest.fixture(autouse=True)
def _clean_db() -> None:
    with session_scope() as s:
        s.execute(
            text(
                "TRUNCATE audit_log, event_sources, review_items, events, "
                "source_pages, sources RESTART IDENTITY CASCADE"
            )
        )


def _seed_aap(session: Session) -> None:
    upsert_source_seed(
        session,
        SourceSeed(
            code="aap_annual_meeting",
            name="American Academy of Periodontology Annual Meeting",
            homepage_url=HOMEPAGE_URL,
            source_type="society",
            country_iso="US",
            parser_name="aap_annual_meeting",
            crawl_frequency="monthly",
            crawl_config={"seed_urls": [HOMEPAGE_URL, GENERAL_INFO_URL]},
        ),
    )


def _fixture_fetch(page: SourcePageRef) -> FetchedContent:
    """Fetch stub: return fixture HTML with a normalized content_hash."""
    name = {
        HOMEPAGE_URL: "homepage.html",
        GENERAL_INFO_URL: "general-information.html",
    }[page.url]
    body = (FIXTURES / name).read_bytes()
    stable_hash = hashlib.sha256(_normalize_body_for_hashing(body)).hexdigest()
    return FetchedContent(
        url=page.url,
        status_code=200,
        content_type="text/html; charset=utf-8",
        body=body,
        fetched_at=datetime.now(UTC),
        content_hash=stable_hash,
    )


# ---------------------------------------------------------------------------
# Test 7: First run creates one event and two event_sources rows
# ---------------------------------------------------------------------------


def test_first_run_creates_one_event_two_event_sources(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Spec §5.2 test 7.

    First run:
      - 2 pages fetched (homepage + general-information)
      - homepage creates the event row (events_created=1)
      - general-information enriches it with the venue (events_updated=1)
      - 0 review_items

    Post-run DB state:
      - exactly 1 events row titled "AAP 2026 Annual Meeting"
      - exactly 2 event_sources rows linked to that event
      - venue_name = "Seattle Convention Center, Arch Building"
    """
    parser = parser_for("aap_annual_meeting")
    monkeypatch.setattr(parser, "fetch", _fixture_fetch, raising=False)

    with session_scope() as s:
        _seed_aap(s)
    with session_scope() as s:
        result: PipelineResult = run_source(s, source_code="aap_annual_meeting")

    assert result.pages_fetched == 2
    assert result.pages_skipped_unchanged == 0
    assert result.events_created == 1
    assert result.events_updated == 1
    assert result.review_items_created == 0

    with session_scope() as s:
        rows = (
            s.execute(
                text("SELECT id, title, starts_on, venue_name FROM events WHERE title = :t"),
                {"t": "AAP 2026 Annual Meeting"},
            )
            .mappings()
            .all()
        )
        assert len(rows) == 1, f"expected exactly 1 event row, got {len(rows)}"
        event_id = rows[0]["id"]
        assert rows[0]["venue_name"] == "Seattle Convention Center, Arch Building", (
            "venue_name must be populated from the general-information page"
        )

        src_count = s.execute(
            text("SELECT count(*) FROM event_sources WHERE event_id = :eid"),
            {"eid": str(event_id)},
        ).scalar_one()
        assert src_count == 2, f"expected 2 event_sources rows, got {src_count}"


# ---------------------------------------------------------------------------
# Test 8: Second run with cfemail rotation still skips (normalization invariant)
# ---------------------------------------------------------------------------


def test_second_run_with_cfemail_rotation_still_skips(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Spec §5.2 test 8.

    After the first run, simulate Cloudflare email-protection rotation: patch
    fetch() to return bodies that differ ONLY in data-cfemail hex values versus
    the original fixtures. The second run must see pages_skipped_unchanged == 2
    because _normalize_body_for_hashing strips the rotating attribute before
    sha-256, so the hash is identical to what was stored in the first run.

    This is the invariant that _normalize_body_for_hashing MUST protect —
    without it, this test fails (skipped_unchanged == 0, re-parse fires).
    """
    parser = parser_for("aap_annual_meeting")
    monkeypatch.setattr(parser, "fetch", _fixture_fetch, raising=False)

    # First run — establishes baseline content hashes in source_pages
    with session_scope() as s:
        _seed_aap(s)
    with session_scope() as s:
        run_source(s, source_code="aap_annual_meeting")

    # Build "rotated" fetch stub: inject a different cfemail hex into the body
    # but produce the same normalized hash.
    def _rotated_fetch(page: SourcePageRef) -> FetchedContent:
        name = {
            HOMEPAGE_URL: "homepage.html",
            GENERAL_INFO_URL: "general-information.html",
        }[page.url]
        body = (FIXTURES / name).read_bytes()
        # Simulate rotation: append a real data-cfemail attribute (not inside a
        # comment) that is stripped by _normalize_body_for_hashing before
        # sha-256.  The regex matches `\s*data-cfemail="<hex>"` so inject it as
        # a bare attribute string in the body — the regex strips it regardless of
        # surrounding context.
        rotated_body = body + b' data-cfemail="deadbeef1234abcd"'  # pragma: allowlist secret
        stable_hash = hashlib.sha256(_normalize_body_for_hashing(rotated_body)).hexdigest()
        return FetchedContent(
            url=page.url,
            status_code=200,
            content_type="text/html; charset=utf-8",
            body=rotated_body,
            fetched_at=datetime.now(UTC),
            content_hash=stable_hash,
        )

    monkeypatch.setattr(parser, "fetch", _rotated_fetch, raising=False)

    with session_scope() as s:
        second: PipelineResult = run_source(s, source_code="aap_annual_meeting")

    assert second.pages_fetched == 2
    assert second.pages_skipped_unchanged == 2, (
        f"expected 2 skipped_unchanged but got {second.pages_skipped_unchanged}; "
        "_normalize_body_for_hashing must strip cfemail rotation before hashing"
    )
    assert second.events_created == 0
    assert second.events_updated == 0
