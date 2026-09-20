"""SPEC-ai-native-sdlc-vs-intent-world AC-001/002/004/005 — hash-bound SPEC approval.

Oracles are the SPEC's own tables, written before the implementation: the deny-list (AC-002),
the nine-row state table (AC-005 golden rows, loaded from the machine SPEC), the identity rule
copied from objective approval (AC-001) and the v3 schema rows (AC-004).
"""

from __future__ import annotations

import copy
import hashlib
import json
import multiprocessing
import os
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
    ApprovalError,
    SpecMachine,
    approval_content_hash,
    approval_state,
    approve,
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
    # Outside the CHECKOUT, but a repository of its own: since
    # SPEC-mutation-survivors-and-approval-p2s, `approve` refuses to write when it cannot
    # resolve a base root, because the read-modify-write lock would otherwise land in a
    # guessed directory (IRR-003). The decoy's location relative to `repo` is what this test
    # is about; whether it sits in any repo at all is not.
    _git(decoy, "init", "-q")
    _git(decoy, "config", "user.name", "Decoy User")
    _git(decoy, "config", "user.email", "decoy@example.com")
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


# ══ SPEC-mutation-survivors-and-approval-p2s ════════════════════════════════════
#
# AC-001/AC-002 (digests), AC-003 (the absent map), AC-004/AC-005 (the shared lock),
# AC-006 (the malformed detail) and AC-011 (the identity refusal).
#
# AC-004 is a plain two-process test, NOT a Hypothesis property. The plan validator
# flagged the two descriptions as incompatible and it is right: a Hypothesis body runs
# once per generated example, and forking two processes per example turns a property
# into a timeout. The relation it asserts is still a property — both accepted writes
# survive, whatever order the lock grants — it just has one deterministic input.
#
# FOUR of these tests PASS before the implementation exists (Phase A.4 screen, recorded):
#   * test_ac_011_approve_refuses_an_empty_identity — characterization of SHIPPED behaviour
#     that the 2026-09-20 mutation run named as a survivor. Its RED evidence is the Phase 4
#     inversion artefact, not a missing implementation.
#   * test_the_removed_list_case_is_a_different_branch — the guard that keeps AC-006's fixture
#     from being confused with the pre-existing branch. Its RED sibling is the AC-006 test.
#   * test_the_approve_cli_still_prints_exactly_four_keys — a negative invariant, vacuously
#     true while `field_hashes` does not exist. Its RED positive sibling,
#     test_ac_001_approve_writes_the_map_into_the_stamp, forces that field into existence.
#   * test_the_landed_specs_content_hash_has_not_moved — a regression pin; it goes red if
#     Phase 2's payload refactor moves the hash, which is the whole hazard it guards.


def _hashed_top_level(doc: dict[str, Any]) -> set[str]:
    """The hashed top-level names, re-derived here rather than imported from the subject."""
    dumped = SpecMachine.model_validate(doc).model_dump(mode="json", exclude_defaults=True)
    for key in ("approval", "spec_quality_score", "spec_quality_score_at", "last_mutation_run"):
        dumped.pop(key, None)
    return set(dumped)


# ── AC-001: the digest map covers exactly the hashed fields ─────────────────────


@settings(max_examples=30, deadline=None)
@given(
    extra_acs=st.integers(min_value=0, max_value=4),
    tier=st.sampled_from([1, 2, 3]),
    # `mutation_runner` carries a prefix validator; the point of generating it is only that
    # an OPTIONAL field's presence moves the hashed key set, so the values stay valid.
    runner=st.one_of(
        st.none(), st.sampled_from(["pytest -x", "python -m pytest", "uv run pytest"])
    ),
)
def test_ac_001_the_digest_keys_are_the_hashed_fields_expanded(
    extra_acs: int, tier: int, runner: str | None
) -> None:
    """The metamorphic relation, not a fixed list: whatever the SPEC carries, the keys follow.

    `ac` is expanded into one key per id plus `ac_order`; every other hashed top-level name
    keeps its own key. Generating the AC count, the tier and an optional-field's presence
    moves the hashed key set around, so an implementation that hardcodes today's names fails.
    """
    doc = copy.deepcopy(_BASE_DOC)
    doc["verification_tier"] = tier
    if runner is not None:
        doc["mutation_runner"] = runner
    for n in range(extra_acs):
        extra = copy.deepcopy(_BASE_DOC["ac"][0])
        extra["id"] = f"AC-{n + 2:03d}"
        doc["ac"].append(extra)

    from harness_maker.spec_machine import field_digests

    model = SpecMachine.model_validate(doc)
    digests = field_digests(model)

    ids = {ac["id"] for ac in doc["ac"]}
    expected = (_hashed_top_level(doc) - {"ac"}) | ids | {"ac_order"}
    assert set(digests) == expected


def test_ac_001_approve_writes_the_map_into_the_stamp(repo: Path) -> None:
    """The map has to reach disk: a helper nothing calls names no field at read time."""
    _write(repo, _BASE_DOC)
    _, yaml_path = _paths(repo)
    assert _approve(yaml_path) == 0
    stamp = load(yaml_path).approval
    assert stamp is not None
    assert stamp.field_hashes, "approve stamped no digest map"
    assert "AC-001" in stamp.field_hashes
    assert "ac_order" in stamp.field_hashes


# ── AC-002: one change, one named field ─────────────────────────────────────────


def _named_fields(detail: str | None) -> set[str]:
    """The field names a detail carries, parsed the way a reader would."""
    if not detail or ":" not in detail:
        return set()
    return {part.strip() for part in detail.rsplit(":", 1)[1].split(",") if part.strip()}


def _seed_runner(d: dict[str, Any]) -> None:
    d["mutation_runner"] = "pytest -x"


@pytest.mark.parametrize(
    ("seed", "mutate", "expected"),
    [
        (None, lambda d: d["ac"][0].__setitem__("title", "moved"), {"AC-001"}),
        (None, lambda d: d.__setitem__("verification_tier", 2), {"verification_tier"}),
        (None, lambda d: d.__setitem__("mutation_runner", "pytest -x"), {"mutation_runner"}),
        (_seed_runner, lambda d: d.pop("mutation_runner"), {"mutation_runner"}),
    ],
    ids=["edit-an-ac", "edit-a-top-level-field", "add-a-key", "remove-a-key"],
)
def test_ac_002_one_change_names_exactly_that_field(
    repo: Path, seed: Any, mutate: Any, expected: set[str]
) -> None:
    """Edit, addition and removal all reach the detail — the key set is content-dependent.

    The removal case needs a field that is **optional with a default**, so that popping it
    changes the key set `model_dump(exclude_defaults=True)` produces rather than making the
    document fail to load. `verification_tier` is `Literal[1, 2, 3]` with no default: removing
    it raises `ValidationError`, `approval_state_of` answers `malformed`, and the case could
    never reach the `invalid` it asserts (A.5 round 1). So the removal case seeds
    `mutation_runner` BEFORE the approval and pops it after.
    """
    doc = copy.deepcopy(_BASE_DOC)
    if seed is not None:
        seed(doc)
    _write(repo, doc)
    _, yaml_path = _paths(repo)
    assert _approve(yaml_path) == 0
    raw = _raw(yaml_path)
    mutate(raw)
    yaml_path.write_text(yaml.safe_dump(raw, sort_keys=False))

    state = approval_state(repo, _SLUG)
    assert state.state == "invalid"
    assert _named_fields(state.detail) == expected


def test_ac_002_a_reordered_ac_list_names_ac_order(repo: Path) -> None:
    """`sort_keys` sorts dict keys, never list order — so a permutation IS hashed.

    Without an `ac_order` key this case moves the hash and names nothing, which is the
    silent hold ADR-003 rejects.
    """
    doc = copy.deepcopy(_BASE_DOC)
    second = copy.deepcopy(doc["ac"][0])
    second["id"] = "AC-002"
    doc["ac"].append(second)
    _write(repo, doc)
    _, yaml_path = _paths(repo)
    assert _approve(yaml_path) == 0

    raw = _raw(yaml_path)
    raw["ac"].reverse()
    yaml_path.write_text(yaml.safe_dump(raw, sort_keys=False))

    state = approval_state(repo, _SLUG)
    assert state.state == "invalid"
    assert _named_fields(state.detail) == {"ac_order"}


# ── AC-003: the stamp that has no map ───────────────────────────────────────────


def test_ac_003_a_pre_digest_stamp_says_it_cannot_name_fields(repo: Path) -> None:
    """Every stamp written before this change has no map, including the one on main."""
    _write(repo, _BASE_DOC)
    _, yaml_path = _paths(repo)
    assert _approve(yaml_path) == 0
    raw = _raw(yaml_path)
    raw["approval"].pop("field_hashes", None)  # a stamp from before this feature
    raw["verification_tier"] = 2
    yaml_path.write_text(yaml.safe_dump(raw, sort_keys=False))

    state = approval_state(repo, _SLUG)
    assert state.state == "invalid"
    assert state.detail is not None
    assert "digest" in state.detail
    assert "predates" not in state.detail, "the stamp's age is not knowable from an absent map"


# ── AC-004 / AC-005: the shared read-modify-write lock ──────────────────────────


def _child_approve(yaml_path: str, barrier: Any) -> None:  # pragma: no cover - child process
    barrier.wait(timeout=30)
    approve(Path(yaml_path))


def _child_mark_tested(  # pragma: no cover - child process
    yaml_path: str, md_path: str, node_id: str, barrier: Any
) -> None:
    barrier.wait(timeout=30)
    errors = mark_tested(Path(yaml_path), Path(md_path), {"AC-001": [node_id]})
    if errors:  # a refused write is not a lost update — fail the child loudly
        raise SystemExit("; ".join(errors))


def test_ac_004_concurrent_writers_keep_both_updates(repo: Path) -> None:
    """Two processes, not two threads: under the GIL a thread pair hides the lost update."""
    md_path, yaml_path = _paths(repo)
    _write(repo, _BASE_DOC)

    # `mark_tested` validates BEFORE it persists: a test_id that does not resolve via
    # `pytest --collect-only` makes it return errors and leave the file untouched. With a
    # fictitious node id the write never happens for a reason that has nothing to do with the
    # lock, so the assertion below could never pass — correct implementation or not
    # (A.5 round 1). The fixture therefore ships a test file that really collects.
    real_test = repo / "tests" / "unit" / "test_collected.py"
    real_test.parent.mkdir(parents=True)
    real_test.write_text("def test_y() -> None:\n    assert True\n")
    node_id = "tests/unit/test_collected.py::test_y"

    ctx = multiprocessing.get_context("fork")
    barrier = ctx.Barrier(2)
    procs = [
        ctx.Process(target=_child_approve, args=(str(yaml_path), barrier)),
        ctx.Process(
            target=_child_mark_tested, args=(str(yaml_path), str(md_path), node_id, barrier)
        ),
    ]
    for p in procs:
        p.start()
    for p in procs:
        p.join(timeout=60)
    assert [p.exitcode for p in procs] == [0, 0]

    model = load(yaml_path)
    assert model.approval is not None, "the approval was overwritten by the test write-back"
    assert model.ac[0].test_ids == [node_id], "the test binding was overwritten by the approval"


def test_ac_005_an_unlockable_filesystem_still_writes(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ENOSYS/EOPNOTSUPP is the branch `world._rmw_lock` already carries — one policy."""
    import fcntl

    def _unsupported(fd: int, op: int) -> None:
        raise OSError(38, "Function not implemented")

    monkeypatch.setattr(fcntl, "flock", _unsupported)
    _write(repo, _BASE_DOC)
    _, yaml_path = _paths(repo)
    assert approve(yaml_path).kind == "human"
    # Binds the assertion to the lock path actually being taken: the helper opens the lock
    # file with O_CREAT BEFORE flock refuses, so an implementation with no lock at all leaves
    # nothing here and this test is vacuous — which is what it was when first written.
    assert (repo / ".claude" / "observability").is_dir()


def test_a_lock_timeout_reaches_the_cli_as_an_approval_error(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`_run_approve` catches ApprovalError; an escaping lock error prints a traceback."""
    import fcntl

    def _always_busy(fd: int, op: int) -> None:
        raise BlockingIOError(11, "Resource temporarily unavailable")

    monkeypatch.setattr(fcntl, "flock", _always_busy)
    monkeypatch.setattr(spec_machine, "_LOCK_TIMEOUT_S", 0.05)
    _write(repo, _BASE_DOC)
    _, yaml_path = _paths(repo)
    with pytest.raises(ApprovalError):
        approve(yaml_path)
    assert _approve(yaml_path) == 1  # the CLI's except clause, not a traceback


def test_the_lock_file_lands_under_the_base_roots_claude_directory(repo: Path) -> None:
    """The literal path, because a prose claim that it is gitignored is what failed before.

    `world._rmw_lock` derives its path as `path.parent.parent / "observability"`, which is
    correct only for `.claude/intent.yaml`. The same expression on `specs/SPEC-x.machine.yaml`
    yields `<repo>/observability/` — untracked and un-ignored.
    """
    _write(repo, _BASE_DOC)
    _, yaml_path = _paths(repo)
    assert _approve(yaml_path) == 0
    expected = repo / ".claude" / "observability" / f".hm-spec-SPEC-{_SLUG}.machine.lock"
    assert expected.exists(), sorted(str(p) for p in repo.rglob("*.lock"))
    assert not (repo / "observability").exists()
    assert not (repo / "specs" / ".claude").exists()


def test_an_ambiguous_base_root_refuses_to_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Fail closed when a repository is there but git will not name its root.

    `resolve_base_root` answers that case by returning its own argument, so this process and
    a peer with working git would take DIFFERENT lock files and neither would notice. That is
    IRR-003's failure, so the write is refused instead of guessing. The narrower sibling case
    — no repository at all — is covered by the test below and deliberately does NOT refuse.
    """
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    global_cfg = tmp_path / "gitconfig"
    global_cfg.write_text("[user]\n\tname = Loose User\n\temail = loose@example.com\n")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(global_cfg))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    root = tmp_path / "repoish"
    (root / "specs").mkdir(parents=True)
    (root / ".git").mkdir()  # a repository marker git itself will not accept
    yaml_path = root / "specs" / f"SPEC-{_SLUG}.machine.yaml"
    yaml_path.write_text(yaml.safe_dump(_BASE_DOC, sort_keys=False))
    before = yaml_path.read_bytes()
    with pytest.raises(ApprovalError):
        approve(yaml_path)
    assert yaml_path.read_bytes() == before


def test_outside_any_repository_the_lock_sits_beside_the_spec(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No repository means no peer disagreement and no tracked directory to dirty.

    Every writer computes the same sibling path, which is all a lock needs; refusing here
    would make `mark_tested` and `mark_judged` require git, which they never did (27 existing
    tests measured that coupling before the rule was narrowed).
    """
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    global_cfg = tmp_path / "gitconfig"
    global_cfg.write_text("[user]\n\tname = Loose User\n\temail = loose@example.com\n")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(global_cfg))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    loose = tmp_path / "loose" / "specs"
    loose.mkdir(parents=True)
    yaml_path = loose / f"SPEC-{_SLUG}.machine.yaml"
    yaml_path.write_text(yaml.safe_dump(_BASE_DOC, sort_keys=False))

    assert approve(yaml_path).kind == "human"
    assert (loose / f".hm-spec-SPEC-{_SLUG}.machine.lock").exists()


# ── AC-006: the malformed detail ────────────────────────────────────────────────


def test_ac_006_a_malformed_spec_reports_the_validation_error(repo: Path) -> None:
    """`verification_tier: 9` is rejected by the Literal at load time — a real ValidationError.

    Removing `irreversible_decisions` does NOT reach this branch: the field is declared
    `list | None = None`, so `load()` succeeds and the pre-existing
    `schema_version 3 without irreversible_decisions` answer is returned instead.
    """
    raw = copy.deepcopy(_BASE_DOC)
    raw["verification_tier"] = 9
    _write(repo, raw)

    state = approval_state(repo, _SLUG)
    assert state.state == "malformed"
    assert state.detail is not None
    assert "verification_tier" in state.detail
    assert len(state.detail) <= 200


def test_the_removed_list_case_is_a_different_branch(repo: Path) -> None:
    """The guard for the AC-006 fixture: this input must NOT be mistaken for the one above."""
    raw = copy.deepcopy(_BASE_DOC)
    raw.pop("irreversible_decisions")
    _write(repo, raw)
    state = approval_state(repo, _SLUG)
    assert state.state == "malformed"
    assert state.detail == "schema_version 3 without irreversible_decisions"


# ── AC-011: approve refuses an empty identity ───────────────────────────────────


def test_ac_011_approve_refuses_an_empty_identity(repo: Path) -> None:
    """An empty `user.name` must raise AND leave the file byte-identical."""
    _git(repo, "config", "--unset", "user.name")
    _write(repo, _BASE_DOC)
    _, yaml_path = _paths(repo)
    before = yaml_path.read_bytes()
    with pytest.raises(ApprovalError):
        approve(yaml_path)
    assert yaml_path.read_bytes() == before


# ── contract guards (Contract Boundaries, PLAN) ─────────────────────────────────


def test_the_approve_cli_still_prints_exactly_four_keys(repo: Path, capsys: Any) -> None:
    """A declared model field reaches `_run_approve`'s dump automatically; the SPEC's IRR-001
    authorised a disk-format extension, not a change to what the command prints."""
    _write(repo, _BASE_DOC)
    _, yaml_path = _paths(repo)
    assert _approve(yaml_path) == 0
    printed = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert set(printed) == {"kind", "content_hash", "approved_by", "approved_at"}


def test_the_landed_specs_content_hash_has_not_moved() -> None:
    """Every existing stamp is bound to this value; a refactor that moves it invalidates all."""
    landed = Path(__file__).parents[2] / "specs/SPEC-ai-native-sdlc-vs-intent-world.machine.yaml"
    model = load(landed)
    stamp = model.approval
    assert stamp is not None
    model.approval = None
    assert approval_content_hash(model) == (
        "9b4df032189323f6a9daf25ccb27aae3a8bfeba199c85f315cf2161a53d0042e"
    )
    assert stamp.content_hash == approval_content_hash(model)


# ── review round 1 repairs ──────────────────────────────────────────────────────


def test_a_top_level_key_colliding_with_a_digest_key_is_refused(repo: Path) -> None:
    """`extra="allow"` lets a SPEC carry a top-level key named `AC-001` or `ac_order`.

    Measured before the fix: editing such a field moved `approval_content_hash` while NO
    digest changed, so the hold fired and named nothing — the silence the map exists to
    remove, arriving through the one door the map itself opened. Refusing at stamp time is
    the recoverable half; naming nothing at read time is not.
    """
    from harness_maker.spec_machine import FieldDigestCollisionError, field_digests

    doc = copy.deepcopy(_BASE_DOC)
    doc["AC-001"] = "an authored top-level key that collides with the AC's own digest key"
    with pytest.raises(FieldDigestCollisionError, match="AC-001"):
        field_digests(SpecMachine.model_validate(doc))

    _write(repo, doc)
    _, yaml_path = _paths(repo)
    assert _approve(yaml_path) == 1, "approve must refuse rather than stamp a lossy map"


def test_the_lock_budget_exceeds_the_longest_held_operation() -> None:
    """A wait budget shorter than the hold makes a CORRECT holder fail its peer.

    The relationship is the invariant, not the numbers: `mark_tested` runs a
    `pytest --collect-only` subprocess while holding the lock, so the budget must outlast it.
    Round 1 shipped 30 s against a 60 s subprocess.
    """
    assert spec_machine._LOCK_TIMEOUT_S > spec_machine._COLLECT_TIMEOUT_S


def test_cross_validate_runs_outside_the_lock(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The post-write check only reads, and it costs a second collect subprocess.

    Asserted on observable state rather than on call order: the lock file is unlocked by the
    time `cross_validate` runs, so a peer can take it from inside that call.
    """
    import fcntl

    md_path, yaml_path = _paths(repo)
    _write(repo, _BASE_DOC)
    real_test = repo / "tests" / "unit" / "test_collected.py"
    real_test.parent.mkdir(parents=True)
    real_test.write_text("def test_y() -> None:\n    assert True\n")

    held: list[bool] = []

    def _probe(md: Path, yml: Path) -> list[str]:
        lock = repo / ".claude" / "observability" / f".hm-spec-{yaml_path.stem}.lock"
        fd = os.open(str(lock), os.O_CREAT | os.O_WRONLY, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)  # would raise if still held
            held.append(False)
        except OSError:
            held.append(True)
        finally:
            os.close(fd)
        return []

    monkeypatch.setattr(spec_machine, "cross_validate", _probe)
    mark_tested(yaml_path, md_path, {"AC-001": ["tests/unit/test_collected.py::test_y"]})
    assert held == [False], "the lock was still held while cross_validate ran"


def test_the_mark_tested_cli_reports_a_lock_failure_instead_of_a_traceback(
    repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: Any
) -> None:
    """`approve` caught ApprovalError; the other two writers the lock was added to did not."""
    md_path, yaml_path = _paths(repo)
    _write(repo, _BASE_DOC)

    def _boom(path: Path) -> Any:
        raise ApprovalError("simulated contention")

    monkeypatch.setattr(spec_machine, "_spec_write_lock", _boom)
    rc = spec_machine.main(
        ["mark-tested", "--yaml", str(yaml_path), "--md", str(md_path), "--ac", "AC-001"]
    )
    assert rc == 1
    assert "mark-tested: simulated contention" in capsys.readouterr().err


def test_the_mark_judged_cli_reports_a_lock_failure_instead_of_a_traceback(
    repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: Any
) -> None:
    """Same gap, same shape — the third writer."""
    _, yaml_path = _paths(repo)
    _write(repo, _BASE_DOC)

    def _boom(path: Path) -> Any:
        raise ApprovalError("simulated contention")

    monkeypatch.setattr(spec_machine, "_spec_write_lock", _boom)
    rc = spec_machine.main(
        [
            "mark-judged",
            "--yaml",
            str(yaml_path),
            "--ac",
            "AC-001",
            "--verdict",
            "pass",
            "--evidence",
            "x",
            "--root",
            str(repo),
        ]
    )
    assert rc == 1
    assert "mark-judged: simulated contention" in capsys.readouterr().err


# ── confirmation-pass repairs ───────────────────────────────────────────────────


@pytest.mark.parametrize("case", ["collision", "slug-mismatch", "many-fields"])
def test_every_reported_state_bounds_its_detail(repo: Path, case: str) -> None:
    """The cap is a property of the DETAIL, not of whichever branch someone remembered.

    Three rounds put the cap at a composition site and three times a sibling branch was
    missed: round 2 capped `_changed_field_names`'s main return while the caller prepended 24
    characters after it (224 out); the confirm-1 repair capped that caller while the
    collision message went out at 739; confirm-2 found the `spec_slug`-mismatch branch three
    lines below still uncapped. It now lives in `_state`, which every branch must call.

    Only `collision` and `slug-mismatch` actually cross 200 characters — `_MAX_NAMED_FIELDS`
    bounds the `many-fields` case to roughly 150 before any cap applies, so that case proves
    the state and not the bound. It is kept for the state assertion and labelled here rather
    than left to imply coverage it does not give.
    """
    doc = copy.deepcopy(_BASE_DOC)
    base_ac = copy.deepcopy(doc["ac"][0])
    for n in range(2, 12):  # enough ids to cross 200 chars; more only adds fixture noise
        extra = copy.deepcopy(base_ac)
        extra["id"] = f"AC-{n:012d}"  # `AC-\d{3,}` sets no upper bound on the digits
        doc["ac"].append(extra)

    if case == "slug-mismatch":
        # This branch is only REACHABLE when the hash still matches and the file name does
        # not: `spec_slug` is a hashed field, so editing it in place returns at the
        # hash-mismatch branch above and never reaches the one under test. Approve under the
        # long slug, then present the same bytes under another name.
        # Long enough that `approval is for '<slug>'` passes 200 characters, short enough
        # that the file name stays inside the filesystem's 255-byte limit.
        doc["spec_slug"] = "a" + "-long" * 42 + "-slug"
        other = repo / "specs" / f"SPEC-{doc['spec_slug']}.machine.yaml"
        other.write_text(yaml.safe_dump(doc, sort_keys=False))
        assert _approve(other) == 0
        _write(repo, None)  # the .md, so the slug resolves
        _, yaml_path = _paths(repo)
        yaml_path.write_bytes(other.read_bytes())
        state = approval_state(repo, _SLUG)
        assert state.state == "invalid"
        assert state.detail is not None
        assert "approval is for" in state.detail, "the slug-mismatch branch was not reached"
        assert len(state.detail) <= 200, f"detail was {len(state.detail)} chars"
        return

    _write(repo, doc)
    _, yaml_path = _paths(repo)
    assert _approve(yaml_path) == 0

    raw = _raw(yaml_path)
    if case == "many-fields":
        for ac in raw["ac"]:
            ac["title"] = "moved"  # every criterion changes at once
    else:  # collision — an authored top-level key per AC id
        for ac in raw["ac"]:
            raw[ac["id"]] = "collides with this AC's own digest key"

    yaml_path.write_text(yaml.safe_dump(raw, sort_keys=False))
    state = approval_state(repo, _SLUG)
    assert state.state == "invalid"
    assert state.detail is not None
    assert len(state.detail) <= 200, f"detail was {len(state.detail)} chars: {state.detail!r}"


@pytest.mark.parametrize("command", ["mark-tested", "mark-judged"])
def test_a_symlinked_lock_path_is_reported_not_raised(
    repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: Any, command: str
) -> None:
    """`O_NOFOLLOW` turns a planted symlink into `ELOOP`, which is NOT a LockTimeoutError.

    Parametrized over BOTH writers: the repair widened two `except` clauses and only one had
    evidence, so narrowing `mark-judged`'s back would have passed the suite silently (three
    lenses raised this in confirmation pass 2).

    It is raised before the polling loop, so `_spec_write_lock`'s `except LockTimeoutError`
    never sees it. `_run_approve` caught `OSError` already; the two handlers this task added
    did not, so the hardening introduced a fresh traceback path at the same CLI boundary two
    earlier findings were about (confirmation pass, P2).
    """
    md_path, yaml_path = _paths(repo)
    _write(repo, _BASE_DOC)
    lock_dir = repo / ".claude" / "observability"
    lock_dir.mkdir(parents=True, exist_ok=True)
    (lock_dir / f".hm-spec-{yaml_path.stem}.lock").symlink_to(repo / "decoy-target")

    argv = (
        ["mark-tested", "--yaml", str(yaml_path), "--md", str(md_path), "--ac", "AC-001"]
        if command == "mark-tested"
        else [
            "mark-judged",
            "--yaml",
            str(yaml_path),
            "--ac",
            "AC-001",
            "--verdict",
            "pass",
            "--evidence",
            "x",
            "--root",
            str(repo),
        ]
    )
    rc = spec_machine.main(argv)
    assert rc == 1
    err = capsys.readouterr().err
    assert f"{command}:" in err
    # The errno, not just the prefix. What this proves is narrower than it first looks, and
    # the earlier wording here overclaimed: an over-broad `except Exception` stringifies the
    # SAME ELOOP message, so this does NOT separate a broad catch from a scoped one. What it
    # does separate is a real `OSError(ELOOP)` from anything else that happens to reach the
    # same `f"{command}: {exc}"` line — a wrapped or re-raised exception, or a narrower catch
    # that never sees ELOOP at all, which is the regression the repair targets.
    assert (
        "symbolic link" in err.lower() or "eloop" in err.lower() or "too many levels" in err.lower()
    )
