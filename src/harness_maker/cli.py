"""harness-maker CLI entrypoint."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import typer

from harness_maker.add_domain import AddDomainError, add_domain, validate_domain_name
from harness_maker.block_merge import MergeReport
from harness_maker.interview import answers_from_harness_yaml, interview
from harness_maker.modular_edit import ModularEditError
from harness_maker.modular_edit import add as modular_add
from harness_maker.modular_edit import remove as modular_remove
from harness_maker.profile import profile
from harness_maker.reconcile import backup, reconcile
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize
from harness_maker.verify import verify

# Shipped sample packs that come bundled in templates/agents/_standards/<name>.md.j2.
# When --add-domain matches one of these, no user-side stub is needed because
# the reviewer Jinja include resolves to the shipped sample.
_SHIPPED_DOMAIN_SAMPLES: frozenset[str] = frozenset({"python"})

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
    add_domain_name: str | None = typer.Option(
        None,
        "--add-domain",
        help=(
            "Register a domain standards pack (e.g. 'tauri'). Adds the name to "
            "harness.yaml project.domains; creates a user-side stub for "
            "non-shipped names. Shipped samples: python."
        ),
    ),
    reinterview: bool = typer.Option(
        False,
        "--reinterview",
        help=(
            "Force the interactive interview even when an existing "
            ".claude/harness.yaml is present. Default: silently reuse prior "
            "answers on re-render."
        ),
    ),
) -> None:
    """Generate or refine the project harness at TARGET/.claude/."""
    p = profile(target)
    # Re-render path: silently reuse prior interview answers from harness.yaml
    # so locale / dev_mode / custom workflows / reviewer-enablement survive
    # without re-prompting. --reinterview forces fresh prompts; --autoloop
    # only kicks in for first-time installs (no harness.yaml yet).
    existing_yaml = target / ".claude" / "harness.yaml"
    reused = None if reinterview else answers_from_harness_yaml(existing_yaml)
    if reused is not None:
        a = reused
        typer.echo(f"reusing settings from {existing_yaml.relative_to(target)}")
    else:
        # Fresh install + non-tty stdin (e.g., invoked via Claude Code slash
        # command, where AskUserQuestion isn't piped through) → auto-flip to
        # autoloop defaults instead of hanging on the interactive prompt.
        effective_autoloop = autoloop or (not sys.stdin.isatty())
        if effective_autoloop and not autoloop:
            typer.echo("non-tty stdin detected; using --autoloop defaults")
        a = interview(p, autoloop_mode=effective_autoloop)
    if add_domain_name is not None:
        try:
            validate_domain_name(add_domain_name)
        except AddDomainError as e:
            typer.echo(f"--add-domain failed: {e}", err=True)
            raise typer.Exit(code=1) from e
        if add_domain_name not in a.domains:
            a.domains.append(add_domain_name)
    bp = synthesize(p, a)
    target_dotclaude = target / ".claude"
    merge_paths: set[Path] = set()
    keep_count = 0
    if target_dotclaude.exists() and any(target_dotclaude.iterdir()):
        backup(target_dotclaude)
        conflicts = reconcile(target_dotclaude, bp)
        from harness_maker.models import ReconcileDecision

        keep_paths = {c.path for c in conflicts if c.decision == ReconcileDecision.KEEP}
        merge_paths = {c.path for c in conflicts if c.decision == ReconcileDecision.MERGE_BLOCK}
        keep_count = len(keep_paths)
        new_files = [f for f in bp.files if f.path not in keep_paths]
        bp = bp.model_copy(update={"files": new_files})
    freeze = DEFAULT_FREEZE_TIME if os.environ.get("HARNESS_MAKER_FREEZE") else None
    merge_reports: dict[Path, MergeReport] = {}
    render(
        bp,
        target_dotclaude,
        freeze_time=freeze,
        merge_paths=merge_paths,
        merge_reports=merge_reports,
    )
    _emit_reconcile_report(keep_count, merge_reports)
    errors = verify(target_dotclaude)
    if errors:
        for err in errors:
            typer.echo(f"VERIFY ERROR: {err}", err=True)
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

    if add_domain_name is not None and add_domain_name not in _SHIPPED_DOMAIN_SAMPLES:
        # User-authored pack: render the skeleton at user side so they can fill
        # in the rules. Shipped names skip this — their content is already
        # inlined into reviewers via the Jinja include.
        try:
            stub = add_domain(target, add_domain_name)
        except AddDomainError as e:
            typer.echo(f"--add-domain failed: {e}", err=True)
            raise typer.Exit(code=1) from e
        typer.echo(f"--add-domain stub created: {stub}")

    typer.echo(f"harness applied to {target_dotclaude} ({len(bp.files)} files)")


def _emit_reconcile_report(
    keep_count: int,
    merge_reports: dict[Path, MergeReport],
) -> None:
    """Surface what reconcile decided so the user knows their edits' fate."""
    if keep_count:
        typer.echo(
            f"  KEEP: {keep_count} file(s) preserved as-is "
            f"(no markers — won't receive new template content)",
        )
    for path, report in merge_reports.items():
        bits: list[str] = []
        if report.user_blocks_preserved:
            bits.append(
                f"preserved {len(report.user_blocks_preserved)} user block(s): "
                f"{', '.join(report.user_blocks_preserved)}",
            )
        if report.user_blocks_seeded:
            bits.append(
                f"seeded {len(report.user_blocks_seeded)} new block(s): "
                f"{', '.join(report.user_blocks_seeded)}",
            )
        if report.user_blocks_orphaned:
            bits.append(
                f"⚠ orphaned {len(report.user_blocks_orphaned)} block(s): "
                f"{', '.join(report.user_blocks_orphaned)}",
            )
        if bits:
            typer.echo(f"  MERGE_BLOCK: {path} — {'; '.join(bits)}")


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
