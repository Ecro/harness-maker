"""Phase 3 + Phase 3-followup — ADR-004 Session UUID (dirname embed).

UUID is now embedded in worktree dirname (`execute-{uuid}-{ts}`) for
durable create→finalize→post-commit-pop binding. `_extract_uuid_from_wt_name`
parses it; `_owned_session_uuids` collects the set of UUIDs from active
`.claude/.hm-loop-*` marker filenames; post-commit-pop matches ref-files
against that set. The persistent-file approach (`_current_session_uuid`)
is kept only for back-compat with refs from pre-dirname-embed code paths.

REVIEW round 1 P0-MAN2 closure: cross-session isolation now ACTUALLY fires.
"""

from __future__ import annotations

import re
from pathlib import Path

from harness_maker.worktree import (
    _LOOP_MARKER_DIR,
    _LOOP_MARKER_PREFIX,
    _current_session_uuid,
    _extract_uuid_from_wt_name,
    _owned_session_uuids,
    _session_owns_marker,
)

# ── _extract_uuid_from_wt_name (new — dirname parser) ──────────────────────


def test_extract_uuid_from_new_format() -> None:
    """`execute-{12hex}-{ts}` → returns 12hex UUID."""
    assert _extract_uuid_from_wt_name("execute-aabbccddeeff-20260523T1336Z") == "aabbccddeeff"


def test_extract_uuid_from_legacy_format() -> None:
    """Pre-dirname-embed format `execute-{ts}` → empty (not owned by anyone)."""
    assert _extract_uuid_from_wt_name("execute-20260523T1336Z") == ""


def test_extract_uuid_from_multi_repo_sibling_format() -> None:
    """`execute-{uuid}-{ts}-{sibling-slug}` matches when slug looks like dedup digits."""
    # The regex allows optional `-{dedup}\d+` suffix. Sibling slugs aren't pure
    # digits — those become a no-match (returns empty); a sibling-aware test
    # would extend the regex. Acceptable for now: parse-fail = "not owned",
    # which is the safe default.
    assert _extract_uuid_from_wt_name("execute-aabbccddeeff-20260523T1336Z-1") == "aabbccddeeff"


def test_extract_uuid_from_malformed() -> None:
    for bad in ("", "random", "execute-only", "execute-INVALID-20260523T1336Z"):
        assert _extract_uuid_from_wt_name(bad) == ""


def test_extract_uuid_from_other_workflow() -> None:
    """Workflow prefix is permissive — any kebab-case prefix works."""
    assert _extract_uuid_from_wt_name("plan-aabbccddeeff-20260523T1336Z") == "aabbccddeeff"


# ── _owned_session_uuids (new — set from active loop markers) ──────────────


def test_owned_session_uuids_empty_when_no_markers(tmp_path: Path) -> None:
    assert _owned_session_uuids(tmp_path) == set()


def test_owned_session_uuids_collects_from_active_markers(tmp_path: Path) -> None:
    cd = tmp_path / _LOOP_MARKER_DIR
    cd.mkdir()
    # Two active sessions A and B
    (cd / f"{_LOOP_MARKER_PREFIX}execute-aaaaaaaaaaaa-20260523T1336Z").write_text("x")
    (cd / f"{_LOOP_MARKER_PREFIX}execute-bbbbbbbbbbbb-20260523T1337Z").write_text("x")
    assert _owned_session_uuids(tmp_path) == {"aaaaaaaaaaaa", "bbbbbbbbbbbb"}


def test_owned_session_uuids_excludes_legacy_format_markers(tmp_path: Path) -> None:
    """Legacy wt names without UUID don't contribute to owned set —
    safe default (refs from those wts can't claim ownership)."""
    cd = tmp_path / _LOOP_MARKER_DIR
    cd.mkdir()
    (cd / f"{_LOOP_MARKER_PREFIX}execute-20260523T1336Z").write_text("x")
    (cd / f"{_LOOP_MARKER_PREFIX}execute-aaaaaaaaaaaa-20260523T1337Z").write_text("x")
    assert _owned_session_uuids(tmp_path) == {"aaaaaaaaaaaa"}


def test_owned_session_uuids_skips_non_marker_files(tmp_path: Path) -> None:
    cd = tmp_path / _LOOP_MARKER_DIR
    cd.mkdir()
    (cd / f"{_LOOP_MARKER_PREFIX}execute-aaaaaaaaaaaa-20260523T1336Z").write_text("x")
    (cd / "harness.yaml").write_text("preset: Side")
    (cd / ".hm-finalize-stash-execute-xyz").write_text("x")
    assert _owned_session_uuids(tmp_path) == {"aaaaaaaaaaaa"}


# ── _current_session_uuid (legacy back-compat) ─────────────────────────────


def test_current_session_uuid_is_12_hex_chars(tmp_path: Path) -> None:
    """Legacy helper still works — used only by _write_stash_ref_file's
    fallback path when wt_name has no embedded UUID."""
    uuid = _current_session_uuid(tmp_path)
    assert re.fullmatch(r"[0-9a-f]{12}", uuid)


def test_current_session_uuid_stable_across_calls(tmp_path: Path) -> None:
    a = _current_session_uuid(tmp_path)
    b = _current_session_uuid(tmp_path)
    assert a == b


# ── _session_owns_marker (helper kept for back-compat unit semantics) ──────


def test_session_owns_marker_matching_uuid_returns_true() -> None:
    assert _session_owns_marker("aabbccddeeff", "aabbccddeeff") is True


def test_session_owns_marker_mismatched_uuid_returns_false() -> None:
    assert _session_owns_marker("aabbccddeeff", "001122334455") is False


def test_session_owns_marker_empty_ref_uuid_returns_false() -> None:
    assert _session_owns_marker("", "aabbccddeeff") is False


# ── owned-uuids CLI (task #14 — HM_OWNED_SESSION_UUIDS env source) ─────────


def test_owned_uuids_cli_empty(tmp_path: Path) -> None:
    """No markers → prints empty CSV (single newline)."""
    import subprocess
    import sys

    proc = subprocess.run(
        [sys.executable, "-m", "harness_maker.worktree", "owned-uuids", str(tmp_path)],
        capture_output=True,
        text=True,
        check=True,
    )
    assert proc.stdout.strip() == ""


def test_owned_uuids_cli_csv_sorted(tmp_path: Path) -> None:
    """Multiple markers → CSV sorted by UUID."""
    import subprocess
    import sys

    cd = tmp_path / _LOOP_MARKER_DIR
    cd.mkdir()
    (cd / f"{_LOOP_MARKER_PREFIX}execute-bbbbbbbbbbbb-20260524T0100Z").write_text("x")
    (cd / f"{_LOOP_MARKER_PREFIX}execute-aaaaaaaaaaaa-20260524T0101Z").write_text("x")
    proc = subprocess.run(
        [sys.executable, "-m", "harness_maker.worktree", "owned-uuids", str(tmp_path)],
        capture_output=True,
        text=True,
        check=True,
    )
    assert proc.stdout.strip() == "aaaaaaaaaaaa,bbbbbbbbbbbb"


def test_owned_uuids_cli_excludes_legacy_markers(tmp_path: Path) -> None:
    """Legacy wt names without UUID → omitted (already covered by helper test;
    this asserts CLI surface."""
    import subprocess
    import sys

    cd = tmp_path / _LOOP_MARKER_DIR
    cd.mkdir()
    (cd / f"{_LOOP_MARKER_PREFIX}execute-20260524T0100Z").write_text("x")
    (cd / f"{_LOOP_MARKER_PREFIX}execute-aaaaaaaaaaaa-20260524T0101Z").write_text("x")
    proc = subprocess.run(
        [sys.executable, "-m", "harness_maker.worktree", "owned-uuids", str(tmp_path)],
        capture_output=True,
        text=True,
        check=True,
    )
    assert proc.stdout.strip() == "aaaaaaaaaaaa"
