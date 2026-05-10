"""harness-maker CLI entrypoint."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import typer

from harness_maker.add_domain import AddDomainError, add_domain, validate_domain_name
from harness_maker.block_merge import MergeReport
from harness_maker.interview import answers_from_harness_yaml, interview
from harness_maker.models import Blueprint, InterviewAnswers, Preset, RefFolder
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
    remove: list[str] = typer.Option(  # noqa: B008
        default=[],
        help="Remove a component (e.g. 'reviewer:security'). Repeatable.",
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
    update: bool = typer.Option(
        False,
        "--update",
        help=(
            "Re-render silently using existing .claude/harness.yaml answers "
            "(no interview). Errors if .claude/harness.yaml is absent — "
            "run harness-maker make (without --update) for initial setup. "
            "--reinterview overrides --update when both are set."
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
    targets_override: str | None = typer.Option(
        None,
        "--targets",
        help="Override IDE targets (comma-separated): 'claude-code', "
        "'cursor', or 'claude-code,cursor'. Re-renders cursor assets when "
        "'cursor' is added; leaves them in place (and unreferenced) when "
        "removed — delete .cursor/ manually if undesired.",
    ),
    grade_threshold_override: str | None = typer.Option(
        None,
        "--grade-threshold",
        help="Review grade gate: A (strict) | B (moderate) | C (relaxed).",
    ),
    domains_override: str | None = typer.Option(
        None,
        "--domains",
        help="Comma-separated domain packs: python, tauri, react, ...",
    ),
    mechanical_checks_override: str | None = typer.Option(
        None,
        "--mechanical-checks",
        help="Semicolon-separated pre-review commands.",
    ),
    recommended_model_override: str | None = typer.Option(
        None,
        "--recommended-model",
        help="Claude model: opus | sonnet | haiku.",
    ),
    focus_override: str | None = typer.Option(
        None,
        "--focus",
        help="Primary work focus: feature|bugfix|security|performance|refactoring.",
    ),
    wrapup_docs_override: str | None = typer.Option(
        None,
        "--wrapup-docs",
        help="Semicolon-separated doc paths for wrapup to update (e.g. CHANGELOG.md;TODO.md).",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Print what would be installed; do not write files.",
    ),
) -> None:
    """Generate or refine the project harness at TARGET/.claude/."""
    existing_yaml = target / ".claude" / "harness.yaml"
    if update and not reinterview and not existing_yaml.is_file():
        typer.echo(
            f"No {existing_yaml.relative_to(target)} found — "
            "run harness-maker make (without --update) for initial setup.",
            err=True,
        )
        raise typer.Exit(code=1)
    p = profile(target)
    # Re-render path: silently reuse prior interview answers from harness.yaml
    # so locale / dev_mode / custom workflows / reviewer-enablement survive
    # without re-prompting. --reinterview forces fresh prompts; --autoloop
    # only kicks in for first-time installs (no harness.yaml yet).
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
        targets_override=targets_override,
        grade_threshold_override=grade_threshold_override,
        domains_override=domains_override,
        mechanical_checks_override=mechanical_checks_override,
        recommended_model_override=recommended_model_override,
        focus_override=focus_override,
        wrapup_docs_override=wrapup_docs_override,
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

    if dry_run:
        _emit_dry_run_summary(bp, target_dotclaude)
        raise typer.Exit(0)

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
    written = render(
        bp,
        target_dotclaude,
        freeze_time=freeze,
        merge_paths=merge_paths,
        merge_reports=merge_reports,
    )
    _write_harness_manifest(target_dotclaude, written)
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
    for remove_spec in remove:
        try:
            removed_path = modular_remove(remove_spec, target_dotclaude)
        except ModularEditError as e:
            typer.echo(f"--remove failed: {e}", err=True)
            raise typer.Exit(code=1) from e
        typer.echo(f"--remove applied: {removed_path}")

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
    _emit_install_summary(a, bp)
    _emit_post_make_readiness(target, a.preset)
    _emit_refdocs_index_build(target, a.ref_folders)


def _emit_dry_run_summary(bp: Blueprint, target_dotclaude: Path) -> None:
    """Print what make() would install without writing any files."""
    existing = set()
    if target_dotclaude.exists():
        for p in target_dotclaude.rglob("*"):
            if p.is_file():
                existing.add(p.relative_to(target_dotclaude))

    new_count = 0
    replace_count = 0
    for fe in bp.files:
        if fe.path in existing:
            replace_count += 1
        else:
            new_count += 1

    typer.echo("─" * 50)
    typer.echo("DRY RUN — no files will be written")
    typer.echo("─" * 50)
    typer.echo(f"  NEW:     {new_count}")
    typer.echo(f"  REPLACE: {replace_count}")
    typer.echo(f"  Total:   {len(bp.files)} files")
    typer.echo("─" * 50)

    cmd_files = [str(f.path) for f in bp.files if str(f.path).startswith("commands/hm/")]
    if cmd_files:
        typer.echo(f"\nSlash commands ({len(cmd_files)}):")
        for c in sorted(cmd_files):
            name = c.replace("commands/hm/", "/hm:").replace(".md", "")
            typer.echo(f"  {name}")


def _emit_install_summary(
    answers: InterviewAnswers,
    bp: Blueprint,
) -> None:
    """Post-install summary with commands, reviewers, and quick-start."""
    try:
        cmd_files = [str(f.path) for f in bp.files if str(f.path).startswith("commands/hm/")]
        reviewer_enabled = answers.reviewers.get("enabled", [])

        typer.echo("\n" + "─" * 50)
        typer.echo("Install summary")
        typer.echo("─" * 50)

        if cmd_files:
            typer.echo(f"\nSlash commands ({len(cmd_files)}):")
            for c in sorted(cmd_files):
                name = c.replace("commands/hm/", "/hm:").replace(".md", "")
                typer.echo(f"  {name}")

        typer.echo(f"\nReviewers active: {', '.join(reviewer_enabled) or '(none)'}")
        typer.echo(f"Grade threshold: {answers.grade_threshold}")

        if answers.mechanical_checks:
            typer.echo(f"Mechanical checks: {'; '.join(answers.mechanical_checks)}")

        typer.echo("\nQuick start:")
        typer.echo("  /hm:execute <task>       — implement a feature with TDD")
        typer.echo("  /hm:ai-readiness         — check AI-readiness score")
        typer.echo("  /hm:configure            — adjust settings later")
        typer.echo("  /hm:make                 — re-render after plugin update")
    except Exception:  # noqa: BLE001 — diagnostic, never fail the make
        pass


def _write_harness_manifest(target_dotclaude: Path, written: list[Path]) -> None:
    """Write .harness-manifest.json listing all rendered file paths.

    Used by Phase 7 (uninstall) to identify frontmatter-less files like
    settings.json and hooks/hooks.json that lack generated_by markers.
    """
    import json

    from harness_maker import __version__

    manifest = {
        "generated_by": "harness-maker",
        "version": __version__,
        "files": sorted(str(p) for p in written),
    }
    manifest_path = target_dotclaude / ".harness-manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )


def _emit_refdocs_index_build(target: Path, ref_folders: list[RefFolder]) -> None:
    """Build docs_index.yaml so the refdocs-search skill has metadata to triage with.

    No-op when no ref_folders were registered. Failures are swallowed with a
    user-visible note — the index can always be rebuilt via
    ``python -m harness_maker.refdocs_index build``.
    """
    if not ref_folders:
        return
    try:
        from harness_maker.refdocs_index import build as build_refdocs_index

        result = build_refdocs_index(target, ref_folders)
    except Exception as e:  # noqa: BLE001 — diagnostic, never fail the make
        typer.echo(f"\n(refdocs index skipped: {type(e).__name__}: {e})")
        return
    typer.echo(
        f"\nref_folders index: {result.entry_count} entries → "
        f"{result.index_path.relative_to(target)}",
    )
    for w in result.warnings:
        typer.echo(f"  warn: {w}")


def _emit_post_make_readiness(target: Path, preset: Preset) -> None:
    """Run the cheap (skip_llm) ai-readiness scan and surface the top actions.

    Wrapped in a broad except so a diagnostic failure never breaks ``make``.
    """
    try:
        from harness_maker.ai_readiness import render_terminal_summary, run_ai_readiness

        plan = run_ai_readiness(target, preset=preset, skip_llm=True)
    except Exception as e:  # noqa: BLE001 — diagnostic, never fail the make
        typer.echo(f"\n(ai-readiness scan skipped: {type(e).__name__}: {e})")
        return
    typer.echo("\n" + "─" * 64)
    typer.echo("Initial AI-readiness scan (LLM judge skipped — see hint below)")
    typer.echo("─" * 64)
    typer.echo(render_terminal_summary(plan, max_actions=5))
    typer.echo("\nNext steps:")
    typer.echo("  • Run /hm:ai-readiness for the full LLM-judged scan + dashboard.")
    typer.echo("  • Walk the action list above; fix P0 items first.")


def _apply_dimension_overrides(
    answers: InterviewAnswers,
    *,
    preset_override: str | None,
    locale_override: str | None,
    dev_mode_override: str | None,
    targets_override: str | None,
    grade_threshold_override: str | None = None,
    domains_override: str | None = None,
    mechanical_checks_override: str | None = None,
    recommended_model_override: str | None = None,
    focus_override: str | None = None,
    wrapup_docs_override: str | None = None,
) -> InterviewAnswers:
    """Apply per-dimension CLI overrides on top of the answers.

    Precedence: CLI flag > harness.yaml > preset default.

    Switching ``preset`` also re-derives the preset-coupled extras
    (``models`` / ``autoloop`` / ``memory`` / ``anti_rot`` / ``worktree`` /
    ``security`` / ``context_lint`` / default reviewer & skill enablement)
    so a Side→Production flip actually unlocks Production-only behaviour
    rather than leaving stale Side defaults around. Extended flags
    (grade_threshold, domains, etc.) are re-applied AFTER the rebuild.
    """
    from harness_maker.interview import _build_answers, _focus_to_additional_reviewers
    from harness_maker.models import DevMode, Preset, Target

    update: dict[str, object] = {}
    if locale_override:
        update["locale"] = locale_override
    if dev_mode_override:
        try:
            update["dev_mode"] = DevMode(dev_mode_override)
        except ValueError as e:
            typer.echo(f"--dev-mode invalid: {dev_mode_override}", err=True)
            raise typer.Exit(code=1) from e
    if targets_override:
        raw = [t.strip() for t in targets_override.split(",") if t.strip()]
        if not raw:
            typer.echo("--targets must specify at least one target", err=True)
            raise typer.Exit(code=1)
        try:
            parsed = [Target(t) for t in raw]
        except ValueError as e:
            valid = ", ".join(t.value for t in Target)
            typer.echo(
                f"--targets invalid: {targets_override!r} (valid: {valid})",
                err=True,
            )
            raise typer.Exit(code=1) from e
        seen: set[Target] = set()
        deduped: list[Target] = []
        for t in parsed:
            if t not in seen:
                seen.add(t)
                deduped.append(t)
        update["targets"] = deduped
    if grade_threshold_override:
        update["grade_threshold"] = grade_threshold_override
    if domains_override:
        update["domains"] = [d.strip() for d in domains_override.split(",") if d.strip()]
    if mechanical_checks_override:
        update["mechanical_checks"] = [
            c.strip() for c in mechanical_checks_override.split(";") if c.strip()
        ]
    if recommended_model_override:
        update["recommended_model"] = recommended_model_override
    if wrapup_docs_override:
        update["wrapup_docs"] = [
            d.strip() for d in wrapup_docs_override.split(";") if d.strip()
        ]

    if preset_override:
        try:
            new_preset = Preset(preset_override)
        except ValueError as e:
            typer.echo(f"--preset invalid: {preset_override}", err=True)
            raise typer.Exit(code=1) from e
        if new_preset != answers.preset:
            rebuilt = _build_answers(
                locale=answers.locale,
                targets=list(answers.targets),
                preset=new_preset,
                dev_mode=answers.dev_mode,
                fused_workflows=answers.fused_workflows,
                default_workflow=answers.default_workflow,
                consensus=answers.consensus,
                caching=answers.caching,
            )
            result = rebuilt.model_copy(update=update)
            if focus_override:
                additional = _focus_to_additional_reviewers(focus_override, new_preset)
                if additional:
                    enabled = list(result.reviewers["enabled"])
                    for r in additional:
                        if r not in enabled:
                            enabled.append(r)
                    result = result.model_copy(
                        update={"reviewers": {**result.reviewers, "enabled": enabled}}
                    )
            return result

    result = answers.model_copy(update=update) if update else answers
    if focus_override:
        effective_preset = Preset(preset_override) if preset_override else answers.preset
        additional = _focus_to_additional_reviewers(focus_override, effective_preset)
        if additional:
            enabled = list(result.reviewers["enabled"])
            for r in additional:
                if r not in enabled:
                    enabled.append(r)
            result = result.model_copy(
                update={"reviewers": {**result.reviewers, "enabled": enabled}}
            )
    return result


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


_AI_READINESS_TARGET = typer.Argument(
    Path("."),
    help="Project root (the directory containing .claude/).",
)


@app.command("ai-readiness")
def ai_readiness_cmd(
    target: Path = _AI_READINESS_TARGET,
    skip_llm: bool = typer.Option(
        False,
        "--skip-llm",
        help="Skip Layer 2 (LLM judge). Use with --json-output to feed Claude-native L2.",
    ),
    model: str = typer.Option(
        "claude-sonnet-4-6",
        "--model",
        help="Model hint for cache diagnostics threshold calculation.",
    ),
    update_dashboard: bool = typer.Option(
        True,
        "--update-dashboard/--no-update-dashboard",
        help="Write the rendered plan to .claude/observability/dashboard.md.",
    ),
    json_output: Path | None = typer.Option(  # noqa: B008
        None,
        "--json-output",
        help="Write L1+L3 structural scores as JSON to this path (implies --skip-llm).",
    ),
) -> None:
    """Compute ai-readiness composite + ranked improvement actions."""
    from harness_maker.ai_readiness import (
        render_dashboard_markdown,
        render_terminal_summary,
        run_ai_readiness,
        run_ai_readiness_structural,
    )
    from harness_maker.io_utils import atomic_write

    target = target.resolve()
    preset = _read_preset(target / ".claude" / "harness.yaml") or Preset.SIDE

    if json_output is not None:
        # Structural-only mode: write L1+L3 as JSON for Claude-native L2 finalize.
        import json

        scores = run_ai_readiness_structural(target, preset=preset, model=model)
        json_output.parent.mkdir(parents=True, exist_ok=True)
        json_output.write_text(json.dumps(scores, indent=2), encoding="utf-8")
        typer.echo(f"Structural scores written to {json_output}")
        # Also print L1+L3 partial summary (L2=50 neutral placeholder).
        from harness_maker.cache_diagnostics import CacheDiagnosis
        from harness_maker.improvement import build_improvement_plan
        from harness_maker.readiness import ReadinessResult

        readiness = ReadinessResult.model_validate(scores["readiness"])
        cache = CacheDiagnosis.model_validate(scores["cache"])
        plan = build_improvement_plan(readiness, [], cache)
        typer.echo(render_terminal_summary(plan))
        typer.echo("(Layer 2 pending — run ai-readiness-finalize after Claude evaluates rubrics)")
        return

    plan = run_ai_readiness(target, preset=preset, skip_llm=skip_llm, model=model)
    typer.echo(render_terminal_summary(plan))
    if update_dashboard:
        dashboard = target / ".claude" / "observability" / "dashboard.md"
        body = render_dashboard_markdown(plan, target.name)
        atomic_write(dashboard, body)
        typer.echo(f"\nDashboard updated: {dashboard}")


@app.command("ai-readiness-finalize")
def ai_readiness_finalize_cmd(
    target: Path = typer.Argument(  # noqa: B008
        default_factory=Path.cwd,
        help="Project root (the directory containing .claude/).  Defaults to cwd.",
    ),
    scores_json: Path = typer.Option(  # noqa: B008
        ...,
        "--scores-json",
        help="Path to L1+L3 scores JSON written by ai-readiness --json-output.",
    ),
    verdicts_json: Path = typer.Option(  # noqa: B008
        ...,
        "--verdicts-json",
        help="Path to Claude-provided L2 verdicts JSON.",
    ),
    update_dashboard: bool = typer.Option(
        True,
        "--update-dashboard/--no-update-dashboard",
        help="Write the rendered plan to .claude/observability/dashboard.md.",
    ),
) -> None:
    """Combine pre-computed L1+L3 scores with Claude-provided L2 verdicts."""
    from harness_maker.ai_readiness import (
        finalize_from_verdicts_json,
        render_dashboard_markdown,
        render_terminal_summary,
    )
    from harness_maker.io_utils import atomic_write

    plan = finalize_from_verdicts_json(scores_json, verdicts_json)
    typer.echo(render_terminal_summary(plan))
    if update_dashboard:
        target = target.resolve()
        dashboard = target / ".claude" / "observability" / "dashboard.md"
        body = render_dashboard_markdown(plan, target.name)
        atomic_write(dashboard, body)
        typer.echo(f"\nDashboard updated: {dashboard}")


def _read_preset(harness_yaml: Path) -> Preset | None:
    """Best-effort preset extraction; returns None on any failure."""
    if not harness_yaml.is_file():
        return None
    import yaml as _yaml

    try:
        text = harness_yaml.read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        for doc in _yaml.safe_load_all(text):
            if isinstance(doc, dict) and "preset" in doc:
                try:
                    return Preset(doc["preset"])
                except (ValueError, TypeError):
                    return None
    except _yaml.YAMLError:
        return None
    return None


@app.command("remove")
def remove_cmd(
    target: Path = typer.Argument(  # noqa: B008
        default_factory=Path.cwd,
        help="Project root to remove harness from.",
    ),
    remove_yaml: bool = typer.Option(
        False,
        "--remove-yaml",
        help="Also remove harness.yaml (default: keep).",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Show what would be removed; do not delete.",
    ),
) -> None:
    """Remove harness-maker generated files from a project."""
    import json

    target_dotclaude = target / ".claude"
    manifest_path = target_dotclaude / ".harness-manifest.json"

    if not manifest_path.exists():
        typer.echo(
            "No .harness-manifest.json found — cannot determine managed files.",
            err=True,
        )
        raise typer.Exit(code=1)

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    file_list: list[str] = manifest.get("files", [])

    removed: list[str] = []
    skipped: list[str] = []

    for rel in file_list:
        if rel == "harness.yaml" and not remove_yaml:
            continue

        fpath = target_dotclaude / rel
        if not fpath.exists():
            continue

        if _has_user_block(fpath):
            skipped.append(rel)
            continue

        if dry_run:
            removed.append(rel)
        else:
            fpath.unlink()
            removed.append(rel)
            _rmdir_if_empty(fpath.parent)

    if not dry_run:
        manifest_path.unlink(missing_ok=True)
        _rmdir_if_empty(manifest_path.parent)

    action = "Would remove" if dry_run else "Removed"
    typer.echo(f"{action} {len(removed)} file(s), skipped {len(skipped)} (user blocks)")
    if skipped:
        for s in skipped:
            typer.echo(f"  skipped (user block): .claude/{s}")
    if removed and dry_run:
        for r in removed:
            typer.echo(f"  {r}")


def _has_user_block(fpath: Path) -> bool:
    """Check if a file contains @hm:user: markers."""
    try:
        content = fpath.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False
    return "@hm:user:" in content


def _rmdir_if_empty(d: Path) -> None:
    """Remove directory if empty, walking up to .claude/."""
    try:
        while d.name and d.name != ".claude":
            if d.exists() and not any(d.iterdir()):
                d.rmdir()
                d = d.parent
            else:
                break
    except OSError:
        pass


@app.command("profile")
def profile_cmd(
    target: Path = typer.Argument(  # noqa: B008
        default_factory=Path.cwd,
        help="Project root to profile.",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output as JSON (one line).",
    ),
) -> None:
    """Inspect project and output detected profile signals."""
    p = profile(target)
    if json_output:
        typer.echo(p.model_dump_json())
    else:
        typer.echo(f"stack: {', '.join(p.stack)}")
        typer.echo(f"scale: {p.scale}")
        typer.echo(f"lifecycle: {p.lifecycle}")
        typer.echo(f"existing_dotclaude: {p.existing_dotclaude}")
        typer.echo(f"spec_only: {p.spec_only}")
        typer.echo(f"vault_member: {p.vault_member}")
        if p.detected_checks:
            typer.echo(f"detected_checks: {', '.join(p.detected_checks)}")
        else:
            typer.echo("detected_checks: (none)")


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
