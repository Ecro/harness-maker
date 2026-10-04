"""SPEC-intent-layer-diet — AC-001…AC-007 (trial machinery and proposal ledger write removed).

AC-005 and AC-007 are preservation oracles: they compare the current code against pins and
goldens captured from the UNMODIFIED code (ADR-003 of the PLAN), so they pass before the change
by design and go red the moment the change moves a render, a pin or the status payload. The RED
positive siblings that force the deletion into existence are AC-001, AC-002, AC-003, AC-004 and
AC-006. Goldens are written by `_write_goldens()` once, before any source edit, and are never
regenerated afterwards.

`test_ac003_span_success_still_emits_the_task_start` also passes before the change: it guards
the success path the deletion must keep (one `start` event with the task fields). It goes red
if the trimmed `_emit_stage_span` stops emitting; its RED sibling is
`test_ac003_span_failure_warns_not_blocks`, which forces the warn-only branch into existence.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import importlib.util
import inspect
import io
import json
import shutil
import subprocess
import sys
import types
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any

import pytest

import harness_maker
from harness_maker import autopilot, autopilot_caps, command_registry, intent, worktree
from harness_maker.models import AtomicStage
from tests.unit import world_fixture as fx

ROOT = Path(__file__).parents[2]
FIXTURES = ROOT / "tests" / "fixtures" / "intent_layer_diet"
PINNED_NOW = dt.datetime(2026, 10, 4, 0, 0, 0, tzinfo=dt.UTC)
STATUS_FIXTURES = ("current", "legacy")
TRIAL_VERBS = {"trial", "reconcile", "record-decision"}


# ── shared helpers ──────────────────────────────────────────────────────────────────────


class _FrozenDatetime(dt.datetime):
    @classmethod
    def now(cls, tz: dt.tzinfo | None = None) -> _FrozenDatetime:
        return cls.fromtimestamp(PINNED_NOW.timestamp(), tz=tz or dt.UTC)


def _status_of(fixture: str, tmp: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Status of a COPY of the fixture root, clock pinned, so nothing touches the fixture.

    The copy is digested around the call: a status read is a pure read, so any file it
    writes or rewrites under the root it reads fails here, not only in the golden compare.
    """
    from harness_maker import intent_cli, world

    root = tmp / fixture
    shutil.copytree(FIXTURES / fixture, root)
    before = _tree_digest(root)
    monkeypatch.setattr(world, "datetime", _FrozenDatetime)
    status: dict[str, Any] = json.loads(
        json.dumps(intent_cli.status_report(root), sort_keys=True, default=str)
    )
    assert _tree_digest(root) == before, "status_report mutated the root it read"
    return status


def _tree_digest(root: Path) -> dict[str, str]:
    return {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(root.rglob("*"))
        if p.is_file() and not p.name.endswith(".golden.json")
    }


def _pin_digest() -> dict[str, str]:
    return {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted((ROOT / "tests" / "snapshot").glob("*.expected.yaml"))
    }


def _write_goldens() -> None:  # pragma: no cover — run once, before the first source edit
    """Capture the AC-005/AC-007 references from the unmodified code. Never re-run after it."""
    mp = pytest.MonkeyPatch()
    try:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            for fixture in STATUS_FIXTURES:
                status = _status_of(fixture, Path(tmp), mp)
                out = FIXTURES / fixture / "status.golden.json"
                out.write_text(json.dumps(status, indent=2, sort_keys=True) + "\n", "utf-8")
    finally:
        mp.undo()
    inputs = {f: _tree_digest(FIXTURES / f) for f in STATUS_FIXTURES}
    (FIXTURES / "inputs.golden.json").write_text(json.dumps(inputs, indent=2) + "\n", "utf-8")
    (FIXTURES / "snapshot_pins.golden.json").write_text(
        json.dumps(_pin_digest(), indent=2) + "\n", "utf-8"
    )


# ── AC-001 ──────────────────────────────────────────────────────────────────────────────


def test_ac001_trial_verbs_removed() -> None:
    sub = next(a for a in intent._parser()._actions if isinstance(a, argparse._SubParsersAction))
    assert not TRIAL_VERBS & set(sub.choices)
    assert not TRIAL_VERBS & command_registry.MODULES["intent"].subcommands
    assert importlib.util.find_spec("harness_maker.intent_trial") is None


def test_ac001_trial_verb_is_rejected_by_the_shipped_entrypoint(tmp_path: Path) -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "harness_maker.hm", "intent", "trial", "status", "T", "--json"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode != 0
    assert "invalid choice" in proc.stderr
    assert "Traceback" not in proc.stderr


# ── AC-002 ──────────────────────────────────────────────────────────────────────────────


def test_ac002_worktree_has_no_trial_reference() -> None:
    src = inspect.getsource(worktree)
    for needle in ("intent_trial", "_trial_active", "protected_trial", "trial_runtime"):
        assert needle not in src, needle


# ── AC-003 ──────────────────────────────────────────────────────────────────────────────


def _install_live_trial(monkeypatch: pytest.MonkeyPatch) -> None:
    """A world where a trial artifact exists: the trimmed code must not consult it."""
    fake = types.ModuleType("harness_maker.intent_trial")
    fake.active_trials = lambda base: ["LIVE-TRIAL"]  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "harness_maker.intent_trial", fake)
    monkeypatch.setattr(harness_maker, "intent_trial", fake, raising=False)


def test_ac003_span_failure_warns_not_blocks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from harness_maker import stage_spans

    _install_live_trial(monkeypatch)

    def boom(*_a: Any, **_k: Any) -> None:
        raise OSError("span store unwritable")

    monkeypatch.setattr(stage_spans, "emit_event", boom)
    worktree._emit_stage_span(tmp_path, stage="hm:execute", task_slug="t")  # must not raise
    err = capsys.readouterr().err
    assert "[span] emission failed" in err
    assert "span store unwritable" in err


def test_ac003_span_success_still_emits_the_task_start(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from harness_maker import stage_spans

    calls: list[dict[str, Any]] = []
    monkeypatch.setattr(
        stage_spans, "emit_event", lambda kind, **kw: calls.append({"kind": kind, **kw})
    )
    worktree._emit_stage_span(tmp_path, stage="hm:spec", git_branch="hm/t", task_slug="t")
    assert len(calls) == 1
    assert calls[0]["kind"] == "start"
    assert calls[0]["stage"] == "hm:spec"
    assert calls[0]["task_slug"] == "t"
    assert calls[0]["git_branch"] == "hm/t"
    assert calls[0]["fence_timeout"] == 5.0  # optional telemetry never waits the merge budget


# ── AC-004 ──────────────────────────────────────────────────────────────────────────────


def test_ac004_gate_remediation_names_hm_intent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from harness_maker import world

    slug = "diet-gate"
    root = fx.build_root(tmp_path, git=False, objectives=[])
    (root / ".claude" / "harness.yaml").write_text("preset: Side\n", encoding="utf-8")
    world.new_objective(
        root, "OBJ-9", title="t", hypothesis="h", scope=["s"], outcome_id="onboarding_minutes"
    )
    plan = root / "work-docs" / f"PLAN-{slug}.md"
    plan.write_text("---\ntype: plan\nobjective: OBJ-9\n---\n\n# PLAN\n", encoding="utf-8")
    autopilot.write(
        root,
        level="auto_safe",
        pipeline=[AtomicStage(s) for s in ("spec", "execute", "review")],
        now=dt.datetime.now(dt.UTC).isoformat(),
    )
    monkeypatch.chdir(root)
    buf = io.StringIO()
    with redirect_stdout(buf):
        autopilot_caps.main(
            [
                "boundary",
                "--root",
                ".",
                "--current",
                "execute",
                "--slug",
                slug,
                "--step-cap",
                "20",
                "--time-cap-min",
                "300",
            ]
        )
    out = json.loads(buf.getvalue().strip().splitlines()[-1])
    assert out["proceed"] is False
    message = out["reason"]
    assert "hm intent approve" in message
    assert "hm intent activate" in message
    assert "hm world" not in message


# ── AC-005 ──────────────────────────────────────────────────────────────────────────────


def test_ac005_snapshot_pins_not_regenerated() -> None:
    """Guards only the pin bytes: the pins must be the pre-change ones. The fresh-render half
    of AC-005 is `tests/unit/test_synthesize_snapshot.py`, which renders against these pins.
    Together: a moved render fails there, a regenerated pin fails here."""
    golden = json.loads((FIXTURES / "snapshot_pins.golden.json").read_text("utf-8"))
    assert _pin_digest() == golden


# ── AC-006 ──────────────────────────────────────────────────────────────────────────────


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, timeout=60)


def test_ac006_from_proposal_ledgers_untouched(tmp_path: Path) -> None:
    from harness_maker import autopilot_ledger, world

    base = fx.build_root(tmp_path / "base")
    _git(base, "add", "-A")
    _git(base, "commit", "-q", "-m", "fixture")
    wt = base / ".worktrees" / "t"
    _git(base, "worktree", "add", "-q", "-b", "hm/t", str(wt))
    autopilot_ledger.append_event(
        base,
        event="objective_proposed",
        fields={"objective": "OLD-1", "candidates": 2, "accepted": 1},
        observability_dir=base / ".claude" / "observability",
    )
    base_ledger = base / ".claude" / "observability" / "auto-advance.jsonl"
    wt_ledger = wt / ".claude" / "observability" / "auto-advance.jsonl"
    base_before = base_ledger.read_bytes()
    assert not wt_ledger.exists()

    rec = world.new_objective(
        wt,
        "OBJ-5",
        title="t",
        hypothesis="h",
        scope=["s"],
        outcome_id="onboarding_minutes",
        from_proposal=True,
        candidates=2,
        declined=["the other one"],
    )

    assert rec["state"] == "proposed"
    assert world.load_world(wt).objectives["OBJ-5"]["rejected"] == ["the other one"]
    assert base_ledger.read_bytes() == base_before
    assert not wt_ledger.exists()
    historical = [json.loads(ln) for ln in base_before.decode().splitlines() if ln.strip()]
    assert [r["event"] for r in historical] == ["objective_proposed"]
    assert autopilot_ledger.count_events(base, "objective_proposed") == 1


# ── AC-007 ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("fixture", STATUS_FIXTURES)
def test_ac007_status_json_identical(
    fixture: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    golden = json.loads((FIXTURES / fixture / "status.golden.json").read_text("utf-8"))
    assert _status_of(fixture, tmp_path, monkeypatch) == golden


def test_ac007_fixture_inputs_byte_unchanged() -> None:
    golden = json.loads((FIXTURES / "inputs.golden.json").read_text("utf-8"))
    assert {f: _tree_digest(FIXTURES / f) for f in STATUS_FIXTURES} == golden
