"""Phase 4 — ledger + JSONL adjudication store + CLI contract (SPEC AC-007, ADR-005/006/007)."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import timedelta
from pathlib import Path

import pytest

from harness_maker.delivery_metrics import main
from tests.unit._dm_git import ANCHOR, DMRepo

_NOW = ANCHOR.isoformat()


def _ambiguous_repo(tmp_path: Path) -> Path:
    """v1.0.0 at day 6 + tail `fix:` 2.4h later → exactly one candidate."""
    r = DMRepo(tmp_path / "ambig")
    r.commit("chore: initial", days_ago=40)
    r.commit("feat: alpha", days_ago=6)
    r.tag("v1.0.0", days_ago=6)
    r.commit("fix: subtle regression", days_ago=5.9)
    return r.root


def _ledger_rows(root: Path) -> list[dict[str, object]]:
    ledger = root / ".claude/observability/delivery-metrics.jsonl"
    if not ledger.is_file():
        return []
    rows = []
    for line in ledger.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def test_ledger_append_and_adjudication_reuse(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """AC-007: adjudicate once → verdict row persisted; a second run on
    unchanged history re-uses it (zero new adjudication requests) and appends
    a NEW snapshot row. Machine predicate: adjudication_requests(second_run) == 0."""
    root = _ambiguous_repo(tmp_path)

    assert main(["candidates", "--root", str(root), "--now", _NOW]) == 0
    first = json.loads(capsys.readouterr().out)
    assert len(first["candidates"]) == 1
    cand = first["candidates"][0]

    assert (
        main(
            [
                "adjudicate",
                "--root",
                str(root),
                "--commit",
                cand["commit_sha"],
                "--release",
                cand["release_ref"],
                "--verdict",
                "routine",
                "--reason",
                "scheduled cleanup, unrelated to the release",
            ]
        )
        == 0
    )
    capsys.readouterr()

    assert main(["compute", "--root", str(root), "--now", _NOW]) == 0
    snap1 = json.loads(capsys.readouterr().out)
    assert snap1["event"] == "snapshot"
    assert snap1["pending_adjudications"] == 0
    # ADR-005 nested snapshot schema: cfr {failed, total, unit, status, reason}.
    assert snap1["cfr"]["failed"] == 0
    assert snap1["cfr"]["total"] == 1
    assert snap1["cfr"]["unit"] == "tag"
    assert snap1["cfr"]["status"] == "ok"

    # Second run, unchanged history: candidates list is EMPTY (verdict reused).
    assert main(["candidates", "--root", str(root), "--now", _NOW]) == 0
    second = json.loads(capsys.readouterr().out)
    assert second["candidates"] == []  # zero new adjudication requests

    assert main(["compute", "--root", str(root), "--now", _NOW]) == 0
    capsys.readouterr()

    rows = _ledger_rows(root)
    assert sum(1 for r in rows if r["event"] == "adjudication") == 1
    assert sum(1 for r in rows if r["event"] == "snapshot") == 2


def test_compute_fail_closed_on_pending_exit_3(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """ADR-006: compute with unresolved candidates exits 3, lists them, and
    writes NO snapshot row (fail-closed)."""
    root = _ambiguous_repo(tmp_path)
    assert main(["compute", "--root", str(root), "--now", _NOW]) == 3
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "pending_adjudications"
    assert len(out["candidates"]) == 1
    assert _ledger_rows(root) == []


def test_compute_assume_routine_is_explicit_and_recorded(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """ADR-006 headless path: --assume-routine computes with pending candidates
    treated as routine (no failure), records how many were assumed, and does
    NOT write verdict rows (a later interactive run can still adjudicate)."""
    root = _ambiguous_repo(tmp_path)
    assert main(["compute", "--root", str(root), "--now", _NOW, "--assume-routine"]) == 0
    snap = json.loads(capsys.readouterr().out)
    assert snap["cfr"]["failed"] == 0  # ADR-005 nested schema
    assert snap["pending_adjudications"] == 1  # assumed, surfaced — not hidden
    rows = _ledger_rows(root)
    assert sum(1 for r in rows if r["event"] == "adjudication") == 0
    assert sum(1 for r in rows if r["event"] == "snapshot") == 1


def test_adjudication_reason_truncated_row_under_pipe_buf(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """ADR-005 byte-cap: an oversized reason is truncated deterministically and
    the serialized row stays <= 4096 bytes (single O_APPEND write)."""
    root = _ambiguous_repo(tmp_path)
    long_reason = "x" * 5000
    assert (
        main(
            [
                "adjudicate",
                "--root",
                str(root),
                "--commit",
                "a" * 40,
                "--release",
                "v1.0.0",
                "--verdict",
                "remediation",
                "--reason",
                long_reason,
            ]
        )
        == 0
    )
    capsys.readouterr()
    ledger = root / ".claude/observability/delivery-metrics.jsonl"
    line = ledger.read_text(encoding="utf-8").splitlines()[0]
    assert len(line.encode("utf-8")) <= 4096
    row = json.loads(line)
    assert len(row["reason"]) <= 200


def test_cli_exit_4_outside_git_repo(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    plain = tmp_path / "plain"
    plain.mkdir()
    assert main(["compute", "--root", str(plain), "--now", _NOW]) == 4
    capsys.readouterr()


def test_git_subprocess_failure_maps_to_exit_4(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """REVIEW re-review P2: a git subprocess OSError/TimeoutExpired (git binary
    missing, or a blame/log timeout on a huge repo) surfaces as the structured
    exit-4 error contract, never a raw traceback."""
    import subprocess as _sp

    root = _ambiguous_repo(tmp_path)

    def _boom(*_a: object, **_k: object) -> object:
        raise _sp.TimeoutExpired(cmd="git", timeout=60)

    monkeypatch.setattr("harness_maker.delivery_metrics.subprocess.run", _boom)
    assert main(["compute", "--root", str(root), "--now", _NOW]) == 4
    err = capsys.readouterr().err
    assert '"status": "error"' in err


def test_read_only_subcommands_never_write(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """AC-009 (0.36.0 — no disabled state): the read-only subcommands
    `candidates` and `trend` never append a ledger row; only `compute`
    (and `adjudicate`) write. So the feature is inert until the user asks
    for a snapshot — there is nothing to gate on."""
    root = _ambiguous_repo(tmp_path)
    assert main(["candidates", "--root", str(root), "--now", _NOW]) == 0
    capsys.readouterr()
    assert main(["trend", "--root", str(root)]) == 0
    capsys.readouterr()
    assert _ledger_rows(root) == []  # neither read-only command wrote anything


def test_legacy_enabled_key_still_runs(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """A 0.35.0-era harness.yaml carrying `delivery_metrics.enabled: false` no
    longer disables anything (the key was removed) — the command just runs,
    the stale key is dropped, tuning is honored."""
    root = _ambiguous_repo(tmp_path)
    cfg_dir = root / ".claude"
    cfg_dir.mkdir(exist_ok=True)
    (cfg_dir / "harness.yaml").write_text(
        "preset: Side\nlocale: en\ntargets: [claude-code]\ndelivery_metrics:\n"
        "  enabled: false\n  tag_pattern: 'v*'\n",
        encoding="utf-8",
    )
    assert main(["compute", "--root", str(root), "--now", _NOW, "--assume-routine"]) == 0
    snap = json.loads(capsys.readouterr().out)
    assert snap["event"] == "snapshot"


def test_trend_lists_snapshots_newest_first(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Two snapshots taken at different --now instants: trend must return the
    LATER one first — a raw-append (oldest-first) or shuffled ordering fails
    on the window_end comparison (test-reviewer R1: ordering must be asserted)."""
    root = _ambiguous_repo(tmp_path)
    earlier = (ANCHOR - timedelta(days=1)).isoformat()
    assert main(["compute", "--root", str(root), "--now", earlier, "--assume-routine"]) == 0
    capsys.readouterr()
    assert main(["compute", "--root", str(root), "--now", _NOW, "--assume-routine"]) == 0
    capsys.readouterr()
    assert main(["trend", "--root", str(root)]) == 0
    out = json.loads(capsys.readouterr().out)
    assert len(out["snapshots"]) == 2
    assert all(s["event"] == "snapshot" for s in out["snapshots"])
    # Newest first: the ANCHOR-run row precedes the ANCHOR-1d row.
    assert out["snapshots"][0]["window_end"] > out["snapshots"][1]["window_end"]


def test_e2e_module_invocation_from_foreign_cwd(tmp_path: Path) -> None:
    """CLAUDE.md checkpoint 8: one real subprocess boundary case — the module
    entrypoint works from an unrelated cwd with --root."""
    root = _ambiguous_repo(tmp_path)
    foreign = tmp_path / "elsewhere"
    foreign.mkdir()
    proc = subprocess.run(  # noqa: S603
        [
            sys.executable,
            "-m",
            "harness_maker.delivery_metrics",
            "candidates",
            "--root",
            str(root),
            "--now",
            _NOW,
        ],
        cwd=foreign,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert len(payload["candidates"]) == 1
