"""`worktree_gate` duplicates two things on purpose — pin both, or they drift.

PLAN-multisession-marker-scoping ADR-005 says to strip `/.worktrees/<name>/` "the way
`autopilot.resolve_marker_root` already does". The gate implements it locally instead of
calling it, because this hook fires on EVERY Write/Edit and importing
`harness_maker.autopilot` drags in pydantic plus the 5k-line `worktree` module onto that
latency path. Duplication buys the latency and owes these tests: without them the two
implementations diverge silently, and a divergence here means the gate roots at the
worktree, finds no markers, and enforces nothing — with no symptom at all.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from harness_maker import autopilot, worktree
from harness_maker.gates import worktree_gate

_GATE_SRC = Path(worktree_gate.__file__)


def test_worktree_dir_name_matches_the_canonical_constant() -> None:
    assert worktree_gate._WORKTREE_DIR_NAME == worktree.WORKTREE_DIR_NAME


@pytest.mark.parametrize("harness_yaml", [True, False])
def test_strip_agrees_with_resolve_marker_root_inside_a_worktree(
    tmp_path: Path, harness_yaml: bool
) -> None:
    """The strict `.claude/harness.yaml` sentinel is the whole difference between
    resolving to the base and silently resolving to the worktree."""
    repo = tmp_path / "repo"
    wt = repo / ".worktrees" / "my-task"
    wt.mkdir(parents=True)
    (repo / ".git").mkdir()
    # A real git worktree carries a `.git` FILE, and that is what makes the no-harness.yaml
    # case degrade the way ADR-005 records: `resolve_marker_root` falls through to a parent
    # walk whose predicate accepts a bare `.git`, and the walk starts AT the worktree — so
    # both implementations root at the worktree and the gate enforces nothing. Accepted, and
    # low-impact for a rendered harness (harness.yaml is always present); pinned here so a
    # later reader does not rediscover it as a bug, and so the two stay identical in it.
    (wt / ".git").write_text("gitdir: ../../.git/worktrees/my-task\n", encoding="utf-8")
    if harness_yaml:
        (repo / ".claude").mkdir()
        (repo / ".claude" / "harness.yaml").write_text("preset: Side\n", encoding="utf-8")

    expected = repo.absolute() if harness_yaml else wt.absolute()
    assert worktree_gate._strip_worktree(wt) == expected
    assert autopilot.resolve_marker_root(wt) == expected


def test_strip_leaves_a_harness_root_alone(tmp_path: Path) -> None:
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / "harness.yaml").write_text("preset: Side\n", encoding="utf-8")
    assert worktree_gate._strip_worktree(tmp_path) == tmp_path.absolute()
    assert autopilot.resolve_marker_root(tmp_path) == tmp_path.absolute()


def test_a_plain_subdirectory_walks_up_to_the_harness_root(tmp_path: Path) -> None:
    """The branch that is NOT the `.worktrees` strip, and the one that fails silently.

    The payload `cwd` is routinely an ordinary subdirectory. Without the parent walk the
    gate looks for `<repo>/src/.claude`, finds no markers, and allows every write in the
    project — indistinguishable from "no peers are active".
    """
    repo = tmp_path / "repo"
    (repo / ".claude").mkdir(parents=True)
    (repo / ".claude" / "harness.yaml").write_text("preset: Side\n", encoding="utf-8")
    src = repo / "src" / "deep"
    src.mkdir(parents=True)
    assert worktree_gate._strip_worktree(src) == repo.absolute()
    assert autopilot.resolve_marker_root(src) == repo.absolute()


def test_a_peer_marker_is_honored_from_a_subdirectory_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The behavioural half of the test above — parity is a means, enforcement is the end."""
    import io
    import json

    from harness_maker import loop_marker

    repo = tmp_path / "repo"
    (repo / ".claude").mkdir(parents=True)
    (repo / ".claude" / "harness.yaml").write_text("preset: Side\n", encoding="utf-8")
    peer_wt = repo / ".worktrees" / "their-task"
    peer_wt.mkdir(parents=True)
    (repo / ".claude" / ".hm-task-their-task").write_text(
        loop_marker.format_marker_content("bbbb2222cafe", [peer_wt]), encoding="utf-8"
    )
    src = repo / "src"
    src.mkdir()
    monkeypatch.setattr(
        "sys.stdin",
        io.StringIO(
            json.dumps(
                {
                    "tool_name": "Write",
                    "cwd": str(src),
                    "session_id": "aaaa1111cafe",
                    "tool_input": {"file_path": str(peer_wt / "f.py")},
                }
            )
        ),
    )
    assert worktree_gate.main() == 2


def test_the_gate_stays_import_light() -> None:
    """The reason the duplication above exists. If a later edit imports `autopilot` or
    `worktree` at module scope, the latency justification is gone and the duplication
    should be replaced by the call — this test is where that conversation starts."""
    tree = ast.parse(_GATE_SRC.read_text(encoding="utf-8"))
    heavy = {"harness_maker.autopilot", "harness_maker.worktree"}
    offenders: list[str] = []
    for node in tree.body:  # module scope ONLY — deferred imports are fine
        if isinstance(node, ast.ImportFrom):
            names = {f"{node.module}.{a.name}" for a in node.names} | {str(node.module)}
            if names & heavy or {f"{node.module}.{a.name}" for a in node.names} & heavy:
                offenders.append(f"line {node.lineno}: from {node.module} import ...")
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in heavy:
                    offenders.append(f"line {node.lineno}: import {alias.name}")
    assert not offenders, (
        "worktree_gate must stay stdlib + loop_marker at module scope — it runs on every "
        f"Write/Edit: {offenders}"
    )
