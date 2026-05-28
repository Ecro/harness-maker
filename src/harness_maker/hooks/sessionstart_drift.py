"""SessionStart drift hook — surface stale-harness reminder via Claude.

Why: `/plugin update` refreshes the plugin's own commands/CLI but does NOT
re-render the user's `.claude/` (templates were rendered at the previous
harness-maker version). Users routinely forget to run `/hm:make` after a
plugin bump, so the rendered harness drifts behind the running plugin code.

This hook fires on SessionStart, reads the project's
`.claude/harness.yaml`, and if its stamped `harness_maker_version`
differs from the running plugin's `__version__`, emits a one-line
reminder via the SessionStart `additionalContext` channel. Silent
when no harness exists or no drift detected.

User-visibility note: Claude Code's SessionStart hook has NO user-visible
output field — both ``additionalContext`` and ``systemMessage`` feed
Claude's context only (per official docs at code.claude.com/docs/en/hooks,
2026-05-13 verification). The earlier 0.11.3 attempt to split into a
"user-facing systemMessage" was based on a misreading of the spec.
Instead, the context message is now phrased as an explicit instruction to
Claude to surface the drift to the user in its first response — that's
the only mechanism that actually reaches the user through this hook.

Phase 9 (personalization-depth) addition: as the secondary capture site for
harness.yaml axis overrides (validator W8), this hook also inspects
``git log -p`` on ``.claude/harness.yaml`` since the last recorded
override timestamp and emits ``OverrideRecord`` events with
``source="session-start"``. Dedup with the primary /hm:configure-exit
capture site is via the (ts + axis_path + after) key. Network-free per
ADR-005 — only invokes local ``git`` via subprocess.
"""

from __future__ import annotations

import functools
import json
import math
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import yaml

from harness_maker.models import AdaptiveConfig
from harness_maker.telemetry import (
    compute_yaml_diff,
    emit_override,
    load_overrides,
    now_iso,
)

# ──────────────────────────────────────────────────────────────────────────────
# Version-drift detection — self-contained in this hook (the original
# ``harness_maker.relevance`` module that previously housed related helpers
# was removed in 0.22.3 per ADR-0007 alongside the external_risks layer).
# ──────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class VersionDrift:
    """Mismatch between a project's stamped harness_maker_version and the
    latest-installed harness-maker package. Direction is from the project's
    perspective: ``upgrade`` = newer package available, ``downgrade`` = package
    is older than what stamped the project (rare, usually a rollback).

    Field naming (REVIEW M2, 2026-05-08): ``stamped`` is the version baked
    into ``harness.yaml`` at last render; ``current`` is the latest plugin
    cached on disk. Older codebases used ``installed`` for the stamped value,
    which read as the opposite semantic to most readers.
    """

    stamped: str  # the version stamped in harness.yaml frontmatter
    current: str  # newest available = max(running __version__, highest cached)
    direction: Literal["upgrade", "downgrade"]


_CACHE_TOPK = 10
"""Cap _scan_plugin_cache_versions to the top-K most recent semver-parseable
entries to bound worst-case scan cost on long-lived installs where every
``/plugin update`` adds a directory and Claude Code does not prune them
(REVIEW M9, 2026-05-08)."""


def _parse_semver(v: str) -> tuple[int, int, int] | None:
    parts = v.split(".")
    if len(parts) != 3:
        return None
    try:
        return (int(parts[0]), int(parts[1]), int(parts[2]))
    except ValueError:
        return None


def _scan_plugin_cache_versions() -> list[str]:
    """Return up to ``_CACHE_TOPK`` highest-semver harness-maker versions cached
    under any marketplace at ``~/.claude/plugins/cache/<marketplace>/harness-maker/``.

    Why glob every marketplace: the cache is keyed by the *marketplace name*
    the user registered the plugin under — ``harness-maker`` for the published
    marketplace, ``harness-maker-local`` for a local dev checkout, etc. A
    previous version hardcoded the ``harness-maker-local`` name and so read a
    stale sibling marketplace whose newest cached build (0.26.4) was older than
    the active install (0.26.7), reporting a phantom "downgrade". Scanning every
    marketplace dir that holds a ``harness-maker/`` plugin subtree fixes this
    regardless of the registration name.
    """
    cache_root = Path.home() / ".claude" / "plugins" / "cache"
    names: set[str] = set()
    try:
        if not cache_root.is_dir():
            return []
        for marketplace in cache_root.iterdir():
            plugin_dir = marketplace / "harness-maker"
            try:
                if not plugin_dir.is_dir():
                    continue
                names.update(d.name for d in plugin_dir.iterdir() if d.is_dir())
            except OSError:
                continue
    except OSError:
        return []
    parsed = [(_parse_semver(n), n) for n in names]
    parsed.sort(key=lambda x: (x[0] is not None, x[0] or (0, 0, 0)), reverse=True)
    return [name for _p, name in parsed[:_CACHE_TOPK]]


@functools.cache
def latest_installed_version() -> str:
    """Resolve the newest harness-maker version available to this session.

    Defined as the maximum (by semver) of the running plugin code's
    ``__version__`` and every version cached on disk across all marketplaces.
    The running version is a *floor*: "latest available" can never be older
    than the code executing this hook. Without that floor, a session running a
    source/editable build ahead of the published marketplace cache (the common
    case in the harness-maker dev repo itself) would report a phantom
    "downgrade" against a freshly-rendered harness. Memoized for the process
    lifetime of the hook (cheap-startup rule, validator C3).
    """
    from harness_maker import __version__

    pairs: list[tuple[tuple[int, int, int], str]] = []
    running = _parse_semver(__version__)
    if running is not None:
        pairs.append((running, __version__))
    for raw in _scan_plugin_cache_versions():
        parsed = _parse_semver(raw)
        if parsed is not None:
            pairs.append((parsed, raw))
    if not pairs:
        return __version__
    pairs.sort(key=lambda x: x[0], reverse=True)
    return pairs[0][1]


def _drift_direction(stamped: str, current: str) -> Literal["upgrade", "downgrade"]:
    """Semver-aware comparison with lexical fallback for unparseable tags."""
    pa = _parse_semver(stamped)
    pb = _parse_semver(current)
    if pa is not None and pb is not None:
        return "upgrade" if pa < pb else "downgrade"
    return "upgrade" if stamped < current else "downgrade"


def detect_version_drift(project_dir: Path) -> VersionDrift | None:
    """Return drift info or None when no drift / harness.yaml unreadable.

    Reads ``<project_dir>/.claude/harness.yaml`` frontmatter for
    ``harness_maker_version`` and compares against
    ``latest_installed_version()``. Missing file, missing frontmatter,
    missing key, or matching versions all return None.
    """
    harness_yaml = project_dir / ".claude" / "harness.yaml"
    if not harness_yaml.exists():
        return None
    try:
        text = harness_yaml.read_text(encoding="utf-8")
    except OSError:
        return None
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---\n", 4)
    if end == -1:
        return None
    try:
        fm = yaml.safe_load(text[4:end])
    except yaml.YAMLError:
        return None
    if not isinstance(fm, dict):
        return None
    stamped = fm.get("harness_maker_version")
    if not isinstance(stamped, str) or not stamped:
        return None
    current = latest_installed_version()
    if stamped == current:
        return None
    direction = _drift_direction(stamped, current)
    return VersionDrift(stamped=stamped, current=current, direction=direction)


def _format_context(stamped: str, current: str, direction: str) -> str:
    """Imperative instruction so Claude surfaces the drift to the user.

    ``additionalContext`` is consumed by the model, not displayed to the user.
    The only way a user sees the drift notice is if Claude *chooses* to mention
    it. Descriptive prose ("drift detected: ...") was too easy to ignore.
    Imperative framing ("Tell the user...") raises surface-rate to near 100%.
    """
    if direction == "upgrade":
        return (
            "[harness-maker drift — TELL THE USER NOW, before answering anything else] "
            f"The project's `.claude/` was rendered with harness-maker {stamped}, "
            f"but the installed plugin is now {current}. Tell the user in your next "
            "response that they should run `/hm:make --update` for a silent re-render, "
            "or `/harness-maker:make` for a full interactive run. Surface this at "
            "the top of your reply; do not bury it after other content."
        )
    return (
        "[harness-maker drift — TELL THE USER NOW, before answering anything else] "
        f"The project's `.claude/` was rendered with harness-maker {stamped}, "
        f"but the installed plugin is now {current} — a downgrade (plugin older "
        "than the stamped version). Tell the user in your next response to verify "
        "intent before running `/harness-maker:make`; this is unusual and may "
        "indicate an accidental rollback."
    )


def _parse_yaml_body(text: str) -> dict[str, Any]:
    """Strip frontmatter then yaml-parse — mirror of cli._load_harness_yaml_body.

    Duplicated (not imported) on purpose: the hook runs as a standalone
    Python process from a Claude Code hook context and must not pull in
    typer / pydantic-heavy modules. Keeping the parser local keeps hook
    startup cheap and import-safe under sandboxed permissions.
    """
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
    """Honour the ``adaptive.disable_telemetry`` opt-out (ADR-005)."""
    adaptive = yaml_body.get("adaptive")
    if not isinstance(adaptive, dict):
        return False
    return adaptive.get("disable_telemetry", False) is True


def _git_show(cwd: Path, rev: str, path: str) -> str | None:
    """Return file content at ``rev`` via ``git show``, or None on any failure.

    Why subprocess + timeout: this runs on every session start; a wedged
    git invocation (network-backed reference resolution in a malformed
    repo, locked index, etc.) would block the user's terminal startup.
    Three seconds is generous for a local-only ``git show``; anything
    slower implies a problem and we silently fall back to no capture.
    """
    try:
        proc = subprocess.run(  # noqa: S603 — fixed argv, no shell
            ["git", "-C", str(cwd), "show", f"{rev}:{path}"],
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout


def _git_last_commit_touching(cwd: Path, path: str, *, since_iso: str | None) -> str | None:
    """SHA of the most recent commit that touched ``path``.

    ``since_iso`` is an inclusive lower bound — passed to ``git log
    --since`` so we don't re-walk history we've already processed. None
    return means "no eligible commit" (either no history, the file was
    never touched, or git is unavailable). The capture-site loop treats
    None as a no-op.
    """
    argv = ["git", "-C", str(cwd), "log", "-1", "--format=%H"]
    if since_iso:
        argv.extend(["--since", since_iso])
    argv.extend(["--", path])
    try:
        proc = subprocess.run(  # noqa: S603
            argv,
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    sha = proc.stdout.strip()
    return sha or None


def _capture_yaml_overrides(cwd: Path) -> None:
    """Secondary capture path: detect harness.yaml edits committed outside
    /hm:configure (validator W8 — no fixed HEAD~N window).

    Strategy:
      1. Find the timestamp of the most recently recorded override in
         the local jsonl. Use it as the ``git log --since`` bound so we
         only re-process new history (per-session pre-Phase 10 ≪ 100ms).
      2. Pick the most recent commit that actually modifies
         ``.claude/harness.yaml`` after that point.
      3. Compare the file at that commit vs the parent commit. Emit one
         OverrideRecord per leaf change with ``source="session-start"``.
      4. Dedup via ``emit_override`` so a record already captured by the
         /hm:configure-exit primary path is skipped.

    Everything is best-effort: any subprocess / parse failure is
    swallowed. The hook MUST NEVER block session start (validator C3
    rollback discipline).
    """
    yaml_path = cwd / ".claude" / "harness.yaml"
    if not yaml_path.is_file():
        return
    try:
        current_text = yaml_path.read_text(encoding="utf-8")
    except OSError:
        return
    current_yaml = _parse_yaml_body(current_text)
    if _telemetry_disabled(current_yaml):
        return
    existing = load_overrides(cwd)
    since_iso = max((r.ts for r in existing), default=None)
    sha = _git_last_commit_touching(cwd, ".claude/harness.yaml", since_iso=since_iso)
    if sha is None:
        return
    before_text = _git_show(cwd, f"{sha}^", ".claude/harness.yaml")
    after_text = _git_show(cwd, sha, ".claude/harness.yaml")
    # If we can't read both sides (e.g. initial commit with no parent),
    # bail — diffing against {} would spuriously flood the jsonl with
    # "session-start override: every-key None → value" records.
    if before_text is None or after_text is None:
        return
    before_yaml = _parse_yaml_body(before_text)
    after_yaml = _parse_yaml_body(after_text)
    if not before_yaml:
        return
    ts = now_iso()
    records = compute_yaml_diff(
        before_yaml,
        after_yaml,
        ts,
        source="session-start",
    )
    for record in records:
        emit_override(record, cwd, disable_telemetry=False)


def _load_adaptive_config(cwd: Path) -> AdaptiveConfig | None:
    """Reconstruct AdaptiveConfig from harness.yaml; None when unavailable.

    Why a hook-local loader (not personalization_audit._read_adaptive_config):
    importing personalization_audit drags in pydantic + render-side modules.
    This hook runs on every session start; cheap-startup is the rule
    (validator C3 rollback discipline). The frontmatter-stripping parser
    already lives here as ``_parse_yaml_body``.
    """
    yaml_path = cwd / ".claude" / "harness.yaml"
    if not yaml_path.is_file():
        return None
    try:
        text = yaml_path.read_text(encoding="utf-8")
    except OSError:
        return None
    body = _parse_yaml_body(text)
    raw = body.get("adaptive")
    if not isinstance(raw, dict):
        # No adaptive block → use defaults so thresholds still apply.
        return AdaptiveConfig()
    try:
        return AdaptiveConfig.model_validate(raw)
    except (ValueError, TypeError):
        return AdaptiveConfig()


def _read_last_audit_iso(cwd: Path) -> datetime | None:
    """Parse the Phase 10 last-audit marker. Missing/unparseable → None
    (treated by the caller as "never audited", i.e. days_since = +inf)."""
    path = cwd / ".claude" / "observability" / "adaptive" / "last-audit.txt"
    if not path.is_file():
        return None
    try:
        text = path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    try:
        ts = datetime.fromisoformat(text)
    except (TypeError, ValueError):
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=UTC)
    return ts


def _personalization_hint(cwd: Path) -> tuple[str, str] | None:
    """Compute (additionalContext, systemMessage) when an audit is due.

    Returns ``None`` when no hint should fire — telemetry opt-out, missing
    config, neither threshold exceeded. Wiki [[sessionstart-systemmessage-required]]
    requires both fields populated for a user-visible banner; we emit them
    in lockstep so a future refactor cannot drop one silently.
    """
    config = _load_adaptive_config(cwd)
    if config is None:
        return None
    if config.disable_telemetry:
        # ADR-005: opt-out is absolute — no hint, no banner.
        return None
    overrides = load_overrides(cwd)
    n_overrides = len(overrides)
    last_audit = _read_last_audit_iso(cwd)
    if last_audit is None:
        days_since = math.inf
    else:
        days_since = (datetime.now(UTC) - last_audit).total_seconds() / 86400.0
    over_count = n_overrides >= config.audit_session_threshold
    over_days = days_since >= config.audit_days_threshold
    if not (over_count or over_days):
        return None
    additional = (
        f"personalization-audit recommended: {n_overrides} axis overrides recorded "
        f"since last audit (threshold {config.audit_session_threshold}). "
        "Run /hm:health (Step 3 Personalization) to review."
    )
    system = (
        f"harness-maker: {n_overrides} personalization axis overrides queued. "
        "Run /hm:health (Step 3 Personalization) to review."
    )
    return additional, system


def run(cwd: Path | None = None) -> int:
    if cwd is None:
        cwd = Path.cwd()

    # Phase 9 secondary capture — runs before the drift check so it
    # records overrides even on sessions where versions match. Wrapped
    # broadly: a capture failure must never starve the drift notice.
    import contextlib

    with contextlib.suppress(Exception):
        _capture_yaml_overrides(cwd)

    # Phase 11 — personalization audit hint. Computed independently of
    # drift so a same-version session still surfaces the banner when
    # thresholds fire. Suppression is best-effort like the capture above:
    # a load failure must never starve the drift notice.
    hint: tuple[str, str] | None = None
    with contextlib.suppress(Exception):
        hint = _personalization_hint(cwd)

    drift = detect_version_drift(cwd)

    if drift is None and hint is None:
        return 0

    hook_output: dict[str, Any] = {"hookEventName": "SessionStart"}
    additional_parts: list[str] = []
    payload: dict[str, Any] = {}
    if drift is not None:
        additional_parts.append(_format_context(drift.stamped, drift.current, drift.direction))
    if hint is not None:
        additional, system = hint
        additional_parts.append(additional)
        # systemMessage lives at the TOP level of the payload (universal hook
        # output field), NOT inside hookSpecificOutput. Codex's wire schema
        # has deny_unknown_fields on SessionStartHookSpecificOutputWire and
        # only permits {hookEventName, additionalContext} there; nesting
        # systemMessage made every Codex SessionStart fail with "hook
        # returned invalid session start JSON output". Claude Code's
        # official schema also documents systemMessage as a top-level
        # universal field — older code that nested it was tolerated only
        # because Claude Code silently ignored the extra key.
        payload["systemMessage"] = system
    hook_output["additionalContext"] = "\n\n".join(additional_parts)

    payload["hookSpecificOutput"] = hook_output
    sys.stdout.write(json.dumps(payload))
    return 0


def main() -> int:
    return run()


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
