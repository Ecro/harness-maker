"""SPEC-ai-native-sdlc-vs-intent-world AC-006 — every land entry refuses on hold.

Golden rows (machine SPEC, AC-006) name the entry and the SPEC state; each row is built in a
real git repo with a real worktree, because the defect this guards against is an abort placed
after a destructive step. "Nothing landed" is therefore asserted on git state (base HEAD,
branch, worktree directory, index), never on the return code alone.
"""

from __future__ import annotations

import argparse
import copy
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml

from harness_maker import spec_machine, wrapup_land
from harness_maker import worktree as wt
from harness_maker.spec_machine import load_golden_table

_SPEC_YAML = Path(__file__).parents[2] / "specs/SPEC-ai-native-sdlc-vs-intent-world.machine.yaml"
_ROWS = load_golden_table(_SPEC_YAML, "AC-006")
_SLUG = "demo"
_IRR = {
    "id": "IRR-001",
    "decision": "public verb renamed",
    "category": "public API/CLI contract",
    "rationale": "callers break",
    "source": "spec",
}
_DOC: dict[str, Any] = {
    "schema_version": 3,
    "spec_slug": _SLUG,
    "verification_tier": 1,
    "irreversible_decisions": [copy.deepcopy(_IRR)],
    "ac": [
        {
            "id": "AC-001",
            "title": "the thing works",
            "type": "mechanical",
            "executable_predicate": "result == 1",
            "oracle_source": "golden",
            "oracle_evidence": "hand-written",
            "pending_test": True,
        }
    ],
}


def _git(cwd: Path, *args: str) -> str:
    cp = subprocess.run(["git", *args], cwd=str(cwd), check=True, capture_output=True, text=True)
    return cp.stdout.strip()


def _init(path: Path) -> Path:
    path.mkdir(parents=True)
    _git(path, "init", "-b", "main")
    _git(path, "config", "user.email", "t@example.com")
    _git(path, "config", "user.name", "T")
    (path / ".gitignore").write_text(".worktrees/\n.claude/\n")
    (path / "README.md").write_text("x\n")
    _git(path, "add", ".")
    _git(path, "commit", "-m", "init")
    return path


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(tmp_path / "no-global"))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setattr(wt, "_cli_post_commit_pop", lambda _a: 0)
    monkeypatch.setattr(wt, "_cli_drain", lambda _a: 0)
    return _init(tmp_path / "base")


def _write_spec(checkout: Path, state: str, *, doc: dict[str, Any] | None = None) -> Path:
    specs = checkout / "specs"
    specs.mkdir(parents=True, exist_ok=True)
    (specs / f"SPEC-{_SLUG}.md").write_text("---\ntype: spec\n---\n")
    body = copy.deepcopy(doc if doc is not None else _DOC)
    if state == "malformed":
        body.pop("irreversible_decisions")
    yaml_path = specs / f"SPEC-{_SLUG}.machine.yaml"
    yaml_path.write_text(yaml.safe_dump(body, sort_keys=False))
    if state in ("approved", "invalid"):
        assert spec_machine.main(["approve", "--yaml", str(yaml_path)]) == 0
    if state == "invalid":
        raw = yaml.safe_load(yaml_path.read_text())
        raw["ac"][0]["title"] = "edited after approval"
        yaml_path.write_text(yaml.safe_dump(raw, sort_keys=False))
    return yaml_path


def _head(path: Path) -> str:
    return _git(path, "rev-parse", "HEAD")


def _land_args(worktree: Path, base: Path, msg: Path) -> argparse.Namespace:
    return argparse.Namespace(
        worktree=str(worktree),
        base=str(base),
        slug=_SLUG,
        message_file=str(msg),
        required=[],
        optional=[],
        allow_legacy_ref=False,
        manifest_only=False,
    )


# ── per-entry builders: each returns (rc, observations) ─────────────────────────


def _run_wrapup_land(repo: Path, row: dict[str, Any], tmp: Path) -> tuple[int, dict[str, Any]]:
    task = repo / ".worktrees" / _SLUG
    _git(repo, "worktree", "add", "-b", f"hm/{_SLUG}", str(task))
    _write_spec(task, row["state"])
    msg = tmp / "msg.txt"
    msg.write_text("feat(demo): subject\n\nbody\n")
    before = _head(task)
    try:
        rc, _ = wrapup_land.run(_land_args(task, repo, msg))
    except wrapup_land.LandAbortError:
        rc = wrapup_land.EXIT_FAILED
    return rc, {
        "staged": bool(_git(task, "diff", "--cached", "--name-only")),
        "committed": _head(task) != before,
        "tokens": (row["state"], "IRR-001"),
    }


def _run_task_land(repo: Path, row: dict[str, Any], _tmp: Path) -> tuple[int, dict[str, Any]]:
    task = wt.task_create(repo, _SLUG, session_uuid="u-demo")
    state = "missing" if row["state"] == "missing_with_list" else row["state"]
    _write_spec(task, state)
    _git(task, "add", "-A")
    _git(task, "commit", "-m", "feat(demo): spec")
    (task / "pending.py").write_text("pending = 1\n")
    before = _head(repo)
    rc = wt.task_land(repo, _SLUG)
    return rc, {
        # Capture-before-hold: the pending edit is on the branch and the worktree is clean.
        "captured": task.is_dir()
        and _git(task, "status", "--porcelain") == ""
        and subprocess.run(
            ["git", "show", f"hm/{_SLUG}:pending.py"], cwd=str(repo), capture_output=True
        ).returncode
        == 0,
        "squashed": _head(repo) != before,
        "worktree_kept": task.is_dir(),
        "branch_kept": f"hm/{_SLUG}" in _git(repo, "branch", "--format=%(refname:short)"),
        "tokens": (state, "IRR-001"),
    }


def _run_finalize(repo: Path, row: dict[str, Any], tmp: Path) -> tuple[int, dict[str, Any]]:
    change = row.get("branch_change")
    if row.get("worktrees") == "two":
        sibling = _init(tmp / "sibling")
        loop_wt, sibling_wt = wt.create("execute", repo, [sibling])
        (loop_wt / "src.py").write_text("print('ok')\n")
        _write_spec(sibling_wt, "invalid")
        heads_before = (_head(repo), _head(sibling))
        rc = wt._cli_finalize([str(loop_wt), "success"])
        return rc, {
            "merged_any": (_head(repo), _head(sibling)) != heads_before,
            "tokens": ("invalid", "IRR-001"),
        }
    if change == "appended IRR to an approved SPEC":
        _write_spec(repo, "approved")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-m", "spec approved")
        # A same-slug task worktree with an APPROVED SPEC must not shadow the loop's checkout.
        shadow = repo / ".worktrees" / _SLUG
        _write_spec(shadow, "approved")
        loop_wt = wt.create("execute", repo)[0]
        yaml_path = loop_wt / "specs" / f"SPEC-{_SLUG}.machine.yaml"
        raw = yaml.safe_load(yaml_path.read_text())
        raw["irreversible_decisions"].append({**_IRR, "id": "IRR-002", "source": "execute"})
        yaml_path.write_text(yaml.safe_dump(raw, sort_keys=False))
        tokens: tuple[str, ...] = ("invalid", "IRR-001", "IRR-002")
    elif change == "no SPEC files":
        loop_wt = wt.create("execute", repo)[0]
        (loop_wt / "src.py").write_text("print('ok')\n")
        tokens = ()
    else:
        loop_wt = wt.create("execute", repo)[0]
        _write_spec(loop_wt, row["state"])
        tokens = (row["state"],)
    before = _head(repo)
    rc = wt._cli_finalize([str(loop_wt), "success"])
    return rc, {"merged": _head(repo) != before, "tokens": tokens}


_BUILDERS = {
    "wrapup_land": _run_wrapup_land,
    "task-land": _run_task_land,
    "finalize_success": _run_finalize,
}


@pytest.mark.parametrize("row", _ROWS, ids=[r.note for r in _ROWS])
def test_ac_006_land_entries_refuse_on_hold(
    repo: Path, tmp_path: Path, row: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    rc, seen = _BUILDERS[row.input["entry"]](repo, row.input, tmp_path)
    err = capsys.readouterr().err
    expected = dict(row.expected)
    if expected.pop("exit") == 0:
        assert rc == 0, err
    else:
        assert rc != 0
        hold_line = next((ln for ln in err.splitlines() if expected["reason_prefix"] in ln), "")
        assert hold_line, err
        # AC-006: the reason names the state and the ids, not just "hold:".
        for token in seen["tokens"]:
            assert token in hold_line, (token, hold_line)
        expected.pop("reason_prefix")
    for key, value in expected.items():
        assert seen[key] is value, (key, seen)


def test_ac_006_hold_then_approve_keeps_the_curated_squash_message(repo: Path) -> None:
    task = wt.task_create(repo, _SLUG, session_uuid="u-demo")
    yaml_path = _write_spec(task, "missing")
    _git(task, "add", "-A")
    _git(task, "commit", "-m", "feat(demo): curated subject\n\nCo-Authored-By: X <x@example.com>")
    (task / "late.py").write_text("late = 1\n")
    assert wt.task_land(repo, _SLUG) != 0
    # The holding call already captured the late edit onto the branch.
    assert _git(task, "status", "--porcelain") == ""
    assert _git(repo, "show", f"hm/{_SLUG}:late.py") == "late = 1"
    assert spec_machine.main(["approve", "--yaml", str(yaml_path)]) == 0
    assert wt.task_land(repo, _SLUG) == 0
    # The edit captured while holding must be in the landed tree, not dropped on retry.
    assert (repo / "late.py").read_text() == "late = 1\n"
    landed = _git(repo, "log", "-1", "--format=%B")
    assert landed.startswith("feat(demo): curated subject")
    assert "Co-Authored-By: X <x@example.com>" in landed


def test_task_land_holds_when_the_checkout_repoints_spec_dir(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The gated checkout's own `spec.dir` cannot point the hold away from its SPEC."""
    task = wt.task_create(repo, _SLUG, session_uuid="u-demo")
    _write_spec(task, "missing")
    (task / ".claude").mkdir(exist_ok=True)
    (task / ".claude" / "harness.yaml").write_text("spec:\n  dir: elsewhere/\n")
    _git(task, "add", "-A")
    _git(task, "commit", "-m", "feat(demo): spec")
    before = _head(repo)
    assert wt.task_land(repo, _SLUG) != 0
    assert _head(repo) == before
    assert f"[land] hold: SPEC {_SLUG} is missing; irreversible: IRR-001" in capsys.readouterr().err


def test_task_land_teardown_of_already_landed_content_is_not_held(repo: Path) -> None:
    """Content already in base (landed by another path) needs teardown, not a land decision.

    A hold here would block only the cleanup, and report it as a land hold.
    """
    task = wt.task_create(repo, _SLUG, session_uuid="u-demo")
    _write_spec(task, "missing")
    _git(task, "add", "-A")
    _git(task, "commit", "-m", "feat(demo): spec")
    _git(repo, "merge", "--squash", f"hm/{_SLUG}")
    _git(repo, "commit", "-m", "feat(demo): landed by hand")
    landed = _head(repo)
    assert wt.task_land(repo, _SLUG) == 0
    assert _head(repo) == landed
    assert not task.is_dir()


def test_task_land_checks_the_branch_when_its_worktree_is_gone(repo: Path) -> None:
    """A removed task worktree does not let the branch's unapproved SPEC land unchecked."""
    task = wt.task_create(repo, _SLUG, session_uuid="u-demo")
    _write_spec(task, "missing")
    _git(task, "add", "-A")
    _git(task, "commit", "-m", "feat(demo): spec")
    _git(repo, "worktree", "remove", "--force", str(task))
    before = _head(repo)
    assert wt.task_land(repo, _SLUG) != 0
    assert _head(repo) == before
    assert f"hm/{_SLUG}" in _git(repo, "branch", "--format=%(refname:short)")
    assert "hm-approval-" not in _git(repo, "worktree", "list")


def test_land_states_sees_a_non_ascii_spec_name(repo: Path) -> None:
    """Default `core.quotePath` quotes such names; the change set must still find them."""
    task = wt.task_create(repo, _SLUG, session_uuid="u-demo")
    specs = task / "specs"
    specs.mkdir()
    doc = copy.deepcopy(_DOC)
    doc["spec_slug"] = "한글"
    (specs / "SPEC-한글.machine.yaml").write_text(yaml.safe_dump(doc, allow_unicode=True))
    states = spec_machine.land_states(repo, task)
    assert [(s.slug, s.land) for s in states] == [("한글", "hold")]


def test_land_states_holds_when_git_cannot_list_the_changes(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Unknown SPEC set = hold, not "check the named slugs and land"."""
    task = wt.task_create(repo, _SLUG, session_uuid="u-demo")
    monkeypatch.setattr(spec_machine, "_git_lines", lambda *_a, **_k: None)
    lines = spec_machine.hold_lines(spec_machine.land_states(repo, task))
    assert lines == [
        "hold: SPEC * is malformed; irreversible: - (git could not list the branch's SPECs)"
    ]


def _spec_dir_config(root: Path, value: str) -> None:
    (root / ".claude").mkdir(exist_ok=True)
    (root / ".claude" / "harness.yaml").write_text(f"spec:\n  dir: {value}\n")


def _held(states: list[spec_machine.ApprovalState]) -> list[tuple[str, str]]:
    return [(s.slug, s.state) for s in states if s.land == "hold"]


def test_land_states_matches_a_dot_slash_spec_dir(repo: Path) -> None:
    """`./specs/` is a valid spelling; git reports `specs/…`, and finalize names no slug."""
    task = wt.task_create(repo, _SLUG, session_uuid="u-demo")
    _spec_dir_config(repo, "./specs/")
    _spec_dir_config(task, "./specs/")
    _write_spec(task, "invalid")
    assert _held(spec_machine.land_states(repo, task)) == [(_SLUG, "invalid")]


def test_land_states_checks_every_changed_copy_of_a_slug(repo: Path) -> None:
    """An approved copy in the old dir cannot mask a changed, unapproved copy in the new one."""
    _write_spec(repo, "approved")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "approved spec")
    task = wt.task_create(repo, _SLUG, session_uuid="u-demo")
    _spec_dir_config(task, "new-specs/")
    new = task / "new-specs"
    new.mkdir()
    (new / f"SPEC-{_SLUG}.machine.yaml").write_text(yaml.safe_dump(_DOC, sort_keys=False))
    held = _held(spec_machine.land_states(repo, task, [_SLUG]))
    assert held == [(_SLUG, "missing")]


def test_land_states_finds_a_changed_spec_left_behind_by_a_moved_spec_dir(repo: Path) -> None:
    """Worktree off (base == checkout): moving `spec.dir` must not hide the SPEC still changed."""
    _spec_dir_config(repo, "elsewhere/")
    _write_spec(repo, "missing")
    held = _held(spec_machine.land_states(repo, repo, [_SLUG]))
    assert (_SLUG, "missing") in held
