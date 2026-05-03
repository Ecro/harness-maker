"""Tests for harness_maker.i18n locale resolution and message lookup."""

from __future__ import annotations

from pathlib import Path

from harness_maker.i18n import DEFAULT_LOCALE, Locale, resolve_locale, t


def _write_harness_yaml(project_dir: Path, body: str) -> None:
    claude_dir = project_dir / ".claude"
    claude_dir.mkdir(parents=True, exist_ok=True)
    (claude_dir / "harness.yaml").write_text(body)


def test_resolve_locale_falls_back_to_en_when_no_yaml(tmp_path: Path) -> None:
    assert resolve_locale(tmp_path) == DEFAULT_LOCALE == "en"


def test_resolve_locale_ko(tmp_path: Path) -> None:
    _write_harness_yaml(tmp_path, "locale: ko\n")
    assert resolve_locale(tmp_path) == "ko"


def test_resolve_locale_en(tmp_path: Path) -> None:
    _write_harness_yaml(tmp_path, "locale: en\n")
    assert resolve_locale(tmp_path) == "en"


def test_resolve_locale_accepts_arbitrary_tag(tmp_path: Path) -> None:
    """Free-text: any tag passes through verbatim — t() handles fallback."""
    _write_harness_yaml(tmp_path, "locale: fr\n")
    assert resolve_locale(tmp_path) == "fr"


def test_resolve_locale_falls_back_when_yaml_missing_locale(tmp_path: Path) -> None:
    _write_harness_yaml(tmp_path, "preset: Side\n")
    assert resolve_locale(tmp_path) == "en"


def test_t_apply_done_ko() -> None:
    msg = t("apply_done", "ko")
    assert msg == "적용 완료."


def test_t_apply_done_en() -> None:
    msg = t("apply_done", "en")
    assert msg == "Apply complete."


def test_t_unknown_locale_falls_back_to_en() -> None:
    """Unknown locale tag → English catalog (silent fallback)."""
    msg = t("apply_done", "ja")
    assert msg == "Apply complete."


def test_t_locale_enum_still_accepted() -> None:
    """Backward compat: t() accepts Locale enum as well as raw str."""
    msg = t("apply_done", Locale.KO)
    assert msg == "적용 완료."


def test_t_q1_choose_language_substitutes_var() -> None:
    msg = t("q1_choose_language", "ko", lang="한국어")
    assert "한국어" in msg
