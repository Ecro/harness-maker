"""Per-axis recommendation registry + confidence-bucketed dispatcher.

Phase 1 shipped the framework; Phase 4 registers the first two concrete
recommenders (``wrapup_docs`` via filesystem probe, ``mcp_servers`` via
framework-to-server mapping). The registry signature is
``Callable[[ProjectProfile, Path], Recommendation | None]`` because some
recommenders (notably ``wrapup_docs``) need filesystem access; Phase 1
anticipated a one-arg shape but the project_dir dependency forces a
framework-level widening in Phase 4.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from harness_maker.models import (
    Confidence,
    DevMode,
    Preset,
    ProjectProfile,
    Recommendation,
    RecommendationEvidence,
)

# Recommender signature: takes profile + project_dir, returns a single
# Recommendation or None (when the recommender has no signal to surface).
Recommender = Callable[[ProjectProfile, Path], Recommendation | None]

_REGISTRY: dict[str, Recommender] = {}

# HIGH-first ordering for confidence-bucketed fan-out (ADR-004/007).
_BUCKET_ORDER: dict[Confidence, int] = {
    Confidence.HIGH: 0,
    Confidence.MEDIUM: 1,
    Confidence.LOW: 2,
}


def register(axis: str) -> Callable[[Recommender], Recommender]:
    """Decorator-style registry entry; duplicate axes fail loudly at import."""
    if not axis:
        raise ValueError("axis name must be non-empty")

    def _decorator(fn: Recommender) -> Recommender:
        if axis in _REGISTRY:
            raise ValueError(f"axis {axis!r} already registered")
        _REGISTRY[axis] = fn
        return fn

    return _decorator


def recommend(
    axis: str,
    profile: ProjectProfile,
    project_dir: Path,
) -> Recommendation | None:
    """Dispatch to a single registered recommender; unknown axis returns None."""
    fn = _REGISTRY.get(axis)
    if fn is None:
        return None
    result = fn(profile, project_dir)
    if result is None:
        return None
    if result.axis != axis:
        raise ValueError(
            f"recommender for axis {axis!r} returned Recommendation "
            f"with axis={result.axis!r}",
        )
    return result


def recommend_all(
    profile: ProjectProfile,
    project_dir: Path,
) -> list[Recommendation]:
    """Fan-out across all registered axes, HIGH bucket first.

    Recommenders may return None when they have insufficient signal; those
    are dropped from the result list.
    """
    out: list[Recommendation] = []
    for axis, fn in _REGISTRY.items():
        result = fn(profile, project_dir)
        if result is None:
            continue
        if result.axis != axis:
            raise ValueError(
                f"recommender for axis {axis!r} returned Recommendation "
                f"with axis={result.axis!r}",
            )
        out.append(result)
    out.sort(key=lambda r: _BUCKET_ORDER[r.confidence])
    return out


# ──────────────────────────────────────────────────────────────────────────────
# Phase 4 concrete recommenders
# ──────────────────────────────────────────────────────────────────────────────

# Exact-name candidates probed at the repo root for wrapup_docs detection.
# Keep this list conservative — a false positive nudges the user toward
# updating a file they didn't think of, which is annoying but not destructive.
_WRAPUP_EXACT_CANDIDATES: tuple[str, ...] = (
    "CHANGELOG.md",
    "TODO.md",
    "HISTORY.md",
    "CHANGELOG",
    "HISTORY",
)

# Glob candidates probed at the repo root (relative). ADR index docs live
# under either docs/ADR-*.md (uppercase prefix) or docs/adrs/*.md (folder).
_WRAPUP_GLOB_CANDIDATES: tuple[str, ...] = (
    "docs/ADR-*.md",
    "docs/adrs/*.md",
)


@register("wrapup_docs")
def recommend_wrapup_docs(
    profile: ProjectProfile,  # noqa: ARG001 — profile unused; filesystem is the signal.
    project_dir: Path,
) -> Recommendation | None:
    """Probe filesystem for changelog/TODO/ADR docs the wrapup stage should update.

    Confidence is HIGH because the signal is an explicit filename match — the
    file literally exists, no inference. Returns None when no candidates hit.
    """
    found: list[str] = []
    for name in _WRAPUP_EXACT_CANDIDATES:
        if (project_dir / name).is_file():
            found.append(name)
    for pattern in _WRAPUP_GLOB_CANDIDATES:
        for hit in sorted(project_dir.glob(pattern)):
            if hit.is_file():
                rel = hit.relative_to(project_dir)
                found.append(rel.as_posix())
    if not found:
        return None
    # De-dup while preserving order (a CHANGELOG.md could match both the exact
    # candidate and a future glob; defensive).
    seen: set[str] = set()
    ordered: list[str] = []
    for name in found:
        if name not in seen:
            seen.add(name)
            ordered.append(name)
    signal_head = ordered[0]
    return Recommendation(
        axis="wrapup_docs",
        value=ordered,
        confidence=Confidence.HIGH,
        evidence=RecommendationEvidence(
            n_observations=len(ordered),
            top_3_signals=ordered[:3],
            confidence=Confidence.HIGH,
        ),
        signal=f"detected: {signal_head}",
    )


# Framework → MCP server name. Conservative: only ship mappings for MCPs
# that exist in the public ecosystem. Adding placeholder names (e.g.
# "tauri-test") would surface a server the user can't actually install.
_FRAMEWORK_MCP_TABLE: dict[str, str] = {
    "react": "playwright",
    "vue": "playwright",
    "svelte": "playwright",
    "next": "playwright",
    "remix": "playwright",
    "astro": "playwright",
}

# Standard MCP server configs (command + args + env). Wired into
# .cursor/mcp.json / .claude/.mcp.json by downstream renderers.
_MCP_SERVER_CONFIGS: dict[str, dict[str, Any]] = {
    "playwright": {
        "command": "npx",
        "args": ["@playwright/mcp@latest"],
        "env": {},
    },
}


@register("mcp_servers")
def recommend_mcp_servers(
    profile: ProjectProfile,
    project_dir: Path,  # noqa: ARG001 — frameworks come from profile, not disk.
) -> Recommendation | None:
    """Map detected frameworks to known MCP server suggestions.

    Confidence is MEDIUM: the framework → server mapping is an opinion
    (front-end stacks benefit from a browser-automation MCP), not an
    identity match. Per Confidence.MEDIUM docstring, this is exactly the
    inference-mapping bucket.
    """
    matched_servers: dict[str, dict[str, Any]] = {}
    matched_frameworks: list[str] = []
    for fw in profile.frameworks:
        server_name = _FRAMEWORK_MCP_TABLE.get(fw)
        if server_name is None:
            continue
        if server_name in _MCP_SERVER_CONFIGS and server_name not in matched_servers:
            matched_servers[server_name] = dict(_MCP_SERVER_CONFIGS[server_name])
        matched_frameworks.append(fw)
    if not matched_servers:
        return None
    return Recommendation(
        axis="mcp_servers",
        value=matched_servers,
        confidence=Confidence.MEDIUM,
        evidence=RecommendationEvidence(
            n_observations=len(matched_frameworks),
            top_3_signals=matched_frameworks[:3],
            confidence=Confidence.MEDIUM,
        ),
        signal=f"frameworks: {', '.join(matched_frameworks[:3])}",
    )


# ──────────────────────────────────────────────────────────────────────────────
# Phase 8 migrated recommenders — preset / dev_mode / mechanical_checks / second_brain
#
# Confidence assignments (PLAN validator W3 backward-compat):
#   preset            → MEDIUM (today the interview always asks; silent flip
#                       would surprise 0.11.x users on upgrade — Phase 8 stays
#                       conservative; tighten in follow-up release once
#                       telemetry shows zero override pattern)
#   dev_mode          → MEDIUM (same reasoning)
#   mechanical_checks → HIGH   (already silent today via mechanical_checks
#                       template — behavior parity with current)
#   second_brain      → HIGH   (vault_member detection is identity — the
#                       file literally exists)
# ──────────────────────────────────────────────────────────────────────────────


@register("preset")
def recommend_preset(
    profile: ProjectProfile,
    project_dir: Path,  # noqa: ARG001 — preset comes from profile signals, not disk.
) -> Recommendation:
    """Small + experiment/maintenance → Side; else Production.

    MEDIUM confidence per ADR-004/007: heuristic over scale + lifecycle is an
    inference, not an identity match. validator W3 keeps this MEDIUM on first
    release so 0.11.x users get an explicit prompt rather than a silent flip.
    """
    if profile.scale == "small" and profile.lifecycle in {"experiment", "maintenance"}:
        value = Preset.SIDE
    else:
        value = Preset.PRODUCTION
    signal = f"scale={profile.scale}, lifecycle={profile.lifecycle}"
    return Recommendation(
        axis="preset",
        value=value,
        confidence=Confidence.MEDIUM,
        evidence=RecommendationEvidence(
            n_observations=2,
            top_3_signals=[f"scale:{profile.scale}", f"lifecycle:{profile.lifecycle}"],
            confidence=Confidence.MEDIUM,
        ),
        signal=signal,
    )


@register("dev_mode")
def recommend_dev_mode(
    profile: ProjectProfile,
    project_dir: Path,
) -> Recommendation:
    """Side → task-driven (lighter); Production → spec-driven.

    MEDIUM confidence: dev_mode is derived from preset, which is itself an
    inference. Bucket parity with preset keeps the UX consistent.
    """
    preset_rec = recommend_preset(profile, project_dir)
    preset_value: Preset = preset_rec.value if preset_rec is not None else Preset.SIDE
    value = DevMode.SPEC_DRIVEN if preset_value == Preset.PRODUCTION else DevMode.TASK_DRIVEN
    return Recommendation(
        axis="dev_mode",
        value=value,
        confidence=Confidence.MEDIUM,
        evidence=RecommendationEvidence(
            n_observations=1,
            top_3_signals=[f"preset:{preset_value.value}"],
            confidence=Confidence.MEDIUM,
        ),
        signal=f"preset={preset_value.value}",
    )


@register("mechanical_checks")
def recommend_mechanical_checks(
    profile: ProjectProfile,
    project_dir: Path,  # noqa: ARG001 — mechanical_checks come from profile probe.
) -> Recommendation | None:
    """Surface the profiler's detected mechanical checks.

    HIGH confidence: profile.detected_checks is built from explicit filename
    matches (pyproject.toml present → ``ruff check .`` etc.). Returns None
    when the profile detected nothing (no false-positive nudge).
    """
    if not profile.detected_checks:
        return None
    checks = list(profile.detected_checks)
    return Recommendation(
        axis="mechanical_checks",
        value=checks,
        confidence=Confidence.HIGH,
        evidence=RecommendationEvidence(
            n_observations=len(checks),
            top_3_signals=checks[:3],
            confidence=Confidence.HIGH,
        ),
        signal=f"detected: {checks[0]}",
    )


@register("second_brain")
def recommend_second_brain(
    profile: ProjectProfile,
    project_dir: Path,  # noqa: ARG001 — vault membership comes from profile probe.
) -> Recommendation | None:
    """Suggest enabling Second Brain when the project is a known vault member.

    HIGH confidence: profile.vault_member is set from explicit file existence
    (``.claude/obsidian.json``) — identity-level evidence. Returns None when
    the project is not a vault member (no surface).
    """
    if not profile.vault_member:
        return None
    return Recommendation(
        axis="second_brain",
        value=True,
        confidence=Confidence.HIGH,
        evidence=RecommendationEvidence(
            n_observations=1,
            top_3_signals=["vault_member"],
            confidence=Confidence.HIGH,
        ),
        signal="detected: .claude/obsidian.json",
    )
