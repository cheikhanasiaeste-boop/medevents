"""seed importer tests."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from medevents_ingest.cli import app
from medevents_ingest.db import session_scope
from medevents_ingest.seed import load_source_seeds
from sqlalchemy import text
from typer.testing import CliRunner

pytestmark = pytest.mark.skipif(
    "DATABASE_URL" not in os.environ,
    reason="DATABASE_URL not set; skipping integration tests",
)


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
