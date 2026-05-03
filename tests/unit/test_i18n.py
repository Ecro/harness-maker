"""Tests for harness_maker.i18n locale resolution and message lookup."""

from __future__ import annotations

from pathlib import Path

from harness_maker.i18n import Locale, resolve_locale, t


def _write_harness_yaml(project_dir: Path, body: str) -> None:
    claude_dir = project_dir / ".claude"
    claude_dir.mkdir(parents=True, exist_ok=True)
    (claude_dir / "harness.yaml").write_text(body)


def test_resolve_locale_returns_none_when_no_yaml(tmp_path: Path) -> None:
    assert resolve_locale(tmp_path) is None


def test_resolve_locale_ko(tmp_path: Path) -> None:
    _write_harness_yaml(tmp_path, "locale: ko\n")
    assert resolve_locale(tmp_path) == Locale.KO


def test_resolve_locale_en(tmp_path: Path) -> None:
    _write_harness_yaml(tmp_path, "locale: en\n")
    assert resolve_locale(tmp_path) == Locale.EN


def test_resolve_locale_invalid_value_returns_none(tmp_path: Path) -> None:
    _write_harness_yaml(tmp_path, "locale: fr\n")
    assert resolve_locale(tmp_path) is None


def test_t_apply_done_ko() -> None:
    msg = t("apply_done", Locale.KO)
    assert msg == "적용 완료."


def test_t_apply_done_en() -> None:
    msg = t("apply_done", Locale.EN)
    assert msg == "Apply complete."


def test_t_q1_choose_language_substitutes_var() -> None:
    msg = t("q1_choose_language", Locale.KO, lang="한국어")
    assert "한국어" in msg
