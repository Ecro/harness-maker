"""Phase 2 — v1 → v2 schema migration in answers_from_harness_yaml.

ADR-004 silent migration: existing harness.yaml with `recommended_model:` key
loads as v2 InterviewAnswers with `default_model` populated, `agent_models={}`,
+ one INFO log line.

CLAUDE.md §2 contract: must use `io_utils.load_harness_yaml()` for
provenance-frontmatter (multi-doc YAML stream) handling.
"""

from __future__ import annotations

import logging
from pathlib import Path

from harness_maker.interview import answers_from_harness_yaml

FIXTURE_V1_PROVENANCE = (
    Path(__file__).resolve().parents[1] / "fixtures" / "harness_yaml_v1_with_provenance.yaml"
)


def test_v1_with_provenance_loads_as_v2_with_default_model(tmp_path: Path, caplog: object) -> None:
    """The wire-path test (validator C-3 + ADR-004): real provenance-frontmatter
    fixture loads via io_utils.load_harness_yaml, recommended_model migrates to
    default_model, agent_models defaults to {}.
    """
    assert FIXTURE_V1_PROVENANCE.exists(), f"fixture missing: {FIXTURE_V1_PROVENANCE}"
    target = tmp_path / "harness.yaml"
    target.write_text(FIXTURE_V1_PROVENANCE.read_text(encoding="utf-8"), encoding="utf-8")

    with caplog.at_level(logging.INFO):  # type: ignore[attr-defined]
        answers = answers_from_harness_yaml(target)

    assert answers is not None
    assert answers.default_model == "claude-opus-4-7"
    assert answers.agent_models == {}
    # Advisory log emitted on migration (ADR-004).
    assert any(
        "recommended_model" in record.getMessage() and "default_model" in record.getMessage()
        for record in caplog.records  # type: ignore[attr-defined]
    ), "expected INFO log mentioning recommended_model → default_model migration"


def test_v1_non_default_recommended_model_preserved(tmp_path: Path) -> None:
    """v1 fixture with a NON-default `recommended_model` value preserves the
    user's choice into `default_model` — they don't silently get the new default.
    """
    yaml_body = (
        "---\n"
        "generated_by: harness-maker\n"
        'content_hash: "fake"\n'
        "---\n"
        "locale: en\n"
        "targets: [claude-code]\n"
        "preset: Side\n"
        "dev_mode: task-driven\n"
        "recommended_model: claude-sonnet-4-6\n"
        "schema_version: 1\n"
    )
    target = tmp_path / "harness.yaml"
    target.write_text(yaml_body, encoding="utf-8")

    answers = answers_from_harness_yaml(target)
    assert answers is not None
    assert answers.default_model == "claude-sonnet-4-6"


def test_v2_clean_no_migration_log(tmp_path: Path, caplog: object) -> None:
    """v2 harness.yaml (default_model directly, no recommended_model key) reads
    without emitting the migration log."""
    yaml_body = (
        "---\n"
        "generated_by: harness-maker\n"
        'content_hash: "fake"\n'
        "---\n"
        "locale: en\n"
        "targets: [claude-code]\n"
        "preset: Production\n"
        "dev_mode: spec-driven\n"
        "default_model: claude-opus-4-7\n"
        "agent_models: {}\n"
        "schema_version: 2\n"
    )
    target = tmp_path / "harness.yaml"
    target.write_text(yaml_body, encoding="utf-8")

    with caplog.at_level(logging.INFO):  # type: ignore[attr-defined]
        answers = answers_from_harness_yaml(target)

    assert answers is not None
    assert answers.default_model == "claude-opus-4-7"
    # No migration log on clean v2 input.
    migration_logs = [
        r
        for r in caplog.records  # type: ignore[attr-defined]
        if "recommended_model" in r.getMessage() and "default_model" in r.getMessage()
    ]
    assert not migration_logs, "v2 input should NOT trigger migration log"


def test_uses_io_utils_load_harness_yaml_for_provenance(tmp_path: Path) -> None:
    """Regression guard: this test verifies the contract that PHASE 2 specifies —
    that the migration path uses io_utils.load_harness_yaml (NOT yaml.safe_load
    on raw text). The fixture is a multi-doc YAML stream; yaml.safe_load alone
    raises ComposerError on it, so a passing test proves the helper is wired.
    """
    target = tmp_path / "harness.yaml"
    target.write_text(FIXTURE_V1_PROVENANCE.read_text(encoding="utf-8"), encoding="utf-8")
    # If this returns non-None, the multi-doc stream was handled correctly.
    answers = answers_from_harness_yaml(target)
    assert answers is not None
    assert answers.preset.value == "Production"


def test_agent_models_malformed_entry_drops_with_warning(tmp_path: Path, caplog: object) -> None:
    """Review code-reviewer + security-reviewer P1 fix: ValidationError must be
    caught when AgentModelSpec construction fails (Pydantic v2 strict mode
    raises ValidationError, not ValueError, so the original except (TypeError,
    ValueError) tuple missed it — silent data loss on re-render).

    Crafted harness.yaml has one VALID agent_models entry + one INVALID
    (extra key triggering extra=forbid). Expected: valid entry survives,
    invalid is dropped with WARNING log naming the offending agent.
    """
    yaml_body = (
        "---\n"
        "generated_by: harness-maker\n"
        'content_hash: "fake"\n'
        "---\n"
        "locale: en\n"
        "targets: [claude-code]\n"
        "preset: Production\n"
        "dev_mode: spec-driven\n"
        "default_model: claude-opus-4-7\n"
        "agent_models:\n"
        "  valid-agent:\n"
        "    claude: opus\n"
        "    cursor: opus\n"
        "  broken-agent:\n"
        "    claude: sonnet\n"
        "    bogus_unknown_field: oops\n"
        "schema_version: 2\n"
    )
    target = tmp_path / "harness.yaml"
    target.write_text(yaml_body, encoding="utf-8")

    with caplog.at_level(logging.WARNING):  # type: ignore[attr-defined]
        answers = answers_from_harness_yaml(target)

    assert answers is not None, (
        "ValidationError must be caught — None means it propagated uncaught "
        "(the bug this test guards against)"
    )
    # Valid entry preserved
    assert "valid-agent" in answers.agent_models
    assert answers.agent_models["valid-agent"].claude == "opus"
    # Invalid entry dropped
    assert "broken-agent" not in answers.agent_models
    # WARNING log names the offending agent so users can fix their yaml
    assert any(
        "broken-agent" in r.getMessage() and "agent_models" in r.getMessage()
        for r in caplog.records  # type: ignore[attr-defined]
    ), "expected WARNING log mentioning broken-agent + agent_models"


def test_v2_with_recommended_model_does_not_emit_migration_log(
    tmp_path: Path, caplog: object
) -> None:
    """Review code-reviewer P1 fix: gate the migration advisory on
    schema_version<2. Without this gate, the log fires on every fresh Phase 2
    render cycle because templates still emit recommended_model: until Phase 3.
    """
    # schema_version=2 file with recommended_model (mimics what Phase 2 templates
    # currently emit — they migrate to default_model in Phase 3).
    yaml_body = (
        "---\n"
        "generated_by: harness-maker\n"
        'content_hash: "fake"\n'
        "---\n"
        "locale: en\n"
        "targets: [claude-code]\n"
        "preset: Production\n"
        "dev_mode: spec-driven\n"
        "recommended_model: claude-opus-4-7\n"
        "schema_version: 2\n"
    )
    target = tmp_path / "harness.yaml"
    target.write_text(yaml_body, encoding="utf-8")

    with caplog.at_level(logging.INFO):  # type: ignore[attr-defined]
        answers = answers_from_harness_yaml(target)

    assert answers is not None
    assert answers.default_model == "claude-opus-4-7"
    # Migration log MUST NOT fire — schema_version is already 2.
    migration_logs = [
        r
        for r in caplog.records  # type: ignore[attr-defined]
        if "deprecated `recommended_model" in r.getMessage()
    ]
    assert not migration_logs, (
        f"migration log fired on schema_version=2 input (Phase 2 templates "
        f"still emit recommended_model:; until Phase 3 the log would be noisy "
        f"on every re-render): {[r.getMessage() for r in migration_logs]}"
    )
