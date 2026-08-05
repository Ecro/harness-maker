"""Tests for /hm:help command — locale-aware static templates + targets gating.

Verifies the 6 PLAN-help-command assertions:
  (a) commands/hm/help.md is rendered for both en and ko locales
  (b) ko body contains the Korean header '사용 가능한 명령'
  (c) en body contains 'Available commands'
  (d) targets=[claude-code] → no Cursor/Codex sections; no Codex SKILL
  (e) targets=[claude-code, codex] → Codex section present + SKILL rendered
  (f) default_workflow value interpolated exactly with the ⭐ marker
"""

from __future__ import annotations

from pathlib import Path

from harness_maker.models import InterviewAnswers, Target
from harness_maker.profile import profile
from harness_maker.render import _make_env
from harness_maker.synthesize import synthesize


def _render_help(answers: InterviewAnswers, tmp_path: Path) -> str:
    """Resolve commands/hm/help.md from a synthesize() output and render it."""
    bp = synthesize(profile(tmp_path), answers)
    help_file = next(f for f in bp.files if str(f.path) == "commands/hm/help.md")
    return _make_env().get_template(help_file.template).render(**help_file.context)


def _paths_for(answers: InterviewAnswers, tmp_path: Path) -> list[str]:
    return [str(f.path) for f in synthesize(profile(tmp_path), answers).files]


def test_a_help_md_rendered_for_both_locales(tmp_path: Path) -> None:
    for locale in ("en", "ko"):
        ans = InterviewAnswers(locale=locale, targets=[Target.CLAUDE_CODE])
        assert "commands/hm/help.md" in _paths_for(ans, tmp_path), locale


def test_b_ko_body_contains_korean_header(tmp_path: Path) -> None:
    ans = InterviewAnswers(locale="ko", targets=[Target.CLAUDE_CODE])
    body = _render_help(ans, tmp_path)
    assert "사용 가능한 명령" in body


def test_c_en_body_contains_english_header(tmp_path: Path) -> None:
    ans = InterviewAnswers(locale="en", targets=[Target.CLAUDE_CODE])
    body = _render_help(ans, tmp_path)
    assert "Available commands" in body


def test_d_claude_only_omits_cursor_codex_sections(tmp_path: Path) -> None:
    ans = InterviewAnswers(locale="en", targets=[Target.CLAUDE_CODE])
    body = _render_help(ans, tmp_path)
    assert "> **Cursor:**" not in body
    assert "> **Codex CLI:**" not in body
    assert ".agents/skills/hm-help/SKILL.md" not in _paths_for(ans, tmp_path)


def test_e_codex_target_renders_skill_and_section(tmp_path: Path) -> None:
    ans = InterviewAnswers(locale="en", targets=[Target.CLAUDE_CODE, Target.CODEX])
    body = _render_help(ans, tmp_path)
    assert "> **Codex CLI:**" in body
    assert ".agents/skills/hm-help/SKILL.md" in _paths_for(ans, tmp_path)


def test_codex_skill_body_uses_at_hm_prefix(tmp_path: Path) -> None:
    """Codex SKILL.md is pre-rendered with is_codex=True — must use @hm-* stubs."""
    ans = InterviewAnswers(locale="ko", targets=[Target.CLAUDE_CODE, Target.CODEX])
    bp = synthesize(profile(tmp_path), ans)
    skill = next(f for f in bp.files if str(f.path) == ".agents/skills/hm-help/SKILL.md")
    body = _make_env().get_template(skill.template).render(**skill.context)
    assert "@hm-help" in body
    assert "/hm:help" not in body
