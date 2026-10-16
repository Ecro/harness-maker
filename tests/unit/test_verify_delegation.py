"""Phase 6: the same delegation pattern for verify, with a receipt that can actually fail.

Reusing the wrapup receipt verbatim would give verify a reconciliation with nothing
in it — every memory field legitimately empty, so `ok=True` for any claim at all.
Verify's observable output is the JSONL record it appends and the per-check verdicts,
so those are what get checked.

The anti-fabrication shape here is the mirror of the promotion arithmetic: a
summarising main loop relaying "all green" while a check said FAIL.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from harness_maker import wrapup_brief as wb
from harness_maker import wrapup_receipt as wr
from harness_maker.models import (
    DelegationConfig,
    InterviewAnswers,
    Preset,
    ProjectProfile,
    Target,
)
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize


def _numbered_step_at(body: str, title: str) -> int:
    """Offset of `<n>. <title>` at the start of a line, for ANY n.

    Pinning the literal `"1. Read inputs…"` broke on a correct renumber ([fail:test]
    test-pins-retired-implementation-name, count:4) and is now blocked by
    `tests/structural/test_no_dead_string_pins.py`. Dropping the ordinal outright was the
    first response and it was WEAKER than what it replaced: a bare `.index(title)` matches a
    prose mention of the same phrase anywhere earlier in the document, which is exactly the
    ambiguity the ordinal was resolving. So the ordinal's SHAPE is pinned and its VALUE is
    not — this still fails if the step stops being a numbered step at all.
    """
    m = re.search(rf"^\d+\. {re.escape(title)}", body, re.M)
    assert m, f"no numbered step titled {title!r}"
    return m.start()


def _git(args: list[str], cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True, timeout=60)


def _task_repo(tmp_path: Path, slug: str = "my-task") -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(["init", "-b", "main"], repo)
    _git(["config", "user.email", "t@e.com"], repo)
    _git(["config", "user.name", "T"], repo)
    (repo / ".gitignore").write_text(".worktrees/\n", encoding="utf-8")
    (repo / "README.md").write_text("x\n", encoding="utf-8")
    _git(["add", "."], repo)
    _git(["commit", "-m", "init"], repo)
    wt = repo / ".worktrees" / slug
    _git(["worktree", "add", "-b", f"hm/{slug}", str(wt)], repo)
    return wt


def _verify(tmp_path: Path, *, preset: str = "Production", stages: list[str] | None = None) -> str:
    answers = InterviewAnswers(
        preset=Preset(preset),
        targets=[Target.CLAUDE_CODE],
        delegation=DelegationConfig(stages=stages or []),
        worktree={"feature_branch_workflow": True},
    )
    render(synthesize(ProjectProfile(), answers), tmp_path, freeze_time=DEFAULT_FREEZE_TIME)
    return (tmp_path / "commands" / "hm" / "verify.md").read_text(encoding="utf-8")


_RECORD_REL = ".claude/observability/verify-2026-07-26.jsonl"


def _receipt(**overrides: object) -> wr.WrapupReceipt:
    """A COMPLETE verify receipt by default.

    The first version defaulted `checks=()` and `record_path=None` — i.e. the exact
    vacuous shape review F-05 showed reconciles clean — so every test built on it was
    measuring a receipt that could not fail for the reason it named. Tests that mean to
    exercise an incomplete receipt now override explicitly.
    """
    fields: dict[str, object] = {
        "schema_version": wr.SCHEMA_VERSION,
        "stage": "verify",
        "result": "PASS",
        "checks": (wr.CheckResult(name="regression-smoke", verdict="PASS"),),
        "record_path": _RECORD_REL,
    }
    fields.update(overrides)
    return wr.WrapupReceipt.model_validate(fields)


def _memory(base: Path, *, record: bool = True) -> None:
    md = base / ".claude" / "memory"
    md.mkdir(parents=True, exist_ok=True)
    (md / "wiki.md").write_text("", encoding="utf-8")
    (md / "failures.md").write_text("", encoding="utf-8")
    if record:
        rec = base / _RECORD_REL
        rec.parent.mkdir(parents=True, exist_ok=True)
        rec.write_text(json.dumps({"result": "PASS"}) + "\n", encoding="utf-8")


# ------------------------------------------------------------------ brief, generalised




def test_a_stage_that_is_not_delegatable_is_still_rejected(tmp_path: Path) -> None:
    """Generalising must not turn the stage field into a free string — a brief for a
    stage with no dispatch block is a caller bug, not a new feature."""
    wt = _task_repo(tmp_path)

    _brief, verdict = wb.derive_brief(wt, stage="execute")

    assert verdict.ok is False
    assert "stage" in verdict.missing


def test_the_wrapup_default_is_unchanged(tmp_path: Path) -> None:
    """Negative control for the generalisation: the existing caller must not have to
    pass anything new."""
    wt = _task_repo(tmp_path)

    brief, _ = wb.derive_brief(wt)

    assert brief is not None
    assert brief.stage == "wrapup"


# ------------------------------------------------------------------ verify receipt


def test_a_verify_receipt_whose_record_exists_and_agrees_reconciles(tmp_path: Path) -> None:
    """Positive control — without it every rejection below is met by a reconciler that
    fails verify receipts unconditionally."""
    _memory(tmp_path)

    result = wr.reconcile(_receipt(), base_root=tmp_path)

    assert result.ok is True


def test_a_verify_receipt_claiming_a_record_that_does_not_exist_is_a_mismatch(
    tmp_path: Path,
) -> None:
    """The JSONL record is verify's only durable artifact. A receipt claiming a run
    that left no trace is the whole failure mode."""
    _memory(tmp_path, record=False)

    result = wr.reconcile(_receipt(), base_root=tmp_path)

    assert result.ok is False
    assert [m.kind for m in result.mismatches] == ["verify-record-missing"]


def test_a_verify_receipt_with_no_record_path_reconciles_clean(tmp_path: Path) -> None:
    """The verify JSONL ledger was retired (nothing read it), so a receipt that names no
    `record_path` is the normal shape now — it must NOT be a `verify-record-missing`."""
    _memory(tmp_path, record=False)

    result = wr.reconcile(_receipt().model_copy(update={"record_path": None}), base_root=tmp_path)

    assert result.ok is True
    assert "verify-record-missing" not in [m.kind for m in result.mismatches]


def test_an_overall_pass_contradicted_by_a_failing_check_is_a_mismatch(
    tmp_path: Path,
) -> None:
    """The anti-fabrication check, mirroring the promotion arithmetic: "RESULT: PASS"
    while a check said FAIL is the shape a summarising main loop produces when it
    reports the outcome it expected instead of the one it got. Verify is a GATE, so
    this is the one mismatch that must never be smoothed over."""
    _memory(tmp_path)

    result = wr.reconcile(
        _receipt(
            result="PASS",
            checks=(
                wr.CheckResult(name="regression-smoke", verdict="PASS"),
                wr.CheckResult(name="security-high", verdict="FAIL"),
            ),
        ),
        base_root=tmp_path,
    )

    assert result.ok is False
    assert [m.kind for m in result.mismatches] == ["verify-result-inconsistent"]
    assert "security-high" in result.mismatches[0].detail


def test_an_overall_fail_with_a_failing_check_is_consistent(tmp_path: Path) -> None:
    """A FAIL verdict is a legitimate, correct outcome — flagging it would push the
    delegate toward reporting PASS."""
    _memory(tmp_path)

    result = wr.reconcile(
        _receipt(
            result="FAIL",
            checks=(wr.CheckResult(name="security-high", verdict="FAIL"),),
        ),
        base_root=tmp_path,
    )

    assert result.ok is True


def test_a_skipped_check_does_not_contradict_an_overall_fail(tmp_path: Path) -> None:
    """Verify stops at the first FAIL, so the remaining checks are SKIP. Treating SKIP
    as a failure would make every real FAIL report two mismatches."""
    _memory(tmp_path)

    result = wr.reconcile(
        _receipt(
            result="FAIL",
            checks=(
                wr.CheckResult(name="security-high", verdict="FAIL"),
                wr.CheckResult(name="worktree-clean", verdict="SKIP"),
            ),
        ),
        base_root=tmp_path,
    )

    assert result.ok is True


def test_the_verify_fields_do_not_disturb_a_wrapup_receipt(tmp_path: Path) -> None:
    """The absent case for the schema extension: a wrapup receipt carries neither
    `checks` nor `record_path`, and must not acquire a verify mismatch for it."""
    _memory(tmp_path)

    result = wr.reconcile(
        wr.WrapupReceipt.model_validate(
            {"schema_version": wr.SCHEMA_VERSION, "stage": "wrapup", "promotion_candidates": 0}
        ),
        base_root=tmp_path,
    )

    assert result.ok is True


def test_a_verify_receipt_parses_from_the_agents_json(tmp_path: Path) -> None:
    receipt, error = wr.parse_receipt(
        json.dumps(
            {
                "schema_version": wr.SCHEMA_VERSION,
                "stage": "verify",
                "result": "PASS",
                "checks": [{"name": "regression-smoke", "verdict": "PASS"}],
            }
        )
    )

    assert error == ""
    assert receipt is not None
    assert receipt.checks[0].verdict == "PASS"


def test_a_check_verdict_outside_the_enum_is_rejected() -> None:
    """`"probably fine"` must not become a third verdict the reconciler ignores."""
    receipt, error = wr.parse_receipt(
        json.dumps(
            {
                "schema_version": wr.SCHEMA_VERSION,
                "stage": "verify",
                "checks": [{"name": "x", "verdict": "probably fine"}],
            }
        )
    )

    assert receipt is None
    assert error


# ------------------------------------------------------------------ render














