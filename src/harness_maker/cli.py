"""harness-maker CLI entrypoint."""

from __future__ import annotations

import typer

app = typer.Typer(help="harness-maker — project-tailored Claude Code harness generator")


@app.command()
def make(
    audit: bool = typer.Option(False, "--audit", help="Audit existing .claude/ structure"),
    add: str | None = typer.Option(None, "--add", help="Add a component by name"),
    remove: str | None = typer.Option(None, "--remove", help="Remove a component by name"),
    promote: str | None = typer.Option(None, "--promote", help="Promote a component to harness"),
) -> None:
    """Generate or refine the project harness."""
    raise NotImplementedError("Phase 1 skeleton — implementation in Phase 2+")


def main() -> None:
    """Run the typer app."""
    app()


if __name__ == "__main__":
    main()
