"""worktree_gate — peer protection, session scoping, absolute fail-open.

PLAN-multisession-marker-scoping Phase 3. This file replaced the self-confinement suite:
the old rule ("inside the repo, outside my marker union → block") had no empty-union case,
so a session with no worktree was either blocked from the entire repo or, bypassed, free to
write into peers' worktrees. It was also session-blind, which is how a DEAD session's
leftover marker came to block an unrelated peer's every `Write`, `/tmp` included.

The invariant now (ADR-004): block iff the target is inside another LIVE session's
worktree. Everything else — the base repo, `/tmp`, an unattributable worktree — is allowed.

Two tests here pin the cases whose omission would be a work stoppage rather than a missed
block: `test_empty_header_marker_never_blocks_anyone` (every standalone `/hm:execute`
worktree writes one) and `test_own_membership_wins_over_a_peer_claim` (routine after a
restart). A third, `test_gate_invoked_from_inside_a_worktree_still_finds_base_markers`,
pins ADR-005 — rooting at the payload `cwd` makes the gate enforce nothing, silently.
"""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from harness_maker import loop_marker
from harness_maker.gates import worktree_gate

MINE = "aaaa1111cafe"
PEER = "bbbb2222cafe"

_FIXTURE = Path(__file__).parents[1] / "fixtures" / "pretooluse_payload_write.json"


def _project(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / ".claude").mkdir(parents=True)
    (repo / ".claude" / "harness.yaml").write_text("preset: Side\n", encoding="utf-8")
    return repo


def _worktree(repo: Path, name: str, owner: str, *, family: str = "loop") -> Path:
    wt = repo / ".worktrees" / name
    wt.mkdir(parents=True, exist_ok=True)
    prefix = ".hm-loop-" if family == "loop" else ".hm-task-"
    (repo / ".claude" / f"{prefix}{name}").write_text(
        loop_marker.format_marker_content(owner, [wt]), encoding="utf-8"
    )
    return wt


def _run(
    monkeypatch: pytest.MonkeyPatch,
    *,
    cwd: Path,
    target: Path,
    session_id: str | None = MINE,
    tool: str = "Write",
) -> int:
    payload: dict[str, object] = {
        "tool_name": tool,
        "cwd": str(cwd),
        "tool_input": {"file_path": str(target)},
    }
    if session_id is not None:
        payload["session_id"] = session_id
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
    return worktree_gate.main()


# --- ADR-004: the one thing that blocks --------------------------------------------


@pytest.mark.parametrize("tool", ["Write", "Edit", "MultiEdit"])
def test_write_into_a_peers_worktree_is_blocked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tool: str
) -> None:
    """Every member of `_GUARDED_TOOLS`. Pinning only `Write` let the most likely edit to
    that frozenset — dropping `Edit`/`MultiEdit` — keep the suite green while disabling the
    gate for the tool that produces most file mutations, and the failure mode is `allow`."""
    repo = _project(tmp_path)
    peer_wt = _worktree(repo, "their-task", PEER)
    assert _run(monkeypatch, cwd=repo, target=peer_wt / "src" / "f.py", tool=tool) == 2
    assert str(peer_wt) in capsys.readouterr().err


def test_a_peers_task_worktree_is_protected_too(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ADR-008: before the task family existed, the per-task model — the DEFAULT under
    `worktree.enabled: true` — had zero enforcement here."""
    repo = _project(tmp_path)
    peer_wt = _worktree(repo, "their-task", PEER, family="task")
    assert _run(monkeypatch, cwd=repo, target=peer_wt / "src" / "f.py") == 2


# --- ADR-004: everything that must NOT block ---------------------------------------


def test_base_repo_write_is_allowed_while_a_peer_holds_a_worktree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A session with no worktree of its own was blocked from the whole repo by the old
    union rule. That is the symptom this PLAN opens with."""
    repo = _project(tmp_path)
    _worktree(repo, "their-task", PEER)
    assert _run(monkeypatch, cwd=repo, target=repo / "src" / "f.py") == 0


def test_tmp_is_never_blocked(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`wrapup.md.j2` writes a wiki body to a `mktemp -t` path — blocking `/tmp` breaks
    the harness's own procedure (interview #1)."""
    repo = _project(tmp_path)
    _worktree(repo, "their-task", PEER)
    assert _run(monkeypatch, cwd=repo, target=tmp_path / "scratch" / "note.md") == 0


def test_my_own_worktree_is_never_blocked(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _project(tmp_path)
    _worktree(repo, "their-task", PEER)
    my_wt = _worktree(repo, "my-task", MINE)
    assert _run(monkeypatch, cwd=my_wt, target=my_wt / "src" / "f.py") == 0


def test_own_membership_wins_over_a_peer_claim(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One path listed by BOTH a loop marker (peer) and a task marker (mine).

    Round 3 review: the previous version of this test wrote a `.hm-loop-*` AND a
    `.hm-task-*` for the same TASK worktree, which no writer produces — `task_create` writes
    only `.hm-task-*`. It passed on a fabricated state, so the criterion it names was never
    exercised. The producible shape is a loop worktree that a task marker also claims, which
    is where own-membership genuinely arbitrates.
    """
    repo = _project(tmp_path)
    shared = _worktree(repo, "execute-abc", PEER)  # loop marker, peer-owned
    (repo / ".claude" / ".hm-task-execute-abc").write_text(
        loop_marker.format_marker_content(MINE, [shared]), encoding="utf-8"
    )
    assert _run(monkeypatch, cwd=repo, target=shared / "src" / "f.py") == 0


def test_a_symlinked_cwd_still_grants_self_membership(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`is_relative_to` is lexical, and marker paths are `.resolve()`d. Comparing an
    unresolved cwd against them denied membership through a symlink and blocked a session
    from its own worktree — silently, with no diagnostic."""
    repo = _project(tmp_path)
    wt = _worktree(repo, "their-task", PEER)
    link = tmp_path / "linked"
    link.symlink_to(repo, target_is_directory=True)
    assert _run(monkeypatch, cwd=link / ".worktrees" / "their-task", target=wt / "f.py") == 0


def test_empty_header_marker_never_blocks_anyone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The third bucket (ADR-004). Only `loop.md.j2` passes `--claude-session-id`, so EVERY
    standalone `/hm:execute` worktree marker has an empty header. Under a two-way
    mine/peer partition those sessions are blocked from their own worktree — a total work
    stoppage, not a missed block."""
    repo = _project(tmp_path)
    anon_wt = _worktree(repo, "execute-abc", "")
    assert _run(monkeypatch, cwd=anon_wt, target=anon_wt / "src" / "f.py") == 0
    assert _run(monkeypatch, cwd=repo, target=anon_wt / "src" / "f.py", session_id=PEER) == 0


def test_a_marker_whose_worktree_is_gone_protects_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _project(tmp_path)
    ghost = repo / ".worktrees" / "ghost"
    (repo / ".claude" / ".hm-task-ghost").write_text(
        loop_marker.format_marker_content(PEER, [ghost]), encoding="utf-8"
    )
    assert _run(monkeypatch, cwd=repo, target=ghost / "src" / "f.py") == 0


def test_non_write_tools_are_not_guarded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _project(tmp_path)
    peer_wt = _worktree(repo, "their-task", PEER)
    assert _run(monkeypatch, cwd=repo, target=peer_wt / "f.py", tool="Read") == 0
    assert _run(monkeypatch, cwd=repo, target=peer_wt / "f.py", tool="Bash") == 0


# --- ADR-006: fail open, absolutely -------------------------------------------------


def test_no_session_id_allows_even_into_a_peers_worktree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Cursor / Codex / any host that sends no id. Failing CLOSED would block every Write
    in those environments while any marker is live."""
    repo = _project(tmp_path)
    peer_wt = _worktree(repo, "their-task", PEER)
    assert _run(monkeypatch, cwd=repo, target=peer_wt / "f.py", session_id=None) == 0


def test_a_non_string_session_id_is_treated_as_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _project(tmp_path)
    peer_wt = _worktree(repo, "their-task", PEER)
    monkeypatch.setattr(
        "sys.stdin",
        io.StringIO(
            json.dumps(
                {
                    "tool_name": "Write",
                    "cwd": str(repo),
                    "session_id": 17,
                    "tool_input": {"file_path": str(peer_wt / "f.py")},
                }
            )
        ),
    )
    assert worktree_gate.main() == 0


def test_malformed_stdin_allows(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO("not json"))
    assert worktree_gate.main() == 0


def test_missing_tool_input_allows(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _project(tmp_path)
    _worktree(repo, "their-task", PEER)
    monkeypatch.setattr(
        "sys.stdin",
        io.StringIO(json.dumps({"tool_name": "Write", "cwd": str(repo), "session_id": MINE})),
    )
    assert worktree_gate.main() == 0


# --- ADR-005: base-root resolution and the payload contract -------------------------


def test_gate_invoked_from_inside_a_worktree_still_finds_base_markers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`cwd` IS the worktree for every `/hm:` stage under `worktree.enabled: true`. Rooting
    there finds no `.claude/` at all and the gate enforces nothing — silently."""
    repo = _project(tmp_path)
    peer_wt = _worktree(repo, "their-task", PEER)
    my_wt = _worktree(repo, "my-task", MINE)
    assert _run(monkeypatch, cwd=my_wt, target=peer_wt / "src" / "f.py") == 2


# `_strip_worktree`'s own branches live in tests/structural/test_gate_base_root_parity.py,
# which owns them together with the `autopilot.resolve_marker_root` parity assertions —
# one place to update when the resolution rule changes.


def test_captured_payload_still_carries_the_fields_the_gate_reads() -> None:
    """The live-probe fixture (ADR-005). An upstream payload change degrades this gate
    SILENTLY — it would simply stop identifying anyone and fail open forever — so the key
    set is asserted rather than assumed."""
    payload = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    assert isinstance(payload["session_id"], str)
    assert isinstance(payload["cwd"], str)
    assert payload["tool_name"] == "Write"
    assert isinstance(payload["tool_input"]["file_path"], str)
    assert "workspace" not in payload, (
        "the probe recorded NO `workspace` key; a gate keyed on workspace.current_dir "
        "resolves nothing in Claude Code"
    )


def test_gate_reads_the_captured_payload_end_to_end(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Drive `main()` with the real shape, not a hand-built dict — the helpers never see
    the fields the payload actually carries."""
    payload = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    repo = _project(tmp_path)
    peer_wt = _worktree(repo, "their-task", PEER)
    payload["cwd"] = str(repo / ".worktrees" / "my-task")
    (repo / ".worktrees" / "my-task").mkdir(parents=True, exist_ok=True)
    payload["session_id"] = MINE
    payload["tool_input"]["file_path"] = str(peer_wt / "src" / "f.py")
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
    assert worktree_gate.main() == 2


def test_a_relative_target_resolves_against_the_tool_cwd_not_the_stripped_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CX-1 (codex). `_project_root` strips a worktree cwd to the base; resolving a relative
    `file_path` against THAT turns `../their-task/f.py` — which really lands in a peer's
    worktree — into a path outside the repo, and the gate allows it."""
    repo = _project(tmp_path)
    _worktree(repo, "their-task", PEER)
    my_wt = _worktree(repo, "my-task", MINE)
    assert _run(monkeypatch, cwd=my_wt, target=Path("../their-task/src/f.py")) == 2


def test_an_absolute_target_is_unaffected_by_the_cwd_split(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _project(tmp_path)
    peer_wt = _worktree(repo, "their-task", PEER)
    my_wt = _worktree(repo, "my-task", MINE)
    assert _run(monkeypatch, cwd=my_wt, target=peer_wt / "src" / "f.py") == 2
    assert _run(monkeypatch, cwd=my_wt, target=my_wt / "src" / "f.py") == 0
