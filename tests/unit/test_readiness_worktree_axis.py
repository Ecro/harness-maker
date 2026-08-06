"""PLAN-worktree-side-defaults follow-up — /hm:health's worktree signal.

RESEARCH V6 measured ZERO worktree signals in either preset's dashboard: neither the
Side `enabled:False`-vs-`scope:[execute]` contradiction, nor an absent flag silently
falling back to the legacy model, produced anything an operator would see. The only
surface was a one-shot stderr line mid-command.

The signal is advisory (`weight=0`) on purpose. Isolation on/off is a config CHOICE, so
neither value is a finding — what IS a finding is resolving through a RETIRED key,
which means the harness has not been re-rendered and is running on a compatibility
fallback.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from harness_maker.readiness import _dim_guardrails


def _harness(tmp_path: Path, block: str) -> Path:
    root = tmp_path / "proj"
    (root / ".claude").mkdir(parents=True)
    (root / ".claude" / "harness.yaml").write_text(
        "preset: Production\ndev_mode: task-driven\n" + block, encoding="utf-8"
    )
    return root


def _signal(root: Path):  # type: ignore[no-untyped-def]
    hits = [s for s in _dim_guardrails(root).signals if s.id == "worktree_axis_current"]
    return hits[0] if hits else None


@pytest.mark.parametrize("value", ["true", "false"])
def test_a_current_axis_passes_and_states_the_mode(tmp_path: Path, value: str) -> None:
    """Both values pass — the axis is a choice. The evidence still names the mode, so a
    dashboard reader can tell which one is live without opening harness.yaml."""
    sig = _signal(_harness(tmp_path, f"worktree:\n  enabled: {value}\n"))
    assert sig is not None
    assert sig.passed is True
    assert sig.weight == 0, "advisory only — a config choice must not move the score"
    assert f"worktree.enabled: {value}" in sig.evidence


@pytest.mark.parametrize(
    ("block", "retired"),
    [
        (
            "worktree:\n  scope: [execute, plan]\n  feature_branch_workflow: true\n",
            "feature_branch_workflow",
        ),
        ("worktree:\n  scope: [execute]\n  branch_prefix: hm-\n", "scope"),
    ],
)
def test_a_legacy_rung_fails_and_names_the_retired_key(
    tmp_path: Path, block: str, retired: str
) -> None:
    """The case with no other surface: it works, silently, on a fallback."""
    sig = _signal(_harness(tmp_path, block))
    assert sig is not None
    assert sig.passed is False
    assert retired in sig.evidence
    assert sig.action is not None
    assert "--update" in sig.action


def test_a_malformed_value_fails_with_the_resolver_diagnostic(tmp_path: Path) -> None:
    """`enabled: "false"` is truthy to `bool(...)`; the reader resolves it fail-closed
    and the dashboard must carry that reason rather than reporting a clean OFF."""
    sig = _signal(
        _harness(tmp_path, 'worktree:\n  enabled: "false"\n  feature_branch_workflow: true\n')
    )
    assert sig is not None
    assert sig.passed is False
    assert "not a boolean" in sig.evidence


def test_a_harness_without_the_block_emits_no_signal(tmp_path: Path) -> None:
    """N-A rather than a failure: a harness.yaml with no worktree block at all predates
    the axis entirely, and inventing a finding for it would penalise every old project
    on a dimension it never opted into."""
    assert _signal(_harness(tmp_path, "")) is None
