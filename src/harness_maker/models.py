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
    """Supported user-facing locales."""

    KO = "ko"
    EN = "en"


class Preset(str, Enum):  # noqa: UP042
    """Project preset that drives default reviewer set, workflows, and gates."""

    SIDE = "Side"
    PRODUCTION = "Production"


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


class ReconcileDecision(str, Enum):  # noqa: UP042
    """Brownfield reconcile decision per conflicting file."""

    KEEP = "keep"
    REPLACE = "replace"
    BOTH = "both"


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
    """One file to render or already rendered (path + provenance metadata)."""

    model_config = ConfigDict(arbitrary_types_allowed=True, strict=True, extra="forbid")

    path: Path
    sha256: str = ""
    rendered_from: str | None = None
    provenance: dict[str, Any] = Field(default_factory=dict)


class ConflictItem(BaseModel):
    """Brownfield reconcile conflict between an existing file and a new blueprint file."""

    model_config = ConfigDict(arbitrary_types_allowed=True, strict=True, extra="forbid")

    existing_path: Path
    new_path: Path
    decision: ReconcileDecision | None = None


# ──────────────────────────────────────────────────────────────────────────────
# Composite models
# ──────────────────────────────────────────────────────────────────────────────


class HarnessConfig(BaseModel):
    """harness.yaml schema — single source of truth for a project's harness."""

    model_config = ConfigDict(strict=True, extra="forbid")

    locale: Locale = Locale.KO
    preset: Preset = Preset.SIDE
    workflows: list[WorkflowDef] = Field(default_factory=list)
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


class Blueprint(BaseModel):
    """Synthesizer output: a full HarnessConfig plus the file list to render."""

    model_config = ConfigDict(arbitrary_types_allowed=True, strict=True, extra="forbid")

    config: HarnessConfig = Field(default_factory=HarnessConfig)
    files: list[FileEntry] = Field(default_factory=list)


class InterviewAnswers(BaseModel):
    """Typed interview output — replaces loose dict[str, Any]."""

    model_config = ConfigDict(strict=True, extra="forbid")

    workflow_names: list[str] = Field(default_factory=lambda: ["dev"])
    default_workflow: str = "dev"
    reviewers: list[str] = Field(default_factory=list)
    consensus: str = "single"  # 'single' | 'cross-check' | 'k-of-n'
    caching: str = "agent-aware"
    models: dict[str, Any] = Field(default_factory=dict)
    autoloop: dict[str, Any] = Field(default_factory=dict)
    memory: dict[str, Any] = Field(default_factory=dict)
    anti_rot: dict[str, Any] = Field(default_factory=dict)
    worktree: dict[str, Any] = Field(default_factory=dict)
    security: dict[str, Any] = Field(default_factory=dict)
    context_lint: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _default_workflow_in_names(self) -> InterviewAnswers:
        if self.default_workflow not in self.workflow_names:
            msg = (
                f"default_workflow={self.default_workflow!r} not in "
                f"workflow_names={self.workflow_names}"
            )
            raise ValueError(msg)
        return self
