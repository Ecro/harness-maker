"""/hm:health loud smoke for the autopilot auto-arm SessionStart hook (P6).

When ``autonomy.autopilot_persistent: true`` is committed but the rendered hooks.json lost the
``autopilot_autoarm`` SessionStart hook, autopilot will NOT persist across sessions (silent
degradation). The smoke makes that loud. N-A (passes) when persistence is off.
"""

from __future__ import annotations

import json
from pathlib import Path

from harness_maker.readiness import _dim_guardrails

_SIG = "autopilot_autoarm_registered"


def _write(project_dir: Path, *, persistent: bool, autoarm: bool) -> None:
    claude = project_dir / ".claude"
    (claude / "hooks").mkdir(parents=True, exist_ok=True)
    cmds = ["uv run python -m harness_maker.hooks.sessionid_envfile"]
    if autoarm:
        cmds.append("uv run python -m harness_maker.hooks.autopilot_autoarm")
    (claude / "hooks" / "hooks.json").write_text(
        json.dumps(
            {
                "hooks": {
                    "SessionStart": [{"hooks": [{"type": "command", "command": c} for c in cmds]}]
                }
            }
        ),
        encoding="utf-8",
    )
    (claude / "harness.yaml").write_text(
        "preset: Production\nautonomy:\n  level: auto_safe\n"
        f"  autopilot_persistent: {'true' if persistent else 'false'}\n",
        encoding="utf-8",
    )


def _find(signals: list, sig_id: str):  # type: ignore[no-untyped-def]
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


def test_na_when_persistent_but_no_hooks_json(tmp_path: Path) -> None:
    # persistent: true but NO hooks.json at all → the hooks_json_present signal owns that
    # case; this smoke must not double-penalize with a misleading "stale render" message.
    claude = tmp_path / ".claude"
    claude.mkdir(parents=True, exist_ok=True)
    (claude / "harness.yaml").write_text(
        "preset: Production\nautonomy:\n  level: auto_safe\n  autopilot_persistent: true\n",
        encoding="utf-8",
    )
    sig = _find(_dim_guardrails(tmp_path).signals, _SIG)
    assert sig is not None
    assert sig.passed is True
