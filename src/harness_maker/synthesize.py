"""Synthesizer — map preset+answers to deterministic Blueprint with FileEntry list.

Per amendment §D, the synthesizer uses two hardcoded mappings:
- SIDE_FILES → Side preset (~27 files, must land in 25-30 range)
- PRODUCTION_FILES → Production preset (~45 files, must land in 35-45 range)

The mapping is intentionally explicit (no logic-driven file selection in Phase 3)
so that the snapshot tests are stable. Phase 6/7 will add dynamic selection.
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


def _stage_files() -> list[FileSpec]:
    return [(f"stages/{s}.md.j2", f"stages/{s}.md", {"stage": s}) for s in _ATOMIC_STAGES]


def _atomic_command_files() -> list[FileSpec]:
    return [
        ("commands/hm/atomic_command.md.j2", f"commands/hm/{s}.md", {"stage": s})
        for s in _ATOMIC_STAGES
    ]


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
    # 20 — single workflow command
    ("commands/hm/workflow_command.md.j2", "commands/hm/dev.md", {"workflow_name": "dev"}),
    # 21-23 — fixed commands
    ("commands/hm/loop.md.j2", "commands/hm/loop.md", {}),
    ("commands/hm/monitor.md.j2", "commands/hm/monitor.md", {}),
    ("commands/hm/refresh.md.j2", "commands/hm/refresh.md", {}),
    # 24 — Side gets one skill
    (
        "skills/verify-before-completion/SKILL.md.j2",
        "skills/verify-before-completion/SKILL.md",
        {"name": "verify-before-completion"},
    ),
    # 25 — Side gets one agent
    ("agents/code-reviewer.md.j2", "agents/code-reviewer.md", {"name": "code-reviewer"}),
    # 26 — hooks
    ("hooks/hooks.json.j2", "hooks/hooks.json", {}),
    # 27 — observability dashboard
    ("observability/dashboard.ko.md.j2", "observability/dashboard.md", {}),
]
# Side total = 27 (in 25-30 range)


_PRODUCTION_SKILLS: list[str] = [
    "conditional-router",
    "ai-readiness-rubric",
    "agent-quality-rubric",
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
    "autoloop-coder",
    "executor",
]


PRODUCTION_FILES: list[FileSpec] = [
    *SIDE_FILES,
    # 3 extra workflow commands
    ("commands/hm/workflow_command.md.j2", "commands/hm/quick.md", {"workflow_name": "quick"}),
    (
        "commands/hm/workflow_command.md.j2",
        "commands/hm/careful.md",
        {"workflow_name": "careful"},
    ),
    ("commands/hm/workflow_command.md.j2", "commands/hm/audit.md", {"workflow_name": "audit"}),
    # 7 extra skills
    *[
        (f"skills/{n}/SKILL.md.j2", f"skills/{n}/SKILL.md", {"name": n})
        for n in _PRODUCTION_SKILLS
    ],
    # 8 extra agents
    *[(f"agents/{n}.md.j2", f"agents/{n}.md", {"name": n}) for n in _PRODUCTION_AGENTS],
]
# Production total = 27 + 3 + 7 + 8 = 45 (in 35-45 range)


def synthesize(
    profile: ProjectProfile,
    answers: InterviewAnswers,
    preset: Preset | None = None,
) -> Blueprint:
    """Map preset+answers to a deterministic Blueprint.

    If `preset` not given, derives from answers: 'single' consensus → Side, else Production.
    Phase 3 hardcodes locale=KO; Phase 6 will read from answers.
    """
    if preset is None:
        preset = Preset.SIDE if answers.consensus == "single" else Preset.PRODUCTION

    file_specs = SIDE_FILES if preset == Preset.SIDE else PRODUCTION_FILES

    # Workflow dict: derive from answers.workflow_names; for now use a fixed stage list.
    default_stages = [
        AtomicStage.RESEARCH,
        AtomicStage.PLAN,
        AtomicStage.EXECUTE,
        AtomicStage.REVIEW,
        AtomicStage.WRAPUP,
    ]
    workflows: dict[str, list[AtomicStage]] = dict.fromkeys(answers.workflow_names, default_stages)

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
