"""Phase B2 — `ask` resolves to a question, never silently to `gated`.

`ask` is a committed level that means "the picker asks this session". Two readers could each
have collapsed it into an existing bucket, and both collapses are silent:

* `effective_level` clamps any unrecognised level to `gated` (a deliberate fail-safe for
  typos). `ask` falling into that clamp makes a configured feature indistinguishable from a
  refusal — it would ship and never fire, which is `[fail:design] absent-case = feature black
  hole` (count:8) in its exact canonical shape.
* `status` reads only the marker, and `ask` lives in harness.yaml, so it reported `absent` —
  the same value as "never configured", and the picker branches on `reason`.

Neither would have raised, logged, or failed a test that only checked the happy path.
"""

from __future__ import annotations

from pathlib import Path

from harness_maker import autopilot
from harness_maker.models import AutonomyConfig

_SESSION = "b2-ask-session"


def _yaml(root: Path, level: str) -> None:
    (root / ".claude").mkdir(parents=True, exist_ok=True)
    (root / ".claude" / "harness.yaml").write_text(
        f"autonomy:\n  level: {level}\n", encoding="utf-8"
    )


def test_ask_survives_effective_level(tmp_path: Path) -> None:
    assert autopilot.effective_level(tmp_path, yaml_level="ask", session_id=_SESSION) == "ask"


def test_a_typo_still_clamps_to_gated(tmp_path: Path) -> None:
    """The fail-safe `ask` must not have weakened."""
    assert autopilot.effective_level(tmp_path, yaml_level="typo", session_id=_SESSION) == "gated"


def test_a_marker_answers_the_question(tmp_path: Path) -> None:
    autopilot.write(
        tmp_path,
        level="auto_full",
        pipeline=list(AutonomyConfig().pipeline),
        claude_session_id=_SESSION,
    )
    assert autopilot.effective_level(tmp_path, yaml_level="ask", session_id=_SESSION) == "auto_full"


def test_status_reports_ask_pending(tmp_path: Path) -> None:
    _yaml(tmp_path, "ask")
    out = autopilot.status(tmp_path, session_id=_SESSION)
    assert out["reason"] == "ask-pending"
    assert out["active"] is False


def test_status_is_armed_once_the_session_answers(tmp_path: Path) -> None:
    _yaml(tmp_path, "ask")
    autopilot.write(
        tmp_path,
        level="auto_safe",
        pipeline=list(AutonomyConfig().pipeline),
        claude_session_id=_SESSION,
    )
    out = autopilot.status(tmp_path, session_id=_SESSION)
    assert out["reason"] == "armed"
    assert out["active"] is True
    assert out["level"] == "auto_safe"


def test_a_non_ask_project_is_unchanged(tmp_path: Path) -> None:
    """The regression arm: `absent` must still mean absent for everyone else."""
    _yaml(tmp_path, "auto_safe")
    assert autopilot.status(tmp_path, session_id=_SESSION)["reason"] == "absent"


def test_an_unreadable_harness_yaml_does_not_raise(tmp_path: Path) -> None:
    (tmp_path / ".claude").mkdir(parents=True)
    (tmp_path / ".claude" / "harness.yaml").write_text("{[not yaml", encoding="utf-8")
    assert autopilot.status(tmp_path, session_id=_SESSION)["reason"] == "absent"
