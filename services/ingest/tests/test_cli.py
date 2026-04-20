"""CLI smoke tests."""

from typer.testing import CliRunner

from medevents_ingest import __version__
from medevents_ingest.cli import app


def test_version_prints_package_version() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout
