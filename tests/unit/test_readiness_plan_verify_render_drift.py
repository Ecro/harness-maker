"""Phase 3 — /hm:health render-drift guard for plan Step 1.7 + verify Check 6.

PLAN-spec-optional-task-driven ADR-003: spec_need's runtime guard backstops
verify at execution time, but plan-side enforcement is LLM-prose (unreachable at
runtime), so a stale render (dev_mode flipped without re-render) is surfaced HERE.
Mirrors wrapup_oracle_waiver_dev_mode_match. Marker = the spec-driven-only
`spec_need` CLI calls that plan Step 1.7 / verify Check 6 render.
"""

from __future__ import annotations

from pathlib import Path

from harness_maker.readiness import _dim_guardrails

_SIG = "plan_verify_dev_mode_match"
_GATED = "run `python -m harness_maker.spec_need op-check ...`"  # spec-driven only
_UNGATED = "no spec-need gating in this stage (task-driven render)"


def _project(tmp_path: Path, dev_mode: str, plan_body: str | None, verify_body: str | None) -> Path:
    claude = tmp_path / ".claude"
    (claude / "commands" / "hm").mkdir(parents=True)
    (claude / "harness.yaml").write_text(f"dev_mode: {dev_mode}\npreset: Production\n", "utf-8")
    if plan_body is not None:
        (claude / "commands" / "hm" / "plan.md").write_text(plan_body, "utf-8")
    if verify_body is not None:
        (claude / "commands" / "hm" / "verify.md").write_text(verify_body, "utf-8")
    return tmp_path


def _signal(project: Path):  # type: ignore[no-untyped-def]
    dim = _dim_guardrails(project)
    return next((s for s in dim.signals if s.id == _SIG), None)


def _passed(project: Path) -> bool:
    sig = _signal(project)
    assert sig is not None
    return sig.passed


def test_spec_driven_with_gating_passes(tmp_path: Path) -> None:
    p = _project(tmp_path, "spec-driven", _GATED, _GATED)
    assert _passed(p) is True


def test_spec_driven_missing_gating_fails_stale_render(tmp_path: Path) -> None:
    # plan has Step 1.7 but verify lost Check 6 → stale task render on verify.
    p = _project(tmp_path, "spec-driven", _GATED, _UNGATED)
    assert _passed(p) is False


def test_task_driven_with_gating_fails_stale_render(tmp_path: Path) -> None:
    # dev_mode flipped to task-driven but plan/verify still carry spec-need gating.
    p = _project(tmp_path, "task-driven", _GATED, _GATED)
    assert _passed(p) is False


def test_task_driven_without_gating_passes(tmp_path: Path) -> None:
    p = _project(tmp_path, "task-driven", _UNGATED, _UNGATED)
    assert _passed(p) is True


def test_na_when_plan_command_absent(tmp_path: Path) -> None:
    p = _project(tmp_path, "spec-driven", None, _GATED)
    assert _signal(p) is None


def test_na_when_verify_command_absent(tmp_path: Path) -> None:
    p = _project(tmp_path, "spec-driven", _GATED, None)
    assert _signal(p) is None


def test_na_when_plan_command_unreadable(tmp_path: Path) -> None:
    p = _project(tmp_path, "spec-driven", _GATED, _GATED)
    (p / ".claude" / "commands" / "hm" / "plan.md").write_bytes(b"\xff\xfe\x00")
    assert _signal(p) is None


def test_na_when_dev_mode_unrecognized(tmp_path: Path) -> None:
    # An unparseable/unknown dev_mode value → freshness UNKNOWN → N-A (no signal),
    # per PLAN Phase 3 exit criterion.
    p = _project(tmp_path, "garbage-mode", _GATED, _GATED)
    assert _signal(p) is None
