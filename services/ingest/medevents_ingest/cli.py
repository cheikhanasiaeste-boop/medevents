"""Typer entrypoint for the ingest CLI."""

from __future__ import annotations

from pathlib import Path

import typer

from .db import session_scope
from .parsers import UnknownParserError, parser_for
from .repositories.sources import get_source_by_code
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


@app.command()
def run(
    source: str = typer.Option(..., "--source", "-s", help="Source code (e.g. 'ada')."),
    force: bool = typer.Option(False, "--force", help="Ignore last_crawled_at."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Parse without writing."),
) -> None:
    """Run ingest for one source.

    W1: resolves the source + parser and exits cleanly. The actual fetch/parse/dedupe
    body is W2 work — this command exists so the operator 'Run now' button can be
    wired in W1 and verified end-to-end (it'll be a no-op until W2).
    """
    with session_scope() as s:
        src = get_source_by_code(s, source)
    if src is None:
        typer.echo(f"ERROR: source '{source}' not found in DB. Run seed-sources?", err=True)
        raise typer.Exit(code=2)

    try:
        parser = parser_for(src.parser_name)
    except UnknownParserError as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(code=3) from exc

    typer.echo(f"resolved source='{src.code}' parser='{parser.name}'")
    typer.echo(f"force={force} dry_run={dry_run}")
    typer.echo("W1: parser body not yet implemented (see W2 spec). Exiting cleanly.")


if __name__ == "__main__":
    app()
