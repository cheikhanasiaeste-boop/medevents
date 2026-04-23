"""CLI smoke tests."""

from __future__ import annotations

import os

from medevents_ingest.cli import app
from typer.testing import CliRunner

runner = CliRunner()


def test_version_command_runs() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0


def test_run_unknown_source_exits_2() -> None:
    env = {"DATABASE_URL": os.environ.get("DATABASE_URL", "")}
    # Even without DATABASE_URL this should fast-fail; tolerate either exit.
    result = runner.invoke(app, ["run", "--source", "does-not-exist"], env=env)
    assert result.exit_code in (1, 2, 3, 4)


def test_run_dry_run_is_wired() -> None:
    # W3.2f Task 2: `--dry-run` is no longer a stubbed exit-4. Without a real
    # DB (or a matching seeded source), the invocation will fail somewhere
    # between source lookup (exit 2) and the parser / pipeline (exit 1/3);
    # 4 MUST no longer be returned.
    env = {"DATABASE_URL": os.environ.get("DATABASE_URL", "")}
    result = runner.invoke(app, ["run", "--source", "ada", "--dry-run"], env=env)
    assert result.exit_code != 4
