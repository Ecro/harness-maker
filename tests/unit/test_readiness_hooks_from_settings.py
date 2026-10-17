"""Readiness's hook signals must read the file Claude Code actually loads.

PLAN-permission-deny-and-hooks-wiring Phase 4. All four guardrail hook signals read
`.claude/hooks/hooks.json` — the path Phase 1 proved Claude Code never loads. Two of
them are additionally written `(not hooks_path.exists()) or (...)`, so retiring that
file would make them PASS FOREVER, for every project, unconditionally.

That is why these are NEGATIVE controls, not a score check: a score-based "does not
regress" criterion cannot see a fail-open signal — the score is unchanged precisely
because the detector died. CLAUDE.md documents `sessionid_envfile_registered` as the
loud smoke against silent degradation; a detector that always passes is not a smoke
alarm. (Global memory 2026-06-08: "Absent-case = feature black hole".)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from harness_maker.models import Preset
from harness_maker.readiness import _dim_guardrails, compute_readiness

_HOOK_SIGNALS = ("hooks_json_present", "hooks_defined", "sessionid_envfile_registered")


def _write_settings(project_dir: Path, hooks: dict[str, Any] | None) -> None:
    claude = project_dir / ".claude"
    claude.mkdir(parents=True, exist_ok=True)
    data: dict[str, Any] = {"permissions": {"allow": [], "deny": []}, "preset": "Production"}
    if hooks is not None:
        data["hooks"] = hooks
    (claude / "settings.json").write_text(json.dumps(data), encoding="utf-8")


def _cmd(mod: str) -> dict[str, str]:
    return {"type": "command", "command": f"uv run --with /p python -m harness_maker.{mod}"}


def _full_hooks() -> dict[str, Any]:
    return {
        "PostToolUse": [{"matcher": "*", "hooks": [_cmd("telemetry")]}],
        "SessionStart": [{"hooks": [_cmd("hooks.sessionid_envfile")]}],
    }


def _sig(project_dir: Path, name: str) -> Any:
    # NOTE the field is `id`, not `name` — `Signal.name` silently resolves to something
    # else on the pydantic model, so `s.name == name` never matched and every assertion
    # read the FIRST signal regardless of which one it asked for. Caught only because the
    # expected-PASS cases failed too; a suite of expected-FAILs would have gone green.
    return next(s for s in _dim_guardrails(project_dir).signals if s.id == name)


@pytest.mark.parametrize("name", _HOOK_SIGNALS)
def test_signals_pass_on_a_healthy_settings_render(tmp_path: Path, name: str) -> None:
    _write_settings(tmp_path, _full_hooks())
    assert _sig(tmp_path, name).passed is True, name


def test_sessionid_signal_fails_when_settings_lost_the_sessionstart_hook(tmp_path: Path) -> None:
    """The negative control. A stale render that dropped SessionStart MUST fail.

    Nothing else catches it: `/hm:loop` silently self-stops at iteration 1 and CLAUDE.md
    attributes that symptom to a WSL2 env-file failure — so a dead detector here means the
    real cause is misdiagnosed as a known one.
    """
    hooks = _full_hooks()
    del hooks["SessionStart"]
    _write_settings(tmp_path, hooks)
    assert _sig(tmp_path, "sessionid_envfile_registered").passed is False


def _failing_ids(project_dir: Path, *, persistent: bool) -> set[str]:
    (project_dir / ".claude" / "harness.yaml").write_text(
        "---\ngenerated_by: harness-maker\n---\n"
        f"autonomy:\n  autopilot_persistent: {str(persistent).lower()}\n",
        encoding="utf-8",
    )
    result = compute_readiness(project_dir, Preset.PRODUCTION)
    return {s.id for d in result.dimensions.values() for s in d.signals if not s.passed}


def test_ac_001_autoarm_signal_is_retired(tmp_path: Path) -> None:
    """SPEC-retire-autopilot-remnants AC-001: `autopilot_persistent` is inert since 0.64.0.

    The autoarm hook is no longer rendered, so no re-render can satisfy a check for it. The
    failing-set comparison also catches the same check kept under another id.
    """
    _write_settings(tmp_path, _full_hooks())
    on = _failing_ids(tmp_path, persistent=True)
    all_ids = {
        s.id
        for d in compute_readiness(tmp_path, Preset.PRODUCTION).dimensions.values()
        for s in d.signals
    }
    assert "autopilot_autoarm_registered" not in all_ids
    assert on == _failing_ids(tmp_path, persistent=False)


def test_signals_fail_when_settings_has_no_hooks_key_at_all(tmp_path: Path) -> None:
    """The absent-case. Post-Phase-4 there is no hooks.json to fall back to, so a
    settings.json with no `hooks` key is a harness with NO hooks — every signal must say
    so. The old `(not hooks_path.exists()) or ...` shape would have passed all of them.
    """
    _write_settings(tmp_path, None)
    for name in _HOOK_SIGNALS:
        assert _sig(tmp_path, name).passed is False, name


def test_stale_hooks_json_cannot_rescue_a_broken_settings(tmp_path: Path) -> None:
    """The regression this phase exists to prevent.

    A leftover `.claude/hooks/hooks.json` — perfectly formed, containing every hook — must
    NOT make the signals green when settings.json (the file Claude Code actually reads) has
    lost them. Scoring the dead file is what let a broken harness read healthy.
    """
    _write_settings(tmp_path, None)
    hooks_dir = tmp_path / ".claude" / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    (hooks_dir / "hooks.json").write_text(
        json.dumps({"hooks": _full_hooks(), "preset": "Production"}), encoding="utf-8"
    )
    for name in _HOOK_SIGNALS:
        assert _sig(tmp_path, name).passed is False, f"{name}: rescued by the dead file"
