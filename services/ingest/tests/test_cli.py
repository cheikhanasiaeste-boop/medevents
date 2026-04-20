"""CLI smoke tests."""

import os

import pytest
from medevents_ingest import __version__
from medevents_ingest.cli import app
from medevents_ingest.db import session_scope
from medevents_ingest.parsers import _reset_registry_for_tests, register_parser
from medevents_ingest.parsers.base import (
    DiscoveredPage,
    FetchedContent,
    ParsedEvent,
    SourcePageRef,
)
from sqlalchemy import text
from typer.testing import CliRunner


def test_version_prints_package_version() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout


_INTEGRATION = pytest.mark.skipif(
    "DATABASE_URL" not in os.environ,
    reason="DATABASE_URL not set; skipping integration tests",
)


@pytest.fixture
def _registered_parser() -> None:
    _reset_registry_for_tests()

    @register_parser("ada_listing")
    class _AdaListing:
        def __init__(self) -> None:
            self.name = "ada_listing"

        def discover(self, source: object):
            yield DiscoveredPage(url="https://x", page_kind="detail")

        def fetch(self, page: SourcePageRef) -> FetchedContent:  # pragma: no cover
            raise NotImplementedError

        def parse(self, content: FetchedContent) -> ParsedEvent | None:  # pragma: no cover
            return None


@pytest.fixture
def _seeded_ada(_registered_parser: None) -> None:
    with session_scope() as s:
        s.execute(text("TRUNCATE sources RESTART IDENTITY CASCADE"))
        s.execute(
            text(
                """
                INSERT INTO sources (code, name, homepage_url, source_type, parser_name, crawl_frequency)
                VALUES ('ada', 'ADA', 'https://www.ada.org/', 'society', 'ada_listing', 'weekly')
                """
            )
        )


@_INTEGRATION
def test_run_resolves_source_and_parser_then_exits(_seeded_ada: None) -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["run", "--source", "ada"])
    assert result.exit_code == 0, result.stdout
    assert "resolved source='ada' parser='ada_listing'" in result.stdout
    assert "W1: parser body not yet implemented" in result.stdout


@_INTEGRATION
def test_run_unknown_source_exits_2() -> None:
    with session_scope() as s:
        s.execute(text("TRUNCATE sources RESTART IDENTITY CASCADE"))
    runner = CliRunner()
    result = runner.invoke(app, ["run", "--source", "nope"])
    assert result.exit_code == 2
    assert "not found in DB" in result.output


@_INTEGRATION
def test_run_unregistered_parser_exits_3(_seeded_ada: None) -> None:
    _reset_registry_for_tests()  # remove ada_listing
    runner = CliRunner()
    result = runner.invoke(app, ["run", "--source", "ada"])
    assert result.exit_code == 3
    assert "No parser registered" in result.output
