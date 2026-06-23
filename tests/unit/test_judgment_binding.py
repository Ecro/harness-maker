"""Tests for judgment AC binding (independent rubric-reviewer verdict).

PLAN-judgment-ac-binding:
- Phase 1: model fields + validate non-empty-subject-paths (ADR-007) + select_judgment +
  canonical subject hash (ADR-004) + mark_judged (strict verdict, non-empty evidence) +
  find_unjudged (pass AND hash-current AND parseable; subject-absent skip; fail-closed) + stale.
- Phase 3: the Production gate predicate (consults the hash → stale = unbound).
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from harness_maker.spec_machine import AcceptanceCriterion, SpecMachine, load, validate

# ---------------------------------------------------------------------------
# Model fields + validate (ADR-007 non-empty subject paths)
# ---------------------------------------------------------------------------


def _judgment_ac(ac_id: str = "AC-001", **over: object) -> AcceptanceCriterion:
    data: dict[str, object] = {
        "id": ac_id,
        "title": "judged thing",
        "type": "judgment",
        "rubric_id": "skill",
        "oracle_source": "rubric",
        "oracle_evidence": "independent reviewer against the skill rubric",
        "judgment_subject_paths": ["src/harness_maker/spec_machine.py"],
    }
    data.update(over)
    return AcceptanceCriterion(**data)  # type: ignore[arg-type]


def _model(*acs: AcceptanceCriterion) -> SpecMachine:
    return SpecMachine(schema_version=2, spec_slug="demo", verification_tier=1, ac=list(acs))


def test_judgment_fields_exist_and_default_null() -> None:
    ac = _judgment_ac()
    assert ac.judgment_verdict is None
    assert ac.judged_at is None
    assert ac.judgment_evidence is None
    assert ac.judgment_subject_hash is None
    assert ac.judgment_subject_paths == ["src/harness_maker/spec_machine.py"]


def test_judgment_verdict_rejects_non_literal() -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        _judgment_ac(judgment_verdict="passed")  # not pass|fail|None


def test_validate_judgment_requires_non_empty_subject_paths_omitted() -> None:
    # omitted key → default [] → must fail at v2
    ac = AcceptanceCriterion(
        id="AC-001",
        title="t",
        type="judgment",
        rubric_id="skill",
        oracle_source="rubric",
        oracle_evidence="x",
    )
    errors = validate(_model(ac))
    assert any("judgment_subject_paths" in e for e in errors), errors


def test_validate_judgment_requires_non_empty_subject_paths_empty_list() -> None:
    ac = _judgment_ac(judgment_subject_paths=[])
    errors = validate(_model(ac))
    assert any("judgment_subject_paths" in e for e in errors), errors


def test_validate_judgment_exempt_from_test_ids_rule() -> None:
    # a judgment AC has no test_ids and no pending_test, but must NOT trip the
    # "needs >=1 test_ids OR pending_test" rule — it binds via a verdict.
    ac = _judgment_ac()
    errors = validate(_model(ac))
    assert not any("needs >=1 test_ids" in e for e in errors), errors


def test_validate_judgment_subject_paths_reject_traversal() -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        _judgment_ac(judgment_subject_paths=["../../etc/passwd"])


# ---------------------------------------------------------------------------
# select_judgment
# ---------------------------------------------------------------------------


def test_select_judgment_includes_only_judgment() -> None:
    from harness_maker.spec_machine import select_judgment

    model = _model(
        _judgment_ac("AC-001"),
        AcceptanceCriterion(
            id="AC-002", title="m", type="mechanical", executable_predicate="f() == 1"
        ),
    )
    assert {a.id for a in select_judgment(model)} == {"AC-001"}


def test_select_judgment_unbound_only() -> None:
    from harness_maker.spec_machine import select_judgment

    model = _model(
        _judgment_ac("AC-001", judgment_verdict="pass"),
        _judgment_ac("AC-002", judgment_verdict="fail"),
        _judgment_ac("AC-003"),  # null
    )
    assert {a.id for a in select_judgment(model, unbound_only=True)} == {"AC-002", "AC-003"}


# ---------------------------------------------------------------------------
# Canonical subject hash (ADR-004)
# ---------------------------------------------------------------------------


def test_subject_hash_deterministic_and_rename_sensitive(tmp_path: Path) -> None:
    from harness_maker.spec_machine import compute_subject_hash

    (tmp_path / "a.py").write_text("alpha\n")
    (tmp_path / "b.py").write_text("beta\n")
    h1 = compute_subject_hash(["a.py", "b.py"], tmp_path)
    h2 = compute_subject_hash(["b.py", "a.py"], tmp_path)  # order-independent
    assert h1 == h2
    # rename changes the hash (names are in the manifest)
    (tmp_path / "a.py").rename(tmp_path / "c.py")
    h3 = compute_subject_hash(["c.py", "b.py"], tmp_path)
    assert h3 != h1


def test_subject_hash_dir_expands(tmp_path: Path) -> None:
    from harness_maker.spec_machine import compute_subject_hash

    d = tmp_path / "pkg"
    d.mkdir()
    (d / "x.py").write_text("x\n")
    (d / "y.py").write_text("y\n")
    h = compute_subject_hash(["pkg"], tmp_path)
    assert isinstance(h, str)
    assert len(h) == 64


def test_subject_hash_missing_file_raises(tmp_path: Path) -> None:
    from harness_maker.spec_machine import SubjectHashError, compute_subject_hash

    with pytest.raises(SubjectHashError):
        compute_subject_hash(["nope.py"], tmp_path)


def test_subject_hash_symlink_escape_rejected(tmp_path: Path) -> None:
    from harness_maker.spec_machine import SubjectHashError, compute_subject_hash

    outside = tmp_path.parent / "outside_secret.txt"
    outside.write_text("secret\n")
    link = tmp_path / "link.py"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("symlinks unsupported")
    with pytest.raises(SubjectHashError):
        compute_subject_hash(["link.py"], tmp_path)


# ---------------------------------------------------------------------------
# mark_judged
# ---------------------------------------------------------------------------


def _judgment_yaml(tmp_path: Path, **over: object) -> Path:
    (tmp_path / "subject.py").write_text("def f():\n    return 1\n")
    ac = {
        "id": "AC-001",
        "title": "subject is correct",
        "type": "judgment",
        "rubric_id": "skill",
        "oracle_source": "rubric",
        "oracle_evidence": "independent reviewer",
        "judgment_subject_paths": ["subject.py"],
    }
    ac.update(over)
    data = {"schema_version": 2, "spec_slug": "demo", "verification_tier": 1, "ac": [ac]}
    y = tmp_path / "SPEC-demo.machine.yaml"
    y.write_text(yaml.safe_dump(data))
    return y


def test_mark_judged_records_verdict_and_hash(tmp_path: Path) -> None:
    from harness_maker.spec_machine import mark_judged

    y = _judgment_yaml(tmp_path)
    errors = mark_judged(
        y, "AC-001", "pass", "criterion-1: subject.py:2 returns 1 (rubric ok)", cwd=tmp_path
    )
    assert errors == [], errors
    ac = load(y).ac[0]
    assert ac.judgment_verdict == "pass"
    assert ac.judgment_evidence is not None
    assert "criterion-1" in ac.judgment_evidence
    assert ac.judged_at is not None
    assert ac.judgment_subject_hash is not None
    assert len(ac.judgment_subject_hash) == 64


def test_mark_judged_rejects_bad_verdict(tmp_path: Path) -> None:
    from harness_maker.spec_machine import mark_judged

    y = _judgment_yaml(tmp_path)
    errors = mark_judged(y, "AC-001", "passed", "e", cwd=tmp_path)
    assert errors
    assert any("verdict" in e.lower() for e in errors)
    assert load(y).ac[0].judgment_verdict is None  # untouched


def test_mark_judged_rejects_empty_evidence(tmp_path: Path) -> None:
    from harness_maker.spec_machine import mark_judged

    y = _judgment_yaml(tmp_path)
    errors = mark_judged(y, "AC-001", "pass", "   ", cwd=tmp_path)
    assert errors
    assert any("evidence" in e.lower() for e in errors)


def test_mark_judged_rejects_non_judgment_ac(tmp_path: Path) -> None:
    from harness_maker.spec_machine import mark_judged

    data = {
        "schema_version": 2,
        "spec_slug": "demo",
        "verification_tier": 1,
        "ac": [
            {"id": "AC-001", "title": "m", "type": "mechanical", "executable_predicate": "f() == 1"}
        ],
    }
    y = tmp_path / "SPEC-demo.machine.yaml"
    y.write_text(yaml.safe_dump(data))
    errors = mark_judged(y, "AC-001", "pass", "e", cwd=tmp_path)
    assert errors
    assert any("judgment" in e.lower() for e in errors)


# ---------------------------------------------------------------------------
# find_unjudged (ADR-003) + stale
# ---------------------------------------------------------------------------


def test_find_unjudged_blocks_unjudged_subject_present(tmp_path: Path) -> None:
    from harness_maker.spec_machine import find_unjudged

    y = _judgment_yaml(tmp_path)  # subject.py exists, verdict null
    assert find_unjudged(y, tmp_path) == ["AC-001"]


def test_find_unjudged_clears_when_pass_and_hash_current(tmp_path: Path) -> None:
    from harness_maker.spec_machine import find_unjudged, mark_judged

    y = _judgment_yaml(tmp_path)
    mark_judged(y, "AC-001", "pass", "ok: subject.py:2", cwd=tmp_path)
    assert find_unjudged(y, tmp_path) == []


def test_find_unjudged_blocks_stale_pass(tmp_path: Path) -> None:
    from harness_maker.spec_machine import find_unjudged, mark_judged

    y = _judgment_yaml(tmp_path)
    mark_judged(y, "AC-001", "pass", "ok", cwd=tmp_path)
    (tmp_path / "subject.py").write_text("def f():\n    return 2  # changed\n")  # drift
    assert find_unjudged(y, tmp_path) == ["AC-001"], "stale pass = unbound"


def test_find_unjudged_blocks_recorded_fail(tmp_path: Path) -> None:
    from harness_maker.spec_machine import find_unjudged, mark_judged

    y = _judgment_yaml(tmp_path)
    mark_judged(y, "AC-001", "fail", "criterion-2 not met", cwd=tmp_path)
    assert find_unjudged(y, tmp_path) == ["AC-001"]


def test_find_unjudged_skips_absent_subject(tmp_path: Path) -> None:
    from harness_maker.spec_machine import find_unjudged

    y = _judgment_yaml(tmp_path, judgment_subject_paths=["not_yet_written.py"])
    assert find_unjudged(y, tmp_path) == [], "subject absent = future-PLAN = skip"


def test_find_unjudged_fail_closed_on_malformed(tmp_path: Path) -> None:
    import yaml as _yaml

    from harness_maker.spec_machine import find_unjudged

    bad = tmp_path / "SPEC-demo.machine.yaml"
    bad.write_text("ac: [: : :\n")
    with pytest.raises(_yaml.YAMLError):
        find_unjudged(bad, tmp_path)


def test_stale_judgment_verdicts_flags_drift(tmp_path: Path) -> None:
    from harness_maker.spec_machine import mark_judged, stale_judgment_verdicts

    y = _judgment_yaml(tmp_path)
    mark_judged(y, "AC-001", "pass", "ok", cwd=tmp_path)
    assert stale_judgment_verdicts(y, tmp_path) == []
    (tmp_path / "subject.py").write_text("changed\n")
    assert stale_judgment_verdicts(y, tmp_path) == ["AC-001"]


# ---------------------------------------------------------------------------
# no-network static contract (ADR-005) — the judgment code must not import an LLM SDK
# ---------------------------------------------------------------------------


def test_spec_machine_has_no_anthropic_import() -> None:
    """ADR-005: the judgment eval is LLM-in-template, never a Python LLM call.

    Static grep (complements the runtime socket-traps) — the judgment code path
    must not construct or import an LLM SDK."""
    import re

    src = Path("src/harness_maker/spec_machine.py").read_text(encoding="utf-8")
    assert not re.search(r"\b(import\s+anthropic|from\s+anthropic|Anthropic\s*\()", src), (
        "spec_machine must not import/construct an LLM SDK (no-network contract)"
    )


# ---------------------------------------------------------------------------
# INTEGRATION — full CLI loop (mark-judged → find-unjudged → drift → stale)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not os.getenv("INTEGRATION"), reason="INTEGRATION=1 to run")
def test_integration_judgment_cli_loop(tmp_path: Path) -> None:
    y = _judgment_yaml(tmp_path)

    def cli(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "harness_maker.spec_machine", *args],
            cwd=str(tmp_path),
            capture_output=True,
            text=True,
            timeout=60,
        )

    # unjudged → gate FAILs (subject present, no verdict)
    assert cli("find-unjudged", "--yaml", str(y), "--root", str(tmp_path)).returncode == 1
    # record an independent pass verdict → gate clears
    mj = cli(
        "mark-judged",
        "--yaml",
        str(y),
        "--ac",
        "AC-001",
        "--verdict",
        "pass",
        "--evidence",
        "criterion-1: subject.py:2 ok",
        "--root",
        str(tmp_path),
    )
    assert mj.returncode == 0, mj.stderr
    assert cli("find-unjudged", "--yaml", str(y), "--root", str(tmp_path)).returncode == 0
    # drift the subject → stale pass → gate FAILs again
    (tmp_path / "subject.py").write_text("def f():\n    return 99\n")
    assert cli("find-unjudged", "--yaml", str(y), "--root", str(tmp_path)).returncode == 1


# ---------------------------------------------------------------------------
# REVIEW Round-2 regressions (k-of-3 fixes)
# ---------------------------------------------------------------------------


def test_find_unjudged_blocks_partial_present_subject(tmp_path: Path) -> None:
    """A multi-path subject with one path present + one absent is IN-SCOPE → block,
    not skipped behind the absent sibling (correctness P1 / CLAUDE.md #6)."""
    from harness_maker.spec_machine import find_unjudged

    y = _judgment_yaml(tmp_path, judgment_subject_paths=["subject.py", "not_yet.py"])
    # subject.py exists (from _judgment_yaml), not_yet.py absent → in-scope, unbound.
    assert find_unjudged(y, tmp_path) == ["AC-001"]


def test_find_unjudged_blocks_empty_subject_paths(tmp_path: Path) -> None:
    """A judgment AC with empty subject_paths (hand-edited past validate) must BLOCK,
    never silently skip (Codex P1 absent-case)."""
    from harness_maker.spec_machine import find_unjudged

    # Build the yaml directly (validate would reject empty paths; the gate must too).
    data = {
        "schema_version": 2,
        "spec_slug": "demo",
        "verification_tier": 1,
        "ac": [
            {
                "id": "AC-001",
                "title": "t",
                "type": "judgment",
                "rubric_id": "skill",
                "oracle_source": "rubric",
                "oracle_evidence": "x",
                "judgment_subject_paths": [],
            }
        ],
    }
    y = tmp_path / "SPEC-demo.machine.yaml"
    y.write_text(yaml.safe_dump(data))
    assert find_unjudged(y, tmp_path) == ["AC-001"]


def test_subject_hash_empty_dir_raises(tmp_path: Path) -> None:
    """A subject dir that expands to zero files = unbound, not a clean empty hash (P2)."""
    from harness_maker.spec_machine import SubjectHashError, compute_subject_hash

    (tmp_path / "emptydir").mkdir()
    with pytest.raises(SubjectHashError):
        compute_subject_hash(["emptydir"], tmp_path)


def test_subject_hash_symlinked_dir_inside_does_not_escape(tmp_path: Path) -> None:
    """A symlinked DIRECTORY inside a subject dir is NOT descended (no escape, security P1)."""
    from harness_maker.spec_machine import compute_subject_hash

    outside = tmp_path.parent / "secrets_dir"
    outside.mkdir(exist_ok=True)
    (outside / "passwd").write_text("SECRET\n")
    subj = tmp_path / "subj"
    subj.mkdir()
    (subj / "real.py").write_text("real\n")
    try:
        (subj / "evil").symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("symlinks unsupported")
    # Must not read the outside file; hash reflects only real.py (no SECRET).
    h = compute_subject_hash(["subj"], tmp_path)
    h_clean = compute_subject_hash(["subj/real.py"], tmp_path)
    # the symlinked-dir contents are excluded → hashing the dir == hashing just real.py
    assert isinstance(h, str)
    assert h == h_clean


def test_subject_hash_dedups_overlapping_declarations(tmp_path: Path) -> None:
    """Declaring a dir AND a file inside it hashes the file ONCE (P2 dedup)."""
    from harness_maker.spec_machine import compute_subject_hash

    d = tmp_path / "pkg"
    d.mkdir()
    (d / "x.py").write_text("x\n")
    h_dir = compute_subject_hash(["pkg"], tmp_path)
    h_both = compute_subject_hash(["pkg", "pkg/x.py"], tmp_path)
    assert h_dir == h_both
