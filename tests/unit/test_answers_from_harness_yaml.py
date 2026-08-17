"""Tests for answers_from_harness_yaml — silent reuse on re-render."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from harness_maker.interview import answers_from_harness_yaml
from harness_maker.models import DevMode, Preset, Target


def _write_yaml(tmp_path: Path, body: str) -> Path:
    target = tmp_path / "harness.yaml"
    target.write_text(
        "---\ngenerated_by: harness-maker\n---\n" + body,
        encoding="utf-8",
    )
    return target


def test_returns_none_when_file_missing(tmp_path: Path) -> None:
    assert answers_from_harness_yaml(tmp_path / "nope.yaml") is None


# ── PLAN-worktree-side-defaults: the block normalizes to the one live key ────
#
# These fixtures use the shapes that actually exist on disk. The pre-collapse
# renderer never wrote `worktree.enabled`, so a legacy harness carries `scope`
# (+ optionally `feature_branch_workflow`) and nothing else.


def test_legacy_feature_branch_flag_true_normalizes_to_enabled(tmp_path: Path) -> None:
    target = _write_yaml(
        tmp_path,
        "preset: Production\ndev_mode: task-driven\n"
        "worktree:\n  scope: [execute, plan]\n  branch_prefix: hm-\n"
        "  feature_branch_workflow: true\n",
    )
    answers = answers_from_harness_yaml(target)
    assert answers is not None
    assert answers.worktree == {"enabled": True}


def test_legacy_feature_branch_flag_false_opt_out_preserved(tmp_path: Path) -> None:
    # An explicit `false` is a user opt-out — it MUST survive re-render, now as
    # `enabled: false`, and must NOT be overridden by the legacy `scope` below it.
    target = _write_yaml(
        tmp_path,
        "preset: Production\ndev_mode: task-driven\n"
        "worktree:\n  scope: [execute, plan]\n  feature_branch_workflow: false\n",
    )
    answers = answers_from_harness_yaml(target)
    assert answers is not None
    assert answers.worktree == {"enabled": False}


def test_legacy_scope_only_resolves_from_scope(tmp_path: Path) -> None:
    # The oldest generation: no flag at all. `scope` containing `execute` meant
    # execute isolation was ON, so that is what the block resolves to.
    target = _write_yaml(
        tmp_path,
        "preset: Side\ndev_mode: task-driven\n"
        "worktree:\n  scope: [execute]\n  branch_prefix: hm-\n",
    )
    answers = answers_from_harness_yaml(target)
    assert answers is not None
    assert answers.worktree == {"enabled": True}


def test_legacy_empty_scope_is_an_off_decision_not_an_absence(tmp_path: Path) -> None:
    # `scope: []` is precisely the hand-edit a user makes trying to disable. A
    # present key must terminate the chain rather than fall through to the preset
    # default, which for Production would silently flip it back ON.
    target = _write_yaml(
        tmp_path,
        "preset: Production\ndev_mode: task-driven\nworktree:\n  scope: []\n",
    )
    answers = answers_from_harness_yaml(target)
    assert answers is not None
    assert answers.worktree == {"enabled": False}


def test_retired_keys_do_not_survive_the_round_trip(tmp_path: Path) -> None:
    target = _write_yaml(
        tmp_path,
        "preset: Production\ndev_mode: task-driven\n"
        "worktree:\n  scope: [execute]\n  branch_prefix: hm-\n  feature_branch_workflow: true\n",
    )
    answers = answers_from_harness_yaml(target)
    assert answers is not None
    assert set(answers.worktree) == {"enabled"}


def test_nonbool_enabled_is_fail_closed_not_a_fallthrough(tmp_path: Path) -> None:
    # A hand-edited non-bool is truthy to `bool(...)`. It must resolve fail-closed
    # and must NOT fall through to the stale legacy key below it — that would turn
    # isolation ON against the apparent opt-out.
    target = _write_yaml(
        tmp_path,
        "preset: Production\ndev_mode: task-driven\n"
        'worktree:\n  enabled: "false"\n  feature_branch_workflow: true\n',
    )
    answers = answers_from_harness_yaml(target)
    assert answers is not None
    assert answers.worktree == {"enabled": False}


def test_absent_block_falls_back_to_the_preset_default(tmp_path: Path) -> None:
    target = _write_yaml(tmp_path, "preset: Production\ndev_mode: task-driven\n")
    answers = answers_from_harness_yaml(target)
    assert answers is not None
    assert answers.worktree == {"enabled": True}


def test_returns_none_when_yaml_invalid(tmp_path: Path) -> None:
    target = tmp_path / "harness.yaml"
    target.write_text("---\n  bad:\nindent\n---\n: : :\n", encoding="utf-8")
    assert answers_from_harness_yaml(target) is None


def test_preserves_locale_and_dev_mode(tmp_path: Path) -> None:
    target = _write_yaml(
        tmp_path,
        "preset: Side\nlocale: ko\ndev_mode: task-driven\ncaching: agent-aware\n",
    )
    answers = answers_from_harness_yaml(target)
    assert answers is not None
    assert answers.locale == "ko"
    assert answers.dev_mode == DevMode.TASK_DRIVEN
    assert answers.preset == Preset.SIDE


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
        "preset: Side\nlocale: en\ndev_mode: task-driven\n",
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


def test_round_trip_second_brain_config(tmp_path: Path) -> None:
    """second_brain survives render → reverse map so upgrades keep vault config."""
    from harness_maker.interview import interview
    from harness_maker.models import SecondBrainConfig, SecondBrainFolder, SecondBrainNoteType
    from harness_maker.profile import profile
    from harness_maker.render import render
    from harness_maker.synthesize import synthesize

    p = profile(tmp_path)
    a = interview(p, autoloop_mode=True).model_copy(
        update={
            "second_brain": SecondBrainConfig(
                enabled=True,
                project_id="harness-maker",
                vault_path="../vault",
                folders=[
                    SecondBrainFolder(
                        path="Projects/harness-maker",
                        read=True,
                        write=True,
                        note_types=[SecondBrainNoteType.DECISION, SecondBrainNoteType.JOURNAL],
                    )
                ],
            )
        },
    )
    bp = synthesize(p, a)
    target = tmp_path / ".claude"
    render(bp, target, dry_run=False)
    reused = answers_from_harness_yaml(target / "harness.yaml")
    assert reused is not None
    assert reused.second_brain.enabled is True
    assert reused.second_brain.project_id == "harness-maker"
    assert reused.second_brain.vault_path == "../vault"
    assert reused.second_brain.folders[0].path == "Projects/harness-maker"
    assert reused.second_brain.folders[0].write is True
    assert reused.second_brain.folders[0].note_types == [
        SecondBrainNoteType.DECISION,
        SecondBrainNoteType.JOURNAL,
    ]


def test_default_second_brain_render_round_trips_without_warning(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Default render uses `folders: []`, not a YAML null that invalidates config."""
    from harness_maker.interview import interview
    from harness_maker.profile import profile
    from harness_maker.render import render
    from harness_maker.synthesize import synthesize

    p = profile(tmp_path)
    a = interview(p, autoloop_mode=True)
    target = tmp_path / ".claude"
    render(synthesize(p, a), target, dry_run=False)
    with caplog.at_level(logging.WARNING, logger="harness_maker.interview"):
        reused = answers_from_harness_yaml(target / "harness.yaml")
    assert reused is not None
    assert reused.second_brain.enabled is False
    assert reused.second_brain.folders == []
    assert not any("second_brain" in rec.message for rec in caplog.records)


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


def test_targets_empty_list_yaml_falls_back_with_warning(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """yaml `targets: []` 도 falsy result → [claude-code] fallback + 경고."""
    target = _write_yaml(
        tmp_path,
        "preset: Side\nlocale: en\ndev_mode: task-driven\n"
        "default_workflow: exec-rev-wrap\n"
        "workflows:\n  exec-rev-wrap:\n    - execute\n    - review\n    - wrapup\n"
        "targets: []\n",
    )
    with caplog.at_level(logging.WARNING, logger="harness_maker.interview"):
        answers = answers_from_harness_yaml(target)
    assert answers is not None
    assert answers.targets == [Target.CLAUDE_CODE]
    assert any("targets" in rec.message for rec in caplog.records)


def test_phase1_fixture_yaml_falls_back_with_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """B11 — Phase 1 manual checklist fixture
    (`tests/cursor-compat/fixture/.claude/harness.yaml`) 이 옛 yaml format
    (targets 키 부재) 임을 검증 + answers_from_harness_yaml 이 [claude-code]
    fallback + 경고 로그 emit. PLAN-cursor-target-impl.md §2.6 의 B11 자동화
    acceptance 를 직접 만족시키는 test (Phase 1 fixture 를 production code 가
    실제로 처리할 수 있는지 회귀 방지).
    """
    fixture = (
        Path(__file__).resolve().parents[2]
        / "tests"
        / "cursor-compat"
        / "fixture"
        / ".claude"
        / "harness.yaml"
    )
    assert fixture.exists(), "Phase 1 fixture missing — broken test setup"

    with caplog.at_level(logging.WARNING, logger="harness_maker.interview"):
        answers = answers_from_harness_yaml(fixture)

    assert answers is not None
    assert answers.targets == [Target.CLAUDE_CODE]
    assert any("targets" in rec.message and "falling back" in rec.message for rec in caplog.records)


def test_round_trip_targets_via_render_and_reverse(tmp_path: Path) -> None:
    """end-to-end round-trip: ``synthesize → render → answers_from_harness_yaml``
    이 ``targets`` 를 보존. CLAUDE.md 체크리스트 #6 (양방향 매퍼) 의 정확한
    검증 — Phase 2.7 의 yaml template 갱신이 다음 re-render 시 silent fallback
    안 일으키는지 보장.
    """
    from harness_maker.interview import interview
    from harness_maker.models import Target
    from harness_maker.profile import profile
    from harness_maker.render import render
    from harness_maker.synthesize import synthesize

    p = profile(tmp_path)
    a = interview(p, autoloop_mode=True).model_copy(
        update={"targets": [Target.CLAUDE_CODE, Target.CURSOR]},
    )
    bp = synthesize(p, a)
    target = tmp_path / ".claude"
    render(bp, target, dry_run=False)

    reused = answers_from_harness_yaml(target / "harness.yaml")
    assert reused is not None
    assert reused.targets == [Target.CLAUDE_CODE, Target.CURSOR]


def test_round_trip_cursor_only_targets(tmp_path: Path) -> None:
    """Cursor-only target 의 round-trip 도 보존."""
    from harness_maker.interview import interview
    from harness_maker.models import Target
    from harness_maker.profile import profile
    from harness_maker.render import render
    from harness_maker.synthesize import synthesize

    p = profile(tmp_path)
    a = interview(p, autoloop_mode=True).model_copy(update={"targets": [Target.CURSOR]})
    bp = synthesize(p, a)
    target = tmp_path / ".claude"
    render(bp, target, dry_run=False)

    reused = answers_from_harness_yaml(target / "harness.yaml")
    assert reused is not None
    assert reused.targets == [Target.CURSOR]


# ──────────────────────────────────────────────────────────────────────────────
# REVIEW M5/M8 — mcp_servers validation + drop warnings
# ──────────────────────────────────────────────────────────────────────────────


def test_mcp_servers_valid_entry_preserved(tmp_path: Path) -> None:
    """A well-formed mcp_servers entry survives round-trip parse."""
    target = _write_yaml(
        tmp_path,
        (
            "preset: Side\nlocale: en\ndev_mode: task-driven\n"
            "mcp_servers:\n"
            "  context7:\n"
            "    command: npx\n"
            "    args: [-y, '@context7/server']\n"
            "    env:\n"
            "      API_KEY: KEY\n"
        ),
    )
    a = answers_from_harness_yaml(target)
    assert a is not None
    assert "context7" in a.mcp_servers
    assert a.mcp_servers["context7"]["command"] == "npx"


def test_mcp_servers_missing_command_dropped_with_warning(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """REVIEW M5/M8: entries with missing/non-string command are dropped + warned."""
    target = _write_yaml(
        tmp_path,
        (
            "preset: Side\n"
            "mcp_servers:\n"
            "  bad-no-command: {args: [foo]}\n"
            "  bad-int-command: {command: 42}\n"
            "  bad-empty-command: {command: ''}\n"
            "  good: {command: uvx, args: [valid]}\n"
        ),
    )
    with caplog.at_level(logging.WARNING):
        a = answers_from_harness_yaml(target)
    assert a is not None
    assert list(a.mcp_servers.keys()) == ["good"]
    assert any("dropped" in r.message and "malformed" in r.message for r in caplog.records)


def test_mcp_servers_bad_args_type_dropped(tmp_path: Path) -> None:
    """args must be list[str] — string-typed args is rejected."""
    target = _write_yaml(
        tmp_path,
        (
            "preset: Side\n"
            "mcp_servers:\n"
            "  bad: {command: npx, args: 'not-a-list'}\n"
            "  bad-mixed: {command: npx, args: [valid, 42]}\n"
            "  good: {command: npx, args: [valid]}\n"
        ),
    )
    a = answers_from_harness_yaml(target)
    assert a is not None
    assert list(a.mcp_servers.keys()) == ["good"]


def test_mcp_servers_bad_env_type_dropped(tmp_path: Path) -> None:
    """env must be dict[str,str] — non-string values rejected."""
    target = _write_yaml(
        tmp_path,
        (
            "preset: Side\n"
            "mcp_servers:\n"
            "  bad: {command: npx, env: {KEY: 42}}\n"
            "  good: {command: npx, env: {KEY: 'string-value'}}\n"
        ),
    )
    a = answers_from_harness_yaml(target)
    assert a is not None
    assert list(a.mcp_servers.keys()) == ["good"]


def test_mcp_servers_args_and_env_optional(tmp_path: Path) -> None:
    """Bare command-only entry (no args/env) is valid and preserved."""
    target = _write_yaml(
        tmp_path,
        ("preset: Side\nmcp_servers:\n  minimal: {command: simple-bin}\n"),
    )
    a = answers_from_harness_yaml(target)
    assert a is not None
    assert a.mcp_servers == {"minimal": {"command": "simple-bin"}}


def test_churn_gate_round_trips_through_the_reverse_mapper(tmp_path: Path) -> None:
    """A user who turned the gate off must not get it back on from a re-render.

    Round-trip coverage for the two keys, mirroring the grade_threshold /
    max_review_rounds pattern above. Review found the reverse-mapper branch shipped
    with no test at all, which is the one place a wrong key name or a wrong guard
    would silently discard the user's setting.
    """
    target = _write_yaml(
        tmp_path,
        "preset: Side\nlocale: en\ndev_mode: task-driven\n"
        "reviewers:\n"
        "  enabled:\n    - code-reviewer\n"
        "  rereview_churn_gate: false\n"
        "  rereview_churn_ratio: 0.35\n",
    )
    answers = answers_from_harness_yaml(target)
    assert answers is not None
    assert answers.rereview_churn_gate is False
    assert answers.rereview_churn_ratio == 0.35


def test_legacy_yaml_without_churn_keys_uses_defaults(tmp_path: Path) -> None:
    """The absent case — a harness.yaml predating the feature keeps working."""
    target = _write_yaml(
        tmp_path,
        "preset: Side\nlocale: en\ndev_mode: task-driven\n",
    )
    answers = answers_from_harness_yaml(target)
    assert answers is not None
    assert answers.rereview_churn_gate is True
    assert answers.rereview_churn_ratio == 0.30


def test_malformed_churn_values_warn_and_fall_back_rather_than_dropping_silently(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Malformed must be LOUD here and fatal at the point of use.

    Raising in the reverse mapper would make a typo un-re-renderable; the sibling
    `mechanical_checks` / `toolchains` handlers both warn-and-drop. The hard error is
    `review_churn`'s, where the value is actually consumed.
    """
    target = _write_yaml(
        tmp_path,
        "preset: Side\nlocale: en\ndev_mode: task-driven\n"
        "reviewers:\n"
        "  enabled:\n    - code-reviewer\n"
        '  rereview_churn_gate: "yes"\n'
        "  rereview_churn_ratio: 1.5\n",
    )
    with caplog.at_level(logging.WARNING):
        answers = answers_from_harness_yaml(target)
    assert answers is not None
    assert answers.rereview_churn_gate is True
    assert answers.rereview_churn_ratio == 0.30
    warnings = " ".join(r.getMessage() for r in caplog.records)
    assert "rereview_churn_gate" in warnings
    assert "rereview_churn_ratio" in warnings
