"""AC-011 (CLI half), AC-014, and the deferred `hm world status` clauses of AC-002.

Every clause runs the SHIPPED entrypoint (`hm world …`) as a subprocess and parses stdout —
never the module function — because the defects this repo keeps finding live in the seam
between a tested library and the prose that calls it. The fixture is the one AC-014 names:
one lower-is-better outcome recorded under a stale definition, one higher-is-better outcome
below target, one active objective edited after approval and depending on a conflicted
assumption, a known unknowns list, and one objective whose revisit condition holds.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from harness_maker import intent, world
from tests.unit import world_fixture as fx

UNKNOWNS = ["whether users read the dashboard"]


def _fixture_root(tmp_path: Path) -> Path:
    onboarding = fx.outcome("onboarding_minutes", target=10, higher_is_better=False)
    success = fx.outcome("success_rate", target=90, higher_is_better=True)
    root = fx.build_root(
        tmp_path,
        intent=fx.intent_doc(onboarding, success, unknowns=UNKNOWNS),
        assumptions=[
            fx.assumption("log_location", status="known"),
            fx.assumption("second", claim="c", status="assumed"),
        ],
        objectives=[
            fx.approved(fx.objective("OBJ-1", state="active", depends_on=["log_location"]), 10),
            fx.approved(
                fx.objective(
                    "OBJ-3",
                    state="active",
                    outcome_id="success_rate",
                    rejected=["ship without a dashboard"],
                    revisit_when={"outcome": "success_rate", "op": "<", "value": 80},
                ),
                90,
            ),
        ],
    )
    # stale definition: the value was recorded under a different how_measured
    stale_hash = fx.definition_hash(fx.outcome("onboarding_minutes", how_measured="old"))
    fx.dump(
        fx.outcomes_path(root),
        {
            "schema_version": 1,
            "values": [
                {
                    "outcome_id": "onboarding_minutes",
                    "value": 17,
                    "observed_at": "2026-09-10T00:00:00Z",
                    "evidence": "e",
                    "definition_hash": stale_hash,
                },
                {
                    "outcome_id": "success_rate",
                    "value": 70,
                    "observed_at": "2026-09-11T00:00:00Z",
                    "evidence": "e",
                    "definition_hash": fx.definition_hash(success),
                },
            ],
        },
    )
    # OBJ-1 edited after approval → approval_valid False; its assumption in conflict → flag True
    doc = fx.load(fx.objective_doc_path(root, "OBJ-1"))
    doc["hypothesis"] = "edited afterwards"
    fx.dump(fx.objective_doc_path(root, "OBJ-1"), doc)
    world.observe(
        root, "log_location", text="E2", observed_at="2026-09-12T00:00:00Z", relation="contradicts"
    )
    return root


def _tree_hash(root: Path) -> str:
    h = hashlib.sha256()
    for p in sorted((root / ".claude").rglob("*")):
        if p.is_file():
            h.update(str(p.relative_to(root)).encode())
            h.update(p.read_bytes())
    return h.hexdigest()


# ── AC-014 ────────────────────────────────────────────────────────────────────


def test_ac_014_status_prints_the_fixture_values_reaches_no_llm_writes_nothing(
    tmp_path: Path,
) -> None:
    root = _fixture_root(tmp_path)
    before = _tree_hash(root)
    proc = fx.run_cli(["status", "--json"], cwd=root)
    assert proc.returncode == 0, proc.stderr
    out = fx.stdout_json(proc)
    assert out["mission"] == "ship it"
    assert out["outcomes"]["onboarding_minutes"] == {
        "last": 17,
        "target": 10,
        "observed_at": "2026-09-10T00:00:00Z",
        "gap": "unevaluable",
        "stale_definition": True,
    }
    assert out["outcomes"]["success_rate"]["gap"] == "below_target"
    assert out["active"]["OBJ-1"] == {"approval_valid": False, "needs_revalidation": True}
    assert out["unknowns"] == UNKNOWNS
    assert out["conflicts"] == ["log_location"]
    assert out["fired_revisits"] == ["OBJ-3"]
    assert _tree_hash(root) == before


def test_ac_014_status_on_the_skeleton_prints_not_filled_in(tmp_path: Path) -> None:
    root = tmp_path
    intent.write_skeleton_if_absent(root / ".claude" / "intent.yaml")
    out = fx.stdout_json(fx.run_cli(["status", "--json"], cwd=root))
    assert out["state"] == "not_filled_in"


def test_ac_002_status_on_a_half_filled_intent_names_mission(tmp_path: Path) -> None:
    root = tmp_path
    fx.dump(root / ".claude" / "intent.yaml", fx.intent_doc(fx.outcome(), mission=""))
    out = fx.stdout_json(fx.run_cli(["status", "--json"], cwd=root))
    assert out["error"]["field"] == "mission"


_LLM_MARKERS = ("anthropic", "openai", "llm_judge", "codex_client")


def test_ac_014_world_entrypoints_reach_no_llm_client() -> None:
    """Import-graph walk in a FRESH interpreter (A.5 round 1: an in-process sys.modules diff
    is always empty once collection has imported `harness_maker.world`)."""
    code = (
        "import json, sys; import harness_maker.world as w; "
        "assert {'status','assume','outcome','objective'} <= set(w.SUBCOMMANDS); "
        "print(json.dumps(sorted(sys.modules)))"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, timeout=120, check=True
    )
    loaded = json.loads(proc.stdout.strip().splitlines()[-1])
    assert "harness_maker.world" in loaded
    reached = {m for m in loaded if any(marker in m.lower() for marker in _LLM_MARKERS)}
    assert not reached, reached


# ── AC-011 CLI half ───────────────────────────────────────────────────────────


def test_ac_011_revisit_prints_the_record_condition_and_last_value(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path)
    out = fx.stdout_json(fx.run_cli(["objective", "revisit", "OBJ-3", "--json"], cwd=root))
    assert out == {
        "objective": "OBJ-3",
        "title": "OBJ-3 title",
        "condition": {"outcome": "success_rate", "op": "<", "value": 80},
        "last_value": 70,
        "result": "candidate",
        "blocked": False,
    }


@pytest.mark.parametrize(
    ("revisit_when", "setup", "expected"),
    [
        ({"outcome": "success_rate", "op": ">=", "value": 80}, None, "not_met"),
        (
            {"outcome": "onboarding_minutes", "op": "<", "value": 100},
            None,
            "unevaluable",
        ),  # stale definition
        (
            {"outcome": "never_recorded", "op": "<", "value": 1},
            "add_outcome",
            "unevaluable",
        ),  # no value
        ({"assumption": "log_location", "status": "known"}, None, "unevaluable"),  # in conflict
        ({"assumption": "ghost", "status": "known"}, None, "unevaluable"),  # dangling
        ({"assumption": "second", "status": "assumed"}, None, "candidate"),
    ],
    ids=["unmet", "stale", "no-value", "conflict", "dangling", "assumption-met"],
)
def test_ac_011_three_results_and_four_unevaluable_causes_never_block(
    tmp_path: Path, revisit_when: dict[str, Any], setup: str | None, expected: str
) -> None:
    root = _fixture_root(tmp_path)
    if setup == "add_outcome":
        doc = fx.load(root / ".claude" / "intent.yaml")
        doc["outcomes"].append(fx.outcome("never_recorded"))
        fx.dump(root / ".claude" / "intent.yaml", doc)
    obj = fx.load(fx.objective_doc_path(root, "OBJ-3"))
    obj["revisit_when"] = revisit_when
    fx.dump(fx.objective_doc_path(root, "OBJ-3"), obj)
    out = fx.stdout_json(fx.run_cli(["objective", "revisit", "OBJ-3", "--json"], cwd=root))
    assert out["result"] == expected
    assert out["blocked"] is False
