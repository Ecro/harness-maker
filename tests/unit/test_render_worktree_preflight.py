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


# ── span emission (Phase 2 of PLAN-economics-attribution-and-carry) ──────────
#
# ADR-008: the span START rides the preflight call the stage already MUST make, so
# emission reliability is coupled to stage reliability. That coupling only holds if
# EVERY wired stage passes its own `--stage`; a template that forgets it degrades to
# the `(unknown-stage)` sentinel, which is the absent case ADR-003 defines.


def test_every_wired_stage_passes_its_own_stage_name_after_the_base_positional(
    tmp_path: Path,
) -> None:
    """Rejects three wrong implementations: a template that inherits the partial but
    forgets `--stage`; one that hard-codes a single name for all seven (copy-paste);
    and — the one a bare `--stage hm:X` grep would MISS — a flag placed BEFORE the
    base positional. The shipped parser treats every non-`--` arg as positional, so
    `task-preflight <slug> --stage hm:plan "$(pwd)"` makes `base_dir = Path("hm:plan")`.
    Pinning the full invocation is what couples the rendered string to a correct parse.
    """
    files = _render(tmp_path, flag_on=True)
    for stage in WIRED_STAGES:
        body = _stage(files, stage)
        assert f'task-preflight <slug> "$(pwd)" --stage hm:{stage}' in body, stage


def test_flag_off_gives_execute_only_coverage_not_zero(tmp_path: Path) -> None:
    """Non-Goal 2, as CORRECTED during Phase 2.

    An earlier version asserted `"--stage hm:" not in body` for all seven stages and
    called that "emits nothing". Two defects: (a) it was entailed by the sibling
    `test_preflight_absent_in_all_stages_when_flag_off`, so it had no independent
    failure mode; (b) the claim was false — flag-off `execute` renders
    `worktree create execute`, which emits `hm:execute` (proven in
    `tests/integration/test_stage_spans_e2e.py`). Asserting rendered PROSE could
    never have caught that, because the emission is a side effect of the CLI.
    """
    files = _render(tmp_path, flag_on=False)
    for stage in WIRED_STAGES:
        assert "--stage hm:" not in _stage(files, stage), stage
    # …but execute keeps a real emitter via its legacy isolation call.
    assert "worktree create execute" in _stage(files, "execute")


def test_fused_workflows_carry_the_stage_name_of_each_fused_stage(tmp_path: Path) -> None:
    """A fused workflow concatenates stage fragments into ONE command file, so it must
    emit one start per fused stage — not a single span for the whole run.

    The default `fused_workflows` is only `exec-rev-wrap`, so an earlier version of
    this test looked for `hm/plan-exec-rev.md`, which the fixture never renders: it
    died on StopIteration before reaching any contract assertion.
    """
    files = _render(tmp_path, flag_on=True)
    fused = next(t for p, t in files.items() if p.endswith("hm/exec-rev-wrap.md"))
    for stage in ("execute", "review", "wrapup"):
        assert f'task-preflight <slug> "$(pwd)" --stage hm:{stage}' in fused, stage


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
!uv run --with <SRC> hm worktree task-preflight <slug> "$(pwd)" --stage hm:wrapup
```


- **stdout** = the task worktree absolute path. **Treat that exact string as `<WT>`** for every Read/Write/Edit and every `!cd <WT> && …` in this stage. Do NOT use a shell variable.
- **stderr warnings**: `[preflight] … other active session(s)` = another session holds a task concurrently (informational, no action needed). `[preflight] … behind …` = the task branch drifted behind the base tip; to rebase it cleanly onto the base before working, run:


```bash
!uv run --with <SRC> hm worktree task-refresh <slug> "$(pwd)"
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


# ── flag-ON: wrapup squash-lands the task branch (ADR-003 wiring; Phase 4 gap) ─


def test_wrapup_lands_task_branch_when_flag_on(tmp_path: Path) -> None:
    # ADR-003: wrapup is the land owner. Flag-on wrapup must wire the actual Step 7.7
    # land invocation (the Phase-4 wiring gap Codex found) — pin the exact command +
    # the heading so an incidental `task-*` mention can't satisfy this.
    body = _stage(_render(tmp_path, flag_on=True), "wrapup")
    assert "Squash-land the task branch" in body, (
        "flag-on wrapup must render the Step 7.7 land step"
    )
    assert "worktree task-land <SLUG> <BASE>" in body, "flag-on wrapup must invoke task-land"


def test_wrapup_no_land_when_flag_off(tmp_path: Path) -> None:
    # Flag-off must render the legacy wrapup with NO land step (the Step 7.7 block is
    # fully inside the flag gate). Byte-neutrality of the gate is asserted separately;
    # here we pin that neither the heading nor the invocation leaks into flag-off.
    body = _stage(_render(tmp_path, flag_on=False), "wrapup")
    assert "task-land" not in body, "flag-off wrapup must not reference task-land"
    assert "Squash-land the task branch" not in body, "flag-off must omit the Step 7.7 heading"


# ── flag-ON: Step 6/7 commit inside <WT> so the curated commit lands on the branch ─


def test_wrapup_commit_runs_inside_worktree_when_flag_on(tmp_path: Path) -> None:
    # REVIEW-2026-06-21 P3-3: staging + commit must target <WT> (the hm/<slug> task
    # worktree), else they execute in the base repo against an empty index → the commit
    # is a no-op and the curated message never reaches the branch Step 7.7 squash-lands
    # (which also defeats P2-3's message reuse).
    #
    # PLAN-workflow-step-audit Phase 2 changed the MECHANISM, not the property: the
    # `cd <WT> &&` shell prefix became an explicit `--worktree <WT>` argument, and the
    # composite refuses a `--worktree` that is not a worktree of `--base`. That is a
    # stronger binding than the prefix — a prefix could be dropped and the call would
    # still run, just in the wrong place.
    body = _stage(_render(tmp_path, flag_on=True), "wrapup")
    assert "hm wrapup_land --worktree <WT> --base <BASE>" in body, (
        "flag-on staging + commit must bind <WT> explicitly"
    )


def test_wrapup_commit_runs_in_base_when_flag_off(tmp_path: Path) -> None:
    # Flag-off has no task worktree, so the composite still takes both roots but there is
    # no Step 7.7 to land onto — asserted by `test_wrapup_no_land_when_flag_off`.
    body = _stage(_render(tmp_path, flag_on=False), "wrapup")
    assert "hm wrapup_land --worktree" in body
    assert "cd <WT> && git commit" not in body, "flag-off must not inject <WT> into the commit"
