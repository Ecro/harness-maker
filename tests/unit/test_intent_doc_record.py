"""AC-001, AC-002, AC-003, AC-010 — `work-docs/INTENT-<ID>.md` IS the objective record.

The INTENT files here are written by a local helper, never by the subject's own writer, so the
loader is judged against an independently produced file. AC-001's differential half compares the
loader's error list to the rule set applied directly; its three named cases (good file under the
bare id / `id` field disagreeing with the stem / a stem without the prefix) are independent
expectations that do not share the id-extraction rule with the subject (validator critical #1).

Hypothesis profile contract (spec-tetrad ADR-002): `ci` = reproducible gate, `dev` = broader
local bug-finding, selected by HYPOTHESIS_PROFILE (default ci).
"""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import yaml
from hypothesis import given, settings
from hypothesis import strategies as st

from harness_maker import world
from tests.unit import world_fixture as fx

settings.register_profile("ci", derandomize=True, max_examples=40, deadline=None)
settings.register_profile("dev", max_examples=200, deadline=None)
settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "ci"))

TARGET = 10
BODY = b"## Problem\n\nwhy\n\n## Proposed outcome\n\nwhat\n"


def _write_intent(root: Path, rec: dict[str, Any], body: bytes, *, stem: str | None = None) -> Path:
    """Independent writer: frontmatter via yaml, fences, body bytes appended verbatim."""
    path = root / "work-docs" / f"{stem or 'INTENT-' + rec['id']}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    fm = yaml.safe_dump(rec, sort_keys=False, allow_unicode=True).encode("utf-8")
    path.write_bytes(b"---\n" + fm + b"---\n" + body)
    return path


def _body_of(path: Path) -> bytes:
    data = path.read_bytes()
    if data.startswith(b"\xef\xbb\xbf"):
        data = data[3:]
    assert data.startswith(b"---")
    end = data.index(b"\n---", 3)
    nl = data.index(b"\n", end + 1)
    return data[nl + 1 :]


def _root(tmp_path: Path, *objs: dict[str, Any], body: bytes = BODY) -> Path:
    root = fx.build_root(tmp_path, assumptions=[fx.assumption()], objectives=[])
    for obj in objs:
        _write_intent(root, obj, body)
    return root


# ── AC-001 ────────────────────────────────────────────────────────────────────


def test_ac_001_a_good_file_loads_under_the_bare_id(tmp_path: Path) -> None:
    rec = fx.objective("OBJ-1")
    root = _root(tmp_path, rec)
    w = world.load_world(root)
    assert "OBJ-1" in w.objectives
    assert "INTENT-OBJ-1" not in w.objectives
    assert w.objectives["OBJ-1"] == rec
    assert w.bodies["OBJ-1"] == BODY
    assert w.broken == {}


def test_ac_001_an_id_field_disagreeing_with_the_stem_is_broken(tmp_path: Path) -> None:
    rec = fx.objective("OBJ-2")
    root = fx.build_root(tmp_path, assumptions=[fx.assumption()], objectives=[])
    _write_intent(root, rec, BODY, stem="INTENT-OBJ-9")
    w = world.load_world(root)
    assert "OBJ-9" in w.broken
    assert "OBJ-9" not in w.objectives
    assert any(e.field == "id" for e in w.broken["OBJ-9"])


def test_ac_001_a_stem_without_the_prefix_is_never_a_record(tmp_path: Path) -> None:
    """Negative invariant — passes against the pre-change loader, which reads no INTENT file at
    all. It goes red the moment a loader keys records by the raw stem, and its RED positive
    sibling `test_ac_001_a_good_file_loads_under_the_bare_id` forces that loader into existence
    (Phase A.4 justification, case 2)."""
    rec = fx.objective("OBJ-3")
    root = fx.build_root(tmp_path, assumptions=[fx.assumption()], objectives=[])
    _write_intent(root, rec, BODY, stem="OBJ-3")
    w = world.load_world(root)
    assert "OBJ-3" not in w.objectives
    assert "OBJ-3" not in w.broken


@pytest.mark.parametrize(
    ("mutate", "field"),
    [
        (lambda r: r.__setitem__("scope", [42]), "scope"),
        (lambda r: r.__setitem__("hypothesis", None), "hypothesis"),
        (lambda r: r.__setitem__("outcome_id", "ghost"), "outcome_id"),
        (lambda r: r.pop("title"), "title"),
    ],
)
def test_ac_001_intent_frontmatter_loads_under_the_disk_rules(
    tmp_path: Path, mutate: Callable[[dict[str, Any]], Any], field: str
) -> None:
    """Differential half: the loader's error list equals the rule set applied to the mapping."""
    rec = fx.objective("OBJ-1")
    mutate(rec)
    root = _root(tmp_path, rec)
    w = world.load_world(root)
    path = world.objective_doc_path(root, "OBJ-1")
    expected = world._validate_objective_raw(
        path, rec, intent_outcomes=w.outcome_by_id, assumption_ids=set(w.assumptions)
    )
    assert w.broken["OBJ-1"] == expected
    assert any(e.field == field for e in w.broken["OBJ-1"])


@pytest.mark.parametrize(
    "data",
    [
        b"# no frontmatter at all\n",
        b"---\nid: OBJ-1\nunterminated\n",
        b"---\n- a\n- b\n---\nbody\n",
        b"---\n: : [\n---\nbody\n",
    ],
    ids=["missing", "unterminated", "non_mapping", "invalid_yaml"],
)
def test_ac_001_missing_or_non_mapping_frontmatter_is_a_file_error(
    tmp_path: Path, data: bytes
) -> None:
    root = fx.build_root(tmp_path, assumptions=[fx.assumption()], objectives=[])
    (root / "work-docs").mkdir(exist_ok=True)
    (root / "work-docs" / "INTENT-OBJ-1.md").write_bytes(data)
    w = world.load_world(root)
    assert "OBJ-1" in w.broken
    assert [e.field for e in w.broken["OBJ-1"]] == ["file"]


def test_ac_001_an_empty_frontmatter_reports_the_required_keys(tmp_path: Path) -> None:
    root = fx.build_root(tmp_path, assumptions=[fx.assumption()], objectives=[])
    (root / "work-docs").mkdir(exist_ok=True)
    (root / "work-docs" / "INTENT-OBJ-1.md").write_bytes(b"---\n---\nbody\n")
    w = world.load_world(root)
    fields = {e.field for e in w.broken["OBJ-1"]}
    assert "file" not in fields
    assert {"title", "hypothesis", "scope", "outcome_id", "state"} <= fields


# ── AC-002 ────────────────────────────────────────────────────────────────────

_WRITERS: dict[str, Callable[[Path], Any]] = {
    "approve": lambda root: world.approve(root, "OBJ-1"),
    "activate": lambda root: world.activate(root, "OBJ-1"),
    "drop": lambda root: world.transition(root, "OBJ-1", "dropped"),
    "close": lambda root: world.close(root, "OBJ-1", observed="met", note="done"),
    "reopen": lambda root: world.transition(root, "OBJ-1", "proposed"),
    "edit": lambda root: world.edit_objective(root, "OBJ-1", title="renamed"),
}
_STATE_FOR: dict[str, str] = {
    "approve": "proposed",
    "activate": "proposed",
    "drop": "active",
    "close": "active",
    "reopen": "dropped",
    "edit": "active",
}


def _record_for(writer: str) -> dict[str, Any]:
    rec = fx.objective("OBJ-1", state=_STATE_FOR[writer])
    if writer in ("activate", "drop", "close", "reopen", "edit"):
        rec = fx.approved(rec, TARGET)
    return rec


_BODIES = st.one_of(
    st.just(b""),
    st.just(b"## Problem\r\n\r\nCRLF body\r\n"),
    st.just(b"trailing   \n\n\n"),
    st.just(b"---\nlooks: like frontmatter\n---\n"),
    st.just("한글 본문\n".encode()),
    st.text().map(lambda s: s.encode("utf-8")),
)


@given(body=_BODIES, writer=st.sampled_from(sorted(_WRITERS)))
def test_ac_002_every_writer_preserves_the_body_bytes(
    tmp_path_factory: pytest.TempPathFactory, body: bytes, writer: str
) -> None:
    root = fx.build_root(tmp_path_factory.mktemp("w"), assumptions=[fx.assumption()])
    path = _write_intent(root, _record_for(writer), body)
    _WRITERS[writer](root)
    assert _body_of(path) == body


@pytest.mark.parametrize("writer", sorted(_WRITERS))
def test_ac_002_a_crlf_bom_file_on_disk_survives_every_writer(tmp_path: Path, writer: str) -> None:
    root = fx.build_root(tmp_path, assumptions=[fx.assumption()])
    rec = _record_for(writer)
    fm = yaml.safe_dump(rec, sort_keys=False).replace("\n", "\r\n").encode("utf-8")
    body = b"## Problem\r\n\r\nkeep me\r\n"
    path = root / "work-docs" / "INTENT-OBJ-1.md"
    path.parent.mkdir(exist_ok=True)
    path.write_bytes(b"\xef\xbb\xbf---\r\n" + fm + b"---\r\n" + body)
    _WRITERS[writer](root)
    assert path.read_bytes().endswith(body)
    assert world.load_world(root).objectives["OBJ-1"]["id"] == "OBJ-1"


def test_ac_002_a_repeated_no_op_write_is_byte_identical(tmp_path: Path) -> None:
    root = fx.build_root(tmp_path, assumptions=[fx.assumption()])
    path = _write_intent(root, fx.approved(fx.objective("OBJ-1", state="active"), TARGET), BODY)
    world.edit_objective(root, "OBJ-1", title="renamed")
    first = path.read_bytes()
    world.edit_objective(root, "OBJ-1", title="renamed")
    assert path.read_bytes() == first


def test_ac_002_the_dump_key_order_covers_every_declared_key_exactly(tmp_path: Path) -> None:
    """ADR-011: one ordered source for membership and order; an unknown key is refused."""
    assert isinstance(world._OBJECTIVE_OPTIONAL, tuple)
    assert set(world._OBJECTIVE_REQUIRED) | set(world._OBJECTIVE_OPTIONAL) == set(
        world._OBJECTIVE_KEYS
    )
    root = fx.build_root(tmp_path, assumptions=[fx.assumption()])
    path = _write_intent(root, fx.objective("OBJ-1"), BODY)
    world.approve(root, "OBJ-1")
    keys = list(yaml.safe_load(path.read_bytes().split(b"---\n")[1]).keys())
    declared = [*world._OBJECTIVE_REQUIRED, *world._OBJECTIVE_OPTIONAL]
    assert keys == [k for k in declared if k in keys]
    with pytest.raises(world.WorldError):
        world._dump_intent(path, {**fx.objective("OBJ-1"), "bogus": 1}, BODY)


def test_ac_002_a_writer_refuses_to_write_when_the_body_is_unknown(tmp_path: Path) -> None:
    """ADR-002: never write an empty body on a `bodies` miss."""
    root = fx.build_root(tmp_path, assumptions=[fx.assumption()])
    path = _write_intent(root, fx.objective("OBJ-1"), BODY)
    w = world.load_world(root)
    del w.bodies["OBJ-1"]
    with pytest.raises(world.WorldError) as exc:
        world._write_record(w, root, "OBJ-1", w.objectives["OBJ-1"])
    assert exc.value.field == "body"
    assert path.read_bytes().endswith(BODY)


# ── AC-003 ────────────────────────────────────────────────────────────────────


@given(edit=st.text(min_size=1).map(lambda s: s.encode("utf-8")))
def test_ac_003_prose_edits_keep_approval_hashed_edits_break_it(
    tmp_path_factory: pytest.TempPathFactory, edit: bytes
) -> None:
    root = fx.build_root(tmp_path_factory.mktemp("h"), assumptions=[fx.assumption()])
    rec = fx.approved(fx.objective("OBJ-1", state="active"), TARGET)
    path = _write_intent(root, rec, BODY)
    assert world.derive(world.load_world(root), "OBJ-1").approval_valid is True
    path.write_bytes(path.read_bytes() + edit)
    assert world.derive(world.load_world(root), "OBJ-1").approval_valid is True


@pytest.mark.parametrize("field", ["hypothesis", "scope", "non_scope", "outcome_id", "target"])
def test_ac_003_a_hashed_frontmatter_edit_reads_false_and_writes_nothing(
    tmp_path: Path, field: str
) -> None:
    """`target` lives in intent.yaml, not the record — the fifth hashed input (S3 Then)."""
    root = fx.build_root(
        tmp_path,
        assumptions=[fx.assumption()],
        intent=fx.intent_doc(fx.outcome(), fx.outcome("o2")),
    )
    rec = fx.approved(fx.objective("OBJ-1", state="active"), TARGET)
    path = _write_intent(root, rec, BODY)
    if field == "target":
        fx.dump(
            root / ".claude" / "intent.yaml", fx.intent_doc(fx.outcome(target=11), fx.outcome("o2"))
        )
    else:
        rec[field] = (
            "o2" if field == "outcome_id" else (["edited"] if field != "hypothesis" else "edited")
        )
        _write_intent(root, rec, BODY)
    before = path.read_bytes()
    assert world.derive(world.load_world(root), "OBJ-1").approval_valid is False
    assert path.read_bytes() == before


# ── AC-010 ────────────────────────────────────────────────────────────────────


def test_ac_010_legacy_objective_path_is_diagnosed(tmp_path: Path) -> None:
    root = fx.build_root(tmp_path, assumptions=[fx.assumption()])
    legacy = root / ".claude" / "world" / "objectives" / "OBJ-7.yaml"
    legacy.parent.mkdir(parents=True, exist_ok=True)
    legacy.write_text(yaml.safe_dump(fx.objective("OBJ-7")), encoding="utf-8")
    w = world.load_world(root)
    assert "OBJ-7" not in w.objectives
    assert "OBJ-7" not in w.broken
    hits = [e for e in w.errors if ".claude/world/objectives/OBJ-7.yaml" in e.message]
    assert len(hits) == 1
    assert "work-docs/INTENT-OBJ-7.md" in hits[0].message
