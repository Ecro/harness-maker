"""SPEC-understanding-handoff — the commit-body Understanding block, checked but never rewritten.

AC-002 pins the classifier grammar against the SPEC's golden table (loaded, not inlined, so
the table stays the single source). AC-003 runs `wrapup_land` once per status and asserts the
warning is exactly one stderr line for a bad block and absent for a good one — a warning that
fired on every wrapup would be noise that hides the `missing` case it exists for. AC-008 reads
the created commit back from git: the classifier sits inside the message path, so a rewrite of
the message would reach the user's branch with every other assertion green. AC-004 pins the
worktree-ON half of that chain, `task_land` reusing the branch-tip body.

A.4 (justified passes against the unmodified subject — preservation guards):
- (round 2) `test_ac_008_…` now also asserts the receipt status per case, so it is RED; its
  verbatim-body assertion is the part that guards against the classifier rewriting, stripping
  or re-appending the message once it sits in the message path.
- `test_ac_004_…` pins existing `task_land` behaviour the SPEC relies on (`worktree.py` is a
  do-not-change boundary); it goes red if the squash stops reusing the branch-tip body. Its RED
  positive sibling is AC-001's render test, which forces the block into that body.
- `test_the_golden_table_covers_every_status` guards AC-003's parametrization against the table
  losing a status; it is data about the SPEC, and AC-003 itself is RED.
"""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path
from typing import Any

import pytest

from harness_maker import worktree as wt
from harness_maker import wrapup_land
from harness_maker.spec_machine import load_golden_table

_SPEC_YAML = Path(__file__).parents[2] / "specs" / "SPEC-understanding-handoff.machine.yaml"
_ROWS = load_golden_table(_SPEC_YAML, "AC-002")
_PREFIX = "[wrapup_land] understanding:"


def _row_id(row: Any) -> str:
    return f"{row.expected['status']}-{row.expected['bullets']}-{row.note or 'plain'}"


# ── AC-002 — classifier ───────────────────────────────────────────────────────


@pytest.mark.parametrize("row", _ROWS, ids=[_row_id(r) for r in _ROWS])
def test_ac_002_classifier_matches_golden_table(row: Any) -> None:
    result = wrapup_land.check_understanding_block(row.input["message"])
    assert {"status": result.status, "bullets": result.bullets} == row.expected


# ── helpers for the git-backed ACs ────────────────────────────────────────────


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, text=True, check=True
    )


def _repo_with_task(root: Path) -> tuple[Path, Path]:
    base = root / "base"
    base.mkdir(parents=True)
    _git(base, "init", "-b", "main")
    _git(base, "config", "user.email", "t@example.com")
    _git(base, "config", "user.name", "T")
    (base / "README.md").write_text("x\n", encoding="utf-8")
    _git(base, "add", "README.md")
    _git(base, "commit", "-m", "init")
    task = base / ".worktrees" / "slug"
    _git(base, "worktree", "add", "-b", "hm/slug", str(task))
    (task / "a.md").write_text("a\n", encoding="utf-8")
    return base, task


def _args(task: Path, base: Path, msg: Path) -> argparse.Namespace:
    return argparse.Namespace(
        worktree=str(task),
        base=str(base),
        slug="slug",
        message_file=str(msg),
        required=[],
        optional=["a.md"],
        allow_legacy_ref=False,
        manifest_only=False,
    )


@pytest.fixture(autouse=True)
def _no_real_pop_or_drain(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(wt, "_cli_post_commit_pop", lambda _a: 0)
    monkeypatch.setattr(wt, "_cli_drain", lambda _a: 0)


def _land(root: Path, message: str) -> tuple[int, dict[str, Any], Path, Path]:
    base, task = _repo_with_task(root)
    msg = root / "msg.txt"
    msg.write_text(message, encoding="utf-8")
    rc, receipt = wrapup_land.run(_args(task, base, msg))
    return rc, receipt, task, msg


_VALID = "feat(x): subject\n\nWhy.\n\nUnderstanding:\n- a -> b\n"


def _first_row_per_status() -> list[Any]:
    seen: dict[str, Any] = {}
    for row in _ROWS:
        seen.setdefault(row.expected["status"], row)
    return list(seen.values())


_STATUS_ROWS = _first_row_per_status()


def test_the_golden_table_covers_every_status() -> None:
    """Guards AC-003's parametrization from silently shrinking with the table."""
    assert {r.expected["status"] for r in _STATUS_ROWS} == {
        "ok",
        "none",
        "missing",
        "empty",
        "too_long",
        "malformed",
    }


# ── AC-003 — warn without blocking ────────────────────────────────────────────


@pytest.mark.parametrize("row", _STATUS_ROWS, ids=[r.expected["status"] for r in _STATUS_ROWS])
def test_ac_003_wrapup_land_warns_without_blocking(
    row: Any, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    baseline_rc, _, _, _ = _land(tmp_path / "valid", _VALID)
    capsys.readouterr()

    rc, receipt, task, _ = _land(tmp_path / "case", row.input["message"])
    stderr = capsys.readouterr().err

    expected_lines = 0 if row.expected["status"] in ("ok", "none") else 1
    assert rc == baseline_rc
    assert stderr.count(_PREFIX) == expected_lines
    assert receipt["steps"]["commit"]["status"] == "created"
    assert receipt["steps"]["understanding"] == row.expected
    assert _git(task, "rev-list", "--count", "HEAD").stdout.strip() == "2"


def test_ac_003_resume_classifies_the_committed_body_not_an_edited_message_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A retry after a failed pop must report what landed, since `task-land` reuses HEAD's body.

    Run 1 commits a body with no block, then the pop fails. The operator adds the block to the
    message file and retries: the commit is `already-present`, so the block never lands — the
    receipt has to say `missing`, not the edited file's `ok`.
    """
    base, task = _repo_with_task(tmp_path)
    msg = tmp_path / "msg.txt"
    msg.write_text("feat(x): subject\n\nWhy.\n", encoding="utf-8")
    monkeypatch.setattr(wt, "_cli_post_commit_pop", lambda _a: 1)
    _, r1 = wrapup_land.run(_args(task, base, msg))
    assert r1["steps"]["commit"]["status"] == "created"
    capsys.readouterr()

    msg.write_text("feat(x): subject\n\nWhy.\n\nUnderstanding:\n- a -> b\n", encoding="utf-8")
    monkeypatch.setattr(wt, "_cli_post_commit_pop", lambda _a: 0)
    _, r2 = wrapup_land.run(_args(task, base, msg))

    assert r2["steps"]["commit"]["status"] == "already-present"
    assert r2["steps"]["understanding"] == {"status": "missing", "bullets": 0}
    assert capsys.readouterr().err.count(_PREFIX) == 1


# ── AC-008 — the committed body is the supplied message ───────────────────────


_TRAILER = "\n\nCo-Authored-By: Claude <noreply@anthropic.com>\n"
_PRESERVATION_CASES = {
    "ok": "feat(x): subject\n\nWhy it matters.\n\nUnderstanding:\n\n- retry ownership: A -> B\n"
    "- unknown: token refresh owner\n- agent-decided: ADR-002 (unmarked: 1)",
    "too_long": "feat(x): subject\n\nWhy.\n\nUnderstanding:\n- a\n- b\n- c\n- d\n- e\n- f",
    "empty": "feat(x): subject\n\nWhy.\n\nUnderstanding:",
    "malformed": "feat(x): subject\n\nWhy.\n\nUnderstanding: none\n- stray bullet",
}


@pytest.mark.parametrize("case", sorted(_PRESERVATION_CASES))
def test_ac_008_wrapup_land_commits_the_supplied_message_unchanged(
    case: str, tmp_path: Path
) -> None:
    """S4: a bad block is warned about, never repaired — the body lands exactly as written."""
    message = _PRESERVATION_CASES[case] + _TRAILER
    _, receipt, task, msg = _land(tmp_path, message)
    assert receipt["steps"]["understanding"]["status"] == case
    committed = _git(task, "log", "-1", "--format=%B").stdout
    assert committed.rstrip() == msg.read_text(encoding="utf-8").rstrip()


# ── AC-004 — task_land keeps the block on the base branch ─────────────────────


def test_ac_004_task_land_squash_preserves_understanding_block(tmp_path: Path) -> None:
    base = tmp_path / "repo"
    base.mkdir()
    _git(base, "init", "-b", "main")
    _git(base, "config", "user.email", "t@e.com")
    _git(base, "config", "user.name", "T")
    (base / ".gitignore").write_text(".worktrees/\n.claude/\n", encoding="utf-8")
    (base / "README.md").write_text("x\n", encoding="utf-8")
    _git(base, "add", ".")
    _git(base, "commit", "-m", "init")

    task = wt.task_create(base, "feat", session_uuid="u-feat")
    (task / "feature.py").write_text("feat\n", encoding="utf-8")
    _git(task, "add", "-A")
    block_text = (
        "Understanding:\n- invariant: token refresh assumes connectivity -> no longer\n"
        "- agent-decided: none (unmarked: 3)"
    )
    body = f"feat(feat): add the widget\n\nWhy.\n\n{block_text}\n\nCo-Authored-By: C <n@x>"
    _git(task, "commit", "-m", body)

    assert wt.task_land(base, "feat") == 0
    squash_body = _git(base, "log", "-1", "--format=%B").stdout
    assert block_text in squash_body
