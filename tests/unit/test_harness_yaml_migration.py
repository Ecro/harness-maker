"""0.16.0 deep_gate migration — warn-and-ignore for deprecated keys.

Covers ADR-011 (PLAN-deep-interview-question-criteria):
- `interview.deep_gate.max_rounds` → logged warning, ignored, parse proceeds.
- `interview.deep_gate.streak_target` → same.
- Both keys present → both warnings emitted.
- Neither key present (clean 0.16.0+ harness.yaml) → silent.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from harness_maker.interview import answers_from_harness_yaml


def _write_yaml(tmp_path: Path, body: str) -> Path:
    yaml_path = tmp_path / "harness.yaml"
    yaml_path.write_text(body, encoding="utf-8")
    return yaml_path


def _base_yaml(*, deep_gate_block: str = "") -> str:
    """Minimal valid harness.yaml + a customizable deep_gate block.

    Includes the required provenance multi-doc prefix that load_harness_yaml
    expects (CLAUDE.md §2 parser-policy).
    """
    return (
        "---\n"
        "generated_by: harness-maker test fixture\n"
        "content_hash: deadbeef\n"
        "---\n"
        "preset: Production\n"
        "locale: en\n"
        "targets: [claude-code]\n"
        "default_model: claude-opus-4-7\n"
        "dev_mode: spec-driven\n"
        "default_workflow: exec-rev-wrap\n"
        "caching: agent-aware\n"
        "schema_version: 2\n"
        "interview:\n"
        f"{deep_gate_block}"
        "  main_loop:\n"
        "    max_rounds: null\n"
        "project:\n"
        "  domains: []\n"
        "spec:\n"
        "  dir: specs\n"
        "work_docs:\n"
        "  dir: work-docs\n"
        "ref_folders: []\n"
        "second_brain:\n"
        "  enabled: false\n"
        "  backend: null\n"
        "  project_id: null\n"
        "  vault_path: null\n"
        "  required_frontmatter: []\n"
        "  folders: []\n"
        "sibling_repos: []\n"
        "wrapup_docs: []\n"
        "workflows:\n"
        "  exec-rev-wrap:\n"
        "    - execute\n"
        "    - review\n"
        "    - wrapup\n"
        "reviewers:\n"
        "  consensus: single\n"
        "  verbosity: normal\n"
        "  auto_fix: true\n"
        "  grade_threshold: A\n"
        "  max_review_rounds: 3\n"
        "  installed: []\n"
        "  enabled: []\n"
        "skills:\n"
        "  installed: []\n"
        "  enabled: []\n"
    )


def test_deprecated_max_rounds_warn_and_ignore(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Existing 0.15.x harness.yaml with deep_gate.max_rounds parses + warns."""
    deep_gate_block = "  deep_gate:\n    max_rounds: 3\n"
    yaml_path = _write_yaml(tmp_path, _base_yaml(deep_gate_block=deep_gate_block))

    with caplog.at_level(logging.WARNING, logger="harness_maker.interview"):
        answers = answers_from_harness_yaml(yaml_path)

    assert answers is not None, "parse must succeed despite deprecated key"
    assert any(
        "deprecated key interview.deep_gate.max_rounds ignored" in record.message
        for record in caplog.records
    ), f"expected warning not emitted; got: {[r.message for r in caplog.records]}"


def test_deprecated_streak_target_warn_and_ignore(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Existing 0.15.x harness.yaml with deep_gate.streak_target parses + warns."""
    deep_gate_block = "  deep_gate:\n    streak_target: 2\n"
    yaml_path = _write_yaml(tmp_path, _base_yaml(deep_gate_block=deep_gate_block))

    with caplog.at_level(logging.WARNING, logger="harness_maker.interview"):
        answers = answers_from_harness_yaml(yaml_path)

    assert answers is not None
    assert any(
        "deprecated key interview.deep_gate.streak_target ignored" in record.message
        for record in caplog.records
    ), f"expected warning not emitted; got: {[r.message for r in caplog.records]}"


def test_both_deprecated_keys_warn_independently(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """A harness.yaml with both deprecated keys emits both warnings."""
    deep_gate_block = "  deep_gate:\n    max_rounds: 3\n    streak_target: 2\n"
    yaml_path = _write_yaml(tmp_path, _base_yaml(deep_gate_block=deep_gate_block))

    with caplog.at_level(logging.WARNING, logger="harness_maker.interview"):
        answers = answers_from_harness_yaml(yaml_path)

    assert answers is not None
    warnings = [r.message for r in caplog.records if "interview.deep_gate." in r.message]
    assert any("max_rounds" in m for m in warnings)
    assert any("streak_target" in m for m in warnings)


def test_killswitch_overlay_false_propagates(tmp_path: Path) -> None:
    """ADR-012: user-set common_ground.llm_inference_enabled: false in
    harness.yaml must overlay onto the resulting InterviewAnswers.interview
    (the F6 read-side wiring of the F1-shipped schema key)."""
    deep_gate_block = "  deep_gate:\n    common_ground:\n      llm_inference_enabled: false\n"
    yaml_path = _write_yaml(tmp_path, _base_yaml(deep_gate_block=deep_gate_block))
    answers = answers_from_harness_yaml(yaml_path)
    assert answers is not None
    assert answers.interview["deep_gate"]["common_ground"]["llm_inference_enabled"] is False, (
        "kill-switch False must propagate from harness.yaml into InterviewAnswers"
    )


def test_killswitch_overlay_true_keeps_default(tmp_path: Path) -> None:
    """Sanity: explicit true matches the default — no spurious mutation."""
    deep_gate_block = "  deep_gate:\n    common_ground:\n      llm_inference_enabled: true\n"
    yaml_path = _write_yaml(tmp_path, _base_yaml(deep_gate_block=deep_gate_block))
    answers = answers_from_harness_yaml(yaml_path)
    assert answers is not None
    assert answers.interview["deep_gate"]["common_ground"]["llm_inference_enabled"] is True


def test_killswitch_overlay_missing_key_keeps_default(tmp_path: Path) -> None:
    """When common_ground section is absent, InterviewAnswers keeps default True."""
    yaml_path = _write_yaml(tmp_path, _base_yaml(deep_gate_block=""))
    answers = answers_from_harness_yaml(yaml_path)
    assert answers is not None
    assert answers.interview["deep_gate"]["common_ground"]["llm_inference_enabled"] is True


def test_killswitch_overlay_with_deprecated_keys_coexist(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """When harness.yaml has both a deprecated key (max_rounds) AND the new
    kill-switch (common_ground.llm_inference_enabled: false), both code paths
    fire correctly: deprecated key warns + kill-switch overlays."""
    deep_gate_block = (
        "  deep_gate:\n    max_rounds: 3\n    common_ground:\n      llm_inference_enabled: false\n"
    )
    yaml_path = _write_yaml(tmp_path, _base_yaml(deep_gate_block=deep_gate_block))
    with caplog.at_level(logging.WARNING, logger="harness_maker.interview"):
        answers = answers_from_harness_yaml(yaml_path)
    assert answers is not None
    # Kill-switch overlay still fires.
    assert answers.interview["deep_gate"]["common_ground"]["llm_inference_enabled"] is False
    # Deprecated warning still emitted.
    assert any(
        "deprecated key interview.deep_gate.max_rounds ignored" in r.message for r in caplog.records
    )


def test_killswitch_overlay_invalid_value_warns(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Non-bool value emits warning and falls back to default True."""
    deep_gate_block = (
        "  deep_gate:\n    common_ground:\n      llm_inference_enabled: 'not a bool'\n"
    )
    yaml_path = _write_yaml(tmp_path, _base_yaml(deep_gate_block=deep_gate_block))
    with caplog.at_level(logging.WARNING, logger="harness_maker.interview"):
        answers = answers_from_harness_yaml(yaml_path)
    assert answers is not None
    assert answers.interview["deep_gate"]["common_ground"]["llm_inference_enabled"] is True
    assert any("llm_inference_enabled must be a boolean" in r.message for r in caplog.records), (
        "expected warning about invalid kill-switch value"
    )


def test_clean_0_16_0_yaml_silent(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """A 0.16.0+ harness.yaml without deprecated keys emits no deprecated-key warning."""
    deep_gate_block = (
        "  deep_gate:\n"
        "    eig_epsilon: 0.5\n"
        "    confidence_tau: 0.7\n"
        "    open_ended_cap_by_locale:\n"
        "      en: 2\n"
        "      ko: 1\n"
        "      ja: 1\n"
        "      default: 1\n"
        "    common_ground:\n"
        "      llm_inference_threshold: 0.95\n"
        "      llm_inference_enabled: true\n"
    )
    yaml_path = _write_yaml(tmp_path, _base_yaml(deep_gate_block=deep_gate_block))

    with caplog.at_level(logging.WARNING, logger="harness_maker.interview"):
        answers = answers_from_harness_yaml(yaml_path)

    assert answers is not None
    deprecated_warnings = [
        r.message
        for r in caplog.records
        if "interview.deep_gate." in r.message and "deprecated" in r.message
    ]
    assert not deprecated_warnings, (
        f"clean 0.16.0+ yaml must not emit deprecated-key warnings; got: {deprecated_warnings}"
    )
