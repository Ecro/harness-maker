"""Phase 4 — /hm:health render-drift guard for the wrapup oracle-waiver advisory.

PLAN-wrapup-waiver-enforcement ADR-004/C5, re-keyed by SPEC-dev-mode-removal: wrapup Step 3.6
renders only at `warn` strictness. Changing harness.yaml's strictness without re-rendering
leaves the advisory missing (warn) or mis-firing (block). The signal must catch that stale
render — and it reads strictness through the one resolver, so an absent key derives from the
preset and a legacy methodology key arrives translated.
"""

from __future__ import annotations

from pathlib import Path

from harness_maker.readiness import Signal, _dim_guardrails

_SIG = "wrapup_oracle_waiver_strictness_match"


def _project(tmp_path: Path, harness_yaml: str, wrapup_body: str | None) -> Path:
    claude = tmp_path / ".claude"
    (claude / "commands" / "hm").mkdir(parents=True)
    (claude / "harness.yaml").write_text(harness_yaml, "utf-8")
    if wrapup_body is not None:
        (claude / "commands" / "hm" / "wrapup.md").write_text(wrapup_body, "utf-8")
    return tmp_path


def _yaml(strictness: str, preset: str = "Production") -> str:
    return f"preset: {preset}\nspec:\n  strictness: {strictness}\n"


def _signal(project: Path) -> Signal | None:
    dim = _dim_guardrails(project)
    return next((s for s in dim.signals if s.id == _SIG), None)


def _passed(project: Path) -> bool:
    sig = _signal(project)
    assert sig is not None
    value: bool = sig.passed
    return value


def test_warn_with_advisory_passes(tmp_path: Path) -> None:
    p = _project(tmp_path, _yaml("warn"), "Step 3.6 ... waiver-check --strictness warn ...")
    assert _passed(p) is True


def test_warn_without_advisory_fails_stale_render(tmp_path: Path) -> None:
    p = _project(tmp_path, _yaml("warn"), "no oracle advisory here (stale block render)")
    assert _passed(p) is False


def test_block_with_advisory_fails_misfire(tmp_path: Path) -> None:
    p = _project(tmp_path, _yaml("block"), "Step 3.6 ... waiver-check ... (stale warn render)")
    assert _passed(p) is False


def test_block_without_advisory_passes(tmp_path: Path) -> None:
    p = _project(tmp_path, _yaml("block"), "clean strict wrapup, no advisory")
    assert _passed(p) is True


def test_absent_key_derives_from_the_preset(tmp_path: Path) -> None:
    """Side with no key resolves to warn, so a wrapup WITHOUT the advisory is stale."""
    p = _project(tmp_path, "preset: Side\n", "no oracle advisory here")
    assert _passed(p) is False


def test_legacy_methodology_key_arrives_translated(tmp_path: Path) -> None:
    """An un-re-rendered harness still carrying the retired key reads as its translation."""
    p = _project(tmp_path, "preset: Production\ndev_mode: task-driven\n", "Step 3.6 waiver-check")
    assert _passed(p) is True


def test_na_when_wrapup_command_absent(tmp_path: Path) -> None:
    p = _project(tmp_path, _yaml("warn"), None)  # no wrapup.md
    assert _signal(p) is None  # N-A → no signal, no penalty


def test_na_when_wrapup_command_unreadable(tmp_path: Path) -> None:
    # A non-UTF-8 (corrupt) rendered wrapup.md must degrade to N-A, never crash
    # the whole /hm:health computation (REVIEW consensus).
    p = _project(tmp_path, _yaml("warn"), "")
    (p / ".claude" / "commands" / "hm" / "wrapup.md").write_bytes(b"\xff\xfe\x00")
    assert _signal(p) is None
