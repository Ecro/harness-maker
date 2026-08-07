"""worktree_gate driven as a REAL subprocess, the way the hook actually runs.

PLAN-multisession-marker-scoping Testing Strategy. The in-process tests monkeypatch
`sys.stdin` and call `main()`; that cannot catch an import-time failure, a wrong module
path in the rendered hooks wiring, or a cwd-dependent resolution bug — the class
`[fail:design] runtime-env-gate-dead-on-arrival` is at count:2 for. Exit code 2 is the
block signal Claude Code reads; anything else is an allow.

The `cwd`-inside-a-worktree invocation is the one that matters most: every `/hm:` stage
under `worktree.enabled: true` runs there, and rooting at that cwd makes the gate enforce
nothing with no visible symptom.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from harness_maker import loop_marker

MINE = "aaaa1111cafe"
PEER = "bbbb2222cafe"


def _project(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / ".claude").mkdir(parents=True)
    (repo / ".claude" / "harness.yaml").write_text("preset: Side\n", encoding="utf-8")
    return repo


def _worktree(repo: Path, name: str, owner: str) -> Path:
    wt = repo / ".worktrees" / name
    wt.mkdir(parents=True, exist_ok=True)
    (repo / ".claude" / f".hm-task-{name}").write_text(
        loop_marker.format_marker_content(owner, [wt]), encoding="utf-8"
    )
    return wt


def _invoke(payload: dict[str, object], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "harness_maker.gates.worktree_gate"],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        cwd=str(cwd),
        timeout=60,
    )


def test_blocks_a_write_into_a_peers_worktree(tmp_path: Path) -> None:
    repo = _project(tmp_path)
    peer_wt = _worktree(repo, "their-task", PEER)
    cp = _invoke(
        {
            "tool_name": "Write",
            "cwd": str(repo),
            "session_id": MINE,
            "tool_input": {"file_path": str(peer_wt / "src" / "f.py")},
        },
        cwd=repo,
    )
    assert cp.returncode == 2, cp.stderr
    assert str(peer_wt) in cp.stderr


def test_allows_a_base_write(tmp_path: Path) -> None:
    repo = _project(tmp_path)
    _worktree(repo, "their-task", PEER)
    cp = _invoke(
        {
            "tool_name": "Write",
            "cwd": str(repo),
            "session_id": MINE,
            "tool_input": {"file_path": str(repo / "src" / "f.py")},
        },
        cwd=repo,
    )
    assert cp.returncode == 0, cp.stderr


def test_invocation_from_inside_a_worktree_still_finds_the_base_markers(tmp_path: Path) -> None:
    repo = _project(tmp_path)
    peer_wt = _worktree(repo, "their-task", PEER)
    my_wt = _worktree(repo, "my-task", MINE)
    cp = _invoke(
        {
            "tool_name": "Write",
            "cwd": str(my_wt),
            "session_id": MINE,
            "tool_input": {"file_path": str(peer_wt / "src" / "f.py")},
        },
        cwd=my_wt,
    )
    assert cp.returncode == 2, cp.stderr


def test_no_session_id_fails_open(tmp_path: Path) -> None:
    repo = _project(tmp_path)
    peer_wt = _worktree(repo, "their-task", PEER)
    cp = _invoke(
        {
            "tool_name": "Write",
            "cwd": str(repo),
            "tool_input": {"file_path": str(peer_wt / "src" / "f.py")},
        },
        cwd=repo,
    )
    assert cp.returncode == 0, cp.stderr
