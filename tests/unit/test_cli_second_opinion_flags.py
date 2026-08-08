"""CLI flag semantics for --second-opinion-models / --autonomy-* (ADR-009/010)."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from harness_maker.cli import _build_autonomy_override, _build_second_opinion_override, app
from harness_maker.models import AutonomyConfig, SecondOpinionConfig

runner = CliRunner()


def _make(tmp_path: Path, *flags: str):  # type: ignore[no-untyped-def]
    return runner.invoke(app, ["make", str(tmp_path), "--autoloop", *flags])


def _read_yaml(tmp_path: Path) -> str:
    return (tmp_path / ".claude" / "harness.yaml").read_text(encoding="utf-8")


def test_both_models_flag(tmp_path: Path) -> None:
    result = _make(tmp_path, "--second-opinion-models", "codex,antigravity")
    assert result.exit_code == 0
    body = _read_yaml(tmp_path)
    assert 'models: ["codex", "antigravity"]' in body


def test_empty_string_disables(tmp_path: Path) -> None:
    result = _make(tmp_path, "--second-opinion-models", "")
    assert result.exit_code == 0
    assert "models: []" in _read_yaml(tmp_path)


def test_invalid_model_errors(tmp_path: Path) -> None:
    result = _make(tmp_path, "--second-opinion-models", "codex,bogus")
    assert result.exit_code == 1
    assert "invalid" in result.output.lower()


def test_duplicate_models_deduped() -> None:
    cfg = _build_second_opinion_override("codex,codex,antigravity", SecondOpinionConfig())
    assert isinstance(cfg, SecondOpinionConfig)
    assert cfg.models == ["codex", "antigravity"]


def test_whitespace_tolerated() -> None:
    cfg = _build_second_opinion_override(" codex , antigravity ", SecondOpinionConfig())
    assert isinstance(cfg, SecondOpinionConfig)
    assert cfg.models == ["codex", "antigravity"]


def test_second_opinion_preserves_existing_subconfigs() -> None:
    from harness_maker.models import SecondOpinionAntigravityConfig

    existing = SecondOpinionConfig(
        models=[],
        agents=["code-reviewer"],
        antigravity=SecondOpinionAntigravityConfig(model="Gemini 3.5 Flash (Low)"),
    )
    cfg = _build_second_opinion_override("antigravity", existing)
    assert isinstance(cfg, SecondOpinionConfig)
    assert cfg.agents == ["code-reviewer"]
    assert cfg.antigravity.model == "Gemini 3.5 Flash (Low)"


def test_autonomy_level_alone_enables() -> None:
    """`--autonomy-level` alone must not turn persistence ON for a non-persistent project.

    The `existing` here is pinned gated/False on purpose: a bare `AutonomyConfig()` now
    MEANS "already persistent", so passing one would assert preservation, not the flag's
    documented "persistence defaults off unless explicitly set" contract.
    """
    existing = AutonomyConfig(level="gated", autopilot_persistent=False)
    cfg = _build_autonomy_override("auto_safe", None, existing)
    assert isinstance(cfg, AutonomyConfig)
    assert cfg.level == "auto_safe"
    assert cfg.autopilot_persistent is False


def test_autonomy_persistent_pair() -> None:
    cfg = _build_autonomy_override("full", True, AutonomyConfig())
    assert isinstance(cfg, AutonomyConfig)
    # B1/ADR-001: `full` is the pre-0.51 name for `auto_safe` and is demoted, never promoted
    # to the new `auto_full`. Loading must not escalate autonomy.
    assert cfg.level == "auto_safe"
    assert cfg.autopilot_persistent is True


def test_autonomy_override_preserves_pipeline_and_extra_deny() -> None:
    # review P1: a --autonomy-* override must NOT drop user-customized pipeline or the
    # security-relevant additive extra_deny baseline.
    from harness_maker.models import AtomicStage

    existing = AutonomyConfig(
        level="auto_safe",
        pipeline=[AtomicStage.EXECUTE, AtomicStage.REVIEW],
        extra_deny=["Bash(rm:*)"],
    )
    cfg = _build_autonomy_override(None, True, existing)
    assert isinstance(cfg, AutonomyConfig)
    assert cfg.pipeline == [AtomicStage.EXECUTE, AtomicStage.REVIEW]
    assert cfg.extra_deny == ["Bash(rm:*)"]
    assert cfg.autopilot_persistent is True
    assert cfg.level == "auto_safe"


def test_autonomy_invalid_level_errors() -> None:
    import pytest
    import typer

    with pytest.raises(typer.Exit) as exc_info:
        _build_autonomy_override("turbo", None, AutonomyConfig())
    assert exc_info.value.exit_code == 1


def test_autonomy_level_flag_renders(tmp_path: Path) -> None:
    result = _make(tmp_path, "--autonomy-level", "auto_safe")
    assert result.exit_code == 0
    assert 'level: "auto_safe"' in _read_yaml(tmp_path)


def test_omitting_flags_leaves_defaults(tmp_path: Path) -> None:
    result = _make(tmp_path)
    assert result.exit_code == 0
    body = _read_yaml(tmp_path)
    assert "models: []" in body  # default: second opinion off
