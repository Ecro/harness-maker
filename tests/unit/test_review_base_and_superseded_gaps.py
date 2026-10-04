"""SPEC-review-base-and-superseded-gaps: oracle advisory, mark-judged refusal, legacy SPEC."""

from __future__ import annotations

import ast
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml

from harness_maker import spec_machine
from harness_maker.observability import spec_drift
from harness_maker.spec_machine import approve, mark_judged

REPO = Path(__file__).resolve().parents[2]


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True)


@pytest.fixture
def specs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(tmp_path / "no-global"))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q")
    _git(root, "config", "user.name", "Base User")
    _git(root, "config", "user.email", "base@example.com")
    (root / "specs").mkdir()
    return root / "specs"


def _ac(ac_id: str, **over: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": ac_id,
        "title": f"criterion {ac_id}",
        "type": "mechanical",
        "executable_predicate": "result == 1",
        "oracle_source": "golden",
        "oracle_evidence": "value hand-written from the SPEC table",
        "pending_test": True,
    }
    base.update(over)
    return base


def _write_spec(specs_dir: Path, slug: str, acs: list[dict[str, Any]]) -> Path:
    doc = {
        "schema_version": 3,
        "spec_slug": slug,
        "verification_tier": 1,
        "irreversible_decisions": [],
        "ac": acs,
    }
    yaml_path = specs_dir / f"SPEC-{slug}.machine.yaml"
    yaml_path.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
    headings = "".join(f"\n### {a['id']}: {a['title']}\n" for a in acs)
    (specs_dir / f"SPEC-{slug}.md").write_text(
        f"---\ntype: spec\ntier: 1\ntest_framework: pytest\n---\n{headings}", encoding="utf-8"
    )
    return yaml_path


# ── AC-005 ──────────────────────────────────────────────────────────────────────────────


def test_ac005_spec_drift_keeps_oracle_advisory_for_superseded(
    specs: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    approve(_write_spec(specs, "target", [_ac("AC-001")]))
    _write_spec(
        specs,
        "fixture",
        [
            _ac(
                "AC-001",
                pending_test=False,
                superseded_by="target",
                oracle_source="legacy-unspecified",
            ),
            _ac(
                "AC-002",
                pending_test=True,
                test_ids=["tests/unit/test_x.py::test_resolves"],
                superseded_by="target",
            ),
            # Live controls: the advisory and resolved-but-pending still fire for a live AC.
            _ac("AC-003", pending_test=False, oracle_source="legacy-unspecified"),
            _ac("AC-004", pending_test=True, test_ids=["tests/unit/test_x.py::test_live"]),
        ],
    )
    # Every candidate id resolves, so only the superseded skip can keep AC-002 out.
    monkeypatch.setattr(spec_drift, "unresolved_test_ids", lambda ids, root: [])
    monkeypatch.setattr(
        "harness_maker.observability.spec_drift.shutil.which", lambda name: "/usr/bin/pytest"
    )

    report = spec_drift.scan(specs)

    assert "fixture::AC-001" in report.missing_oracle_source
    assert "fixture::AC-003" in report.missing_oracle_source
    assert not {"fixture::AC-001", "fixture::AC-002"} & set(report.coverage_gaps)
    assert "fixture::AC-002" not in report.resolved_but_pending
    assert "fixture::AC-004" in report.resolved_but_pending


# ── AC-006 ──────────────────────────────────────────────────────────────────────────────


def _judgment(ac_id: str, **over: Any) -> dict[str, Any]:
    return _ac(
        ac_id,
        type="judgment",
        executable_predicate=None,
        rubric_id="code-quality",
        oracle_source="rubric",
        oracle_evidence="rubric code-quality, named before the subject existed",
        judgment_subject_paths=["src/never_written.py"],
        **over,
    )


@pytest.mark.parametrize("via", ["api", "cli"])
def test_ac006_mark_judged_refuses_superseded(
    specs: Path, via: str, capsys: pytest.CaptureFixture[str]
) -> None:
    approve(_write_spec(specs, "target", [_ac("AC-001")]))
    yaml_path = _write_spec(specs, "judged", [_judgment("AC-001", superseded_by="target")])
    before = yaml_path.read_bytes()

    if via == "api":
        errors = mark_judged(yaml_path, "AC-001", "pass", "criterion 1: ok", cwd=specs.parent)
        assert errors, "a superseded AC was judged"
        # The subject path does not exist, so a check placed after the hash would surface a
        # SubjectHashError here instead of the refusal.
        assert "AC-001" in errors[0], errors
        assert "superseded" in errors[0], errors
    else:
        rc = spec_machine.main(
            [
                "mark-judged",
                "--yaml",
                str(yaml_path),
                "--ac",
                "AC-001",
                "--verdict",
                "fail",
                "--evidence",
                "criterion 1: no",
                "--root",
                str(specs.parent),
            ]
        )
        assert rc != 0
        err = capsys.readouterr().err
        assert "AC-001" in err, err
        assert "superseded" in err, err
    assert yaml_path.read_bytes() == before


def test_ac006_live_judgment_ac_still_reaches_the_subject_hash(specs: Path) -> None:
    """Control: without `superseded_by` the same fixture fails on the subject, not the refusal."""
    yaml_path = _write_spec(specs, "live", [_judgment("AC-001")])
    errors = mark_judged(yaml_path, "AC-001", "pass", "criterion 1: ok", cwd=specs.parent)
    assert errors
    assert "superseded" not in errors[0]


# ── AC-009 ──────────────────────────────────────────────────────────────────────────────


def _legacy_ac004() -> dict[str, Any]:
    raw = yaml.safe_load(
        (REPO / "specs/SPEC-ai-review-exit-criteria.machine.yaml").read_text(encoding="utf-8")
    )
    return next(a for a in raw["ac"] if a["id"] == "AC-004")


def test_ac009_legacy_spec_states_the_task_branch_exception() -> None:
    md = (REPO / "specs/SPEC-ai-review-exit-criteria.md").read_text(encoding="utf-8")
    row = next(line for line in md.splitlines() if line.startswith("| **`review_base`** |"))
    assert "no commits of its own" not in row, "still lists the zero-commit branch as a skip case"
    assert "task branch" in row

    ac = _legacy_ac004()
    assert ac.get("superseded_by") is None, "AC-004 was retired instead of edited"
    tree = ast.parse(ac["executable_predicate"], mode="eval").body
    assert isinstance(tree, ast.BoolOp)
    assert isinstance(tree.op, ast.And)
    conjuncts = [ast.unparse(v) for v in tree.values]
    assert "frozen_tree_hash == working_tree_hash" in conjuncts
    assert "freeze_commit_parent == review_base" in conjuncts
    assert "review_base != head_sha" not in conjuncts, "the HEAD skip is still unconditional"
    # The HEAD clause must be waived on a task branch: `on_task_branch or review_base != head_sha`.
    waivers = [
        v
        for v in tree.values
        if isinstance(v, ast.BoolOp)
        and isinstance(v.op, ast.Or)
        and sorted(ast.unparse(o) for o in v.values)
        == ["on_task_branch", "review_base != head_sha"]
    ]
    assert len(waivers) == 1, conjuncts
