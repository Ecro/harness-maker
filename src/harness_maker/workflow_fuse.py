"""Workflow fuse — compose atomic stage fragments into a single workflow prompt.

Per Phase 6 amendment §B, `fuse(stages, workflow_name)` returns the FULL fused
prompt body. The renderer passes this body via the `fused_body` Jinja context
variable when rendering `commands/hm/<workflow_name>.md`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

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

    default_config = HarnessConfig().model_dump(mode="json")

    parts: list[str] = [f"# /hm:{workflow_name}\n"]
    for stage in stages:
        tpl = env.get_template(f"stages/{stage.value}.md.j2")
        body = tpl.render(
            workflow_context=workflow_name,
            stage=stage.value,
            project_name="",
            feature="",
            config=default_config,
        )
        parts.append(f"\n## Stage: {stage.value}\n\n{body}")
    return "\n".join(parts)
