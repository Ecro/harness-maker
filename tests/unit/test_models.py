"""Tests for Pydantic data models in harness_maker.models."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from harness_maker.models import (
    AdaptiveConfig,
    AtomicStage,
    Blueprint,
    Confidence,
    ConflictItem,
    DevMode,
    FileEntry,
    HarnessConfig,
    InterviewAnswers,
    Locale,
    ModelTier,
    Preset,
    ProjectProfile,
    Recommendation,
    RecommendationEvidence,
    ReconcileDecision,
    SecondBrainConfig,
    SecondBrainFolder,
    SecondBrainNoteType,
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
    assert Target.CODEX.value == "codex"
    assert {m.value for m in Target} == {"claude-code", "cursor", "codex"}


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


def test_harness_config_targets_codex() -> None:
    cfg = HarnessConfig(targets=[Target.CODEX])
    assert cfg.targets == [Target.CODEX]


def test_harness_config_targets_all_three() -> None:
    cfg = HarnessConfig(targets=[Target.CLAUDE_CODE, Target.CURSOR, Target.CODEX])
    assert cfg.targets == [Target.CLAUDE_CODE, Target.CURSOR, Target.CODEX]


def test_interview_answers_targets_codex() -> None:
    from harness_maker.models import InterviewAnswers

    ans = InterviewAnswers(targets=[Target.CODEX])
    assert ans.targets == [Target.CODEX]


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


def test_second_brain_config_defaults_disabled() -> None:
    cfg = SecondBrainConfig()
    assert cfg.enabled is False
    assert cfg.backend == "filesystem"
    assert cfg.project_id == ""
    assert cfg.vault_path == ""
    assert cfg.trusted_allowlist is True
    assert cfg.folders == []
    assert cfg.required_frontmatter == ["type", "created", "updated", "tags", "links"]


def test_second_brain_config_accepts_filesystem_allowlist() -> None:
    cfg = SecondBrainConfig(
        enabled=True,
        project_id="harness-maker",
        vault_path="../vault",
        folders=[
            SecondBrainFolder(
                path="Projects/harness-maker",
                read=True,
                write=True,
                note_types=[SecondBrainNoteType.DECISION, SecondBrainNoteType.FAILURE],
            )
        ],
    )
    assert cfg.enabled is True
    assert cfg.folders[0].path == "Projects/harness-maker"
    assert cfg.folders[0].note_types == [
        SecondBrainNoteType.DECISION,
        SecondBrainNoteType.FAILURE,
    ]


def test_second_brain_rejects_non_filesystem_backend() -> None:
    with pytest.raises(ValidationError):
        SecondBrainConfig(
            enabled=True,
            backend="rest",
            project_id="harness-maker",
            vault_path="../vault",
        )


def test_second_brain_folder_rejects_absolute_path() -> None:
    with pytest.raises(ValidationError):
        SecondBrainFolder(path="/Users/noel/Vault", read=True)


def test_second_brain_folder_rejects_dot_dot_traversal() -> None:
    """REVIEW-2026-05-17 security finding: '..' segments must be blocked.

    Without this guard, --add-folder ../escape could persist a traversal
    path into harness.yaml; downstream search_notes would then iterate
    Markdown files outside the vault boundary.
    """
    with pytest.raises(ValidationError, match="\\.\\.|traversal"):
        SecondBrainFolder(path="../escape", read=True)
    with pytest.raises(ValidationError, match="\\.\\.|traversal"):
        SecondBrainFolder(path="Projects/../../outside", read=True)


def test_harness_config_carries_second_brain_config() -> None:
    cfg = HarnessConfig(
        second_brain=SecondBrainConfig(
            enabled=True,
            project_id="harness-maker",
            vault_path="../vault",
            folders=[SecondBrainFolder(path="Projects/harness-maker", read=True, write=True)],
        )
    )
    restored = HarnessConfig.model_validate_json(cfg.model_dump_json())
    assert restored.second_brain.enabled is True
    assert restored.second_brain.project_id == "harness-maker"
    assert restored.second_brain.folders[0].write is True


def test_second_brain_requires_project_id_for_write_folders() -> None:
    with pytest.raises(ValidationError, match="project_id is required"):
        SecondBrainConfig(
            enabled=True,
            vault_path="../vault",
            folders=[SecondBrainFolder(path="Projects/harness-maker", write=True)],
        )


def test_second_brain_write_folder_must_include_project_id_segment() -> None:
    with pytest.raises(ValidationError, match="must include project_id"):
        SecondBrainConfig(
            enabled=True,
            project_id="harness-maker",
            vault_path="../vault",
            folders=[SecondBrainFolder(path="Projects/shared", write=True)],
        )


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
    assert p.lifecycle == "dormant"
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


# ──────────────────────────────────────────────────────────────────────────────
# sibling_repos — Phase 1 (multi-repo support)
# ──────────────────────────────────────────────────────────────────────────────


def test_harness_config_sibling_repos_default_empty() -> None:
    cfg = HarnessConfig()
    assert cfg.sibling_repos == []


def test_harness_config_sibling_repos_relative_path_valid() -> None:
    cfg = HarnessConfig(sibling_repos=["../repo-b"])
    assert cfg.sibling_repos == ["../repo-b"]


def test_harness_config_sibling_repos_multiple_valid() -> None:
    cfg = HarnessConfig(sibling_repos=["../repo-b", "../repo-c"])
    assert cfg.sibling_repos == ["../repo-b", "../repo-c"]


def test_harness_config_sibling_repos_absolute_rejected() -> None:
    with pytest.raises(ValidationError, match="absolute"):
        HarnessConfig(sibling_repos=["/abs/path/repo-b"])


def test_harness_config_sibling_repos_absolute_tilde_rejected() -> None:
    with pytest.raises(ValidationError, match="absolute"):
        HarnessConfig(sibling_repos=["~/projects/repo-b"])


def test_interview_answers_sibling_repos_default_empty() -> None:
    ans = InterviewAnswers()
    assert ans.sibling_repos == []


def test_interview_answers_sibling_repos_relative_path_valid() -> None:
    ans = InterviewAnswers(sibling_repos=["../repo-b"])
    assert ans.sibling_repos == ["../repo-b"]


def test_interview_answers_sibling_repos_absolute_rejected() -> None:
    with pytest.raises(ValidationError, match="absolute"):
        InterviewAnswers(sibling_repos=["/abs/path/repo-b"])


# ──────────────────────────────────────────────────────────────────────────────
# InterviewAnswers.mechanical_checks
# ──────────────────────────────────────────────────────────────────────────────


def test_interview_answers_mechanical_checks_default_empty() -> None:
    ans = InterviewAnswers()
    assert ans.mechanical_checks == []


def test_interview_answers_mechanical_checks_round_trip_via_synthesize() -> None:
    from harness_maker.models import ProjectProfile
    from harness_maker.synthesize import synthesize

    checks = ["ruff check .", "uv run pytest tests/unit -x -q"]
    ans = InterviewAnswers(mechanical_checks=checks)
    bp = synthesize(ProjectProfile(), ans)
    assert bp.config.reviewers["mechanical_checks"] == checks


# ──────────────────────────────────────────────────────────────────────────────
# Confidence enum — ADR-007
# ──────────────────────────────────────────────────────────────────────────────


def test_confidence_members_exactly_three() -> None:
    """ADR-007: exactly HIGH / MEDIUM / LOW (no float scale, no tunables)."""
    assert {m.value for m in Confidence} == {"high", "medium", "low"}


def test_confidence_value_strings() -> None:
    assert Confidence.HIGH.value == "high"
    assert Confidence.MEDIUM.value == "medium"
    assert Confidence.LOW.value == "low"


def test_confidence_is_str_enum() -> None:
    """str-Enum so it round-trips through YAML/JSON dumps cleanly."""
    assert isinstance(Confidence.HIGH, str)
    assert Confidence.HIGH == "high"


# ──────────────────────────────────────────────────────────────────────────────
# ProjectProfile — Phase 1 new detection fields (backward compat)
# ──────────────────────────────────────────────────────────────────────────────


def test_project_profile_new_fields_defaults() -> None:
    """New Phase 1 fields must default safely so old YAML loads keep working."""
    p = ProjectProfile()
    assert p.frameworks == []
    assert p.package_manager == ""
    assert p.ci_provider == ""
    assert p.foreign_ai_configs == []
    assert p.detection_confidence == {}


def test_project_profile_new_fields_populated() -> None:
    p = ProjectProfile(
        frameworks=["react", "fastapi"],
        package_manager="uv",
        ci_provider="github-actions",
        foreign_ai_configs=[".github/copilot-instructions.md"],
        detection_confidence={
            "frameworks": Confidence.HIGH,
            "ci_provider": Confidence.MEDIUM,
        },
    )
    assert "react" in p.frameworks
    assert p.package_manager == "uv"
    assert p.ci_provider == "github-actions"
    assert p.foreign_ai_configs == [".github/copilot-instructions.md"]
    assert p.detection_confidence == {
        "frameworks": Confidence.HIGH,
        "ci_provider": Confidence.MEDIUM,
    }


def test_project_profile_round_trip_json_with_new_fields() -> None:
    p = ProjectProfile(
        frameworks=["next.js"],
        package_manager="pnpm",
        ci_provider="github-actions",
        foreign_ai_configs=[".cursor/rules/a.mdc"],
        detection_confidence={"package_manager": Confidence.HIGH},
    )
    restored = ProjectProfile.model_validate_json(p.model_dump_json())
    assert restored == p


def test_project_profile_legacy_yaml_load_without_new_fields() -> None:
    """Old profile YAML predating Phase 1 must still validate (defaults fill in)."""
    p = ProjectProfile.model_validate(
        {
            "stack": ["python"],
            "scale": "small",
            "lifecycle": "dormant",
            "existing_dotclaude": False,
            "spec_only": False,
            "vault_member": False,
            "detected_checks": [],
        }
    )
    assert p.frameworks == []
    assert p.package_manager == ""
    assert p.ci_provider == ""
    assert p.foreign_ai_configs == []
    assert p.detection_confidence == {}


def test_project_profile_rejects_unknown_field() -> None:
    """extra='forbid' is preserved — unknown field still raises."""
    with pytest.raises(ValidationError):
        ProjectProfile.model_validate({"mystery": 1})


# ──────────────────────────────────────────────────────────────────────────────
# AdaptiveConfig — ADR-005
# ──────────────────────────────────────────────────────────────────────────────


def test_adaptive_config_defaults() -> None:
    """ADR-005: opt-out telemetry, 30 sessions / 14 days audit thresholds."""
    ac = AdaptiveConfig()
    assert ac.disable_telemetry is False
    assert ac.audit_session_threshold == 30
    assert ac.audit_days_threshold == 14


def test_adaptive_config_disable_telemetry_override() -> None:
    ac = AdaptiveConfig(disable_telemetry=True)
    assert ac.disable_telemetry is True


def test_adaptive_config_round_trip_json() -> None:
    ac = AdaptiveConfig(
        disable_telemetry=True,
        audit_session_threshold=50,
        audit_days_threshold=7,
    )
    restored = AdaptiveConfig.model_validate_json(ac.model_dump_json())
    assert restored == ac


def test_adaptive_config_extra_forbidden() -> None:
    with pytest.raises(ValidationError):
        AdaptiveConfig.model_validate({"unknown": 1})


def test_harness_config_adaptive_default_is_adaptive_config() -> None:
    cfg = HarnessConfig()
    assert isinstance(cfg.adaptive, AdaptiveConfig)
    assert cfg.adaptive.disable_telemetry is False
    assert cfg.adaptive.audit_session_threshold == 30
    assert cfg.adaptive.audit_days_threshold == 14


def test_harness_config_adaptive_override() -> None:
    cfg = HarnessConfig(adaptive=AdaptiveConfig(disable_telemetry=True))
    assert cfg.adaptive.disable_telemetry is True


def test_harness_config_adaptive_round_trip_json() -> None:
    cfg = HarnessConfig(
        adaptive=AdaptiveConfig(
            disable_telemetry=True,
            audit_session_threshold=42,
            audit_days_threshold=21,
        )
    )
    restored = HarnessConfig.model_validate_json(cfg.model_dump_json())
    assert restored.adaptive == cfg.adaptive


def test_harness_config_legacy_yaml_without_adaptive() -> None:
    """Old harness.yaml predating Phase 1 must still load (default_factory)."""
    cfg = HarnessConfig.model_validate({"locale": "en"})
    assert isinstance(cfg.adaptive, AdaptiveConfig)


# ──────────────────────────────────────────────────────────────────────────────
# Recommendation + RecommendationEvidence — ADR-011
# ──────────────────────────────────────────────────────────────────────────────


def test_recommendation_evidence_defaults() -> None:
    ev = RecommendationEvidence(confidence=Confidence.HIGH)
    assert ev.n_observations == 0
    assert ev.top_3_signals == []
    assert ev.confidence == Confidence.HIGH


def test_recommendation_evidence_full() -> None:
    ev = RecommendationEvidence(
        n_observations=5,
        top_3_signals=["pyproject.toml", "uv.lock", "ruff.toml"],
        confidence=Confidence.HIGH,
    )
    assert ev.n_observations == 5
    assert ev.top_3_signals == ["pyproject.toml", "uv.lock", "ruff.toml"]


def test_recommendation_minimal() -> None:
    rec = Recommendation(
        axis="preset",
        value="Side",
        confidence=Confidence.MEDIUM,
        evidence=RecommendationEvidence(confidence=Confidence.MEDIUM),
    )
    assert rec.axis == "preset"
    assert rec.value == "Side"
    assert rec.confidence == Confidence.MEDIUM
    assert rec.signal == ""


def test_recommendation_with_signal() -> None:
    rec = Recommendation(
        axis="second_brain.vault_path",
        value="../vault",
        confidence=Confidence.HIGH,
        evidence=RecommendationEvidence(
            n_observations=1,
            top_3_signals=["../vault/.obsidian"],
            confidence=Confidence.HIGH,
        ),
        signal="found ../vault/.obsidian directory",
    )
    assert rec.signal == "found ../vault/.obsidian directory"
    assert rec.evidence.top_3_signals == ["../vault/.obsidian"]


def test_recommendation_round_trip_json() -> None:
    rec = Recommendation(
        axis="preset",
        value="Production",
        confidence=Confidence.HIGH,
        evidence=RecommendationEvidence(
            n_observations=3,
            top_3_signals=["CI", "tests/", "CHANGELOG.md"],
            confidence=Confidence.HIGH,
        ),
        signal="three production markers detected",
    )
    restored = Recommendation.model_validate_json(rec.model_dump_json())
    assert restored == rec


def test_recommendation_value_accepts_any_type() -> None:
    """value: Any — axes carry strings, ints, lists, dicts, bools."""
    Recommendation(
        axis="targets",
        value=["claude-code", "cursor"],
        confidence=Confidence.LOW,
        evidence=RecommendationEvidence(confidence=Confidence.LOW),
    )
    Recommendation(
        axis="adaptive.disable_telemetry",
        value=True,
        confidence=Confidence.LOW,
        evidence=RecommendationEvidence(confidence=Confidence.LOW),
    )
    Recommendation(
        axis="adaptive.audit_session_threshold",
        value=30,
        confidence=Confidence.LOW,
        evidence=RecommendationEvidence(confidence=Confidence.LOW),
    )


def test_recommendation_extra_forbidden() -> None:
    with pytest.raises(ValidationError):
        Recommendation.model_validate(
            {
                "axis": "preset",
                "value": "Side",
                "confidence": "high",
                "evidence": {"confidence": "high"},
                "rogue_field": 1,
            }
        )


def test_recommendation_evidence_extra_forbidden() -> None:
    with pytest.raises(ValidationError):
        RecommendationEvidence.model_validate(
            {"confidence": "high", "rogue": 1},
        )


def test_recommendation_requires_axis() -> None:
    with pytest.raises(ValidationError):
        Recommendation.model_validate(
            {
                "value": "Side",
                "confidence": "high",
                "evidence": {"confidence": "high"},
            }
        )


def test_recommendation_rejects_invalid_confidence() -> None:
    with pytest.raises(ValidationError):
        Recommendation.model_validate(
            {
                "axis": "preset",
                "value": "Side",
                "confidence": "very-high",
                "evidence": {"confidence": "very-high"},
            }
        )


# ──────────────────────────────────────────────────────────────────────────────
# Auto-fix round (PLAN-personalization-depth-2026-05 Phase 1)
# ──────────────────────────────────────────────────────────────────────────────


def test_adaptive_config_rejects_non_positive_thresholds() -> None:
    with pytest.raises(ValidationError):
        AdaptiveConfig(audit_session_threshold=0)
    with pytest.raises(ValidationError):
        AdaptiveConfig(audit_days_threshold=-1)


def test_project_profile_rejects_absolute_foreign_ai_config_paths() -> None:
    with pytest.raises(ValidationError, match="must contain relative paths"):
        ProjectProfile(foreign_ai_configs=["/etc/passwd"])
    with pytest.raises(ValidationError):
        ProjectProfile(foreign_ai_configs=["~/secret.json"])


def test_recommendation_evidence_rejects_more_than_three_signals() -> None:
    with pytest.raises(ValidationError):
        RecommendationEvidence(
            confidence=Confidence.HIGH,
            top_3_signals=["a", "b", "c", "d"],
        )


def test_recommendation_confidence_mirror_invariant() -> None:
    with pytest.raises(ValidationError, match="mirror invariant"):
        Recommendation(
            axis="x",
            value=1,
            confidence=Confidence.HIGH,
            evidence=RecommendationEvidence(confidence=Confidence.LOW),
        )
