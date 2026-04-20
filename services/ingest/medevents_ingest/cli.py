"""Typer entrypoint for the ingest CLI."""

from __future__ import annotations

from pathlib import Path

import typer

from .db import session_scope
from .seed import load_source_seeds, upsert_all

app = typer.Typer(no_args_is_help=True, add_completion=False, help="MedEvents ingestion CLI")


@app.command()
def version() -> None:
    """Print the package version."""
    from . import __version__

    typer.echo(__version__)


@app.command("seed-sources")
def seed_sources(
    path: Path = typer.Option(  # noqa: B008
        Path("config/sources.yaml"),
        "--path",
        "-p",
        help="Path to sources.yaml relative to repo root.",
    ),
) -> None:
    """Upsert curated sources from YAML into the `sources` table."""
    if not path.exists():
        typer.echo(f"ERROR: {path} not found", err=True)
        raise typer.Exit(code=2)
    seeds = load_source_seeds(path)
    with session_scope() as s:
        n = upsert_all(s, seeds)
    typer.echo(f"upserted {n} source(s) from {path}")


if __name__ == "__main__":
    app()
