"""AC-012 — the boundary entrypoint reads the PLAN link from the current checkout, every
existing gate is byte-identical to the Phase 0 baseline, and `objective_gate` only ever
replaces an `advance`.

Differential oracle: `tests/fixtures/autopilot_caps_baseline.json`, captured from the
pre-change module. Every call goes through the shipped `boundary` entrypoint with only a
slug and a cwd — no test passes an objective in (the signature clause pins that).

Passing-before-the-change justification (Phase A.4): the baseline-equality cells
(`test_ac_012_absent_and_approved_links_equal_the_baseline`, all 231) and the "baseline halts"
cells of `test_ac_012_failing_links_only_replace_an_advance` (424 of 616) are NEGATIVE
invariants — they pin that nothing moves; the RED positive siblings are the 192 cells where the
baseline advances and `objective_gate` must appear, in the same parametrised function.
"""

from __future__ import annotations

import datetime as dt
import inspect
import io
import json
import subprocess
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any

import pytest
import yaml

from harness_maker import autopilot, autopilot_caps
from harness_maker.models import AtomicStage
from tests.unit import world_fixture as fx

_FIXTURE = Path(__file__).parents[1] / "fixtures" / "autopilot_caps_baseline.json"
_BASELINE = json.loads(_FIXTURE.read_text(encoding="utf-8"))
_STAGES: list[str] = _BASELINE["stages"]
_KEEP = ("proceed", "halt_kind", "next_stage", "pipeline_complete", "judgment_auto_answered")
_PIPELINE = [AtomicStage(s) for s in _STAGES]
SLUG = "task-a"

#: Restated from the generator (kept in sync by the equality assertion below).
INPUTS: dict[str, tuple[bool, str, list[str]]] = {
    "armed": (True, "auto_safe", ["--step-cap", "20", "--time-cap-min", "300"]),
    "no_marker": (False, "auto_safe", ["--step-cap", "20", "--time-cap-min", "300"]),
    "step_cap": (True, "auto_safe", ["--step-cap", "0", "--time-cap-min", "300"]),
    "time_cap": (True, "auto_safe", ["--step-cap", "20", "--time-cap-min", "0"]),
    "jg_absent_safe": (True, "auto_safe", []),
    "jg_pending_safe": (True, "auto_safe", ["--judgment-gate", "pending"]),
    "jg_clear_safe": (True, "auto_safe", ["--judgment-gate", "clear"]),
    "jg_blocked_safe": (True, "auto_safe", ["--judgment-gate", "blocked"]),
    "jg_pending_full": (True, "auto_full", ["--judgment-gate", "pending"]),
    "jg_clear_full": (True, "auto_full", ["--judgment-gate", "clear"]),
    "jg_blocked_full": (True, "auto_full", ["--judgment-gate", "blocked"]),
}


def test_inputs_match_the_frozen_fixture() -> None:
    assert set(INPUTS) == set(_BASELINE["inputs"])


# ── PLAN variants ─────────────────────────────────────────────────────────────


class PlanCase:
    def __init__(
        self,
        name: str,
        frontmatter: str | None,
        *,
        objective_state: str = "active",
        valid_approval: bool = True,
        expected_reason: str | None = None,
        expected_raw: Any = None,
        expected_parse_error: bool = False,
        expected_display: str | None = None,
    ) -> None:
        self.name = name
        self.frontmatter = frontmatter
        self.objective_state = objective_state
        self.valid_approval = valid_approval
        self.expected_reason = expected_reason
        self.expected_raw = expected_raw
        self.expected_parse_error = expected_parse_error
        self.expected_display = expected_display


BASELINE_CASES = [
    PlanCase("key_absent", "---\ntype: plan\ntask_slug: task-a\n---\n"),
    PlanCase("file_absent", None),
    PlanCase(
        "approved_active", "---\ntype: plan\nobjective: OBJ-1\n---\n", expected_display="OBJ-1"
    ),
]
FAILING_CASES = [
    PlanCase(
        "null",
        "---\ntype: plan\nobjective:\n---\n",
        expected_reason="link_invalid",
        expected_raw=None,
        expected_display="None",
    ),
    PlanCase(
        "empty",
        '---\ntype: plan\nobjective: ""\n---\n',
        expected_reason="link_invalid",
        expected_raw="",
        expected_display="''",
    ),
    PlanCase(
        "number",
        "---\ntype: plan\nobjective: 42\n---\n",
        expected_reason="link_invalid",
        expected_raw=42,
        expected_display="42",
    ),
    PlanCase(
        "yaml_date",
        "---\ntype: plan\nobjective: 2026-09-16\n---\n",
        expected_reason="link_invalid",
        expected_raw={"yaml_type": "date", "repr": "2026-09-16"},
        expected_display=repr(dt.date(2026, 9, 16)),
    ),
    PlanCase(
        "unparseable",
        "---\ntype: plan\n: : [\nobjective: OBJ-1\n---\n",
        expected_reason="link_invalid",
        expected_raw=None,
        expected_parse_error=True,
        expected_display="<unparseable frontmatter>",
    ),
    PlanCase(
        "missing_id",
        "---\ntype: plan\nobjective: OBJ-NOPE\n---\n",
        expected_reason="missing",
        expected_raw="OBJ-NOPE",
        expected_display="OBJ-NOPE",
    ),
    PlanCase(
        "not_active",
        "---\ntype: plan\nobjective: OBJ-1\n---\n",
        objective_state="proposed",
        expected_reason="not_active",
        expected_raw="OBJ-1",
        expected_display="OBJ-1",
    ),
    PlanCase(
        "approval_invalid",
        "---\ntype: plan\nobjective: OBJ-1\n---\n",
        valid_approval=False,
        expected_reason="approval_invalid",
        expected_raw="OBJ-1",
        expected_display="OBJ-1",
    ),
]


def _project(root: Path, case: PlanCase, *, git: bool = False) -> Path:
    obj = fx.objective("OBJ-1", state=case.objective_state)
    if case.valid_approval:
        obj = fx.approved(obj, 10)
    fx.build_root(root, git=git, objectives=[obj])
    (root / ".claude" / "harness.yaml").write_text("preset: Side\n", encoding="utf-8")
    if case.frontmatter is not None:
        plan = root / "work-docs" / f"PLAN-{SLUG}.md"
        plan.parent.mkdir(parents=True, exist_ok=True)
        plan.write_text(case.frontmatter + "\n# PLAN\n", encoding="utf-8")
    return root


def _boundary(
    root: Path,
    stage: str,
    extra: list[str],
    *,
    monkeypatch: pytest.MonkeyPatch,
    slug: str | None = SLUG,
) -> dict[str, Any]:
    """The shipped entrypoint with `--root .` from `root` as cwd — exactly the rendered call."""
    monkeypatch.chdir(root)
    argv = ["boundary", "--root", ".", "--current", stage, *extra]
    if slug is not None:
        argv += ["--slug", slug]
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = autopilot_caps.main(argv)
    out = json.loads(buf.getvalue().strip().splitlines()[-1])
    return {"rc": rc, **{k: out.get(k) for k in _KEEP}, "_message": out.get("reason", "")}


def _arm(root: Path, level: str) -> None:
    autopilot.write(root, level=level, pipeline=_PIPELINE, now=dt.datetime.now(dt.UTC).isoformat())  # type: ignore[arg-type]


def _events(root: Path) -> list[dict[str, Any]]:
    p = root / ".claude" / "observability" / "auto-advance.jsonl"
    if not p.exists():
        return []
    return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]


def _strip(cell: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in cell.items() if k != "_message"}


# ── the matrix ───────────────────────────────────────────────────────────────


@pytest.mark.parametrize("case", BASELINE_CASES, ids=lambda c: c.name)
@pytest.mark.parametrize("stage", _STAGES)
@pytest.mark.parametrize("inp", list(INPUTS))
def test_ac_012_absent_and_approved_links_equal_the_baseline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, case: PlanCase, stage: str, inp: str
) -> None:
    armed, level, extra = INPUTS[inp]
    root = _project(tmp_path, case)
    if armed:
        _arm(root, level)
    got = _strip(_boundary(root, stage, extra, monkeypatch=monkeypatch))
    assert got == _BASELINE["matrix"][f"{stage}|{inp}"], (case.name, stage, inp)


@pytest.mark.parametrize("case", FAILING_CASES, ids=lambda c: c.name)
@pytest.mark.parametrize("stage", _STAGES)
@pytest.mark.parametrize("inp", list(INPUTS))
def test_ac_012_failing_links_only_replace_an_advance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, case: PlanCase, stage: str, inp: str
) -> None:
    armed, level, extra = INPUTS[inp]
    root = _project(tmp_path, case)
    if armed:
        _arm(root, level)
    baseline = _BASELINE["matrix"][f"{stage}|{inp}"]
    got = _boundary(root, stage, extra, monkeypatch=monkeypatch)
    if baseline["proceed"] is not True:
        assert _strip(got) == baseline, (case.name, stage, inp)
        return
    assert got["proceed"] is False
    assert got["halt_kind"] == "objective_gate"
    assert case.expected_display is not None
    assert case.expected_display in got["_message"]
    last = _events(root)[-1]
    assert last["event"] == "gate_blocked"
    assert last["reason"] == case.expected_reason
    assert last["display_ref"] == case.expected_display
    assert last["raw_link"] == case.expected_raw
    assert last["parse_error"] is case.expected_parse_error
    # No advance was authorized on this path.
    assert all(e["event"] != "advance_authorized" for e in _events(root))


def test_ac_012_the_date_link_is_readable_from_the_event_file_as_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = FAILING_CASES[3]
    assert case.name == "yaml_date"
    root = _project(tmp_path, case)
    _arm(root, "auto_safe")
    _boundary(root, "execute", INPUTS["armed"][2], monkeypatch=monkeypatch)
    raw_text = (root / ".claude" / "observability" / "auto-advance.jsonl").read_text(
        encoding="utf-8"
    )
    last = json.loads(raw_text.strip().splitlines()[-1])
    assert last["raw_link"] == {"yaml_type": "date", "repr": "2026-09-16"}


def test_ac_012_the_entrypoint_takes_no_objective_argument() -> None:
    assert "objective" not in inspect.signature(autopilot_caps._objective_check).parameters
    assert "objective" not in inspect.signature(autopilot_caps._cmd_boundary).parameters
    with pytest.raises(SystemExit):
        autopilot_caps.main(
            ["boundary", "--root", ".", "--current", "execute", "--objective", "OBJ-1"]
        )


def test_ac_012_marker_persisted_slug_still_evaluates_the_gate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = FAILING_CASES[7]
    assert case.name == "approval_invalid"
    root = _project(tmp_path, case)
    _arm(root, "auto_safe")
    # research advances in the baseline and persists the slug into the marker.
    first = _boundary(root, "research", INPUTS["armed"][2], monkeypatch=monkeypatch)
    assert first["halt_kind"] == "objective_gate"
    # No --slug: the check keys on the marker-persisted slug.
    second = _boundary(root, "execute", INPUTS["armed"][2], monkeypatch=monkeypatch, slug=None)
    assert second["halt_kind"] == "objective_gate"
    assert _events(root)[-1]["reason"] == "approval_invalid"


# ── two checkouts (ADR-009) ──────────────────────────────────────────────────


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, timeout=60)


def test_ac_012_two_checkouts_the_worktree_link_is_the_one_used(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    base = tmp_path / "base"
    base.mkdir()
    obj = fx.approved(fx.objective("OBJ-1", state="active"), 10)
    fx.build_root(base, objectives=[obj])
    (base / ".claude" / "harness.yaml").write_text("preset: Side\n", encoding="utf-8")
    plan = base / "work-docs" / f"PLAN-{SLUG}.md"
    plan.parent.mkdir(parents=True, exist_ok=True)
    plan.write_text("---\ntype: plan\n---\n# PLAN\n", encoding="utf-8")
    (base / ".gitignore").write_text(".worktrees/\n", encoding="utf-8")
    _git(base, "add", "-A")
    _git(base, "commit", "-q", "-m", "init")
    wt = base / ".worktrees" / SLUG
    _git(base, "worktree", "add", "-q", "-b", f"hm/{SLUG}", str(wt))
    # In the WORKTREE: the PLAN links OBJ-1 and the outcome target is edited → approval invalid.
    (wt / "work-docs" / f"PLAN-{SLUG}.md").write_text(
        "---\ntype: plan\nobjective: OBJ-1\n---\n# PLAN\n", encoding="utf-8"
    )
    doc = yaml.safe_load((wt / ".claude" / "intent.yaml").read_text(encoding="utf-8"))
    doc["outcomes"][0]["target"] = 11
    (wt / ".claude" / "intent.yaml").write_text(yaml.safe_dump(doc), encoding="utf-8")
    _arm(base, "auto_safe")
    extra = INPUTS["armed"][2]
    from_wt = _boundary(wt, "execute", extra, monkeypatch=monkeypatch)
    assert from_wt["halt_kind"] == "objective_gate"
    assert _events(base)[-1]["reason"] == "approval_invalid"
    assert not (wt / ".claude" / "observability" / "auto-advance.jsonl").exists()
    _arm(base, "auto_safe")
    from_main = _strip(_boundary(base, "execute", extra, monkeypatch=monkeypatch))
    assert from_main == _BASELINE["matrix"]["execute|armed"]


# ── AC-006 (SPEC-objective-gap-proposal) — a CLI-built `proposed` record halts with not_active ──


def test_ac_006_a_proposed_record_built_by_the_verb_halts_with_not_active(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The proposal path makes `proposed`-linked PLANs common; the gate reason must stay
    `not_active` (never `approval_invalid`) so the operator is told to approve + activate."""
    from harness_maker import world

    root = fx.build_root(tmp_path, git=False, objectives=[])
    (root / ".claude" / "harness.yaml").write_text("preset: Side\n", encoding="utf-8")
    world.new_objective(
        root,
        "OBJ-9",
        title="t",
        hypothesis="h",
        scope=["s"],
        outcome_id="onboarding_minutes",
        from_proposal=True,
        candidates=1,
    )
    plan = root / "work-docs" / f"PLAN-{SLUG}.md"
    plan.write_text("---\ntype: plan\nobjective: OBJ-9\n---\n\n# PLAN\n", encoding="utf-8")
    _arm(root, "auto_safe")
    got = _boundary(
        root, "execute", ["--step-cap", "20", "--time-cap-min", "300"], monkeypatch=monkeypatch
    )
    assert got["proceed"] is False
    assert got["halt_kind"] == "objective_gate"
    gate = [e for e in _events(root) if e["event"] == "gate_blocked"]
    assert gate[-1]["reason"] == "not_active"
