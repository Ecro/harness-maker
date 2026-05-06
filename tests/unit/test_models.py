"""Tests for Pydantic data models in harness_maker.models."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from harness_maker.models import (
    AtomicStage,
    Blueprint,
    ConflictItem,
    DevMode,
    FileEntry,
    HarnessConfig,
    InterviewAnswers,
    Locale,
    ModelTier,
    Preset,
    ProjectProfile,
    ReconcileDecision,
    Target,
    WorkflowDef,
)

# ──────────────────────────────────────────────────────────────────────────────
# Enums
# ──────────────────────────────────────────────────────────────────────────────


def test_locale_members() -> None:
    assert Locale.KO.value == "ko"
    assert Locale.EN.value == "en"
    assert {m.value for m in Locale} == {"ko", "en"}


def test_dev_mode_members() -> None:
    assert DevMode.SPEC_DRIVEN.value == "spec-driven"
    assert DevMode.TASK_DRIVEN.value == "task-driven"
    assert {m.value for m in DevMode} == {"spec-driven", "task-driven"}


def test_preset_members() -> None:
    assert Preset.SIDE.value == "Side"
    assert Preset.PRODUCTION.value == "Production"
    assert {m.value for m in Preset} == {"Side", "Production"}


def test_model_tier_members() -> None:
    assert {m.value for m in ModelTier} == {"opus", "sonnet", "haiku"}


def test_target_members() -> None:
    assert Target.CLAUDE_CODE.value == "claude-code"
    assert Target.CURSOR.value == "cursor"
    assert {m.value for m in Target} == {"claude-code", "cursor"}


def test_atomic_stage_members() -> None:
    assert {m.value for m in AtomicStage} == {
        "research",
        "spec",
        "plan",
        "execute",
        "review",
        "wrapup",
        "verify",
    }


def test_reconcile_decision_members() -> None:
    assert {m.value for m in ReconcileDecision} == {"keep", "replace", "both", "merge_block"}


# ──────────────────────────────────────────────────────────────────────────────
# HarnessConfig
# ──────────────────────────────────────────────────────────────────────────────


def test_harness_config_defaults() -> None:
    cfg = HarnessConfig()
    assert cfg.locale == "en"
    assert cfg.preset == Preset.SIDE
    assert cfg.dev_mode == DevMode.SPEC_DRIVEN
    assert cfg.default_workflow == "dev"
    assert "dev" in cfg.workflows
    assert AtomicStage.EXECUTE in cfg.workflows["dev"]
    assert cfg.execution == {}
    assert cfg.caching == "agent-aware"
    assert cfg.project == {"domains": []}
    assert cfg.spec == {"dir": "specs/"}


def test_harness_config_accepts_arbitrary_locale_tag() -> None:
    """Free-text locale: ``ja`` is accepted even though we ship no ja catalog."""
    cfg = HarnessConfig(locale="ja")
    assert cfg.locale == "ja"


def test_harness_config_round_trip_json() -> None:
    cfg = HarnessConfig(
        locale="en",
        preset=Preset.PRODUCTION,
        dev_mode=DevMode.TASK_DRIVEN,
        workflows={"dev": [AtomicStage.EXECUTE]},
        execution={"default": "step"},
    )
    raw_json = cfg.model_dump_json()
    restored = HarnessConfig.model_validate_json(raw_json)
    assert restored == cfg


def test_harness_config_extra_forbidden() -> None:
    with pytest.raises(ValidationError):
        HarnessConfig.model_validate({"unknown_field": 1})


def test_harness_config_targets_default() -> None:
    """Default = [claude-code] (옛 yaml fallback 보호용 default factory)."""
    cfg = HarnessConfig()
    assert cfg.targets == [Target.CLAUDE_CODE]


def test_harness_config_targets_multi_select() -> None:
    cfg = HarnessConfig(targets=[Target.CLAUDE_CODE, Target.CURSOR])
    assert cfg.targets == [Target.CLAUDE_CODE, Target.CURSOR]


def test_harness_config_targets_cursor_only() -> None:
    cfg = HarnessConfig(targets=[Target.CURSOR])
    assert cfg.targets == [Target.CURSOR]


def test_harness_config_targets_empty_raises() -> None:
    """빈 list 는 min_length=1 으로 거부 — 인터뷰가 명시 multi-select 강제."""
    with pytest.raises(ValidationError):
        HarnessConfig(targets=[])


def test_harness_config_targets_invalid_value_raises() -> None:
    with pytest.raises(ValidationError):
        HarnessConfig.model_validate({"targets": ["not-a-real-target"]})


def test_harness_config_recommended_model_default() -> None:
    """CLAUDE.md § Targets 정책: Cursor user 도 Anthropic 모델 권장."""
    cfg = HarnessConfig()
    assert cfg.recommended_model == "claude-opus-4-7"


def test_harness_config_recommended_model_override() -> None:
    cfg = HarnessConfig(recommended_model="claude-sonnet-4-6")
    assert cfg.recommended_model == "claude-sonnet-4-6"


def test_harness_config_targets_schema_gap_fallback() -> None:
    """옛 yaml (``targets`` 키 없음) load 시 default_factory 가 [claude-code] 보호.

    Warning log 는 yaml-aware loader (interview.py / synthesize.py) 책임 —
    Phase 2.1 이후. 본 test 는 model 단의 default 박힘만 확인.
    """
    cfg = HarnessConfig.model_validate({"locale": "en"})
    assert cfg.targets == [Target.CLAUDE_CODE]


# ──────────────────────────────────────────────────────────────────────────────
# WorkflowDef
# ──────────────────────────────────────────────────────────────────────────────


def test_workflow_def_valid_name() -> None:
    wf = WorkflowDef(name="dev", stages=[AtomicStage.EXECUTE])
    assert wf.name == "dev"
    assert wf.stages == [AtomicStage.EXECUTE]


def test_workflow_def_uppercase_name_raises() -> None:
    with pytest.raises(ValidationError):
        WorkflowDef(name="Bad-Name", stages=[AtomicStage.EXECUTE])


def test_workflow_def_underscore_name_raises() -> None:
    with pytest.raises(ValidationError):
        WorkflowDef(name="a_b", stages=[AtomicStage.EXECUTE])


def test_workflow_def_starts_with_digit_raises() -> None:
    with pytest.raises(ValidationError):
        WorkflowDef(name="1dev", stages=[AtomicStage.EXECUTE])


# ──────────────────────────────────────────────────────────────────────────────
# Blueprint + FileEntry
# ──────────────────────────────────────────────────────────────────────────────


def test_blueprint_with_file_entry() -> None:
    bp = Blueprint(
        config=HarnessConfig(),
        files=[FileEntry(path=Path("/tmp/x.md"), template="t.md.j2")],
    )
    assert len(bp.files) == 1
    assert bp.files[0].path == Path("/tmp/x.md")
    assert bp.files[0].template == "t.md.j2"


def test_blueprint_default_empty() -> None:
    bp = Blueprint()
    assert bp.files == []
    assert isinstance(bp.config, HarnessConfig)


def test_file_entry_defaults() -> None:
    fe = FileEntry(path=Path("a.md"), template="a.md.j2")
    assert fe.template == "a.md.j2"
    assert fe.context == {}
    assert fe.frontmatter == {}
    assert fe.body_sha256 is None


# ──────────────────────────────────────────────────────────────────────────────
# ProjectProfile
# ──────────────────────────────────────────────────────────────────────────────


def test_project_profile_defaults() -> None:
    p = ProjectProfile()
    assert p.stack == ["unknown"]
    assert p.scale == "small"
    assert p.lifecycle == "experiment"
    assert p.existing_dotclaude is False
    assert p.spec_only is False
    assert p.vault_member is False


def test_project_profile_custom() -> None:
    p = ProjectProfile(
        stack=["python", "rust"],
        scale="medium",
        lifecycle="active",
        existing_dotclaude=True,
        spec_only=False,
        vault_member=True,
    )
    assert "python" in p.stack
    assert p.vault_member is True


# ──────────────────────────────────────────────────────────────────────────────
# InterviewAnswers
# ──────────────────────────────────────────────────────────────────────────────


def test_interview_answers_defaults() -> None:
    ans = InterviewAnswers()
    assert ans.locale == "en"
    assert ans.targets == [Target.CLAUDE_CODE]
    assert ans.preset.value == "Side"
    assert ans.dev_mode == DevMode.SPEC_DRIVEN
    assert "exec-rev-wrap" in ans.fused_workflows
    assert ans.default_workflow == "exec-rev-wrap"
    assert ans.reviewers == {"installed": [], "enabled": []}
    assert ans.skills == {"installed": [], "enabled": []}
    assert ans.consensus == "single"
    assert ans.caching == "agent-aware"


def test_interview_answers_targets_multi_select() -> None:
    ans = InterviewAnswers(targets=[Target.CLAUDE_CODE, Target.CURSOR])
    assert ans.targets == [Target.CLAUDE_CODE, Target.CURSOR]


def test_interview_answers_targets_empty_raises() -> None:
    with pytest.raises(ValidationError):
        InterviewAnswers(targets=[])


# ──────────────────────────────────────────────────────────────────────────────
# ConflictItem
# ──────────────────────────────────────────────────────────────────────────────


def test_conflict_item_with_decision() -> None:
    ci = ConflictItem(
        path=Path("/tmp/x"),
        decision=ReconcileDecision.KEEP,
        reason="hash-mismatch-user-modified",
    )
    assert ci.decision == ReconcileDecision.KEEP
    assert ci.reason == "hash-mismatch-user-modified"


def test_conflict_item_decision_none_default() -> None:
    ci = ConflictItem(path=Path("/tmp/x"))
    assert ci.decision is None
    assert ci.reason is None
