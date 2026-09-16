"""AC-001 (objective half), AC-008, AC-009, AC-010, AC-015 (close half) — objective records.

Hashes are recomputed test-side from the SPEC payload rules (`world_fixture.approval_hash`);
validity is read through `world.derive` on a RELOADED world and the file bytes are compared
so a verifier that writes cannot pass.
"""

from __future__ import annotations

import itertools
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from harness_maker import world
from tests.unit import world_fixture as fx

STATES = ("proposed", "active", "closed", "dropped")
LEGAL = {
    ("proposed", "active"),
    ("active", "closed"),
    ("proposed", "dropped"),
    ("active", "dropped"),
    ("dropped", "proposed"),
}
TARGET = 10


def _root(
    tmp_path: Path, obj: dict[str, Any], *, extra: list[dict[str, Any]] | None = None
) -> Path:
    return fx.build_root(
        tmp_path,
        assumptions=[fx.assumption(), fx.assumption("second", claim="c")],
        objectives=[obj, *(extra or [])],
    )


def _obj(oid: str, state: str, *, valid_approval: bool) -> dict[str, Any]:
    kwargs: dict[str, Any] = {"state": state}
    if state == "closed":
        kwargs.update(observed="met", note="n", closed_at="2026-09-03T00:00:00Z")
    obj = fx.objective(oid, **kwargs)
    if valid_approval:
        # A dropped record may carry the approval it had when active — reopen must CLEAR it.
        obj = fx.approved(obj, TARGET)
    return obj


# ── AC-008 ────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(("src", "dst"), list(itertools.product(STATES, STATES)))
def test_ac_008_direct_transitions_follow_the_table(tmp_path: Path, src: str, dst: str) -> None:
    root = _root(tmp_path, _obj("OBJ-1", src, valid_approval=True))
    before = fx.objective_doc_path(root, "OBJ-1").read_bytes()
    assert (
        fx.load(fx.objective_doc_path(root, "OBJ-1"))["approval"] is not None
    )  # every pre-state carries one
    legal = (src, dst) in LEGAL
    try:
        world.transition(root, "OBJ-1", dst, observed="met", note="n")
        accepted = True
    except world.WorldError:
        accepted = False
    assert accepted is legal, (src, dst)
    after = fx.load(fx.objective_doc_path(root, "OBJ-1"))
    assert after["state"] == (dst if legal else src)
    if not legal:
        assert fx.objective_doc_path(root, "OBJ-1").read_bytes() == before
    if (src, dst) == ("dropped", "proposed"):
        assert after["approval"] is None


def test_ac_008_activation_needs_a_valid_approval(tmp_path: Path) -> None:
    root = _root(tmp_path, _obj("OBJ-1", "proposed", valid_approval=False))
    with pytest.raises(world.WorldError) as exc:
        world.transition(root, "OBJ-1", "active")
    assert exc.value.field == "approval"
    assert fx.load(fx.objective_doc_path(root, "OBJ-1"))["state"] == "proposed"


@pytest.mark.parametrize("state", ["closed", "dropped"])
@pytest.mark.parametrize("field", ["title", "scope", "note", "observed", "depends_on"])
def test_ac_008_terminal_records_refuse_every_field_edit(
    tmp_path: Path, state: str, field: str
) -> None:
    root = _root(tmp_path, _obj("OBJ-1", state, valid_approval=True))
    before = fx.objective_doc_path(root, "OBJ-1").read_bytes()
    with pytest.raises(world.WorldError):
        world.edit_objective(
            root, "OBJ-1", **{field: ["x"] if field in ("scope", "depends_on") else "x"}
        )
    assert fx.objective_doc_path(root, "OBJ-1").read_bytes() == before


# ── AC-009 ────────────────────────────────────────────────────────────────────

HASHED_EDITS: dict[str, Any] = {
    "scope": ["a different scope"],
    "non_scope": ["something else"],
    "hypothesis": "a new hypothesis",
    "outcome_id": "other_outcome",
}
NON_HASHED_EDITS: dict[str, Any] = {
    "depends_on": ["second"],
    "rejected": ["do nothing"],
    "revisit_when": {"assumption": "second", "status": "unknown"},
}


def _two_outcome_root(tmp_path: Path, obj: dict[str, Any]) -> Path:
    return fx.build_root(
        tmp_path,
        intent=fx.intent_doc(fx.outcome(), fx.outcome("other_outcome", target=5)),
        assumptions=[fx.assumption(), fx.assumption("second", claim="c")],
        objectives=[obj],
    )


@pytest.mark.parametrize("field", sorted(HASHED_EDITS))
def test_ac_009_hashed_edit_invalidates_without_writing(tmp_path: Path, field: str) -> None:
    root = _two_outcome_root(tmp_path, _obj("OBJ-1", "active", valid_approval=True))
    doc = fx.load(fx.objective_doc_path(root, "OBJ-1"))
    assert doc["approval"]["content_hash"] == fx.approval_hash(doc, TARGET)
    doc[field] = HASHED_EDITS[field]
    fx.dump(fx.objective_doc_path(root, "OBJ-1"), doc)
    before = fx.objective_doc_path(root, "OBJ-1").read_bytes()
    d = world.derive(world.load_world(root), "OBJ-1")
    assert d.approval_valid is False
    assert fx.objective_doc_path(root, "OBJ-1").read_bytes() == before
    assert fx.load(fx.objective_doc_path(root, "OBJ-1"))["state"] == "active"


def test_ac_009_target_edit_in_intent_invalidates(tmp_path: Path) -> None:
    root = _two_outcome_root(tmp_path, _obj("OBJ-1", "active", valid_approval=True))
    doc = fx.load(root / ".claude" / "intent.yaml")
    doc["outcomes"][0]["target"] = 11
    fx.dump(root / ".claude" / "intent.yaml", doc)
    assert world.derive(world.load_world(root), "OBJ-1").approval_valid is False


def test_ac_009_how_measured_edit_does_not_invalidate(tmp_path: Path) -> None:
    root = _two_outcome_root(tmp_path, _obj("OBJ-1", "active", valid_approval=True))
    doc = fx.load(root / ".claude" / "intent.yaml")
    doc["outcomes"][0]["how_measured"] = "a different instrument"
    fx.dump(root / ".claude" / "intent.yaml", doc)
    assert world.derive(world.load_world(root), "OBJ-1").approval_valid is True


@pytest.mark.parametrize("field", sorted(NON_HASHED_EDITS))
def test_ac_009_non_hashed_edit_keeps_validity(tmp_path: Path, field: str) -> None:
    root = _two_outcome_root(tmp_path, _obj("OBJ-1", "active", valid_approval=True))
    doc = fx.load(fx.objective_doc_path(root, "OBJ-1"))
    doc[field] = NON_HASHED_EDITS[field]
    fx.dump(fx.objective_doc_path(root, "OBJ-1"), doc)
    assert world.derive(world.load_world(root), "OBJ-1").approval_valid is True


@pytest.mark.parametrize("state", ["closed", "dropped"])
def test_ac_009_terminal_objectives_read_not_applicable(tmp_path: Path, state: str) -> None:
    root = _two_outcome_root(tmp_path, _obj("OBJ-1", state, valid_approval=True))
    doc = fx.load(fx.objective_doc_path(root, "OBJ-1"))
    doc["hypothesis"] = "edited after the fact"
    fx.dump(fx.objective_doc_path(root, "OBJ-1"), doc)
    assert world.derive(world.load_world(root), "OBJ-1").approval_valid is None


def test_ac_009_approve_records_git_identity_and_the_canonical_hash(tmp_path: Path) -> None:
    root = _two_outcome_root(tmp_path, _obj("OBJ-1", "proposed", valid_approval=False))
    world.approve(root, "OBJ-1")
    doc = fx.load(fx.objective_doc_path(root, "OBJ-1"))
    assert doc["approval"]["content_hash"] == fx.approval_hash(doc, TARGET)
    assert doc["approval"]["approved_by"] == fx.GIT_NAME
    assert doc["approval"]["approved_target"] == TARGET
    parsed = datetime.fromisoformat(doc["approval"]["approved_at"])
    assert parsed.tzinfo is not None
    assert parsed.astimezone(UTC) == parsed


def test_ac_009_canonical_json_sorts_keys_it_was_not_handed_sorted() -> None:
    """The subject's own payload literals are alphabetical, so a canonicaliser that dropped
    `sort_keys=True` would still match every fixture hash; only an out-of-order input sees it.
    List order is data (scope order is meaningful) and must survive untouched."""
    out_of_order = {"target": 10, "scope": ["b", "a"], "hypothesis": "h"}
    assert world.canonical_json(out_of_order) == '{"hypothesis":"h","scope":["b","a"],"target":10}'
    assert world.canonical_json(out_of_order) == world.canonical_json(
        dict(sorted(out_of_order.items()))
    )


def test_ac_009_approve_reads_the_name_at_the_base_root_from_a_linked_worktree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """SPEC 'Approval provenance': `approved_by` comes from the base root even when the record
    is approved inside a task worktree (the two-roots row keeps the FILES at the checkout)."""
    base = tmp_path / "base"
    _two_outcome_root(base, _obj("OBJ-1", "proposed", valid_approval=False))
    subprocess.run(["git", "-C", str(base), "add", "-A"], check=True, timeout=30)
    subprocess.run(
        ["git", "-C", str(base), "commit", "-q", "-m", "fixture"], check=True, timeout=30
    )
    wt = tmp_path / "wt"
    subprocess.run(
        ["git", "-C", str(base), "worktree", "add", "-q", str(wt), "-b", "hm/t"],
        check=True,
        timeout=30,
    )
    asked: list[Path] = []

    def _record(root: Path) -> str:
        asked.append(root.resolve())
        return fx.GIT_NAME

    monkeypatch.setattr(world, "_git_user_name", _record)
    world.approve(wt, "OBJ-1")
    assert asked == [base.resolve()]
    assert fx.load(fx.objective_doc_path(wt, "OBJ-1"))["approval"]["approved_by"] == fx.GIT_NAME


def test_ac_009_approve_with_empty_git_identity_is_refused_and_writes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Isolate git from the host's global identity (A.5 round 1): no HOME config, no system config.
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(tmp_path / "home" / "nogitconfig"))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    root = fx.build_root(
        tmp_path, git=False, objectives=[_obj("OBJ-1", "proposed", valid_approval=False)]
    )
    fx.git_init(root, name=None)
    before = fx.objective_doc_path(root, "OBJ-1").read_bytes()
    with pytest.raises(world.WorldError) as exc:
        world.approve(root, "OBJ-1")
    assert exc.value.field == "approved_by"
    assert fx.objective_doc_path(root, "OBJ-1").read_bytes() == before


# ── AC-010 ────────────────────────────────────────────────────────────────────


def test_ac_010_cap_breach_warns_on_the_same_call_that_activates(tmp_path: Path) -> None:
    root = _root(
        tmp_path,
        _obj("OBJ-1", "active", valid_approval=True),
        extra=[_obj("OBJ-2", "proposed", valid_approval=True)],
    )
    result = world.activate(root, "OBJ-2", cap=1)
    assert result.activated is True
    assert result.warning is not None
    assert result.warning.count == 2
    assert result.warning.cap == 1
    assert fx.load(fx.objective_doc_path(root, "OBJ-2"))["state"] == "active"


# ── AC-015 close half ─────────────────────────────────────────────────────────


def test_ac_015_close_persists_three_fields(tmp_path: Path) -> None:
    root = _root(tmp_path, _obj("OBJ-1", "active", valid_approval=True))
    world.close(root, "OBJ-1", observed="missed", note="target not reached")
    doc = fx.load(fx.objective_doc_path(root, "OBJ-1"))
    assert doc["state"] == "closed"
    assert doc["observed"] == "missed"
    assert doc["note"] == "target not reached"
    assert datetime.fromisoformat(doc["closed_at"]).tzinfo is not None


@pytest.mark.parametrize(
    ("observed", "note", "field"),
    [(None, "n", "observed"), ("met", "", "note"), ("success", "n", "observed")],
    ids=["observed-missing", "note-empty", "observed-invalid"],
)
def test_ac_015_refused_closes_name_the_field_and_write_nothing(
    tmp_path: Path, observed: str | None, note: str, field: str
) -> None:
    root = _root(tmp_path, _obj("OBJ-1", "active", valid_approval=True))
    before = fx.objective_doc_path(root, "OBJ-1").read_bytes()
    with pytest.raises(world.WorldError) as exc:
        world.close(root, "OBJ-1", observed=observed, note=note)
    assert exc.value.field == field
    assert fx.objective_doc_path(root, "OBJ-1").read_bytes() == before


def test_ac_015_second_close_is_refused(tmp_path: Path) -> None:
    root = _root(tmp_path, _obj("OBJ-1", "active", valid_approval=True))
    world.close(root, "OBJ-1", observed="met", note="n")
    with pytest.raises(world.WorldError):
        world.close(root, "OBJ-1", observed="missed", note="again")


# ── AC-001 objective half ─────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("mutate", "expected_field"),
    [
        (lambda d: d.__setitem__("id", "OBJ-9"), "id"),
        (lambda d: d.__setitem__("scope", []), "scope"),
        (lambda d: d.__setitem__("outcome_id", "nope"), "outcome_id"),
        (lambda d: d.__setitem__("depends_on", ["ghost"]), "depends_on[0]"),
        (
            lambda d: d.update(
                state="closed", observed=None, note="n", closed_at="2026-09-03T00:00:00Z"
            ),
            "observed",
        ),
    ],
    ids=[
        "id-vs-stem",
        "empty-scope",
        "unknown-outcome",
        "dangling-depends-on",
        "closed-null-observed",
    ],
)
def test_ac_001_objective_defect_names_its_field(
    tmp_path: Path, mutate: Any, expected_field: str
) -> None:
    root = _root(tmp_path, _obj("OBJ-1", "proposed", valid_approval=False))
    doc = fx.load(fx.objective_doc_path(root, "OBJ-1"))
    mutate(doc)
    fx.dump(fx.objective_doc_path(root, "OBJ-1"), doc)
    w = world.load_world(root)
    errors = w.broken.get("OBJ-1")
    assert errors, "a defective objective must be reported, not loaded silently"
    assert errors[0].field == expected_field
