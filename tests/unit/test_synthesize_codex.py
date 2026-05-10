"""Phase 9 tests: Codex target full-blueprint integration + context_lint AGENTS.md threshold.

RED before Phase 9 implementation:
- AGENTS.md not in THRESHOLDS (context_lint.py)
- Full synthesize() with codex target not tested end-to-end

GREEN after Phase 9:
- synthesize(codex) emits AGENTS.md + .codex/ + .agents/skills/ (11+7=18 skill paths)
- synthesize(claude-code only) emits NO .codex/, AGENTS.md, or .agents/ paths
- context_lint.lint() warns AGENTS.md over 500-line Production threshold
- context_lint.lint() passes AGENTS.md under 500-line threshold
"""

from __future__ import annotations

from pathlib import Path

from harness_maker.context_lint import THRESHOLDS, lint
from harness_maker.interview import interview
from harness_maker.models import Preset, Target
from harness_maker.profile import profile
from harness_maker.synthesize import synthesize


def _make_answers(fix_dir: Path, targets: list[str]):
    """Build InterviewAnswers with given targets using autoloop mode."""
    p = profile(fix_dir)
    a = interview(p, autoloop_mode=True)
    return a.model_copy(update={"targets": {Target(t) for t in targets}})


# ── synthesize: codex target wiring ───────────────────────────────────────────


def test_synthesize_codex_target_emits_agents_md(tmp_path: Path) -> None:
    """synthesize() with codex target must include AGENTS.md in blueprint files."""
    answers = _make_answers(tmp_path, ["codex"])
    bp = synthesize(profile(tmp_path), answers)
    paths = {str(f.path) for f in bp.files}
    assert "AGENTS.md" in paths, "Blueprint missing AGENTS.md for codex target"


def test_synthesize_codex_target_emits_codex_config_toml(tmp_path: Path) -> None:
    """synthesize() with codex target must include .codex/config.toml."""
    answers = _make_answers(tmp_path, ["codex"])
    bp = synthesize(profile(tmp_path), answers)
    paths = {str(f.path) for f in bp.files}
    assert ".codex/config.toml" in paths, "Blueprint missing .codex/config.toml"


def test_synthesize_codex_target_emits_skill_paths(tmp_path: Path) -> None:
    """synthesize() with codex target must emit 11 + 7 + N workflows + 1 loop .agents/skills/ entries."""
    answers = _make_answers(tmp_path, ["codex"])
    bp = synthesize(profile(tmp_path), answers)
    skill_paths = [str(f.path) for f in bp.files if str(f.path).startswith(".agents/skills/")]
    n_workflows = len(answers.fused_workflows)
    expected = 11 + 7 + n_workflows + 1  # existing + stages + workflows + loop
    assert len(skill_paths) == expected, (
        f"Expected {expected} .agents/skills/ entries, got {len(skill_paths)}"
    )


def test_synthesize_claude_code_only_no_agents_md(tmp_path: Path) -> None:
    """synthesize() with only claude-code target must NOT include AGENTS.md."""
    answers = _make_answers(tmp_path, ["claude-code"])
    bp = synthesize(profile(tmp_path), answers)
    paths = {str(f.path) for f in bp.files}
    assert "AGENTS.md" not in paths, "Blueprint must not emit AGENTS.md for claude-code-only target"


def test_synthesize_claude_code_only_no_codex_paths(tmp_path: Path) -> None:
    """synthesize() with only claude-code target must emit NO .codex/ or .agents/ paths."""
    answers = _make_answers(tmp_path, ["claude-code"])
    bp = synthesize(profile(tmp_path), answers)
    codex_paths = [
        str(f.path)
        for f in bp.files
        if str(f.path).startswith(".codex/") or str(f.path).startswith(".agents/")
    ]
    assert not codex_paths, f"claude-code-only target should emit no Codex paths; got {codex_paths}"


# ── context_lint: AGENTS.md threshold ─────────────────────────────────────────


def test_context_lint_agents_md_threshold_exists_for_production() -> None:
    """THRESHOLDS must contain an AGENTS.md entry for Production preset."""
    assert ("AGENTS.md", Preset.PRODUCTION.value) in THRESHOLDS, (
        "THRESHOLDS missing ('AGENTS.md', 'Production') entry"
    )


def test_context_lint_agents_md_production_threshold_is_500() -> None:
    """AGENTS.md Production threshold must be 500 lines (matches CLAUDE.md Production)."""
    assert THRESHOLDS[("AGENTS.md", Preset.PRODUCTION.value)] == 500, (
        "AGENTS.md Production threshold must be 500"
    )


def test_context_lint_agents_md_under_threshold_no_warning(tmp_path: Path) -> None:
    """lint() must return no warnings for AGENTS.md under 500 lines (Production)."""
    agents_md = tmp_path / "AGENTS.md"
    agents_md.write_text("# AGENTS.md\n" + "line\n" * 10, encoding="utf-8")
    warnings = lint(agents_md, "AGENTS.md", Preset.PRODUCTION)
    assert not warnings, f"Unexpected warnings for short AGENTS.md: {warnings}"


def test_context_lint_agents_md_over_threshold_warns(tmp_path: Path) -> None:
    """lint() must return a warning for AGENTS.md exceeding 500 lines (Production)."""
    agents_md = tmp_path / "AGENTS.md"
    agents_md.write_text("# AGENTS.md\n" + "line\n" * 510, encoding="utf-8")
    warnings = lint(agents_md, "AGENTS.md", Preset.PRODUCTION)
    assert warnings, "Expected warning for AGENTS.md over 500-line threshold"
    assert any("AGENTS.md" in w or "500" in w for w in warnings), (
        f"Warning should mention AGENTS.md or 500-line limit: {warnings}"
    )
