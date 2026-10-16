"""harness.yaml keys 0.64.0 made inert: one warning each per `make` run (SPEC-hm-overhaul-p1)."""

from __future__ import annotations

from typing import Any

from harness_maker.models import RETIRED_DELEGATION_STAGES
from harness_maker.synthesize import LENS_REVIEWERS, RETIRED_AGENTS, RETIRED_SKILLS


def _dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _names(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(v).strip().lower() for v in value if isinstance(v, str) and v.strip()]


def inert_key_warnings(data: dict[str, Any]) -> list[str]:
    """One line per inert key, in a fixed order; `[]` when nothing is inert.

    Warn-only (IRR-006): the schema keeps every key and a re-render keeps its value, so a 0.62
    file still parses under `extra="forbid"`. The warning is the only signal that a value which
    used to steer something now steers nothing, and it fires at `make` time, never at stage run.
    """
    out: list[str] = []
    if _dict(data.get("loop")).get("enabled") is True:
        out.append(
            "loop.enabled: /hm:loop is retired; use the host's /loop. The value is kept and inert."
        )
    stages = _names(_dict(data.get("delegation")).get("stages"))
    dropped = [s for s in stages if s in RETIRED_DELEGATION_STAGES]
    if dropped:
        out.append(
            f"delegation.stages: {', '.join(dropped)} no longer exist as stages and are skipped; "
            "the other stages still delegate."
        )
    reviewers = _dict(data.get("reviewers"))
    fanout = reviewers.get("fanout") is True
    named = {*_names(reviewers.get("installed")), *_names(reviewers.get("enabled"))}
    lenses = [n for n in LENS_REVIEWERS if n in named]
    installed_lenses = [n for n in LENS_REVIEWERS if n in _names(reviewers.get("installed"))]
    if lenses and not fanout:
        out.append(
            f"reviewers.installed/enabled: {', '.join(lenses)} do not render or run unless "
            "reviewers.fanout is true; only code-reviewer runs."
        )
    if fanout and not installed_lenses:
        out.append(
            "reviewers.fanout: true, but reviewers.installed names no lens reviewer, so only "
            "code-reviewer runs."
        )
    skills = _names(_dict(data.get("skills")).get("enabled"))
    retired_skills = [s for s in skills if s in RETIRED_SKILLS]
    if retired_skills:
        out.append(
            f"skills.enabled: {', '.join(retired_skills)} are retired and do not render; "
            "the value is kept and inert."
        )
    for name in _dict(data.get("agent_models")):
        if name in RETIRED_AGENTS:
            out.append(f"agent_models.{name}: the agent is retired; the key is kept and inert.")
        elif name in LENS_REVIEWERS and not fanout:
            out.append(
                f"agent_models.{name}: {name} renders only with reviewers.fanout true; "
                "the key is kept and inert."
            )
    if _dict(data.get("instrumentation")).get("stage_agent_ledger") is True:
        out.append(
            "instrumentation.stage_agent_ledger: the 0.64.0 stages emit no ledger rows; "
            "the value is kept and inert."
        )
    if _dict(data.get("autonomy")).get("autopilot_persistent") is True:
        out.append(
            "autonomy.autopilot_persistent: autopilot is retired; the value is kept and inert."
        )
    return out
