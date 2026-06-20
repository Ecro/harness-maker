"""Phase 5 (ADR-002/004/006): flag-on worktree preflight wiring across stages.

When `worktree.feature_branch_workflow` is on, every `/hm:` stage template renders
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

from harness_maker import synthesize as _synth
from harness_maker.models import InterviewAnswers, Preset, ProjectProfile, Target
from harness_maker.render import DEFAULT_FREEZE_TIME, render

WIRED_STAGES = ("execute", "plan", "review", "wrapup", "verify", "research", "spec")


def _render(tmp_path: Path, *, flag_on: bool) -> dict[str, str]:
    worktree = {"feature_branch_workflow": True} if flag_on else {}
    blueprint = synthesize_blueprint(worktree)
    render(blueprint, tmp_path, freeze_time=DEFAULT_FREEZE_TIME)
    return {
        str(f.relative_to(tmp_path)): f.read_text(encoding="utf-8") for f in tmp_path.rglob("*.md")
    }


def synthesize_blueprint(worktree: dict[str, object]) -> object:
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


def test_preflight_present_in_all_stages_when_flag_on(tmp_path: Path) -> None:
    files = _render(tmp_path, flag_on=True)
    for stage in WIRED_STAGES:
        body = _stage(files, stage)
        assert "Task worktree preflight" in body, stage
        assert "worktree task-preflight <slug>" in body, stage
        assert "worktree task-refresh <slug>" in body, stage
        assert "<WT>" in body, stage


# ── flag-OFF: preflight absent; legacy paths intact ──────────────────────────


def test_preflight_absent_in_all_stages_when_flag_off(tmp_path: Path) -> None:
    files = _render(tmp_path, flag_on=False)
    for stage in WIRED_STAGES:
        body = _stage(files, stage)
        assert "Task worktree preflight" not in body, stage
        assert "task-preflight" not in body, stage


def test_flag_off_render_succeeds_on_absent_key(tmp_path: Path) -> None:
    # worktree={} → the `feature_branch_workflow` key is ABSENT. Under
    # StrictUndefined a bare `config.worktree.feature_branch_workflow` would raise
    # UndefinedError; the `is defined and .get(...)` gate must not (validator W1).
    files = _render(tmp_path, flag_on=False)  # must not raise
    assert files  # rendered something


# ── execute dual-path: flag flips ephemeral isolation ↔ task preflight ────────


def test_execute_dualpath_flag_on_uses_preflight(tmp_path: Path) -> None:
    files = _render(tmp_path, flag_on=True)
    body = _stage(files, "execute")
    assert "worktree task-preflight <slug>" in body
    # the legacy ephemeral-isolation command is replaced when the flag is on
    assert "worktree create execute" not in body


def test_execute_dualpath_flag_off_uses_legacy_isolation(tmp_path: Path) -> None:
    files = _render(tmp_path, flag_on=False)
    body = _stage(files, "execute")
    assert "Step 0 — Worktree isolation" in body
    assert "worktree create execute" in body
    assert "task-preflight" not in body


# ── flag-ON determinism: full golden block (validator W2) ─────────────────────

_GOLDEN_PREFLIGHT = """### Task worktree preflight (feature-branch workflow)

`harness.yaml worktree.feature_branch_workflow` is **on**: this stage operates inside the persistent per-task worktree `.worktrees/<slug>/` on branch `hm/<slug>` — shared by every `/hm:` stage for this task — NOT an ephemeral `execute-<uuid>` worktree. Claim/refresh it and surface concurrent work + drift:


```bash
!uv run --with <SRC> python -m harness_maker.worktree task-preflight <slug> "$(pwd)"
```


- **stdout** = the task worktree absolute path. **Treat that exact string as `<WT>`** for every Read/Write/Edit and every `!cd <WT> && …` in this stage. Do NOT use a shell variable.
- **stderr warnings**: `[preflight] … other active session(s)` = another session holds a task concurrently (informational, no action needed). `[preflight] … behind …` = the task branch drifted behind the base tip; to rebase it cleanly onto the base before working, run:


```bash
!uv run --with <SRC> python -m harness_maker.worktree task-refresh <slug> "$(pwd)"
```


  `task-refresh` rebases `hm/<slug>` onto the base tip (base HEAD, not a hardcoded `main`), preserving commits; a conflict aborts and leaves the branch untouched — resolve manually, then retry. Refuse to refresh a dirty worktree: commit or discard first."""


def test_preflight_block_matches_golden(tmp_path: Path) -> None:
    files = _render(tmp_path, flag_on=True)
    body = _stage(files, "wrapup")
    start = body.index("### Task worktree preflight")
    end = body.index("### Step 1 — Pre-flight")
    block = body[start:end].rstrip("\n")
    # normalize the machine-specific install ref to keep the golden path-independent
    src = _synth._compute_install_ref()
    block = block.replace(src, "<SRC>")
    assert block == _GOLDEN_PREFLIGHT


# ── fused workflows inherit the preflight (master Phase 5 AC) ──────────────────


def _fused_execute_commands(files: dict[str, str]) -> dict[str, str]:
    """Rendered fused `/hm:` command files whose body fuses the execute stage."""
    return {p: t for p, t in files.items() if "commands/hm/" in p and "## Stage: execute" in t}


def test_fused_workflows_inherit_preflight_when_flag_on(tmp_path: Path) -> None:
    files = _render(tmp_path, flag_on=True)
    fused = _fused_execute_commands(files)
    assert fused, "expected at least one fused command embedding the execute stage"
    for path, body in fused.items():
        assert "Task worktree preflight" in body, path
        assert "worktree task-preflight <slug>" in body, path


def test_fused_workflows_omit_preflight_when_flag_off(tmp_path: Path) -> None:
    files = _render(tmp_path, flag_on=False)
    for path, body in _fused_execute_commands(files).items():
        assert "task-preflight" not in body, path
