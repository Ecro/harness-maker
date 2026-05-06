"""Tests for answers_from_harness_yaml — silent reuse on re-render."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from harness_maker.interview import answers_from_harness_yaml
from harness_maker.models import AtomicStage, DevMode, Preset, Target


def _write_yaml(tmp_path: Path, body: str) -> Path:
    target = tmp_path / "harness.yaml"
    target.write_text(
        "---\ngenerated_by: harness-maker\n---\n" + body,
        encoding="utf-8",
    )
    return target


def test_returns_none_when_file_missing(tmp_path: Path) -> None:
    assert answers_from_harness_yaml(tmp_path / "nope.yaml") is None


def test_returns_none_when_yaml_invalid(tmp_path: Path) -> None:
    target = tmp_path / "harness.yaml"
    target.write_text("---\n  bad:\nindent\n---\n: : :\n", encoding="utf-8")
    assert answers_from_harness_yaml(target) is None


def test_preserves_locale_and_dev_mode(tmp_path: Path) -> None:
    target = _write_yaml(
        tmp_path,
        "preset: Side\nlocale: ko\ndev_mode: task-driven\n"
        "default_workflow: exec-rev-wrap\ncaching: agent-aware\n"
        "workflows:\n  exec-rev-wrap:\n    - execute\n    - review\n    - wrapup\n",
    )
    answers = answers_from_harness_yaml(target)
    assert answers is not None
    assert answers.locale == "ko"
    assert answers.dev_mode == DevMode.TASK_DRIVEN
    assert answers.preset == Preset.SIDE
    assert answers.default_workflow == "exec-rev-wrap"
    assert answers.fused_workflows["exec-rev-wrap"] == [
        AtomicStage.EXECUTE,
        AtomicStage.REVIEW,
        AtomicStage.WRAPUP,
    ]


def test_preserves_review_knobs(tmp_path: Path) -> None:
    target = _write_yaml(
        tmp_path,
        "preset: Side\nlocale: en\ndev_mode: task-driven\n"
        "default_workflow: exec-rev-wrap\n"
        "workflows:\n  exec-rev-wrap:\n    - execute\n    - review\n    - wrapup\n"
        "reviewers:\n"
        "  consensus: cross-check\n"
        "  auto_fix: false\n"
        "  grade_threshold: B\n"
        "  max_review_rounds: 5\n"
        "  installed: []\n"
        "  enabled:\n    - code-reviewer\n    - security-reviewer\n",
    )
    answers = answers_from_harness_yaml(target)
    assert answers is not None
    assert answers.consensus == "cross-check"
    assert answers.auto_fix is False
    assert answers.grade_threshold == "B"
    assert answers.max_review_rounds == 5
    assert "code-reviewer" in answers.reviewers["enabled"]
    assert "security-reviewer" in answers.reviewers["enabled"]


def test_legacy_yaml_without_review_knobs_uses_defaults(tmp_path: Path) -> None:
    """harness.yaml from harness-maker < 0.3.0 lacks auto_fix/grade_threshold/
    max_review_rounds; reuse must fill these from InterviewAnswers defaults
    rather than crashing.
    """
    target = _write_yaml(
        tmp_path,
        "preset: Side\nlocale: en\ndev_mode: task-driven\n"
        "default_workflow: exec-rev-wrap\n"
        "workflows:\n  exec-rev-wrap:\n    - execute\n    - review\n",
    )
    answers = answers_from_harness_yaml(target)
    assert answers is not None
    assert answers.auto_fix is True
    assert answers.grade_threshold == "A"
    assert answers.max_review_rounds == 3


def test_unknown_preset_returns_none(tmp_path: Path) -> None:
    """Schema drift on `preset` is fatal — caller falls back to interview."""
    target = _write_yaml(tmp_path, "preset: Experimental\n")
    assert answers_from_harness_yaml(target) is None


def test_invalid_workflow_stages_skipped(tmp_path: Path) -> None:
    """Unknown stage names in a workflow are dropped, not propagated."""
    target = _write_yaml(
        tmp_path,
        "preset: Side\nlocale: en\ndev_mode: task-driven\n"
        "default_workflow: exec-rev-wrap\n"
        "workflows:\n  exec-rev-wrap:\n    - execute\n    - imaginary\n    - wrapup\n",
    )
    answers = answers_from_harness_yaml(target)
    assert answers is not None
    assert answers.fused_workflows["exec-rev-wrap"] == [
        AtomicStage.EXECUTE,
        AtomicStage.WRAPUP,
    ]


def test_default_workflow_falls_back_when_missing_from_workflows(tmp_path: Path) -> None:
    """If `default_workflow` names a key not present in `workflows`, fall
    back to the first workflow rather than failing model validation.
    """
    target = _write_yaml(
        tmp_path,
        "preset: Side\nlocale: en\ndev_mode: task-driven\n"
        "default_workflow: imaginary\n"
        "workflows:\n  exec-rev-wrap:\n    - execute\n    - review\n    - wrapup\n",
    )
    answers = answers_from_harness_yaml(target)
    assert answers is not None
    assert answers.default_workflow == "exec-rev-wrap"


def test_handles_missing_workflows_block(tmp_path: Path) -> None:
    target = _write_yaml(tmp_path, "preset: Side\nlocale: en\ndev_mode: task-driven\n")
    answers = answers_from_harness_yaml(target)
    assert answers is not None
    # Falls back to preset starter set; default_workflow must exist among them.
    assert answers.default_workflow in answers.fused_workflows


def test_preserves_project_domains(tmp_path: Path) -> None:
    target = _write_yaml(
        tmp_path,
        "preset: Side\nlocale: en\ndev_mode: task-driven\n"
        "default_workflow: exec-rev-wrap\n"
        "workflows:\n  exec-rev-wrap:\n    - execute\n    - review\n    - wrapup\n"
        "project:\n  domains: [python, tauri]\n",
    )
    answers = answers_from_harness_yaml(target)
    assert answers is not None
    assert answers.domains == ["python", "tauri"]


def test_no_frontmatter_still_parses(tmp_path: Path) -> None:
    target = tmp_path / "harness.yaml"
    target.write_text(
        "preset: Side\nlocale: ko\ndev_mode: task-driven\n"
        "default_workflow: exec-rev-wrap\n"
        "workflows:\n  exec-rev-wrap:\n    - execute\n    - review\n    - wrapup\n",
        encoding="utf-8",
    )
    answers = answers_from_harness_yaml(target)
    assert answers is not None
    assert answers.locale == "ko"


def test_round_trip_ref_folders(tmp_path: Path) -> None:
    """ref_folders survives interview → synthesize → render → reverse map.

    Required by CLAUDE.md checkpoint 6 — every format we persist needs a
    working reverse mapper, otherwise upgrades silently lose user state.
    """
    from harness_maker.interview import interview
    from harness_maker.models import RefFolder
    from harness_maker.profile import profile
    from harness_maker.render import render
    from harness_maker.synthesize import synthesize

    p = profile(tmp_path)
    a = interview(p, autoloop_mode=True).model_copy(
        update={
            "ref_folders": [
                RefFolder(path="./docs"),
                RefFolder(path="../shared", glob="**/*.md"),
            ],
        },
    )
    bp = synthesize(p, a)
    target = tmp_path / ".claude"
    render(bp, target, dry_run=False)
    reused = answers_from_harness_yaml(target / "harness.yaml")
    assert reused is not None
    assert len(reused.ref_folders) == 2
    assert reused.ref_folders[0].path == "./docs"
    assert reused.ref_folders[0].glob == "**/*.{md,txt,pdf}"
    assert reused.ref_folders[1].path == "../shared"
    assert reused.ref_folders[1].glob == "**/*.md"


def test_targets_present_in_yaml_parsed(tmp_path: Path) -> None:
    """yaml 의 targets 키가 valid list 면 그대로 파싱."""
    target = _write_yaml(
        tmp_path,
        "preset: Side\nlocale: en\ndev_mode: task-driven\n"
        "default_workflow: exec-rev-wrap\n"
        "workflows:\n  exec-rev-wrap:\n    - execute\n    - review\n    - wrapup\n"
        "targets:\n  - claude-code\n  - cursor\n",
    )
    answers = answers_from_harness_yaml(target)
    assert answers is not None
    assert answers.targets == [Target.CLAUDE_CODE, Target.CURSOR]


def test_targets_missing_falls_back_with_warning(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """옛 yaml (targets 키 부재) → [claude-code] fallback + 경고 로그.

    Phase 2.0 의 model 단 책임이 Phase 2.1 yaml-aware loader (_parse_targets)
    로 이전됐음을 검증.
    """
    target = _write_yaml(
        tmp_path,
        "preset: Side\nlocale: en\ndev_mode: task-driven\n"
        "default_workflow: exec-rev-wrap\n"
        "workflows:\n  exec-rev-wrap:\n    - execute\n    - review\n    - wrapup\n",
    )
    with caplog.at_level(logging.WARNING, logger="harness_maker.interview"):
        answers = answers_from_harness_yaml(target)
    assert answers is not None
    assert answers.targets == [Target.CLAUDE_CODE]
    assert any("targets" in rec.message and "falling back" in rec.message for rec in caplog.records)


def test_targets_invalid_values_filtered_with_warning(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """yaml targets list 에 알 수 없는 값만 있으면 [claude-code] fallback + 경고."""
    target = _write_yaml(
        tmp_path,
        "preset: Side\nlocale: en\ndev_mode: task-driven\n"
        "default_workflow: exec-rev-wrap\n"
        "workflows:\n  exec-rev-wrap:\n    - execute\n    - review\n    - wrapup\n"
        "targets:\n  - vscode-fork\n  - 12345\n",
    )
    with caplog.at_level(logging.WARNING, logger="harness_maker.interview"):
        answers = answers_from_harness_yaml(target)
    assert answers is not None
    assert answers.targets == [Target.CLAUDE_CODE]
    assert any("targets" in rec.message for rec in caplog.records)
