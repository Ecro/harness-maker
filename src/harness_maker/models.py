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
    MERGE_JSON = "merge_json"  # schema-aware JSON 3-way merge (hooks.json; ADR-003/006)


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
    lifecycle: str = "dormant"  # active | maintenance | dormant (ADR-006)
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
    """One CVE record from OSV.dev (consumed by secscan/dependency_cves.py)."""

    model_config = ConfigDict(strict=True, extra="forbid")

    source: str  # "osv_dev"
    item_id: str  # URL or unique id
    title: str
    summary: str = ""
    published: str | None = None  # ISO date
    score: float = 0.0  # relevance score [0,1]
    metadata: dict[str, Any] = Field(default_factory=dict)


class Finding(BaseModel):
    """One security finding from any of the 5 security gates."""

    model_config = ConfigDict(strict=True, extra="forbid")

    severity: str  # "high" | "P0" | "P1" | "P2" | "medium" | "low"
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


class FeedbackConfig(BaseModel):
    """Maintainer-dogfooding feedback drafts (PLAN-auto-feedback-2026-05 ADR-001/002).

    Default off. When ``enabled=True``, dispatcher wrappers emit an in-band
    LLM-judgment block that writes local drafts to
    ``.claude/observability/feedback/`` and prints a footer with the exact
    ``gh issue create --web`` command for manual submission. Zero socket
    calls from harness-maker Python — preserves PRIVACY.md + ADR-005 of
    PLAN-oss-readiness-audit (``tests/unit/test_no_network.py``).
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    enabled: bool = False


SECOND_OPINION_MODELS = ("codex", "antigravity")


class SecondOpinionCodexConfig(BaseModel):
    """Codex-specific second-opinion knobs (PLAN-second-opinion-multi-model ADR-002).

    ``hermetic`` maps to ``codex exec --ignore-user-config --ignore-rules`` (ADR-006
    reproducibility). ``output_schema_path`` is the ``--output-schema`` argument. Both
    are Codex-only — antigravity has no equivalent flags, so they live in this sub-block
    rather than at the top level (avoids the silent-no-op footgun for antigravity).
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    hermetic: bool = True
    output_schema_path: str = ".claude/schemas/second-opinion-finding.schema.json"

    @field_validator("output_schema_path")
    @classmethod
    def _validate_output_schema_path(cls, v: str) -> str:
        """Reject absolute paths, traversal, and shell metacharacters.

        Defense in depth — review security-reviewer P1: this field flows
        into the rendered Bash recipe as `--output-schema <path>`. Without
        strict validation, a tampered harness.yaml could achieve path
        traversal (reading `~/.ssh/id_rsa`) or shell injection (via
        `;`, `|`, `$()`, backticks, quote-escape).
        """
        if not v:
            raise ValueError("output_schema_path must not be empty")
        path = Path(v)
        if path.is_absolute():
            raise ValueError(f"output_schema_path must be project-relative, got absolute: {v!r}")
        if ".." in path.parts:
            raise ValueError(f"output_schema_path must not contain '..' segments: {v!r}")
        if not v.endswith(".json"):
            raise ValueError(f"output_schema_path must end with '.json': {v!r}")
        if any(c in v for c in "`$();|&\"'\n\r\\"):
            raise ValueError(f"output_schema_path contains shell-significant characters: {v!r}")
        return v


class SecondOpinionAntigravityConfig(BaseModel):
    """Antigravity-specific second-opinion knobs (PLAN-second-opinion-multi-model ADR-002/007).

    ``model`` is the ``agy --model`` argument — a free-text display name (e.g.
    "Gemini 3.1 Pro (High)"), NOT a closed enum, because ``agy models`` returns unstable
    display strings with no machine IDs (ADR-007). Interview-time resolution offers a live
    list; render never re-shells (determinism). Validated only against shell-injection
    metacharacters, not against a fixed list.
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    model: str = "Gemini 3.1 Pro (High)"

    @field_validator("model")
    @classmethod
    def _validate_model(cls, v: str) -> str:
        """Reject shell-significant characters — the value flows into the rendered
        ``agy --model "<model>"`` Bash recipe (parens/spaces are legitimate; quotes,
        command-substitution, and control chars are not)."""
        if not v.strip():
            raise ValueError("antigravity model must not be empty")
        if any(c in v for c in "`$;|&\"'\n\r\\"):
            raise ValueError(f"antigravity model contains shell-significant characters: {v!r}")
        return v


class SecondOpinionConfig(BaseModel):
    """Multi-vendor cross-model second-opinion routing (PLAN-second-opinion-multi-model).

    Supersedes the single-vendor ``codex_second_opinion`` block. ``models`` is the enabled
    set (empty = feature off); when non-empty, the allow-listed reviewer agents (``agents``,
    a GLOBAL allowlist applied identically to every enabled model — ADR-002) receive a
    ``Bash(<cli>:*)`` permission line and a rendered second-opinion section per model.

    Each enabled model runs under the mandatory matrix (Production = every validation/review;
    Side = high-diff-gated) uniformly (ADR-003). Failures degrade via ``failure_policy``
    (warn-and-proceed): a missing/removed CLI, a rate-limit/subscription error, a timeout, or
    unparseable output all route to a ledger skip/failed row and the stage proceeds
    (ADR-011 fail-closed adapter). Per-model knobs live in the ``codex`` / ``antigravity``
    sub-blocks so vendor-specific flags never silently no-op on the other vendor.
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    models: list[Literal["codex", "antigravity"]] = Field(default_factory=list)
    agents: list[str] = Field(
        default_factory=lambda: ["code-reviewer", "consensus-arbiter", "plan-validator"],
    )
    failure_policy: Literal["warn-and-proceed"] = "warn-and-proceed"
    codex: SecondOpinionCodexConfig = Field(default_factory=SecondOpinionCodexConfig)
    antigravity: SecondOpinionAntigravityConfig = Field(
        default_factory=SecondOpinionAntigravityConfig
    )

    @field_validator("models")
    @classmethod
    def _dedupe_models(cls, v: list[str]) -> list[str]:
        """De-duplicate, order-preserving — a repeated model is a config typo, not two votes."""
        seen: set[str] = set()
        out: list[str] = []
        for m in v:
            if m not in seen:
                seen.add(m)
                out.append(m)
        return out

    @property
    def enabled(self) -> bool:
        """True when at least one second-opinion model is configured (feature on)."""
        return bool(self.models)


_GIT_ARGV_FORBIDDEN = set("`$();|&\"'\n\r\\ \t")

# git's extended-revision operators — rejected ONLY for values used in a
# revision context (default_branch), NOT for tag_pattern. REVIEW security P1:
# `default_branch` is interpolated into `refs/heads/<branch>` and reused as a
# `git log` revision, so `master^{/regex}` is a valid revspec gadget (full-history
# message scan → DoS, or redirect to an attacker-chosen commit). `tag_pattern`
# goes to `git tag --list <pattern>` (fnmatch), where these chars are literals —
# forbidding them globally would break legit monorepo schemes like `pkg@*`.
_GIT_REVSPEC_OPERATORS = set("^~:@{}")


def _validate_git_argv_value(v: str, *, field: str) -> str:
    """Reject shapes that could act as git options or shell fragments.

    delivery_metrics string fields flow into git argv (never a shell), so the
    threat is option injection (leading ``-``), traversal, and defense-in-depth
    against a later caller quoting mistake — same posture as
    ``SecondOpinionCodexConfig.output_schema_path``. fnmatch glob chars
    (``* ? [ ]``) stay allowed: they are the point of a tag pattern. Callers in a
    *revision* context additionally pass ``forbid_revspec=True`` (see
    ``_validate_default_branch``).
    """
    if not v:
        raise ValueError(f"{field} must not be empty")
    if v.startswith("-"):
        raise ValueError(f"{field} must not start with '-' (git option injection): {v!r}")
    if ".." in Path(v).parts:
        raise ValueError(f"{field} must not contain '..' segments: {v!r}")
    if any(c in _GIT_ARGV_FORBIDDEN for c in v):
        raise ValueError(f"{field} contains shell-significant or whitespace characters: {v!r}")
    return v


def _validate_git_revision_value(v: str, *, field: str) -> str:
    """Stricter validator for a value used as a git REVISION (not a glob).

    Adds revspec-operator rejection on top of the argv checks — see
    ``_GIT_REVSPEC_OPERATORS`` (REVIEW security P1).
    """
    v = _validate_git_argv_value(v, field=field)
    if any(c in _GIT_REVSPEC_OPERATORS for c in v):
        raise ValueError(f"{field} must not contain git revision operators (^~:@{{}}): {v!r}")
    return v


class DeliveryMetricsConfig(BaseModel):
    """Local git delivery-metrics tuning (PLAN-cfr-churn-metrics ADR-003;
    0.36.0 dropped the ``enabled`` flag — see below).

    ``/hm:metrics`` is a manual, read-only, zero-network command (compute CFR
    over ``cfr_window_days`` with releases = ``tag_pattern`` tags + first-parent
    task-land fallback; post-merge churn via cohort-blame survival at the
    ``churn_maturation_days`` boundary). Because it is inert until the user
    invokes it, there is NO on/off switch — this block holds only the per-project
    TUNING knobs, all with sensible defaults, that you touch when your repo's
    release convention / monorepo scoping differs from the defaults.

    Migration: a legacy harness.yaml carrying ``delivery_metrics.enabled`` still
    loads — both readers (``interview.answers_from_harness_yaml`` and
    ``delivery_metrics._load_cli_config``) filter unknown keys to the model's
    fields before validating, so the removed key is silently dropped and the
    tuning values are preserved.
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    tag_pattern: str = "v*"
    default_branch: str | None = None
    cfr_window_days: int = Field(default=28, ge=1)
    # Two separate windows by design (plan-validator advisory): maturation is
    # how long a commit must age before churn is judged; cohort is how wide a
    # slice of matured commits one snapshot covers. A single "window_days"
    # was misreadable as a trailing-14d cohort.
    churn_maturation_days: int = Field(default=14, ge=1)
    churn_cohort_days: int = Field(default=14, ge=1)
    blame_file_cap: int = Field(default=500, ge=1)
    paths: list[str] = Field(default_factory=list)

    @field_validator("tag_pattern")
    @classmethod
    def _validate_tag_pattern(cls, v: str) -> str:
        return _validate_git_argv_value(v, field="tag_pattern")

    @field_validator("default_branch")
    @classmethod
    def _validate_default_branch(cls, v: str | None) -> str | None:
        if v is None:
            return v
        # Revision context — reject revspec operators too (REVIEW security P1).
        return _validate_git_revision_value(v, field="default_branch")

    @field_validator("paths")
    @classmethod
    def _validate_paths(cls, v: list[str]) -> list[str]:
        for item in v:
            _validate_git_argv_value(item, field="paths")
            if Path(item).is_absolute():
                raise ValueError(f"paths must be project-relative, got absolute: {item!r}")
        return v


class EconomicsConfig(BaseModel):
    """Per-project tuning for the transcript-backed economics report.

    No ``enabled`` flag, deliberately — like ``/hm:metrics`` the reader is inert until
    invoked, so an on/off switch would only add a way to be surprised (the same reason
    0.36.0 removed ``delivery_metrics.enabled``). ``price_model`` is a FALLBACK for
    unrecognised model strings only; every turn is priced from its own recorded model
    (ADR-010).
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    window_days: int = 30
    price_model: str = "opus"
    adjacency_estimate: bool = True
    adjacency_max_gap_min: float = 10.0
    adjacency_max_turns: int = 20
    idle_gap_cap_min: float = 5.0
    # Forward span-ledger caps (ADR-003 of PLAN-economics-attribution-and-carry).
    # Calibrated against this repo's measured unattributed-run distribution: 400 turns
    # captures 96.1% with exactly one run over, and 240 min sits between p95 (179.1)
    # and p99 (485.2), cutting 4 of 144 runs. Both must still be able to REJECT — an
    # unbounded span hands unrelated conversation to whichever stage ran last.
    span_max_turns: int = 400
    span_max_min: float = 240.0


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


DELEGATABLE_STAGES: tuple[str, ...] = ("wrapup", "verify")


class DelegationConfig(BaseModel):
    """Which stages run their body inside a subagent (ADR-011 of PLAN-economics-…).

    A LIST, not per-stage booleans: ADR-011 rejected `wrapup.delegate` because Phase 6
    used the same key to gate *verify* — a key named for one stage silently
    controlling another. Empty means off, which is the shipped default for one
    release; the soak exit condition lives in the ADR.

    **Scope of the switch (review M-13):** emptying `stages` removes the *dispatch
    block* from the rendered stage commands. The `stage-delegate` agent asset is
    rendered unconditionally, like every other member of `_ALL_AGENTS` — nothing
    invokes it when no dispatch block exists, so it is inert rather than off.

    Names are normalised rather than validated into a `Literal`, deliberately: strict
    validation would make a typo poison the whole tolerant-fallback block load and
    silently revert every other key in it. `unknown_stages` keeps the typo REPORTABLE
    instead — an opt-in that never fires is the absent-case black hole this project
    has shipped eight times.
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    stages: list[str] = Field(default_factory=list)

    @field_validator("stages", mode="after")
    @classmethod
    def _normalise(cls, v: list[str]) -> list[str]:
        """A hand-edited `- Wrapup ` reads as "on" to the user and "off" to `in`."""
        return [s.strip().lower() for s in v if s.strip()]

    @property
    def unknown_stages(self) -> tuple[str, ...]:
        return tuple(s for s in self.stages if s not in DELEGATABLE_STAGES)


class PermissionsConfig(BaseModel):
    """Main-session ``settings.json`` permission deny-list policy.

    Default ``deny_dangerous=False`` — solo-friendly: ``settings.json`` ships an
    EMPTY ``permissions.deny`` so ``rm`` / ``curl | sh`` / writes to ``/etc`` /
    ``~/.ssh`` are NOT blocked in the user's own session (too inefficient for
    solo work). The reviewer AGENTS keep their own read-only ``Bash(rm:*)``
    deny regardless — this toggle only governs the main-session settings.json.

    Set ``deny_dangerous=True`` to restore the full destructive-pattern deny
    baseline. ``readiness.py``'s two deny signals (``permissions_deny_present``,
    ``deny_covers_dangerous``) become N/A — not penalized — when this is False,
    because a deliberate opt-out is a config choice, not a missing guardrail.
    """

    model_config = ConfigDict(strict=True, extra="forbid")
    deny_dangerous: bool = False


class AutonomyConfig(BaseModel):
    """Pipeline auto-advance policy (PLAN-human-bottleneck-auto-advance).

    ADR-002: ``level`` decides how far the workflow auto-advances past inter-stage
    STOP boundaries. Default ``gated`` (today's behavior). An old harness.yaml
    without an ``autonomy`` key loads as ``gated`` via the default-factory — the
    absent-case = feature-black-hole guard. ``auto_safe`` advances the two-way-door
    boundaries but ALWAYS stops at the plan architecture interview, a review
    CHANGES_REQUESTED grade-gate, and the wrapup merge/push. ``full`` currently behaves
    IDENTICALLY to ``auto_safe`` — the mandatory safety gates are non-negotiable and are
    honored at every level (a `full` session must never auto-push or skip a
    CHANGES_REQUESTED review). ``full`` is reserved for a future wider-advance policy; it
    is NOT a gate-bypass. (REVIEW P6: the P6 stage-terminal applies the gates
    unconditionally, so the earlier "full ~= /hm:loop bypass" wording was a code/doc
    divergence — corrected here.)

    ADR-003: the destructive never-auto deny baseline is code/template-fixed and is
    intentionally NOT a field here — only ``extra_deny`` (additive) is user-settable,
    so a harness.yaml edit can never SUBTRACT a baseline guard.

    ADR-007: ``step_cap`` / ``time_cap_min`` bound a chained interactive session so a
    runaway chain halts instead of looping uncapped.
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    level: Literal["gated", "auto_safe", "full"] = "gated"
    pipeline: list[AtomicStage] = Field(
        default_factory=lambda: [
            AtomicStage.RESEARCH,
            AtomicStage.SPEC,
            AtomicStage.PLAN,
            AtomicStage.EXECUTE,
            AtomicStage.REVIEW,
            AtomicStage.VERIFY,
            AtomicStage.WRAPUP,
        ],
    )
    # PLAN-autopilot-config-surface ADR-002: ``None`` = unlimited (the boundary cap check is
    # skipped). The field DEFAULT stays bounded (20/300) so the absent/malformed fallback is
    # SAFE — only a fresh interview opts into unlimited (ADR-005). ``gt=0`` still rejects a
    # hand-edited 0/negative (→ tolerant ``_parse_autonomy`` fallback), preserving the existing
    # zero-step-cap fallback test; the real runaway bound under unlimited is the finite pipeline
    # + the wrapup merge-gate, not the cap (ADR-003).
    step_cap: int | None = Field(default=20, gt=0)
    time_cap_min: int | None = Field(default=300, gt=0)
    extra_deny: list[str] = Field(default_factory=list)
    # ADR-003: when True, a SessionStart hook (``harness_maker.hooks.autopilot_autoarm``)
    # re-arms a fresh ``.hm-autopilot`` marker each session from the committed level/pipeline,
    # so the 18h TTL never trips in practice. The committed ``false`` is the real off-switch.
    autopilot_persistent: bool = False

    @field_validator("pipeline")
    @classmethod
    def _pipeline_no_duplicates(cls, v: list[AtomicStage]) -> list[AtomicStage]:
        # next_stage() resolves the NEXT stage by first index, so a duplicate stage
        # (e.g. [execute, execute]) makes the chain return the same stage forever. With the
        # caps now nullable (unlimited), that runaway is no longer bounded — so the
        # boundedness invariant (finite, strictly-advancing pipeline) requires uniqueness.
        # Codex review P1 of PLAN-autopilot-config-surface.
        if len(v) != len(set(v)):
            raise ValueError("autonomy.pipeline must not contain duplicate stages")
        return v


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
        default="opus",
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

    @field_validator("locale")
    @classmethod
    def _sanitize_locale(cls, v: str) -> str:
        """Security: locale is interpolated raw into Jinja2-rendered, agent-facing
        prose (the output_language directive + ~8 other ``{{ config.locale }}``
        sites) without escaping, so a multi-line or oversized value could inject
        agent instructions (REVIEW security P3). Unlike ``default_model`` (which
        rejects), locale's contract is *unknown tag → silent English fallback*, so
        sanitize rather than raise: accept only a short single-line tag (preserving
        legit non-ASCII tags like 한국어), else fall back to "en"."""
        v = v.strip()
        if not v or "\n" in v or "\r" in v or len(v) > 35:
            return "en"
        return v

    # Intentional asymmetry (ADR-002): the model default is the conservative
    # SPEC_DRIVEN for bare construction, but the reverse mapper
    # (interview.answers_from_harness_yaml) and the ADVISORY runtime gates
    # (spec_gate/spec_drift/spec_quality) resolve an ABSENT/unknown dev_mode to
    # task-driven, so a public-plugin config that loses its key never
    # surprise-forces SPEC. Deliberate exception: the spec_need verify ORACLE gate
    # is fail-CLOSED (absent/unreadable → enforce, never relaxed) — do NOT "align"
    # it to this relaxed default. Render fallbacks that relied on this default now
    # pin dev_mode explicitly (synthesize/workflow_fuse).
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
    # Main-session settings.json deny-list policy. Default off (empty deny) —
    # see PermissionsConfig. Old harness.yaml without this key → default.
    permissions: PermissionsConfig = Field(default_factory=PermissionsConfig)
    # Pipeline auto-advance policy. Old harness.yaml without this key → default
    # (level=gated) per AutonomyConfig — the absent-case = feature black hole guard.
    autonomy: AutonomyConfig = Field(default_factory=AutonomyConfig)
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
    # Maintainer-dogfooding feedback drafts (PLAN-auto-feedback-2026-05 ADR-002).
    # default_factory keeps old harness.yaml without `feedback:` key loading;
    # `enabled: false` ⇒ dispatcher conditional is dead branch (zero IO).
    feedback: FeedbackConfig = Field(default_factory=FeedbackConfig)
    # Multi-vendor second opinions (PLAN-second-opinion-multi-model — supersedes the
    # single-vendor codex_second_opinion block). default_factory keeps legacy harness.yaml
    # loading; empty `models` keeps Jinja conditionals in templates as dead branches.
    second_opinion: SecondOpinionConfig = Field(
        default_factory=SecondOpinionConfig,
    )
    # Opt-in git delivery metrics (PLAN-cfr-churn-metrics ADR-003).
    # default_factory keeps legacy harness.yaml loading; `enabled: false`
    # renders no /hm:metrics command and performs zero writes (SPEC AC-008/009).
    delivery_metrics: DeliveryMetricsConfig = Field(default_factory=DeliveryMetricsConfig)
    # Transcript-backed economics tuning (PLAN-harness-economics-observability ADR-004).
    economics: EconomicsConfig = Field(default_factory=EconomicsConfig)
    # Whole-stage subagent delegation (PLAN-economics-attribution-and-carry ADR-011).
    # default_factory keeps legacy harness.yaml loading; empty `stages` leaves every
    # dispatch block a dead Jinja branch.
    delegation: DelegationConfig = Field(default_factory=DelegationConfig)
    # ADR-011: schema_version bumped 1 → 2 for the agent_models/default_model
    # rename. PLAN-second-opinion-multi-model ADR-001: bumped 2 → 3 for the
    # codex_second_opinion → second_opinion rename (silent migration in interview.py).
    schema_version: int = 3
    # 0.16.0: deep_gate redesigned as 5-term inequality (PLAN-deep-interview-question-criteria).
    # Default literal lives in `interview_deep_gate_defaults()` at module bottom —
    # also consumed by `harness_maker.interview._preset_extras` to avoid 3-way drift.
    interview: dict[str, Any] = Field(
        default_factory=lambda: {
            "deep_gate": interview_deep_gate_defaults(),
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
        default="opus",
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

    @field_validator("locale")
    @classmethod
    def _sanitize_locale(cls, v: str) -> str:
        """Security: locale is interpolated raw into Jinja2-rendered, agent-facing
        prose (the output_language directive + ~8 other ``{{ config.locale }}``
        sites) without escaping, so a multi-line or oversized value could inject
        agent instructions (REVIEW security P3). Unlike ``default_model`` (which
        rejects), locale's contract is *unknown tag → silent English fallback*, so
        sanitize rather than raise: accept only a short single-line tag (preserving
        legit non-ASCII tags like 한국어), else fall back to "en"."""
        v = v.strip()
        if not v or "\n" in v or "\r" in v or len(v) > 35:
            return "en"
        return v

    # Intentional asymmetry (ADR-002): the model default is the conservative
    # SPEC_DRIVEN for bare construction, but the reverse mapper
    # (interview.answers_from_harness_yaml) and the ADVISORY runtime gates
    # (spec_gate/spec_drift/spec_quality) resolve an ABSENT/unknown dev_mode to
    # task-driven, so a public-plugin config that loses its key never
    # surprise-forces SPEC. Deliberate exception: the spec_need verify ORACLE gate
    # is fail-CLOSED (absent/unreadable → enforce, never relaxed) — do NOT "align"
    # it to this relaxed default. Render fallbacks that relied on this default now
    # pin dev_mode explicitly (synthesize/workflow_fuse).
    dev_mode: DevMode = DevMode.SPEC_DRIVEN
    domains: list[str] = Field(default_factory=list)
    ref_folders: list[RefFolder] = Field(default_factory=list)
    second_brain: SecondBrainConfig = Field(default_factory=SecondBrainConfig)
    # Mirrors HarnessConfig.permissions so it round-trips through
    # answers_from_harness_yaml → synthesize (else a user's deny_dangerous=true
    # is silently dropped on re-render — REVIEW P1).
    permissions: PermissionsConfig = Field(default_factory=PermissionsConfig)
    # Mirrors HarnessConfig.autonomy so the pipeline auto-advance policy round-trips
    # through answers_from_harness_yaml → synthesize (else level/pipeline/caps are
    # silently dropped on re-render — same contract as permissions above).
    autonomy: AutonomyConfig = Field(default_factory=AutonomyConfig)
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
    # Mirror of HarnessConfig.interview (0.16.0 deep_gate redesign — see HarnessConfig).
    interview: dict[str, Any] = Field(
        default_factory=lambda: {
            "deep_gate": interview_deep_gate_defaults(),
            "main_loop": {"max_rounds": None},
        }
    )
    schema_version: int = 3
    sibling_repos: list[str] = Field(default_factory=list)
    # Paths to additional documents that wrapup should update/manage.
    # User specifies via --wrapup-docs or /hm:configure. Examples:
    # CHANGELOG.md, TODO.md, docs/ADR-index.md.
    wrapup_docs: list[str] = Field(default_factory=list)
    # Mirror of HarnessConfig.feedback (PLAN-auto-feedback-2026-05 ADR-002).
    # default_factory mirrors HarnessConfig default (enabled=false). Survives
    # answers_from_harness_yaml round-trip per CLAUDE.md checkpoint 6.
    feedback: FeedbackConfig = Field(default_factory=FeedbackConfig)
    # Mirror of HarnessConfig.second_opinion (PLAN-second-opinion-multi-model —
    # supersedes codex_second_opinion). InterviewAnswers extra='forbid' would reject
    # the key without this declaration on round-trip.
    second_opinion: SecondOpinionConfig = Field(
        default_factory=SecondOpinionConfig,
    )
    # Mirror of HarnessConfig.delivery_metrics (PLAN-cfr-churn-metrics ADR-003)
    # — same round-trip contract as feedback/second_opinion above.
    delivery_metrics: DeliveryMetricsConfig = Field(default_factory=DeliveryMetricsConfig)
    # Mirror of HarnessConfig.economics — without this declaration InterviewAnswers'
    # extra='forbid' would reject the key on round-trip (checkpoint 6).
    economics: EconomicsConfig = Field(default_factory=EconomicsConfig)
    # Mirror of HarnessConfig.delegation. ADR-011 designates `delegation.stages` as
    # the ROLLBACK for a medium-likelihood/high-impact quality risk, so dropping it
    # on `--update` would disarm the escape hatch itself.
    delegation: DelegationConfig = Field(default_factory=DelegationConfig)

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


def interview_deep_gate_defaults() -> dict[str, Any]:
    """5-term inequality gate defaults (0.16.0 — PLAN-deep-interview-question-criteria).

    Consumed by:
      - HarnessConfig.interview default_factory
      - InterviewAnswers.interview default_factory
      - harness_maker.interview._preset_extras (Side + Production branches)

    Single source of truth — changing ε/τ/threshold/locale-cap here propagates
    to all three sites. ADR-007: uniform across Side/Production presets.
    ADR-012: only `common_ground.llm_inference_enabled` is user-tunable.
    """
    return {
        "eig_epsilon": 0.5,
        "confidence_tau": 0.7,
        "open_ended_cap_by_locale": {"en": 2, "ko": 1, "ja": 1, "default": 1},
        "common_ground": {
            "llm_inference_threshold": 0.95,
            "llm_inference_enabled": True,
        },
    }
