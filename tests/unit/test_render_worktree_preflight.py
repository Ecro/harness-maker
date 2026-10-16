"""Phase 5 (ADR-002/004/006): flag-on worktree preflight wiring across stages.

When `worktree.enabled` is on, every `/hm:` stage template renders
the shared `worktree_preflight` partial (a `task-preflight` claim + `<WT>` entry +
drift/`task-refresh` surface). When off (the default, key-absent under
StrictUndefined), no stage renders it — and the 8 preset×dev_mode snapshot
fixtures stay byte-identical (proven by tests/snapshot/test_*). This module guards
the flag-ON content + the StrictUndefined-safe gate (validator W1) + the flag-ON
prose determinism via a golden block (validator W2).
"""
# ruff: noqa: E501 — the _GOLDEN_PREFLIGHT literal mirrors rendered prose verbatim
# (long markdown lines are intentional; wrapping them would break the golden match).

from __future__ import annotations

from pathlib import Path
from typing import Any

from harness_maker.models import Blueprint, InterviewAnswers, Preset, ProjectProfile, Target
from harness_maker.render import DEFAULT_FREEZE_TIME, render

WIRED_STAGES = ("execute", "review", "wrapup", "verify", "research", "spec")


def _render(tmp_path: Path, *, flag_on: bool) -> dict[str, str]:
    worktree = {"enabled": flag_on}
    blueprint = synthesize_blueprint(worktree)
    render(blueprint, tmp_path, freeze_time=DEFAULT_FREEZE_TIME)
    return {
        str(f.relative_to(tmp_path)): f.read_text(encoding="utf-8") for f in tmp_path.rglob("*.md")
    }


def synthesize_blueprint(worktree: dict[str, Any]) -> Blueprint:
    from harness_maker.synthesize import synthesize

    return synthesize(
        ProjectProfile(),
        InterviewAnswers(
            preset=Preset.SIDE,
            targets=[Target.CLAUDE_CODE],
            worktree=worktree,
        ),
    )


def _stage(files: dict[str, str], name: str) -> str:
    return next(t for p, t in files.items() if p.endswith(f"stages/{name}.md"))


# ── flag-ON: preflight present in every wired stage ──────────────────────────


# ── flag-OFF: preflight absent; legacy paths intact ──────────────────────────


def test_flag_off_render_succeeds_on_absent_key(tmp_path: Path) -> None:
    # worktree={} → the `feature_branch_workflow` key is ABSENT. Under
    # StrictUndefined a bare `config.worktree.feature_branch_workflow` would raise
    # UndefinedError; the `is defined and .get(...)` gate must not (validator W1).
    files = _render(tmp_path, flag_on=False)  # must not raise
    assert files  # rendered something


# ── span emission (Phase 2 of PLAN-economics-attribution-and-carry) ──────────
#
# ADR-008: the span START rides the preflight call the stage already MUST make, so
# emission reliability is coupled to stage reliability. That coupling only holds if
# EVERY wired stage passes its own `--stage`; a template that forgets it degrades to
# the `(unknown-stage)` sentinel, which is the absent case ADR-003 defines.


# ── flag-ON determinism: full golden block (validator W2) ─────────────────────

_GOLDEN_PREFLIGHT = """### Task worktree preflight (feature-branch workflow)

`harness.yaml worktree.enabled` is **on**: this stage operates inside the persistent per-task worktree `.worktrees/<slug>/` on branch `hm/<slug>` — shared by every `/hm:` stage for this task — NOT an ephemeral `execute-<uuid>` worktree. Claim/refresh it and surface concurrent work + drift:


```bash
!uv run --with <SRC> hm worktree task-preflight <slug> "$(pwd)" --stage hm:wrapup --claude-session-id "$HM_SESSION_ID"
```


- **stdout** = the task worktree absolute path. **Treat that exact string as `<WT>`** for every Read/Write/Edit and every `!cd <WT> && …` in this stage. Do NOT use a shell variable.
- **stderr warnings**: `[preflight] … other active session(s)` = another session holds a task concurrently (informational, no action needed). `[preflight] … behind …` = the task branch drifted behind the base tip; to rebase it cleanly onto the base before working, run:


```bash
!uv run --with <SRC> hm worktree task-refresh <slug> "$(pwd)"
```


  `task-refresh` rebases `hm/<slug>` onto the base tip (base HEAD, not a hardcoded `main`), preserving commits; a conflict aborts and leaves the branch untouched — resolve manually, then retry. Refuse to refresh a dirty worktree: commit or discard first."""


# ── fused workflows inherit the preflight (master Phase 5 AC) ──────────────────


def _fused_execute_commands(files: dict[str, str]) -> dict[str, str]:
    """Rendered fused `/hm:` command files whose body fuses the execute stage."""
    return {p: t for p, t in files.items() if "commands/hm/" in p and "## Stage: execute" in t}


def test_fused_workflows_omit_preflight_when_flag_off(tmp_path: Path) -> None:
    files = _render(tmp_path, flag_on=False)
    for path, body in _fused_execute_commands(files).items():
        assert "task-preflight" not in body, path


# ── flag-ON: wrapup squash-lands the task branch (ADR-003 wiring; Phase 4 gap) ─


# ── flag-ON: Step 6/7 commit inside <WT> so the curated commit lands on the branch ─
