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

import json
import math
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from harness_maker.models import AdaptiveConfig
from harness_maker.relevance import detect_version_drift
from harness_maker.telemetry import (
    compute_yaml_diff,
    emit_override,
    load_overrides,
    now_iso,
)


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
        "Run /hm:personalization-audit to review."
    )
    system = (
        f"harness-maker: {n_overrides} personalization axis overrides queued. "
        "/hm:personalization-audit to review."
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
    if drift is not None:
        additional_parts.append(_format_context(drift.stamped, drift.current, drift.direction))
    if hint is not None:
        additional, system = hint
        additional_parts.append(additional)
        hook_output["systemMessage"] = system
    hook_output["additionalContext"] = "\n\n".join(additional_parts)

    payload = {"hookSpecificOutput": hook_output}
    sys.stdout.write(json.dumps(payload))
    return 0


def main() -> int:
    return run()


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
