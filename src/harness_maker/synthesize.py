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
    Preset,
    ProjectProfile,
    Target,
)
from harness_maker.workflow_fuse import fuse

# Each tuple: (template path under templates/, output path under .claude/, context supplement)
FileSpec = tuple[str, str, dict[str, Any]]

# Computed once — points to the directory containing pyproject.toml.
# Works both from the source repo and from the plugin cache.
_HARNESS_MAKER_PKG_ROOT = str(Path(__file__).parent.parent.parent)

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
    "plan-validator",
    "security-auditor",
    "security-reviewer",
    "stuck",
    "test-reviewer",
    "ux-reviewer",
]
_ALL_SKILLS: list[str] = [
    "agent-quality-rubric",
    "ai-readiness-rubric",
    "autoloop-driver",
    "conditional-router",
    "context-linter",
    "refdocs-search",
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
    from harness_maker.models import HarnessConfig
    from harness_maker.render import _make_env

    env = _make_env()
    default_config = HarnessConfig().model_dump(mode="json")
    for s in _ATOMIC_STAGES:
        tpl = env.get_template(f"stages/{s}.md.j2")
        body = tpl.render(
            workflow_context="",
            stage=s,
            project_name="",
            feature="",
            config=default_config,
            # stages/execute.md.j2 calls `python -m harness_maker.worktree`
            # via this absolute path baked into the rendered slash command.
            harness_maker_src_path=_HARNESS_MAKER_PKG_ROOT,
        )
        out.append(
            (
                "commands/hm/atomic_command.md.j2",
                f"commands/hm/{s}.md",
                {"stage": s, "stage_body": body},
            ),
        )
    return out


# Reviewer agents that include the partials in templates/agents/_partials/.
# `reviewer_kind` switches the schema partial on a per-reviewer basis so each
# agent emits its own specialty fields (category, race_kind, wcag_ref, …).
_REVIEWER_KIND: dict[str, str] = {
    "code-reviewer": "code",
    "security-reviewer": "security",
    "performance-reviewer": "performance",
    "concurrency-reviewer": "concurrency",
    "ux-reviewer": "ux",
}


def _agent_files() -> list[FileSpec]:
    return [
        (
            f"agents/{n}.md.j2",
            f"agents/{n}.md",
            {"name": n, "reviewer_kind": _REVIEWER_KIND.get(n, "")},
        )
        for n in _ALL_AGENTS
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


_ALL_RUBRICS: list[str] = ["claude_md", "agent_prompt", "skill", "workflow"]


def _rubric_files() -> list[FileSpec]:
    """Layer-2 rubric YAML data files for the LLM judge."""
    return [
        (
            f"rubrics/{n}.yaml.j2",
            f"rubrics/{n}.yaml",
            {"name": n},
        )
        for n in _ALL_RUBRICS
    ]


# Locales that ship with first-party prose templates. Anything else falls back
# to the English copy silently — matches `i18n.t()` fallback behavior in
# `models.Locale` so users get readable assets regardless of free-text tag.
_TEMPLATE_LOCALES: frozenset[str] = frozenset({"en", "ko"})


def _localized(stem: str, locale: str) -> str:
    """Pick `<stem>.<locale>.md.j2`, falling back to `.en` for unknown locales.

    Why: `harness.yaml.locale` is free-text (`models.HarnessConfig.locale`).
    Built-in catalogs only cover en/ko. Without this fallback an unknown
    locale (or a placeholder default) would resolve to a missing template
    file and the renderer would crash mid-blueprint.
    """
    suffix = locale if locale in _TEMPLATE_LOCALES else "en"
    return f"{stem}.{suffix}.md.j2"


def _base_files(preset: Preset, locale: str = "en") -> list[FileSpec]:
    """Shared base: stages + atomic commands + all agents/skills + fixed assets.

    Preset gates the structural variants (harness.yaml / settings.json /
    CLAUDE.md). Locale gates the prose-only templates (CLAUDE.md +
    memory/{failures,wiki}). Unknown locales silently fall back to en.
    """
    yaml_template = (
        "harness-yaml/Side.yaml.j2" if preset == Preset.SIDE else "harness-yaml/Production.yaml.j2"
    )
    settings_template = (
        "settings/Side.json.j2" if preset == Preset.SIDE else "settings/Production.json.j2"
    )
    claude_md_stem = "claude-md/Side" if preset == Preset.SIDE else "claude-md/Production"
    return [
        (yaml_template, "harness.yaml", {}),
        (settings_template, "settings.json", {}),
        (_localized(claude_md_stem, locale), "../CLAUDE.md", {}),
        (_localized("memory/failures", locale), "memory/failures.md", {}),
        (_localized("memory/wiki", locale), "memory/wiki.md", {}),
        ("memory/session-readme.md.j2", "memory/session/README.md", {}),
        *_stage_files(),
        *_atomic_command_files(),
        ("commands/hm/loop.md.j2", "commands/hm/loop.md", {}),
        ("commands/hm/ai-readiness.md.j2", "commands/hm/ai-readiness.md", {}),
        ("commands/hm/refresh.md.j2", "commands/hm/refresh.md", {}),
        ("commands/hm/make.md.j2", "commands/hm/make.md", {}),
        ("commands/hm/configure.md.j2", "commands/hm/configure.md", {}),
        ("commands/hm/uninstall.md.j2", "commands/hm/uninstall.md", {}),
        *_skill_files(),
        *_agent_files(),
        *_rubric_files(),
        ("hooks/hooks.json.j2", "hooks/hooks.json", {}),
        ("observability/dashboard.md.j2", "observability/dashboard.md", {}),
    ]


# Public skeletons retained for backwards-compat counts in tests; both presets
# now install the full inventory. These default to en — locale-specific
# fan-out is exercised through synthesize() at request time.
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


def _cursor_target_files() -> list[FileSpec]:
    """Cursor target 전용 자산 — ``targets`` 에 cursor 포함 시에만 추가.

    **Hooks 정정 (PLAN-cursor-rootcause.md R1.A/B/C/D)**: Cursor IDE 는
    ``.claude/hooks/hooks.json`` 을 안 읽음. 2.4 changelog 의 "Claude Code
    hooks 호환" 은 CLI 한정. IDE 는 ``.cursor/hooks.json`` 만 봄. 또 schema 가
    camelCase (``preToolUse`` 등) — PascalCase 는 silent ignore. 따라서 cursor
    target 일 때는 **별도 렌더**:

    - ``.cursor/rules/harness.mdc`` — Cursor IDE-rules (alwaysApply: true)
    - ``.cursor/hooks.json`` — Cursor camelCase hooks + PATH wrap (R1.D 방어)
    - ``.cursor/mcp.json`` — Cursor MCP 서버 정의 (pure JSON)

    Agents / skills 는 여전히 single-source ``.claude/`` (Cursor 2.4+ 가
    ``.claude/skills/`` / ``.claude/agents/`` 를 native 호환 — Cursor docs
    공식 명시).
    """
    return [
        (
            "cursor/rules/harness.mdc.j2",
            ".cursor/rules/harness.mdc",
            {},
        ),
        (
            "cursor/hooks.json.j2",
            ".cursor/hooks.json",
            {},
        ),
        (
            "cursor/mcp.json.j2",
            ".cursor/mcp.json",
            {},
        ),
    ]


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
    base_specs = _base_files(effective_preset, answers.locale)

    file_specs: list[FileSpec] = [
        *base_specs,
        *_workflow_command_files(answers.fused_workflows),
    ]

    if Target.CURSOR in answers.targets:
        file_specs.extend(_cursor_target_files())

    config = HarnessConfig(
        locale=answers.locale,
        targets=list(answers.targets),
        preset=effective_preset,
        dev_mode=answers.dev_mode,
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
            "verbosity": "standard",
            "auto_fix": answers.auto_fix,
            "grade_threshold": answers.grade_threshold,
            "max_review_rounds": answers.max_review_rounds,
            "mechanical_checks": list(answers.mechanical_checks),
        },
        project={"domains": list(answers.domains)},
        spec={"dir": "specs/"},
        work_docs={"dir": "work-docs/"},
        ref_folders=list(answers.ref_folders),
        sibling_repos=list(answers.sibling_repos),
        mcp_servers=dict(answers.mcp_servers),
        wrapup_docs=list(answers.wrapup_docs),
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
                "harness_maker_src_path": _HARNESS_MAKER_PKG_ROOT,
            },
            frontmatter={},
        )
        for tpl, out_path, ctx in file_specs
    ]
    return Blueprint(config=config, files=files)
