"""Typer entrypoint for the ingest CLI."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import typer

from .db import session_scope
from .parsers import UnknownParserError, parser_for
from .pipeline import run_all, run_source
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
    source: str | None = typer.Option(
        None,
        "--source",
        "-s",
        help="Source code (e.g. 'ada'). Mutually exclusive with --all.",
    ),
    run_all_flag: bool = typer.Option(
        False,
        "--all",
        help="Run every active source whose schedule is due. Mutually exclusive with --source.",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Under --all: run every active source regardless of due-ness.",
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Parse without writing."),
) -> None:
    """Run ingest for one source OR every active, due source."""
    if source is None and not run_all_flag:
        typer.echo("ERROR: must pass either --source CODE or --all", err=True)
        raise typer.Exit(code=2)
    if source is not None and run_all_flag:
        typer.echo("ERROR: --source and --all are mutually exclusive", err=True)
        raise typer.Exit(code=2)

    if run_all_flag:
        with session_scope() as s:
            try:
                batch = run_all(s, force=force, now=datetime.now(UTC), dry_run=dry_run)
            finally:
                # Belt-and-braces: guarantee no write survives the session scope
                # under --dry-run even if a bypass branch were missed in the
                # future. `session_scope` would otherwise commit on normal exit.
                if dry_run:
                    s.rollback()
        # Exit 0 if at least one source succeeded OR every source was skipped-not-due.
        # Exit non-zero only if at least one source was selected AND every selected source failed.
        if batch.sources_selected > 0 and batch.succeeded == 0:
            raise typer.Exit(code=1)
        return

    # Single-source path (unchanged semantic; --force still plumbing only here).
    # `source` is narrowed to `str` by the mutex validation above — if
    # run_all_flag is False, `source` must be non-None.
    assert source is not None
    with session_scope() as s:
        src = get_source_by_code(s, source)
        if src is None:
            typer.echo(
                f"ERROR: source '{source}' not found in DB. Run seed-sources?",
                err=True,
            )
            raise typer.Exit(code=2)
        try:
            parser_for(src.parser_name)
        except UnknownParserError as exc:
            typer.echo(f"ERROR: {exc}", err=True)
            raise typer.Exit(code=3) from exc

        try:
            result = run_source(s, source_code=source, force=force, dry_run=dry_run)
        finally:
            # Belt-and-braces rollback (see run_all branch above).
            if dry_run:
                s.rollback()

    prefix = "dry_run=1 " if dry_run else ""
    typer.echo(
        f"{prefix}source={result.source_code} "
        f"fetched={result.pages_fetched} "
        f"skipped_unchanged={result.pages_skipped_unchanged} "
        f"created={result.events_created} "
        f"updated={result.events_updated} "
        f"review_items={result.review_items_created}"
    )


if __name__ == "__main__":
    app()
