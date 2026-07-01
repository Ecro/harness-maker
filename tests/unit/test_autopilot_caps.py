"""P5 — runaway caps + kill switch for autopilot chaining (ADR-007/009)."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from harness_maker import autopilot, autopilot_caps, autopilot_ledger
from harness_maker.iter_receipts import Verdict
from harness_maker.models import AtomicStage

# write() constructs the marker in strict mode → AtomicStage instances, not plain str.
_PIPELINE = list(AtomicStage)


def _arm(root: Path, *, created: datetime, level: str = "auto_safe") -> None:
    """Write a live marker stamped at `created` (matches the project session uuid)."""
    autopilot.write(root, level=level, pipeline=_PIPELINE, now=created.isoformat())  # type: ignore[arg-type]


# ── caps: step ────────────────────────────────────────────────────────────────


def test_step_cap_halts(tmp_path: Path) -> None:
    now = datetime(2026, 6, 20, 12, 0, tzinfo=UTC)
    _arm(tmp_path, created=now)
    d = autopilot_caps.evaluate_boundary(tmp_path, steps=3, step_cap=3, time_cap_min=60, now=now)
    assert d.proceed is False
    assert d.halt_kind == "step_cap"


def test_under_step_cap_proceeds(tmp_path: Path) -> None:
    now = datetime(2026, 6, 20, 12, 0, tzinfo=UTC)
    _arm(tmp_path, created=now)
    d = autopilot_caps.evaluate_boundary(tmp_path, steps=2, step_cap=3, time_cap_min=60, now=now)
    assert d.proceed is True
    assert d.halt_kind is None


# ── caps: time ──────────────────────────────────────────────────────────────


def test_time_cap_halts(tmp_path: Path) -> None:
    created = datetime(2026, 6, 20, 12, 0, tzinfo=UTC)
    _arm(tmp_path, created=created)
    now = created + timedelta(minutes=31)
    d = autopilot_caps.evaluate_boundary(tmp_path, steps=0, step_cap=20, time_cap_min=30, now=now)
    assert d.proceed is False
    assert d.halt_kind == "time_cap"


def test_under_time_cap_proceeds(tmp_path: Path) -> None:
    created = datetime(2026, 6, 20, 12, 0, tzinfo=UTC)
    _arm(tmp_path, created=created)
    now = created + timedelta(minutes=29)
    d = autopilot_caps.evaluate_boundary(tmp_path, steps=0, step_cap=20, time_cap_min=30, now=now)
    assert d.proceed is True
    assert d.halt_kind is None


# ── kill switch: marker removal aborts at next boundary ─────────────────────


def test_marker_removal_aborts_at_boundary(tmp_path: Path) -> None:
    now = datetime(2026, 6, 20, 12, 0, tzinfo=UTC)
    # never armed → no marker → kill switch.
    d = autopilot_caps.evaluate_boundary(tmp_path, steps=0, step_cap=20, time_cap_min=60, now=now)
    assert d.proceed is False
    assert d.halt_kind == "kill_switch"


def test_cleared_marker_aborts(tmp_path: Path) -> None:
    now = datetime(2026, 6, 20, 12, 0, tzinfo=UTC)
    _arm(tmp_path, created=now)
    autopilot.clear(tmp_path)  # user kill switch
    d = autopilot_caps.evaluate_boundary(tmp_path, steps=0, step_cap=20, time_cap_min=60, now=now)
    assert d.proceed is False
    assert d.halt_kind == "kill_switch"


def test_stale_marker_aborts(tmp_path: Path) -> None:
    created = datetime(2026, 6, 20, 12, 0, tzinfo=UTC)
    _arm(tmp_path, created=created)
    now = created + timedelta(hours=19)  # past _MARKER_TTL_HOURS → active_marker None
    d = autopilot_caps.evaluate_boundary(tmp_path, steps=0, step_cap=20, time_cap_min=600, now=now)
    assert d.proceed is False
    assert d.halt_kind == "kill_switch"


# ── precedence: kill switch wins over caps ──────────────────────────────────


def test_kill_switch_wins_over_step_cap(tmp_path: Path) -> None:
    now = datetime(2026, 6, 20, 12, 0, tzinfo=UTC)
    # no marker AND steps over cap → kill switch is surfaced (not step_cap).
    d = autopilot_caps.evaluate_boundary(tmp_path, steps=99, step_cap=3, time_cap_min=60, now=now)
    assert d.proceed is False
    assert d.halt_kind == "kill_switch"


# ── ledger: halted_cap event (ADR-009) ──────────────────────────────────────


def _ledger_lines(root: Path) -> list[dict]:
    path = root / ".claude" / "observability" / "auto-advance.jsonl"
    if not path.is_file():
        return []
    return [json.loads(ln) for ln in path.read_text().splitlines() if ln.strip()]


def test_cap_halt_writes_halted_cap_event(tmp_path: Path) -> None:
    now = datetime(2026, 6, 20, 12, 0, tzinfo=UTC)
    autopilot_caps.record_cap_halt(tmp_path, halt_kind="step_cap", steps=3, now=now)
    lines = _ledger_lines(tmp_path)
    assert len(lines) == 1
    assert lines[0]["event"] == "halted_cap"
    assert lines[0]["halt_kind"] == "step_cap"
    assert lines[0]["steps"] == 3


def test_kill_switch_does_not_write_cap_event(tmp_path: Path) -> None:
    # record_cap_halt only accepts cap kinds — kill_switch is rejected (not a cap halt).
    with pytest.raises(ValueError, match="kill_switch"):
        autopilot_caps.record_cap_halt(tmp_path, halt_kind="kill_switch", steps=0)  # type: ignore[arg-type]


# ── ledger: ADR-009 disjoint enum ───────────────────────────────────────────


def test_ledger_rejects_iter_receipts_verdict_literals(tmp_path: Path) -> None:
    for forbidden in ("pass", "fail", "skipped"):
        with pytest.raises(ValueError, match="ADR-009"):
            autopilot_ledger.append_event(tmp_path, event=forbidden)  # type: ignore[arg-type]


def test_ledger_accepts_the_three_events(tmp_path: Path) -> None:
    for ev in ("advanced", "gate_blocked", "halted_cap"):
        autopilot_ledger.append_event(tmp_path, event=ev, fields={"stage": "review"})  # type: ignore[arg-type]
    lines = _ledger_lines(tmp_path)
    assert [ln["event"] for ln in lines] == ["advanced", "gate_blocked", "halted_cap"]


def test_ledger_event_vocab_disjoint_from_verdict() -> None:
    # ADR-009 structural invariant: the two enums can never overlap.
    verdict_literals = set(Verdict.__args__)  # type: ignore[attr-defined]
    assert autopilot_ledger.EVENTS.isdisjoint(verdict_literals)


def test_fields_cannot_overwrite_event(tmp_path: Path) -> None:
    # ADR-009 bypass guard (Codex review P1): a fields dict carrying a reserved key must
    # NOT override the validated event — else a Verdict literal reaches disk.
    autopilot_ledger.append_event(
        tmp_path, event="advanced", fields={"event": "pass", "ts": "spoofed"}
    )
    lines = _ledger_lines(tmp_path)
    assert lines[0]["event"] == "advanced"
    assert lines[0]["ts"] != "spoofed"


# ── ledger: path containment (REVIEW P1) ────────────────────────────────────


def test_absolute_observability_dir_escape_raises(tmp_path: Path) -> None:
    outside = tmp_path.parent / "hm-escape-ledger"  # absolute, NOT within project_root
    with pytest.raises(ValueError, match="escapes project_root"):
        autopilot_ledger.append_event(tmp_path, event="advanced", observability_dir=outside)


def test_absolute_observability_dir_within_root_ok(tmp_path: Path) -> None:
    inside = tmp_path / "custom-obs"  # absolute, within project_root
    autopilot_ledger.append_event(tmp_path, event="advanced", observability_dir=inside)
    assert (inside / "auto-advance.jsonl").is_file()


# ── caps: boundary equality + cap precedence (REVIEW P2/P3) ──────────────────


def test_time_cap_halts_at_exact_cap(tmp_path: Path) -> None:
    created = datetime(2026, 6, 20, 12, 0, tzinfo=UTC)
    _arm(tmp_path, created=created)
    now = created + timedelta(minutes=30)  # exactly the cap → `>=` must halt
    d = autopilot_caps.evaluate_boundary(tmp_path, steps=0, step_cap=20, time_cap_min=30, now=now)
    assert d.proceed is False
    assert d.halt_kind == "time_cap"


def test_step_cap_wins_over_time_cap(tmp_path: Path) -> None:
    created = datetime(2026, 6, 20, 12, 0, tzinfo=UTC)
    _arm(tmp_path, created=created)
    now = created + timedelta(minutes=99)  # both caps tripped → step checked first
    d = autopilot_caps.evaluate_boundary(tmp_path, steps=5, step_cap=3, time_cap_min=30, now=now)
    assert d.proceed is False
    assert d.halt_kind == "step_cap"


# ── misroute guardrail: `autopilot_caps on/off` → redirect to root CLI ─────────


@pytest.mark.parametrize("verb", ["on", "off"])
def test_toggle_verb_redirects_to_root_cli(verb: str, capsys: pytest.CaptureFixture[str]) -> None:
    rc = autopilot_caps.main([verb, "--level", "auto_safe"])
    assert rc == 2
    err = capsys.readouterr().err
    # Names the real command so the operator (or LLM) can copy it verbatim.
    assert "python -m harness_maker autopilot" in err
    assert f"autopilot {verb}" in err
    # Passthrough of the trailing args so the corrected command is complete.
    assert "--level auto_safe" in err
    # Must NOT emit argparse's cryptic "invalid choice" for these verbs.
    assert "invalid choice" not in err


def test_boundary_subcommand_still_parses(tmp_path: Path) -> None:
    # Guardrail must not shadow the real subcommands.
    rc = autopilot_caps.main(["boundary", "--root", str(tmp_path), "--current", "plan"])
    assert rc == 0
