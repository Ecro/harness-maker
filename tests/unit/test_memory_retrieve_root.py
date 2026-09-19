"""AC-001/002 (SPEC-mission-context-loop) — the recall reader roots where the writer writes.

`memory_md` writes every tier at the BASE root (it strips `.worktrees/<name>`), so a fact a DRI
captures mid-task lands in base `.claude/memory/wiki.md`, uncommitted. The oracle for the
reader's default is therefore the writer's own `memory_md._memory_dir`: the expected value never
comes from `memory_retrieve`. The subprocess case is the observable one — a stage whose cwd is a
task worktree must see a base-only entry, not the worktree's stale branch copy.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

from harness_maker import memory_md
from harness_maker.memory_retrieve import resolve_memory_dir

settings.register_profile("ci", derandomize=True, max_examples=40, deadline=None)
settings.register_profile("dev", max_examples=200, deadline=None)
settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "ci"))

_NAME = st.from_regex(r"[a-z][a-z0-9-]{0,15}", fullmatch=True)
_SUBDIRS = st.lists(st.from_regex(r"[a-z][a-z0-9_]{0,8}", fullmatch=True), max_size=3)
_BASE = Path(tempfile.gettempdir()) / "hm-mcl-base"


@given(name=_NAME, subdirs=_SUBDIRS, in_worktree=st.booleans())
def test_ac_001_default_memory_dir_is_writer_root(
    name: str, subdirs: list[str], in_worktree: bool
) -> None:
    cwd = _BASE.joinpath(".worktrees", name, *subdirs) if in_worktree else _BASE
    resolved = resolve_memory_dir(None, cwd)
    assert resolved == memory_md._memory_dir(cwd)
    assert resolved == _BASE.resolve() / ".claude" / "memory"


def _seed_entry(root: Path, slug: str, body: str) -> None:
    memory_md.upsert_wiki(root, slug, "fact", body, today="2026-09-19")


def test_ac_001_worktree_cwd_recalls_a_base_only_entry(tmp_path: Path) -> None:
    base = tmp_path / "proj"
    (base / ".claude" / "memory").mkdir(parents=True)
    _seed_entry(base, "staging-api-rate-limit", "The staging gateway throttles at 10 req/s.")
    wt = base / ".worktrees" / "task-a"
    # The branch copy a worktree carries: same file, without the uncommitted capture.
    (wt / ".claude" / "memory").mkdir(parents=True)
    (wt / ".claude" / "memory" / "wiki.md").write_text(
        f"# Wiki Index\n\n{memory_md.OPEN_MARKER}\n{memory_md.CLOSE_MARKER}\n",
        encoding="utf-8",
    )
    out = subprocess.run(
        [sys.executable, "-m", "harness_maker.memory_retrieve", "--topic", "staging gateway"],
        cwd=wt,
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    )
    assert "staging-api-rate-limit" in out.stdout


def test_ac_002_explicit_memory_dir_wins(tmp_path: Path) -> None:
    worktree_cwd = tmp_path / "proj" / ".worktrees" / "task-a"
    explicit = Path("custom") / "memory"
    assert resolve_memory_dir(explicit, cwd=worktree_cwd) == explicit
    absolute = tmp_path / "elsewhere" / "memory"
    assert resolve_memory_dir(absolute, cwd=worktree_cwd) == absolute


def test_ac_002_explicit_memory_dir_is_what_the_cli_reads(tmp_path: Path) -> None:
    base = tmp_path / "proj"
    (base / ".claude" / "memory").mkdir(parents=True)
    _seed_entry(base, "base-only-entry", "Present only in the base tier.")
    other = tmp_path / "other"
    (other / ".claude" / "memory").mkdir(parents=True)
    _seed_entry(other, "other-only-entry", "Present only in the explicit tier.")
    wt = base / ".worktrees" / "task-a"
    wt.mkdir(parents=True)
    out = subprocess.run(
        [
            sys.executable,
            "-m",
            "harness_maker.memory_retrieve",
            "--topic",
            "present only tier",
            "--memory-dir",
            str(other / ".claude" / "memory"),
        ],
        cwd=wt,
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    )
    assert "other-only-entry" in out.stdout
    assert "base-only-entry" not in out.stdout


def test_d5_base_without_memory_dir_reports_the_base_path(tmp_path: Path) -> None:
    """Newly reachable window (Phase D.5): the base has no tier, only the worktree does.

    Before the fix the worktree copy was read; now the reader looks where the writer writes and
    finds nothing there. The contract is the module's existing graceful degrade — exit 0, a
    `memory dir does not exist` notice naming the BASE path — never a silent read of the copy.
    """
    base = tmp_path / "proj"
    wt = base / ".worktrees" / "task-a"
    (wt / ".claude" / "memory").mkdir(parents=True)
    memory_md_text = f"# Wiki Index\n\n{memory_md.OPEN_MARKER}\n{memory_md.CLOSE_MARKER}\n"
    (wt / ".claude" / "memory" / "wiki.md").write_text(memory_md_text, encoding="utf-8")
    out = subprocess.run(
        [sys.executable, "-m", "harness_maker.memory_retrieve", "--topic", "anything"],
        cwd=wt,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert out.returncode == 0
    expected = str(base.resolve() / ".claude" / "memory")
    assert f"memory dir does not exist: {expected}" in out.stderr
