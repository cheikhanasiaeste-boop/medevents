"""Typer entrypoint for the ingest CLI."""

import typer

app = typer.Typer(no_args_is_help=True, add_completion=False, help="MedEvents ingestion CLI")


@app.callback()
def _main() -> None:
    """Force Typer to keep group mode (prevents single-command auto-promotion).

    Additional commands (`seed-sources`, `run`) land in later tasks; once any
    second command is registered this callback becomes cosmetic but harmless.
    """


@app.command()
def version() -> None:
    """Print the package version."""
    from . import __version__

    typer.echo(__version__)


if __name__ == "__main__":
    app()
