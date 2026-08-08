"""Phase 3 — the autonomy default is promoted, and the conservative paths diverge from it.

PLAN-harness-diet ADR-010 flips `AutonomyConfig`'s class default to `auto_safe` /
`autopilot_persistent: true` so a NEW harness auto-arms. ADR-013 is the other half: a
default flip reaches every bare `AutonomyConfig()` construction, including the ones that
exist precisely to be safe. Each such site is classified here, and the divergence is
asserted rather than left to a future "simplify" refactor to collapse.

Site classification (`rg 'AutonomyConfig\\(\\)'`):
  delivery          interview.py `_build_answers` fallback → stays bare, inherits the flip
                    (fresh installs only; `cli` now passes `autonomy=` on a preset switch)
  delivery/inert    autopilot.py `list(AutonomyConfig().pipeline)` → reads `pipeline` only
  explicit refusal  interview.py `_ask_autonomy` "[y/N]" → no  → pinned gated
  absent block      interview.py `_parse_autonomy` non-dict      → pinned gated
  malformed block   interview.py `_parse_autonomy` ValidationError → pinned gated
  absent base       cli.py `_build_autonomy_override`            → pinned gated
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from harness_maker.interview import _ask_autonomy, _parse_autonomy
from harness_maker.models import AutonomyConfig


def test_the_class_default_is_promoted() -> None:
    """ADR-010: a new harness auto-arms without the user re-enabling it every session."""
    cfg = AutonomyConfig()
    assert cfg.level == "ask"  # ADR-012: the class default now ASKS per session.
    assert cfg.autopilot_persistent is True


def test_an_absent_autonomy_block_stays_gated() -> None:
    """A package upgrade must not escalate autonomy on a harness that never asked for it."""
    cfg = _parse_autonomy(None)
    assert cfg.level == "gated"
    assert cfg.autopilot_persistent is False


def test_a_malformed_autonomy_block_stays_gated() -> None:
    """One typo in an enum must not be the thing that turns on persistent auto-advance."""
    cfg = _parse_autonomy({"level": "bogus"})
    assert cfg.level == "gated"
    assert cfg.autopilot_persistent is False


def test_a_present_block_is_read_as_stated_intent_not_as_a_delivery_site() -> None:
    """ADR-013 originally left partial blocks inheriting the flip. Overturned on evidence.

    Because every previously-rendered harness.yaml spells out all six autonomy fields and is
    round-tripped verbatim, a partial block is the ONLY route by which the promotion can
    reach an existing project — and it reaches it in the worst possible shape. Two
    independent second-opinion models flagged it: `{autopilot_persistent: false}` inheriting
    `level: auto_safe` overrides an explicit refusal, and `{step_cap: 20}` auto-arms someone
    who only wanted a limit.
    """
    for block in ({}, {"step_cap": 20}, {"autopilot_persistent": False}):
        cfg = _parse_autonomy(block)
        assert cfg.level == "gated", block
        assert cfg.autopilot_persistent is False, block
    # Scoped to the two flipped fields only — an explicit value still wins, and an unrelated
    # field is untouched, so this is not a general strictness change.
    explicit = _parse_autonomy({"level": "full", "autopilot_persistent": True, "step_cap": 7})
    assert explicit.level == "auto_safe"  # B1/ADR-001: demoted on load, never escalated.
    assert explicit.autopilot_persistent is True
    assert explicit.step_cap == 7


def test_parsing_does_not_mutate_the_callers_block() -> None:
    """The conservative defaults are applied to a COPY — `value` may be the caller's dict."""
    block: dict[str, object] = {"step_cap": 20}
    _parse_autonomy(block)
    assert block == {"step_cap": 20}


def test_an_explicit_decline_stays_gated(monkeypatch: pytest.MonkeyPatch) -> None:
    """The sharpest case: the user was ASKED and said no.

    Leaving this site bare would convert a refusal into the exact behaviour refused —
    strictly worse than the malformed-config case, where nobody was asked.
    """
    monkeypatch.setattr("harness_maker.interview._input_or_empty", lambda _prompt: "n")
    cfg = _ask_autonomy()
    assert cfg.level == "gated"
    assert cfg.autopilot_persistent is False


def test_accepting_the_interview_prompt_still_arms(monkeypatch: pytest.MonkeyPatch) -> None:
    """Positive control — without it, the decline test passes on a broken prompt."""
    # Level answered EXPLICITLY: the offered default is now `ask` (ADR-012), and an empty
    # level answer here would assert the default rather than that accepting the prompt arms.
    replies = iter(["y", "auto_safe", "y", "", ""])
    monkeypatch.setattr("harness_maker.interview._input_or_empty", lambda _p: next(replies, ""))
    cfg = _ask_autonomy()
    assert cfg.level == "auto_safe"
    assert cfg.autopilot_persistent is True


def test_a_configure_override_with_no_existing_block_does_not_inherit_the_flip() -> None:
    """`_build_autonomy_override`'s own docstring says persistence defaults OFF.

    Its bare fallback is the branch taken when the project has no valid autonomy block, so
    inheriting the flip would make `--autonomy-persistent false` silently set level
    `auto_safe` — contradicting the documented contract. Not named in the PLAN; found by
    enumerating every bare construction.
    """
    from harness_maker.cli import _build_autonomy_override

    merged = _build_autonomy_override(level=None, persistent=False, existing=None)
    assert isinstance(merged, AutonomyConfig)
    assert merged.level == "gated"
    assert merged.autopilot_persistent is False


def test_the_class_default_and_the_conservative_fallback_differ_on_purpose() -> None:
    """Guard against a future refactor collapsing the pinned sites back to `AutonomyConfig()`.

    If this ever fails because both sides read `auto_safe`, the pins were removed — not
    because the divergence stopped mattering.
    """
    delivered = AutonomyConfig()
    fallback = _parse_autonomy(None)
    assert (delivered.level, delivered.autopilot_persistent) != (
        fallback.level,
        fallback.autopilot_persistent,
    )


def test_the_pipeline_source_of_truth_is_unaffected_by_the_flip() -> None:
    """`autopilot.py` reads only `pipeline` from a bare construction — it stays bare."""
    stages = [s.value for s in AutonomyConfig().pipeline]
    assert stages == ["research", "spec", "plan", "execute", "review", "verify", "wrapup"]


@pytest.mark.parametrize("preset_name", ["Side", "Production"])
def test_both_presets_render_the_promoted_default(tmp_path: Path, preset_name: str) -> None:
    """The shipped harness.yaml is what a user actually gets — assert the rendered bytes."""
    import yaml

    from harness_maker.models import Preset

    from .test_schema_migration import _render_preset

    out = _render_preset(tmp_path, Preset(preset_name))
    docs: list[Any] = list(yaml.safe_load_all((out / "harness.yaml").read_text(encoding="utf-8")))
    body = [d for d in docs if d and isinstance(d, dict) and "preset" in d][0]
    assert body["autonomy"]["level"] == "ask"  # ADR-012: the class default now ASKS per session.
    assert body["autonomy"]["autopilot_persistent"] is True
    assert body["autonomy"]["step_cap"] == 20
    assert body["autonomy"]["time_cap_min"] == 300


def test_reinterview_preserves_an_existing_projects_explicit_opt_out(tmp_path: Path) -> None:
    """The `--reinterview` escalation route, found by the round-2 security re-review.

    `--reinterview` sets `reused = None`, so `answers_from_harness_yaml` — and therefore
    `_parse_autonomy` — never runs. Combined with the non-tty auto-flip to `autoloop_mode`
    (a slash-command or CI invocation has no tty), an EXISTING project that explicitly set
    `level: gated` / `autopilot_persistent: false` would be rebuilt from the promoted class
    default and then auto-armed every session by the SessionStart hook.

    This is a RECURRENCE: the identical defect was found once before for
    `worktree.feature_branch_workflow`, and the fix sits on the adjacent lines with its own
    "REVIEW security P2" note. A second field was added to the same rebuild path without
    inheriting that guard.
    """
    import subprocess
    import sys

    project = tmp_path / "proj"
    (project / ".claude").mkdir(parents=True)
    (project / ".claude" / "harness.yaml").write_text(
        "preset: Side\nlocale: en\ntargets: [claude-code]\ndev_mode: task-driven\n"
        "autonomy:\n  level: gated\n  autopilot_persistent: false\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "init", "-q"], cwd=project, check=True, timeout=60)
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "harness_maker.cli",
            "make",
            str(project),
            "--update",
            "--reinterview",
        ],
        capture_output=True,
        text=True,
        timeout=300,
        stdin=subprocess.DEVNULL,  # non-tty: the path that triggers the auto-flip
    )
    assert proc.returncode == 0, proc.stderr[-2000:]
    body = (project / ".claude" / "harness.yaml").read_text(encoding="utf-8")
    assert '"gated"' in body or "level: gated" in body, body[body.find("autonomy:") :][:200]
    assert "autopilot_persistent: false" in body, body[body.find("autonomy:") :][:200]


def _make_project(tmp_path: Path, autonomy_block: str) -> Path:
    import subprocess

    project = tmp_path / "proj"
    (project / ".claude").mkdir(parents=True)
    (project / ".claude" / "harness.yaml").write_text(
        "preset: Side\nlocale: en\ntargets: [claude-code]\ndev_mode: task-driven\n"
        + autonomy_block,
        encoding="utf-8",
    )
    subprocess.run(["git", "init", "-q"], cwd=project, check=True, timeout=60)
    return project


def _run_make(project: Path, *extra: str) -> str:
    import subprocess
    import sys

    proc = subprocess.run(
        [sys.executable, "-m", "harness_maker.cli", "make", str(project), "--update", *extra],
        capture_output=True,
        text=True,
        timeout=300,
        stdin=subprocess.DEVNULL,  # non-tty: the path that auto-flips to autoloop defaults
    )
    assert proc.returncode == 0, proc.stderr[-2000:]
    return (project / ".claude" / "harness.yaml").read_text(encoding="utf-8")


def test_reinterview_does_not_clobber_an_explicit_autonomy_flag(tmp_path: Path) -> None:
    """The re-apply must not override an explicit `--autonomy-level`.

    The first version of the `--reinterview` fix ran unconditionally, AFTER both
    `_ask_autonomy` and `_apply_dimension_overrides` — so it silently discarded a fresh
    interview answer and an explicit flag, inverting `--reinterview`'s own "ask me fresh"
    contract. The `feature_branch_workflow` re-apply it was copied from is never
    interview-asked, so that precedent did not carry.
    """
    project = _make_project(tmp_path, "autonomy:\n  level: gated\n  autopilot_persistent: false\n")
    body = _run_make(project, "--reinterview", "--autonomy-level", "full")
    autonomy = body[body.find("autonomy:") :][:200]
    # `--autonomy-level full` is accepted and written as its current name rather than
    # rejected: a scripted --update carrying an old level must not fail the make.
    assert "auto_safe" in autonomy, autonomy


def test_reinterview_on_a_harness_with_no_autonomy_block_stays_gated(tmp_path: Path) -> None:
    """Absent-case escalation: a project predating the `autonomy:` key never chose.

    The first fix only re-applied when the on-disk value was a dict, so a harness.yaml
    without the key fell through to the promoted class default and gained persistent
    auto-advance on a silent re-render — contradicting the README's own claim.
    """
    project = _make_project(tmp_path, "")
    body = _run_make(project, "--reinterview")
    autonomy = body[body.find("autonomy:") :][:200]
    assert "gated" in autonomy, autonomy
    assert "autopilot_persistent: false" in autonomy, autonomy
