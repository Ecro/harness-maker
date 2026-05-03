"""Synthesizer — map preset+answers to deterministic Blueprint with FileEntry list.

Per the new architecture every preset installs the FULL skill + agent inventory.
The harness.yaml `reviewers.enabled` and `skills.enabled` lists govern default
activation; users opt into more reviewers per-task via inline command flags.

Workflow command FileEntries are generated dynamically from
`answers.fused_workflows` (a typed `dict[name, list[AtomicStage]]`). The
`workflow_fuse.fuse(...)` helper produces the per-workflow body that the
`workflow_command.md.j2` template wraps.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from harness_maker.models import (
    AtomicStage,
    Blueprint,
    FileEntry,
    HarnessConfig,
    InterviewAnswers,
    Locale,
    Preset,
    ProjectProfile,
)
from harness_maker.workflow_fuse import fuse

# Each tuple: (template path under templates/, output path under .claude/, context supplement)
FileSpec = tuple[str, str, dict[str, Any]]

_ATOMIC_STAGES: list[str] = [s.value for s in AtomicStage]

# Every preset installs the full reviewer/skill inventory; activation is data,
# not file presence.
_ALL_AGENTS: list[str] = [
    "autoloop-coder",
    "code-reviewer",
    "concurrency-reviewer",
    "consensus-arbiter",
    "executor",
    "performance-reviewer",
    "security-auditor",
    "security-reviewer",
    "ux-reviewer",
]
_ALL_SKILLS: list[str] = [
    "agent-quality-rubric",
    "ai-readiness-rubric",
    "autoloop-driver",
    "conditional-router",
    "context-linter",
    "relevance-filter",
    "research-crawler",
    "security-scanner",
    "verify-before-completion",
    "worktree-isolator",
]


def _stage_files() -> list[FileSpec]:
    return [
        (
            f"stages/{s}.md.j2",
            f"stages/{s}.md",
            {"stage": s, "workflow_context": "", "project_name": "", "feature": ""},
        )
        for s in _ATOMIC_STAGES
    ]


def _atomic_command_files() -> list[FileSpec]:
    """Generate one /hm:<stage> command per atomic stage, with rendered body."""
    out: list[FileSpec] = []
    # Lazy import: avoid jinja env construction at module import time
    from harness_maker.render import _make_env

    env = _make_env()
    for s in _ATOMIC_STAGES:
        tpl = env.get_template(f"stages/{s}.md.j2")
        body = tpl.render(
            workflow_context="",
            stage=s,
            project_name="",
            feature="",
        )
        out.append(
            (
                "commands/hm/atomic_command.md.j2",
                f"commands/hm/{s}.md",
                {"stage": s, "stage_body": body},
            ),
        )
    return out


def _agent_files() -> list[FileSpec]:
    return [
        (f"agents/{n}.md.j2", f"agents/{n}.md", {"name": n}) for n in _ALL_AGENTS
    ]


def _skill_files() -> list[FileSpec]:
    return [
        (
            f"skills/{n}/SKILL.md.j2",
            f"skills/{n}/SKILL.md",
            {"name": n},
        )
        for n in _ALL_SKILLS
    ]


def _base_files(preset: Preset) -> list[FileSpec]:
    """Shared base: stages + atomic commands + all agents/skills + fixed assets.

    The only preset-dependent files are harness.yaml, settings.json, and
    CLAUDE.md (which currently share a Side/Production split per locale).
    """
    yaml_template = (
        "harness-yaml/Side.yaml.j2"
        if preset == Preset.SIDE
        else "harness-yaml/Production.yaml.j2"
    )
    settings_template = (
        "settings/Side.json.j2"
        if preset == Preset.SIDE
        else "settings/Production.json.j2"
    )
    return [
        (yaml_template, "harness.yaml", {}),
        (settings_template, "settings.json", {}),
        ("claude-md/Side.ko.md.j2", "../CLAUDE.md", {}),
        ("memory/failures.ko.md.j2", "memory/failures.md", {}),
        ("memory/wiki.ko.md.j2", "memory/wiki.md", {}),
        *_stage_files(),
        *_atomic_command_files(),
        ("commands/hm/loop.md.j2", "commands/hm/loop.md", {}),
        ("commands/hm/monitor.md.j2", "commands/hm/monitor.md", {}),
        ("commands/hm/refresh.md.j2", "commands/hm/refresh.md", {}),
        *_skill_files(),
        *_agent_files(),
        ("hooks/hooks.json.j2", "hooks/hooks.json", {}),
        ("observability/dashboard.ko.md.j2", "observability/dashboard.md", {}),
    ]


# Public skeletons retained for backwards-compat counts in tests; both presets
# now install the full inventory.
SIDE_FILES: list[FileSpec] = _base_files(Preset.SIDE)
PRODUCTION_FILES: list[FileSpec] = _base_files(Preset.PRODUCTION)


def _workflow_command_files(
    fused_workflows: dict[str, list[AtomicStage]],
) -> list[FileSpec]:
    """Build a FileSpec per workflow with the fused body in context."""
    out: list[FileSpec] = []
    for name, stages in fused_workflows.items():
        body = fuse(stages, name)
        out.append(
            (
                "commands/hm/workflow_command.md.j2",
                f"commands/hm/{name}.md",
                {"workflow_name": name, "fused_body": body},
            ),
        )
    return out


def synthesize(
    profile: ProjectProfile,
    answers: InterviewAnswers,
    preset: Preset | None = None,
) -> Blueprint:
    """Map preset+answers to a deterministic Blueprint.

    `preset` argument is honored if given; otherwise `answers.preset` wins.
    Workflow command FileEntries are generated from `answers.fused_workflows`.
    """
    effective_preset = preset or answers.preset
    base_specs = _base_files(effective_preset)

    file_specs: list[FileSpec] = [
        *base_specs,
        *_workflow_command_files(answers.fused_workflows),
    ]

    config = HarnessConfig(
        locale=Locale.KO,
        preset=effective_preset,
        workflows=dict(answers.fused_workflows),
        default_workflow=answers.default_workflow,
        caching=answers.caching,
        autoloop=answers.autoloop,
        memory=answers.memory,
        anti_rot=answers.anti_rot,
        worktree=answers.worktree,
        security=answers.security,
        context_lint=answers.context_lint,
        models=answers.models,
        reviewers={
            "installed": answers.reviewers.get("installed", []),
            "enabled": answers.reviewers.get("enabled", []),
            "consensus": answers.consensus,
        },
    )

    config_dump = config.model_dump(mode="json")
    # Skills inventory + enabled list aren't part of HarnessConfig today, but
    # templates need them; expose via per-file context.
    skills_dump = {
        "installed": answers.skills.get("installed", []),
        "enabled": answers.skills.get("enabled", []),
    }
    files = [
        FileEntry(
            path=Path(out_path),
            template=tpl,
            context={
                **ctx,
                "preset": effective_preset.value,
                "config": config_dump,
                "skills": skills_dump,
                "stack": profile.stack,
                "scale": profile.scale,
                "lifecycle": profile.lifecycle,
            },
            frontmatter={},
        )
        for tpl, out_path, ctx in file_specs
    ]
    return Blueprint(config=config, files=files)
