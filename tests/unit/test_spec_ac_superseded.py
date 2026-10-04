"""SPEC-spec-ac-superseded — the superseded_by AC state, `retire`, and every owes-a-test reader."""

from __future__ import annotations

import copy
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import pytest
import yaml
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from harness_maker import spec_machine
from harness_maker.observability import spec_drift
from harness_maker.spec_inventory import batch_refiner
from harness_maker.spec_machine import (
    approval_content_hash,
    approval_state_of,
    approve,
    compute_subject_hash,
    cross_validate,
    evaluate_coverage,
    find_unbound_closed_type_acs,
    find_unjudged,
    load,
    mark_tested,
    select_pytest_bindable,
    stale_judgment_verdicts,
    validate,
)

ROOT = Path(__file__).parents[2]
BINDING_ERROR = "needs >=1 test_ids OR pending_test=true"
# SPEC S8 / round-2 DRI answer — never derived from the code under test.
STAND_INS = (
    ("intent-layer-improvements", "AC-002", "intent-surface-diet"),
    ("intent-layer-improvements", "AC-011", "intent-surface-diet"),
    ("intent-layer-diet", "AC-005", "intent-surface-diet"),
    ("intent-layer-improvements", "AC-006", "intent-layer-diet"),
)


# ── fixtures ────────────────────────────────────────────────────────────────────────────


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True)


def _init_repo(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    _git(root, "init", "-q")
    _git(root, "config", "user.name", "Base User")
    _git(root, "config", "user.email", "base@example.com")
    (root / "specs").mkdir(exist_ok=True)
    return root / "specs"


@pytest.fixture
def specs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(tmp_path / "no-global"))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    return _init_repo(tmp_path / "repo")


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


def _approved(specs_dir: Path, slug: str, acs: list[dict[str, Any]] | None = None) -> Path:
    yaml_path = _write_spec(specs_dir, slug, acs or [_ac("AC-001")])
    approve(yaml_path)
    return yaml_path


def _landed(specs_dir: Path) -> Path:
    """A landed, human-approved SPEC whose AC-002 carries history test_ids."""
    _approved(specs_dir, "target")
    return _approved(
        specs_dir,
        "landed",
        [_ac("AC-001"), _ac("AC-002", test_ids=["tests/old.py::test_gone"], pending_test=True)],
    )


def _ac_of(yaml_path: Path, ac_id: str) -> Any:
    return next(a for a in load(yaml_path).ac if a.id == ac_id)


def _retire(*args: str) -> int:
    return spec_machine.main(["retire", *args])


# ── AC-001 ──────────────────────────────────────────────────────────────────────────────


def test_ac001_retire_records_superseded_by(specs: Path) -> None:
    landed = _landed(specs)
    before = _ac_of(landed, "AC-002")
    assert _retire("--yaml", str(landed), "--ac", "AC-002", "--by", "target") == 0
    after = _ac_of(landed, "AC-002")
    assert after.superseded_by == "target"
    assert after.pending_test is False
    assert after.test_ids == before.test_ids
    # Control: the untouched AC stays live.
    assert getattr(_ac_of(landed, "AC-001"), "superseded_by", None) is None


# ── AC-002 ──────────────────────────────────────────────────────────────────────────────


def _refusal_setup(specs: Path, case: str) -> tuple[Path, dict[str, Any]]:
    landed = _landed(specs)
    kw: dict[str, Any] = {"ac_id": "AC-002", "by": "target"}
    if case == "bad-slug":
        kw["by"] = "Bad Slug"
    elif case == "traversal":
        # `specs/SPEC-x/../up.machine.yaml` resolves to a real approved file, so a missing
        # grammar check would accept it; only the slug grammar can refuse it.
        (specs / "SPEC-x").mkdir()
        (specs / "up.machine.yaml").write_text(
            (specs / "SPEC-target.machine.yaml").read_text(encoding="utf-8"), encoding="utf-8"
        )
        kw["by"] = "x/../up"
    elif case == "missing-target":
        kw["by"] = "ghost"
    elif case == "draft-target":
        _write_spec(specs, "draft", [_ac("AC-001")])
        kw["by"] = "draft"
    elif case == "invalid-target":
        tampered = _approved(specs, "tampered")
        raw = yaml.safe_load(tampered.read_text(encoding="utf-8"))
        raw["ac"][0]["title"] = "edited after approval"
        tampered.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
        kw["by"] = "tampered"
    elif case == "other-checkout":
        # base/.worktrees/<slug> is what approval_state's precedence prefers; the target is
        # approved only there, while the copy beside --yaml is a draft.
        root = specs.parent
        _write_spec(specs, "elsewhere", [_ac("AC-001")])
        _git(root, "add", "-A")
        _git(root, "commit", "-qm", "seed")
        wt = root / ".worktrees" / "elsewhere"
        _git(root, "worktree", "add", "-q", str(wt))
        approve(wt / "specs" / "SPEC-elsewhere.machine.yaml")
        kw["by"] = "elsewhere"
    elif case == "malformed-target":
        (specs / "SPEC-broken.machine.yaml").write_text("ac: [not, a, mapping\n", encoding="utf-8")
        (specs / "SPEC-broken.md").write_text("---\ntype: spec\n---\n", encoding="utf-8")
        kw["by"] = "broken"
    elif case == "legacy-target":
        legacy = _write_spec(specs, "legacy", [_ac("AC-001")])
        raw = yaml.safe_load(legacy.read_text(encoding="utf-8"))
        raw["schema_version"] = 2
        raw.pop("irreversible_decisions")
        legacy.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
        kw["by"] = "legacy"
    elif case == "self":
        kw["by"] = "landed"
    elif case == "unknown-ac":
        kw["ac_id"] = "AC-099"
    elif case == "both-flags":
        kw["clear"] = True
    elif case == "neither-flag":
        kw["by"] = None
    elif case == "retarget":
        _approved(specs, "target2")
        assert spec_machine.retire(landed, "AC-002", by="target") == []
        kw["by"] = "target2"
    return landed, kw


# case → a phrase the refusal must carry, naming the check that failed (SPEC S2).
REFUSAL_CASES = {
    "bad-slug": "must match",
    "traversal": "must match",
    "missing-target": "not found",
    "draft-target": "not approved",
    "invalid-target": "not approved",
    "malformed-target": "not approved",
    "legacy-target": "not approved",
    "other-checkout": "not approved",
    "self": "own spec",
    "unknown-ac": "unknown ac",
    "both-flags": "exactly one",
    "neither-flag": "exactly one",
    "retarget": "already superseded",
}


@pytest.mark.parametrize("case", sorted(REFUSAL_CASES))
def test_ac002_retire_refuses_unsafe(specs: Path, case: str) -> None:
    landed, kw = _refusal_setup(specs, case)
    before = landed.read_bytes()
    errors = spec_machine.retire(landed, kw.pop("ac_id"), **kw)
    assert any(REFUSAL_CASES[case] in e.lower() for e in errors), (case, errors)
    assert landed.read_bytes() == before, case


def test_ac002_retire_accepts_exempt_target(specs: Path) -> None:
    landed = _landed(specs)
    exempt = _write_spec(specs, "skipped", [_ac("AC-001")])
    approve(exempt, exempt=True)
    assert spec_machine.retire(landed, "AC-002", by="skipped") == []
    assert _ac_of(landed, "AC-002").superseded_by == "skipped"


def test_ac002_retire_cli_refusal_exits_nonzero(specs: Path) -> None:
    landed = _landed(specs)
    before = landed.read_bytes()
    assert _retire("--yaml", str(landed), "--ac", "AC-002", "--by", "ghost") != 0
    assert landed.read_bytes() == before


def test_ac002_retire_cli_unreadable_spec_exits_cleanly(
    specs: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    broken = specs / "SPEC-broken.machine.yaml"
    broken.write_text("ac: [not, a, mapping\n", encoding="utf-8")
    assert _retire("--yaml", str(broken), "--ac", "AC-001", "--by", "target") == 1
    assert capsys.readouterr().err.startswith("retire: ")


def test_ac002_same_target_rerun_is_noop(specs: Path) -> None:
    landed = _landed(specs)
    assert spec_machine.retire(landed, "AC-002", by="target") == []
    before = landed.read_bytes()
    assert spec_machine.retire(landed, "AC-002", by="target") == []
    assert landed.read_bytes() == before


# ── AC-003 ──────────────────────────────────────────────────────────────────────────────


@settings(max_examples=12, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(n_acs=st.integers(min_value=1, max_value=5), data=st.data())
def test_ac003_retire_keeps_approval_hash(n_acs: int, data: st.DataObject) -> None:
    pick = data.draw(st.integers(min_value=1, max_value=n_acs))
    types = data.draw(
        st.lists(st.sampled_from(["mechanical", "property"]), min_size=n_acs, max_size=n_acs)
    )
    with tempfile.TemporaryDirectory() as td, pytest.MonkeyPatch.context() as mp:
        mp.setenv("HOME", str(Path(td) / "home"))
        mp.setenv("GIT_CONFIG_GLOBAL", str(Path(td) / "no-global"))
        mp.setenv("GIT_CONFIG_NOSYSTEM", "1")
        specs_dir = _init_repo(Path(td) / "repo")
        acs = []
        for i, kind in enumerate(types, start=1):
            if kind == "property":
                acs.append(
                    _ac(
                        f"AC-{i:03d}",
                        type="property",
                        executable_predicate=None,
                        oracle_source="property",
                        input_domain="ints",
                        transformation="double",
                        expected_relation="f(x) == 2 * x",
                    )
                )
            else:
                acs.append(_ac(f"AC-{i:03d}"))
        _approved(specs_dir, "target")
        landed = _approved(specs_dir, "landed", acs)
        stamped = yaml.safe_load(landed.read_text(encoding="utf-8"))["approval"]["content_hash"]
        ac_id = f"AC-{pick:03d}"
        md = specs_dir / "SPEC-landed.md"

        assert spec_machine.retire(landed, ac_id, by="target") == []
        assert approval_content_hash(load(landed)) == stamped
        assert approval_state_of("landed", landed, md).state == "approved"

        assert spec_machine.retire(landed, ac_id, clear=True) == []
        assert approval_content_hash(load(landed)) == stamped
        assert approval_state_of("landed", landed, md).state == "approved"


# ── AC-004 ──────────────────────────────────────────────────────────────────────────────


def _model(acs: list[dict[str, Any]]) -> Any:
    return spec_machine.SpecMachine.model_validate(
        {
            "schema_version": 3,
            "spec_slug": "m",
            "verification_tier": 1,
            "irreversible_decisions": [],
            "ac": acs,
        }
    )


def _errors_for(errors: list[str], ac_id: str) -> list[str]:
    return [e for e in errors if e.startswith(f"{ac_id}:") or f" {ac_id} " in e]


def test_ac004_validate_exempts_only_binding(specs: Path) -> None:
    _approved(specs, "target")
    model = _model(
        [
            _ac("AC-001", pending_test=False, superseded_by="target"),
            _ac("AC-002", pending_test=False),  # live control
            _ac(
                "AC-003",
                pending_test=False,
                superseded_by="target",
                oracle_source="legacy-unspecified",
            ),
            _ac("AC-004", pending_test=False, superseded_by="Bad Slug"),
            _ac("AC-005", pending_test=False, superseded_by="ghost"),
        ]
    )
    errors = validate(model, spec_dir=specs)
    assert not any(BINDING_ERROR in e for e in _errors_for(errors, "AC-001"))
    assert any(BINDING_ERROR in e for e in _errors_for(errors, "AC-002"))
    assert any("oracle_source" in e for e in _errors_for(errors, "AC-003"))
    assert any("superseded_by" in e and "slug" in e for e in _errors_for(errors, "AC-004"))
    assert any("superseded_by" in e and "ghost" in e for e in _errors_for(errors, "AC-005"))
    # The existing AC-001 target resolves: no target error for it.
    assert not any("superseded_by" in e for e in _errors_for(errors, "AC-001"))


def test_ac004_validate_does_not_check_target_approval(specs: Path) -> None:
    _write_spec(specs, "draft", [_ac("AC-001")])  # exists, never approved
    errors = validate(
        _model([_ac("AC-001", pending_test=False, superseded_by="draft")]), spec_dir=specs
    )
    assert not any("superseded_by" in e for e in errors)


# ── AC-005 ──────────────────────────────────────────────────────────────────────────────


def _mixed(specs: Path, root: Path) -> Path:
    subject = root / "subject.txt"
    subject.write_text("judged content\n", encoding="utf-8")
    good_hash = compute_subject_hash(["subject.txt"], root)
    judgment = {
        "type": "judgment",
        "executable_predicate": None,
        "rubric_id": "r",
        "oracle_source": "rubric",
        "judgment_subject_paths": ["subject.txt"],
        "pending_test": False,
    }
    _approved(specs, "target")
    return _write_spec(
        specs,
        "mixed",
        [
            _ac("AC-001", test_ids=["t.py::test_a"], pending_test=False),  # live, bound
            _ac("AC-002", pending_test=True),  # live, pending
            _ac(
                "AC-003",
                test_ids=["tests/gone.py::test_g"],
                pending_test=False,
                superseded_by="target",
            ),
            {**_ac("AC-004", **judgment), "judgment_verdict": "fail", "superseded_by": "target"},
            {
                **_ac("AC-005", **judgment),
                "judgment_verdict": "pass",
                "judgment_subject_hash": "0" * 64,
                "superseded_by": "target",
            },
            {**_ac("AC-006", **judgment), "judgment_verdict": "fail"},  # live control
            {
                **_ac("AC-007", **judgment),
                "judgment_verdict": "pass",
                "judgment_subject_hash": "0" * 64,
            },
            _ac("AC-008", pending_test=True, superseded_by="target"),  # hand-left pending
            {
                **_ac("AC-009", **judgment),
                "judgment_verdict": "pass",
                "judgment_subject_hash": good_hash,
            },
        ],
    )


def test_ac005_rule3_skips_superseded(specs: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    yaml_path = _mixed(specs, specs.parent)
    seen: list[str] = []

    def fake_collect(test_ids: list[str], cwd: Path) -> list[str]:
        seen.extend(test_ids)
        return []

    monkeypatch.setattr(spec_machine, "_check_pytest_collect", fake_collect)
    cross_validate(specs / "SPEC-mixed.md", yaml_path)
    assert "tests/gone.py::test_g" not in seen
    assert "t.py::test_a" in seen  # live control


def test_ac005_coverage_counts_live_only(specs: Path) -> None:
    yaml_path = _mixed(specs, specs.parent)
    rep = evaluate_coverage(yaml_path)
    assert set(rep) == {"coverage", "missing", "total"}
    # Live: AC-001 bound, AC-002 pending, AC-006/007/009 judgment without test_ids.
    assert rep["total"] == 5
    assert rep["missing"] == ["AC-006", "AC-007", "AC-009"]
    assert rep["coverage"] == pytest.approx(2 / 5)


def test_ac005_all_superseded_matches_zero_ac(specs: Path) -> None:
    _approved(specs, "target")
    all_sup = _write_spec(
        specs, "allsup", [_ac("AC-001", pending_test=False, superseded_by="target")]
    )
    zero = _write_spec(specs, "zero", [])
    expected = {"coverage": 0.0, "missing": [], "total": 0}
    assert evaluate_coverage(all_sup) == expected
    assert evaluate_coverage(zero) == expected


def test_ac005_find_unbound_skips_superseded(specs: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    yaml_path = _mixed(specs, specs.parent)
    every = {a.id for a in load(yaml_path).ac}
    monkeypatch.setattr(spec_machine, "_collectable_ac_tests", lambda model, cwd: (every, True))
    assert find_unbound_closed_type_acs(yaml_path, specs.parent) == ["AC-002"]
    assert [a.id for a in select_pytest_bindable(load(yaml_path), pending_only=True)] == ["AC-002"]


def test_ac005_judgment_readers_skip_superseded(specs: Path) -> None:
    yaml_path = _mixed(specs, specs.parent)
    assert find_unjudged(yaml_path, specs.parent) == ["AC-006", "AC-007"]
    assert stale_judgment_verdicts(yaml_path, specs.parent) == ["AC-007"]


def test_ac005_spec_drift_skips_superseded(specs: Path) -> None:
    _approved(specs, "target")
    _write_spec(
        specs,
        "drift",
        [
            _ac("AC-001", pending_test=False, superseded_by="target"),
            _ac("AC-002", pending_test=False),  # live gap control
        ],
    )
    report = spec_drift.scan(specs)
    assert "drift::AC-001" not in report.coverage_gaps
    assert "drift::AC-002" in report.coverage_gaps


def test_ac005_batch_refiner_leaves_superseded_untouched(
    specs: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _approved(specs, "target")
    yaml_path = _write_spec(
        specs,
        "refine",
        [
            _ac("AC-001", test_ids=["t.py::test_live"], pending_test=True),
            _ac(
                "AC-002",
                test_ids=["tests/gone.py::test_g"],
                pending_test=False,
                superseded_by="target",
            ),
        ],
    )
    # Unresolvable ids are dropped from live ACs; a superseded AC's history must survive that.
    monkeypatch.setattr(
        batch_refiner, "_resolve_test_ids", lambda ids, root: {i for i in ids if "gone" not in i}
    )
    batch_refiner.refine_spec("refine", specs.parent, specs)
    raw = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    sup = next(a for a in raw["ac"] if a["id"] == "AC-002")
    live = next(a for a in raw["ac"] if a["id"] == "AC-001")
    assert sup["test_ids"] == ["tests/gone.py::test_g"]
    assert sup["superseded_by"] == "target"
    assert live["pending_test"] is False  # live control: refined as before


# ── AC-006 ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("validate_after", [True, False])
@pytest.mark.parametrize(
    "request_ids",
    [{"AC-002": ["t.py::test_x"]}, {"AC-001": ["t.py::test_y"], "AC-002": ["t.py::test_x"]}],
    ids=["only-superseded", "mixed"],
)
def test_ac006_mark_tested_refuses_atomically(
    specs: Path,
    monkeypatch: pytest.MonkeyPatch,
    request_ids: dict[str, list[str]],
    validate_after: bool,
) -> None:
    landed = _landed(specs)
    assert spec_machine.retire(landed, "AC-002", by="target") == []
    before = landed.read_bytes()
    calls: list[Any] = []

    def record(*args: Any, **kwargs: Any) -> list[str]:
        calls.append(args)
        return []

    monkeypatch.setattr(spec_machine, "unresolved_test_ids", record)
    monkeypatch.setattr(spec_machine, "_check_pytest_collect", record)
    errors = mark_tested(
        landed, specs / "SPEC-landed.md", copy.deepcopy(request_ids), validate_after=validate_after
    )
    assert any("AC-002" in e for e in errors)
    assert landed.read_bytes() == before
    assert calls == []


# ── AC-007 ──────────────────────────────────────────────────────────────────────────────


def test_ac007_clear_repends(specs: Path) -> None:
    landed = _approved(specs, "landed", [_ac("AC-001"), _ac("AC-002", pending_test=True)])
    _approved(specs, "target")
    raw = yaml.safe_load(landed.read_text(encoding="utf-8"))
    raw["ac"][1]["test_ids"] = ["tests/gone.py::test_g"]
    landed.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    for ac_id in ("AC-001", "AC-002"):  # empty and stale-history test_ids
        assert spec_machine.retire(landed, ac_id, by="target") == []
        assert spec_machine.retire(landed, ac_id, clear=True) == []
        cleared = _ac_of(landed, ac_id)
        assert getattr(cleared, "superseded_by", None) is None
        assert cleared.pending_test is True


def test_ac007_clear_on_live_refused(specs: Path) -> None:
    landed = _landed(specs)
    before = landed.read_bytes()
    assert spec_machine.retire(landed, "AC-001", clear=True)
    assert landed.read_bytes() == before


# ── AC-008 ──────────────────────────────────────────────────────────────────────────────


def test_ac008_absent_field_not_serialised(specs: Path) -> None:
    yaml_path = _write_spec(specs, "plain", [_ac("AC-001"), _ac("AC-002")])
    assert (
        mark_tested(
            yaml_path, specs / "SPEC-plain.md", {"AC-001": ["t.py::test_z"]}, validate_after=False
        )
        == []
    )
    assert "superseded_by" not in yaml_path.read_text(encoding="utf-8")
    landed = _landed(specs)
    assert spec_machine.retire(landed, "AC-002", by="target") == []
    assert spec_machine.retire(landed, "AC-002", clear=True) == []
    assert "superseded_by" not in landed.read_text(encoding="utf-8")


# ── AC-009 ──────────────────────────────────────────────────────────────────────────────


def test_ac009_landed_stand_ins_retired() -> None:
    for slug, ac_id, target in STAND_INS:
        yaml_path = ROOT / "specs" / f"SPEC-{slug}.machine.yaml"
        raw = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
        ac = next(a for a in raw["ac"] if a["id"] == ac_id)
        assert ac.get("superseded_by") == target, (slug, ac_id)
        assert ac.get("pending_test") is False, (slug, ac_id)
    for slug in ("intent-layer-improvements", "intent-layer-diet"):
        yaml_path = ROOT / "specs" / f"SPEC-{slug}.machine.yaml"
        md_path = ROOT / "specs" / f"SPEC-{slug}.md"
        assert approval_state_of(slug, yaml_path, md_path).state == "approved", slug
        assert find_unbound_closed_type_acs(yaml_path, ROOT) == [], slug
