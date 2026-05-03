"""harness-maker CLI entrypoint."""

from __future__ import annotations

import os
from pathlib import Path

import typer

from harness_maker.interview import interview
from harness_maker.modular_edit import ModularEditError
from harness_maker.modular_edit import add as modular_add
from harness_maker.modular_edit import remove as modular_remove
from harness_maker.profile import profile
from harness_maker.reconcile import backup, reconcile
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize
from harness_maker.verify import verify

app = typer.Typer(
    help="harness-maker — project-tailored Claude Code harness generator",
    no_args_is_help=False,
)


@app.command()
def make(
    target: Path = typer.Argument(  # noqa: B008
        default_factory=Path.cwd,
        help="Target project directory (defaults to cwd)",
    ),
    autoloop: bool = typer.Option(False, "--autoloop", help="Use defaults silently"),
    audit: bool = typer.Option(False, "--audit", help="Audit existing .claude/ structure"),  # noqa: ARG001
    add: str | None = typer.Option(
        None,
        "--add",
        help="Add a component (e.g. 'reviewer:security' or 'skill:conditional-router')",
    ),
    remove: str | None = typer.Option(
        None,
        "--remove",
        help="Remove a component (e.g. 'reviewer:security')",
    ),
    promote: str | None = typer.Option(  # noqa: ARG001
        None,
        "--promote",
        help="Promote a component to harness",
    ),
) -> None:
    """Generate or refine the project harness at TARGET/.claude/."""
    p = profile(target)
    a = interview(p, autoloop_mode=autoloop)
    bp = synthesize(p, a)
    target_dotclaude = target / ".claude"
    if target_dotclaude.exists() and any(target_dotclaude.iterdir()):
        backup(target_dotclaude)
        conflicts = reconcile(target_dotclaude, bp)
        from harness_maker.models import ReconcileDecision

        keep_paths = {c.path for c in conflicts if c.decision == ReconcileDecision.KEEP}
        new_files = [f for f in bp.files if f.path not in keep_paths]
        bp = bp.model_copy(update={"files": new_files})
    freeze = DEFAULT_FREEZE_TIME if os.environ.get("HARNESS_MAKER_FREEZE") else None
    render(bp, target_dotclaude, freeze_time=freeze)
    errors = verify(target_dotclaude)
    if errors:
        for e in errors:
            typer.echo(f"VERIFY ERROR: {e}", err=True)
        raise typer.Exit(code=1)

    # Phase 6 — modular installer hooks. Run AFTER the base make completes
    # so the installer mutates the freshly-rendered tree.
    if add:
        try:
            rendered = modular_add(add, target_dotclaude)
        except ModularEditError as e:
            typer.echo(f"--add failed: {e}", err=True)
            raise typer.Exit(code=1) from e
        typer.echo(f"--add applied: {rendered}")
    if remove:
        try:
            removed = modular_remove(remove, target_dotclaude)
        except ModularEditError as e:
            typer.echo(f"--remove failed: {e}", err=True)
            raise typer.Exit(code=1) from e
        typer.echo(f"--remove applied: {removed}")

    typer.echo(f"harness applied to {target_dotclaude} ({len(bp.files)} files)")


@app.command(hidden=True)
def _version() -> None:
    """Print version (hidden command, forces multi-command mode)."""
    from harness_maker import __version__

    typer.echo(__version__)


def main() -> None:
    """Run the typer app."""
    app()


if __name__ == "__main__":
    main()
