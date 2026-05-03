"""Synthesizer — map preset+answers to deterministic Blueprint with FileEntry list.

Per amendment §D, the synthesizer uses two hardcoded skeletons:
- SIDE_FILES → Side preset (~24 files + 1 workflow = 25 files)
- PRODUCTION_FILES → Production preset (~24 + 4 workflow + 7 skill + 8 agent = 43 files)

Phase 6 (this file): workflow command rendering is now DYNAMIC. Workflow command
FileEntries are generated from HarnessConfig.workflows at synthesis time, with
each entry's `fused_body` Jinja context computed via `workflow_fuse.fuse(...)`.
The static SIDE_FILES / PRODUCTION_FILES skeletons no longer encode workflow
names; the workflow loop in `synthesize()` appends them dynamically.
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

_ATOMIC_STAGES: list[str] = [
    "research",
    "spec",
    "plan",
    "execute",
    "review",
    "wrapup",
    "verify",
]

# Default stage sequence assigned to each workflow when the interview doesn't
# specialise it. Matches the architecture's "dev" recommendation.
_DEFAULT_WORKFLOW_STAGES: list[AtomicStage] = [
    AtomicStage.RESEARCH,
    AtomicStage.PLAN,
    AtomicStage.EXECUTE,
    AtomicStage.REVIEW,
    AtomicStage.WRAPUP,
]

# Preset-seeded workflow stage recipes (per architecture preset comparison).
_WORKFLOW_RECIPES: dict[str, list[AtomicStage]] = {
    "dev": [
        AtomicStage.PLAN,
        AtomicStage.EXECUTE,
        AtomicStage.REVIEW,
        AtomicStage.WRAPUP,
    ],
    "quick": [AtomicStage.EXECUTE],
    "careful": list(AtomicStage),
    "audit": [AtomicStage.REVIEW],
    "ship": [AtomicStage.EXECUTE, AtomicStage.REVIEW, AtomicStage.WRAPUP],
}


def _stages_for_workflow(name: str) -> list[AtomicStage]:
    return _WORKFLOW_RECIPES.get(name, _DEFAULT_WORKFLOW_STAGES)


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


# ──────────────────────────────────────────────────────────────────────────────
# Side skeleton (workflow commands appended dynamically in synthesize())
# ──────────────────────────────────────────────────────────────────────────────

SIDE_FILES: list[FileSpec] = [
    # 1 — harness.yaml
    ("harness-yaml/Side.yaml.j2", "harness.yaml", {}),
    # 2 — settings.json
    ("settings/Side.json.j2", "settings.json", {}),
    # 3 — CLAUDE.md (project root)
    ("claude-md/Side.ko.md.j2", "../CLAUDE.md", {}),
    # 4-5 — memory
    ("memory/failures.ko.md.j2", "memory/failures.md", {}),
    ("memory/wiki.ko.md.j2", "memory/wiki.md", {}),
    # 6-12 — stages (7)
    *_stage_files(),
    # 13-19 — atomic commands (7)
    *_atomic_command_files(),
    # 20-22 — fixed commands
    ("commands/hm/loop.md.j2", "commands/hm/loop.md", {}),
    ("commands/hm/monitor.md.j2", "commands/hm/monitor.md", {}),
    ("commands/hm/refresh.md.j2", "commands/hm/refresh.md", {}),
    # 23 — Side gets one skill
    (
        "skills/verify-before-completion/SKILL.md.j2",
        "skills/verify-before-completion/SKILL.md",
        {"name": "verify-before-completion"},
    ),
    # 24 — autoloop-driver skill (required by /hm:loop on every preset)
    (
        "skills/autoloop-driver/SKILL.md.j2",
        "skills/autoloop-driver/SKILL.md",
        {"name": "autoloop-driver"},
    ),
    # 25 — autoloop-coder agent (Side also exposes /hm:loop, so needs the worker)
    (
        "agents/autoloop-coder.md.j2",
        "agents/autoloop-coder.md",
        {"name": "autoloop-coder"},
    ),
    # 26 — ai-readiness-rubric (Health 6-dim — used by /hm:monitor on every preset)
    (
        "skills/ai-readiness-rubric/SKILL.md.j2",
        "skills/ai-readiness-rubric/SKILL.md",
        {"name": "ai-readiness-rubric"},
    ),
    # 27 — agent-quality-rubric (Bronze auto-flag — used by /hm:monitor everywhere)
    (
        "skills/agent-quality-rubric/SKILL.md.j2",
        "skills/agent-quality-rubric/SKILL.md",
        {"name": "agent-quality-rubric"},
    ),
    # 28 — Side gets one reviewer agent
    ("agents/code-reviewer.md.j2", "agents/code-reviewer.md", {"name": "code-reviewer"}),
    # 25 — hooks
    ("hooks/hooks.json.j2", "hooks/hooks.json", {}),
    # 26 — observability dashboard
    ("observability/dashboard.ko.md.j2", "observability/dashboard.md", {}),
]
# Side base = 26; +1 workflow (dev) → 27 files (in 25-30 range)


_PRODUCTION_SKILLS: list[str] = [
    "conditional-router",
    # ai-readiness-rubric + agent-quality-rubric are now in SIDE_FILES.
    "relevance-filter",
    "worktree-isolator",
    "security-scanner",
    "context-linter",
]

_PRODUCTION_AGENTS: list[str] = [
    "security-reviewer",
    "security-auditor",
    "performance-reviewer",
    "ux-reviewer",
    "concurrency-reviewer",
    "consensus-arbiter",
    # autoloop-coder is now in SIDE_FILES (every preset exposes /hm:loop).
    "executor",
]


PRODUCTION_FILES: list[FileSpec] = [
    *SIDE_FILES,
    # 7 extra skills
    *[(f"skills/{n}/SKILL.md.j2", f"skills/{n}/SKILL.md", {"name": n}) for n in _PRODUCTION_SKILLS],
    # 8 extra agents
    *[(f"agents/{n}.md.j2", f"agents/{n}.md", {"name": n}) for n in _PRODUCTION_AGENTS],
]
# Production base = 26 + 7 + 8 = 41; +4 workflows (dev/quick/careful/audit) → 45


def _workflow_command_files(
    workflow_names: list[str],
    workflows: dict[str, list[AtomicStage]],
) -> list[FileSpec]:
    """Build a FileSpec per workflow with the fused body in context."""
    out: list[FileSpec] = []
    for name in workflow_names:
        stages = workflows.get(name, _stages_for_workflow(name))
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

    If `preset` not given, derives from answers: 'single' consensus → Side, else Production.
    Workflow command FileEntries are generated dynamically from
    answers.workflow_names (per Phase 6 amendment §B).
    """
    if preset is None:
        preset = Preset.SIDE if answers.consensus == "single" else Preset.PRODUCTION

    base_specs = SIDE_FILES if preset == Preset.SIDE else PRODUCTION_FILES

    # Resolve per-workflow stage list from the preset recipe.
    workflows: dict[str, list[AtomicStage]] = {
        name: _stages_for_workflow(name) for name in answers.workflow_names
    }

    # Append dynamic workflow command FileSpecs to the static base.
    file_specs: list[FileSpec] = [
        *base_specs,
        *_workflow_command_files(answers.workflow_names, workflows),
    ]

    config = HarnessConfig(
        locale=Locale.KO,
        preset=preset,
        workflows=workflows,
        default_workflow=answers.default_workflow,
        caching=answers.caching,
        autoloop=answers.autoloop,
        memory=answers.memory,
        anti_rot=answers.anti_rot,
        worktree=answers.worktree,
        security=answers.security,
        context_lint=answers.context_lint,
        models=answers.models,
        reviewers={"list": answers.reviewers, "consensus": answers.consensus},
    )

    # Build a context payload that's stable across runs.
    config_dump = config.model_dump(mode="json")
    files = [
        FileEntry(
            path=Path(out_path),
            template=tpl,
            context={
                **ctx,
                "preset": preset.value,
                "config": config_dump,
                "stack": profile.stack,
                "scale": profile.scale,
                "lifecycle": profile.lifecycle,
            },
            frontmatter={},
        )
        for tpl, out_path, ctx in file_specs
    ]
    return Blueprint(config=config, files=files)
