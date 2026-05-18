"""Pydantic v2 data models for harness-maker (config, blueprint, profile, interview)."""

from __future__ import annotations

import re
from enum import Enum
from pathlib import Path
from typing import Any, Literal

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    field_validator,
    model_validator,
)

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


class Target(str, Enum):  # noqa: UP042
    """IDE target — which IDE(s) the rendered harness must work in.

    Drives whether ``.cursor/rules/``, ``.cursor/commands/``, ``.cursor/mcp.json``
    are rendered alongside the shared ``.claude/`` assets. preset/dev_mode 와
    직교; 인터뷰에서 명시 multi-select 강제. 옛 yaml fallback 은
    ``HarnessConfig._targets_schema_gap_fallback`` validator 가 처리.
    """

    CLAUDE_CODE = "claude-code"
    CURSOR = "cursor"
    CODEX = "codex"


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


class Confidence(str, Enum):  # noqa: UP042
    """Bucketed confidence for personalization recommendations.

    ADR-004/007: exactly three buckets, no float scale, no user-tunable
    thresholds. Per-detection convention — explicit manifest match → HIGH;
    inferred from dep name → MEDIUM; pure guess → LOW.

    Phase 3 cross-reference: presence-only detection maps a dep-name match
    directly to HIGH (identity mapping — the manifest *says* the framework
    is a dep). MEDIUM is reserved for genuinely opinion/inference mappings
    introduced in Phase 4+ (e.g. dep-name → architectural style). LOW
    applies when nothing was detected at all.
    """

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


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
    detected_checks: list[str] = Field(default_factory=list)
    # Phase 1 (personalization-depth): richer detection signals feeding the
    # recommendation framework. All defaults empty so older serialized profiles
    # still validate via Field defaults (CLAUDE.md §6 reverse-mapper rule).
    frameworks: list[str] = Field(default_factory=list)
    package_manager: str = ""
    ci_provider: str = ""
    foreign_ai_configs: list[str] = Field(default_factory=list)
    detection_confidence: dict[str, Confidence] = Field(default_factory=dict)

    @field_validator("foreign_ai_configs", mode="before")
    @classmethod
    def _reject_absolute_foreign_ai_paths(cls, v: object) -> object:
        """Sibling-validator mirror: foreign-AI-config paths must be repo-relative."""
        if not isinstance(v, list):
            return v
        for p in v:
            if isinstance(p, str) and (Path(p).is_absolute() or p.startswith("~")):
                raise ValueError(
                    f"foreign_ai_configs must contain relative paths; got absolute: {p!r}"
                )
        return v


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


class RefFolder(BaseModel):
    """User-registered reference document folder for skill-driven search.

    Path is stored as free-text str (not Path) so harness.yaml stays portable
    across machines — relative paths like ``../shared-architecture`` survive
    git commits. Existence/glob validation is performed at registration time
    in interview.py, not here.
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    path: str
    glob: str = "**/*.{md,txt,pdf}"


class SecondBrainNoteType(str, Enum):  # noqa: UP042
    """Managed Obsidian Second Brain note types."""

    DECISION = "decision"
    PREFERENCE = "preference"
    FAILURE = "failure"
    PROJECT = "project"
    REFERENCE = "reference"
    JOURNAL = "journal"


def _default_second_brain_note_types() -> list[SecondBrainNoteType]:
    return list(SecondBrainNoteType)


class SecondBrainFolder(BaseModel):
    """One Obsidian vault folder allowlist entry.

    Folder paths are relative to ``SecondBrainConfig.vault_path``. Absolute
    folder paths would bypass the vault boundary and are rejected.
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    path: str
    read: bool = True
    write: bool = False
    note_types: list[SecondBrainNoteType] = Field(
        default_factory=_default_second_brain_note_types,
        min_length=1,
    )

    @field_validator("path")
    @classmethod
    def _reject_absolute_or_empty_path(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("second_brain folder path cannot be empty")
        if Path(cleaned).is_absolute() or cleaned.startswith("~"):
            raise ValueError("second_brain folder path must be relative to vault_path")
        # Block `..` traversal — otherwise a folder path with parent-dir segments
        # could be persisted into harness.yaml and used as a runtime allowlist root
        # outside the vault boundary (REVIEW-2026-05-17 security finding).
        if ".." in Path(cleaned).parts:
            raise ValueError("second_brain folder path must not contain '..' segments")
        return cleaned

    @field_validator("note_types", mode="before")
    @classmethod
    def _parse_note_types(cls, v: object) -> object:
        """Allow YAML/JSON string values while keeping the model strict elsewhere."""
        if not isinstance(v, list):
            return v
        out: list[SecondBrainNoteType] = []
        for item in v:
            if isinstance(item, SecondBrainNoteType):
                out.append(item)
                continue
            if isinstance(item, str):
                out.append(SecondBrainNoteType(item))
                continue
            out.append(item)
        return out


class SecondBrainConfig(BaseModel):
    """Obsidian Second Brain configuration.

    The first backend is intentionally filesystem-only. Vault paths may be
    absolute because personal Obsidian vaults often live outside the repo.
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    enabled: bool = False
    backend: str = "filesystem"
    project_id: str = ""
    vault_path: str = ""
    trusted_allowlist: bool = True
    folders: list[SecondBrainFolder] = Field(default_factory=list)
    required_frontmatter: list[str] = Field(
        default_factory=lambda: ["type", "created", "updated", "tags", "links"],
    )

    @field_validator("backend")
    @classmethod
    def _filesystem_backend_only(cls, v: str) -> str:
        if v != "filesystem":
            raise ValueError("second_brain backend must be 'filesystem'")
        return v

    @field_validator("project_id")
    @classmethod
    def _project_id_slug(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            return ""
        if not re.fullmatch(r"[a-z][a-z0-9-]{0,63}", cleaned):
            raise ValueError("second_brain project_id must be kebab-case")
        return cleaned

    @model_validator(mode="after")
    def _write_folders_are_project_namespaced(self) -> SecondBrainConfig:
        write_folders = [f for f in self.folders if f.write]
        if not write_folders:
            return self
        if not self.project_id:
            raise ValueError("second_brain.project_id is required when any folder has write=true")
        for folder in write_folders:
            if self.project_id not in Path(folder.path).parts:
                raise ValueError(
                    "writable second_brain folder paths must include project_id "
                    f"{self.project_id!r} as a path segment"
                )
        return self


class RecommendationEvidence(BaseModel):
    """Reused by personalization-audit (Phase 10) — evidence schema is contract.

    ADR-011: ``confidence`` is mirrored from the parent Recommendation so the
    evidence record stands alone in audit logs / Second Brain decision notes.
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    n_observations: int = 0
    top_3_signals: list[str] = Field(default_factory=list, max_length=3)
    confidence: Confidence


class Recommendation(BaseModel):
    """One recommendation produced by a per-axis recommender.

    ADR-011: ``signal`` is the one-line human-readable "why" — emitted as a
    yaml comment only when the bucket is HIGH (Phase 3+ writes harness.yaml).
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    axis: str
    value: Any
    confidence: Confidence
    evidence: RecommendationEvidence
    signal: str = ""

    @model_validator(mode="after")
    def _confidence_must_mirror_evidence(self) -> Recommendation:
        if self.confidence != self.evidence.confidence:
            raise ValueError(
                f"Recommendation.confidence ({self.confidence}) must equal "
                f"evidence.confidence ({self.evidence.confidence}); ADR-011 mirror invariant"
            )
        return self


class AdaptiveConfig(BaseModel):
    """Adaptive personalization knobs (telemetry + audit thresholds).

    ADR-005: opt-out default for telemetry (``disable_telemetry=False`` means
    telemetry is on); audit triggers after 30 sessions or 14 days, whichever
    fires first. Wired into HarnessConfig.adaptive.
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    disable_telemetry: bool = False
    audit_session_threshold: int = Field(default=30, gt=0)
    audit_days_threshold: int = Field(default=14, gt=0)


# ──────────────────────────────────────────────────────────────────────────────
# Per-agent model routing (ADR-001/002/003 from PLAN-model-routing-multi-ide)
# ──────────────────────────────────────────────────────────────────────────────


class CodexAgentSpec(BaseModel):
    """Codex-side per-agent routing knobs.

    ``model`` ``None`` means "inherit ~/.codex/config.toml default" (preferred
    on ChatGPT-tier accounts which reject most explicit Codex IDs — see
    RESEARCH-codex-plan-validator-model-unavailable). ``reasoning_effort`` is
    the dominant cost lever on reasoning models.
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    model: str | None = None
    reasoning_effort: Literal["none", "minimal", "low", "medium", "high", "xhigh"] | None = None


_MODEL_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_.:-]+$")


class AgentModelSpec(BaseModel):
    """Per-agent override carrying optional Claude / Cursor / Codex values.

    ADR-003 R5: ``cursor`` accepts either an alias key (``opus``/``sonnet``/
    ``haiku``) or a concrete model ID (``claude-4-7-opus``). Alias-form is
    normalized to concrete ID at render boundary by ``presets.resolve_agent_spec``.

    Security: ``claude``/``cursor`` values flow into Jinja2-rendered YAML
    frontmatter (``model: {{ claude_model }}``); a field_validator enforces a
    strict character set [a-zA-Z0-9_.:-] to prevent YAML-injection via embedded
    newlines / colons / hash signs (review security-reviewer P0/P1 fix).
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    claude: str | None = None
    cursor: str | None = None
    codex: CodexAgentSpec | None = None

    @field_validator("claude", "cursor")
    @classmethod
    def _validate_model_id_chars(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if not _MODEL_ID_PATTERN.fullmatch(v):
            raise ValueError(
                f"model id must match [a-zA-Z0-9_.:-]+ (got {v!r}) — "
                "embedded YAML-significant characters are rejected to prevent "
                "frontmatter injection"
            )
        return v


# ──────────────────────────────────────────────────────────────────────────────
# Composite models
# ──────────────────────────────────────────────────────────────────────────────


class HarnessConfig(BaseModel):
    """harness.yaml schema — single source of truth for a project's harness."""

    # populate_by_name=True lets `recommended_model` (old) and `default_model`
    # (new canonical, ADR-002) both populate the field via AliasChoices below.
    model_config = ConfigDict(strict=True, extra="forbid", populate_by_name=True)

    # Free-text locale tag. en/ko ship with built-in i18n catalogs; unknown
    # tags fall back to English in i18n.t().
    locale: str = "en"
    # IDE target multi-select. 새 인터뷰는 multi-select 답변을 받음 (빈 입력은
    # default [claude-code] 선택). 옛 yaml load 시 yaml-aware loader
    # (interview._parse_targets) 가 [claude-code] fallback + 경고 로그 — 옛
    # yaml 으로부터의 추론 금지. 빈 list 직접 입력은 min_length=1 이 거부.
    targets: list[Target] = Field(
        default_factory=lambda: [Target.CLAUDE_CODE],
        min_length=1,
    )
    # ADR-002: floor fallback model. Renamed from `recommended_model` (which
    # remains a read-side property below and a validation alias for old
    # harness.yaml files — ADR-004 silent migration).
    default_model: str = Field(
        default="claude-opus-4-7",
        validation_alias=AliasChoices("default_model", "recommended_model"),
    )
    # ADR-001/002: per-agent override map. Empty default → preset map applies
    # via presets.resolve_agent_spec (ADR-005 3-tier chain).
    agent_models: dict[str, AgentModelSpec] = Field(default_factory=dict)
    preset: Preset = Preset.SIDE

    @model_validator(mode="before")
    @classmethod
    def _migrate_recommended_model_dual_key(cls, data: object) -> object:
        """ADR-004 silent migration: if both `default_model` and the deprecated
        `recommended_model` are present in the input dict, `default_model` wins
        and `recommended_model` is silently dropped (instead of raising
        extra_forbidden). Required because AliasChoices alone treats the
        non-chosen key as an extra field under `extra="forbid"`.
        """
        if isinstance(data, dict) and "default_model" in data and "recommended_model" in data:
            data = {k: v for k, v in data.items() if k != "recommended_model"}
        return data

    @field_validator("default_model")
    @classmethod
    def _validate_default_model_chars(cls, v: str) -> str:
        """Security: default_model reaches Jinja2-rendered configs (aider, claude
        frontmatter, etc.) without escaping. Enforce safe character set to block
        YAML / config injection (review security-reviewer P0 fix)."""
        if not _MODEL_ID_PATTERN.fullmatch(v):
            raise ValueError(
                f"default_model must match [a-zA-Z0-9_.:-]+ (got {v!r}) — "
                "embedded YAML-significant characters are rejected to prevent "
                "rendered-config injection"
            )
        return v

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
    ref_folders: list[RefFolder] = Field(default_factory=list)
    second_brain: SecondBrainConfig = Field(default_factory=SecondBrainConfig)
    # MCP servers — propagated to .cursor/mcp.json (and future .claude/.mcp.json).
    # Shape: {"server-name": {"command": "...", "args": [...], "env": {...}}}.
    # Users add manually to harness.yaml; preserved across re-render via
    # answers_from_harness_yaml. No interview question yet.
    mcp_servers: dict[str, dict[str, Any]] = Field(default_factory=dict)
    # Sibling repos that are part of the same logical project. Relative paths
    # only (absolute paths break cross-machine portability — same policy as
    # RefFolder). Resolved against primary repo root at worktree create time.
    sibling_repos: list[str] = Field(default_factory=list)
    wrapup_docs: list[str] = Field(default_factory=list)
    # Adaptive personalization knobs (Phase 1 of personalization-depth).
    # default_factory keeps old harness.yaml files (no `adaptive:` key) loading.
    adaptive: AdaptiveConfig = Field(default_factory=AdaptiveConfig)
    # ADR-011: schema_version bumped 1 → 2 for the agent_models/default_model
    # rename. ADR-004 silent migration handles existing v1 harness.yaml.
    schema_version: int = 2
    interview: dict[str, Any] = Field(
        default_factory=lambda: {
            "deep_gate": {"max_rounds": 3, "streak_target": 2},
            "main_loop": {"max_rounds": None},
        }
    )

    @field_validator("sibling_repos", mode="before")
    @classmethod
    def _reject_absolute_sibling_paths(cls, v: object) -> object:
        """Relative paths survive cross-machine git clones; absolute paths do not.

        Rejects both /abs/path and ~/home-relative paths — neither survives a
        clone to a machine with a different directory layout.
        """
        if not isinstance(v, list):
            return v
        for p in v:
            if isinstance(p, str) and (Path(p).is_absolute() or p.startswith("~")):
                raise ValueError(f"sibling_repos must contain relative paths; got absolute: {p!r}")
        return v

    @computed_field  # type: ignore[prop-decorator]
    @property
    def recommended_model(self) -> str:
        """Read-side back-compat — deprecated, slated for removal in 0.17.0 per
        ADR-012. computed_field (not plain @property) so Jinja2 templates that
        access ``config.recommended_model`` via ``model_dump()`` dicts continue
        to resolve until templates are migrated to ``default_model`` in Phase 3.
        """
        return self.default_model


class Blueprint(BaseModel):
    """Synthesizer output: a full HarnessConfig plus the file list to render."""

    model_config = ConfigDict(arbitrary_types_allowed=True, strict=True, extra="forbid")

    config: HarnessConfig = Field(default_factory=HarnessConfig)
    files: list[FileEntry] = Field(default_factory=list)


class InterviewAnswers(BaseModel):
    """Typed interview output — replaces loose dict[str, Any]."""

    # populate_by_name=True lets the deprecated `recommended_model` key
    # still construct InterviewAnswers (per ADR-004 silent migration).
    model_config = ConfigDict(strict=True, extra="forbid", populate_by_name=True)

    locale: str = "en"
    # IDE target multi-select (preset/dev_mode 와 직교). 빈 list 거부 (min_length=1).
    # 인터뷰 default 는 [claude-code]; cursor 는 명시 multi-select.
    targets: list[Target] = Field(
        default_factory=lambda: [Target.CLAUDE_CODE],
        min_length=1,
    )
    # ADR-002 mirror of HarnessConfig.default_model. AliasChoices accepts both
    # the new canonical name and the old `recommended_model` key.
    default_model: str = Field(
        default="claude-opus-4-7",
        validation_alias=AliasChoices("default_model", "recommended_model"),
    )
    # ADR-001/002 mirror.
    agent_models: dict[str, AgentModelSpec] = Field(default_factory=dict)
    preset: Preset = Preset.SIDE

    @model_validator(mode="before")
    @classmethod
    def _migrate_recommended_model_dual_key(cls, data: object) -> object:
        """Mirror of HarnessConfig validator — same ADR-004 silent migration.
        Required for InterviewAnswers.model_validate paths that originate from
        load_harness_yaml() in Phase 2 (dual-key inputs would raise
        extra_forbidden without this guard)."""
        if isinstance(data, dict) and "default_model" in data and "recommended_model" in data:
            data = {k: v for k, v in data.items() if k != "recommended_model"}
        return data

    @field_validator("default_model")
    @classmethod
    def _validate_default_model_chars(cls, v: str) -> str:
        """Mirror of HarnessConfig: enforce safe character set to block injection."""
        if not _MODEL_ID_PATTERN.fullmatch(v):
            raise ValueError(
                f"default_model must match [a-zA-Z0-9_.:-]+ (got {v!r}) — "
                "embedded YAML-significant characters are rejected to prevent "
                "rendered-config injection"
            )
        return v

    dev_mode: DevMode = DevMode.SPEC_DRIVEN
    domains: list[str] = Field(default_factory=list)
    ref_folders: list[RefFolder] = Field(default_factory=list)
    second_brain: SecondBrainConfig = Field(default_factory=SecondBrainConfig)
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
    # Shell commands run as mechanical pre-check in /hm:review before LLM reviewers.
    # User adds to harness.yaml manually (no interview question). Empty list = feature off.
    mechanical_checks: list[str] = Field(default_factory=list)
    # MCP servers — user adds to harness.yaml manually (no interview question
    # yet). Propagated to .cursor/mcp.json on re-render via answers_from_harness_yaml.
    mcp_servers: dict[str, dict[str, Any]] = Field(default_factory=dict)
    models: dict[str, Any] = Field(default_factory=dict)
    autoloop: dict[str, Any] = Field(default_factory=dict)
    memory: dict[str, Any] = Field(default_factory=dict)
    anti_rot: dict[str, Any] = Field(default_factory=dict)
    worktree: dict[str, Any] = Field(default_factory=dict)
    security: dict[str, Any] = Field(default_factory=dict)
    context_lint: dict[str, Any] = Field(default_factory=dict)
    interview: dict[str, Any] = Field(
        default_factory=lambda: {
            "deep_gate": {"max_rounds": 3, "streak_target": 2},
            "main_loop": {"max_rounds": None},
        }
    )
    schema_version: int = 2
    sibling_repos: list[str] = Field(default_factory=list)
    # Paths to additional documents that wrapup should update/manage.
    # User specifies via --wrapup-docs or /hm:configure. Examples:
    # CHANGELOG.md, TODO.md, docs/ADR-index.md.
    wrapup_docs: list[str] = Field(default_factory=list)

    @field_validator("sibling_repos", mode="before")
    @classmethod
    def _reject_absolute_sibling_paths(cls, v: object) -> object:
        """Relative paths survive cross-machine git clones; absolute paths do not."""
        if not isinstance(v, list):
            return v
        for p in v:
            if isinstance(p, str) and (Path(p).is_absolute() or p.startswith("~")):
                raise ValueError(f"sibling_repos must contain relative paths; got absolute: {p!r}")
        return v

    @model_validator(mode="after")
    def _default_workflow_in_fused(self) -> InterviewAnswers:
        if self.default_workflow not in self.fused_workflows:
            msg = (
                f"default_workflow={self.default_workflow!r} not in "
                f"fused_workflows={sorted(self.fused_workflows)}"
            )
            raise ValueError(msg)
        return self

    @computed_field  # type: ignore[prop-decorator]
    @property
    def recommended_model(self) -> str:
        """Read-side back-compat — ADR-012 deprecation window. computed_field
        so the key appears in model_dump() for downstream template consumers."""
        return self.default_model
