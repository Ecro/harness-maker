"""Tests for Pydantic data models in harness_maker.models."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from harness_maker.models import (
    AtomicStage,
    Blueprint,
    ConflictItem,
    FileEntry,
    HarnessConfig,
    InterviewAnswers,
    Locale,
    ModelTier,
    Preset,
    ProjectProfile,
    ReconcileDecision,
    WorkflowDef,
)


# ──────────────────────────────────────────────────────────────────────────────
# Enums
# ──────────────────────────────────────────────────────────────────────────────


def test_locale_members() -> None:
    assert Locale.KO.value == "ko"
    assert Locale.EN.value == "en"
    assert {m.value for m in Locale} == {"ko", "en"}


def test_preset_members() -> None:
    assert Preset.SIDE.value == "Side"
    assert Preset.PRODUCTION.value == "Production"
    assert {m.value for m in Preset} == {"Side", "Production"}


def test_model_tier_members() -> None:
    assert {m.value for m in ModelTier} == {"opus", "sonnet", "haiku"}


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
    assert {m.value for m in ReconcileDecision} == {"keep", "replace", "both"}


# ──────────────────────────────────────────────────────────────────────────────
# HarnessConfig
# ──────────────────────────────────────────────────────────────────────────────


def test_harness_config_defaults() -> None:
    cfg = HarnessConfig()
    assert cfg.locale == Locale.KO
    assert cfg.preset == Preset.SIDE
    assert cfg.default_workflow == "dev"
    assert cfg.workflows == []
    assert cfg.execution == {}
    assert cfg.caching == "agent-aware"


def test_harness_config_round_trip_json() -> None:
    cfg = HarnessConfig(
        locale=Locale.EN,
        preset=Preset.PRODUCTION,
        workflows=[WorkflowDef(name="dev", stages=[AtomicStage.EXECUTE])],
        execution={"default": "step"},
    )
    raw_json = cfg.model_dump_json()
    restored = HarnessConfig.model_validate_json(raw_json)
    assert restored == cfg


def test_harness_config_extra_forbidden() -> None:
    with pytest.raises(ValidationError):
        HarnessConfig.model_validate({"unknown_field": 1})


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
        files=[FileEntry(path=Path("/tmp/x.md"), sha256="abc")],
    )
    assert len(bp.files) == 1
    assert bp.files[0].path == Path("/tmp/x.md")
    assert bp.files[0].sha256 == "abc"


def test_blueprint_default_empty() -> None:
    bp = Blueprint()
    assert bp.files == []
    assert isinstance(bp.config, HarnessConfig)


def test_file_entry_defaults() -> None:
    fe = FileEntry(path=Path("a.md"))
    assert fe.sha256 == ""
    assert fe.rendered_from is None
    assert fe.provenance == {}


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
    assert ans.workflow_names == ["dev"]
    assert ans.default_workflow == "dev"
    assert ans.reviewers == []
    assert ans.consensus == "single"
    assert ans.caching == "agent-aware"


# ──────────────────────────────────────────────────────────────────────────────
# ConflictItem
# ──────────────────────────────────────────────────────────────────────────────


def test_conflict_item_with_decision() -> None:
    ci = ConflictItem(
        existing_path=Path("/tmp/old"),
        new_path=Path("/tmp/new"),
        decision=ReconcileDecision.KEEP,
    )
    assert ci.decision == ReconcileDecision.KEEP


def test_conflict_item_decision_none_default() -> None:
    ci = ConflictItem(existing_path=Path("/tmp/old"), new_path=Path("/tmp/new"))
    assert ci.decision is None
