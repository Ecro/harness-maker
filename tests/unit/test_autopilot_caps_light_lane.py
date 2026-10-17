"""SPEC-hm-light-lane-s3a AC-003..006 and AC-013 — execute's boundary skips review and verify.

The oracle for every non-skip path is the e7dd6648 module itself: `capture_e7dd6648.py.txt`
ran `hm autopilot_caps boundary` on fixtures built by `light_lane_s3a_fixture` before the edit,
and AC-004 rebuilds the same fixtures for the new module and compares the masked observations.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from harness_maker import autopilot, autopilot_ledger
from harness_maker.observability import verification_cache
from tests.unit import light_lane_s3a_fixture as fx

GOLDENS = Path(__file__).parents[1] / "fixtures" / "light_lane_s3a"
BOUNDARY = json.loads((GOLDENS / "boundary_e7dd6648.json").read_text(encoding="utf-8"))
RENDERS = json.loads((GOLDENS / "renders_e7dd6648.json").read_text(encoding="utf-8"))
_VERIFY_ORACLE = BOUNDARY["cases"]["light+passed/verify/auto_full/absent/default"]["observation"]
#: The key set of `_cmd_boundary`'s output at e7dd6648.
E7DD_KEYS = frozenset(_VERIFY_ORACLE["json"])
E7DD_EVENTS = frozenset(RENDERS["events"])


@pytest.fixture(autouse=True)
def _isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(home / "no-global"))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("HARNESS_MAKER_CACHE_DIR", str(home / "cache"))
    monkeypatch.delenv("HM_SESSION_ID", raising=False)
    # Tool versions are part of the cache key; pinning them keeps each case to git calls only.
    monkeypatch.setattr(verification_cache, "_tool_versions", lambda root: {})


def _run(tmp_path: Path, case: fx.Case) -> tuple[Path, dict[str, Any], list[dict[str, Any]]]:
    root = tmp_path / "repo"
    argv = fx.build(root, case)
    before = len(_rows(root))
    obs = fx.observe(root, argv)
    return root, obs, obs["rows"][before:]


def _rows(root: Path) -> list[dict[str, Any]]:
    path = autopilot_ledger.ledger_path(root)
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def test_light_execute_skips_review_and_verify(tmp_path: Path) -> None:
    root, obs, new_rows = _run(tmp_path, fx.Case("light", "passed", "execute", "auto_full"))
    out = obs["json"]
    assert out["proceed"] is False
    assert out["halt_kind"] == "merge_gate"
    assert out["next_stage"] == "wrapup"
    assert set(out) == E7DD_KEYS
    assert "review" in out["reason"]
    assert "verify" in out["reason"]
    assert [r["event"] for r in new_rows] == ["advance_entered", "stage_skipped", "gate_blocked"]
    skipped = new_rows[1]
    assert skipped["skipped"] == ["review", "verify"]
    assert skipped["from"] == "execute"
    assert skipped["to"] == "wrapup"
    assert skipped["reason"] == "lane light"
    assert new_rows[2]["stage"] == "wrapup"
    assert obs["marker"] is None
    assert not autopilot.marker_path(root, session_id=None).exists()
    # Same halt as verify's own boundary at e7dd6648, apart from the reason naming the skip.
    oracle = dict(_VERIFY_ORACLE["json"])
    assert {k: v for k, v in out.items() if k not in ("reason", "steps")} == {
        k: v for k, v in oracle.items() if k not in ("reason", "steps")
    }


_CASES = fx.ac004_cases()


@pytest.mark.parametrize("case", _CASES, ids=[c.key for c in _CASES])
def test_full_lane_boundary_matches_e7dd6648(tmp_path: Path, case: fx.Case) -> None:
    golden = BOUNDARY["cases"][case.key]
    _root, obs, _new = _run(tmp_path, case)
    if "observation" in golden:
        assert obs == golden["observation"]
    assert fx.observation_sha(obs) == golden["sha256"], json.dumps(obs)[:2000]


def test_ac004_domain_is_the_captured_one() -> None:
    keys = [c.key for c in _CASES]
    assert len(set(keys)) == len(keys)
    assert sorted(keys) == sorted(BOUNDARY["cases"])


@pytest.mark.parametrize(
    ("pipeline", "current", "gate", "expected"),
    [
        (
            "custom",
            "execute",
            None,
            {"next_stage": "wrapup", "halt_kind": "merge_gate", "skipped": ["verify"]},
        ),
        (
            "no_wrapup",
            "execute",
            None,
            {
                "pipeline_complete": True,
                "marker": None,
                "skipped": ["review", "verify"],
                "to": None,
            },
        ),
        # A narrowed marker is a human asking for the stages it lists (review item M).
        (
            "narrowed_review",
            "execute",
            None,
            {"next_stage": "review", "proceed": True, "skipped": None},
        ),
        ("from_spec", "spec", "clear", {"next_stage": "execute", "proceed": True, "skipped": None}),
    ],
    ids=["execute-verify-wrapup", "ends-at-verify", "narrowed-to-review", "spec-stage"],
)
def test_skip_respects_pipeline_shape(
    tmp_path: Path, pipeline: str, current: str, gate: str | None, expected: dict[str, Any]
) -> None:
    root, obs, new_rows = _run(
        tmp_path, fx.Case("light", "passed", current, "auto_safe", gate, pipeline)
    )
    out = obs["json"]
    skipped_rows = [r for r in new_rows if r["event"] == "stage_skipped"]
    for key in ("next_stage", "halt_kind", "pipeline_complete", "narrow_end", "proceed"):
        if key in expected:
            assert out[key] == expected[key], key
    if "marker" in expected:
        assert obs["marker"] is None
    if expected["skipped"] is None:
        assert skipped_rows == []
        return
    assert len(skipped_rows) == 1
    assert skipped_rows[0]["skipped"] == expected["skipped"]
    if "to" in expected:
        assert skipped_rows[0]["to"] is expected["to"]
    if pipeline == "narrowed_review":
        marker = autopilot.load(root, session_id=None)
        assert marker is not None
        assert marker.restore_pipeline is not None


@pytest.mark.parametrize(
    ("lane", "record"),
    [
        ("light", "none"),
        ("light", "real_beside"),
        ("light", "failed"),
        ("light", "other_slug"),
        ("light", "tree_changed"),
        ("light", "stale_since"),
        ("light", "no_computed_at"),
        ("light", "bad_computed_at"),
        ("untrusted", "passed"),
        # AC-016: the record's own drift, checks, tree binding and timestamps.
        ("light", "drift_scope"),
        ("light", "drift_scenario"),
        ("light", "nested_slug"),
        ("light", "regression_fail"),
        ("light", "security_fail"),
        ("light", "mechanical_fail"),
        ("light", "spec_requirement_fail"),
        ("light", "other_key"),
        ("light", "no_key"),
        ("light", "naive_computed_at"),
        ("light", "date_only"),
        ("light", "second_before"),
    ],
)
def test_no_passing_record_no_skip(tmp_path: Path, lane: str, record: str) -> None:
    _root, obs, new_rows = _run(tmp_path, fx.Case(lane, record, "execute", "auto_safe"))
    out = obs["json"]
    assert out["next_stage"] == "review"
    assert out["proceed"] is True
    assert "stage_skipped" not in [r["event"] for r in new_rows]


def test_stage_skipped_is_a_ledger_event(tmp_path: Path) -> None:
    assert "stage_skipped" in autopilot_ledger.EVENTS
    assert {"stage_skipped"} == autopilot_ledger.EVENTS - E7DD_EVENTS
    root = tmp_path / "repo"
    fx.init_repo(root)
    t0 = "2000-01-01T00:00:00+00:00"
    autopilot_ledger.append_event(root, event="advance_entered", fields={"to": "execute"})
    entries_before = autopilot_ledger.count_entries(root, since=t0)
    total_before = autopilot_ledger._total_entries(root)
    autopilot_ledger.append_event(
        root,
        event="stage_skipped",
        fields={
            "from": "execute",
            "skipped": ["review", "verify"],
            "to": "wrapup",
            "reason": "lane light",
        },
    )
    assert autopilot_ledger.count_entries(root, since=t0) == entries_before
    assert autopilot_ledger._total_entries(root) == total_before + 1


# ── AC-016: the skip is bound to the checked tree and the record's own checks ────────────


def _no_skip(obs: dict[str, Any], new_rows: list[dict[str, Any]]) -> None:
    assert obs["json"]["next_stage"] == "review"
    assert obs["json"]["proceed"] is True
    assert "stage_skipped" not in [r["event"] for r in new_rows]


def test_computed_at_equal_to_since_skips(tmp_path: Path) -> None:
    _root, obs, new_rows = _run(tmp_path, fx.Case("light", "at_since", "execute", "auto_full"))
    assert obs["json"]["next_stage"] == "wrapup"
    assert "stage_skipped" in [r["event"] for r in new_rows]


def test_probe_b_a_later_failed_run_does_not_skip(tmp_path: Path) -> None:
    """Run 1 passes and writes its record; the code changes; run 2 passes Check 2 (a fresh
    `run` marker for the new tree) but fails security, so it writes no record. The run 1 record
    must not be read as a pass for the new tree at the boundary."""
    root = tmp_path / "repo"
    argv = fx.build(root, fx.Case("light", "passed", "execute", "auto_safe"))
    fx.change_tree(root)
    fx.mark_fresh(root)
    before = len(_rows(root))
    obs = fx.observe(root, argv)
    _no_skip(obs, obs["rows"][before:])
    # The digest half left with the review stage (SPEC-maker-advance IRR-002): any REVIEW record
    # now means wrapup, whose `hm check` re-runs the gates on the new tree.


def test_a_mark_pass_marker_does_not_skip(tmp_path: Path) -> None:
    """A `mark-pass` marker records that someone said the suite passed; only `run`'s counts."""
    root = tmp_path / "repo"
    argv = fx.build(root, fx.Case("light", "passed", "execute", "auto_safe"))
    fx.mark_fresh(root, writer=None)
    before = len(_rows(root))
    obs = fx.observe(root, argv)
    _no_skip(obs, obs["rows"][before:])


def test_no_stage_skipped_row_before_an_objective_halt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "repo"
    argv = fx.build(root, fx.Case("light", "passed", "execute", "auto_safe", None, "then_spec"))
    (root / "work-docs" / f"PLAN-{fx.SLUG}.md").write_text(
        "---\ntype: plan\nobjective: OBJ-NOPE\n---\n", encoding="utf-8"
    )
    monkeypatch.chdir(root)
    before = len(_rows(root))
    obs = fx.observe(root, argv)
    new_rows = obs["rows"][before:]
    assert obs["json"]["halt_kind"] == "objective_gate"
    assert "stage_skipped" not in [r["event"] for r in new_rows]
    assert "lane light" not in obs["json"]["reason"]
