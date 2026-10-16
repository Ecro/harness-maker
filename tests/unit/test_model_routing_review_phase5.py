"""Phase 5 regression tests for REVIEW-model-routing-2026-05-19 findings.

Covers:
- MV-1 / MV-2: Pydantic model_copy validator bypass in interview.answers_from_harness_yaml
- MV-3: Jinja2 `is defined` returning True for None → `model: None` render
- CP-1 / R-1: trajectory-monitor removed from preset maps (dormant agent dead data)
- CP-2: _ALL_AGENTS ⊆ _COMMUNICATION_VARIANT symmetry enforced by structural test

The tests are RED before Phase 5 fixes; GREEN after.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

from harness_maker.io_utils import atomic_write
from harness_maker.models import AgentModelSpec, HarnessConfig, Preset
from harness_maker.presets import PRESET_AGENT_MODELS, resolve_agent_spec
from harness_maker.synthesize import _ALL_AGENTS, _COMMUNICATION_VARIANT

# Authoritative source for the post-fix fallback value — referenced
# instead of duplicating a literal in assertions (test-reviewer P5
# banned-pattern category 6 fix).
_HARNESS_DEFAULT_MODEL = HarnessConfig.model_fields["default_model"].default

# Regex matching the model: line; the value must be a non-empty concrete
# ID (no None, no null, no empty scalar). This is the actual MV-3 Then-clause:
# "agent dispatch must not break due to model: None render".
_VALID_MODEL_LINE = re.compile(r"^model:\s+[a-zA-Z0-9_.:-]+\s*$", re.MULTILINE)


# ──────────────────────────────────────────────────────────────────────────────
# MV-1 / MV-2 — Pydantic model_copy validator bypass on default_model load path
# ──────────────────────────────────────────────────────────────────────────────


def _write_harness_yaml(tmp_path: Path, body: dict[str, Any]) -> Path:
    """Helper: write a minimal harness.yaml with provenance frontmatter prefix
    so io_utils.load_harness_yaml can parse the multi-document stream."""
    frontmatter = (
        "---\n"
        "generated_by: test-fixture\n"
        "harness_maker_version: 0.0.0-test\n"
        "generated_at: '2026-01-01T00:00:00+00:00'\n"
        "source_template: test\n"
        "provenance: test\n"
        "content_hash: 0\n"
        "---\n"
    )
    yaml_body = yaml.safe_dump(body, sort_keys=False)
    path = tmp_path / "harness.yaml"
    atomic_write(path, frontmatter + yaml_body)
    return path


def test_mv1_default_model_yaml_injection_rejected_by_loader(tmp_path: Path) -> None:
    """MV-1: A harness.yaml `default_model` containing embedded YAML-significant
    characters (newline) must NOT pass through to update["default_model"] via
    Pydantic model_copy. The loader must validate against _MODEL_ID_PATTERN
    and fall back rather than render malicious YAML into agent frontmatter.
    """
    from harness_maker.interview import answers_from_harness_yaml

    payload = "claude-opus\ntools: [Write(*)]"
    yaml_path = _write_harness_yaml(
        tmp_path,
        {
            "preset": "Production",
            "targets": ["claude-code"],
            "default_model": payload,
        },
    )
    answers = answers_from_harness_yaml(yaml_path)
    assert answers is not None
    # Exact MV-1 Then-clause: the injected payload must NOT survive into
    # answers.default_model. We do not assume what the fallback value IS —
    # only that it is NOT the malicious payload, and that no YAML-significant
    # character (newline) reaches the renderer.
    assert answers.default_model != payload, (
        f"injected default_model survived: {answers.default_model!r}"
    )
    assert "\n" not in answers.default_model, (
        f"newline-laden default_model leaked past validator: {answers.default_model!r}"
    )
    # Fallback reaches via the canonical HarnessConfig.default_model default
    # (referenced from the model definition itself, NOT a literal copy).
    assert answers.default_model == _HARNESS_DEFAULT_MODEL


def test_mv2_recommended_model_migration_yaml_injection_rejected(tmp_path: Path) -> None:
    """MV-2: Same bypass exists on the schema-v1 `recommended_model` → `default_model`
    migration path. Validate before assignment on that branch too.
    """
    from harness_maker.interview import answers_from_harness_yaml

    payload = "claude-opus\ntools: [Write(*)]"
    yaml_path = _write_harness_yaml(
        tmp_path,
        {
            "preset": "Production",
            "targets": ["claude-code"],
            "schema_version": 1,
            "recommended_model": payload,
        },
    )
    answers = answers_from_harness_yaml(yaml_path)
    assert answers is not None
    # Same shape as MV-1, applied to the schema-v1 migration branch.
    assert answers.default_model != payload
    assert "\n" not in answers.default_model
    assert answers.default_model == _HARNESS_DEFAULT_MODEL


# ──────────────────────────────────────────────────────────────────────────────
# MV-3 — Jinja `is defined` returns True for None → model: None render bug
# ──────────────────────────────────────────────────────────────────────────────


def _extract_model_from_frontmatter(rendered: str) -> object:
    """Parse the YAML frontmatter of a rendered agent .md and return the
    parsed `model` field value (or None if missing). Use YAML parse rather
    than substring regex so we catch all None-equivalent leak shapes:

    - `model: None` (Python repr) → str "None"
    - `model: null` or `model: Null` → Python None
    - `model: ~` → Python None
    - `model:` (empty scalar) → Python None or missing
    """
    m = re.match(r"^---\n(.*?)\n---\n", rendered, re.DOTALL)
    if m is None:
        raise AssertionError(f"no frontmatter detected in rendered output:\n{rendered[:300]}")
    fm = yaml.safe_load(m.group(1))
    return fm.get("model") if isinstance(fm, dict) else None


def test_mv3_jinja_dispatcher_does_not_emit_model_none() -> None:
    """MV-3: When `claude_model` is in context but is None (user override that
    set only `cursor:` or `codex:`), the dispatcher template must NOT emit
    a None-equivalent value in `model:`. Verified by parsing the YAML
    frontmatter and asserting the model field is a non-empty concrete
    identifier (not Python None, not the literal string "None", not "").
    """
    from jinja2 import Environment, FileSystemLoader

    templates_dir = Path(__file__).resolve().parents[2] / "src" / "harness_maker" / "templates"
    env = Environment(loader=FileSystemLoader(str(templates_dir)))
    template = env.get_template("agents/autoloop-coder.md.j2")
    rendered = template.render(
        name="autoloop-coder",
        claude_model=None,
        codex_reasoning_effort="medium",
        reviewer_kind="",
        communication_variant="full",
    )
    model = _extract_model_from_frontmatter(rendered)
    # YAML-parse-based None checks — catch every None-equivalent leak shape.
    assert model is not None, (
        f"`model:` field is YAML null (None/null/~/empty). Rendered head:\n{rendered[:400]}"
    )
    assert isinstance(model, str), f"`model:` is not a string: {type(model).__name__}={model!r}"
    assert model.strip(), f"`model:` is empty after strip: {model!r}"
    # Catch Python's str(None) leaking through Jinja rendering of None value.
    assert model != "None", (
        f"`model:` is literal 'None' string (Jinja `is defined` None-bug). "
        f"Rendered head:\n{rendered[:400]}"
    )


# ──────────────────────────────────────────────────────────────────────────────
# CP-1 / R-1 — trajectory-monitor preset entries removed (dormant agent)
# ──────────────────────────────────────────────────────────────────────────────


def test_cp1_trajectory_monitor_absent_from_preset_maps() -> None:
    """CP-1 / R-1: trajectory-monitor is not in _ALL_AGENTS, _ALL_SKILLS, or
    _COMMUNICATION_VARIANT. Its preset map entries are unreachable dead data.
    They MUST be removed in Phase 5.
    """
    assert "trajectory-monitor" not in PRESET_AGENT_MODELS[Preset.PRODUCTION], (
        "trajectory-monitor still in _PRODUCTION_MAP — dead data per CP-1"
    )
    assert "trajectory-monitor" not in PRESET_AGENT_MODELS[Preset.SIDE], (
        "trajectory-monitor still in _SIDE_MAP — dead data per CP-1"
    )


def test_cp1_resolver_still_safe_for_trajectory_monitor_name() -> None:
    """After CP-1 removal, calling resolve_agent_spec('trajectory-monitor', config)
    must NOT KeyError — Tier 3 _spec_from_default_model fallback applies."""
    config = HarnessConfig(preset=Preset.PRODUCTION)
    spec = resolve_agent_spec("trajectory-monitor", config)
    # Tier 3 derives from default_model "claude-opus-4-7" → claude="opus"
    assert spec.claude == "opus"


# ──────────────────────────────────────────────────────────────────────────────
# CP-2 — _ALL_AGENTS ⊆ _COMMUNICATION_VARIANT structural symmetry
# ──────────────────────────────────────────────────────────────────────────────


def test_cp2_all_agents_subset_of_communication_variant() -> None:
    """CP-2: Every name in _ALL_AGENTS MUST have a matching entry in
    _COMMUNICATION_VARIANT. Otherwise _codex_agent_files()'s bare dict
    access at synthesize.py:325 raises KeyError at render time rather
    than test time.
    """
    all_agents = set(_ALL_AGENTS)
    variants = set(_COMMUNICATION_VARIANT.keys())
    missing = all_agents - variants
    assert not missing, (
        f"_ALL_AGENTS members missing from _COMMUNICATION_VARIANT: {sorted(missing)} "
        "— would KeyError in _codex_agent_files()"
    )


# ──────────────────────────────────────────────────────────────────────────────
# Cross-fix integration: render the full _agent_files context end-to-end
# for an agent override that only sets cursor (the C-2 trigger scenario).
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("cursor", "claude_model", "model_line"),
    [
        # A tier alias carries over, exactly as db19f023's `_alias_by_cursor_id` derived it.
        ("sonnet", "sonnet", "model: sonnet"),
        ("haiku", "haiku", "model: haiku"),
        # Anything else never named a Claude model: the template floor renders.
        ("some-concrete-id", None, "model: opus"),
    ],
)
def test_user_override_cursor_only_keeps_its_alias(
    cursor: str, claude_model: str | None, model_line: str
) -> None:
    """0.63.0 (SPEC-hm-overhaul-p1 AC-001, PR-C review round 1): a cursor-only override still
    picks the Claude model when it holds a tier alias.

    A user who writes `agent_models: {autoloop-coder: {cursor: sonnet}}` (no `claude:`) leaves
    spec.claude None. 0.62 rendered the Claude `model:` from that alias; dropping the fallback
    would move the agent to the template floor, so "T minus cursor" would not render the same.
    The `model:` line must stay valid (MV-3), never the bare `None` / `null`.
    """
    from jinja2 import Environment, FileSystemLoader

    from harness_maker.synthesize import _agent_files

    config = HarnessConfig(
        preset=Preset.PRODUCTION,
        agent_models={"autoloop-coder": AgentModelSpec(cursor=cursor)},
    )
    spec = resolve_agent_spec("autoloop-coder", config)
    assert spec.claude is None  # Tier-1 cursor-only override
    assert spec.cursor == cursor  # parsed and carried unnormalized

    ctx = next(
        c
        for tmpl, dst, c in _agent_files(preset=Preset.PRODUCTION, agent_models=config.agent_models)
        if dst == "agents/autoloop-coder.md"
    )
    assert ctx["claude_model"] == claude_model

    templates_dir = Path(__file__).resolve().parents[2] / "src" / "harness_maker" / "templates"
    env = Environment(loader=FileSystemLoader(str(templates_dir)))
    rendered = env.get_template("agents/autoloop-coder.md.j2").render(
        **ctx, communication_variant="full"
    )
    # MV-3: a valid non-empty model: line (not None/null/~/empty).
    assert _VALID_MODEL_LINE.search(rendered) is not None, (
        f"invalid model: line rendered; head:\n{rendered[:300]}"
    )
    assert f"\n{model_line}\n" in rendered


# Phase A.5 / B reference: pytest -k phase5_test_model_routing
# After fixes land, every assertion above must pass.
