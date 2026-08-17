"""Phase 1 — pure per-AC evidence scorer + tri-state waiver-check CLI.

PLAN-wrapup-waiver-enforcement ADR-001/002/004. The scorer is the single
source of truth shared with spec_quality (no threshold drift); the CLI is
non-blocking (always exit 0) but emits a tri-state status that separates a
policy warning (`flagged`) from a check that could not run (`check_error`).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from harness_maker.spec_machine import (
    ORACLE_EVIDENCE_WEAK_THRESHOLD,
    main,
    score_ac_oracle_evidence,
)

# --- pure scorer (the shared ladder) ---------------------------------------


def test_score_ac_oracle_evidence_matrix() -> None:
    assert score_ac_oracle_evidence({"oracle_source": "legacy-unspecified"}) == 0
    assert score_ac_oracle_evidence({"oracle_source": "golden", "oracle_evidence": ""}) == 20
    assert score_ac_oracle_evidence({"oracle_source": "golden", "oracle_evidence": "short"}) == 40
    assert (
        score_ac_oracle_evidence(
            {"oracle_source": "differential", "oracle_evidence": "reference impl golden bytes"}
        )
        == 85
    )
    assert (
        score_ac_oracle_evidence(
            {"oracle_source": "golden", "oracle_evidence": "a fairly generic justification line"}
        )
        == 60
    )


def test_weak_threshold_is_40() -> None:
    assert ORACLE_EVIDENCE_WEAK_THRESHOLD == 40
    # empty (20) and legacy (0) are weak; a 40 (short) is the boundary, NOT < 40.
    assert score_ac_oracle_evidence({"oracle_source": "golden", "oracle_evidence": ""}) < 40
    assert score_ac_oracle_evidence({"oracle_source": "golden", "oracle_evidence": "short"}) == 40


# --- CLI helpers ------------------------------------------------------------


def _write_yaml(tmp_path: Path, slug: str, acs: list[dict[str, Any]]) -> Path:
    p = tmp_path / f"SPEC-{slug}.machine.yaml"
    p.write_text(
        yaml.safe_dump({"schema_version": 2, "spec_slug": slug, "verification_tier": 1, "ac": acs}),
        encoding="utf-8",
    )
    return p


def _run(
    tmp_path: Path, yaml_path: Path, mode: str, capsys: pytest.CaptureFixture[str]
) -> tuple[int, dict[str, Any]]:
    rc = main(
        ["waiver-check", "--yaml", str(yaml_path), "--dev-mode", mode, "--root", str(tmp_path)]
    )
    out = capsys.readouterr().out
    # The CLI prints a single JSON status line.
    status = json.loads([ln for ln in out.splitlines() if ln.strip().startswith("{")][-1])
    return rc, status


def _receipt(tmp_path: Path, slug: str) -> Path:
    return tmp_path / ".claude" / "observability" / f"oracle-waiver-check-{slug}.jsonl"


# --- tri-state CLI ----------------------------------------------------------


def test_waiver_check_flags_weak_unwaived_task_driven(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    y = _write_yaml(
        tmp_path,
        "flag",
        [{"id": "AC-001", "title": "t", "oracle_source": "golden", "oracle_evidence": ""}],
    )
    rc, status = _run(tmp_path, y, "task-driven", capsys)
    assert rc == 0
    assert status["status"] == "flagged"
    assert "AC-001" in status["flagged_acs"]


def test_waiver_check_waived_not_flagged(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    y = _write_yaml(
        tmp_path,
        "waived",
        [
            {
                "id": "AC-001",
                "title": "t",
                "oracle_source": "golden",
                "oracle_evidence": "",
                "oracle_independence_waiver": "accepted: prototype",
            }
        ],
    )
    rc, status = _run(tmp_path, y, "task-driven", capsys)
    assert rc == 0
    assert status["status"] == "ok"
    assert status["flagged_acs"] == []


def test_waiver_check_spec_driven_is_ok_noop(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    y = _write_yaml(
        tmp_path,
        "spec",
        [{"id": "AC-001", "title": "t", "oracle_source": "golden", "oracle_evidence": ""}],
    )
    rc, status = _run(tmp_path, y, "spec-driven", capsys)
    assert rc == 0
    assert status["status"] == "ok"  # spec-driven already blocks at authoring


def test_waiver_check_malformed_yaml_is_check_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bad = tmp_path / "SPEC-bad.machine.yaml"
    bad.write_text(":bad: : yaml :", encoding="utf-8")
    rc, status = _run(tmp_path, bad, "task-driven", capsys)
    assert rc == 0  # exit 0 ALWAYS (ADR-002)
    assert status["status"] == "check_error"  # NOT a clean pass


def test_waiver_check_non_list_ac_is_check_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    p = tmp_path / "SPEC-nonlist.machine.yaml"
    p.write_text(yaml.safe_dump({"schema_version": 2, "spec_slug": "x", "ac": "oops"}), "utf-8")
    rc, status = _run(tmp_path, p, "task-driven", capsys)
    assert rc == 0
    assert status["status"] == "check_error"


def test_waiver_check_missing_file_is_check_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rc, status = _run(tmp_path, tmp_path / "nope.yaml", "task-driven", capsys)
    assert rc == 0
    assert status["status"] == "check_error"


def test_waiver_check_writes_receipt_under_root(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    y = _write_yaml(
        tmp_path,
        "rcpt",
        [{"id": "AC-001", "title": "t", "oracle_source": "golden", "oracle_evidence": ""}],
    )
    _run(tmp_path, y, "task-driven", capsys)
    receipt = _receipt(tmp_path, "rcpt")
    assert receipt.exists()
    # Receipt stays under root (never escapes via a crafted slug/path).
    assert receipt.resolve().is_relative_to(tmp_path.resolve())
    last = json.loads(receipt.read_text(encoding="utf-8").splitlines()[-1])
    assert last["status"] == "flagged"


# --- robustness: never-raises / exit-0 contract (REVIEW consensus) ----------


def test_non_str_oracle_evidence_is_check_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    y = _write_yaml(
        tmp_path,
        "nonstr",
        [{"id": "AC-001", "title": "t", "oracle_source": "golden", "oracle_evidence": [1, 2]}],
    )
    rc, status = _run(tmp_path, y, "task-driven", capsys)
    assert rc == 0
    assert status["status"] == "check_error"  # NOT a crash, NOT a clean ok


def test_non_str_waiver_is_check_error(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    y = _write_yaml(
        tmp_path,
        "nonstrw",
        [
            {
                "id": "AC-001",
                "title": "t",
                "oracle_source": "golden",
                "oracle_independence_waiver": 12,
            }
        ],
    )
    rc, status = _run(tmp_path, y, "task-driven", capsys)
    assert rc == 0
    assert status["status"] == "check_error"


def test_non_dict_ac_entry_is_check_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    p = tmp_path / "SPEC-nondict.machine.yaml"
    p.write_text(yaml.safe_dump({"schema_version": 2, "spec_slug": "x", "ac": [123]}), "utf-8")
    rc, status = _run(tmp_path, p, "task-driven", capsys)
    assert rc == 0
    assert status["status"] == "check_error"  # not silently "ok"


def test_non_utf8_file_is_check_error(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    bad = tmp_path / "SPEC-binary.machine.yaml"
    bad.write_bytes(b"\xff\xfe\x00bad")
    rc, status = _run(tmp_path, bad, "task-driven", capsys)
    assert rc == 0  # UnicodeDecodeError must become check_error, not a crash
    assert status["status"] == "check_error"


def test_receipt_write_failure_still_exits_zero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    y = _write_yaml(
        tmp_path,
        "rcptfail",
        [{"id": "AC-001", "title": "t", "oracle_source": "golden", "oracle_evidence": ""}],
    )
    # root is a FILE → mkdir of .claude/observability under it raises OSError,
    # which the CLI swallows (receipt is best-effort telemetry).
    root_file = tmp_path / "rootfile"
    root_file.write_text("x", "utf-8")
    rc = main(
        ["waiver-check", "--yaml", str(y), "--dev-mode", "task-driven", "--root", str(root_file)]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert '"flagged"' in out


def test_large_flagged_list_receipt_is_truncated(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    acs = [
        {"id": f"AC-{i:04d}", "title": "t", "oracle_source": "golden", "oracle_evidence": ""}
        for i in range(500)
    ]
    y = _write_yaml(tmp_path, "big", acs)
    _run(tmp_path, y, "task-driven", capsys)
    last = json.loads(_receipt(tmp_path, "big").read_text(encoding="utf-8").splitlines()[-1])
    # The receipt line stays within the atomic-append bound via truncation.
    assert last.get("truncated") is True
    assert last["flagged_count"] == 500
