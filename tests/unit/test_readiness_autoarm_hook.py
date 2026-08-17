"""/hm:health loud smoke for the autopilot auto-arm SessionStart hook (P6).

When ``autonomy.autopilot_persistent: true`` is committed but the rendered hooks.json lost the
``autopilot_autoarm`` SessionStart hook, autopilot will NOT persist across sessions (silent
degradation). The smoke makes that loud. N-A (passes) when persistence is off.
"""

from __future__ import annotations

import json
from pathlib import Path

from harness_maker.readiness import Signal, _dim_guardrails

_SIG = "autopilot_autoarm_registered"


def _write(project_dir: Path, *, persistent: bool, autoarm: bool) -> None:
    """Hooks go in settings.json — Claude Code never reads .claude/hooks/hooks.json
    (Phase 4 of PLAN-permission-deny-and-hooks-wiring)."""
    claude = project_dir / ".claude"
    claude.mkdir(parents=True, exist_ok=True)
    cmds = ["uv run python -m harness_maker.hooks.sessionid_envfile"]
    if autoarm:
        cmds.append("uv run python -m harness_maker.hooks.autopilot_autoarm")
    (claude / "settings.json").write_text(
        json.dumps(
            {
                "permissions": {"allow": [], "deny": []},
                "hooks": {
                    "SessionStart": [{"hooks": [{"type": "command", "command": c} for c in cmds]}]
                },
            }
        ),
        encoding="utf-8",
    )
    (claude / "harness.yaml").write_text(
        "preset: Production\nautonomy:\n  level: auto_safe\n"
        f"  autopilot_persistent: {'true' if persistent else 'false'}\n",
        encoding="utf-8",
    )


def _find(signals: list[Signal], sig_id: str) -> Signal | None:
    return next((s for s in signals if s.id == sig_id), None)


def test_passes_when_persistent_and_autoarm_registered(tmp_path: Path) -> None:
    _write(tmp_path, persistent=True, autoarm=True)
    sig = _find(_dim_guardrails(tmp_path).signals, _SIG)
    assert sig is not None
    assert sig.passed is True


def test_fails_loudly_when_persistent_but_autoarm_missing(tmp_path: Path) -> None:
    _write(tmp_path, persistent=True, autoarm=False)
    sig = _find(_dim_guardrails(tmp_path).signals, _SIG)
    assert sig is not None
    assert sig.passed is False
    assert sig.action  # actionable remediation present


def test_na_when_persistence_off(tmp_path: Path) -> None:
    # Intentional opt-out is a config choice, not a missing guardrail → passes (N-A).
    _write(tmp_path, persistent=False, autoarm=False)
    sig = _find(_dim_guardrails(tmp_path).signals, _SIG)
    assert sig is not None
    assert sig.passed is True


def test_fails_when_persistent_but_settings_has_no_hooks_at_all(tmp_path: Path) -> None:
    """INVERTED at Phase 4 — this used to assert `passed is True`.

    The old "don't double-penalize, `hooks_json_present` owns it" contract made the signal
    fail OPEN; retiring hooks.json would have made it pass forever for every project. With
    `autopilot_persistent: true` and no hooks, autopilot silently stops persisting across
    sessions — exactly what this smoke exists to catch. `not _autopilot_persistent` remains
    a genuine N/A; "no hooks at all" does not.
    """
    claude = tmp_path / ".claude"
    claude.mkdir(parents=True, exist_ok=True)
    (claude / "harness.yaml").write_text(
        "preset: Production\nautonomy:\n  level: auto_safe\n  autopilot_persistent: true\n",
        encoding="utf-8",
    )
    sig = _find(_dim_guardrails(tmp_path).signals, _SIG)
    assert sig is not None
    assert sig.passed is False
