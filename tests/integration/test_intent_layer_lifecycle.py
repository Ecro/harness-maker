"""AC-013 — the state paths survive the whole lifecycle as deliverables, including real
`work-docs/INTENT-<ID>.md` records (SPEC-playbook-alignment moved the record there; the lifecycle
now authors one through `objective new`, approves and activates it, and lands it).

On a clean consuming project: none of the paths is gitignored (git's own `check-ignore` is
the oracle), `_path_owner` says `deliverable`, `make --update` leaves every byte alone, a
finalize stash round trip returns them byte-identical (deliverables are stash-PRESERVED by
design), and `wrapup_land` stages them with only the PLAN passed as `--required` — the four
must arrive through `derive_deliverable_globs`, not through prose.

Passing-before-the-change justification (Phase A.4):
`test_ac_013_finalize_stash_round_trip_is_byte_identical` is a NEGATIVE invariant — the state
files must never be classified as harness artifacts (which
would exclude them from the stash and from the user's stash protection). It is vacuously true
until a change misclassifies them; its RED positive sibling is
`test_ac_013_paths_are_not_ignored_and_classify_as_deliverable`, which forces the
classification change into existence.
"""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from harness_maker import worktree as wt
from harness_maker import world, wrapup_land
from harness_maker.cli import app
from tests.unit import world_fixture as fx

SLUG = "slug"
runner = CliRunner()


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, text=True, check=False, timeout=120
    )


STATE_PATHS = [
    ".claude/intent.yaml",
    ".claude/world/assumptions.yaml",
    ".claude/world/outcomes.yaml",
    "work-docs/INTENT-OBJ-1.md",
    "work-docs/INTENT-OBJ-2.md",
]


def _bytes(root: Path) -> dict[str, bytes]:
    return {p: (root / p).read_bytes() for p in STATE_PATHS}


def _populate(root: Path) -> None:
    fx.build_root(
        root,
        git=False,
        intent=fx.intent_doc(fx.outcome(), mission="keep users"),
        assumptions=[fx.assumption()],
        objectives=[fx.objective("OBJ-1"), fx.objective("OBJ-2")],
    )


@pytest.fixture
def project(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    root.mkdir()
    fx.git_init(root)
    (root / "README.md").write_text("x\n", encoding="utf-8")
    assert _git(root, "add", "README.md").returncode == 0
    assert _git(root, "commit", "-q", "-m", "init").returncode == 0
    result = runner.invoke(app, ["make", str(root), "--autoloop"])
    assert result.exit_code == 0, result.output
    # make wrote the skeleton; the human fills the rest in.
    _populate(root)
    return root


def test_ac_013_paths_are_not_ignored_and_classify_as_deliverable(project: Path) -> None:
    for p in STATE_PATHS:
        r = _git(project, "check-ignore", "-q", p)
        assert r.returncode == 1, f"{p} is ignored: {r.stdout}{r.stderr}"
        assert wt._path_owner(p) == "deliverable", p


def test_ac_013_make_update_leaves_every_byte_alone(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The regen guard refuses `--update` when the TEST PROCESS runs inside a `.worktrees/`
    # checkout; the fixture project is a tmp dir, so the guard is about our cwd, not it.
    monkeypatch.setenv("HARNESS_MAKER_BYPASS_WORKTREE_GUARD", "1")
    before = _bytes(project)
    result = runner.invoke(app, ["make", str(project), "--autoloop", "--update"])
    assert result.exit_code == 0, result.output
    assert _bytes(project) == before


def test_ac_013_finalize_stash_round_trip_is_byte_identical(project: Path) -> None:
    before = _bytes(project)
    sha = wt._stash_base_dirty(project, "wt-probe")
    assert sha is not None, "the state files are user dirt at finalize and must be stashed"
    assert not (project / "work-docs" / "INTENT-OBJ-1.md").exists()
    r = _git(project, "stash", "apply", sha)
    assert r.returncode == 0, r.stderr
    assert _bytes(project) == before


def test_ac_013_wrapup_land_stages_the_state_paths_through_the_derived_globs(
    project: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Commit the rendered harness so the worktree starts clean, then put the state edits
    # and the PLAN on the task branch only.
    assert _git(project, "add", "-A").returncode == 0
    assert _git(project, "commit", "-q", "-m", "harness").returncode == 0
    wt_path = project / ".worktrees" / SLUG
    assert _git(project, "worktree", "add", "-q", "-b", f"hm/{SLUG}", str(wt_path)).returncode == 0
    plan = wt_path / "work-docs" / f"PLAN-{SLUG}.md"
    plan.parent.mkdir(parents=True, exist_ok=True)
    plan.write_text("---\ntype: plan\n---\n# PLAN\n", encoding="utf-8")
    doc = fx.load(wt_path / ".claude" / "world" / "assumptions.yaml")
    doc["assumptions"][0]["claim"] = "edited on the task branch"
    fx.dump(wt_path / ".claude" / "world" / "assumptions.yaml", doc)
    # The Playbook path: author through the verb, approve, activate — then land it.
    world.new_objective(
        wt_path,
        "OBJ-3",
        title="t",
        hypothesis="h",
        scope=["s"],
        outcome_id="onboarding_minutes",
    )
    world.approve(wt_path, "OBJ-3")
    world.activate(wt_path, "OBJ-3")
    assert world.derive(world.load_world(wt_path), "OBJ-3").approval_valid is True
    msg = tmp_path / "msg.txt"
    msg.write_text("feat: land\n\nbody\n", encoding="utf-8")
    monkeypatch.setattr(wt, "_cli_post_commit_pop", lambda _a: 0)
    monkeypatch.setattr(wt, "_cli_drain", lambda _a: 0)
    args = argparse.Namespace(
        worktree=str(wt_path),
        base=str(project),
        slug=SLUG,
        message_file=str(msg),
        required=[f"work-docs/PLAN-{SLUG}.md"],
        optional=[],
        allow_legacy_ref=False,
        # manifest-only: the isolated-worktree sweep would stage everything and hide a
        # derive_deliverable_globs that never learned the state paths (A.4: vacuous pass).
        manifest_only=True,
    )
    rc, receipt = wrapup_land.run(args)
    assert rc == 0, receipt
    staged: list[Any] = receipt["steps"]["index_after"]
    for p in (".claude/world/assumptions.yaml", "work-docs/INTENT-OBJ-3.md"):
        assert p in staged, (p, staged)


# ── SPEC-objective-gap-proposal — gap → proposal → approve → activate, end to end ─────────────


def test_gap_proposal_lifecycle_from_an_unmeasured_world(project: Path) -> None:
    """The proposer's path on a project whose outcomes were never measured: `gap` names the
    evidence gap, the accepted candidate lands as `proposed` with the declined title in
    `rejected[]`, the gate would halt on it (no valid approval), and after the human approve +
    activate the same reader shows it `active`."""
    before = world.gap_report(project)
    assert before["state"] == "ok"
    assert before["outcomes"]["onboarding_minutes"]["reason"] == "never_measured"
    assert set(before["objectives"]) == {"OBJ-1", "OBJ-2"}
    rec = world.new_objective(
        project,
        "OBJ-9",
        title="t",
        hypothesis="h",
        scope=["s"],
        outcome_id="onboarding_minutes",
        from_proposal=True,
        candidates=2,
        declined=["the other candidate"],
    )
    assert rec["state"] == "proposed"
    mid = world.gap_report(project)
    assert mid["objectives"]["OBJ-9"]["rejected"] == ["the other candidate"]
    assert world.derive(world.load_world(project), "OBJ-9").approval_valid is not True
    rows = (project / ".claude" / "observability" / "auto-advance.jsonl").read_text().splitlines()
    assert sum('"objective_proposed"' in ln and '"OBJ-9"' in ln for ln in rows) == 1
    world.approve(project, "OBJ-9")
    world.activate(project, "OBJ-9")
    after = world.gap_report(project)
    assert after["objectives"]["OBJ-9"]["state"] == "active"
    assert world.status_report(project)["active"]["OBJ-9"]["approval_valid"] is True
