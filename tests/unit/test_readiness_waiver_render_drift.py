"""Phase 4 — /hm:health render-drift guard for the wrapup oracle-waiver advisory.

PLAN-wrapup-waiver-enforcement ADR-004/C5: flipping harness.yaml dev_mode
without re-rendering leaves the wrapup advisory missing (task-driven) or
mis-firing (spec-driven). The signal must catch that stale render.
"""

from __future__ import annotations

from pathlib import Path

from harness_maker.readiness import _dim_guardrails

_SIG = "wrapup_oracle_waiver_dev_mode_match"


def _project(tmp_path: Path, dev_mode: str, wrapup_body: str | None) -> Path:
    claude = tmp_path / ".claude"
    (claude / "commands" / "hm").mkdir(parents=True)
    (claude / "harness.yaml").write_text(f"dev_mode: {dev_mode}\npreset: Production\n", "utf-8")
    if wrapup_body is not None:
        (claude / "commands" / "hm" / "wrapup.md").write_text(wrapup_body, "utf-8")
    return tmp_path


def _signal(project: Path):
    dim = _dim_guardrails(project)
    return next((s for s in dim.signals if s.id == _SIG), None)


def _passed(project: Path) -> bool:
    sig = _signal(project)
    assert sig is not None
    return sig.passed


def test_task_driven_with_advisory_passes(tmp_path: Path) -> None:
    p = _project(tmp_path, "task-driven", "Step 3.6 ... waiver-check --dev-mode task-driven ...")
    assert _passed(p) is True


def test_task_driven_without_advisory_fails_stale_render(tmp_path: Path) -> None:
    p = _project(tmp_path, "task-driven", "no oracle advisory here (stale spec-driven render)")
    assert _passed(p) is False


def test_spec_driven_with_advisory_fails_misfire(tmp_path: Path) -> None:
    p = _project(tmp_path, "spec-driven", "Step 3.6 ... waiver-check ... (stale task render)")
    assert _passed(p) is False


def test_spec_driven_without_advisory_passes(tmp_path: Path) -> None:
    p = _project(tmp_path, "spec-driven", "clean spec-driven wrapup, no advisory")
    assert _passed(p) is True


def test_na_when_wrapup_command_absent(tmp_path: Path) -> None:
    p = _project(tmp_path, "task-driven", None)  # no wrapup.md
    assert _signal(p) is None  # N-A → no signal, no penalty


def test_na_when_wrapup_command_unreadable(tmp_path: Path) -> None:
    # A non-UTF-8 (corrupt) rendered wrapup.md must degrade to N-A, never crash
    # the whole /hm:health computation (REVIEW consensus).
    p = _project(tmp_path, "task-driven", "")
    (p / ".claude" / "commands" / "hm" / "wrapup.md").write_bytes(b"\xff\xfe\x00")
    assert _signal(p) is None
