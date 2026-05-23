"""Tests for post-commit P0/P1 fixes to PLAN-loop-mid-stop-and-review-skip.

Covers:
- ``RuntimeBlock`` + ``LoopContext.runtime`` round-trip via
  ``save_loop_context`` → ``parse_loop_context`` (P0#2 — `extra="forbid"`
  used to make this impossible).
- ``iter_receipts.set_iter_marker`` atomic write (P1#1 — replaces
  non-atomic shell `printf > file` redirect).
- ``--written-at`` CLI flag rejected unless ``HM_TEST_RECEIPTS=1`` (P1#6 —
  prevent operator backdating).
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from harness_maker import iter_receipts
from harness_maker.autoloop_driver import (
    ExitCriterion,
    ImprovementContext,
    LastTestResult,
    LoopContext,
    RuntimeBlock,
    parse_loop_context,
    save_loop_context,
)

# ── LoopContext.runtime round-trip (P0#2) ───────────────────────────────────


def _make_ctx() -> LoopContext:
    return LoopContext(
        slug="loop-mid-stop-and-review-skip",
        source="(test)",
        created_at="2026-05-23T00:00:00Z",
        updated_at="2026-05-23T00:00:00Z",
        context=ImprovementContext(
            purpose="test",
            invariants=["inv1"],
            priority="speed>safety",
            test_reliability="hi",
            stopping_criteria="all tests green",
            exit_criteria_checklist=[
                ExitCriterion(label="lint clean", cmd="ruff check", required=True),
            ],
        ),
    )


def test_loop_context_accepts_runtime_block(tmp_path: Path) -> None:
    """Phase 3's runtime: persistence must not raise ValidationError."""
    ctx = _make_ctx()
    ctx.runtime = RuntimeBlock(
        convergence_streak=1,
        stage_retry_counts={"iter-3:review": 1, "iter-4:execute": 2},
        last_test_result=LastTestResult(exit_code=0, failing=[]),
    )
    path = tmp_path / "loop-mid-stop-and-review-skip.yaml"
    save_loop_context(ctx, path)
    loaded = parse_loop_context(path)
    assert loaded.runtime is not None
    assert loaded.runtime.convergence_streak == 1
    assert loaded.runtime.stage_retry_counts == {"iter-3:review": 1, "iter-4:execute": 2}
    assert loaded.runtime.last_test_result.exit_code == 0


def test_loop_context_legacy_yaml_without_runtime_still_loads(tmp_path: Path) -> None:
    """Pre-Phase-3 YAML files must round-trip cleanly (runtime is Optional)."""
    ctx = _make_ctx()
    # runtime stays None
    path = tmp_path / "legacy.yaml"
    save_loop_context(ctx, path)
    loaded = parse_loop_context(path)
    assert loaded.runtime is None


def test_loop_context_rejects_unknown_top_level_key(tmp_path: Path) -> None:
    """extra='forbid' still blocks ARBITRARY unknown keys (not just runtime)."""
    path = tmp_path / "bad.yaml"
    path.write_text(
        "slug: x\n"
        "source: ''\n"
        "created_at: '2026-05-23T00:00:00Z'\n"
        "updated_at: '2026-05-23T00:00:00Z'\n"
        "context:\n"
        "  purpose: p\n"
        "  invariants: []\n"
        "  priority: p\n"
        "  test_reliability: t\n"
        "  stopping_criteria: s\n"
        "evil_field: payload\n"
    )
    with pytest.raises(Exception):  # noqa: B017,PT011 — pydantic ValidationError
        parse_loop_context(path)


# ── iter_receipts.set_iter_marker atomicity (P1#1) ──────────────────────────


def test_set_iter_marker_writes_correct_path(tmp_path: Path) -> None:
    path = iter_receipts.set_iter_marker(iter=7, root=tmp_path)
    assert path == tmp_path / ".claude" / ".hm-iter-receipts" / ".current-iter"
    assert path.read_text() == "7"


def test_set_iter_marker_overwrites_existing(tmp_path: Path) -> None:
    iter_receipts.set_iter_marker(iter=1, root=tmp_path)
    iter_receipts.set_iter_marker(iter=42, root=tmp_path)
    marker = tmp_path / ".claude" / ".hm-iter-receipts" / ".current-iter"
    assert marker.read_text() == "42"


def test_set_iter_marker_rejects_zero(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match=">= 1"):
        iter_receipts.set_iter_marker(iter=0, root=tmp_path)


def test_set_iter_marker_no_trailing_newline(tmp_path: Path) -> None:
    """Stage receipt shell guards use `$(cat .current-iter)` so newline trim
    is unnecessary on the consumer side; atomic_write here writes the integer
    string exactly (no automatic newline appended).
    """
    path = iter_receipts.set_iter_marker(iter=9, root=tmp_path)
    assert path.read_bytes() == b"9"  # exactly one byte, no \n


def test_set_iter_marker_cli_roundtrip(tmp_path: Path) -> None:
    r = subprocess.run(
        [
            sys.executable,
            "-m",
            "harness_maker.iter_receipts",
            "set-iter-marker",
            "--iter",
            "3",
            "--root",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert r.returncode == 0, r.stderr
    marker = tmp_path / ".claude" / ".hm-iter-receipts" / ".current-iter"
    assert marker.read_text() == "3"


# ── --written-at gated by HM_TEST_RECEIPTS=1 (P1#6) ─────────────────────────


def _cli_write_with_backdate(
    tmp_path: Path, env: dict[str, str]
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "harness_maker.iter_receipts",
            "write",
            "--iter",
            "1",
            "--stage",
            "execute",
            "--verdict",
            "pass",
            "--root",
            str(tmp_path),
            "--written-at",
            "2020-01-01T00:00:00Z",
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
        env={**os.environ, **env},
    )


def test_written_at_rejected_without_test_env_flag(tmp_path: Path) -> None:
    r = _cli_write_with_backdate(tmp_path, env={"HM_TEST_RECEIPTS": ""})
    assert r.returncode == 1
    assert "HM_TEST_RECEIPTS" in r.stderr


def test_written_at_accepted_with_test_env_flag(tmp_path: Path) -> None:
    r = _cli_write_with_backdate(tmp_path, env={"HM_TEST_RECEIPTS": "1"})
    assert r.returncode == 0, r.stderr
    rec = iter_receipts.read(tmp_path / ".claude" / ".hm-iter-receipts" / "iter-1" / "execute.json")
    assert rec.written_at == "2020-01-01T00:00:00Z"


# ── patch-runtime CLI (P1 #3 follow-up) ─────────────────────────────────────


def _write_ctx_yaml(tmp_path: Path) -> Path:
    ctx = _make_ctx()
    p = tmp_path / "ctx.yaml"
    save_loop_context(ctx, p)
    return p


def test_patch_runtime_sets_stage_retry_count(tmp_path: Path) -> None:
    p = _write_ctx_yaml(tmp_path)
    iter_receipts.patch_runtime_block(
        context_path=p,
        counter="stage_retry_counts",
        key="iter-3:review",
        value=2,
    )
    loaded = parse_loop_context(p)
    assert loaded.runtime is not None
    assert loaded.runtime.stage_retry_counts == {"iter-3:review": 2}


def test_patch_runtime_clear_resets_counter(tmp_path: Path) -> None:
    p = _write_ctx_yaml(tmp_path)
    # seed
    iter_receipts.patch_runtime_block(
        context_path=p,
        counter="stage_retry_counts",
        key="iter-1:execute",
        value=1,
    )
    # clear
    iter_receipts.patch_runtime_block(
        context_path=p,
        counter="stage_retry_counts",
        clear=True,
    )
    loaded = parse_loop_context(p)
    assert loaded.runtime is not None
    assert loaded.runtime.stage_retry_counts == {}


def test_patch_runtime_cli_clear(tmp_path: Path) -> None:
    p = _write_ctx_yaml(tmp_path)
    # seed via direct call
    iter_receipts.patch_runtime_block(
        context_path=p,
        counter="stage_retry_counts",
        key="iter-5:review",
        value=2,
    )
    # clear via CLI
    r = subprocess.run(
        [
            sys.executable,
            "-m",
            "harness_maker.iter_receipts",
            "patch-runtime",
            "--context",
            str(p),
            "--counter",
            "stage_retry_counts",
            "--clear",
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert r.returncode == 0, r.stderr
    loaded = parse_loop_context(p)
    assert loaded.runtime is not None
    assert loaded.runtime.stage_retry_counts == {}
