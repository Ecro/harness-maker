"""AC-001 (assumptions half), AC-004, AC-005, AC-006 — the assumptions ledger.

Every assertion is on the RELOADED file (`world_fixture.load`), never on a return value, and
evidence / history are compared as whole ordered lists against the pre-state plus exactly the
new entry (codex R1-3 / rev-4 #13).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from harness_maker import world
from tests.unit import world_fixture as fx

E2 = {"text": "E2", "observed_at": "2026-09-05T00:00:00Z", "relation": "contradicts"}
E_SUP = {"text": "now 12", "observed_at": "2026-09-06T00:00:00Z", "relation": "supersedes"}
E_CONF = {"text": "still 12", "observed_at": "2026-09-07T00:00:00Z", "relation": "confirms"}


def _root(tmp_path: Path, **objs: Any) -> Path:
    return fx.build_root(
        tmp_path,
        assumptions=[fx.assumption(), fx.assumption("concurrent_users", claim="3 users")],
        objectives=[
            fx.objective("OBJ-ACTIVE", state="active", depends_on=["log_location"]),
            fx.objective(
                "OBJ-CLOSED",
                state="closed",
                depends_on=["log_location"],
                observed="met",
                note="done",
                closed_at="2026-09-03T00:00:00Z",
            ),
        ],
    )


def _assumption(root: Path, aid: str) -> dict[str, Any]:
    doc = fx.load(fx.assumptions_path(root))
    return next(a for a in doc["assumptions"] if a["id"] == aid)


def _tuples(a: dict[str, Any]) -> list[tuple[str, str, str]]:
    return [(e["text"], e["observed_at"], e["relation"]) for e in a["evidence"]]


# ── AC-004 ────────────────────────────────────────────────────────────────────


def test_ac_004_contradicts_yields_conflict_keeps_both_tuples_and_derives_flags(
    tmp_path: Path,
) -> None:
    root = _root(tmp_path)
    before = _assumption(root, "log_location")
    obj_bytes = {
        oid: fx.objective_doc_path(root, oid).read_bytes() for oid in ("OBJ-ACTIVE", "OBJ-CLOSED")
    }
    world.observe(
        root, "log_location", text=E2["text"], observed_at=E2["observed_at"], relation="contradicts"
    )
    after = _assumption(root, "log_location")
    assert after["status"] == "conflict"
    assert _tuples(after) == _tuples(before) + [(E2["text"], E2["observed_at"], E2["relation"])]
    assert after["claim"] == before["claim"]
    w = world.load_world(root)
    assert world.derive(w, "OBJ-ACTIVE").needs_revalidation is True
    assert world.derive(w, "OBJ-CLOSED").needs_revalidation is False
    assert {oid: fx.objective_doc_path(root, oid).read_bytes() for oid in obj_bytes} == obj_bytes


# ── AC-005 ────────────────────────────────────────────────────────────────────


def test_ac_005_supersedes_replaces_claim_appends_history_keeps_status(tmp_path: Path) -> None:
    root = _root(tmp_path)
    before = _assumption(root, "concurrent_users")
    world.observe(
        root,
        "concurrent_users",
        text=E_SUP["text"],
        observed_at=E_SUP["observed_at"],
        relation="supersedes",
        claim="12 users",
    )
    after = _assumption(root, "concurrent_users")
    assert after["claim"] == "12 users"
    assert after["history"] == before["history"] + [before["claim"]]
    assert _tuples(after) == _tuples(before) + [(E_SUP["text"], E_SUP["observed_at"], "supersedes")]
    assert after["status"] == before["status"]


def test_ac_005_confirms_appends_evidence_only(tmp_path: Path) -> None:
    root = _root(tmp_path)
    before = _assumption(root, "concurrent_users")
    world.observe(
        root,
        "concurrent_users",
        text=E_CONF["text"],
        observed_at=E_CONF["observed_at"],
        relation="confirms",
    )
    after = _assumption(root, "concurrent_users")
    assert after["claim"] == before["claim"]
    assert after["history"] == before["history"]
    assert _tuples(after) == _tuples(before) + [(E_CONF["text"], E_CONF["observed_at"], "confirms")]
    assert after["status"] == before["status"]


def test_ac_005_supersedes_without_a_claim_is_refused_by_field(tmp_path: Path) -> None:
    root = _root(tmp_path)
    with pytest.raises(world.WorldError) as exc:
        world.observe(
            root,
            "concurrent_users",
            text="x",
            observed_at="2026-09-06T00:00:00Z",
            relation="supersedes",
        )
    assert exc.value.field == "claim"


# ── AC-006 ────────────────────────────────────────────────────────────────────


def test_ac_006_resolve_is_the_only_exit_from_conflict(tmp_path: Path) -> None:
    root = _root(tmp_path)
    world.observe(
        root, "log_location", text=E2["text"], observed_at=E2["observed_at"], relation="contradicts"
    )
    before = _assumption(root, "log_location")
    world.resolve(root, "log_location", status="assumed", claim="logs live in /srv/log")
    after = _assumption(root, "log_location")
    assert after["status"] == "assumed"
    assert after["claim"] == "logs live in /srv/log"
    assert after["history"] == before["history"] + [before["claim"]]
    assert _tuples(after) == _tuples(before)
    assert world.derive(world.load_world(root), "OBJ-ACTIVE").needs_revalidation is False


@pytest.mark.parametrize(
    ("aid", "status"),
    [("log_location", "conflict"), ("concurrent_users", "assumed")],
    ids=["resolve-to-conflict", "resolve-a-non-conflict"],
)
def test_ac_006_refused_resolves_write_nothing(tmp_path: Path, aid: str, status: str) -> None:
    root = _root(tmp_path)
    if aid == "log_location":
        world.observe(
            root, aid, text=E2["text"], observed_at=E2["observed_at"], relation="contradicts"
        )
    before = fx.assumptions_path(root).read_bytes()
    with pytest.raises(world.WorldError):
        world.resolve(root, aid, status=status, claim="new claim")
    assert fx.assumptions_path(root).read_bytes() == before


# ── AC-001 assumptions half ───────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("mutate", "expected_field"),
    [
        (lambda d: d["assumptions"].append(fx.assumption("log_location")), "assumptions[].id"),
        (lambda d: d.pop("assumptions"), "assumptions"),
        (lambda d: d["assumptions"][0].__setitem__("claim", None), "assumptions[0].claim"),
        (lambda d: d["assumptions"][0].__setitem__("claim", ""), "assumptions[0].claim"),
        (lambda d: d["assumptions"][0].__setitem__("evidence", "E1"), "assumptions[0].evidence"),
        (
            lambda d: d["assumptions"][0]["evidence"][0].pop("relation"),
            "assumptions[0].evidence[0].relation",
        ),
        (lambda d: d["assumptions"][0].__setitem__("history", [3]), "assumptions[0].history[0]"),
        (lambda d: d["assumptions"][0].__setitem__("colour", "blue"), "assumptions[0].colour"),
    ],
    ids=[
        "duplicate-id",
        "missing-envelope-key",
        "null-claim",
        "empty-claim",
        "non-list-evidence",
        "evidence-missing-relation",
        "non-string-history",
        "unknown-key",
    ],
)
def test_ac_001_assumptions_defect_names_its_field(
    tmp_path: Path, mutate: Any, expected_field: str
) -> None:
    root = _root(tmp_path)
    doc = fx.load(fx.assumptions_path(root))
    mutate(doc)
    fx.dump(fx.assumptions_path(root), doc)
    errors = world.validate_assumptions(fx.assumptions_path(root))
    assert errors
    assert errors[0].field == expected_field
