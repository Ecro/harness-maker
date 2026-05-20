"""Tests for spec_machine (P1, ADR-006/007)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from harness_maker.spec_machine import (
    FUZZY_RATIO_THRESHOLD,
    SCHEMA_VERSION,
    AcceptanceCriterion,
    SpecMachine,
    evaluate_coverage,
    load,
    migrate,
    resolve_pytest_selector,
    validate,
)


def _minimal_yaml(tmp_path: Path, **overrides) -> Path:
    """Write a minimal valid SpecMachine yaml; return path."""
    data = {
        "schema_version": SCHEMA_VERSION,
        "spec_slug": "render",
        "verification_tier": 1,
        "mutation_threshold": 85,
        "paths_to_mutate": ["src/harness_maker/render.py"],
        "ac": [
            {
                "id": "AC-001",
                "title": "render emits content_hash",
                "type": "mechanical",
                "test_ids": ["tests/unit/test_render.py::test_emits_hash"],
                "executable_predicate": "'content_hash:' in render(answers())",
            }
        ],
    }
    data.update(overrides)
    p = tmp_path / "SPEC-render.machine.yaml"
    p.write_text(yaml.safe_dump(data))
    return p


def test_load_minimal(tmp_path: Path) -> None:
    p = _minimal_yaml(tmp_path)
    sm = load(p)
    assert sm.spec_slug == "render"
    assert sm.verification_tier == 1
    assert len(sm.ac) == 1


def test_validate_mechanical_requires_predicate() -> None:
    sm = SpecMachine(
        spec_slug="x",
        verification_tier=1,
        ac=[
            AcceptanceCriterion(
                id="AC-001", title="t", type="mechanical", test_ids=["t::f"],
                executable_predicate="",  # empty
            )
        ],
    )
    errors = validate(sm)
    assert any("executable_predicate" in e for e in errors)


def test_validate_parametric_requires_golden_table() -> None:
    sm = SpecMachine(
        spec_slug="x",
        verification_tier=1,
        ac=[
            AcceptanceCriterion(
                id="AC-001",
                title="t",
                type="parametric",
                test_ids=["t::f"],
                golden_table=[],
            )
        ],
    )
    assert any("golden_table" in e for e in validate(sm))


def test_validate_judgment_requires_rubric_id() -> None:
    sm = SpecMachine(
        spec_slug="x",
        verification_tier=1,
        ac=[
            AcceptanceCriterion(
                id="AC-001", title="t", type="judgment", test_ids=["t::f"],
            )
        ],
    )
    assert any("rubric_id" in e for e in validate(sm))


def test_validate_ac_without_test_ids_must_be_pending() -> None:
    sm = SpecMachine(
        spec_slug="x",
        verification_tier=1,
        ac=[
            AcceptanceCriterion(
                id="AC-001",
                title="t",
                type="mechanical",
                executable_predicate="True",
                test_ids=[],
                pending_test=False,
            )
        ],
    )
    assert any("test_ids" in e for e in validate(sm))


def test_validate_ac_pending_test_ok() -> None:
    sm = SpecMachine(
        spec_slug="x",
        verification_tier=1,
        ac=[
            AcceptanceCriterion(
                id="AC-001",
                title="t",
                type="mechanical",
                executable_predicate="True",
                test_ids=[],
                pending_test=True,
            )
        ],
    )
    assert validate(sm) == []


def test_ac_id_format() -> None:
    with pytest.raises(ValidationError):
        AcceptanceCriterion(id="bad-id", title="x", type="mechanical")


def test_evaluate_coverage_full(tmp_path: Path) -> None:
    p = _minimal_yaml(tmp_path)
    rep = evaluate_coverage(p)
    assert rep["coverage"] == pytest.approx(1.0)
    assert rep["missing"] == []


def test_evaluate_coverage_partial(tmp_path: Path) -> None:
    p = _minimal_yaml(
        tmp_path,
        ac=[
            {
                "id": "AC-001",
                "title": "t",
                "type": "mechanical",
                "test_ids": ["t::f"],
                "executable_predicate": "True",
            },
            {
                "id": "AC-002",
                "title": "u",
                "type": "mechanical",
                "test_ids": [],
                "pending_test": False,
                "executable_predicate": "True",
            },
        ],
    )
    rep = evaluate_coverage(p)
    assert rep["coverage"] == pytest.approx(0.5)
    assert rep["missing"] == ["AC-002"]


def test_evaluate_coverage_empty_yaml(tmp_path: Path) -> None:
    p = _minimal_yaml(tmp_path, ac=[])
    rep = evaluate_coverage(p)
    assert rep["coverage"] == 0.0


def test_resolve_pytest_selector() -> None:
    assert resolve_pytest_selector("render") == "spec-render or test_render"
    assert resolve_pytest_selector("agent-code-reviewer") == (
        "spec-agent-code-reviewer or test_agent_code_reviewer"
    )


def test_migrate_dry_run_default() -> None:
    rep = migrate(1, 2, Path("/tmp"))
    assert rep["status"] == "dry-run"


def test_migrate_same_version_noop() -> None:
    rep = migrate(1, 1, Path("/tmp"), confirm=True)
    assert rep["status"] == "noop"


def test_fuzzy_ratio_threshold_constant() -> None:
    # Locked at 0.85; P4 calibration may tune.
    assert pytest.approx(0.85) == FUZZY_RATIO_THRESHOLD


# ---------------------------------------------------------------------------
# cross_validate — 6-rule matrix (positive + negative for each rule)
# ---------------------------------------------------------------------------


def _write_md_yaml_pair(
    tmp_path: Path,
    *,
    slug: str = "render",
    md_frontmatter: dict | None = None,
    md_acs: list[dict] | None = None,
    yaml_overrides: dict | None = None,
) -> tuple[Path, Path]:
    md_frontmatter = md_frontmatter if md_frontmatter is not None else {"type": "spec", "tier": 1, "slug": slug}
    md_acs = md_acs if md_acs is not None else [{"id": "AC-001", "title": "render emits content_hash"}]
    fm = yaml.safe_dump(md_frontmatter).strip()
    body_lines = []
    for ac in md_acs:
        body_lines.append(f"### {ac['id']}: {ac['title']}")
        body_lines.append("")
    md_text = f"---\n{fm}\n---\n\n# SPEC\n\n" + "\n".join(body_lines)
    md = tmp_path / f"SPEC-{slug}.md"
    md.write_text(md_text)
    yaml_data = {
        "schema_version": 1,
        "spec_slug": slug,
        "verification_tier": 1,
        "mutation_threshold": 85,
        "paths_to_mutate": ["src/harness_maker/render.py"],
        "ac": [
            {
                "id": ac["id"],
                "title": ac["title"],
                "type": "mechanical",
                "test_ids": [],
                "executable_predicate": "True",
                "pending_test": True,
            }
            for ac in md_acs
        ],
    }
    if yaml_overrides:
        yaml_data.update(yaml_overrides)
    yp = tmp_path / f"SPEC-{slug}.machine.yaml"
    yp.write_text(yaml.safe_dump(yaml_data))
    return md, yp


def test_cross_validate_rule1_pass(tmp_path: Path) -> None:
    from harness_maker.spec_machine import cross_validate

    md, yp = _write_md_yaml_pair(tmp_path)
    errors = cross_validate(md, yp)
    rule1_errors = [e for e in errors if "rule-1" in e]
    assert rule1_errors == []


def test_cross_validate_rule1_fail_missing_heading(tmp_path: Path) -> None:
    from harness_maker.spec_machine import cross_validate

    md, yp = _write_md_yaml_pair(
        tmp_path,
        md_acs=[],  # no heading in .md
        yaml_overrides={
            "ac": [
                {
                    "id": "AC-001",
                    "title": "missing in md",
                    "type": "mechanical",
                    "executable_predicate": "True",
                    "test_ids": [],
                    "pending_test": True,
                }
            ]
        },
    )
    errors = cross_validate(md, yp)
    assert any("rule-1" in e for e in errors)


def test_cross_validate_rule5_tier_mismatch(tmp_path: Path) -> None:
    from harness_maker.spec_machine import cross_validate

    md, yp = _write_md_yaml_pair(
        tmp_path,
        md_frontmatter={"type": "spec", "tier": 2, "slug": "render"},
        yaml_overrides={"verification_tier": 1},
    )
    errors = cross_validate(md, yp)
    assert any("rule-5" in e for e in errors)


def test_cross_validate_rule6_parent_missing(tmp_path: Path) -> None:
    from harness_maker.spec_machine import cross_validate

    md, yp = _write_md_yaml_pair(
        tmp_path,
        yaml_overrides={"parent_spec": "SPEC-nonexistent"},
    )
    errors = cross_validate(md, yp)
    assert any("rule-6" in e for e in errors)


# ---------------------------------------------------------------------------
# Rules 2/3/4: negative cases (added per REVIEW T-P0-A — ADR-007 desync matrix)
# ---------------------------------------------------------------------------


def test_cross_validate_rule2_title_mismatch(tmp_path: Path) -> None:
    """Yaml ac.title diverges from md heading title beyond fuzzy threshold."""
    from harness_maker.spec_machine import cross_validate

    md, yp = _write_md_yaml_pair(
        tmp_path,
        md_acs=[{"id": "AC-001", "title": "render emits content_hash field"}],
        yaml_overrides={
            "ac": [
                {
                    "id": "AC-001",
                    "title": "completely unrelated bird taxonomy concept",
                    "type": "mechanical",
                    "test_ids": [],
                    "executable_predicate": "True",
                    "pending_test": True,
                }
            ]
        },
    )
    errors = cross_validate(md, yp)
    assert any("rule-2" in e for e in errors)


def test_cross_validate_rule2_fuzzy_within_threshold(tmp_path: Path) -> None:
    """Near-identical titles (small edit) pass rule-2."""
    from harness_maker.spec_machine import cross_validate

    md, yp = _write_md_yaml_pair(
        tmp_path,
        md_acs=[{"id": "AC-001", "title": "render emits content_hash"}],
        yaml_overrides={
            "ac": [
                {
                    "id": "AC-001",
                    "title": "render emits content_hash.",  # added period
                    "type": "mechanical",
                    "test_ids": [],
                    "executable_predicate": "True",
                    "pending_test": True,
                }
            ]
        },
    )
    errors = cross_validate(md, yp)
    assert not any("rule-2" in e for e in errors)


def test_cross_validate_rule3_unresolved_test_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A non-pending AC referencing a non-existent test_id triggers rule-3."""
    import harness_maker.spec_machine as sm
    from harness_maker.spec_machine import cross_validate

    # Mock the pytest-collect call to deterministically return "not found".
    def _stub_check(test_ids: list[str], cwd: Path) -> list[str]:
        return list(test_ids)

    monkeypatch.setattr(sm, "_check_pytest_collect", _stub_check)

    md, yp = _write_md_yaml_pair(
        tmp_path,
        yaml_overrides={
            "ac": [
                {
                    "id": "AC-001",
                    "title": "render emits content_hash",
                    "type": "mechanical",
                    "test_ids": ["tests/unit/test_missing.py::test_does_not_exist"],
                    "executable_predicate": "True",
                    "pending_test": False,
                }
            ]
        },
    )
    errors = cross_validate(md, yp)
    assert any("rule-3" in e for e in errors)


def test_cross_validate_rule3_skipped_for_pending_test(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """pending_test=True AC bypasses rule-3 even with unresolvable test_ids."""
    import harness_maker.spec_machine as sm
    from harness_maker.spec_machine import cross_validate

    def _stub_check(test_ids: list[str], cwd: Path) -> list[str]:
        return list(test_ids)

    monkeypatch.setattr(sm, "_check_pytest_collect", _stub_check)

    md, yp = _write_md_yaml_pair(tmp_path)  # defaults have pending_test=True
    errors = cross_validate(md, yp)
    assert not any("rule-3" in e for e in errors)


def test_cross_validate_rule4_rubric_missing(tmp_path: Path) -> None:
    """rubric_id pointing at a nonexistent file triggers rule-4."""
    from harness_maker.spec_machine import cross_validate

    md, yp = _write_md_yaml_pair(
        tmp_path,
        yaml_overrides={
            "ac": [
                {
                    "id": "AC-001",
                    "title": "render emits content_hash",
                    "type": "judgment",
                    "test_ids": [],
                    "rubric_id": "nonexistent_rubric_xyzzy",
                    "pending_test": True,
                }
            ]
        },
    )
    errors = cross_validate(md, yp)
    assert any("rule-4" in e for e in errors)


def test_cross_validate_rule5_pass(tmp_path: Path) -> None:
    """md frontmatter tier matches yaml verification_tier → no rule-5."""
    from harness_maker.spec_machine import cross_validate

    md, yp = _write_md_yaml_pair(
        tmp_path,
        md_frontmatter={"type": "spec", "tier": 1, "slug": "render"},
        yaml_overrides={"verification_tier": 1},
    )
    errors = cross_validate(md, yp)
    assert not any("rule-5" in e for e in errors)


def test_cross_validate_rule6_pass_no_parent(tmp_path: Path) -> None:
    """No parent_spec field → rule-6 silent."""
    from harness_maker.spec_machine import cross_validate

    md, yp = _write_md_yaml_pair(tmp_path)
    errors = cross_validate(md, yp)
    assert not any("rule-6" in e for e in errors)
