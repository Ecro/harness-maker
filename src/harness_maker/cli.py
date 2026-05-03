"""harness-maker CLI entrypoint."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import typer

from harness_maker.add_domain import AddDomainError, add_domain, validate_domain_name
from harness_maker.block_merge import MergeReport
from harness_maker.interview import answers_from_harness_yaml, interview
from harness_maker.models import Blueprint, FileEntry, InterviewAnswers
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
    preset_override: str | None = typer.Option(
        None,
        "--preset",
        help="Override preset for this run: 'Side' or 'Production'. Reuses "
        "all other answers from harness.yaml when present.",
    ),
    locale_override: str | None = typer.Option(
        None,
        "--locale",
        help="Override locale tag (e.g., 'ko', 'en', 'ja'). Free-text; "
        "unknown locales fall back to English at runtime.",
    ),
    dev_mode_override: str | None = typer.Option(
        None,
        "--dev-mode",
        help="Override dev_mode: 'spec-driven' or 'task-driven'.",
    ),
    statusline_policy: str | None = typer.Option(
        None,
        "--statusline-policy",
        help=(
            "How to handle an existing custom statusLine in settings.json: "
            "'keep' (preserve user, install nothing), 'overwrite' (replace "
            "with harness-maker's), or 'combine' (render a wrapper that "
            "joins user output + harness-maker output). Default: preserve "
            "user-custom statusLines silently; auto-upgrade harness-shipped ones."
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
    a = _apply_dimension_overrides(
        a,
        preset_override=preset_override,
        locale_override=locale_override,
        dev_mode_override=dev_mode_override,
    )
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
    bp = _apply_statusline_policy(bp, target_dotclaude, statusline_policy)
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
        statusline_policy=statusline_policy,
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


_VALID_STATUSLINE_POLICIES: frozenset[str] = frozenset({"keep", "overwrite", "combine"})


def _apply_statusline_policy(
    blueprint: Blueprint,
    target_dotclaude: Path,
    policy: str | None,
) -> Blueprint:
    """Append combined-wrapper FileEntries to the blueprint when policy=combine.

    Reads the user's prior statusLine command from ``settings.json`` so the
    one-shot ``user-statusline.sh`` captures it. ``keep`` / ``overwrite`` /
    None require no extra files — they're handled by the merge logic at
    settings.json render time.
    """
    if policy is None:
        return blueprint
    if policy not in _VALID_STATUSLINE_POLICIES:
        typer.echo(
            f"--statusline-policy invalid: {policy} (expected: keep | overwrite | combine)",
            err=True,
        )
        raise typer.Exit(code=1)
    if policy != "combine":
        return blueprint
    user_cmd = _read_existing_statusline_command(target_dotclaude / "settings.json")
    if user_cmd is None:
        typer.echo(
            "--statusline-policy=combine: no existing custom statusLine to combine; "
            "falling back to overwrite.",
            err=True,
        )
        return blueprint
    extra = [
        FileEntry(
            path=Path("lib/user-statusline.sh"),
            template="lib/user-statusline.sh.j2",
            context={"user_statusline_command": user_cmd},
        ),
        FileEntry(
            path=Path("lib/run-statusline-combined.sh"),
            template="lib/run-statusline-combined.sh.j2",
            context={},
        ),
    ]
    return blueprint.model_copy(update={"files": [*blueprint.files, *extra]})


def _read_existing_statusline_command(settings_path: Path) -> str | None:
    """Best-effort extract of ``statusLine.command`` from existing settings.json."""
    if not settings_path.exists():
        return None
    try:
        text = settings_path.read_text(encoding="utf-8")
    except OSError:
        return None
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end != -1:
            text = text[end + 5 :]
    import json as _json

    try:
        data = _json.loads(text)
    except _json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    sl = data.get("statusLine")
    if not isinstance(sl, dict):
        return None
    cmd = sl.get("command")
    return cmd if isinstance(cmd, str) and cmd else None


def _apply_dimension_overrides(
    answers: InterviewAnswers,
    *,
    preset_override: str | None,
    locale_override: str | None,
    dev_mode_override: str | None,
) -> InterviewAnswers:
    """Apply per-dimension CLI overrides (preset/locale/dev_mode) on top of
    the answers (whether reused or freshly interviewed).

    Switching ``preset`` also re-derives the preset-coupled extras
    (``models`` / ``autoloop`` / ``memory`` / ``anti_rot`` / ``worktree`` /
    ``security`` / ``context_lint`` / default reviewer & skill enablement)
    so a Side→Production flip actually unlocks Production-only behaviour
    rather than leaving stale Side defaults around.
    """
    from harness_maker.interview import _build_answers
    from harness_maker.models import DevMode, Preset

    update: dict[str, object] = {}
    if locale_override:
        update["locale"] = locale_override
    if dev_mode_override:
        try:
            update["dev_mode"] = DevMode(dev_mode_override)
        except ValueError as e:
            typer.echo(f"--dev-mode invalid: {dev_mode_override}", err=True)
            raise typer.Exit(code=1) from e
    if preset_override:
        try:
            new_preset = Preset(preset_override)
        except ValueError as e:
            typer.echo(f"--preset invalid: {preset_override}", err=True)
            raise typer.Exit(code=1) from e
        if new_preset != answers.preset:
            # Rebuild from scratch so preset-derived extras are correct, then
            # re-overlay the answers we want to carry across (workflows,
            # locale, etc.).
            rebuilt = _build_answers(
                locale=answers.locale,
                preset=new_preset,
                dev_mode=answers.dev_mode,
                fused_workflows=answers.fused_workflows,
                default_workflow=answers.default_workflow,
                consensus=answers.consensus,
                caching=answers.caching,
            )
            return rebuilt.model_copy(update=update)
    return answers.model_copy(update=update) if update else answers


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
