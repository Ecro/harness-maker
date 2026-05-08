"""Tests for tool cascade firewall (Phase 7)."""

from __future__ import annotations

import json
import multiprocessing as mp
from pathlib import Path

from harness_maker.tool_cascade import RecoveryAction, ToolCascade


def _cascade_worker(log_path: str, worker_id: int, n: int) -> None:
    """Top-level worker for multiprocessing.Process."""
    cascade = ToolCascade(max_retries=10, log_path=Path(log_path))
    for i in range(n):
        cascade.on_failure(f"tool-{worker_id}-{i}", f"err-{i}")


def test_retry_on_first_failure() -> None:
    cascade = ToolCascade(max_retries=3)
    action, target = cascade.on_failure("Bash", "timeout")
    assert action == RecoveryAction.RETRY
    assert target == "Bash"


def test_retry_three_times_then_abort() -> None:
    cascade = ToolCascade(max_retries=3)
    for _ in range(3):
        action, _ = cascade.on_failure("Bash", "timeout")
        assert action == RecoveryAction.RETRY
    action, target = cascade.on_failure("Bash", "timeout")
    assert action == RecoveryAction.ABORT
    assert target == ""


def test_switch_to_alternative() -> None:
    cascade = ToolCascade(
        max_retries=1,
        alternatives={"Bash": ["Shell", "Exec"]},
    )
    cascade.on_failure("Bash", "error")
    action, target = cascade.on_failure("Bash", "error")
    assert action == RecoveryAction.SWITCH
    assert target == "Shell"


def test_switch_exhausts_then_abort() -> None:
    cascade = ToolCascade(
        max_retries=1,
        alternatives={"Bash": ["Shell"]},
    )
    cascade.on_failure("Bash", "e1")
    cascade.on_failure("Bash", "e2")
    action, target = cascade.on_failure("Bash", "e3")
    assert action == RecoveryAction.ABORT
    assert target == ""


def test_reset_clears_count() -> None:
    cascade = ToolCascade(max_retries=3)
    cascade.on_failure("Bash", "error")
    cascade.on_failure("Bash", "error")
    cascade.reset("Bash")
    assert cascade.get_failure_count("Bash") == 0
    action, _ = cascade.on_failure("Bash", "error")
    assert action == RecoveryAction.RETRY


def test_failure_logged_to_jsonl(tmp_path: Path) -> None:
    log_path = tmp_path / "cascade.jsonl"
    cascade = ToolCascade(max_retries=3, log_path=log_path)
    cascade.on_failure("Read", "file not found")
    assert log_path.is_file()
    entry = json.loads(log_path.read_text().strip())
    assert entry["tool_name"] == "Read"
    assert entry["error"] == "file not found"
    assert entry["failure_count"] == 1


def test_multiple_failures_logged(tmp_path: Path) -> None:
    log_path = tmp_path / "cascade.jsonl"
    cascade = ToolCascade(max_retries=3, log_path=log_path)
    cascade.on_failure("Read", "e1")
    cascade.on_failure("Read", "e2")
    lines = log_path.read_text().strip().split("\n")
    assert len(lines) == 2


def test_full_cascade_sequence() -> None:
    """retry(3) → switch(Shell) → switch(Exec) → abort."""
    cascade = ToolCascade(
        max_retries=3,
        alternatives={"Bash": ["Shell", "Exec"]},
    )
    results = []
    for _ in range(6):
        results.append(cascade.on_failure("Bash", "fail"))
    assert results[0] == (RecoveryAction.RETRY, "Bash")
    assert results[1] == (RecoveryAction.RETRY, "Bash")
    assert results[2] == (RecoveryAction.RETRY, "Bash")
    assert results[3] == (RecoveryAction.SWITCH, "Shell")
    assert results[4] == (RecoveryAction.SWITCH, "Exec")
    assert results[5] == (RecoveryAction.ABORT, "")


def test_independent_tool_tracking() -> None:
    cascade = ToolCascade(max_retries=2)
    cascade.on_failure("Bash", "e1")
    cascade.on_failure("Bash", "e2")
    action_read, _ = cascade.on_failure("Read", "e1")
    assert action_read == RecoveryAction.RETRY
    action_bash, _ = cascade.on_failure("Bash", "e3")
    assert action_bash == RecoveryAction.ABORT


def test_concurrent_append_no_loss(tmp_path: Path) -> None:
    """4 processes × 50 failures: log must contain exactly 200 entries.

    Validates Phase 12a fix for the read-modify-replace race that previously
    caused failure log entries to be dropped under concurrent retry storms.
    """
    log_path = tmp_path / "cascade.jsonl"
    n_per_worker = 50
    n_workers = 4
    ctx = mp.get_context("spawn")
    procs = [
        ctx.Process(target=_cascade_worker, args=(str(log_path), wid, n_per_worker))
        for wid in range(n_workers)
    ]
    for p in procs:
        p.start()
    for p in procs:
        p.join(timeout=60)
        assert not p.is_alive(), "worker timed out"
        assert p.exitcode == 0, f"worker exited with {p.exitcode}"
    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == n_per_worker * n_workers, (
        f"expected {n_per_worker * n_workers} entries, got {len(lines)}"
    )
    parsed = [json.loads(line) for line in lines if line.strip()]
    assert len(parsed) == n_per_worker * n_workers
