"""seed importer tests."""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from medevents_ingest import db as _db
from medevents_ingest.cli import app
from medevents_ingest.db import session_scope
from medevents_ingest.seed import load_source_seeds
from sqlalchemy import text
from typer.testing import CliRunner

# DB-gated: TRUNCATE on every test. Never point TEST_DATABASE_URL at the dev DB.
# Historically this suite used DATABASE_URL directly, which leaked a `testseed`
# row into the dev DB whenever `test_seed_sources_command_upserts` ran locally
# (surfaced by the W3.2f `run --all --force --dry-run` batch as a stale
# UnknownParserError source). Aliased to TEST_DATABASE_URL now so the upsert +
# TRUNCATE only touch the disposable test DB.
pytestmark = pytest.mark.skipif(
    "TEST_DATABASE_URL" not in os.environ,
    reason="TEST_DATABASE_URL not set; skipping integration tests",
)


@pytest.fixture(autouse=True)
def _alias_test_database_url(
    _no_env_pollution: None,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[None]:
    """Re-point DATABASE_URL at TEST_DATABASE_URL after conftest strips it.

    Mirrors the load-bearing pattern in `test_aap_pipeline.py` verbatim:
    the `_no_env_pollution` parameter is a deliberate fixture ordering
    dependency so the conftest scrubber runs BEFORE this alias, not after.
    Engine-cache reset at both setup and teardown prevents a prior test's
    dev-DB-bound engine from surviving into this suite or leaking out.
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
def _clean_db() -> None:
    with session_scope() as s:
        s.execute(
            text(
                "TRUNCATE audit_log, event_sources, review_items, events, source_pages, sources RESTART IDENTITY CASCADE"
            )
        )


def test_load_source_seeds_parses_real_yaml(tmp_path: Path) -> None:
    yaml_text = """
- code: ada
  name: American Dental Association
  homepage_url: https://www.ada.org/
  source_type: society
  country_iso: US
  parser_name: ada_listing
  crawl_frequency: weekly
  crawl_config:
    listing_url: https://www.ada.org/meetings-events
"""
    path = tmp_path / "sources.yaml"
    path.write_text(yaml_text)
    seeds = load_source_seeds(path)
    assert len(seeds) == 1
    assert seeds[0].code == "ada"
    assert seeds[0].crawl_config["listing_url"].startswith("https://")


def test_seed_sources_command_upserts(tmp_path: Path) -> None:
    yaml_text = """
- code: testseed
  name: Test Seed Source
  homepage_url: https://example.com/
  source_type: other
  parser_name: testseed_parser
  crawl_frequency: monthly
"""
    path = tmp_path / "sources.yaml"
    path.write_text(yaml_text)

    runner = CliRunner()
    result = runner.invoke(app, ["seed-sources", "--path", str(path)])
    assert result.exit_code == 0, result.stdout
    assert "upserted 1 source" in result.stdout

    # verify in DB
    with session_scope() as s:
        row = (
            s.execute(text("SELECT code, name FROM sources WHERE code = 'testseed'"))
            .mappings()
            .one()
        )
        assert row["name"] == "Test Seed Source"
