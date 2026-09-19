"""Phase 1/5 — the backlog seam degrades without halting, in its shipped spelling.

Salvage (ADR-007): wrapup now reads `hm proposals summary` (one JSON object), not
`count --open`. `count` keeps its bare-integer contract and its tests below; the `summary`
states the CLI OWNS are driven at the bottom. Caller-side branches stay render-asserted
(`test_render_wrapup_backlog_warning.py`) — see the scope note that follows.

Phase D.5's newly-reachable window: wrapup now runs a subprocess and parses its stdout as an
integer. Before this phase, none of that subprocess's failure states existed in wrapup at all.
A render-grep asserts the *instruction* is present; it never enters the window.

**Scope, stated honestly.** Every input state the CLI owns is driven here. For a readable
backlog — absent, empty, malformed, any size — the invariant the template depends on holds:
**exit 0 and a well-formed payload on stdout.** One owned state does exit non-zero, on
purpose: a backlog that exists but cannot be read (not UTF-8, no permission) prints ONE stderr
line and exits 1 rather than reporting `open: 0`, which would hide the very file this reader
surfaces (review 7edb61e2 — an earlier version of this note claimed no non-zero path existed,
and a non-UTF-8 file produced a raw traceback). "Executable missing" and "a pre-release plugin
without the verb" are properties of the caller's environment, not of this command; those stay
render-asserted prose in `test_render_wrapup_backlog_warning.py`.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

CMD = [sys.executable, "-m", "harness_maker.proposals"]


def _count(path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [*CMD, "count", "--open", "--file", str(path)],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


def _assert_bare_integer(result: subprocess.CompletedProcess[str]) -> int:
    """The template reads this value; anything but exit-0-plus-an-int breaks the warning."""
    assert result.returncode == 0, f"exit {result.returncode}, stderr={result.stderr!r}"
    out = result.stdout.strip()
    assert out.isdigit(), f"stdout is not a bare integer: {out!r}"
    return int(out)


def test_absent_backlog_counts_zero_and_exits_clean(tmp_path: Path) -> None:
    """Absent-case (CLAUDE.md count:8): a project with no backlog is not an error."""
    assert _assert_bare_integer(_count(tmp_path / "does-not-exist.md")) == 0


def test_directory_in_place_of_the_backlog_does_not_raise(tmp_path: Path) -> None:
    """A path that exists but is not a file is a real state on a half-migrated project."""
    d = tmp_path / "pending-proposals.md"
    d.mkdir()
    assert _assert_bare_integer(_count(d)) == 0


def test_empty_backlog_counts_zero(tmp_path: Path) -> None:
    p = tmp_path / "b.md"
    p.write_text("", encoding="utf-8")
    assert _assert_bare_integer(_count(p)) == 0


def test_malformed_markdown_still_yields_an_integer(tmp_path: Path) -> None:
    """Truncated table, unclosed backtick, heading with no body — none may crash the count."""
    p = tmp_path / "b.md"
    p.write_text(
        "## RESOLVED 2026-01-01 — batch\n\n| Retired |\n|---|\n| `a`, `b\n\n"
        "## Proposal:\n\n## Proposal: real-one (2026-01-02)\n",
        encoding="utf-8",
    )
    # `## Proposal:` with an empty name contributes nothing; `real-one` is the only open name.
    assert _assert_bare_integer(_count(p)) == 1


def test_below_threshold_and_at_threshold_are_both_representable(tmp_path: Path) -> None:
    """The template branches on >= 5; both sides must be reachable from real input."""
    p = tmp_path / "b.md"
    p.write_text(
        "".join(f"## Proposal: p{i} (2026-01-01)\n\nbody\n\n" for i in range(4)), encoding="utf-8"
    )
    assert _assert_bare_integer(_count(p)) == 4
    p.write_text(
        "".join(f"## Proposal: p{i} (2026-01-01)\n\nbody\n\n" for i in range(6)), encoding="utf-8"
    )
    assert _assert_bare_integer(_count(p)) == 6


@pytest.mark.parametrize("sub", ["list", "count"])
def test_no_subcommand_flags_defaults_to_open(tmp_path: Path, sub: str) -> None:
    """`--open` is the default; a template that omits it must not get triaged results."""
    p = tmp_path / "b.md"
    p.write_text("## Proposal: only-open (2026-01-01)\n\nbody\n", encoding="utf-8")
    result = subprocess.run(
        [*CMD, sub, "--file", str(p)], capture_output=True, text=True, timeout=60, check=False
    )
    assert result.returncode == 0, result.stderr
    assert "only-open" in result.stdout or result.stdout.strip() == "1"


# --------------------------------------------------------------------------------------
# `summary` — the call wrapup's main loop actually makes (ADR-006/007)
# --------------------------------------------------------------------------------------


def _summary(path: Path) -> dict[str, object]:
    """The template parses exactly this: exit 0 and one JSON object with an integer `open`."""
    result = subprocess.run(
        [*CMD, "summary", "--file", str(path)],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, f"exit {result.returncode}, stderr={result.stderr!r}"
    lines = [ln for ln in result.stdout.splitlines() if ln.strip()]
    assert len(lines) == 1, f"expected one JSON line, got {result.stdout!r}"
    payload = json.loads(lines[0])
    assert isinstance(payload, dict)
    assert isinstance(payload["open"], int)
    assert not isinstance(payload["open"], bool)
    return payload


def _proposals(n: int, date: str | None = "2026-01-01") -> str:
    suffix = f" ({date})" if date else ""
    return "".join(f"## Proposal: p{i}{suffix}\n\nbody\n\n" for i in range(n))


def test_summary_absent_backlog_is_an_empty_state_not_a_failure(tmp_path: Path) -> None:
    """ADR-007 (codex 76c01355): no backlog file = open 0, which prints nothing (0 < 5)."""
    assert _summary(tmp_path / "does-not-exist.md") == {"open": 0, "oldest": None}


def test_summary_empty_backlog(tmp_path: Path) -> None:
    p = tmp_path / "b.md"
    p.write_text("", encoding="utf-8")
    assert _summary(p) == {"open": 0, "oldest": None}


@pytest.mark.parametrize("n", [4, 5], ids=["below-threshold", "at-threshold"])
def test_summary_both_sides_of_the_threshold(tmp_path: Path, n: int) -> None:
    """The template branches on >= 5; exactly 4 and exactly 5 must both be reachable."""
    p = tmp_path / "b.md"
    p.write_text(_proposals(n), encoding="utf-8")
    assert _summary(p) == {"open": n, "oldest": "2026-01-01"}


def test_summary_undated_open_proposals_yield_null_oldest(tmp_path: Path) -> None:
    """The warning drops its `(oldest …)` part rather than printing a fabricated date."""
    p = tmp_path / "b.md"
    p.write_text(_proposals(6, date=None), encoding="utf-8")
    assert _summary(p) == {"open": 6, "oldest": None}


@pytest.mark.parametrize("sub", ["count", "summary"])
def test_unreadable_backlog_fails_loudly_in_one_line(tmp_path: Path, sub: str) -> None:
    """Review 7edb61e2: a backlog that exists but is not UTF-8 is a failure, never `open: 0`.

    One stderr line and exit 1 is the shape wrapup's degrade contract turns into a single
    notice; a traceback is not, and a silent zero would hide the file.
    """
    p = tmp_path / "b.md"
    p.write_bytes(b"## Proposal: broken \xff\xfe (2026-01-01)\n")
    extra = ["--open"] if sub == "count" else []
    result = subprocess.run(
        [*CMD, sub, *extra, "--file", str(p)],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 1, result.stdout
    assert result.stdout == ""
    lines = [ln for ln in result.stderr.splitlines() if ln.strip()]
    assert len(lines) == 1, result.stderr
    assert lines[0].startswith("hm proposals: cannot read")
    assert "Traceback" not in result.stderr
