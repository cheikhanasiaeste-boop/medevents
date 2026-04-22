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
    """Run ingest for one source end-to-end (fetch -> parse -> upsert)."""
    from .pipeline import run_source

    if dry_run:
        typer.echo("ERROR: --dry-run is not yet implemented (W3).", err=True)
        raise typer.Exit(code=4)

    with session_scope() as s:
        src = get_source_by_code(s, source)
        if src is None:
            typer.echo(f"ERROR: source '{source}' not found in DB. Run seed-sources?", err=True)
            raise typer.Exit(code=2)
        try:
            parser_for(src.parser_name)
        except UnknownParserError as exc:
            typer.echo(f"ERROR: {exc}", err=True)
            raise typer.Exit(code=3) from exc

        result = run_source(s, source_code=source, force=force)

    typer.echo(
        f"source={result.source_code} "
        f"fetched={result.pages_fetched} "
        f"skipped_unchanged={result.pages_skipped_unchanged} "
        f"created={result.events_created} "
        f"updated={result.events_updated} "
        f"review_items={result.review_items_created}"
    )


if __name__ == "__main__":
    app()
