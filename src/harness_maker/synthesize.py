"""Synthesizer — map preset+answers to deterministic Blueprint with FileEntry list.

Per the new architecture every preset installs the FULL skill + agent inventory.
The harness.yaml `reviewers.enabled` and `skills.enabled` lists govern default
activation; users opt into more reviewers per-task via inline command flags.

Only the seven atomic stage commands are emitted — the fused-workflow axis was
removed (PLAN-harness-diet ADR-001/002); `/hm:loop` and autopilot chain stages
instead.
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Any

import typer

from harness_maker.models import (
    AgentModelSpec,
    AtomicStage,
    Blueprint,
    FileEntry,
    HarnessConfig,
    InterviewAnswers,
    Preset,
    ProjectProfile,
    Target,
)

logger = logging.getLogger(__name__)

#: `review.md.j2` points at this skill's §5 from an UNGUARDED line, so the
#: auto-fix loop's round-state contract is only reachable if the skill is
#: enabled — in every harness, `second_opinion.models` empty or not.
ROUND_STATE_SKILL = "second-opinion-gate"

# Each tuple: (template path under templates/, output path under .claude/, context supplement)
FileSpec = tuple[str, str, dict[str, Any]]

# Computed once — points to the directory containing pyproject.toml.
# Works both from the source repo and from the plugin cache.
_HARNESS_MAKER_PKG_ROOT = str(Path(__file__).parent.parent.parent)


def _portablize_ref(raw: str) -> str:
    """Replace the render-machine home-dir prefix in ``raw`` with the literal ``$HOME``.

    WHY (PLAN-portable-hook-paths, ADR-001/002): the raw install ref is a plugin-cache
    ``file://`` path prefixed with the render-machine home (e.g.
    ``/home/noel/.claude/plugins/cache/...``). Baked verbatim into committed hook /
    command bodies it flip-flops across a team repo (each dev's home rewrites it on
    re-render). Substituting ``$HOME`` keeps the local cache (no network, exact version)
    while making the committed path machine-portable — the IDE's shell expands ``$HOME``
    at run time.

    Boundary-safe (R4): only a true path-segment match substitutes, so a sibling like
    ``/home/noel-other`` is never corrupted into ``$HOME-other``. A PyPI name or any path
    not under the render-machine home passes through unchanged (legitimately non-portable
    system installs stay absolute).
    """
    home = str(Path.home())
    if raw == home:
        return "$HOME"
    if raw.startswith(home + os.sep):
        return "$HOME" + raw[len(home) :]
    return raw


#: One warning per process. `_compute_install_ref` is called from four sites, so an
#: undeduplicated warning fires four times per `make` and reads like four defects.
_INSTALL_REF_WARNED: set[str] = set()


def _reset_install_ref_warning() -> None:
    """Test seam — the dedup set is process-global by design."""
    _INSTALL_REF_WARNED.clear()


#: Suffixes `uv run --with <file>` installs directly. A wheel/sdist install records the
#: ARCHIVE in `direct_url.json` (PEP 610), not a project directory, so the project-dir
#: predicate alone rejected an install class that worked (ADR-010a).
_INSTALLABLE_ARCHIVE_SUFFIXES = (".whl", ".tar.gz", ".tar.bz2", ".tar.xz", ".zip")


def _is_resolvable_project(path: str) -> bool:
    """Can `uv run --with <path>` actually resolve this?

    Existence is NOT the predicate. `_compute_install_ref`'s own docstring records
    the 0.15.0 incident where an EXISTING uv-archive ``lib/python3.12`` directory was
    baked and every hook then failed with "does not appear to be a Python project".
    An ``exists()``-only guard would not have caught this repo's single documented
    instance of the class it is meant to prevent.

    ADR-010a: two shapes resolve — a project **directory** (has ``pyproject.toml``) and an
    installable **archive** file. Suffix-based, not content-validating: the render cannot
    install the archive to find out, and a corrupt wheel is not the failure mode here.
    """
    try:
        p = Path(path)
        if (p / "pyproject.toml").is_file():
            return True
        return p.is_file() and p.name.endswith(_INSTALLABLE_ARCHIVE_SUFFIXES)
    except OSError:
        return False


def _warn_unresolvable_install_ref(path: str) -> None:
    if path in _INSTALL_REF_WARNED:
        return
    _INSTALL_REF_WARNED.add(path)
    typer.echo(
        f"WARN: install ref {path!r} is not resolvable (not a project directory and not "
        "an installable archive) — rendered hooks would fail to execute, and they are "
        "blocking PreToolUse gates, so the project would lose Edit. Falling back to "
        "the published distribution.",
        err=True,
    )


#: A plain PEP 440 release, the only shape safe to pin: `1`, `1.2`, `1.2.3`, `1.2.3.post1`.
#: Anything with a pre-release (`a`/`b`/`rc`), a `.dev` segment or a `+local` segment names a
#: build no index serves, and pinning it renders a gate nothing can resolve (ADR-010b).
#: A regex rather than `packaging.version` on purpose — `packaging` is not in this project's
#: `dependencies` and is only ever present transitively, so an import here would work on the
#: maintainer's machine and fail on a user's.
_PLAIN_RELEASE_RE = re.compile(r"^\d+(?:\.\d+)*(?:\.post\d+)?$")


def _pinned_distribution_ref(dist: object) -> str:
    """Version-pinned so the hooks run the same gate code as the templates beside them.

    A bare ``harness-maker`` lets a harness rendered by this release execute a future
    release's ``spec_gate``. The bare form is the fallback for a version we cannot pin:
    absent (a harness predating the 0.15.3 PyPI publication) or not a plain release
    (a dev/local build — ADR-010b).
    """
    version = getattr(dist, "version", None)
    if isinstance(version, str) and _PLAIN_RELEASE_RE.match(version):
        return f"harness-maker=={version}"
    detail = (
        f"version {version!r} is a local/pre-release build no index serves"
        if isinstance(version, str) and version
        else "no distribution version is available"
    )
    # Same dedup set, same reason: `_compute_install_ref` runs at four call sites, so an
    # undeduplicated warning reads as four defects. The first cut routed only the path
    # warning through it and left this one firing 4x — the exact readability failure the
    # set exists to prevent, reintroduced beside the code stating the rationale.
    key = f"version:{version!r}"
    if key not in _INSTALL_REF_WARNED:
        _INSTALL_REF_WARNED.add(key)
        typer.echo(
            f"WARN: {detail} — falling back to the unpinned 'harness-maker'. Rendered hooks "
            "may resolve a different release than these templates, which beats a pin that "
            "resolves to nothing and leaves every blocking gate dead.",
            err=True,
        )
    return "harness-maker"


def _pkg_root_ref(dist: object | None) -> str:
    """The source-tree fallback, held to the SAME resolvability bar as the `file://` one.

    ADR-007 refreshes a preserved user hook to the template's command text on the premise
    that the template's ref is validated. It was validated on the `file://` branch only —
    these two returns handed back `_HARNESS_MAKER_PKG_ROOT` unchecked, and that is exactly
    the 0.15.0 archive shape (`…/lib/python3.12`, no `pyproject.toml`) this function's own
    docstring records. In that state the refresh would overwrite a user's still-working
    invocation with a dead one, so the premise has to be made true rather than assumed.
    """
    if _is_resolvable_project(_HARNESS_MAKER_PKG_ROOT):
        return _portablize_ref(_HARNESS_MAKER_PKG_ROOT)
    _warn_unresolvable_install_ref(_HARNESS_MAKER_PKG_ROOT)
    return _pinned_distribution_ref(dist) if dist is not None else "harness-maker"


def _compute_install_ref() -> str:
    """Return the source path/name to embed in rendered ``uv run --with <ref>`` calls.

    ADR-002 (revised 0.15.3): the value is baked into every rendered hook,
    skill, and slash command. It must be either a directory uv can resolve as
    a Python project (containing ``pyproject.toml``) or a PyPI distribution
    name. As of 0.15.3 harness-maker is published on PyPI, so the
    ``"harness-maker"`` branch is reachable for users who install via
    ``pip install harness-maker`` or ``uv add harness-maker``. The
    ``file://`` branch still dominates in practice because Claude Code /
    Cursor / Codex marketplaces install via local plugin cache, not PyPI.

    Detection rule:
    1. ``distribution("harness-maker")`` raises → not installed (running from a
       source checkout without ``pip install``). Use the source-tree fallback
       derived from ``__file__``.
    2. ``direct_url.json`` exists with a ``file://`` URL → the URL path is the
       *original* source uv was given. Return that. This is the **only**
       correct value when ``synthesize`` is imported from a uv archive cache
       (``~/.cache/uv/archive-v0/<hash>/lib/python3.12/site-packages/...``),
       where ``_HARNESS_MAKER_PKG_ROOT`` resolves to the archive's
       ``lib/python3.12`` directory rather than a Python project. This is
       also the path that 99% of plugin-marketplace installs take, since
       ``/plugin install harness-maker@harness-maker-local`` writes a
       ``file://`` URL pointing at the cache directory.
    3. ``url`` is non-``file://`` (PyPI / git+https / other index) → return
       ``"harness-maker"`` so uv resolves the name from the index. Reachable
       starting 0.15.3.
    4. Any parse error → fall back to ``_HARNESS_MAKER_PKG_ROOT``.

    Before 0.15.1, step 2 returned ``_HARNESS_MAKER_PKG_ROOT`` instead of the
    URL path. When the renderer ran from a uv archive cache (the default for
    ``uv run --with /plugin/cache/...``), that constant pointed at the
    archive's ``lib/python3.12`` directory — not a Python project — and every
    rendered hook fired ``uv run --with <archive>/lib/python3.12 ...`` which
    failed with "does not appear to be a Python project". Bug surfaced by
    /hm:health audit 2026-05-18.
    """
    # `_portablize_ref` wraps EVERY return branch (ADR-002 / codex #4): the source-tree
    # fallback, the decoded file:// path, and the parse-error fallback are all home-
    # prefixed in practice. Wrapping the PyPI-name branch too is a harmless no-op
    # (a distribution name is not a path under home).
    try:
        from importlib.metadata import distribution

        dist = distribution("harness-maker")
    except Exception:  # noqa: BLE001 — PackageNotFoundError or any import issue
        return _pkg_root_ref(None)

    try:
        import json
        from urllib.parse import unquote, urlparse

        raw = dist.read_text("direct_url.json")
        if raw is not None:
            du = json.loads(raw)
            url = du.get("url", "")
            if isinstance(url, str) and url.startswith("file://"):
                decoded = unquote(urlparse(url).path)
                # PLAN-render-degrades-live-harness ADR-001. Checked HERE — on the
                # decoded path, BEFORE `_portablize_ref`. After wrapping, the value is
                # the literal `$HOME/...`, which Python does not expand, so the
                # predicate would be False for EVERY valid home-cache install and the
                # whole fleet would render the fallback — worse than the defect.
                if _is_resolvable_project(decoded):
                    return _portablize_ref(decoded)
                _warn_unresolvable_install_ref(decoded)
                return _pinned_distribution_ref(dist)
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        return _pkg_root_ref(dist)
    return _portablize_ref("harness-maker")


_ATOMIC_STAGES: list[str] = [s.value for s in AtomicStage]

# Every preset installs the full reviewer/skill inventory; activation is data,
# not file presence.
_ALL_AGENTS: list[str] = [
    "autoloop-coder",
    "code-reviewer",
    "code-verifier",
    "concurrency-reviewer",
    "consensus-arbiter",
    "executor",
    "judgment-reviewer",
    "performance-reviewer",
    "plan-validator",
    "security-auditor",
    "security-reviewer",
    "stage-delegate",
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
    "second-opinion-gate",
    "security-scanner",
    "targeted-test-selection",
    "verify-before-completion",
    "worktree-isolator",
]


def _stage_files() -> list[FileSpec]:
    return [
        (
            f"stages/{s}.md.j2",
            f"stages/{s}.md",
            {"stage": s, "project_name": "", "feature": ""},
        )
        for s in _ATOMIC_STAGES
    ]


def _atomic_command_files(
    config_dump: dict[str, object] | None = None,
) -> list[FileSpec]:
    """Generate one /hm:<stage> command per atomic stage, with rendered body.

    `config_dump` is the user's resolved HarnessConfig as a dict — when
    provided, the stage body is rendered with real values (locale, deep_gate
    thresholds, …). When None, a fresh default HarnessConfig is used; this
    fallback exists only for the legacy module-level SIDE_FILES /
    PRODUCTION_FILES constants and for any test paths that don't have answers.
    """
    out: list[FileSpec] = []
    from harness_maker.models import DevMode, HarnessConfig  # local import: avoid cycle
    from harness_maker.render import _make_env  # local import: avoid cycle

    env = _make_env()
    if config_dump is None:
        # ADR-002: pin dev_mode explicitly so the fallback render does not depend
        # on the HarnessConfig class default (a future default flip must not
        # silently drop Step 1.7 / Check 6 from these fallback renders).
        config_dump = HarnessConfig(dev_mode=DevMode.SPEC_DRIVEN).model_dump(mode="json")
    install_ref = _compute_install_ref()
    for s in _ATOMIC_STAGES:
        tpl = env.get_template(f"stages/{s}.md.j2")
        body = tpl.render(
            stage=s,
            project_name="",
            feature="",
            config=config_dump,
            harness_maker_src_path=install_ref,
            is_codex=False,
        )
        out.append(
            (
                "commands/hm/atomic_command.md.j2",
                f"commands/hm/{s}.md",
                {"stage": s, "stage_body": body},
            ),
        )
    return out


# ADR-016 — one-line `description:` per rendered `/hm:` command.
#
# Without it Claude Code and Cursor fall back to the command's first body line, which for
# 14 of the 15 commands is the identical banner block; the tool listing showed one string
# fifteen times. Keyed by the rendered path so the atomic-stage commands (generated in a
# loop) and the standalone ones share one table.
#
# Per-target parser question (ADR-016 requires it ANSWERED, not assumed): commands render
# to `.claude/commands/hm/*.md` only — never to `.codex/agents/*.toml` (agents) or
# `.cursor/rules/*.mdc` (rules) — and `description` is a documented frontmatter key for
# both readers of that path. So the field is unconditional.
# `tests/structural/test_command_descriptions.py` pins that premise and fails if a future
# release starts rendering commands to another target's path.
#
# Each line is drawn from the command's own summary, condensed. Keep them DISTINCT — the
# whole reason the field exists is that they were not.
_COMMAND_DESCRIPTIONS: dict[str, str] = {
    "commands/hm/research.md": (
        "Survey the ground before deciding: facts, prior art and alternatives into a RESEARCH doc."
    ),
    "commands/hm/spec.md": (
        "Lock what and why — acceptance criteria via a 6-category interview into a SPEC doc."
    ),
    "commands/hm/plan.md": (
        "Lock how and in what order — deep interview, ADRs and validated phases into a PLAN doc."
    ),
    "commands/hm/execute.md": ("Implement a PLAN's phases TDD-first. Stages, never commits."),
    "commands/hm/review.md": (
        "Multi-reviewer consensus review with a grade gate and an auto-fix loop."
    ),
    "commands/hm/verify.md": (
        "Pre-completion stop sign — deterministic regression, structure and security checks."
    ),
    "commands/hm/wrapup.md": (
        "Close the unit of work: final verification, memory capture, and the single commit."
    ),
    "commands/hm/loop.md": (
        "Run a bounded autoloop over a master PLAN, iterating stages until convergence."
    ),
    "commands/hm/loop-p5-batch.md": (
        "Bulk-author SPECs for a large PLAN's Phase 5 in prompt-driven batches."
    ),
    "commands/hm/health.md": (
        "Two-layer harness audit — structural integrity plus personalization drift."
    ),
    "commands/hm/metrics.md": (
        "Delivery-metrics trend — change-failure rate and post-merge churn, with interpretation."
    ),
    "commands/hm/make.md": "Re-render this project's harness after a plugin update.",
    "commands/hm/configure.md": (
        "Change one harness dimension without re-running the full interview."
    ),
    "commands/hm/uninstall.md": "Remove harness-maker's generated files from this project.",
    "commands/hm/help.md": "List the /hm: commands and what each one is for.",
}


def _command_frontmatter(out_path: str) -> dict[str, Any]:
    """ADR-016 description for a rendered command; empty for every other file kind."""
    description = _COMMAND_DESCRIPTIONS.get(out_path)
    return {"description": description} if description else {}


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

# Communication-protocol variant per agent (PLAN-antisycophancy-2026-05 ADR-002).
# Claude render path reads source dispatcher frontmatter automatically via
# render._extract_source_communication_variant. Codex/Cursor render paths
# bypass dispatcher source — they need the variant explicitly in context.
_COMMUNICATION_VARIANT: dict[str, str] = {
    "autoloop-coder": "full",
    "executor": "full",
    "stage-delegate": "full",
    "stuck": "full",
    # trajectory-monitor is intentionally absent from _ALL_AGENTS (no body
    # file, JSON-output agent); Codex render path does not need a variant
    # entry for it. If it is ever added to _ALL_AGENTS, also add the matching
    # variant here.
    "code-reviewer": "reframe",
    "code-verifier": "reframe",
    "concurrency-reviewer": "reframe",
    "consensus-arbiter": "reframe",
    "judgment-reviewer": "reframe",
    "performance-reviewer": "reframe",
    "plan-validator": "reframe",
    "security-auditor": "reframe",
    "security-reviewer": "reframe",
    "test-reviewer": "reframe",
    "ux-reviewer": "reframe",
}


def _agent_files(
    preset: Preset = Preset.SIDE,
    agent_models: dict[str, AgentModelSpec] | None = None,
    default_model: str = "opus",
) -> list[FileSpec]:
    """Agent .md.j2 contexts include per-agent model values resolved through
    the 3-tier presets.resolve_agent_spec chain (ADR-005). Templates render
    `model: {{ claude_model }}` instead of hardcoded aliases (ADR-003).

    Module-load skeletons (SIDE_FILES / PRODUCTION_FILES) pass defaults so
    the FileSpec list stays import-time-evaluable; synthesize() passes the
    live HarnessConfig values at render time.
    """
    from harness_maker.models import HarnessConfig
    from harness_maker.presets import CURSOR_MODEL_IDS, resolve_agent_spec

    # Reverse map: a Tier-1 user override of `cursor:` only (no `claude:`) leaves
    # spec.claude None. ADR-001 renders the agent `model:` from the Claude alias,
    # so derive the alias back from the normalized cursor concrete id — otherwise
    # the cursor-only override would silently fall through to the `sonnet` default
    # in the partial, downgrading the user's intent.
    _alias_by_cursor_id = {v: k for k, v in CURSOR_MODEL_IDS.items()}

    config = HarnessConfig(
        preset=preset,
        agent_models=agent_models or {},
        default_model=default_model,
    )
    out: list[FileSpec] = []
    for n in _ALL_AGENTS:
        spec = resolve_agent_spec(n, config)
        claude_model = spec.claude or _alias_by_cursor_id.get(spec.cursor or "")
        out.append(
            (
                f"agents/{n}.md.j2",
                f"agents/{n}.md",
                {
                    "name": n,
                    "reviewer_kind": _REVIEWER_KIND.get(n, ""),
                    "claude_model": claude_model,
                    "cursor_model": spec.cursor,
                    "codex_reasoning_effort": (spec.codex.reasoning_effort if spec.codex else None),
                },
            )
        )
    return out


# Codex agent metadata: description only. ChatGPT-tier Codex CLI rejects every
# hardcoded model string (o4, o4-mini, gpt-5-codex, gpt-5.5-codex) with HTTP
# 400, so per-agent `model = ...` is omitted from rendered TOML. Codex inherits
# the user's ~/.codex/config.toml profile default. ADR-001 in
# work-docs/PLAN-codex-plan-validator-model-unavailable.md. The template's
# `{% if model_codex %}` gate stays intact so a future opt-in knob can re-enable
# per-agent models without touching the template.
#
# Each value is a plain `str` (no enclosing parens, no implicit concatenation)
# so the literal shape cannot be visually mistaken for a tuple — the original
# `dict[str, tuple[str, str]]` bug crept in by adding a trailing `, "model"`
# to a parenthesized multi-line string that silently became a tuple. Plain
# single-line string literals (with line-length suppression for long
# descriptions) close that re-introduction surface.
_CODEX_AGENT_META: dict[str, str] = {
    "autoloop-coder": "Implementation agent for autoloop iterations — bounded scope, write-tool-only, no open-ended exploration; worktree-bounded writes",  # noqa: E501
    "code-reviewer": "Reviews code changes for correctness, readability, maintainability, and basic security/performance hygiene",  # noqa: E501
    "code-verifier": "Reduce-only verifier. Mode B (cross-model PIDA) is the only live caller and the default: accepted/rejected/duplicate/unresolved for second-opinion findings against injected oracle output. Mode A (the Pass 1.5 KEEP/DROP/DEMOTE reduction) is retained but no longer dispatched — its call site was removed. MUST NOT introduce new findings.",  # noqa: E501
    "concurrency-reviewer": "Reviews changes for race conditions, deadlocks, ISR safety, and async correctness",  # noqa: E501
    "consensus-arbiter": "Aggregates findings from multiple reviewer agents via surface match + reasoning alignment + severity resolution; tags every finding consensus-passed | weak-consensus | manual-only",  # noqa: E501
    "executor": "Workflow executor with worktree-bounded write permissions — only writes to .worktrees/, never to repo root",  # noqa: E501
    "judgment-reviewer": "Independently evaluates a judgment AC's subject against its rubric and returns a per-criterion verdict with cited locators (PLAN-judgment-ac-binding ADR-006). Read-only.",  # noqa: E501
    "performance-reviewer": "Reviews changes for hot-path regressions, allocation hotspots, and algorithmic inefficiency",  # noqa: E501
    "plan-validator": "Critiques a draft PLAN document for gaps, ambiguities, missing exit criteria, and feasibility risks before /hm:execute is invoked. Read-only.",  # noqa: E501
    "security-auditor": "Deep 5-gate security audit (secrets, permissions, hook injection, dependency CVEs, prompt injection) — read-only, returns structured findings JSON",  # noqa: E501
    "security-reviewer": "Reviews changes for secrets exposure, injection, auth flaws, and unsafe permission grants",  # noqa: E501
    "stage-delegate": "Runs a whole pipeline stage body (wrapup or verify) from a validated brief and returns a machine receipt, cutting main-loop context carry",  # noqa: E501
    "stuck": "Escalation analyst — invoked when /hm:execute, /hm:review, or /hm:plan blocks. Performs root-cause analysis, proposes 2-3 unblock paths, and writes a structured escalation note. Read-only.",  # noqa: E501
    "test-reviewer": "Phase A.5 gate for /hm:execute. Critiques RED-stage tests for SPEC alignment, banned-pattern violations, and assertion quality before Phase B (RED gate) runs. Read-only.",  # noqa: E501
    "ux-reviewer": "Reviews UI changes for accessibility, consistency, and interaction quality",
}


def _codex_agent_files(
    preset: Preset = Preset.SIDE,
    agent_models: dict[str, AgentModelSpec] | None = None,
    default_model: str = "opus",
) -> list[FileSpec]:
    """Codex agent TOML files — one per agent using codex/agent.toml.j2.

    `model_codex` stays None (Codex CLI rejects most hardcoded IDs on
    ChatGPT-tier accounts — see RESEARCH-codex-plan-validator-model-unavailable).
    ADR-008 (PLAN-model-routing-multi-ide): `model_reasoning_effort` is the
    tier-agnostic cost lever and IS rendered per-agent when set by the
    resolved spec.
    """
    from harness_maker.models import HarnessConfig
    from harness_maker.presets import resolve_agent_spec

    config = HarnessConfig(
        preset=preset,
        agent_models=agent_models or {},
        default_model=default_model,
    )
    out: list[FileSpec] = []
    for n in _ALL_AGENTS:
        spec = resolve_agent_spec(n, config)
        out.append(
            (
                "codex/agent.toml.j2",
                f".codex/agents/{n}.toml",
                {
                    "name": n,
                    "description": _CODEX_AGENT_META[n],
                    "model_codex": None,
                    "codex_reasoning_effort": (spec.codex.reasoning_effort if spec.codex else None),
                    "reviewer_kind": _REVIEWER_KIND.get(n, ""),
                    # REVIEW Phase 5 CP-2: defensive .get() fallback. If a
                    # future agent is added to _ALL_AGENTS without a matching
                    # _COMMUNICATION_VARIANT entry, render falls back to
                    # "full" (the safest universal default) rather than
                    # KeyError-ing at user render time. The structural test
                    # `test_cp2_all_agents_subset_of_communication_variant`
                    # catches the omission at test time.
                    "communication_variant": _COMMUNICATION_VARIANT.get(n, "full"),
                },
            )
        )
    return out


def _skill_files() -> list[FileSpec]:
    return [
        (
            f"skills/{n}/SKILL.md.j2",
            f"skills/{n}/SKILL.md",
            {"name": n},
        )
        for n in _ALL_SKILLS
    ]


# `repair_guard_force` judges the rendered Phase D.5 repair guard. It ships to every
# harness because that step does — and because "does this step carry operative force"
# is a semantic question, which is exactly what a literal-grep structural test cannot
# answer (two attempts at a mechanical mutation control were circular; ADR-003).
_ALL_RUBRICS: list[str] = ["claude_md", "agent_prompt", "skill", "repair_guard_force"]


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


def _schema_files(second_opinion_enabled: bool) -> list[FileSpec]:
    """JSON Schema files rendered to ``.claude/schemas/*.json``.

    PLAN-codex-second-llm-integration ADR-008 / PLAN-second-opinion-multi-model ADR-004:
    schema is gated on the opt-in feature — rendered only when at least one
    second-opinion model is configured. Path uses the inside-.claude/ convention
    (no leading dot, no .claude/ prefix), so ``_is_schemas_json`` predicate matches
    and ``_render_pure_json`` is the dispatch target (no provenance frontmatter;
    external consumer is ``codex exec --output-schema``). Antigravity shares the same
    finding schema (ADR-004 — one shared severity vocabulary).
    """
    if not second_opinion_enabled:
        return []
    return [
        (
            "schemas/second-opinion-finding.schema.json",
            "schemas/second-opinion-finding.schema.json",
            {},
        ),
    ]


def _base_files(
    preset: Preset,
    locale: str = "en",
    agent_models: dict[str, AgentModelSpec] | None = None,
    default_model: str = "opus",
    config_dump: dict[str, object] | None = None,
) -> list[FileSpec]:
    """Shared base: stages + atomic commands + all agents/skills + fixed assets.

    Preset gates the structural variants (harness.yaml / settings.json /
    CLAUDE.md). Locale gates the prose-only templates (CLAUDE.md +
    memory/{failures,wiki}). Unknown locales silently fall back to en.
    `agent_models` + `default_model` flow into `_agent_files()` for per-agent
    model frontmatter resolution (ADR-005).
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
        *_atomic_command_files(config_dump=config_dump),
        ("commands/hm/loop.md.j2", "commands/hm/loop.md", {}),
        ("commands/hm/loop-p5-batch.md.j2", "commands/hm/loop-p5-batch.md", {}),
        ("commands/hm/health.md.j2", "commands/hm/health.md", {}),
        # PLAN-cfr-churn-metrics (0.36.0): /hm:metrics is a manual, read-only
        # command with no on/off flag — always rendered as the full CFR+churn
        # command. `delivery_metrics` config holds only per-project tuning knobs.
        ("commands/hm/metrics.md.j2", "commands/hm/metrics.md", {}),
        ("commands/hm/make.md.j2", "commands/hm/make.md", {}),
        ("commands/hm/configure.md.j2", "commands/hm/configure.md", {}),
        ("commands/hm/uninstall.md.j2", "commands/hm/uninstall.md", {}),
        (_localized("commands/hm/help", locale), "commands/hm/help.md", {}),
        *_skill_files(),
        *_agent_files(preset, agent_models, default_model),
        *_rubric_files(),
        # `.claude/hooks/hooks.json` is NOT rendered (ADR-005 of
        # PLAN-permission-deny-and-hooks-wiring). Claude Code reads project hooks ONLY
        # from settings files; that path is valid for a PLUGIN bundle only, so everything
        # rendered there was dead. Hooks now ship in settings.json's `hooks` key — see
        # templates/settings/*.json.j2. `.cursor/hooks.json` and `.codex/hooks.json` are
        # unaffected: their IDEs really do read them. A stale on-disk copy is retired by
        # cli._retire_stale_hooks_json (pristine-exact-match only) + guarded from the
        # orphan sweep by reconcile._SWEEP_NEVER_DELETE so user-merged hooks are never lost.
        ("observability/dashboard.md.j2", "observability/dashboard.md", {}),
    ]


# Public skeletons retained for backwards-compat counts in tests; both presets
# now install the full inventory. These default to en — locale-specific
# fan-out is exercised through synthesize() at request time.
SIDE_FILES: list[FileSpec] = _base_files(Preset.SIDE)
PRODUCTION_FILES: list[FileSpec] = _base_files(Preset.PRODUCTION)


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


def _codex_target_files(
    *,
    config_dump: dict[str, object] | None = None,
    preset: Preset = Preset.SIDE,
    agent_models: dict[str, AgentModelSpec] | None = None,
    default_model: str = "opus",
) -> list[FileSpec]:
    """Codex target-specific assets: config.toml + AGENTS.md + hooks.json + agents + skills.

    Phase 4 (ADR-008): `agent_models` + `default_model` flow into
    `_codex_agent_files` for per-agent `model_reasoning_effort`. The
    `[profiles.cheap]` / `[profiles.deep]` shortcuts (`codex -p cheap` /
    `codex -p deep`) used to live in this project-local config but Codex
    CLI v0.130+ rejects them at the project layer — they now install at
    USER level via `codex_user_config.bootstrap_user_codex_profiles`,
    invoked from `cli.make` when codex is in targets.
    """
    from harness_maker.render import _make_env  # local import: avoid cycle

    if config_dump is None:
        from harness_maker.models import DevMode, HarnessConfig  # local import: avoid cycle

        # ADR-002: pin dev_mode — do not depend on the class default (see above).
        config_dump = HarnessConfig(dev_mode=DevMode.SPEC_DRIVEN).model_dump(mode="json")
    env = _make_env()
    install_ref = _compute_install_ref()
    loop_body = env.get_template("commands/hm/loop.md.j2").render(
        harness_maker_src_path=install_ref,
        is_codex=True,
        config=config_dump,
    )
    p5_batch_body = env.get_template("commands/hm/loop-p5-batch.md.j2").render(
        harness_maker_src_path=install_ref,
        is_codex=True,
        config=config_dump,
    )
    help_locale_raw = str(config_dump.get("locale", "en")) if config_dump else "en"
    help_body = env.get_template(_localized("commands/hm/help", help_locale_raw)).render(
        harness_maker_src_path=install_ref,
        is_codex=True,
        config=config_dump,
    )
    return [
        (
            "codex/config.toml.j2",
            ".codex/config.toml",
            {"agents": _CODEX_AGENT_META},
        ),
        (
            "codex/AGENTS.md.j2",
            "AGENTS.md",
            {},
        ),
        (
            "codex/hooks.json.j2",
            ".codex/hooks.json",
            {},
        ),
        *_codex_agent_files(preset, agent_models, default_model),
        *_codex_skill_files(),
        *_codex_stage_skills(config_dump=config_dump),
        (
            "codex/loop_skill.md.j2",
            ".agents/skills/hm-loop/SKILL.md",
            {"loop_body": loop_body},
        ),
        (
            "codex/loop_p5_batch_skill.md.j2",
            ".agents/skills/hm-loop-p5-batch/SKILL.md",
            {"p5_batch_body": p5_batch_body},
        ),
        (
            "codex/help_skill.md.j2",
            ".agents/skills/hm-help/SKILL.md",
            {"help_body": help_body},
        ),
    ]


def _codex_skill_files() -> list[FileSpec]:
    """Existing 9 skills dual-rendered to .agents/skills/ for Codex.

    ADR-0007 (0.22.3) removed research-crawler + relevance-filter; base count 11 → 9.
    """
    return [
        (f"skills/{n}/SKILL.md.j2", f".agents/skills/{n}/SKILL.md", {"name": n})
        for n in _ALL_SKILLS
    ]


_CODEX_OUTPUT_ROOTS = (".codex", ".agents")
_CODEX_OUTPUT_FILES = ("AGENTS.md",)


def _is_codex_output(out_path: str) -> bool:
    """Is this rendered file destined for Codex? Derived from the path, never hand-listed.

    The old context builder hard-coded ``False`` on the grounds that Codex bodies are
    pre-rendered by `_codex_stage_skills`. Only half true: the STAGE BODY is pre-rendered
    with ``is_codex=True``, but the WRAPPER around it (`codex/stage_skill.md.j2` and the
    partials it includes) is rendered here — and so received ``False`` for every Codex file
    on disk. Any `is_codex` branch in a wrapper-level partial therefore took the Claude arm
    while looking, in the template source, like it was Codex-aware.

    Derived rather than enumerated because a hand-list is the failure mode this project keeps
    re-learning: a new Codex output would silently miss the flag and nothing would say so.
    An explicit `is_codex` in a FileSpec's own context still wins.
    """
    parts = Path(out_path).parts
    return (parts[0] in _CODEX_OUTPUT_ROOTS if parts else False) or (
        out_path in _CODEX_OUTPUT_FILES
    )


def _codex_stage_skills(*, config_dump: dict[str, object] | None = None) -> list[FileSpec]:
    """Seven stage-trigger SKILL.md files with embedded procedure bodies (is_codex=True)."""
    from harness_maker.render import _make_env  # local import: avoid cycle

    if config_dump is None:
        from harness_maker.models import DevMode, HarnessConfig  # local import: avoid cycle

        # ADR-002: pin dev_mode — do not depend on the class default (see above).
        config_dump = HarnessConfig(dev_mode=DevMode.SPEC_DRIVEN).model_dump(mode="json")
    env = _make_env()
    install_ref = _compute_install_ref()
    out: list[FileSpec] = []
    for s in _ATOMIC_STAGES:
        tpl = env.get_template(f"stages/{s}.md.j2")
        body = tpl.render(
            stage=s,
            project_name="",
            feature="",
            config=config_dump,
            harness_maker_src_path=install_ref,
            is_codex=True,
        )
        out.append(
            (
                "codex/stage_skill.md.j2",
                f".agents/skills/hm-{s}/SKILL.md",
                {"stage": s, "stage_body": body},
            )
        )
    return out


def _normalize_worktree(answers: InterviewAnswers) -> dict[str, Any]:
    """Collapse any generation of `worktree` answers to the one live key.

    PLAN-worktree-side-defaults ADR-001/007. THE normalization point: templates
    read `config.worktree['enabled']` and nothing else, so an answers dict built
    before this change (`{"feature_branch_workflow": True}`, `{"scope": [...]}`,
    or bare `{}`) must still resolve rather than render `StrictUndefined`. Uses the
    same resolver as the runtime reader so the two cannot disagree; a fully absent
    block falls back to the preset default.
    """
    from harness_maker.interview import _preset_extras
    from harness_maker.worktree import resolve_worktree_enabled

    res = resolve_worktree_enabled(answers.worktree)
    if res.value is None:
        default = _preset_extras(answers.preset)["worktree"]["enabled"]
        return {"enabled": bool(default)}
    return {"enabled": res.value}


def synthesize(
    profile: ProjectProfile,
    answers: InterviewAnswers,
    preset: Preset | None = None,
) -> Blueprint:
    """Map preset+answers to a deterministic Blueprint.

    `preset` argument is honored if given; otherwise `answers.preset` wins.
    """
    effective_preset = preset or answers.preset

    # Build config FIRST so atomic/workflow stage bodies render with the user's
    # real locale + deep-gate thresholds. Building it after _base_files() was
    # the silent-default-locale bug (rendered commands hardcoded `en` even when
    # answers.locale == 'ko').
    config = HarnessConfig(
        locale=answers.locale,
        targets=list(answers.targets),
        default_model=answers.default_model,
        agent_models=dict(answers.agent_models),
        preset=effective_preset,
        dev_mode=answers.dev_mode,
        caching=answers.caching,
        autoloop=answers.autoloop,
        memory=answers.memory,
        anti_rot=answers.anti_rot,
        worktree=_normalize_worktree(answers),
        security=answers.security,
        permissions=answers.permissions,
        autonomy=answers.autonomy,
        instrumentation=answers.instrumentation,
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
            "rereview_churn_gate": answers.rereview_churn_gate,
            "rereview_churn_ratio": answers.rereview_churn_ratio,
            "mechanical_checks": list(answers.mechanical_checks),
        },
        project={"domains": list(answers.domains)},
        spec={"dir": "specs/"},
        work_docs={"dir": "work-docs/"},
        ref_folders=list(answers.ref_folders),
        second_brain=answers.second_brain,
        sibling_repos=list(answers.sibling_repos),
        mcp_servers=dict(answers.mcp_servers),
        wrapup_docs=list(answers.wrapup_docs),
        schema_version=answers.schema_version,
        interview=answers.interview,
        # PLAN-auto-feedback-2026-05 ADR-002 — propagate opt-in flag to render.
        feedback=answers.feedback,
        # PLAN-second-opinion-multi-model — propagate second_opinion so
        # config.second_opinion.{models,agents,codex,antigravity} is available in every
        # agent template's render context (ADR-002/011 Jinja-loop pattern).
        second_opinion=answers.second_opinion,
        # Root-level toolchains (ADR-002) — without this the rendered harness.yaml never
        # carries the key, so the reverse mapper reads it back as unconfigured and every
        # re-render silently discards it.
        toolchains=list(answers.toolchains),
        # PLAN-cfr-churn-metrics ADR-003 — propagate the per-project tuning so
        # /hm:metrics + health templates can read window/tag/path knobs.
        delivery_metrics=answers.delivery_metrics,
        # PLAN-harness-economics-observability ADR-004 — propagate the economics tuning
        # so /hm:metrics + health templates can read the window/estimator knobs.
        economics=answers.economics,
        # ADR-011: without this the rendered harness.yaml always emits the empty
        # default, so `--update` silently disarms the delegation rollback switch.
        delegation=answers.delegation,
    )
    config_dump = config.model_dump(mode="json")

    base_specs = _base_files(
        effective_preset,
        answers.locale,
        agent_models=dict(answers.agent_models),
        default_model=answers.default_model,
        config_dump=config_dump,
    )

    file_specs: list[FileSpec] = [
        *base_specs,
        # PLAN-second-opinion-multi-model ADR-004 — schema only when a model is configured.
        *_schema_files(answers.second_opinion.enabled),
    ]

    if Target.CURSOR in answers.targets:
        file_specs.extend(_cursor_target_files())

    if Target.CODEX in answers.targets:
        file_specs.extend(
            _codex_target_files(
                config_dump=config_dump,
                preset=effective_preset,
                agent_models=dict(answers.agent_models),
                default_model=answers.default_model,
            )
        )

    # Skills inventory + enabled list aren't part of HarnessConfig today, but
    # templates need them; expose via per-file context.
    # PLAN-review-round-inflation ADR-005. Both presets force-enable this skill
    # (`interview.py`), but `skills.enabled` is user-editable and the pointer at
    # its §5 renders unguarded — so a harness that trimmed it would ship a
    # pointer aimed at a document it never loads, and the loop's termination
    # contract would be reachable only by chance. Auto-add and say so; never
    # abort (CLAUDE.md checkpoint #1 — a raise here turns `--update` into a total
    # render failure for that user with no migration path).
    enabled_skills = list(answers.skills.get("enabled", []))
    if ROUND_STATE_SKILL not in enabled_skills:
        enabled_skills.append(ROUND_STATE_SKILL)
        logger.warning(
            "%s was not in skills.enabled; re-adding it. review.md.j2 points at its §5 "
            "(the auto-fix loop's round-state contract) from a line that renders in every "
            "harness, so disabling the skill leaves that pointer dangling.",
            ROUND_STATE_SKILL,
        )
    skills_dump = {
        "installed": answers.skills.get("installed", []),
        "enabled": enabled_skills,
    }
    install_ref = _compute_install_ref()
    # PLAN-auto-feedback-2026-05 ADR-005: in-band LLM feedback dispatcher
    # block is gated on `feedback.enabled` at the wrapper render level. Inject
    # globally (StrictUndefined raises on ACCESS, not PRESENCE — templates
    # that don't reference `feedback_enabled` are unaffected).
    feedback_enabled = bool(config_dump.get("feedback", {}).get("enabled", False))
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
                "harness_maker_src_path": install_ref,
                "feedback_enabled": feedback_enabled,
                "is_codex": ctx.get("is_codex", _is_codex_output(out_path)),
            },
            frontmatter=_command_frontmatter(out_path),
        )
        for tpl, out_path, ctx in file_specs
    ]
    return Blueprint(config=config, files=files)
