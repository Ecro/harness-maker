"""harness-maker CLI entrypoint."""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

import typer
import yaml

from harness_maker.add_domain import AddDomainError, add_domain, validate_domain_name
from harness_maker.block_merge import MergeReport
from harness_maker.interview import answers_from_harness_yaml, interview
from harness_maker.io_utils import atomic_write, denormalize_home_to_tilde
from harness_maker.locate import compare_version
from harness_maker.locate import resolve as resolve_plugin
from harness_maker.models import Blueprint, InterviewAnswers, Preset, RefFolder
from harness_maker.modular_edit import ModularEditError
from harness_maker.modular_edit import add as modular_add
from harness_maker.modular_edit import remove as modular_remove
from harness_maker.profile import profile
from harness_maker.reconcile import OrphanSweepReport, backup, reconcile, sweep_orphans
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize
from harness_maker.telemetry import (
    compute_yaml_diff,
    emit_override,
    now_iso,
)
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
    default_model_override: str | None = typer.Option(
        None,
        "--default-model",
        help=(
            "Floor fallback Claude model: opus | sonnet | haiku. "
            "Per-agent overrides go in harness.yaml > agent_models."
        ),
    ),
    recommended_model_override: str | None = typer.Option(
        None,
        "--recommended-model",
        help="[DEPRECATED — use --default-model. Removed no earlier than 0.17.0 per ADR-012.]",
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
    ref_folders_override: str | None = typer.Option(
        None,
        "--ref-folders",
        help=(
            "Reference doc folders for refdocs-search. '::'-separated entries, each 'path[;glob]'. "
            "Example: '../docs::../specs;**/*.pdf'"
        ),
    ),
    sibling_repos_override: str | None = typer.Option(
        None,
        "--sibling-repos",
        help="Semicolon-separated relative paths to sibling repos (e.g. '../backend;../frontend').",
    ),
    second_brain_vault_path: str | None = typer.Option(
        None,
        "--second-brain-vault-path",
        help=(
            "Obsidian vault path (absolute or ~-relative) to enable Second Brain. "
            "Pass empty string '' to disable."
        ),
    ),
    second_brain_project_id: str | None = typer.Option(
        None,
        "--second-brain-project-id",
        help="kebab-case project id for Second Brain namespace isolation.",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Print what would be installed; do not write files.",
    ),
    require_version: str | None = typer.Option(
        None,
        "--require-version",
        help=(
            ">=X.Y constraint on the installed harness-maker plugin. "
            "Exit 2 before any work if the resolved version is older. "
            "See `harness-maker locate --help` for resolution rules."
        ),
    ),
) -> None:
    """Generate or refine the project harness at TARGET/.claude/."""
    # PLAN-locate-cli-version-gate ADR-002 + REVIEW-2026-05-21 fixes:
    # - Resolve against `target` (not Path.cwd()) so the gate matches the
    #   project the user is operating on (F7).
    # - Exit 3 (not 2) when no install found to match locate's contract (F2).
    # - Multi-IDE recovery message — installed_plugins.json only holds Claude
    #   Code entries, but Cursor / Codex users may share that JSON or run
    #   their own update flows; list all three commands so the user picks (F17).
    # - Actionable "what to do" pointer for the no-install case (F18).
    if require_version is not None:
        entry = resolve_plugin(cwd=target.resolve())
        if entry is None:
            typer.echo(
                "harness-maker: --require-version specified but no installed "
                "plugin entry found (checked ~/.claude/plugins/installed_plugins.json). "
                "See docs/BOOTSTRAP.md for install instructions.",
                err=True,
            )
            raise typer.Exit(3)
        try:
            ok = compare_version(entry.version, require_version)
        except ValueError as e:
            typer.echo(f"harness-maker: --require-version invalid ({e})", err=True)
            raise typer.Exit(2) from None
        if not ok:
            typer.echo(
                f"harness-maker installed={entry.version} "
                f"(marketplace={entry.marketplace}) "
                f"required=>={require_version} — to update: "
                "`claude plugin update harness-maker` (Claude Code), "
                "`git -C <installPath> pull` (Cursor git clone), or "
                "`codex plugin update harness-maker` (Codex CLI)",
                err=True,
            )
            raise typer.Exit(2)

    # ADR-013 (PLAN-model-routing-multi-ide): turn the documented footgun
    # `[fail:snapshot-regen-inside-worktree]` (count:4) into enforced
    # prevention. Reject `--update` if cwd is inside a `.worktrees/`
    # ancestor — running regen from a worktree corrupts state because the
    # regen reads/writes the wrong working tree.
    #
    # Accepted risk: an explicit `target` argument pointing to a worktree
    # path (e.g. `make ./.worktrees/foo --update` from a clean cwd) is NOT
    # blocked. Adding that check would break harness-maker's own dogfood
    # sandbox regen pipeline (`tests/e2e/sandbox` lives inside the worktree
    # during local dev). Documented in REVIEW-... 2026-05-18.
    #
    # Bypass for CI / programmatic runs: HARNESS_MAKER_BYPASS_WORKTREE_GUARD=1.
    if update and not os.environ.get("HARNESS_MAKER_BYPASS_WORKTREE_GUARD"):
        try:
            cwd = Path.cwd().resolve()
        except OSError as exc:
            typer.echo(f"[ERROR] cannot resolve cwd: {exc}", err=True)
            raise typer.Exit(code=1) from exc
        for ancestor in [cwd, *cwd.parents]:
            if ancestor.name == ".worktrees":
                typer.echo(
                    f"[ERROR] Snapshot regen invoked from inside .worktrees/ — "
                    f"this corrupts state.\n"
                    f"        Run from the main repo root instead:\n"
                    f"          cd <repo-root>\n"
                    f"          uv run harness-maker make . --update\n"
                    f"        (cwd={cwd})\n"
                    f"        (CI/programmatic: set HARNESS_MAKER_BYPASS_WORKTREE_GUARD=1)",
                    err=True,
                )
                raise typer.Exit(code=1)
    existing_yaml = target / ".claude" / "harness.yaml"
    # Phase 9 (personalization-depth) — primary capture site for axis-level
    # overrides. Snapshot BEFORE any writes so the diff later picks up
    # changes from CLI overrides + interview + reconcile. Captured even
    # when /hm:configure dispatched without per-axis flags (e.g., domain
    # add): the synthesize step may still mutate the yaml.
    pre_yaml_body = _load_harness_yaml_body(existing_yaml)
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
    # ADR-012 deprecation: --recommended-model is a back-compat alias for
    # --default-model. Emit DeprecationWarning on use; new code should use
    # --default-model. Removal no earlier than 0.17.0.
    if recommended_model_override is not None:
        import warnings

        warnings.warn(
            "--recommended-model is renamed to --default-model. The old name "
            "will be removed no earlier than 0.17.0 (ADR-012, "
            "PLAN-model-routing-multi-ide).",
            DeprecationWarning,
            stacklevel=2,
        )
        if default_model_override is None:
            default_model_override = recommended_model_override
    a = _apply_dimension_overrides(
        a,
        preset_override=preset_override,
        locale_override=locale_override,
        dev_mode_override=dev_mode_override,
        targets_override=targets_override,
        grade_threshold_override=grade_threshold_override,
        domains_override=domains_override,
        mechanical_checks_override=mechanical_checks_override,
        recommended_model_override=default_model_override,
        focus_override=focus_override,
        wrapup_docs_override=wrapup_docs_override,
        ref_folders_override=ref_folders_override,
        sibling_repos_override=sibling_repos_override,
        second_brain_vault_path=second_brain_vault_path,
        second_brain_project_id=second_brain_project_id,
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
    # full_bp holds the unfiltered blueprint for orphan-sweep: KEEP'd files
    # are still expected on disk (the user owns them now), so we must NOT
    # let the post-reconcile mutation classify them as orphans.
    full_bp = bp
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
    # ADR-005 orphan sweep — delete blueprint-orphaned ours-clean files
    # (legacy commands removed by /hm:make --update). Uses full_bp (with
    # KEEP entries intact) so user-preserved files survive. Runs AFTER
    # render so the manifest is up-to-date for the classifier.
    sweep_report = sweep_orphans(target, full_bp)
    _emit_orphan_sweep_report(sweep_report)
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

    # Phase 9 — record axis-level overrides for Phase 10 audit. Failure
    # here MUST NOT block the install: telemetry is a best-effort
    # observability signal (ADR-005). Wrap broadly, swallow, log.
    try:
        _emit_configure_exit_overrides(target, pre_yaml_body)
    except Exception as e:  # noqa: BLE001 — diagnostic, never fail the make
        typer.echo(f"telemetry: override capture skipped ({e})", err=True)


@app.command("locate")
def locate_cmd(
    plain: bool = typer.Option(
        False,
        "--plain",
        help="Print installPath only (no JSON, no decoration).",
    ),
    require_version: str | None = typer.Option(
        None,
        "--require-version",
        help=">=X.Y constraint. Exit 2 if installed version is older.",
    ),
) -> None:
    """Resolve the active harness-maker plugin install for the current cwd.

    Single source of truth so external bootstrap scripts don't re-implement
    the resolver and pick the wrong version (see PLAN-locate-cli-version-gate).

    Exit codes: 0 found+ok, 2 version mismatch, 3 no install found.
    """
    entry = resolve_plugin(cwd=Path.cwd())
    if entry is None:
        typer.echo(
            "harness-maker: no installed plugin entry found "
            "(checked ~/.claude/plugins/installed_plugins.json). "
            "See docs/BOOTSTRAP.md for install instructions per IDE.",
            err=True,
        )
        raise typer.Exit(3)

    if require_version is not None:
        try:
            ok = compare_version(entry.version, require_version)
        except ValueError as e:
            typer.echo(f"harness-maker: --require-version invalid ({e})", err=True)
            raise typer.Exit(2) from None
        if not ok:
            typer.echo(
                f"harness-maker installed={entry.version} "
                f"(marketplace={entry.marketplace}) "
                f"required=>={require_version} — to update: "
                "`claude plugin update harness-maker` (Claude Code), "
                "`git -C <installPath> pull` (Cursor git clone), or "
                "`codex plugin update harness-maker` (Codex CLI)",
                err=True,
            )
            raise typer.Exit(2)

    if plain:
        typer.echo(str(entry.install_path))
        return

    payload: dict[str, Any] = {
        "marketplace": entry.marketplace,
        "version": entry.version,
        "scope": entry.scope,
        "installPath": str(entry.install_path),
        "gitCommitSha": entry.git_commit_sha,
        "installedAt": entry.installed_at,
    }
    if entry.project_path is not None:
        payload["projectPath"] = str(entry.project_path)
    typer.echo(json.dumps(payload, indent=2))


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
        typer.echo("  /hm:health               — check the 3-layer harness health")
        typer.echo("  /hm:configure            — adjust settings later")
        typer.echo("  /hm:make                 — re-render after plugin update")
    except Exception:  # noqa: BLE001 — diagnostic, never fail the make
        pass


def _load_harness_yaml_body(yaml_path: Path) -> dict[str, Any]:
    """Parse a harness.yaml file's body (strips frontmatter) into a dict.

    Returns an empty dict if the file does not exist, lacks a body, or
    fails to parse — Phase 9 telemetry must never be the reason a make
    blocks. Symmetric with ``_load_harness_yaml_body`` round-trips: we
    only diff structures both sides could plausibly produce.
    """
    if not yaml_path.is_file():
        return {}
    try:
        text = yaml_path.read_text(encoding="utf-8")
    except OSError:
        return {}
    body = text
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end != -1:
            body = text[end + len("\n---\n") :]
    try:
        parsed = yaml.safe_load(body)
    except yaml.YAMLError:
        return {}
    if isinstance(parsed, dict):
        return parsed
    return {}


def _telemetry_disabled(yaml_body: dict[str, Any]) -> bool:
    """Read ``adaptive.disable_telemetry`` from a parsed harness.yaml body.

    Defensive: any non-dict / non-bool shape → False (telemetry on) so we
    fail SAFE for the audit (better to record one extra noisy event than
    silently swallow legitimate signal). The pydantic AdaptiveConfig
    schema enforces the bool elsewhere; this helper just tolerates
    pre-Phase-1 yamls that may lack the block entirely.
    """
    adaptive = yaml_body.get("adaptive")
    if not isinstance(adaptive, dict):
        return False
    value = adaptive.get("disable_telemetry", False)
    return value is True


def _emit_configure_exit_overrides(
    target: Path,
    pre_yaml_body: dict[str, Any],
) -> None:
    """Diff pre-run vs post-run harness.yaml and emit one record per leaf change.

    Why post-make capture (not earlier interception): pre/post compare
    captures every mutation path — CLI flags, interview answers,
    domain-add, foreign-config import — without re-implementing each.
    The dedup key shared with SessionStart prevents double-record when
    a user commits the change and starts a new session right after.
    """
    yaml_path = target / ".claude" / "harness.yaml"
    post_yaml_body = _load_harness_yaml_body(yaml_path)
    # First install: no prior state to diff against (every key would
    # spuriously become a "configure-exit override" of None → value).
    # Capture starts on the second invocation, when /hm:configure is
    # actually doing what it's named for.
    if not pre_yaml_body:
        return
    disabled = _telemetry_disabled(post_yaml_body) or _telemetry_disabled(pre_yaml_body)
    ts = now_iso()
    records = compute_yaml_diff(
        pre_yaml_body,
        post_yaml_body,
        ts,
        source="configure-exit",
    )
    for record in records:
        emit_override(record, target, disable_telemetry=disabled)


def _write_harness_manifest(target_dotclaude: Path, written: list[Path]) -> None:
    """Write .harness-manifest.json listing all rendered file paths.

    Used by Phase 7 (uninstall) to identify frontmatter-less files like
    settings.json and hooks/hooks.json that lack generated_by markers.
    """
    import json

    from harness_maker import __version__

    project_root = target_dotclaude.parent.resolve()
    files: list[str] = []
    for path in written:
        try:
            files.append(path.resolve().relative_to(project_root).as_posix())
        except ValueError:
            files.append(path.as_posix())
    manifest = {
        "generated_by": "harness-maker",
        "version": __version__,
        "files": sorted(files),
    }
    manifest_path = target_dotclaude / ".harness-manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(manifest_path, json.dumps(manifest, indent=2) + "\n")


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
    typer.echo("Initial structural-health scan (LLM judge skipped — see hint below)")
    typer.echo("─" * 64)
    typer.echo(render_terminal_summary(plan, max_actions=5))
    typer.echo("\nNext steps:")
    typer.echo("  • Run /hm:health for the full 3-layer scan + unified dashboard.")
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
    ref_folders_override: str | None = None,
    sibling_repos_override: str | None = None,
    second_brain_vault_path: str | None = None,
    second_brain_project_id: str | None = None,
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
    if domains_override is not None:
        update["domains"] = [d.strip() for d in domains_override.split(",") if d.strip()]
    if mechanical_checks_override is not None:
        update["mechanical_checks"] = [
            c.strip() for c in mechanical_checks_override.split(";") if c.strip()
        ]
    if recommended_model_override:
        # Phase 3 mid-step: route the legacy CLI arg into the new canonical
        # field. Phase 5 formalizes the --recommended-model deprecation alias
        # to --default-model (ADR-012) with DeprecationWarning.
        # Phase 8 review security fix: model_copy(update=...) bypasses the
        # Pydantic field_validator on default_model — enforce the same safe
        # character set at the CLI boundary so injection payloads can't slip
        # through the kwarg path.
        from harness_maker.models import _MODEL_ID_PATTERN

        if not _MODEL_ID_PATTERN.fullmatch(recommended_model_override):
            typer.echo(
                f"[ERROR] --default-model / --recommended-model must match "
                f"[a-zA-Z0-9_.:-]+ (got {recommended_model_override!r})",
                err=True,
            )
            raise typer.Exit(code=1)
        update["default_model"] = recommended_model_override
    if wrapup_docs_override is not None:
        update["wrapup_docs"] = [d.strip() for d in wrapup_docs_override.split(";") if d.strip()]
    if ref_folders_override is not None:
        update["ref_folders"] = _parse_ref_folders_flag(ref_folders_override)
    if sibling_repos_override is not None:
        update["sibling_repos"] = [
            r.strip() for r in sibling_repos_override.split(";") if r.strip()
        ]
    if second_brain_vault_path is not None:
        from harness_maker.models import SecondBrainConfig  # noqa: PLC0415

        if second_brain_vault_path == "":
            update["second_brain"] = SecondBrainConfig()
        else:
            existing_id = answers.second_brain.project_id
            update["second_brain"] = SecondBrainConfig(
                enabled=True,
                vault_path=denormalize_home_to_tilde(second_brain_vault_path),
                project_id=(
                    second_brain_project_id if second_brain_project_id is not None else existing_id
                ),
            )
    elif second_brain_project_id is not None and answers.second_brain.enabled:
        from harness_maker.models import SecondBrainConfig  # noqa: PLC0415

        existing = answers.second_brain
        update["second_brain"] = SecondBrainConfig(
            enabled=existing.enabled,
            vault_path=existing.vault_path,
            project_id=second_brain_project_id,
            folders=list(existing.folders),
        )

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


def _parse_ref_folders_flag(raw: str) -> list[object]:
    """Parse --ref-folders value into a list of RefFolder dicts for model_copy.

    Format: '::'-separated entries, each entry is 'path[;glob]'.
    Example: '../docs::../specs;**/*.pdf'

    Absolute paths under $HOME are re-prefixed with ``~`` for portability
    across machines (see ``denormalize_home_to_tilde``).
    """
    from harness_maker.models import RefFolder

    out: list[object] = []
    for entry in raw.split("::"):
        entry = entry.strip()
        if not entry:
            continue
        path_part, _, glob_part = entry.partition(";")
        path_part = denormalize_home_to_tilde(path_part.strip())
        glob = glob_part.strip() or "**/*.{md,txt,pdf}"
        if path_part:
            out.append(RefFolder(path=path_part, glob=glob))
    return out


def _emit_orphan_sweep_report(report: OrphanSweepReport) -> None:
    """Surface what the orphan-sweep did so the user can audit deletions.

    Deleted paths are listed inline (typically a handful of legacy commands);
    kept-with-classification entries point to the date-stamped observability
    log for follow-up review.
    """
    if report.deleted:
        typer.echo(f"  SWEEP: {len(report.deleted)} orphan(s) deleted (ours-clean):")
        for p in report.deleted:
            typer.echo(f"    - {p.as_posix()}")
    if report.kept:
        typer.echo(
            f"  SWEEP: {len(report.kept)} orphan(s) kept "
            f"(see .claude/observability/orphans-*.jsonl)",
        )


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
        if report.orphan_outside_content:
            # Count + path + remediation only — never echo the dropped content
            # itself. The lines are user-controlled file fragments that may
            # contain secrets (API keys / tokens) or attacker-supplied prompt-
            # injection payloads; this string lands in Bash tool stdout and
            # therefore in the LLM's next-turn context. Open the file to see
            # what was dropped.
            bits.append(
                f"⚠ dropped {len(report.orphan_outside_content)} line(s) outside "
                f"@hm:user:* blocks — open the file, move content inside the "
                f"marker, re-run /hm:make --update",
            )
        if bits:
            typer.echo(f"  MERGE_BLOCK: {path} — {'; '.join(bits)}")


_HEALTH_TARGET = typer.Argument(
    Path("."),
    help="Project root (the directory containing .claude/).",
)


def _personalization_section_from_plan(plan: object) -> dict[str, Any]:
    """Map ``PersonalizationPlan`` → dashboard third-section dict (ADR-006).

    Centralised so the integration test can compare bytes built from the
    same helper against bytes written into dashboard.md. Lives here (not in
    ``personalization_audit``) because the module is intentionally
    UNCHANGED per ADR-006 hard rule — wiring belongs to the consumer.
    """
    from harness_maker.personalization_audit import PersonalizationPlan

    if not isinstance(plan, PersonalizationPlan):
        return {
            "composite": 0,
            "tier": "bronze",
            "layers": {},
            "action_items": [],
        }
    return {
        "composite": plan.composite_score,
        "tier": plan.tier,
        "layers": dict(plan.layer_scores),
        "action_items": [item.model_dump() for item in plan.actions],
    }


@app.command("health")
def health_cmd(
    target: Path = _HEALTH_TARGET,
    skip_llm: bool = typer.Option(
        False,
        "--skip-llm",
        help="Skip the optional LLM relevance scorer for external risks.",
    ),
    model: str = typer.Option(
        "claude-sonnet-4-6",
        "--model",
        help="Model hint for cache diagnostics threshold calculation.",
    ),
    update_dashboard: bool = typer.Option(
        True,
        "--update-dashboard/--no-update-dashboard",
        help="Write the rendered three-section dashboard.md.",
    ),
    json_output: Path | None = typer.Option(  # noqa: B008
        None,
        "--json-output",
        help=(
            "Write structural L1+L3 JSON to this path. Used by the slash "
            "command flow to feed Claude-native L2 evaluation; finalize "
            "with `harness-maker health-finalize`."
        ),
    ),
) -> None:
    """Run the three /hm:health layers and write the unified dashboard.

    Layer 1 — structural (ai_readiness L1+L3, /hm:health Step 1).
    Layer 2 — external risks (placeholder count until the LLM relevance
              orchestrator lands in Phase 2; the structured-question loop
              fills in items).
    Layer 3 — personalization (personalization_audit.run_audit, ADR-006
              rubric UNCHANGED).
    """
    from harness_maker.ai_readiness import run_structural
    from harness_maker.observability.dashboard import write_dashboard
    from harness_maker.personalization_audit import run_audit

    _ = skip_llm  # external-risk LLM scorer is wired in Phase 2 template work
    target = target.resolve()
    preset = _read_preset(target / ".claude" / "harness.yaml") or Preset.SIDE

    if json_output is not None:
        import json

        scores = {
            "structural": run_structural(target, preset=preset, model=model),
        }
        json_output.parent.mkdir(parents=True, exist_ok=True)
        json_output.write_text(json.dumps(scores, indent=2), encoding="utf-8")
        typer.echo(f"Structural scores written to {json_output}")
        typer.echo(
            "(Step 2 external risks + Step 3 personalization pending — run "
            "`harness-maker health-finalize` after Claude evaluates rubrics)",
        )
        return

    structural = run_structural(target, preset=preset, model=model)
    # External risks: Phase 1 emits an empty queue. The Phase 2 template
    # populates it via the crawler + relevance + stale-asset orchestration.
    external_risks: dict[str, Any] = {"pending": 0, "items": []}
    personalization_plan = run_audit(target)
    personalization = _personalization_section_from_plan(personalization_plan)

    typer.echo(
        f"health: structural={structural['score']}/100 "
        f"external_risks_pending={external_risks['pending']} "
        f"personalization={personalization['composite']}/100 "
        f"(tier: {personalization['tier']})",
    )

    if update_dashboard:
        dashboard_path = write_dashboard(
            target,
            structural,
            external_risks,
            personalization,
        )
        typer.echo(f"Dashboard updated: {dashboard_path}")


@app.command("health-finalize")
def health_finalize_cmd(
    target: Path = typer.Argument(  # noqa: B008
        default_factory=Path.cwd,
        help="Project root (the directory containing .claude/). Defaults to cwd.",
    ),
    scores_json: Path = typer.Option(  # noqa: B008
        ...,
        "--scores-json",
        help="Path to structural scores JSON written by `health --json-output`.",
    ),
    external_risks_json: Path | None = typer.Option(  # noqa: B008
        None,
        "--external-risks-json",
        help=(
            "Path to JSON with pending external-risk items "
            '({"pending": N, "items": [...]}). Optional; defaults to '
            "empty queue when omitted."
        ),
    ),
    update_dashboard: bool = typer.Option(
        True,
        "--update-dashboard/--no-update-dashboard",
        help="Write the rendered three-section dashboard.md.",
    ),
) -> None:
    """Combine pre-computed structural scores with Claude-provided external
    risk + personalization layers into the unified dashboard."""
    import json

    from harness_maker.observability.dashboard import write_dashboard
    from harness_maker.personalization_audit import run_audit

    target = target.resolve()
    try:
        scores = json.loads(scores_json.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        typer.echo(f"health-finalize: cannot read {scores_json}: {e}", err=True)
        raise typer.Exit(code=1) from e
    structural = scores.get("structural")
    if not isinstance(structural, dict):
        typer.echo(
            f"health-finalize: scores JSON missing 'structural' key in {scores_json}",
            err=True,
        )
        raise typer.Exit(code=1)

    external_risks: dict[str, Any] = {"pending": 0, "items": []}
    if external_risks_json is not None:
        try:
            payload = json.loads(external_risks_json.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            typer.echo(
                f"health-finalize: cannot read {external_risks_json}: {e}",
                err=True,
            )
            raise typer.Exit(code=1) from e
        if isinstance(payload, dict):
            external_risks = {
                "pending": payload.get("pending", 0),
                "items": payload.get("items", []),
            }

    personalization_plan = run_audit(target)
    personalization = _personalization_section_from_plan(personalization_plan)

    typer.echo(
        f"health-finalize: structural={structural.get('score', 0)}/100 "
        f"external_risks_pending={external_risks['pending']} "
        f"personalization={personalization['composite']}/100",
    )
    if update_dashboard:
        dashboard_path = write_dashboard(
            target,
            structural,
            external_risks,
            personalization,
        )
        typer.echo(f"Dashboard updated: {dashboard_path}")


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


def _read_harness_config(harness_yaml: Path) -> dict[str, object] | None:
    """Best-effort harness.yaml body extraction for commands that need policy."""
    if not harness_yaml.is_file():
        return None
    import yaml as _yaml

    try:
        text = harness_yaml.read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        for doc in _yaml.safe_load_all(text):
            if isinstance(doc, dict) and "generated_by" not in doc:
                return doc
    except _yaml.YAMLError:
        return None
    return None


@app.command("security-scan")
def security_scan_cmd(
    target: Path = typer.Argument(  # noqa: B008
        default_factory=Path.cwd,
        help="Project root to scan.",
    ),
) -> None:
    """Run the bundled security scanner and print a compact summary."""
    from collections import Counter

    from harness_maker.security_scanner import scan_all

    target = target.resolve()
    harness_config = _read_harness_config(target / ".claude" / "harness.yaml")
    findings = scan_all(target, harness_config=harness_config)
    by_severity = Counter(f.severity for f in findings)

    typer.echo(f"Security scan: {len(findings)} finding(s)")
    if by_severity:
        bits = [f"{severity}={count}" for severity, count in sorted(by_severity.items())]
        typer.echo("Severity: " + ", ".join(bits))
    for finding in findings[:20]:
        typer.echo(
            f"  {finding.severity} {finding.category} "
            f"{finding.file}:{finding.line} — {finding.evidence}",
        )
    if len(findings) > 20:
        typer.echo(f"  ... {len(findings) - 20} more")

    policy = "warn"
    if isinstance(harness_config, dict):
        security = harness_config.get("security")
        if isinstance(security, dict):
            on_finding = security.get("on_finding")
            if isinstance(on_finding, dict) and on_finding.get("high") == "block":
                policy = "block"
    if policy == "block" and any(f.severity in {"high", "P0"} for f in findings):
        raise typer.Exit(code=1)


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
    project_root = target.resolve()

    for rel in file_list:
        fpath = _resolve_manifest_file(target_dotclaude, rel)
        if fpath is None:
            skipped.append(rel)
            continue

        if fpath == (target_dotclaude / "harness.yaml").resolve() and not remove_yaml:
            continue

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
            _rmdir_if_empty(fpath.parent, stop=project_root)

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
    """Return True only when a user block contains real user content."""
    try:
        content = fpath.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False
    lines = content.splitlines()
    in_block = False
    block_has_content = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("<!-- @hm:user:"):
            in_block = True
            block_has_content = False
            continue
        if stripped.startswith("<!-- @hm:/user:"):
            if block_has_content:
                return True
            in_block = False
            block_has_content = False
            continue
        if in_block and stripped and not (stripped.startswith("<!--") and stripped.endswith("-->")):
            block_has_content = True
    return False


def _resolve_manifest_file(target_dotclaude: Path, rel: str) -> Path | None:
    """Resolve old and current manifest entries without escaping the project."""
    project_root = target_dotclaude.parent.resolve()
    raw = Path(rel)
    if raw.is_absolute():
        candidate = raw
    elif (raw.parts and raw.parts[0] in {".claude", ".cursor", ".codex", ".agents"}) or (
        raw.name in {"CLAUDE.md", "AGENTS.md"} and len(raw.parts) == 1
    ):
        candidate = project_root / raw
    else:
        # Backward compatibility with pre-0.9.5 manifests whose entries were
        # relative to .claude, e.g. "commands/hm/execute.md".
        candidate = target_dotclaude / raw
    try:
        resolved = candidate.resolve()
    except OSError:
        resolved = candidate.absolute()
    try:
        resolved.relative_to(project_root)
    except ValueError:
        return None
    return resolved


def _rmdir_if_empty(d: Path, *, stop: Path | None = None) -> None:
    """Remove empty directories up to the project root or .claude boundary."""
    stop = stop.resolve() if stop is not None else None
    try:
        while d.name and d.name != ".claude":
            if stop is not None and d.resolve() == stop:
                break
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


@app.command("verify")
def verify_stage_cmd(
    target: Path = typer.Argument(  # noqa: B008
        default_factory=Path.cwd,
        help="Project root (the directory containing .claude/). Defaults to cwd.",
    ),
    prior_dashboard: Path | None = typer.Option(  # noqa: B008
        None,
        "--prior-dashboard",
        help=(
            "Path to the prior dashboard.md snapshot (Check 3 baseline). "
            "When omitted, Check 3 emits a no-baseline PASS — the slash "
            "command should pre-stage the snapshot from the start of the "
            "work unit when a delta gate is wanted."
        ),
    ),
    pending: Path | None = typer.Option(  # noqa: B008
        None,
        "--pending",
        help=(
            "Override path to the external_risks pending JSONL. Defaults "
            "to <target>/.claude/observability/health/pending.jsonl."
        ),
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Treat FAIL as PASS for the exit code. --reason required.",
    ),
    reason: str | None = typer.Option(
        None,
        "--reason",
        help="Required when --force is set. Logged in the JSONL record.",
    ),
) -> None:
    """CI/automation wrapper for the verify stage.

    Runs the **machine-checkable subset** of the 6-check protocol — Check 3
    (structural delta) and Check 4 (external_risks pending). Checks 1, 2, 5,
    6 are prompt-driven and are emitted as ``SKIPPED`` records. ADR-002 /
    ADR-004 semantics: missing baseline = no-baseline PASS with an explicit
    ``reason`` field. ``personalization`` is intentionally never read here.

    The full 6-check protocol still lives in the verify-stage slash command
    template (templates/stages/verify.md.j2); this CLI is a thin wrapper for
    CI pipelines and the e2e harness.
    """
    from harness_maker.observability.dashboard import parse_dashboard

    target = target.resolve()
    dotclaude = target / ".claude"
    obs = dotclaude / "observability"
    current_dashboard = obs / "dashboard.md"

    # ── Check 3 ─────────────────────────────────────────────────────────
    check3 = _verify_structural_check(current_dashboard, prior_dashboard, parse_dashboard)

    # ── Check 4 ─────────────────────────────────────────────────────────
    pending_path = pending if pending is not None else obs / "health" / "pending.jsonl"
    check4 = _verify_external_risks_check(pending_path, current_dashboard, parse_dashboard)

    checks: list[dict[str, Any]] = [
        {"id": 1, "name": "plan_spec_satisfaction", "result": "SKIPPED"},
        {"id": 2, "name": "regression_smoke", "result": "SKIPPED"},
        check3,
        check4,
        {"id": 5, "name": "security_high", "result": "SKIPPED"},
        {"id": 6, "name": "worktree_merge", "result": "SKIPPED"},
    ]
    failing = [c for c in checks if c["result"] == "FAIL"]
    overall_fail = bool(failing)
    if overall_fail and force and not reason:
        typer.echo("--force requires --reason=<text>", err=True)
        raise typer.Exit(code=2)

    result = "FAIL" if overall_fail else "PASS"
    record = {
        "timestamp": _verify_timestamp(),
        "stage": "verify",
        "result": result,
        "checks": checks,
        "force_override": bool(force and overall_fail),
        "override_reason": reason if (force and overall_fail) else None,
    }
    _write_verify_jsonl(obs, record)
    _emit_verify_text(checks, result, force_override=bool(force and overall_fail), reason=reason)
    if overall_fail and not force:
        raise typer.Exit(code=1)


def _verify_timestamp() -> str:
    """Deterministic-friendly timestamp source for tests via env override."""
    from datetime import UTC, datetime  # noqa: PLC0415

    pinned = os.environ.get("HARNESS_MAKER_VERIFY_TIMESTAMP")
    if pinned:
        return pinned
    return datetime.now(UTC).isoformat()


def _verify_structural_check(
    current_path: Path,
    prior_path: Path | None,
    parser: Any,
) -> dict[str, Any]:
    """Compute Check 3 (structural delta) per ADR-002 / ADR-004."""
    current = parser(current_path) if current_path.is_file() else None
    prior = parser(prior_path) if (prior_path is not None and prior_path.is_file()) else None
    current_score = (
        current["structural"]["score"]
        if current is not None and isinstance(current["structural"]["score"], int)
        else None
    )
    prior_score = (
        prior["structural"]["score"]
        if prior is not None and isinstance(prior["structural"]["score"], int)
        else None
    )
    # No-baseline branches: either current OR prior missing/unparseable.
    if current is None:
        cause = (
            "dashboard.md missing"
            if not current_path.is_file()
            else "pre-0.13.0 schema or unparseable"
        )
        return {
            "id": 3,
            "name": "structural_delta",
            "result": "PASS",
            "delta": None,
            "prior": prior_score,
            "current": None,
            "reason": f"no-baseline: {cause}",
        }
    if prior_path is None:
        return {
            "id": 3,
            "name": "structural_delta",
            "result": "PASS",
            "delta": None,
            "prior": None,
            "current": current_score,
            "reason": "no-baseline: prior dashboard not provided",
        }
    if prior is None or prior_score is None:
        cause = (
            "prior dashboard.md missing"
            if not prior_path.is_file()
            else "prior pre-0.13.0 schema or unparseable"
        )
        return {
            "id": 3,
            "name": "structural_delta",
            "result": "PASS",
            "delta": None,
            "prior": None,
            "current": current_score,
            "reason": f"no-baseline: {cause}",
        }
    if current_score is None:
        return {
            "id": 3,
            "name": "structural_delta",
            "result": "PASS",
            "delta": None,
            "prior": prior_score,
            "current": None,
            "reason": "no-baseline: current structural score missing",
        }
    delta = current_score - prior_score
    return {
        "id": 3,
        "name": "structural_delta",
        "result": "FAIL" if delta < -5 else "PASS",
        "delta": delta,
        "prior": prior_score,
        "current": current_score,
        "reason": None,
    }


def _verify_external_risks_check(
    pending_path: Path,
    current_dashboard: Path,
    parser: Any,
) -> dict[str, Any]:
    """Compute Check 4 (external_risks) per ADR-002 / ADR-004.

    Source precedence:
      1. <obs>/health/pending.jsonl (one JSON record per line).
      2. <obs>/dashboard.md → ``## External risks`` items[].
    Missing both → no-baseline PASS.
    """
    items: list[dict[str, Any]] = []
    source_used: str | None = None
    if pending_path.is_file():
        source_used = "pending.jsonl"
        try:
            raw = pending_path.read_text(encoding="utf-8")
        except OSError:
            raw = ""
        for line in raw.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            try:
                rec = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            if isinstance(rec, dict):
                items.append(rec)
    elif current_dashboard.is_file():
        parsed = parser(current_dashboard)
        if parsed is not None:
            source_used = "dashboard.md"
            dashboard_items = parsed["external_risks"]["items"]
            if isinstance(dashboard_items, list):
                for it in dashboard_items:
                    if isinstance(it, dict):
                        items.append(it)
    if source_used is None:
        return {
            "id": 4,
            "name": "external_risks_pending",
            "result": "PASS",
            "blocking_items": 0,
            "items": [],
            "reason": "no-baseline: no pending.jsonl and no parseable dashboard.md",
        }
    blocking_categories = {"security", "breaking-change"}
    blockers: list[dict[str, Any]] = []
    for it in items:
        score = it.get("relevance_score")
        cat = it.get("category")
        if isinstance(score, (int, float)) and score >= 0.8 and cat in blocking_categories:
            blockers.append(it)
    if blockers:
        return {
            "id": 4,
            "name": "external_risks_pending",
            "result": "FAIL",
            "blocking_items": len(blockers),
            "items": [str(b.get("id", "")) for b in blockers],
            "reason": None,
        }
    return {
        "id": 4,
        "name": "external_risks_pending",
        "result": "PASS",
        "blocking_items": 0,
        "items": [],
        "reason": None,
    }


def _write_verify_jsonl(obs_dir: Path, record: dict[str, Any]) -> None:
    """Append the verify record to ``verify-<YYYY-MM-DD>.jsonl``.

    Atomic append per the io_utils contract — concurrent runs cannot
    interleave lines.
    """
    from datetime import UTC, datetime  # noqa: PLC0415

    from harness_maker.io_utils import atomic_append  # noqa: PLC0415

    pinned = os.environ.get("HARNESS_MAKER_VERIFY_TIMESTAMP")
    if pinned and "T" in pinned:
        # Best-effort date derivation from the pinned timestamp.
        date_str = pinned.split("T", 1)[0]
    else:
        date_str = datetime.now(UTC).date().isoformat()
    obs_dir.mkdir(parents=True, exist_ok=True)
    out_path = obs_dir / f"verify-{date_str}.jsonl"
    atomic_append(out_path, json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n")


def _emit_verify_text(
    checks: list[dict[str, Any]],
    result: str,
    *,
    force_override: bool,
    reason: str | None,
) -> None:
    """Human-readable verify summary on stdout."""
    typer.echo("=== /hm:verify ===\n")
    for c in checks:
        cid = c["id"]
        name = c["name"]
        outcome = c["result"]
        extra = ""
        if name == "structural_delta" and outcome != "SKIPPED":
            prior = c.get("prior")
            current = c.get("current")
            delta = c.get("delta")
            if delta is not None:
                extra = f"  (structural {prior} -> {current}, delta {delta:+d})"
            elif c.get("reason"):
                extra = f"  ({c['reason']})"
        elif name == "external_risks_pending" and outcome != "SKIPPED":
            blocking = c.get("blocking_items", 0)
            if outcome == "FAIL":
                extra = f"  ({blocking} blocking item(s): {', '.join(c.get('items', []))})"
            elif c.get("reason"):
                extra = f"  ({c['reason']})"
        typer.echo(f"[{cid}/6] {name:30s} {outcome}{extra}")
    typer.echo("")
    typer.echo(f"RESULT: {result}")
    if force_override:
        typer.echo(f"FORCE OVERRIDE: --reason={reason!r}")


verify_stage = verify_stage_cmd


@app.command("configure-second-brain")
def configure_second_brain_cmd(
    target: Path = typer.Argument(  # noqa: B008
        default_factory=Path.cwd,
        help="Target project directory (defaults to cwd)",
    ),
    check: bool = typer.Option(
        False,
        "--check",
        help="Emit JSON state guidance for the slash command to render.",
    ),
    add_folder: str | None = typer.Option(
        None,
        "--add-folder",
        help=(
            "Add a writable Second Brain folder entry to harness.yaml. Path is "
            "vault-relative and must contain project_id (see ADR-004)."
        ),
    ),
) -> None:
    """Inspect or extend Second Brain configuration (ADR-003 dispatch surface).

    The slash command ``/hm:configure`` calls this subcommand with ``--check``
    to inspect state, then dispatches user intent through ``--add-folder`` on
    a second invocation. Pure stdin/stdout — no AskUserQuestion (slash command
    owns the user interaction; this command only manipulates files).
    """
    from harness_maker.io_utils import load_harness_yaml
    from harness_maker.models import SecondBrainConfig, SecondBrainFolder

    yaml_path = target / ".claude" / "harness.yaml"
    if not yaml_path.exists():
        typer.echo(
            json.dumps({"error": f"no harness.yaml at {yaml_path}"}),
            err=True,
        )
        raise typer.Exit(code=2)
    raw = load_harness_yaml(yaml_path)
    sb_block: dict[str, Any] = raw.get("second_brain") or {}
    try:
        cfg = SecondBrainConfig.model_validate(sb_block)
    except Exception as exc:  # noqa: BLE001 — surface YAML validation issues
        typer.echo(json.dumps({"error": f"invalid second_brain block: {exc}"}), err=True)
        raise typer.Exit(code=2) from exc

    if check:
        default_suggestion = f"99_HM/{cfg.project_id}" if cfg.project_id else ""
        guidance = {
            "enabled": cfg.enabled,
            "vault_path": cfg.vault_path,
            "project_id": cfg.project_id,
            "folders_empty": len(cfg.folders) == 0,
            "folder_count": len(cfg.folders),
            "default_suggestion": default_suggestion,
        }
        typer.echo(json.dumps(guidance))
        return

    if add_folder is not None:
        cleaned = add_folder.strip()
        if not cleaned:
            typer.echo(json.dumps({"error": "--add-folder requires a path"}), err=True)
            raise typer.Exit(code=2)
        existing_folders = sb_block.get("folders", []) or []
        if any(isinstance(f, dict) and f.get("path") == cleaned for f in existing_folders):
            typer.echo(json.dumps({"already_present": cleaned, "folder_count": len(cfg.folders)}))
            return
        new_folder = SecondBrainFolder(path=cleaned, read=True, write=True)
        merged_folders = [*existing_folders, new_folder.model_dump(mode="json")]
        updated = SecondBrainConfig.model_validate({**sb_block, "folders": merged_folders})
        new_body_yaml = yaml.safe_dump(
            {**raw, "second_brain": updated.model_dump(mode="json")},
            sort_keys=False,
            allow_unicode=True,
        )
        # Preserve the provenance frontmatter shape while recomputing content_hash
        # — otherwise the reconciler sees a stale hash and treats harness.yaml as
        # user-modified, blocking future re-renders (REVIEW-2026-05-17 finding).
        text = yaml_path.read_text(encoding="utf-8")
        frontmatter_block = ""
        if text.startswith("---\n"):
            end = text.find("\n---\n", 4)
            if end != -1:
                raw_fm_text = text[len("---\n") : end]
                fm_data = yaml.safe_load(raw_fm_text) or {}
                if isinstance(fm_data, dict):
                    fm_data["content_hash"] = hashlib.sha256(
                        new_body_yaml.encode("utf-8")
                    ).hexdigest()
                    frontmatter_block = (
                        "---\n"
                        + yaml.safe_dump(
                            fm_data,
                            sort_keys=False,
                            allow_unicode=True,
                            default_flow_style=False,
                        )
                        + "---\n"
                    )
                else:
                    frontmatter_block = text[: end + len("\n---\n")]
        atomic_write(yaml_path, frontmatter_block + new_body_yaml)
        typer.echo(json.dumps({"added": cleaned, "folder_count": len(updated.folders)}))
        return

    typer.echo(
        json.dumps({"error": "pass --check or --add-folder"}),
        err=True,
    )
    raise typer.Exit(code=2)


@app.command(hidden=True)
def _version() -> None:
    """Print version (hidden command, forces multi-command mode)."""
    from harness_maker import __version__

    typer.echo(__version__)


# Module-level aliases for the 0.13.0 surface check
# (``'health' in dir(harness_maker.cli)``). The typer-registered names
# are kebab-case ("health" / "health-finalize"); exposing snake-case
# module attributes lets external tools introspect the surface without
# poking at typer internals.
health = health_cmd
health_finalize = health_finalize_cmd


def main() -> None:
    """Run the typer app."""
    app()


if __name__ == "__main__":
    main()
