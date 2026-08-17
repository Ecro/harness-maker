"""Tests for spec_machine (P1, ADR-006/007)."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

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


def _minimal_yaml(tmp_path: Path, **overrides: Any) -> Path:
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
                "oracle_source": "differential",
                "oracle_evidence": "compared against the reference renderer golden",
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
                id="AC-001",
                title="t",
                type="mechanical",
                test_ids=["t::f"],
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
                id="AC-001",
                title="t",
                type="judgment",
                test_ids=["t::f"],
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
                executable_predicate="result == 1",
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
                executable_predicate="result == 1",  # assertable expr (not the tautology "True")
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
    md_frontmatter: dict[str, Any] | None = None,
    md_acs: list[dict[str, Any]] | None = None,
    yaml_overrides: dict[str, Any] | None = None,
) -> tuple[Path, Path]:
    md_frontmatter = (
        md_frontmatter if md_frontmatter is not None else {"type": "spec", "tier": 1, "slug": slug}
    )
    md_acs = (
        md_acs if md_acs is not None else [{"id": "AC-001", "title": "render emits content_hash"}]
    )
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


# ---------------------------------------------------------------------------
# Phase 0 — executable_predicate tightening (ADR-007 of PLAN-spec-test-accumulation)
# ---------------------------------------------------------------------------


def _mechanical_ac(predicate: str) -> SpecMachine:
    return SpecMachine(
        spec_slug="x",
        verification_tier=1,
        ac=[
            AcceptanceCriterion(
                id="AC-001",
                title="t",
                type="mechanical",
                executable_predicate=predicate,
                test_ids=["t::f"],
            )
        ],
    )


@pytest.mark.parametrize(
    "prose",
    [
        "retries are bounded and idempotent",  # NAME NAME → SyntaxError
        "the system handles errors gracefully",  # adjacent names → SyntaxError
        "works correctly",  # NAME NAME → SyntaxError
    ],
)
def test_validate_rejects_prose_predicate(prose: str) -> None:
    """Phase 0: prose that does not parse as an expression is rejected."""
    errors = validate(_mechanical_ac(prose))
    assert any("executable_predicate" in e for e in errors), f"{prose!r} should be rejected"


def test_validate_predicate_known_limitation_prose_that_parses() -> None:
    """Honest limitation (validator C2 residual): prose that is incidentally a valid
    boolean expression ('fast and reliable' = Name and Name) slips through ast.parse.
    This documents — does not assert away — the gap; the test-reviewer is the
    backstop for semantic-but-parseable predicates."""
    errors = validate(_mechanical_ac("fast and reliable"))
    assert not any("executable_predicate" in e for e in errors)


@pytest.mark.parametrize("trivial", ["True", "False", "retries", "result", "123"])
def test_validate_rejects_trivial_predicate(trivial: str) -> None:
    """Phase 0: a bare name/constant parses but is a tautology, not an oracle."""
    errors = validate(_mechanical_ac(trivial))
    assert any("executable_predicate" in e for e in errors), f"{trivial!r} should be rejected"


@pytest.mark.parametrize(
    "expr",
    [
        "result.count <= 3",
        "is_valid(result)",
        "'content_hash:' in render(answers())",
        "not response.error",
        "a == 1 and b > 0",
        "len(items) == 5",
    ],
)
def test_validate_accepts_assertable_predicate(expr: str) -> None:
    """Phase 0: a real comparison/call/bool-op referencing a symbol passes."""
    errors = validate(_mechanical_ac(expr))
    assert not any("executable_predicate" in e for e in errors), f"{expr!r} should pass"


def test_validate_empty_predicate_keeps_legacy_message() -> None:
    """Empty predicate still reports the non-empty requirement (message stability)."""
    errors = validate(_mechanical_ac(""))
    assert any("requires non-empty executable_predicate" in e for e in errors)


# ---------------------------------------------------------------------------
# Phase 1 — mark_tested forward write-back (ADR-005 of PLAN-spec-test-accumulation)
# ---------------------------------------------------------------------------


def test_mark_tested_flips_pending_and_records_test_ids(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Positive: write-back flips pending_test→false, records test_ids, cross_validate clean.

    Two assertions on the producer→consumer round-trip (guards against
    [fail:design] producer-consumer-schema-drift): the on-disk reload shows BOTH
    pending_test=False AND the test_id present.
    """
    import harness_maker.spec_machine as sm
    from harness_maker.spec_machine import load, mark_tested

    # All authored tests resolve.
    monkeypatch.setattr(sm, "_check_pytest_collect", lambda test_ids, cwd: [])

    md, yp = _write_md_yaml_pair(tmp_path)  # AC-001 pending_test=True, test_ids=[]
    errors = mark_tested(yp, md, {"AC-001": ["tests/unit/test_x.py::test_render_emits_hash"]})
    assert errors == []
    reloaded = load(yp)
    assert reloaded.ac[0].pending_test is False
    assert "tests/unit/test_x.py::test_render_emits_hash" in reloaded.ac[0].test_ids


def test_mark_tested_fails_when_test_unresolved(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Negative: a recorded test_id that does not resolve surfaces rule-3 (gate fires)."""
    import harness_maker.spec_machine as sm
    from harness_maker.spec_machine import mark_tested

    # Nothing resolves → cross_validate rule-3 fires once pending flips to false.
    monkeypatch.setattr(sm, "_check_pytest_collect", lambda test_ids, cwd: list(test_ids))

    md, yp = _write_md_yaml_pair(tmp_path)
    errors = mark_tested(yp, md, {"AC-001": ["tests/unit/test_missing.py::test_nope"]})
    assert any("rule-3" in e for e in errors)


def test_mark_tested_unknown_ac_id(tmp_path: Path) -> None:
    """Naming a non-existent AC is a hard error (no silent no-op)."""
    from harness_maker.spec_machine import load, mark_tested

    md, yp = _write_md_yaml_pair(tmp_path)
    before = load(yp).ac[0].pending_test
    errors = mark_tested(yp, md, {"AC-999": []})
    assert any("unknown ac id" in e for e in errors)
    # Unknown-id path must not mutate the file.
    assert load(yp).ac[0].pending_test == before


def test_mark_tested_idempotent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Re-running mark-tested with the same test_id does not duplicate it."""
    import harness_maker.spec_machine as sm
    from harness_maker.spec_machine import load, mark_tested

    monkeypatch.setattr(sm, "_check_pytest_collect", lambda test_ids, cwd: [])

    md, yp = _write_md_yaml_pair(tmp_path)
    tid = "tests/unit/test_x.py::test_y"
    mark_tested(yp, md, {"AC-001": [tid]})
    mark_tested(yp, md, {"AC-001": [tid]})
    assert load(yp).ac[0].test_ids == [tid]


def test_main_validate_rejects_prose(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """CLI boundary: `validate` exits 1 on a prose predicate (template Step 4 is now real)."""
    from harness_maker.spec_machine import main

    p = _minimal_yaml(
        tmp_path,
        ac=[
            {
                "id": "AC-001",
                "title": "t",
                "type": "mechanical",
                "test_ids": ["t::f"],
                "executable_predicate": "retries are bounded",  # prose
            }
        ],
    )
    rc = main(["validate", str(p)])
    assert rc == 1
    assert "executable_predicate" in capsys.readouterr().err


def test_main_mark_tested_no_targets_returns_2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """CLI guard: mark-tested with neither --ac nor --test-id is a usage error."""
    from harness_maker.spec_machine import main

    md, yp = _write_md_yaml_pair(tmp_path)
    rc = main(["mark-tested", "--yaml", str(yp), "--md", str(md)])
    assert rc == 2


def test_mark_tested_real_pytest_collect_lifecycle(tmp_path: Path) -> None:
    """End-to-end forward-binding with REAL pytest --collect-only (no mock).

    Proves the ADR-005 cwd contract: cross_validate scopes collection to
    md_path.parent.parent, so a test physically present under <root>/tests/
    resolves and the write-back validates clean. Integration boundary +
    producer→consumer round-trip (no mock of _check_pytest_collect).
    """
    from harness_maker.spec_machine import cross_validate, load, mark_tested

    root = tmp_path
    (root / "specs").mkdir()
    (root / "tests").mkdir()
    (root / "tests" / "test_demo.py").write_text(
        "def test_real_node():\n    assert True\n", encoding="utf-8"
    )
    md = root / "specs" / "SPEC-demo.md"
    md.write_text(
        "---\ntype: spec\ntier: 1\nslug: demo\n---\n\n# SPEC\n\n### AC-001: demo bound\n\n",
        encoding="utf-8",
    )
    yp = root / "specs" / "SPEC-demo.machine.yaml"
    yp.write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "spec_slug": "demo",
                "verification_tier": 1,
                "mutation_threshold": 85,
                "paths_to_mutate": ["src/demo.py"],
                "ac": [
                    {
                        "id": "AC-001",
                        "title": "demo bound",
                        "type": "mechanical",
                        "test_ids": [],
                        "executable_predicate": "result == 1",
                        "pending_test": True,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    errors = mark_tested(yp, md, {"AC-001": ["tests/test_demo.py::test_real_node"]})
    assert errors == [], errors  # real collect resolves the merged test
    reloaded = load(yp)
    assert reloaded.ac[0].pending_test is False
    assert reloaded.ac[0].test_ids == ["tests/test_demo.py::test_real_node"]
    # And a fresh cross_validate over the now-bound (non-pending) AC stays clean.
    assert cross_validate(md, yp) == []


# ---------------------------------------------------------------------------
# REVIEW fixes (PLAN-spec-test-accumulation round 1)
# ---------------------------------------------------------------------------


def test_check_pytest_collect_drops_option_like_test_id(monkeypatch: pytest.MonkeyPatch) -> None:
    """S-P1: a test_id whose file starts with '-' is never spliced into pytest argv."""
    import harness_maker.spec_machine as sm

    captured: dict[str, list[str]] = {}

    class _Result:
        returncode = 0
        stdout = "tests/ok.py::test_y\n"  # the legit file collects; -pevil never reaches argv

    def _fake_run(args, **kwargs):  # type: ignore[no-untyped-def]
        captured["args"] = args
        return _Result()

    monkeypatch.setattr(subprocess, "run", _fake_run)
    unresolved = sm._check_pytest_collect(["-pevil::x", "tests/ok.py::test_y"], cwd=Path("."))
    assert "-pevil" not in captured["args"]  # never spliced as an option
    assert "-pevil::x" not in captured["args"]
    assert "--" in captured["args"]  # positional fence present
    assert "-pevil::x" in unresolved  # dropped token reported unresolved, not silently passed
    assert "tests/ok.py::test_y" not in unresolved  # the legit one resolves


def test_mark_tested_unresolved_does_not_mutate_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """C-P2c: a failing pre-check leaves the file UNTOUCHED (no half-bound state)."""
    import harness_maker.spec_machine as sm
    from harness_maker.spec_machine import load, mark_tested

    monkeypatch.setattr(sm, "_check_pytest_collect", lambda test_ids, cwd: list(test_ids))
    md, yp = _write_md_yaml_pair(tmp_path)
    before = yp.read_text()
    errors = mark_tested(yp, md, {"AC-001": ["tests/test_x.py::test_missing"]})
    assert any("rule-3" in e for e in errors)
    assert yp.read_text() == before  # untouched
    assert load(yp).ac[0].pending_test is True  # not flipped


def test_mark_tested_refuses_zero_test_ids(tmp_path: Path) -> None:
    """C-P2d: flipping an AC with no test_ids (e.g. bare --ac) is rejected, not persisted."""
    from harness_maker.spec_machine import load, mark_tested

    md, yp = _write_md_yaml_pair(tmp_path)  # AC-001 has empty test_ids
    errors = mark_tested(yp, md, {"AC-001": []})
    assert any("no test_ids" in e for e in errors)
    assert load(yp).ac[0].pending_test is True  # untouched


def test_mark_tested_resolves_class_nested_nodeid(tmp_path: Path) -> None:
    """C-P1 contract lock: a class-nested nodeid resolves when declared exactly."""
    from harness_maker.spec_machine import load, mark_tested

    root = tmp_path
    (root / "specs").mkdir()
    (root / "tests").mkdir()
    (root / "tests" / "test_cls.py").write_text(
        "class TestC:\n    def test_member(self):\n        assert True\n", encoding="utf-8"
    )
    md = root / "specs" / "SPEC-c.md"
    md.write_text(
        "---\ntype: spec\ntier: 1\nslug: c\n---\n\n# SPEC\n\n### AC-001: cls bound\n\n",
        encoding="utf-8",
    )
    yp = root / "specs" / "SPEC-c.machine.yaml"
    yp.write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "spec_slug": "c",
                "verification_tier": 1,
                "mutation_threshold": 85,
                "paths_to_mutate": ["src/c.py"],
                "ac": [
                    {
                        "id": "AC-001",
                        "title": "cls bound",
                        "type": "mechanical",
                        "test_ids": [],
                        "executable_predicate": "result == 1",
                        "pending_test": True,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    errors = mark_tested(yp, md, {"AC-001": ["tests/test_cls.py::TestC::test_member"]})
    assert errors == [], errors  # exact class nodeid resolves
    assert load(yp).ac[0].pending_test is False
