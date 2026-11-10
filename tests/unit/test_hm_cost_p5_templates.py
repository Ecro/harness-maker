"""SPEC-hm-cost-p5 AC-003, AC-004: the spec stage, the spec-validator agent and the registry state
the rule the CLI applies, and neither rendered text grows."""

from __future__ import annotations

import subprocess
from typing import Any

import pytest

from harness_maker import spec_machine, step_sensitivity
from harness_maker.models import HarnessConfig
from harness_maker.render import _extract_source_communication_variant, _make_env
from harness_maker.synthesize import _HARNESS_MAKER_PKG_ROOT
from tests.unit import hm_cost_p5_fixture as fx
from tests.unit import test_agent_body_partials as agents

TEMPLATES = "src/harness_maker/templates"
STAGE = "stages/spec.md.j2"
AGENT_BODY = "agents/spec-validator_body.md.j2"
VALIDATOR_FIRST = "Approve after spec-validator"


def _at_base(path: str) -> str:
    """The template's source at the base commit, so sizes are not numbers this change produced."""
    return subprocess.run(
        ["git", "-C", str(fx.REPO_ROOT), "show", f"{fx.BASE_SHA}:{TEMPLATES}/{path}"],
        capture_output=True, text=True, timeout=60, check=True,
    ).stdout  # fmt: skip


def _stage(source: str | None, *, is_codex: bool) -> str:
    env = _make_env()
    template = env.get_template(STAGE) if source is None else env.from_string(source)
    cfg: dict[str, Any] = HarnessConfig().model_dump(mode="json")
    return template.render(
        stage="spec", workflow_context="", project_name="", feature="", config=cfg,
        harness_maker_src_path=_HARNESS_MAKER_PKG_ROOT, is_codex=is_codex,
        communication_variant="reframe",
    )  # fmt: skip


def _agent(source: str | None) -> str:
    env = _make_env()
    name = "spec-validator"
    template = env.get_template(AGENT_BODY) if source is None else env.from_string(source)
    return template.render(
        name=name,
        reviewer_kind=agents._REVIEWER_KINDS.get(name, ""),
        config=agents._FULL_CONFIG,
        communication_variant=_extract_source_communication_variant(f"agents/{name}.md.j2", env),
    )


def _step(text: str, number: str) -> str:
    head = f"## Step {number} "
    assert head in text, f"no {head!r}"
    return text.split(head, 1)[1].split("\n## ", 1)[0]


@pytest.mark.parametrize("is_codex", [False, True])
def test_ac_003_stage_states_the_rule_and_does_not_grow(is_codex: bool) -> None:
    text = _stage(None, is_codex=is_codex)
    step2 = _step(text, "2")
    assert "Approve this SPEC and end interview" in step2
    assert VALIDATOR_FIRST in step2
    body = _step(text, "4.6").split("\n", 1)[1]  # the heading already says "spec-validator"
    assert '`"validator": "run"`' in body
    assert VALIDATOR_FIRST in body
    assert "Step 0" not in body
    assert "irreversible_decisions: []" not in body
    # S6: the validator-first choice is stamped only after a pass that raised nothing critical
    step5 = _step(text, "5")
    assert "or the validator one with no critical critique" in step5
    assert step5.index("no critical critique") < step5.index("spec_machine approve")
    # SPEC-ask-less (rule R, DRI-only interview) grows the stage by 34 chars, within its PLAN's
    # surface allowance.
    assert len(text) <= len(_stage(_at_base(STAGE), is_codex=is_codex)) + 34


def test_ac_003_agent_triggers_state_the_rule_and_do_not_grow() -> None:
    text = _agent(None)
    triggers = text.split("## Triggers", 1)[1].split("\n## ", 1)[0]
    assert '`"validator": "run"`' in triggers
    assert VALIDATOR_FIRST in triggers
    assert "declares or implies an irreversible decision" not in text
    assert "Step-0" not in triggers
    assert len(text) <= len(_agent(_at_base(AGENT_BODY)))


def test_ac_004_registry_carries_the_measurement_and_the_threshold() -> None:
    (entry,) = [
        e for e in step_sensitivity.REGISTRY if (e.stage, e.ordinal) == ("spec", "Step 4.6")
    ]
    assert entry.cls == "TUNE"
    assert "n=" in entry.source
    assert "Side-preset only" in entry.source
    assert spec_machine.VALIDATOR_SKIP_MAX_ACS == 8
    assert f"≤ {spec_machine.VALIDATOR_SKIP_MAX_ACS} live ACs" in entry.note
    assert "conditional on irreversible decisions" not in entry.note
    assert "hm-novalidator" in entry.measure_cmd
