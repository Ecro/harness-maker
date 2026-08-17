"""PLAN-layer3-per-session-ownership Phase 1 — per-session owned-uuid sourcing.

The create-time/wrapup `post-commit-pop` owned-set was sourced from all sessions'
markers (`owned-uuids`), so a session popped peers' deferred stashes. This phase
adds (a) `wt-uuid` (parse the per-session uuid from an `execute-<uuid>-<ts>` path),
(b) a slug-keyed crumb so a standalone/recovered wrapup recovers its own uuid
machine-derived, and (c) drops the `owned_uuids and` short-circuit so an EMPTY
owned-set fail-safe-skips a uuid'd ref instead of popping it. ADR-004 boundedness:
the ref writer always stamps a uuid derived from the dirname.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from harness_maker.worktree import (
    _cli_owned_crumb_add,
    _cli_owned_crumb_clear,
    _cli_owned_crumb_read,
    _cli_wt_uuid,
    _owned_crumb_read,
    _read_stash_ref_file,
    _validate_stash_ref_fields,
    _write_stash_ref_file,
)

_EXEC = "execute-deadbeef1234-20260621T0000Z"
_EXEC2 = "execute-444455556666-20260621T0001Z"


# ── wt-uuid CLI ──────────────────────────────────────────────────────────────


def test_wt_uuid_parses_execute_name(capsys: pytest.CaptureFixture[str]) -> None:
    rc = _cli_wt_uuid([f"/a/b/.worktrees/{_EXEC}"])
    assert rc == 0
    assert capsys.readouterr().out.strip() == "deadbeef1234"


def test_wt_uuid_slug_name_empty_with_stderr_warn(capsys: pytest.CaptureFixture[str]) -> None:
    """A flag-on `.worktrees/<slug>` task path has no uuid → empty stdout + warn."""
    rc = _cli_wt_uuid(["/a/b/.worktrees/myslug"])
    out = capsys.readouterr()
    assert rc == 0
    assert out.out.strip() == ""
    assert "myslug" in out.err or "no uuid" in out.err.lower()


def test_wt_uuid_multi_csv(capsys: pytest.CaptureFixture[str]) -> None:
    rc = _cli_wt_uuid([_EXEC, _EXEC2])
    assert rc == 0
    assert capsys.readouterr().out.strip() == "deadbeef1234,444455556666"


def test_wt_uuid_nonexistent_path_ok(capsys: pytest.CaptureFixture[str]) -> None:
    """Pure string parse — the path need not exist on disk (wrapup post-cleanup)."""
    rc = _cli_wt_uuid([f"/gone/.worktrees/{_EXEC}"])
    assert rc == 0
    assert capsys.readouterr().out.strip() == "deadbeef1234"


# ── slug crumb ───────────────────────────────────────────────────────────────


def test_owned_crumb_roundtrip_and_dedup(tmp_path: Path) -> None:
    (tmp_path / ".claude").mkdir()
    assert _cli_owned_crumb_add([str(tmp_path), "myslug", "deadbeef1234"]) == 0
    assert _cli_owned_crumb_add([str(tmp_path), "myslug", "444455556666"]) == 0
    assert _cli_owned_crumb_add([str(tmp_path), "myslug", "deadbeef1234"]) == 0  # dedup
    assert _owned_crumb_read(tmp_path, "myslug") == ["444455556666", "deadbeef1234"]


def test_owned_crumb_read_absent_empty(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (tmp_path / ".claude").mkdir()
    assert _cli_owned_crumb_read([str(tmp_path), "absent"]) == 0
    assert capsys.readouterr().out.strip() == ""


def test_owned_crumb_clear(tmp_path: Path) -> None:
    (tmp_path / ".claude").mkdir()
    _cli_owned_crumb_add([str(tmp_path), "myslug", "deadbeef1234"])
    assert _owned_crumb_read(tmp_path, "myslug") == ["deadbeef1234"]
    assert _cli_owned_crumb_clear([str(tmp_path), "myslug"]) == 0
    assert _owned_crumb_read(tmp_path, "myslug") == []


def test_owned_crumb_slug_keyed_isolation(tmp_path: Path) -> None:
    """Distinct slugs write distinct crumbs — peer tasks never share an owned set."""
    (tmp_path / ".claude").mkdir()
    _cli_owned_crumb_add([str(tmp_path), "slugA", "aaaaaaaaaaaa"])
    _cli_owned_crumb_add([str(tmp_path), "slugB", "bbbbbbbbbbbb"])
    assert _owned_crumb_read(tmp_path, "slugA") == ["aaaaaaaaaaaa"]
    assert _owned_crumb_read(tmp_path, "slugB") == ["bbbbbbbbbbbb"]


# ── ADR-004: writer always stamps a uuid for a standard worktree name ─────────


def test_writer_always_stamps_session_uuid(tmp_path: Path) -> None:
    """Bounds the legacy no-uuid fallback to genuinely pre-upgrade refs: a current
    `execute-<uuid>-<ts>` worktree name always yields a non-empty session_uuid
    (the writer derives it from the dirname)."""
    base = tmp_path
    (base / ".claude").mkdir()
    marker = base / ".claude" / f".hm-loop-{_EXEC}"
    marker.write_text(f"{base}\n", encoding="utf-8")
    _write_stash_ref_file(base, _EXEC, "a" * 40, marker)
    ref = base / ".claude" / f".hm-finalize-stash-{_EXEC}"
    fields = _validate_stash_ref_fields(_read_stash_ref_file(ref))
    assert fields is not None
    assert fields["session_uuid"] == "deadbeef1234"


def test_writer_legacy_bare_timestamp_empty_session_uuid(tmp_path: Path) -> None:
    """REVIEW P1: a legacy bare-timestamp worktree name (no embedded uuid) must
    write an EMPTY session_uuid so the ref falls through to post-commit-pop's
    marker fallback (its old owner-pops-own behavior) — NOT a `_current_session_uuid`
    value that `wt-uuid` can't reproduce into the crumb (which would strand the
    owner's own legacy stash)."""
    base = tmp_path
    (base / ".claude").mkdir()
    legacy = "execute-20260101T0000Z"  # no -<uuid>- segment
    marker = base / ".claude" / f".hm-loop-{legacy}"
    marker.write_text(f"{base}\n", encoding="utf-8")
    _write_stash_ref_file(base, legacy, "a" * 40, marker)
    fields = _read_stash_ref_file(base / ".claude" / f".hm-finalize-stash-{legacy}")
    assert fields.get("session_uuid", "") == "", (
        "legacy bare-timestamp ref must carry an empty session_uuid (marker-fallback path)"
    )


def test_crumb_cli_rejects_empty_slug(tmp_path: Path) -> None:
    """REVIEW P2: an empty <slug> (missed substitution) must be rejected, not write a
    shared `.hm-owned-uuids-` crumb across unrelated tasks."""
    from harness_maker.worktree import _cli_owned_crumb_add, _cli_owned_crumb_read

    (tmp_path / ".claude").mkdir()
    assert _cli_owned_crumb_add([str(tmp_path), "", "deadbeef1234"]) == 2
    assert _cli_owned_crumb_add([str(tmp_path), "  ", "deadbeef1234"]) == 2
    assert _cli_owned_crumb_read([str(tmp_path), ""]) == 2
    assert not list((tmp_path / ".claude").glob(".hm-owned-uuids-*")), (
        "no crumb may be written for an empty slug"
    )
