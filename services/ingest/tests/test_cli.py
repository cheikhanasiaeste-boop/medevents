"""CLI smoke tests."""

from medevents_ingest import __version__
from medevents_ingest.cli import app
from typer.testing import CliRunner


def test_version_prints_package_version() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout
