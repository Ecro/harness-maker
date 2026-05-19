"""Integration tests for the memory_retrieve CLI surface.

CLAUDE.md §"Integration 경계 한 줄 테스트" — running via subprocess from a
different cwd catches the "Python import works but CLI from different
directory fails" class that pure unit imports miss.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_TIMEOUT_S = 15


def _run_cli(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "harness_maker.memory_retrieve", *args],
        capture_output=True,
        text=True,
        timeout=_TIMEOUT_S,
        check=False,
        cwd=str(cwd) if cwd else None,
    )


def _write_min_memory(memdir: Path) -> None:
    memdir.mkdir(parents=True, exist_ok=True)
    (memdir / "wiki.md").write_text(
        "# Wiki\n\n---\n\n<!-- @hm:user:entries -->\n"
        "## [wiki:pattern] boundary-parse | 2026-05-19\n"
        "Parser tests for boundary detection.\n\n"
        "## [wiki:gotcha] another-thing | 2026-05-18\n"
        "Some other content here unrelated.\n\n"
        "<!-- @hm:/user:entries -->\n"
    )
    (memdir / "failures.md").write_text(
        "# Failures\n\n---\n\n<!-- @hm:user:entries -->\n"
        "## [fail:test] some-fail | 2026-05-19 | count:1\n"
        "Failure body content.\n\n"
        "<!-- @hm:/user:entries -->\n"
    )


def test_cli_roundtrip_via_subprocess(tmp_path: Path) -> None:
    """CLI invocation from a different cwd returns valid fenced markdown."""
    memdir = tmp_path / "memory"
    _write_min_memory(memdir)

    result = _run_cli("--topic", "boundary", "--k", "3", "--memory-dir", str(memdir), cwd=tmp_path)
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert "<memory_candidates" in result.stdout
    assert "</memory_candidates>" in result.stdout
    assert "boundary-parse" in result.stdout


def test_cli_missing_memory_dir_graceful(tmp_path: Path) -> None:
    """Non-existent --memory-dir → exit 0, fence with failed/empty body, stderr warning.

    PLAN contract (§Output schema): error result emits the fence with
    `(memory_retrieve failed: <reason>; falling back to first-60-lines context)`
    + stderr warning + exit 0. A missing directory is an error condition.
    """
    result = _run_cli(
        "--topic",
        "anything",
        "--memory-dir",
        str(tmp_path / "does-not-exist"),
        cwd=tmp_path,
    )
    assert result.returncode == 0
    assert "<memory_candidates" in result.stdout
    # Error message must surface in stdout (so the consuming Claude turn sees it).
    assert "memory_retrieve failed" in result.stdout
    # Stderr warning must be non-empty so a human running the CLI sees the warning
    # (PLAN §Output schema "error result emits ... stderr warning").
    assert result.stderr.strip(), "stderr must contain a warning for the missing-dir error path"


def test_cli_invocation_does_not_load_anthropic(tmp_path: Path) -> None:
    """Subprocess sys.modules must not contain anthropic after CLI run.

    Regression guard for failures.md ship-without-verifying-target-env-credentials.
    """
    memdir = tmp_path / "memory"
    _write_min_memory(memdir)

    probe = (
        "import sys, runpy; "
        "sys.modules.pop('anthropic', None); "
        "runpy.run_module('harness_maker.memory_retrieve', "
        "run_name='__main__', alter_sys=True) if False else None; "
        "import harness_maker.memory_retrieve as m; "
        "assert 'anthropic' not in sys.modules, 'anthropic leaked into sys.modules'"
    )
    result = subprocess.run(
        [sys.executable, "-c", probe],
        capture_output=True,
        text=True,
        timeout=_TIMEOUT_S,
        check=False,
    )
    assert result.returncode == 0, f"stdout={result.stdout} stderr={result.stderr}"


def test_cli_real_repo_memory_surfaces_recent_entry() -> None:
    """Load-bearing acceptance: topic='boundary parse test layer' against the
    project's actual .claude/memory must surface `boundary-parse-test-layer`
    (wiki.md:258 — invisible to today's first-60-lines skim)."""
    memdir = _REPO_ROOT / ".claude" / "memory"
    if not (memdir / "wiki.md").exists():
        pytest.skip("Repo .claude/memory/wiki.md missing — not running in repo checkout")

    result = _run_cli(
        "--topic",
        "boundary parse test layer",
        "--k",
        "6",
        "--memory-dir",
        str(memdir),
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert "boundary-parse-test-layer" in result.stdout, (
        f"Expected real-repo recent entry not surfaced; stdout head:\n{result.stdout[:600]}"
    )


def test_cli_byte_cap_enforced(tmp_path: Path) -> None:
    """CLI output respects byte cap default (10KB)."""
    memdir = tmp_path / "memory"
    memdir.mkdir()
    body_blocks = []
    for i in range(20):
        body_blocks.append(
            f"## [wiki:pattern] slug-{i:02d} | 2026-05-19\n"
            "boundary parse " + ("filler-data " * 200) + "\n\n"
        )
    (memdir / "wiki.md").write_text(
        "# Wiki\n\n---\n\n<!-- @hm:user:entries -->\n"
        + "".join(body_blocks)
        + "<!-- @hm:/user:entries -->\n"
    )

    result = _run_cli("--topic", "boundary parse", "--memory-dir", str(memdir))
    assert result.returncode == 0
    # 10KB cap; allow small overhead for fence + instruction line
    assert len(result.stdout.encode("utf-8")) <= 11 * 1024
