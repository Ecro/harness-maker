"""Phase 3 render tests for PLAN-spec-requirement-gate — verify.md.j2 Check 6.

Asserts that:
(a) task-driven render = 5 checks: no Check 6, no spec_need reference, and
    all count phrasing says "5" (no stray "5-check"/"5 Checks" count phrasing
    is implicitly guaranteed by the render being 5-check).
(b) spec-driven render = 6 checks: Check 6 PRESENT, count phrasing says "6",
    and NO stray "5-check"/"5 Checks" count phrasing remains.
(c) seam: spec-driven prose contains both `hm spec_need op-check`
    and `hm spec_need waiver-check` CLI calls.
(d) Check 6 prose names `not-evaluated` as a FAIL condition and describes the
    clean N-A on absent PLAN frontmatter.

Round 2 additions:
(FIX-6) spec_need CLI calls in verify Check 6 MUST use --root <WT> (not --root .)
        so hashes are computed against the worktree files, not project-root files.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from harness_maker.models import DevMode, InterviewAnswers, Preset, ProjectProfile, Target
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize


def _verify(tmp_path: Path, dev_mode: DevMode) -> str:
    """Render a full harness and return the verify stage body."""
    bp = synthesize(
        ProjectProfile(),
        InterviewAnswers(
            preset=Preset.PRODUCTION,
            targets=[Target.CLAUDE_CODE],
            dev_mode=dev_mode,
        ),
    )
    render(bp, tmp_path, freeze_time=DEFAULT_FREEZE_TIME)
    verify_files = list(tmp_path.rglob("stages/verify.md"))
    assert verify_files, "verify.md stage file not found in rendered output"
    return verify_files[0].read_text(encoding="utf-8")


# ── module-scoped fixtures ───────────────────────────────────────────────────


@pytest.fixture(scope="module")
def task_driven_verify(tmp_path_factory: pytest.TempPathFactory) -> str:
    out = tmp_path_factory.mktemp("verify-task")
    return _verify(out, DevMode.TASK_DRIVEN)


@pytest.fixture(scope="module")
def spec_driven_verify(tmp_path_factory: pytest.TempPathFactory) -> str:
    out = tmp_path_factory.mktemp("verify-spec")
    return _verify(out, DevMode.SPEC_DRIVEN)


# ── (a) task-driven: 5 checks, no Check 6, no spec_need ref ─────────────────


def test_task_driven_no_check_6_heading(task_driven_verify: str) -> None:
    """(a) Task-driven render must NOT contain the Check 6 heading."""
    assert "Check 6" not in task_driven_verify, (
        "task-driven verify must not contain 'Check 6' — spec-need gate is spec-driven only"
    )


def test_task_driven_no_spec_need_reference(task_driven_verify: str) -> None:
    """(a) Task-driven render must NOT reference hm spec_need."""
    assert "hm spec_need" not in task_driven_verify, (
        "task-driven verify must not reference hm spec_need"
    )


def test_task_driven_count_says_5(task_driven_verify: str) -> None:
    """(a) Task-driven render must say '5 Checks' / '5-check' in count context."""
    # The heading uses 'The 5 Checks'
    assert "The 5 Checks" in task_driven_verify, (
        "task-driven verify heading must say 'The 5 Checks'"
    )


def test_task_driven_stop_sign_says_5(task_driven_verify: str) -> None:
    """(a) Task-driven render intro must say '5-check stop sign'."""
    assert "5-check stop sign" in task_driven_verify, (
        "task-driven verify intro must say '5-check stop sign'"
    )


def test_task_driven_rubric_says_5(task_driven_verify: str) -> None:
    """(a) Task-driven Purpose paragraph must say '5-check rubric'."""
    assert "5-check rubric" in task_driven_verify, (
        "task-driven verify Purpose section must say '5-check rubric'"
    )


def test_task_driven_result_line_says_5(task_driven_verify: str) -> None:
    """(a) Task-driven result example must say '1 of 5 checks failed'."""
    assert "1 of 5 checks failed" in task_driven_verify, (
        "task-driven verify output example must say '1 of 5 checks failed'"
    )


def test_task_driven_outside_contract_says_5(task_driven_verify: str) -> None:
    """(a) Advisory probes section must say 'OUTSIDE the 5-check contract'."""
    assert "OUTSIDE the 5-check contract" in task_driven_verify, (
        "task-driven advisory probes section must say 'OUTSIDE the 5-check contract'"
    )


# ── (b) spec-driven: 6 checks, Check 6 present, no stray 5-count ────────────


def test_spec_driven_check_6_heading_present(spec_driven_verify: str) -> None:
    """(b) Spec-driven render must contain the Check 6 heading."""
    assert "### Check 6 — SPEC requirement (spec-driven)" in spec_driven_verify, (
        "spec-driven verify must contain '### Check 6 — SPEC requirement (spec-driven)'"
    )


def test_spec_driven_count_says_6(spec_driven_verify: str) -> None:
    """(b) Spec-driven render must say 'The 6 Checks' in the heading."""
    assert "The 6 Checks" in spec_driven_verify, (
        "spec-driven verify heading must say 'The 6 Checks'"
    )


def test_spec_driven_stop_sign_says_6(spec_driven_verify: str) -> None:
    """(b) Spec-driven intro must say '6-check stop sign'."""
    assert "6-check stop sign" in spec_driven_verify, (
        "spec-driven verify intro must say '6-check stop sign'"
    )


def test_spec_driven_rubric_says_6(spec_driven_verify: str) -> None:
    """(b) Spec-driven Purpose paragraph must say '6-check rubric'."""
    assert "6-check rubric" in spec_driven_verify, (
        "spec-driven verify Purpose section must say '6-check rubric'"
    )


def test_spec_driven_result_line_says_6(spec_driven_verify: str) -> None:
    """(b) Spec-driven result example must say '1 of 6 checks failed'."""
    assert "1 of 6 checks failed" in spec_driven_verify, (
        "spec-driven verify output example must say '1 of 6 checks failed'"
    )


def test_spec_driven_outside_contract_says_6(spec_driven_verify: str) -> None:
    """(b) Spec-driven advisory probes section must say 'OUTSIDE the 6-check contract'."""
    assert "OUTSIDE the 6-check contract" in spec_driven_verify, (
        "spec-driven advisory probes section must say 'OUTSIDE the 6-check contract'"
    )


def test_spec_driven_no_stray_5_check_count(spec_driven_verify: str) -> None:
    """(b) Spec-driven render must contain NO stray '5-check'/'5 Checks' count phrasing."""
    # These are count-context phrases, NOT the ordinal 'Check 5' heading name.
    stray_patterns = ["5-check", "The 5 Checks", "5 Checks", "1 of 5 checks"]
    for pattern in stray_patterns:
        assert pattern not in spec_driven_verify, (
            f"spec-driven verify must not contain stray count phrasing '{pattern}' — "
            "all count refs must be branched to '6'"
        )


def test_spec_driven_ordinal_check_5_still_present(spec_driven_verify: str) -> None:
    """(b) The ordinal '### Check 5 — Worktree merge cleanliness' MUST remain unchanged."""
    assert "### Check 5 — Worktree merge cleanliness" in spec_driven_verify, (
        "spec-driven verify must keep '### Check 5 — Worktree merge cleanliness' "
        "— this is the ORDINAL name of the 5th check, not a count reference"
    )


# ── (c) seam: CLI calls present in spec-driven ───────────────────────────────


def test_spec_driven_seam_op_check(spec_driven_verify: str) -> None:
    """(c) Spec-driven verify must contain the literal op-check CLI call."""
    assert "hm spec_need op-check" in spec_driven_verify, (
        "spec-driven verify must call 'hm spec_need op-check' "
        "— proves module wiring (seam test per project memory lesson)"
    )


def test_spec_driven_seam_waiver_check(spec_driven_verify: str) -> None:
    """(c) Spec-driven verify must contain the literal waiver-check CLI call."""
    assert "hm spec_need waiver-check" in spec_driven_verify, (
        "spec-driven verify must call 'hm spec_need waiver-check' — proves module wiring"
    )


def test_spec_driven_seam_check6_before_advisory(spec_driven_verify: str) -> None:
    """(c) Check 6 must appear before the Advisory probes section."""
    idx_check6 = spec_driven_verify.find("### Check 6")
    idx_advisory = spec_driven_verify.find("## Advisory probes")
    assert idx_check6 > 0, "Check 6 heading not found"
    assert idx_advisory > 0, "Advisory probes section not found"
    assert idx_check6 < idx_advisory, (
        f"Check 6 (at {idx_check6}) must appear before Advisory probes (at {idx_advisory})"
    )


# ── (d) Check 6 contract: not-evaluated as FAIL + clean N-A on absent ────────


def test_spec_driven_check6_not_evaluated_is_fail(spec_driven_verify: str) -> None:
    """(d) Check 6 prose must name 'not-evaluated' as a FAIL condition."""
    # Find the Check 6 section
    idx = spec_driven_verify.find("### Check 6")
    assert idx > 0, "Check 6 heading not found"
    # Read a large window covering the full Check 6 block
    section = spec_driven_verify[idx : idx + 4000]
    assert "not-evaluated" in section, (
        "Check 6 prose must name 'not-evaluated' as a FAIL condition — "
        "it is the fail-closed detection state (ADR-002)"
    )


def test_spec_driven_check6_fail_closed_description(spec_driven_verify: str) -> None:
    """(d) Check 6 must describe not-evaluated as the fail-closed detection state."""
    idx = spec_driven_verify.find("### Check 6")
    assert idx > 0
    section = spec_driven_verify[idx : idx + 4000]
    # The prose must explain that not-evaluated is a positive FAIL signal
    assert "fail-closed" in section or "FAIL signal" in section, (
        "Check 6 must describe 'not-evaluated' as a fail-closed signal or explicit FAIL, "
        "not merely as an absence of verdict"
    )


def test_spec_driven_check6_clean_na_on_absent_frontmatter(spec_driven_verify: str) -> None:
    """(d) Check 6 must describe clean N-A when PLAN frontmatter is absent/foreign."""
    idx = spec_driven_verify.find("### Check 6")
    assert idx > 0
    section = spec_driven_verify[idx : idx + 4000]
    # The prose must describe the clean N-A (automatic PASS) case
    assert "N-A" in section or "absent" in section, (
        "Check 6 must describe the clean N-A case when PLAN frontmatter is absent/foreign"
    )
    # Must NOT false-FAIL on missing frontmatter
    assert (
        "Never false-FAIL" in section
        or "never false-FAIL" in section
        or ("no spec_need_verdict" in section)
    ), "Check 6 must explicitly state it never false-FAILs on absent PLAN frontmatter"


def test_spec_driven_check6_verdict_set_described(spec_driven_verify: str) -> None:
    """(d) Check 6 must list the triggering verdict set {add, change, delete, not-evaluated}."""
    idx = spec_driven_verify.find("### Check 6")
    assert idx > 0
    section = spec_driven_verify[idx : idx + 4000]
    # All four FAIL verdicts must be mentioned
    for verdict in ("add", "change", "delete", "not-evaluated"):
        assert verdict in section, (
            f"Check 6 must mention verdict '{verdict}' in the FAIL condition set"
        )


def test_spec_driven_check6_waiver_recomputes_hash(spec_driven_verify: str) -> None:
    """(d) Check 6 must state that waiver-check recomputes the hash (stale = rejected)."""
    idx = spec_driven_verify.find("### Check 6")
    assert idx > 0
    section = spec_driven_verify[idx : idx + 4000]
    # The ADR-001/008 guarantee: waiver-check recomputes vs live diff
    assert (
        "recompute" in section.lower()
        or "recomputes" in section.lower()
        or ("stale" in section and "waiver" in section)
    ), (
        "Check 6 must state that waiver-check recomputes the hash so a stale waiver "
        "is rejected (ADR-008 diff-expiry contract)"
    )


# ── FIX-6: spec_need CLI calls in Check 6 use --root <WT> ────────────────────


def test_spec_driven_check6_uses_root_wt(spec_driven_verify: str) -> None:
    """FIX-6: spec-driven Check 6 spec_need CLI calls MUST use --root <WT>, not --root .

    Under feature_branch_workflow, files live in <WT>. Using --root . reads
    project-root files (stale/absent for add-case new files) → compute_subject_hash
    raises → waiver check breaks.
    """
    idx = spec_driven_verify.find("### Check 6")
    assert idx > 0, "Check 6 heading not found"
    section = spec_driven_verify[idx : idx + 4000]
    # All spec_need calls in Check 6 must use --root <WT>
    import re as _re

    single_line_pattern = _re.compile(r"hm spec_need \S+ .*?--root (\S+)")
    matches = single_line_pattern.findall(section)
    assert matches, "No spec_need --root arguments found in Check 6"
    dot_roots = [m for m in matches if m.strip() in (".", "./", ".\\")]
    assert dot_roots == [], (
        f"Check 6 spec_need CLI calls must use --root <WT>, not --root .; "
        f"found {len(dot_roots)} '--root .' occurrences — FIX-6 (R2-P2b)"
    )


# ── regression: task-driven must not get 6-count phrasing either ────────────


def test_task_driven_no_6_count_phrases(task_driven_verify: str) -> None:
    """Sanity: task-driven render must not accidentally contain '6 Checks' or '6-check'."""
    for pattern in ("The 6 Checks", "6-check", "6-check stop sign", "6-check rubric"):
        assert pattern not in task_driven_verify, (
            f"task-driven verify must not contain spec-driven count phrasing '{pattern}'"
        )


# ── snapshot-level: verify SKILL still has exactly 5 numbered checks ─────────


def test_verify_skill_still_5_checks_task_driven(
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    """The verify-before-completion SKILL must keep exactly 5 numbered checks.

    The SKILL is intentionally NOT updated for Phase 3 — it is a separate
    asset managed independently (test_verify.py:test_work_docs_footgun_probe
    already asserts this for task-driven; we add the spec-driven assertion here
    to ensure the SKILL is unchanged in both modes).
    """
    # Use task-driven (the SKILL is shared/same in both dev_modes)
    out = tmp_path_factory.mktemp("skill-check")
    bp = synthesize(
        ProjectProfile(),
        InterviewAnswers(
            preset=Preset.PRODUCTION,
            targets=[Target.CLAUDE_CODE],
            dev_mode=DevMode.TASK_DRIVEN,
        ),
    )
    render(bp, out, freeze_time=DEFAULT_FREEZE_TIME)
    skill_path = out / "skills" / "verify-before-completion" / "SKILL.md"
    assert skill_path.is_file(), "verify-before-completion SKILL.md not found"
    skill_text = skill_path.read_text(encoding="utf-8")
    check_headings = re.findall(r"^### (\d+)\. ", skill_text, flags=re.MULTILINE)
    assert check_headings == ["1", "2", "3", "4", "5"], (
        f"verify-before-completion SKILL must keep exactly 5 numbered checks; "
        f"got headings={check_headings}. Check 6 belongs in the stage prompt only."
    )
