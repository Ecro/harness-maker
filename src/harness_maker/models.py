"""Pydantic v2 data models for harness-maker (config, blueprint, profile, interview)."""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

# ──────────────────────────────────────────────────────────────────────────────
# Enums (string-valued)
# ──────────────────────────────────────────────────────────────────────────────


class Locale(str, Enum):  # noqa: UP042
    """Built-in locales with first-class i18n catalogs.

    The ``HarnessConfig.locale`` field is a free-text ``str`` (any tag accepted),
    so users can request locales we don't yet ship messages for. ``i18n.t()``
    silently falls back to English for unknown locales.
    """

    KO = "ko"
    EN = "en"


class Preset(str, Enum):  # noqa: UP042
    """Project preset that drives default reviewer set, workflows, and gates."""

    SIDE = "Side"
    PRODUCTION = "Production"


class DevMode(str, Enum):  # noqa: UP042
    """Development methodology — independent of preset depth.

    spec-driven enforces SPEC + tests via spec-gate hook; task-driven omits the
    spec-gate hook entirely. Any preset×dev_mode cross is allowed.
    """

    SPEC_DRIVEN = "spec-driven"
    TASK_DRIVEN = "task-driven"


class ModelTier(str, Enum):  # noqa: UP042
    """Claude model tiers referenced by config."""

    OPUS = "opus"
    SONNET = "sonnet"
    HAIKU = "haiku"


class AtomicStage(str, Enum):  # noqa: UP042
    """Seven atomic stages composable into named workflows."""

    RESEARCH = "research"
    SPEC = "spec"
    PLAN = "plan"
    EXECUTE = "execute"
    REVIEW = "review"
    WRAPUP = "wrapup"
    VERIFY = "verify"


# Slash-command-friendly abbreviations used to derive transparent fused workflow
# names like `exec-rev-wrap`. Joined with `-` so each stage stays visible.
STAGE_ABBREV: dict[AtomicStage, str] = {
    AtomicStage.RESEARCH: "res",
    AtomicStage.SPEC: "spec",
    AtomicStage.PLAN: "plan",
    AtomicStage.EXECUTE: "exec",
    AtomicStage.REVIEW: "rev",
    AtomicStage.WRAPUP: "wrap",
    AtomicStage.VERIFY: "ver",
}


def auto_workflow_name(stages: list[AtomicStage]) -> str:
    """Build a transparent slash-friendly name from stage abbreviations."""
    return "-".join(STAGE_ABBREV[s] for s in stages)


def _empty_install_enabled() -> dict[str, list[str]]:
    """Default factory: typed empty {installed: [], enabled: []}."""
    return {"installed": [], "enabled": []}


class ReconcileDecision(str, Enum):  # noqa: UP042
    """Brownfield reconcile decision per conflicting file."""

    KEEP = "keep"
    REPLACE = "replace"
    BOTH = "both"
    MERGE_BLOCK = "merge_block"  # block-marker-aware 3-way merge (user blocks preserved)


# ──────────────────────────────────────────────────────────────────────────────
# Leaf models (no forward refs)
# ──────────────────────────────────────────────────────────────────────────────


class ProjectProfile(BaseModel):
    """Profiler output describing detected project signals."""

    model_config = ConfigDict(strict=True, extra="forbid")

    stack: list[str] = Field(default_factory=lambda: ["unknown"])
    scale: str = "small"  # small | medium | large
    lifecycle: str = "experiment"  # experiment | active | maintenance
    existing_dotclaude: bool = False
    spec_only: bool = False
    vault_member: bool = False


class WorkflowDef(BaseModel):
    """User-named workflow consisting of a sequence of atomic stages."""

    model_config = ConfigDict(strict=True, extra="forbid")

    name: str = Field(pattern=r"^[a-z][a-z0-9-]{0,30}$", max_length=31)
    stages: list[AtomicStage]


class FileEntry(BaseModel):
    """One file to render (template + context + frontmatter); body_sha256 populated post-render."""

    model_config = ConfigDict(arbitrary_types_allowed=True, strict=True, extra="forbid")

    path: Path
    template: str
    context: dict[str, Any] = Field(default_factory=dict)
    frontmatter: dict[str, Any] = Field(default_factory=dict)
    body_sha256: str | None = None  # populated post-render


class ConflictItem(BaseModel):
    """Brownfield reconcile conflict between an existing file and a new blueprint file."""

    model_config = ConfigDict(arbitrary_types_allowed=True, strict=True, extra="forbid")

    path: Path
    decision: ReconcileDecision | None = None
    reason: str | None = None


class CrawlItem(BaseModel):
    """One refreshed item from a crawler source (Anthropic blog, GitHub releases, arxiv, OSV)."""

    model_config = ConfigDict(strict=True, extra="forbid")

    source: str  # "anthropic_blog" | "github_releases" | "arxiv" | "osv_dev"
    item_id: str  # URL or unique id
    title: str
    summary: str = ""
    published: str | None = None  # ISO date
    score: float = 0.0  # relevance score [0,1]
    metadata: dict[str, Any] = Field(default_factory=dict)


class Finding(BaseModel):
    """One security finding from any of the 5 security gates."""

    model_config = ConfigDict(strict=True, extra="forbid")

    severity: str  # "high" | "medium" | "low"
    category: str  # "secrets" | "permissions" | "hook_injection" | "cve" | "prompt_injection"
    file: str = ""
    line: int = 0
    evidence: str = ""
    fix: str = ""


# ──────────────────────────────────────────────────────────────────────────────
# Composite models
# ──────────────────────────────────────────────────────────────────────────────


class HarnessConfig(BaseModel):
    """harness.yaml schema — single source of truth for a project's harness."""

    model_config = ConfigDict(strict=True, extra="forbid")

    # Free-text locale tag. en/ko ship with built-in i18n catalogs; unknown
    # tags fall back to English in i18n.t().
    locale: str = "en"
    preset: Preset = Preset.SIDE
    dev_mode: DevMode = DevMode.SPEC_DRIVEN
    workflows: dict[str, list[AtomicStage]] = Field(
        default_factory=lambda: {
            "dev": [
                AtomicStage.RESEARCH,
                AtomicStage.PLAN,
                AtomicStage.EXECUTE,
                AtomicStage.REVIEW,
                AtomicStage.WRAPUP,
            ],
        },
    )
    default_workflow: str = "dev"
    execution: dict[str, Any] = Field(default_factory=dict)
    reviewers: dict[str, Any] = Field(default_factory=dict)
    caching: str = "agent-aware"
    hooks: dict[str, Any] = Field(default_factory=dict)
    memory: dict[str, Any] = Field(default_factory=dict)
    autoloop: dict[str, Any] = Field(default_factory=dict)
    anti_rot: dict[str, Any] = Field(default_factory=dict)
    dashboard: dict[str, Any] = Field(default_factory=dict)
    models: dict[str, Any] = Field(default_factory=dict)
    worktree: dict[str, Any] = Field(default_factory=dict)
    security: dict[str, Any] = Field(default_factory=dict)
    context_lint: dict[str, Any] = Field(default_factory=dict)
    project: dict[str, Any] = Field(default_factory=lambda: {"domains": []})
    spec: dict[str, Any] = Field(default_factory=lambda: {"dir": "specs/"})
    work_docs: dict[str, Any] = Field(default_factory=lambda: {"dir": "work-docs/"})


class Blueprint(BaseModel):
    """Synthesizer output: a full HarnessConfig plus the file list to render."""

    model_config = ConfigDict(arbitrary_types_allowed=True, strict=True, extra="forbid")

    config: HarnessConfig = Field(default_factory=HarnessConfig)
    files: list[FileEntry] = Field(default_factory=list)


class InterviewAnswers(BaseModel):
    """Typed interview output — replaces loose dict[str, Any]."""

    model_config = ConfigDict(strict=True, extra="forbid")

    locale: str = "en"
    preset: Preset = Preset.SIDE
    dev_mode: DevMode = DevMode.SPEC_DRIVEN
    domains: list[str] = Field(default_factory=list)
    # Map of user-named workflow → ordered atomic stages. Names are typically
    # auto-derived via STAGE_ABBREV (e.g. `exec-rev-wrap`) but user can override.
    fused_workflows: dict[str, list[AtomicStage]] = Field(
        default_factory=lambda: {
            "exec-rev-wrap": [
                AtomicStage.EXECUTE,
                AtomicStage.REVIEW,
                AtomicStage.WRAPUP,
            ],
        },
    )
    default_workflow: str = "exec-rev-wrap"
    # All reviewers/skills are installed regardless of preset; `enabled` lists
    # govern which ones the harness activates by default. Per-task override is
    # via inline flags on the workflow command (e.g. --with-reviewers=...).
    reviewers: dict[str, list[str]] = Field(
        default_factory=_empty_install_enabled,
    )
    skills: dict[str, list[str]] = Field(
        default_factory=_empty_install_enabled,
    )
    consensus: str = "single"  # 'single' | 'cross-check' | 'k-of-n'
    # Review-stage grade gate — see templates/stages/review.md.j2. Runtime
    # override via `--no-auto-fix` on the workflow command is prompt-driven
    # (no code path here).
    auto_fix: bool = True
    grade_threshold: str = "A"  # 'A' | 'B' | 'C'
    max_review_rounds: int = 3
    caching: str = "agent-aware"
    models: dict[str, Any] = Field(default_factory=dict)
    autoloop: dict[str, Any] = Field(default_factory=dict)
    memory: dict[str, Any] = Field(default_factory=dict)
    anti_rot: dict[str, Any] = Field(default_factory=dict)
    worktree: dict[str, Any] = Field(default_factory=dict)
    security: dict[str, Any] = Field(default_factory=dict)
    context_lint: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _default_workflow_in_fused(self) -> InterviewAnswers:
        if self.default_workflow not in self.fused_workflows:
            msg = (
                f"default_workflow={self.default_workflow!r} not in "
                f"fused_workflows={sorted(self.fused_workflows)}"
            )
            raise ValueError(msg)
        return self
