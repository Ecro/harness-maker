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
import importlib.util
import inspect
import subprocess
import sys
import types
from pathlib import Path
from typing import Any

import pytest

import harness_maker
from harness_maker import command_registry, intent, worktree

ROOT = Path(__file__).parents[2]
PINNED_NOW = dt.datetime(2026, 10, 4, 0, 0, 0, tzinfo=dt.UTC)
TRIAL_VERBS = {"trial", "reconcile", "record-decision"}


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


# ── AC-004, AC-006, AC-007 (retired by SPEC-intent-lean) ────────────────────────────────
#
# The objective gate (AC-004), the `--from-proposal` path (AC-006) and the old status payload
# (AC-007, with its `tests/fixtures/intent_layer_diet/` goldens) were removed by SPEC-intent-lean;
# their ACs are marked `superseded_by: intent-lean`.
