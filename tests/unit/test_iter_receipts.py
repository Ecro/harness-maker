"""Tests for harness_maker.iter_receipts — PLAN-loop-mid-stop-and-review-skip P1.

Covers ADR-004 (schema + module shape) and the Gate 0 contract surface
(read/list/verify) that ADR-001 depends on.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from harness_maker import iter_receipts
from harness_maker.iter_receipts import IterReceipt

# ── schema ──────────────────────────────────────────────────────────────────


def test_schema_accepts_valid_record() -> None:
    rec = IterReceipt(iter=1, stage="execute", verdict="pass", written_at="2026-05-23T05:00:00Z")
    assert rec.iter == 1
    assert rec.stage == "execute"
    assert rec.verdict == "pass"


def test_schema_rejects_extra_field() -> None:
    with pytest.raises(ValidationError):
        IterReceipt.model_validate(
            {
                "iter": 1,
                "stage": "execute",
                "verdict": "pass",
                "written_at": "2026-05-23T05:00:00Z",
                "extra_evil": "forge",
            }
        )


def test_schema_rejects_invalid_verdict() -> None:
    with pytest.raises(ValidationError):
        IterReceipt(iter=1, stage="execute", verdict="ok", written_at="2026-05-23T05:00:00Z")


def test_schema_rejects_zero_iter() -> None:
    with pytest.raises(ValidationError):
        IterReceipt(iter=0, stage="execute", verdict="pass", written_at="2026-05-23T05:00:00Z")


def test_schema_rejects_empty_stage() -> None:
    with pytest.raises(ValidationError):
        IterReceipt(iter=1, stage="", verdict="pass", written_at="2026-05-23T05:00:00Z")


@pytest.mark.parametrize(
    "evil_stage",
    [
        "../escape",
        "a/b",
        "..",
        ".hidden",
        "stage with space",
        "a\x00b",  # NUL byte
        "a%2Fb",  # percent-encoded slash
        "a\\b",  # backslash (Windows-style traversal)
    ],
)
def test_stage_name_rejects_path_unsafe(evil_stage: str) -> None:
    """Path traversal / non-alnum stage names must be rejected at write time.

    Even if pydantic accepts the schema field, write() applies a stricter
    filename-safe check so `<root>/.claude/.hm-iter-receipts/iter-N/<stage>.json`
    cannot escape the receipts directory.
    """
    with pytest.raises(ValueError, match="stage"):
        iter_receipts.write(
            iter=1,
            stage=evil_stage,
            verdict="pass",
            root=Path("/tmp/iter_receipts_test_unused"),
        )


# ── write / read / list ─────────────────────────────────────────────────────


def test_write_creates_expected_path(tmp_path: Path) -> None:
    path = iter_receipts.write(iter=3, stage="execute", verdict="pass", root=tmp_path)
    assert path == tmp_path / ".claude" / ".hm-iter-receipts" / "iter-3" / "execute.json"
    assert path.is_file()


def test_write_rejects_nonexistent_root(tmp_path: Path) -> None:
    # Guard against phantom/fabricated --root: atomic_write would otherwise
    # silently materialize a bogus receipts tree (review CR-3/CC-3).
    phantom = tmp_path / ".worktrees" / "execute-20260531T120000Z"
    with pytest.raises(ValueError, match="phantom worktree path"):
        iter_receipts.write(iter=1, stage="execute", verdict="pass", root=phantom)
    assert not phantom.exists()


def test_set_iter_marker_rejects_nonexistent_root(tmp_path: Path) -> None:
    phantom = tmp_path / ".worktrees" / "execute-20260531T120000Z"
    with pytest.raises(ValueError, match="phantom worktree path"):
        iter_receipts.set_iter_marker(iter=1, root=phantom)
    assert not phantom.exists()


def test_write_content_round_trips(tmp_path: Path) -> None:
    path = iter_receipts.write(iter=2, stage="review", verdict="fail", root=tmp_path)
    rec = iter_receipts.read(path)
    assert rec.iter == 2
    assert rec.stage == "review"
    assert rec.verdict == "fail"
    assert rec.written_at  # auto-stamped, non-empty


def test_write_is_atomic_against_concurrent_overwrite(tmp_path: Path) -> None:
    p1 = iter_receipts.write(iter=1, stage="execute", verdict="pass", root=tmp_path)
    p2 = iter_receipts.write(iter=1, stage="execute", verdict="fail", root=tmp_path)
    assert p1 == p2
    rec = iter_receipts.read(p1)
    assert rec.verdict == "fail"  # last write wins


def test_list_iter_returns_all_stages(tmp_path: Path) -> None:
    iter_receipts.write(iter=4, stage="execute", verdict="pass", root=tmp_path)
    iter_receipts.write(iter=4, stage="review", verdict="pass", root=tmp_path)
    iter_receipts.write(iter=5, stage="execute", verdict="pass", root=tmp_path)  # different iter
    found = iter_receipts.list_iter(iter=4, root=tmp_path)
    stages = sorted(r.stage for r in found)
    assert stages == ["execute", "review"]


def test_list_iter_empty_when_no_writes(tmp_path: Path) -> None:
    found = iter_receipts.list_iter(iter=99, root=tmp_path)
    assert found == []


def test_list_iter_ignores_non_json_files(tmp_path: Path) -> None:
    """Driver writes .current-iter alongside receipts; list_iter must skip it."""
    iter_receipts.write(iter=1, stage="execute", verdict="pass", root=tmp_path)
    iter_dir = tmp_path / ".claude" / ".hm-iter-receipts" / "iter-1"
    (iter_dir / ".current-iter").write_text("1")
    (iter_dir / "scratch.txt").write_text("ignore me")
    found = iter_receipts.list_iter(iter=1, root=tmp_path)
    assert [r.stage for r in found] == ["execute"]


def test_list_iter_skips_corrupt_receipt(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """Corrupt JSON in an iter dir must be skipped and surfaced via a log warning."""
    iter_receipts.write(iter=1, stage="execute", verdict="pass", root=tmp_path)
    iter_dir = tmp_path / ".claude" / ".hm-iter-receipts" / "iter-1"
    (iter_dir / "review.json").write_text("{this is not valid json")
    with caplog.at_level("WARNING", logger="harness_maker.iter_receipts"):
        found = iter_receipts.list_iter(iter=1, root=tmp_path)
    assert [r.stage for r in found] == ["execute"]
    assert any("review.json" in rec.message for rec in caplog.records)


# ── verify (Gate 0 surface) ─────────────────────────────────────────────────


def test_verify_all_pass(tmp_path: Path) -> None:
    iter_receipts.write(iter=1, stage="execute", verdict="pass", root=tmp_path)
    iter_receipts.write(iter=1, stage="review", verdict="pass", root=tmp_path)
    result = iter_receipts.verify(iter=1, expected_stages=["execute", "review"], root=tmp_path)
    assert result.all_passed is True
    assert result.missing == []
    assert result.non_pass == []


def test_verify_detects_missing_stage(tmp_path: Path) -> None:
    iter_receipts.write(iter=1, stage="execute", verdict="pass", root=tmp_path)
    # review never written
    result = iter_receipts.verify(iter=1, expected_stages=["execute", "review"], root=tmp_path)
    assert result.all_passed is False
    assert result.missing == ["review"]
    assert result.non_pass == []


def test_verify_detects_skipped_verdict_as_failure(tmp_path: Path) -> None:
    iter_receipts.write(iter=1, stage="execute", verdict="pass", root=tmp_path)
    iter_receipts.write(iter=1, stage="review", verdict="skipped", root=tmp_path)
    result = iter_receipts.verify(iter=1, expected_stages=["execute", "review"], root=tmp_path)
    assert result.all_passed is False
    assert result.missing == []
    assert result.non_pass == ["review"]


def test_verify_detects_fail_verdict_as_failure(tmp_path: Path) -> None:
    iter_receipts.write(iter=1, stage="execute", verdict="fail", root=tmp_path)
    iter_receipts.write(iter=1, stage="review", verdict="pass", root=tmp_path)
    result = iter_receipts.verify(iter=1, expected_stages=["execute", "review"], root=tmp_path)
    assert result.all_passed is False
    assert result.missing == []
    assert result.non_pass == ["execute"]


# ── PIPE_BUF guard ──────────────────────────────────────────────────────────


def test_write_rejects_oversize_stage_name() -> None:
    """stage max_length 64 enforced at schema layer."""
    long_stage = "a" * 65
    with pytest.raises(ValidationError):
        IterReceipt(iter=1, stage=long_stage, verdict="pass", written_at="2026-05-23T05:00:00Z")


# ── CLI ─────────────────────────────────────────────────────────────────────


def _run_cli(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "harness_maker.iter_receipts", *args],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
        cwd=str(cwd) if cwd else None,
    )


def test_cli_write_then_read_roundtrip(tmp_path: Path) -> None:
    r = _run_cli(
        "write",
        "--iter",
        "7",
        "--stage",
        "execute",
        "--verdict",
        "pass",
        "--root",
        str(tmp_path),
    )
    assert r.returncode == 0, r.stderr
    written_path = Path(r.stdout.strip())
    assert written_path.is_file()
    data = json.loads(written_path.read_text())
    assert data["iter"] == 7
    assert data["stage"] == "execute"
    assert data["verdict"] == "pass"


def _cli_write(tmp_path: Path, *, iter_n: int, stage: str, verdict: str) -> None:
    _run_cli(
        "write",
        "--iter",
        str(iter_n),
        "--stage",
        stage,
        "--verdict",
        verdict,
        "--root",
        str(tmp_path),
    )


def _cli_verify(tmp_path: Path, *, iter_n: int, expected: str) -> subprocess.CompletedProcess[str]:
    return _run_cli(
        "verify",
        "--iter",
        str(iter_n),
        "--expected",
        expected,
        "--root",
        str(tmp_path),
    )


def test_cli_verify_exit_code_pass(tmp_path: Path) -> None:
    _cli_write(tmp_path, iter_n=1, stage="execute", verdict="pass")
    _cli_write(tmp_path, iter_n=1, stage="review", verdict="pass")
    r = _cli_verify(tmp_path, iter_n=1, expected="execute,review")
    assert r.returncode == 0
    assert "PASS" in r.stdout or "pass" in r.stdout.lower()


def test_cli_verify_exit_code_fail(tmp_path: Path) -> None:
    _cli_write(tmp_path, iter_n=1, stage="execute", verdict="pass")
    # review missing
    r = _cli_verify(tmp_path, iter_n=1, expected="execute,review")
    assert r.returncode == 1
    assert "review" in r.stdout or "review" in r.stderr


def test_cli_rejects_invalid_verdict_from_stdin(tmp_path: Path) -> None:
    r = _run_cli(
        "write",
        "--iter",
        "1",
        "--stage",
        "execute",
        "--verdict",
        "great-job",
        "--root",
        str(tmp_path),
    )
    assert r.returncode != 0
