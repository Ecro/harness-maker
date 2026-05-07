"""worktree_gate hook tests — block Write/Edit/MultiEdit outside active <WT>.

The gate's contract: when `.claude/.hm-loop-active` marker exists and tool
target is OUTSIDE the recorded worktree, exit 2 (block). All other paths
(no marker, target inside WT, non-write tool) exit 0.
"""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from harness_maker.gates import worktree_gate


def _run(monkeypatch: pytest.MonkeyPatch, payload: dict[str, object]) -> int:
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
    return worktree_gate.main()


def _write_marker(project_root: Path, wt_path: Path) -> None:
    marker = project_root / ".claude" / ".hm-loop-active"
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(str(wt_path) + "\n", encoding="utf-8")


# ── allow paths ─────────────────────────────────────────────────────────────


def test_no_marker_means_no_active_loop_so_allow(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    rc = _run(
        monkeypatch,
        {"tool_name": "Write", "tool_input": {"file_path": str(tmp_path / "src/foo.py")}},
    )
    assert rc == 0


def test_target_inside_active_worktree_is_allowed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Active marker + Write to a path INSIDE the worktree → allow."""
    project = tmp_path / "repo"
    project.mkdir()
    wt = project / ".worktrees" / "execute-x"
    wt.mkdir(parents=True)
    _write_marker(project, wt)
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(project))
    rc = _run(
        monkeypatch,
        {"tool_name": "Edit", "tool_input": {"file_path": str(wt / "src/foo.py")}},
    )
    assert rc == 0


def test_non_write_tool_is_allowed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Read / Bash / Grep are not in _GUARDED_TOOLS — pass through."""
    project = tmp_path / "repo"
    project.mkdir()
    wt = project / ".worktrees" / "execute-x"
    wt.mkdir(parents=True)
    _write_marker(project, wt)
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(project))
    for tool in ("Read", "Bash", "Grep", "Glob", "Task"):
        rc = _run(
            monkeypatch,
            {"tool_name": tool, "tool_input": {"file_path": str(project / "src/foo.py")}},
        )
        assert rc == 0, f"tool={tool} should pass through"


def test_stale_marker_pointing_to_missing_dir_is_treated_as_no_active(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Marker points to a path that no longer exists (e.g. crashed loop) →
    treat as if no marker; don't lock the user out."""
    project = tmp_path / "repo"
    project.mkdir()
    _write_marker(project, project / ".worktrees" / "deleted-name")
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(project))
    rc = _run(
        monkeypatch,
        {"tool_name": "Write", "tool_input": {"file_path": str(project / "src/foo.py")}},
    )
    assert rc == 0


def test_empty_marker_file_treated_as_no_active(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Whitespace-only marker → no active loop."""
    project = tmp_path / "repo"
    project.mkdir()
    marker = project / ".claude" / ".hm-loop-active"
    marker.parent.mkdir(parents=True)
    marker.write_text("   \n", encoding="utf-8")
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(project))
    rc = _run(
        monkeypatch,
        {"tool_name": "Write", "tool_input": {"file_path": str(project / "x.py")}},
    )
    assert rc == 0


def test_malformed_stdin_does_not_crash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Garbage stdin → exit 0 (defensive — never block on hook bug)."""
    monkeypatch.setattr("sys.stdin", io.StringIO("not json {{{"))
    assert worktree_gate.main() == 0


def test_missing_tool_input_passes_through(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Active marker but tool_input missing file_path → allow (defensive)."""
    project = tmp_path / "repo"
    project.mkdir()
    wt = project / ".worktrees" / "execute-x"
    wt.mkdir(parents=True)
    _write_marker(project, wt)
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(project))
    rc = _run(monkeypatch, {"tool_name": "Write", "tool_input": {}})
    assert rc == 0


# ── block paths ─────────────────────────────────────────────────────────────


def test_write_to_main_while_loop_active_is_blocked(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Active marker + Write to main repo (outside <WT>) → exit 2 + stderr."""
    project = tmp_path / "repo"
    project.mkdir()
    wt = project / ".worktrees" / "execute-x"
    wt.mkdir(parents=True)
    _write_marker(project, wt)
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(project))
    rc = _run(
        monkeypatch,
        {
            "tool_name": "Write",
            "tool_input": {"file_path": str(project / "src/foo.py")},
        },
    )
    assert rc == 2
    err = capsys.readouterr().err
    assert "blocked" in err
    assert str(wt) in err
    assert "finalize" in err  # hint at how to recover


def test_edit_to_sibling_worktree_blocked(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Two worktrees: marker points to wt-A; Edit targets wt-B (different
    branch). wt-B is NOT under wt-A → blocked, even though both are
    .worktrees/. Prevents loops from cross-contaminating."""
    project = tmp_path / "repo"
    project.mkdir()
    wt_a = project / ".worktrees" / "execute-a"
    wt_a.mkdir(parents=True)
    wt_b = project / ".worktrees" / "execute-b"
    wt_b.mkdir(parents=True)
    _write_marker(project, wt_a)
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(project))
    rc = _run(
        monkeypatch,
        {"tool_name": "Edit", "tool_input": {"file_path": str(wt_b / "x.py")}},
    )
    assert rc == 2
    assert str(wt_a) in capsys.readouterr().err


def test_multiedit_is_guarded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """MultiEdit is in _GUARDED_TOOLS — same enforcement as Write/Edit."""
    project = tmp_path / "repo"
    project.mkdir()
    wt = project / ".worktrees" / "execute-x"
    wt.mkdir(parents=True)
    _write_marker(project, wt)
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(project))
    rc = _run(
        monkeypatch,
        {
            "tool_name": "MultiEdit",
            "tool_input": {"file_path": str(project / "main.py")},
        },
    )
    assert rc == 2


def test_relative_path_resolved_against_project_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Relative file_path → resolved against project root, not cwd of hook
    subprocess. Without this, a hook spawned from $HOME with a relative
    path would silently treat outside-WT writes as inside-WT."""
    project = tmp_path / "repo"
    project.mkdir()
    wt = project / ".worktrees" / "execute-x"
    wt.mkdir(parents=True)
    _write_marker(project, wt)
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(project))
    monkeypatch.chdir("/")  # ensure cwd is NOT project
    rc = _run(
        monkeypatch,
        {"tool_name": "Write", "tool_input": {"file_path": "src/foo.py"}},
    )
    # Resolves to project/src/foo.py → outside wt → blocked
    assert rc == 2


# ── env-var fallback chain ───────────────────────────────────────────────────


def test_cursor_project_dir_used_when_claude_unset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Mirror telemetry.py's resolution order: CURSOR_PROJECT_DIR is
    consulted when CLAUDE_PROJECT_DIR is unset."""
    project = tmp_path / "repo"
    project.mkdir()
    wt = project / ".worktrees" / "execute-x"
    wt.mkdir(parents=True)
    _write_marker(project, wt)
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    monkeypatch.setenv("CURSOR_PROJECT_DIR", str(project))
    rc = _run(
        monkeypatch,
        {"tool_name": "Write", "tool_input": {"file_path": str(project / "x.py")}},
    )
    assert rc == 2  # outside WT, blocked


def test_stdin_workspace_current_dir_wins_over_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Round H BLOCK 1 fix: payload.workspace.current_dir takes priority
    over env vars and cwd. Without this, multi-window IDE scenarios where
    env vars are stripped or wrong silently bypass the gate."""
    project_a = tmp_path / "repo-a"
    project_a.mkdir()
    project_b = tmp_path / "repo-b"
    project_b.mkdir()
    wt_a = project_a / ".worktrees" / "execute-x"
    wt_a.mkdir(parents=True)
    _write_marker(project_a, wt_a)
    # env points to project-b (wrong project), but stdin says project-a
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(project_b))
    monkeypatch.chdir("/")
    rc = _run(
        monkeypatch,
        {
            "tool_name": "Write",
            "tool_input": {"file_path": str(project_a / "x.py")},
            "workspace": {"current_dir": str(project_a)},
        },
    )
    # Gate consults stdin → resolves project-a → reads project-a's marker →
    # target outside wt_a → blocks.
    assert rc == 2


def test_stdin_cwd_field_used_when_workspace_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cursor's payload uses ``cwd`` (not nested under workspace). Order:
    workspace.current_dir → cwd → env → os.getcwd()."""
    project = tmp_path / "repo"
    project.mkdir()
    wt = project / ".worktrees" / "execute-x"
    wt.mkdir(parents=True)
    _write_marker(project, wt)
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    monkeypatch.delenv("CURSOR_PROJECT_DIR", raising=False)
    monkeypatch.chdir("/")
    rc = _run(
        monkeypatch,
        {
            "tool_name": "Write",
            "tool_input": {"file_path": str(project / "x.py")},
            "cwd": str(project),
        },
    )
    assert rc == 2


def test_symlinked_target_outside_wt_is_blocked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Round H NIT 10: a symlink inside the WT pointing at a main-repo
    file must NOT bypass the gate. _target_path calls Path.resolve() which
    follows symlinks; resolved target lives outside WT → blocked."""
    project = tmp_path / "repo"
    project.mkdir()
    main_file = project / "src" / "main.py"
    main_file.parent.mkdir()
    main_file.write_text("# main\n")
    wt = project / ".worktrees" / "execute-x"
    wt.mkdir(parents=True)
    # Symlink inside WT points at main_file
    smuggle = wt / "smuggle.py"
    smuggle.symlink_to(main_file)
    _write_marker(project, wt)
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(project))
    rc = _run(
        monkeypatch,
        {"tool_name": "Write", "tool_input": {"file_path": str(smuggle)}},
    )
    assert rc == 2  # symlink resolves to main_file, outside WT → blocked
