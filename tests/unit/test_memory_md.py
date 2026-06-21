"""Tests for harness_maker.memory_md — PLAN-multisession-fleet-reverify (H1).

The plain-markdown memory tiers (session/wiki/failures) must be written under a
flock so concurrent fleet sessions cannot clobber each other. Every read-modify-
write happens INSIDE the lock; the lock sentinel is a separate ``.lock`` file,
never the target ``.md`` (ADR-001/002). These tests are the H1 proof.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from harness_maker import memory_md

# ── lock-path helpers (ADR-002/005) ──────────────────────────────────────────


def test_lock_paths_are_separate_sentinels_not_the_target_md(tmp_path: Path) -> None:
    # ADR-002: lock the .lock sentinel, NEVER the target .md file.
    assert memory_md.session_lock_path(tmp_path).name == ".session.lock"
    assert memory_md.wiki_lock_path(tmp_path).name == ".wiki.lock"
    assert memory_md.failures_lock_path(tmp_path).name == ".failures.lock"
    for p in (
        memory_md.session_lock_path(tmp_path),
        memory_md.wiki_lock_path(tmp_path),
        memory_md.failures_lock_path(tmp_path),
    ):
        assert p.suffix == ".lock"
        assert not str(p).endswith(".md")


def test_lock_path_is_base_rooted_strips_worktree(tmp_path: Path) -> None:
    # ADR-005: session memory always targets the BASE repo, never a worktree copy.
    base = tmp_path
    wt = base / ".worktrees" / "execute-abc123-20260621T0000Z"
    wt.mkdir(parents=True)
    assert memory_md.session_lock_path(wt) == memory_md.session_lock_path(base)


def test_lock_path_byte_identical_from_differently_spelled_roots(tmp_path: Path) -> None:
    # ADR-005: CLI (--root) and hook (cwd) must compute the SAME resolved path.
    (tmp_path / "sub").mkdir()
    spelled_a = tmp_path
    spelled_b = tmp_path / "sub" / ".."
    assert memory_md.session_lock_path(spelled_a) == memory_md.session_lock_path(spelled_b)


# ── append-session ────────────────────────────────────────────────────────────


def test_append_session_creates_file_with_header_when_absent(tmp_path: Path) -> None:
    memory_md.append_session(tmp_path, "## [decision:x] first entry\nbody.", today="2026-06-21")
    log = tmp_path / ".claude" / "memory" / "session" / "2026-06-21.md"
    text = log.read_text(encoding="utf-8")
    assert "# Session Log — 2026-06-21" in text
    assert "first entry" in text


def test_append_session_accumulates_without_clobber(tmp_path: Path) -> None:
    memory_md.append_session(tmp_path, "## [decision:a] alpha", today="2026-06-21")
    memory_md.append_session(tmp_path, "## [decision:b] beta", today="2026-06-21")
    text = (tmp_path / ".claude" / "memory" / "session" / "2026-06-21.md").read_text("utf-8")
    assert "alpha" in text
    assert "beta" in text


def test_append_session_preserves_multiline_and_metachars(tmp_path: Path) -> None:
    body = "## [decision:m] x\nline `$(rm -rf /)` & ${HOME}\n- bullet\n  indented"
    memory_md.append_session(tmp_path, body, today="2026-06-21")
    text = (tmp_path / ".claude" / "memory" / "session" / "2026-06-21.md").read_text("utf-8")
    assert "`$(rm -rf /)` & ${HOME}" in text
    assert "  indented" in text


# ── upsert-wiki ───────────────────────────────────────────────────────────────


def _fresh_tier(path: Path, kind: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"# {kind} Index\n\n{memory_md.OPEN_MARKER}\n{memory_md.CLOSE_MARKER}\n",
        encoding="utf-8",
    )


def test_upsert_wiki_inserts_inside_marker_block(tmp_path: Path) -> None:
    wiki = tmp_path / ".claude" / "memory" / "wiki.md"
    _fresh_tier(wiki, "Wiki")
    memory_md.upsert_wiki(tmp_path, "my-slug", "pattern", "learned X.", today="2026-06-21")
    text = wiki.read_text("utf-8")
    open_i = text.index(memory_md.OPEN_MARKER)
    close_i = text.index(memory_md.CLOSE_MARKER)
    entry_i = text.index("[wiki:pattern] my-slug")
    assert open_i < entry_i < close_i  # entry landed INSIDE the block
    assert "learned X." in text


def test_upsert_wiki_same_slug_replaces_not_duplicates(tmp_path: Path) -> None:
    wiki = tmp_path / ".claude" / "memory" / "wiki.md"
    _fresh_tier(wiki, "Wiki")
    memory_md.upsert_wiki(tmp_path, "dup", "pattern", "first body.", today="2026-06-21")
    memory_md.upsert_wiki(tmp_path, "dup", "pattern", "second body.", today="2026-06-21")
    text = wiki.read_text("utf-8")
    assert text.count("] dup ") == 1  # exactly one heading with this slug
    assert "second body." in text
    assert "first body." not in text


def test_upsert_wiki_creates_block_when_file_absent(tmp_path: Path) -> None:
    # marker-absent-entirely (benign) → create block + warn, NOT fail.
    memory_md.upsert_wiki(tmp_path, "s", "pattern", "b.", today="2026-06-21")
    wiki = tmp_path / ".claude" / "memory" / "wiki.md"
    text = wiki.read_text("utf-8")
    assert memory_md.OPEN_MARKER in text
    assert memory_md.CLOSE_MARKER in text
    assert "[wiki:pattern] s" in text


# ── upsert-failure (count++) ─────────────────────────────────────────────────


def test_upsert_failure_new_entry_has_count_1(tmp_path: Path) -> None:
    fail = tmp_path / ".claude" / "memory" / "failures.md"
    _fresh_tier(fail, "Failures")
    memory_md.upsert_failure(tmp_path, "boom", "design", "it broke.", today="2026-06-21")
    text = fail.read_text("utf-8")
    assert "[fail:design] boom | 2026-06-21 | count:1" in text


def test_upsert_failure_same_slug_increments_count_and_preserves_first_date(
    tmp_path: Path,
) -> None:
    fail = tmp_path / ".claude" / "memory" / "failures.md"
    _fresh_tier(fail, "Failures")
    memory_md.upsert_failure(tmp_path, "boom", "design", "v1.", today="2026-06-20")
    memory_md.upsert_failure(tmp_path, "boom", "design", "v2.", today="2026-06-21")
    text = fail.read_text("utf-8")
    assert text.count("] boom ") == 1
    assert "count:2" in text
    assert "boom | 2026-06-20 | count:2" in text  # first-seen date preserved


# ── fail-closed set (ADR-001, validator W4/CX8) ──────────────────────────────


def test_failclosed_missing_close_marker(tmp_path: Path) -> None:
    wiki = tmp_path / ".claude" / "memory" / "wiki.md"
    wiki.parent.mkdir(parents=True)
    wiki.write_text(f"# Wiki\n\n{memory_md.OPEN_MARKER}\n## [wiki:x] a | d\nbody\n", "utf-8")
    with pytest.raises(memory_md.MemoryBlockError):
        memory_md.upsert_wiki(tmp_path, "b", "pattern", "x.", today="2026-06-21")


def test_failclosed_duplicate_open_marker(tmp_path: Path) -> None:
    wiki = tmp_path / ".claude" / "memory" / "wiki.md"
    wiki.parent.mkdir(parents=True)
    wiki.write_text(
        f"# Wiki\n\n{memory_md.OPEN_MARKER}\n{memory_md.OPEN_MARKER}\n{memory_md.CLOSE_MARKER}\n",
        "utf-8",
    )
    with pytest.raises(memory_md.MemoryBlockError):
        memory_md.upsert_wiki(tmp_path, "b", "pattern", "x.", today="2026-06-21")


def test_failclosed_duplicate_same_slug_already_present(tmp_path: Path) -> None:
    wiki = tmp_path / ".claude" / "memory" / "wiki.md"
    wiki.parent.mkdir(parents=True)
    wiki.write_text(
        f"# Wiki\n\n{memory_md.OPEN_MARKER}\n"
        "## [wiki:pattern] twice | 2026-06-01\nb1\n"
        "## [wiki:pattern] twice | 2026-06-02\nb2\n"
        f"{memory_md.CLOSE_MARKER}\n",
        "utf-8",
    )
    with pytest.raises(memory_md.MemoryBlockError):
        memory_md.upsert_wiki(tmp_path, "twice", "pattern", "x.", today="2026-06-21")


def test_failclosed_noninteger_count(tmp_path: Path) -> None:
    fail = tmp_path / ".claude" / "memory" / "failures.md"
    fail.parent.mkdir(parents=True)
    fail.write_text(
        f"# Failures\n\n{memory_md.OPEN_MARKER}\n"
        "## [fail:design] boom | 2026-06-01 | count:NaN\nbody\n"
        f"{memory_md.CLOSE_MARKER}\n",
        "utf-8",
    )
    with pytest.raises(memory_md.MemoryBlockError):
        memory_md.upsert_failure(tmp_path, "boom", "design", "x.", today="2026-06-21")


def test_failclosed_body_contains_marker_string(tmp_path: Path) -> None:
    wiki = tmp_path / ".claude" / "memory" / "wiki.md"
    _fresh_tier(wiki, "Wiki")
    with pytest.raises(memory_md.MemoryBlockError):
        memory_md.upsert_wiki(
            tmp_path, "s", "pattern", f"sneaky {memory_md.CLOSE_MARKER}", today="2026-06-21"
        )


# ── negative: unlocked RMW CAN lose an entry (participating-writers boundary) ──


def test_unlocked_rmw_loses_an_entry_deterministic(tmp_path: Path) -> None:
    """Documents ADR-004's boundary: a non-participating (unlocked) writer clobbers.

    Deterministic interleaving — no race timing. Two writers both read the same
    snapshot, then both write back; the second overwrites the first's entry.
    """
    log = tmp_path / "shared.md"
    log.write_text("base\n", "utf-8")
    snap_a = log.read_text("utf-8")
    snap_b = log.read_text("utf-8")  # both read the SAME stale snapshot
    log.write_text(snap_a + "entry-A\n", "utf-8")
    log.write_text(snap_b + "entry-B\n", "utf-8")  # clobbers A
    final = log.read_text("utf-8")
    assert "entry-B" in final
    assert "entry-A" not in final  # lost update — exactly the H1 hazard


# ── subprocess concurrency proof (ADR-004; validator W1/CX6/CX9) ──────────────


def _run_cli(args: list[str]) -> subprocess.Popen[bytes]:
    return subprocess.Popen(
        [sys.executable, "-m", "harness_maker.memory_md", *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


@pytest.mark.parametrize("n", [12])
def test_subprocess_concurrent_append_session_no_lost_update(tmp_path: Path, n: int) -> None:
    # N separate PROCESSES (not threads — flock is process-scoped) append
    # concurrently; the lock must serialize them so ALL entries survive.
    procs = [
        _run_cli(
            ["append-session", "--root", str(tmp_path), "--today", "2026-06-21", "--body", f"E{i}"]
        )
        for i in range(n)
    ]
    for p in procs:
        out, err = p.communicate(timeout=60)
        assert p.returncode == 0, err.decode()
    text = (tmp_path / ".claude" / "memory" / "session" / "2026-06-21.md").read_text("utf-8")
    for i in range(n):
        assert f"E{i}" in text, f"lost E{i} under concurrency"


@pytest.mark.parametrize("n", [12])
def test_subprocess_concurrent_upsert_wiki_distinct_slugs(tmp_path: Path, n: int) -> None:
    wiki = tmp_path / ".claude" / "memory" / "wiki.md"
    _fresh_tier(wiki, "Wiki")
    procs = [
        _run_cli(
            [
                "upsert-wiki",
                "--root",
                str(tmp_path),
                "--slug",
                f"slug{i}",
                "--category",
                "pattern",
                "--today",
                "2026-06-21",
                "--body",
                f"body{i}",
            ]
        )
        for i in range(n)
    ]
    for p in procs:
        out, err = p.communicate(timeout=60)
        assert p.returncode == 0, err.decode()
    text = wiki.read_text("utf-8")
    assert text.count(memory_md.CLOSE_MARKER) == 1  # marker discipline intact
    for i in range(n):
        assert f"slug{i}" in text, f"lost slug{i} under concurrency"


# ── CLI surface ───────────────────────────────────────────────────────────────


def test_cli_body_via_stdin(tmp_path: Path) -> None:
    p = subprocess.run(
        [
            sys.executable,
            "-m",
            "harness_maker.memory_md",
            "append-session",
            "--root",
            str(tmp_path),
            "--today",
            "2026-06-21",
        ],
        input=b"## [decision:s] from stdin\nbody",
        capture_output=True,
        timeout=60,
    )
    assert p.returncode == 0, p.stderr.decode()
    text = (tmp_path / ".claude" / "memory" / "session" / "2026-06-21.md").read_text("utf-8")
    assert "from stdin" in text


def test_cli_failclosed_returns_nonzero(tmp_path: Path) -> None:
    wiki = tmp_path / ".claude" / "memory" / "wiki.md"
    wiki.parent.mkdir(parents=True)
    wiki.write_text(f"# Wiki\n\n{memory_md.OPEN_MARKER}\nno close marker\n", "utf-8")
    p = subprocess.run(
        [
            sys.executable,
            "-m",
            "harness_maker.memory_md",
            "upsert-wiki",
            "--root",
            str(tmp_path),
            "--slug",
            "s",
            "--category",
            "pattern",
            "--body",
            "x",
        ],
        capture_output=True,
        timeout=60,
    )
    assert p.returncode != 0


# ── REVIEW round-2 regressions (consensus + Codex findings) ──────────────────


def test_upsert_wiki_rejects_heading_shaped_body(tmp_path: Path) -> None:
    # REVIEW P1 (security + code-reviewer): a `## [..]` line in the body would
    # become a phantom heading on the next upsert → silent truncation.
    wiki = tmp_path / ".claude" / "memory" / "wiki.md"
    _fresh_tier(wiki, "Wiki")
    with pytest.raises(memory_md.MemoryBlockError):
        memory_md.upsert_wiki(
            tmp_path, "s", "pattern", "see:\n## [wiki:x] victim ref", today="2026-06-21"
        )


def test_upsert_failure_rejects_heading_shaped_body(tmp_path: Path) -> None:
    fail = tmp_path / ".claude" / "memory" / "failures.md"
    _fresh_tier(fail, "Failures")
    with pytest.raises(memory_md.MemoryBlockError):
        memory_md.upsert_failure(
            tmp_path, "boom", "design", "## [fail:x] phantom", today="2026-06-21"
        )


def test_failclosed_markerless_nonempty_file(tmp_path: Path) -> None:
    # REVIEW Codex HIGH: a file with real content but no markers (corruption) must
    # NOT be silently split into unmanaged-old + managed-new halves.
    wiki = tmp_path / ".claude" / "memory" / "wiki.md"
    wiki.parent.mkdir(parents=True)
    wiki.write_text("# Wiki\n\n## [wiki:pattern] orphan | 2026-06-01\nold body\n", "utf-8")
    with pytest.raises(memory_md.MemoryBlockError):
        memory_md.upsert_wiki(tmp_path, "new", "pattern", "x.", today="2026-06-21")


@pytest.mark.parametrize("bad_slug", ["has space", "Upper", "a]b", "x|y", ""])
def test_upsert_rejects_invalid_slug(tmp_path: Path, bad_slug: str) -> None:
    # REVIEW P2 (code-reviewer): un-reparseable slug → silent duplicate.
    wiki = tmp_path / ".claude" / "memory" / "wiki.md"
    _fresh_tier(wiki, "Wiki")
    with pytest.raises(memory_md.MemoryBlockError):
        memory_md.upsert_wiki(tmp_path, bad_slug, "pattern", "x.", today="2026-06-21")


def test_upsert_rejects_invalid_category(tmp_path: Path) -> None:
    wiki = tmp_path / ".claude" / "memory" / "wiki.md"
    _fresh_tier(wiki, "Wiki")
    with pytest.raises(memory_md.MemoryBlockError):
        memory_md.upsert_wiki(tmp_path, "s", "a]b", "x.", today="2026-06-21")


@pytest.mark.parametrize("n", [12])
def test_subprocess_concurrent_upsert_failure_same_slug_count(tmp_path: Path, n: int) -> None:
    # REVIEW P1 (concurrency): same-slug count++ is the sharpest read-N→write-N+1
    # lost-update. N processes on the SAME slug must serialize to count:N exactly.
    fail = tmp_path / ".claude" / "memory" / "failures.md"
    _fresh_tier(fail, "Failures")
    procs = [
        _run_cli(
            [
                "upsert-failure",
                "--root",
                str(tmp_path),
                "--slug",
                "boom",
                "--category",
                "design",
                "--today",
                "2026-06-21",
                "--body",
                f"hit{i}",
            ]
        )
        for i in range(n)
    ]
    for p in procs:
        _out, err = p.communicate(timeout=60)
        assert p.returncode == 0, err.decode()
    text = fail.read_text("utf-8")
    assert text.count("] boom ") == 1  # single entry, no duplicates
    assert f"count:{n}" in text  # every increment landed (no lost update)
