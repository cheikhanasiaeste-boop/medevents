"""CLI tests for `--dry-run` wiring (W3.2f Task 2).

These tests exercise the Typer command layer end-to-end via
`typer.testing.CliRunner`. Database access is avoided by patching
`medevents_ingest.cli.session_scope` with a `@contextmanager` that yields a
MagicMock session, and by patching the pipeline entrypoints + repositories
the command calls through the `cli` module import site.

Patches are applied at `medevents_ingest.cli.<name>` rather than
`medevents_ingest.pipeline.<name>` because Task 2 hoisted
`from .pipeline import run_all, run_source` to module scope in cli.py — so
`medevents_ingest.cli` owns its own bindings and those are the names the
command resolves against. This matches the pattern used by
`test_dry_run_unit.py` (`monkeypatch.setattr(pipeline, "<name>", stub)`).
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any
from unittest.mock import MagicMock

import pytest
from medevents_ingest.cli import app
from medevents_ingest.pipeline import BatchResult, PipelineResult
from typer.testing import CliRunner

# Click 8.3+ removed the `mix_stderr` CliRunner kwarg; streams are split by
# default. `result.stderr` is available on modern Click. If stderr splitting
# ever regresses we fall back to asserting against combined `result.output`.
runner = CliRunner()


@pytest.fixture
def fake_session_scope(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Replace `cli.session_scope` with a context manager yielding a MagicMock.

    Returns the session MagicMock so tests can assert `.rollback()` was called
    under --dry-run (belt-and-braces behavior).
    """
    session = MagicMock(name="Session")

    @contextmanager
    def _scope() -> Iterator[MagicMock]:
        yield session

    monkeypatch.setattr("medevents_ingest.cli.session_scope", _scope)
    return session


def _make_pipeline_result(source_code: str = "ada") -> PipelineResult:
    return PipelineResult(
        source_code=source_code,
        pages_fetched=3,
        pages_skipped_unchanged=1,
        events_created=2,
        events_updated=0,
        review_items_created=0,
    )


# ---------------------------------------------------------------------------
# Test 15: run --source --dry-run -> exit 0, summary prefixed with dry_run=1
# ---------------------------------------------------------------------------


def test_cli_run_source_dry_run_exits_zero(
    monkeypatch: pytest.MonkeyPatch,
    fake_session_scope: MagicMock,
) -> None:
    # Source lookup returns a Source-like MagicMock with a parser_name attr.
    fake_source = MagicMock(name="Source")
    fake_source.parser_name = "ada"
    monkeypatch.setattr(
        "medevents_ingest.cli.get_source_by_code",
        lambda _s, _c: fake_source,
    )
    # parser_for must not raise.
    monkeypatch.setattr(
        "medevents_ingest.cli.parser_for",
        lambda _n: MagicMock(name="Parser"),
    )

    captured: dict[str, Any] = {}

    def _fake_run_source(
        _session: Any,
        *,
        source_code: str,
        force: bool = False,
        dry_run: bool = False,
    ) -> PipelineResult:
        captured["dry_run"] = dry_run
        captured["source_code"] = source_code
        return _make_pipeline_result(source_code=source_code)

    monkeypatch.setattr("medevents_ingest.cli.run_source", _fake_run_source)

    result = runner.invoke(app, ["run", "--source", "ada", "--dry-run"])

    assert result.exit_code == 0, result.output
    assert captured.get("dry_run") is True
    assert "dry_run=1 " in result.stdout
    assert "source=ada" in result.stdout
    # Belt-and-braces rollback must have fired.
    fake_session_scope.rollback.assert_called()


# ---------------------------------------------------------------------------
# Test 16: unknown source + --dry-run -> exit 2 (dry-run does NOT suppress)
# ---------------------------------------------------------------------------


def test_cli_run_source_dry_run_unknown_source_exits_two(
    monkeypatch: pytest.MonkeyPatch,
    fake_session_scope: MagicMock,
) -> None:
    monkeypatch.setattr(
        "medevents_ingest.cli.get_source_by_code",
        lambda _s, _c: None,
    )

    result = runner.invoke(app, ["run", "--source", "nope", "--dry-run"])

    assert result.exit_code == 2
    # CliRunner(mix_stderr=False) keeps streams separate; the error message is
    # echoed to stderr via `typer.echo(..., err=True)`.
    assert "not found" in result.stderr


# ---------------------------------------------------------------------------
# Test 17: run --all --dry-run -> exit 0, dry_run=True threaded through
# ---------------------------------------------------------------------------


def test_cli_run_all_dry_run_exits_zero(
    monkeypatch: pytest.MonkeyPatch,
    fake_session_scope: MagicMock,
) -> None:
    captured: dict[str, Any] = {}

    def _fake_run_all(
        _session: Any,
        *,
        force: bool,
        now: Any,
        dry_run: bool = False,
    ) -> BatchResult:
        captured["dry_run"] = dry_run
        captured["force"] = force
        return BatchResult(
            sources_selected=2,
            succeeded=2,
            failed=0,
            skipped_not_due=0,
        )

    monkeypatch.setattr("medevents_ingest.cli.run_all", _fake_run_all)

    result = runner.invoke(app, ["run", "--all", "--dry-run"])

    assert result.exit_code == 0, result.output
    assert captured.get("dry_run") is True
    fake_session_scope.rollback.assert_called()


# ---------------------------------------------------------------------------
# Test 18: run --source --dry-run passes preview lines through to stdout
# ---------------------------------------------------------------------------


def test_cli_run_source_dry_run_emits_preview_lines(
    monkeypatch: pytest.MonkeyPatch,
    fake_session_scope: MagicMock,
) -> None:
    fake_source = MagicMock(name="Source")
    fake_source.parser_name = "ada"
    monkeypatch.setattr(
        "medevents_ingest.cli.get_source_by_code",
        lambda _s, _c: fake_source,
    )
    monkeypatch.setattr(
        "medevents_ingest.cli.parser_for",
        lambda _n: MagicMock(name="Parser"),
    )

    def _fake_run_source(
        _session: Any,
        *,
        source_code: str,
        force: bool = False,
        dry_run: bool = False,
    ) -> PipelineResult:
        # Simulate pipeline.py's real dry-run preview output.
        print("dry_run=1 preview event='Example Event' starts_on=2026-10-01")
        return _make_pipeline_result(source_code=source_code)

    monkeypatch.setattr("medevents_ingest.cli.run_source", _fake_run_source)

    result = runner.invoke(app, ["run", "--source", "ada", "--dry-run"])

    assert result.exit_code == 0, result.output
    assert "preview event='Example Event'" in result.stdout
    assert "dry_run=1 source=ada" in result.stdout
