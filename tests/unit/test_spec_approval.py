"""SPEC-ai-native-sdlc-vs-intent-world AC-001/002/004/005 — hash-bound SPEC approval.

Oracles are the SPEC's own tables, written before the implementation: the deny-list (AC-002),
the nine-row state table (AC-005 golden rows, loaded from the machine SPEC), the identity rule
copied from objective approval (AC-001) and the v3 schema rows (AC-004).
"""

from __future__ import annotations

import copy
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml
from hypothesis import given, settings
from hypothesis import strategies as st

from harness_maker import command_registry, spec_machine
from harness_maker.spec_machine import (
    AcceptanceCriterion,
    SpecMachine,
    approval_content_hash,
    approval_state,
    load,
    load_golden_table,
    mark_tested,
    validate,
)

_SPEC_YAML = Path(__file__).parents[2] / "specs/SPEC-ai-native-sdlc-vs-intent-world.machine.yaml"
_SLUG = "demo"

_IRR = {
    "id": "IRR-001",
    "decision": "public verb renamed",
    "category": "public API/CLI contract",
    "rationale": "callers break",
    "source": "spec",
}

_BASE_DOC: dict[str, Any] = {
    "schema_version": 3,
    "spec_slug": _SLUG,
    "verification_tier": 1,
    "irreversible_decisions": [copy.deepcopy(_IRR)],
    "ac": [
        {
            "id": "AC-001",
            "title": "the thing works",
            "type": "mechanical",
            "executable_predicate": "result == 1",
            "oracle_source": "golden",
            "oracle_evidence": "value hand-written from the SPEC table",
            "pending_test": True,
        }
    ],
}


# ── fixture helpers ─────────────────────────────────────────────────────────────


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True)


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(tmp_path / "no-global"))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q")
    _git(root, "config", "user.name", "Base User")
    _git(root, "config", "user.email", "base@example.com")
    (root / "specs").mkdir()
    return root


def _paths(root: Path) -> tuple[Path, Path]:
    return root / "specs" / f"SPEC-{_SLUG}.md", root / "specs" / f"SPEC-{_SLUG}.machine.yaml"


def _write(root: Path, doc: dict[str, Any] | None, *, md: bool = True) -> Path:
    md_path, yaml_path = _paths(root)
    if md:
        md_path.write_text("---\ntype: spec\ntier: 1\n---\n\n### AC-001: the thing works\n")
    if doc is not None:
        yaml_path.write_text(yaml.safe_dump(doc, sort_keys=False))
    return yaml_path


def _raw(path: Path) -> dict[str, Any]:
    loaded = yaml.safe_load(path.read_text())
    assert isinstance(loaded, dict)
    return loaded


def _approve(yaml_path: Path, *extra: str) -> int:
    return spec_machine.main(["approve", "--yaml", str(yaml_path), *extra])


def _independent_hash(raw: dict[str, Any]) -> str:
    """Re-derive the SPEC's hash rule without calling the function under test."""
    model = SpecMachine.model_validate(raw)
    dumped = model.model_dump(mode="json", exclude_defaults=True)
    for key in ("approval", "spec_quality_score", "spec_quality_score_at", "last_mutation_run"):
        dumped.pop(key, None)
    for ac in dumped.get("ac", []):
        for key in (
            "test_ids",
            "pending_test",
            "judgment_verdict",
            "judged_at",
            "judgment_evidence",
            "judgment_subject_hash",
        ):
            ac.pop(key, None)
    text = json.dumps(dumped, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ── AC-001 ──────────────────────────────────────────────────────────────────────


def test_ac_001_approve_records_stamp(repo: Path) -> None:
    yaml_path = _write(repo, _BASE_DOC)
    assert _approve(yaml_path) == 0
    approval = _raw(yaml_path)["approval"]
    expected_hash = _independent_hash(_raw(yaml_path))
    base_root_user_name = "Base User"
    # The AC-001 executable_predicate, verbatim.
    assert (  # noqa: PT018
        approval["kind"] == "human"
        and approval["content_hash"] == expected_hash
        and approval["approved_by"] == base_root_user_name
    )
    assert approval["approved_at"]


def test_ac_001_empty_user_name_refuses(repo: Path) -> None:
    _git(repo, "config", "--unset", "user.name")
    yaml_path = _write(repo, _BASE_DOC)
    before = yaml_path.read_bytes()
    assert _approve(yaml_path) != 0
    assert yaml_path.read_bytes() == before


def test_ac_001_exempt_stamp_needs_no_identity(repo: Path) -> None:
    _git(repo, "config", "--unset", "user.name")
    doc = copy.deepcopy(_BASE_DOC)
    doc["irreversible_decisions"] = []
    yaml_path = _write(repo, doc)
    assert _approve(yaml_path, "--exempt") == 0
    approval = _raw(yaml_path)["approval"]
    assert approval["kind"] == "exempt"
    assert approval.get("approved_by") is None
    assert approval["content_hash"] == _independent_hash(_raw(yaml_path))


def test_ac_001_verbs_are_registered(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    verbs = command_registry.MODULES["spec_machine"].subcommands
    assert {"approve", "approval-status"} <= set(verbs)
    _write(repo, _BASE_DOC)
    rc = spec_machine.main(["approval-status", "--root", str(repo), "--slug", _SLUG])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["state"] == "missing"
    assert payload["land"] == "hold"


# ── AC-002 ──────────────────────────────────────────────────────────────────────

_TOP_FIELDS = sorted(set(SpecMachine.model_fields) - {"approval", "ac"})
_AC_FIELDS = sorted(AcceptanceCriterion.model_fields)
# Copied from the SPEC's "Hash scope (deny-list)" constraint row — never from the module under
# test, so a wrong deny-list in the implementation cannot also be the expected value.
_DENY = {
    "spec_quality_score",
    "spec_quality_score_at",
    "last_mutation_run",
    "ac.test_ids",
    "ac.pending_test",
    "ac.judgment_verdict",
    "ac.judged_at",
    "ac.judgment_evidence",
    "ac.judgment_subject_hash",
}

_REPLACEMENTS: dict[str, Any] = {
    "schema_version": 2,
    "spec_slug": "other-slug",
    "verification_tier": 2,
    "mutation_threshold": 70,
    "mutation_threshold_rationale": "changed",
    "last_mutation_run": "2026-09-19",
    "paths_to_mutate": ["src/harness_maker/spec_machine.py"],
    "mutation_runner": "pytest -x tests/unit",
    "spec_quality_score": 91,
    "spec_quality_score_at": "2026-09-19",
    "parent_spec": "SPEC-cluster",
    "irreversible_decisions": [],
    "ac.id": "AC-002",
    "ac.title": "a different claim",
    "ac.type": "judgment",
    "ac.test_ids": ["tests/unit/test_x.py::test_y"],
    "ac.executable_predicate": "result == 2",
    "ac.golden_table": [{"input": {"a": 1}, "expected": 2}],
    "ac.rubric_id": "rubric-x",
    "ac.note": "a note",
    "ac.pending_test": False,
    "ac.oracle_source": "property",
    "ac.oracle_evidence": "a different justification",
    "ac.oracle_independence_waiver": "waived for a reason",
    "ac.input_domain": "all strings",
    "ac.transformation": "encode then decode",
    "ac.expected_relation": "x == y",
    "ac.preconditions": ["non-empty"],
    "ac.observable_output": "bytes",
    "ac.generator_hint": "text()",
    "ac.judgment_verdict": "pass",
    "ac.judged_at": "2026-09-19",
    "ac.judgment_evidence": "reviewer says ok",
    "ac.judgment_subject_paths": ["src/does-not-exist.py"],
    "ac.judgment_subject_hash": "0" * 64,
}

_FIELD_PATHS = [*_TOP_FIELDS, *(f"ac.{f}" for f in _AC_FIELDS)]


def test_ac_002_every_model_field_has_a_mutation() -> None:
    missing = [p for p in _FIELD_PATHS if p not in _REPLACEMENTS]
    assert not missing, f"new model fields need a mutation in _REPLACEMENTS: {missing}"


@pytest.mark.parametrize("field_path", _FIELD_PATHS)
def test_ac_002_valid_iff_only_denylisted_fields_changed(repo: Path, field_path: str) -> None:
    yaml_path = _write(repo, _BASE_DOC)
    assert _approve(yaml_path) == 0
    raw = _raw(yaml_path)
    value = copy.deepcopy(_REPLACEMENTS[field_path])
    if field_path.startswith("ac."):
        raw["ac"][0][field_path[3:]] = value
    else:
        raw[field_path] = value
    yaml_path.write_text(yaml.safe_dump(raw, sort_keys=False))
    state = approval_state(repo, _SLUG).state
    assert (state == "approved") == (field_path in _DENY), (field_path, state)


@pytest.mark.parametrize(
    "edit",
    ["unknown_top_key", "unknown_ac_key", "append_irreversible", "empty_irreversible"],
)
def test_ac_002_non_model_edits_invalidate(repo: Path, edit: str) -> None:
    yaml_path = _write(repo, _BASE_DOC)
    assert _approve(yaml_path) == 0
    raw = _raw(yaml_path)
    if edit == "unknown_top_key":
        raw["extension_field"] = "authored by a newer tool"
    elif edit == "unknown_ac_key":
        raw["ac"][0]["extension_field"] = "authored"
    elif edit == "append_irreversible":
        raw["irreversible_decisions"].append({**_IRR, "id": "IRR-002", "source": "execute"})
    else:
        raw["irreversible_decisions"] = []
    yaml_path.write_text(yaml.safe_dump(raw, sort_keys=False))
    assert approval_state(repo, _SLUG).state == "invalid"


def test_ac_002_new_defaulted_model_field_keeps_the_hash() -> None:
    class NewerSpecMachine(SpecMachine):
        added_later: int = 0

    raw = copy.deepcopy(_BASE_DOC)
    assert approval_content_hash(NewerSpecMachine.model_validate(raw)) == approval_content_hash(
        SpecMachine.model_validate(raw)
    )


@settings(max_examples=40, deadline=None)
@given(new_title=st.text(min_size=1, max_size=40))
def test_ac_002_title_edits_change_the_hash_iff_the_text_differs(new_title: str) -> None:
    raw = copy.deepcopy(_BASE_DOC)
    before = approval_content_hash(SpecMachine.model_validate(raw))
    raw["ac"][0]["title"] = new_title
    after = approval_content_hash(SpecMachine.model_validate(raw))
    assert (before == after) == (new_title == _BASE_DOC["ac"][0]["title"])


def test_ac_002_round_trip_keeps_new_fields(repo: Path) -> None:
    md_path, yaml_path = _paths(repo)
    _write(repo, _BASE_DOC)
    assert _approve(yaml_path) == 0
    mark_tested(
        yaml_path, md_path, {"AC-001": ["tests/unit/test_x.py::test_y"]}, validate_after=False
    )
    raw = _raw(yaml_path)
    assert raw["irreversible_decisions"]
    assert raw["approval"]["kind"] == "human"
    assert approval_state(repo, _SLUG).state == "approved"


def test_ac_002_round_trip_keeps_legacy_shape(repo: Path) -> None:
    md_path, yaml_path = _paths(repo)
    legacy = {k: v for k, v in _BASE_DOC.items() if k != "irreversible_decisions"}
    legacy["schema_version"] = 2
    _write(repo, legacy)
    mark_tested(
        yaml_path, md_path, {"AC-001": ["tests/unit/test_x.py::test_y"]}, validate_after=False
    )
    raw = _raw(yaml_path)
    assert "approval" not in raw
    assert "irreversible_decisions" not in raw
    assert approval_state(repo, _SLUG).state == "legacy"


# ── AC-004 ──────────────────────────────────────────────────────────────────────


def _v3(**changes: Any) -> SpecMachine:
    raw = copy.deepcopy(_BASE_DOC)
    raw.update(changes)
    return load_model(raw)


def load_model(raw: dict[str, Any]) -> SpecMachine:
    return SpecMachine.model_validate(raw)


def _without_list(version: int | None) -> SpecMachine:
    raw = {k: v for k, v in copy.deepcopy(_BASE_DOC).items() if k != "irreversible_decisions"}
    if version is None:
        raw.pop("schema_version")
        raw["ac"][0]["oracle_source"] = "legacy-unspecified"
    else:
        raw["schema_version"] = version
    return load_model(raw)


def test_ac_004_schema_v3_requires_a_well_formed_list() -> None:
    dup = [copy.deepcopy(_IRR), copy.deepcopy(_IRR)]
    rejected_v3_fixtures = [
        _without_list(3),
        _v3(irreversible_decisions=dup),
        _v3(irreversible_decisions=[{**_IRR, "id": "IRR-1"}]),
        _v3(irreversible_decisions=[{**_IRR, "category": "vibes"}]),
        _v3(irreversible_decisions=[{**_IRR, "source": "someone"}]),
    ]
    accepted_legacy_fixtures = [_without_list(None), _without_list(2)]
    # The AC-004 executable_predicate, verbatim.
    assert all(validate(f) for f in rejected_v3_fixtures) and not any(  # noqa: PT018
        validate(f) for f in accepted_legacy_fixtures
    )


# ── AC-005 ──────────────────────────────────────────────────────────────────────

_ROWS = load_golden_table(_SPEC_YAML, "AC-005")


def _build_row(root: Path, row_input: dict[str, Any]) -> None:
    if row_input.get("spec_md") is False and row_input.get("machine_yaml") is False:
        return
    if row_input.get("spec_md") is True and row_input.get("machine_yaml") is False:
        _write(root, None)
        return
    doc = copy.deepcopy(_BASE_DOC)
    version = row_input.get("schema_version")
    listed = row_input.get("irreversible_decisions")
    approval = row_input.get("approval")
    edited = row_input.get("edited_after")
    if version == "omitted":
        doc.pop("schema_version")
        doc["ac"][0]["oracle_source"] = "legacy-unspecified"
    if listed == "absent" and approval != "human_valid_before_strip":
        # The stripped-writer row approves a valid v3 file first and strips the list after.
        doc.pop("irreversible_decisions")
    elif isinstance(listed, list):
        doc["irreversible_decisions"] = [{**_IRR, "id": i} for i in listed] if listed else []
    if edited == "emptied_list":
        doc["irreversible_decisions"] = [copy.deepcopy(_IRR)]
    yaml_path = _write(root, doc)
    if approval == "human" or approval == "human_valid_before_strip":
        assert _approve(yaml_path) == 0
    elif approval == "exempt":
        raw = _raw(yaml_path)
        raw["approval"] = {
            "kind": "exempt",
            "content_hash": approval_content_hash(load(yaml_path)),
            "approved_by": None,
            "approved_at": "2026-09-19T00:00:00Z",
        }
        yaml_path.write_text(yaml.safe_dump(raw, sort_keys=False))
    raw = _raw(yaml_path)
    if approval == "human_valid_before_strip":
        raw.pop("irreversible_decisions")
    if edited is True:
        raw["ac"][0]["title"] = "edited after approval"
    if edited == "emptied_list":
        raw["irreversible_decisions"] = []
    yaml_path.write_text(yaml.safe_dump(raw, sort_keys=False))


@pytest.mark.parametrize("row", _ROWS, ids=[r.note for r in _ROWS])
def test_ac_005_state_table(repo: Path, row: Any) -> None:
    _build_row(repo, row.input)
    got = approval_state(repo, _SLUG)
    assert got.state == row.expected["state"]
    assert got.land == row.expected["land"]
    assert (got.notice is not None) == bool(row.expected.get("notice", False))


def test_ac_005_malformed_approval_block_is_malformed(repo: Path) -> None:
    yaml_path = _write(repo, _BASE_DOC)
    raw = _raw(yaml_path)
    raw["approval"] = {"kind": "human"}
    yaml_path.write_text(yaml.safe_dump(raw, sort_keys=False))
    got = approval_state(repo, _SLUG)
    assert (got.state, got.land) == ("malformed", "hold")


def test_ac_005_explicit_checkout_wins_over_same_slug_task_worktree(repo: Path) -> None:
    task = repo / ".worktrees" / _SLUG
    (task / "specs").mkdir(parents=True)
    _write(task, _BASE_DOC)
    assert _approve(_paths(task)[1]) == 0
    other = repo / "elsewhere"
    (other / "specs").mkdir(parents=True)
    _write(other, _BASE_DOC)
    assert approval_state(repo, _SLUG).state == "approved"
    assert approval_state(repo, _SLUG, checkout=other).state == "missing"


def test_golden_row_extension_keys_are_hashed_and_round_trip(repo: Path) -> None:
    """A golden row is authored SPEC content like an AC: unknown keys survive and are approved."""
    md_path, yaml_path = _paths(repo)
    doc = copy.deepcopy(_BASE_DOC)
    doc["ac"][0]["golden_table"] = [{"input": {}, "expected": 1, "authored_ext": "A"}]
    _write(repo, doc)
    assert _approve(yaml_path) == 0
    mark_tested(
        yaml_path, md_path, {"AC-001": ["tests/unit/test_x.py::test_y"]}, validate_after=False
    )
    raw = _raw(yaml_path)
    assert raw["ac"][0]["golden_table"][0]["authored_ext"] == "A"
    assert approval_state(repo, _SLUG).state == "approved"
    raw["ac"][0]["golden_table"][0]["authored_ext"] = "B"
    yaml_path.write_text(yaml.safe_dump(raw, sort_keys=False))
    assert approval_state(repo, _SLUG).state == "invalid"


@pytest.mark.parametrize("bad_dir", ["ABSOLUTE", "../outside/"])
def test_spec_dir_outside_the_checkout_is_ignored(repo: Path, tmp_path: Path, bad_dir: str) -> None:
    """A `spec.dir` escaping the checkout cannot supply the SPEC the gate reads."""
    decoy = tmp_path / "outside"
    decoy.mkdir()
    doc = copy.deepcopy(_BASE_DOC)
    doc["irreversible_decisions"] = []
    decoy_yaml = decoy / f"SPEC-{_SLUG}.machine.yaml"
    decoy_yaml.write_text(yaml.safe_dump(doc, sort_keys=False))
    assert _approve(decoy_yaml, "--exempt") == 0
    value = f"{decoy}/" if bad_dir == "ABSOLUTE" else bad_dir
    (repo / ".claude").mkdir(exist_ok=True)
    (repo / ".claude" / "harness.yaml").write_text(f"spec:\n  dir: {value}\n")
    assert approval_state(repo, _SLUG, checkout=repo).state == "no_spec"


def test_an_approved_spec_copied_under_another_slug_is_not_approved(repo: Path) -> None:
    """The hash binds content to itself; the file name must match the content's own slug."""
    doc = copy.deepcopy(_BASE_DOC)
    doc["spec_slug"] = "other"
    other = repo / "specs" / "SPEC-other.machine.yaml"
    other.write_text(yaml.safe_dump(doc, sort_keys=False))
    assert _approve(other) == 0
    assert approval_state(repo, "other").state == "approved"
    _, yaml_path = _paths(repo)
    yaml_path.write_bytes(other.read_bytes())
    state = approval_state(repo, _SLUG)
    assert (state.state, state.land) == ("invalid", "hold")
