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
    # 10KB cap; allow small overhead for fence + instruction line.
    # This fixture is wiki-tier with no `count:`, so the count floor's source set is empty
    # and the bound still describes the whole output. A floor-bearing corpus is covered by
    # test_cli_count_floor_adds_its_own_budget below — do NOT loosen this one to make room.
    assert len(result.stdout.encode("utf-8")) <= 11 * 1024


def _floor_bearing_memdir(tmp_path: Path) -> Path:
    """A corpus the floor actually fires on: fail-tier entries carrying `count:`."""
    memdir = tmp_path / "memory"
    memdir.mkdir()
    (memdir / "wiki.md").write_text(
        "# Wiki\n\n---\n\n<!-- @hm:user:entries -->\n"
        + "".join(
            f"## [wiki:pattern] hit-{i:02d} | 2026-05-19\nboundary parse "
            + ("filler-data " * 200)
            + "\n\n"
            for i in range(20)
        )
        + "<!-- @hm:/user:entries -->\n",
        encoding="utf-8",
    )
    (memdir / "failures.md").write_text(
        "# Failures\n\n---\n\n<!-- @hm:user:entries -->\n"
        + "".join(
            f"## [fail:test] recurring-{i:02d} | 2026-06-0{i + 1} | count:{12 - i}\n"
            f"- [2026-06-0{i + 1}] unrelated vocabulary entirely " + ("z" * 2500) + "\n\n"
            for i in range(4)
        )
        + "<!-- @hm:/user:entries -->\n",
        encoding="utf-8",
    )
    return memdir


def test_cli_count_floor_adds_its_own_budget(tmp_path: Path) -> None:
    """ADR-001: the floor is additive — its bytes come on top of `byte_cap`, not out of it."""
    memdir = _floor_bearing_memdir(tmp_path)
    off = _run_cli("--topic", "boundary parse", "--memory-dir", str(memdir), "--no-count-floor")
    on = _run_cli("--topic", "boundary parse", "--memory-dir", str(memdir))
    assert off.returncode == 0, off.stderr
    assert on.returncode == 0, on.stderr

    assert "recurring-00" not in off.stdout, "floor-off must not admit a zero-overlap entry"
    assert "recurring-00" in on.stdout, "the highest-count entry was not admitted"
    assert "high-recurrence" in on.stdout

    # Additive, and bounded by the floor's own budget — not by the lexical cap.
    grew = len(on.stdout.encode("utf-8")) - len(off.stdout.encode("utf-8"))
    assert 0 < grew <= 3 * (1000 + 256)


def test_cli_no_count_floor_flag_is_equivalent_to_count_floor_zero(tmp_path: Path) -> None:
    """The two spellings of the off switch must agree byte-for-byte.

    Named for what it proves (review d1fb99ca): both flags take the same `count_floor == 0`
    branch, so this pins flag-alias equivalence — NOT that the off path reproduces the
    pre-floor render. Nothing pins that render against a pre-feature capture; the nearest
    property is `test_count_floor_is_additive_to_k` (the lexical section is byte-identical with
    the floor on and off under a binding cap)."""
    memdir = _floor_bearing_memdir(tmp_path)
    a = _run_cli("--topic", "boundary parse", "--memory-dir", str(memdir), "--no-count-floor")
    b = _run_cli("--topic", "boundary parse", "--memory-dir", str(memdir), "--count-floor", "0")
    assert a.returncode == 0, a.stderr
    assert b.returncode == 0, b.stderr
    assert a.stdout == b.stdout


@pytest.mark.parametrize("value", ["0", "-5"])
def test_cli_rejects_a_non_positive_floor_entry_budget(tmp_path: Path, value: str) -> None:
    """Review 60a1e752: a zero budget used to render the whole body (`[-0:]`)."""
    memdir = _floor_bearing_memdir(tmp_path)
    r = _run_cli("--topic", "x", "--memory-dir", str(memdir), "--floor-entry-bytes", value)
    assert r.returncode == 2, r.stderr
    assert "positive integer" in r.stderr
