"""Workflow fuse — compose atomic stage fragments into a single workflow prompt.

Per Phase 6 amendment §B, `fuse(stages, workflow_name)` returns the FULL fused
prompt body. The renderer passes this body via the `fused_body` Jinja context
variable when rendering `commands/hm/<workflow_name>.md`.

`lint_workflow(...)` is an optional LLM second-pass that detects
contradictions between fused stages (e.g., a stage that says "auto-fix"
followed by a stage that says "manual confirm only"). Failures degrade
gracefully — the lint never raises, since a workflow with un-detected
contradictions is still better than a make that fails outright.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

from harness_maker.llm_judge import JudgeClient
from harness_maker.models import AtomicStage

if TYPE_CHECKING:
    from jinja2 import Environment


def fuse(
    stages: list[AtomicStage],
    workflow_name: str,
    env: Environment | None = None,
) -> str:
    """Fuse atomic stage fragments into a single workflow prompt body.

    Each fragment is rendered with `workflow_context=workflow_name` so the
    fragment can mention which workflow it's part of. Fragments are joined
    with a `## Stage: <name>` separator so the resulting prompt has clear
    section breaks.

    Returns:
        The full fused prompt body, with a leading `# /hm:<workflow>` header
        and one `## Stage: <name>` block per stage. An empty `stages` list
        returns just the header (no separator blocks).
    """
    if env is None:
        from harness_maker.render import _make_env  # local import: avoid cycle

        env = _make_env()

    from harness_maker.models import HarnessConfig
    from harness_maker.synthesize import _compute_install_ref

    default_config = HarnessConfig().model_dump(mode="json")
    install_ref = _compute_install_ref()

    parts: list[str] = [f"# /hm:{workflow_name}\n"]
    for stage in stages:
        tpl = env.get_template(f"stages/{stage.value}.md.j2")
        body = tpl.render(
            workflow_context=workflow_name,
            stage=stage.value,
            project_name="",
            feature="",
            config=default_config,
            harness_maker_src_path=install_ref,
            is_codex=False,
        )
        parts.append(f"\n## Stage: {stage.value}\n\n{body}")
    return "\n".join(parts)


# ── LLM contradiction lint ─────────────────────────────────────────────────


_LINT_TEXT_CAP = 16_000  # cost guard

_LINT_SYSTEM_PROMPT = """You audit fused workflow prompts for INTERNAL \
contradictions between stages.

A contradiction is when one stage says X and another stage says NOT-X for
the same workflow run. Examples:
  - Stage A: "auto-fix consensus findings"; Stage B: "never apply edits".
  - Stage A: "commit at phase boundaries"; Stage B: "do not commit".
  - Stage A: "always run tests"; Stage B: "skip tests on docs-only changes"
    that the surrounding flow does not branch on.

Trivial overlap (both stages mention reading PLAN.md) is NOT a
contradiction. Only flag concrete behavioural conflicts.

Output JSON ONLY:
{
  "contradictions": [
    {"between": ["<stage>", "<stage>"], "summary": "<one line>",
     "evidence": "<short quote>", "severity": "high|medium|low"}
  ]
}

Empty list = no contradictions detected."""


class Contradiction(BaseModel):
    """One LLM-flagged contradiction between fused stages."""

    model_config = ConfigDict(strict=True, extra="forbid")

    between: list[str]
    summary: str
    evidence: str
    severity: str  # high | medium | low


def _strip_markdown_fence(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        nl = stripped.find("\n")
        if nl != -1:
            stripped = stripped[nl + 1 :]
        if stripped.endswith("```"):
            stripped = stripped[:-3]
    return stripped.strip()


def _parse_lint_response(raw: str) -> list[Contradiction]:
    body = _strip_markdown_fence(raw)
    try:
        data = json.loads(body)
    except (json.JSONDecodeError, ValueError):
        return []
    if not isinstance(data, dict):
        return []
    raw_list = data.get("contradictions")
    if not isinstance(raw_list, list):
        return []
    out: list[Contradiction] = []
    for entry in raw_list:
        if not isinstance(entry, dict):
            continue
        try:
            out.append(Contradiction.model_validate(entry))
        except Exception:  # noqa: BLE001 — drop malformed entries silently
            continue
    return out


def lint_workflow(
    fused_body: str,
    workflow_name: str,
    *,
    client: JudgeClient,
    model: str = "claude-sonnet-4-6",
) -> list[Contradiction]:
    """Detect contradictions between fused stages of a workflow.

    Returns empty list on any LLM transport failure (lint must never block
    /hm:make). Caller decides whether to surface results to the user.
    """
    if not fused_body.strip():
        return []
    user = (
        f"Workflow: {workflow_name}\n\n"
        f"--- BEGIN FUSED BODY ---\n{fused_body[:_LINT_TEXT_CAP]}\n--- END FUSED BODY ---"
    )
    try:
        raw = client.judge(_LINT_SYSTEM_PROMPT, user, model)
    except Exception:  # noqa: BLE001 — degrade gracefully
        return []
    return _parse_lint_response(raw)
