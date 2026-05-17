"""Compute personalization rubric score from telemetry + harness.yaml + ProjectProfile."""

from __future__ import annotations

import re
import sys
from collections import Counter
from datetime import UTC, datetime, timedelta
from importlib import resources
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict

from harness_maker.detection_cache import load_or_run
from harness_maker.io_utils import atomic_write
from harness_maker.models import AdaptiveConfig, Confidence, ProjectProfile
from harness_maker.telemetry import OverrideRecord, load_overrides

# ── Evidence-bearing ActionItem (ADR-011) ──────────────────────────────────
#
# The ai_readiness ActionItem (improvement.py) uses extra="forbid" and has
# no evidence field. ADR-011 mandates a structured evidence schema per item,
# so we cannot reuse that model verbatim. The pattern (priority + summary +
# suggestion + ranked list inside a Plan) is mirrored exactly.


class ActionEvidence(BaseModel):
    """Per-action evidence required by ADR-011 (drop_when contract)."""

    model_config = ConfigDict(strict=True, extra="forbid")

    n_observations: int
    top_3_signals: list[str]
    confidence: Confidence


class PersonalizationActionItem(BaseModel):
    """One concrete personalization improvement, with locked evidence schema."""

    model_config = ConfigDict(strict=True, extra="forbid")

    priority: str  # P0 | P1 | P2
    dimension: str
    summary: str
    suggestion: str
    evidence: ActionEvidence


class PersonalizationPlan(BaseModel):
    """Composite-score + ranked actions for /hm:personalization-audit."""

    model_config = ConfigDict(strict=True, extra="forbid")

    composite_score: int  # 0-100
    tier: str  # bronze | silver | gold | platinum
    layer_scores: dict[str, int]  # l1_conversion, l2_stability, l3_cadence
    actions: list[PersonalizationActionItem]


# ── Rubric loading ─────────────────────────────────────────────────────────


def _default_rubric_path() -> Path:
    """Locate the packaged rubric without relying on the dev-cwd."""
    # importlib.resources works once installed (uv_build) and during dev.
    pkg_root = resources.files("harness_maker")
    return Path(str(pkg_root)) / "rubrics" / "personalization.yaml"


def _load_rubric(rubric_path: Path | None) -> dict[str, Any]:
    """Parse rubric YAML; raise ValueError with a context-rich message on
    structural drift (mirrors validator C3 forward-compat warning style)."""
    path = rubric_path if rubric_path is not None else _default_rubric_path()
    if not path.is_file():
        msg = f"personalization rubric not found at {path}"
        raise FileNotFoundError(msg)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        msg = f"personalization rubric at {path} is not a mapping"
        raise ValueError(msg)
    return data


# ── Layer scoring ──────────────────────────────────────────────────────────


_HIGH_DETECTED_RE = re.compile(
    r"#\s*detected:.*\(high\)",
    re.IGNORECASE,
)


def _count_high_silent_lines(harness_yaml_text: str) -> int:
    """High-confidence detections render as ``# detected: ... (high)`` comments
    in harness.yaml (Phase 3 silent emit). Counting those lines approximates
    the ``high_silent`` term in L1's formula without a separate telemetry feed.
    """
    return sum(1 for line in harness_yaml_text.splitlines() if _HIGH_DETECTED_RE.search(line))


def _filter_recent(records: list[OverrideRecord], now: datetime, days: int) -> list[OverrideRecord]:
    """Keep only records whose ts is within ``days`` of ``now``.

    Records with unparseable ts are dropped (defensive: a corrupt timestamp
    should not silently inflate the override count). The window is inclusive
    on the lower bound."""
    cutoff = now - timedelta(days=days)
    out: list[OverrideRecord] = []
    for r in records:
        try:
            ts = datetime.fromisoformat(r.ts)
        except (TypeError, ValueError):
            continue
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=UTC)
        if ts >= cutoff:
            out.append(r)
    return out


def compute_l1_conversion(
    medium_accepted: int,
    high_silent: int,
    total_recommendations: int,
) -> int:
    """ADR-011 L1 formula. Bounded to [0, 100] to defend against future drift."""
    denom = max(total_recommendations, 1)
    raw = (medium_accepted + high_silent) / denom * 100
    return max(0, min(100, round(raw)))


def compute_l2_stability(override_events_last_30d: int, penalty_factor: int = 5) -> int:
    """ADR-011 L2 formula: 100 - min(100, N * penalty_factor)."""
    return max(0, 100 - min(100, override_events_last_30d * penalty_factor))


def compute_l3_cadence(
    days_since_last_audit: float | None,
    disable_telemetry: bool,
    *,
    window_days: int = 14,
) -> int:
    """ADR-011 L3 score table. ``days_since_last_audit=None`` means "never run"
    → the audit-cadence condition fails."""
    audit_ok = days_since_last_audit is not None and days_since_last_audit <= window_days
    telemetry_ok = not disable_telemetry
    if audit_ok and telemetry_ok:
        return 100
    if audit_ok or telemetry_ok:
        return 50
    return 0


def compute_composite(
    l1: int,
    l2: int,
    l3: int,
    *,
    weights: dict[str, float] | None = None,
) -> int:
    """ADR-011 weighted sum, rounded to int and bounded to [0, 100]."""
    w = weights or {"l1_conversion": 0.4, "l2_stability": 0.3, "l3_cadence": 0.3}
    raw = l1 * w["l1_conversion"] + l2 * w["l2_stability"] + l3 * w["l3_cadence"]
    return max(0, min(100, round(raw)))


def assign_tier(composite: int, tiers: dict[str, dict[str, int]]) -> str:
    """Map composite to bronze/silver/gold/platinum using rubric tier table."""
    # Defensive: iterate in ascending min order, return the matching band.
    for name, band in sorted(tiers.items(), key=lambda kv: kv[1]["min"]):
        if band["min"] <= composite <= band["max"]:
            return name
    return "bronze"


# ── Action generation ──────────────────────────────────────────────────────


def _confidence_for(n: int) -> Confidence:
    """Bucket observation count into ADR-004/007 confidence buckets.

    ≥5 overrides on one axis is a strong signal the default is wrong;
    2-4 is suggestive; 1 is noise."""
    if n >= 5:
        return Confidence.HIGH
    if n >= 2:
        return Confidence.MEDIUM
    return Confidence.LOW


def _action_for_frequent_axis(
    axis_path: str,
    count: int,
    contributing_paths: list[str],
) -> PersonalizationActionItem | None:
    """Build the ADR-011-shaped ActionItem; drop if evidence schema would
    fail the rubric's drop_when contract."""
    if count == 0 or not contributing_paths:
        return None
    evidence = ActionEvidence(
        n_observations=count,
        top_3_signals=contributing_paths[:3],
        confidence=_confidence_for(count),
    )
    return PersonalizationActionItem(
        priority="P1" if count >= 5 else "P2",
        dimension="override_stability",
        summary=f"Axis '{axis_path}' overridden {count} times in last 30 days",
        suggestion=(
            f"Consider changing the default for '{axis_path}' to match the "
            "user's repeated override target."
        ),
        evidence=evidence,
    )


def _action_for_l3_failure(
    l3: int,
    days_since_audit: float | None,
    disable_telemetry: bool,
    window_days: int,
) -> PersonalizationActionItem | None:
    """When L3 == 0, surface the specific failing condition(s)."""
    if l3 != 0:
        return None
    reasons: list[str] = []
    if disable_telemetry:
        reasons.append("disable_telemetry=true")
    if days_since_audit is None:
        reasons.append("no previous audit timestamp")
    elif days_since_audit > window_days:
        reasons.append(f"last audit {int(days_since_audit)} days ago")
    if not reasons:
        return None
    if disable_telemetry:
        summary = "Adaptive telemetry is opt-ed out — audit cadence cannot improve."
        suggestion = (
            "Set ``adaptive.disable_telemetry: false`` in .claude/harness.yaml "
            "to enable Phase 9 override capture (100% local, ADR-005)."
        )
    else:
        summary = "Audit cadence stale — run /hm:personalization-audit more often."
        suggestion = "Re-run /hm:personalization-audit at least every 14 days."
    evidence = ActionEvidence(
        n_observations=len(reasons),
        top_3_signals=reasons[:3],
        confidence=Confidence.HIGH,
    )
    return PersonalizationActionItem(
        priority="P1",
        dimension="audit_cadence",
        summary=summary,
        suggestion=suggestion,
        evidence=evidence,
    )


# ── State loading helpers ──────────────────────────────────────────────────


def _read_harness_yaml(project_dir: Path) -> dict[str, Any]:
    """Parse .claude/harness.yaml or return {} if absent.

    Validator C3 silent-fallback: a missing file is treated as a fresh
    bronze-tier project, not an error."""
    path = project_dir / ".claude" / "harness.yaml"
    if not path.is_file():
        return {}
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return {}
    try:
        for doc in yaml.safe_load_all(text):
            if isinstance(doc, dict) and "preset" in doc:
                return doc
    except yaml.YAMLError:
        return {}
    return {}


def _read_adaptive_config(harness_data: dict[str, Any]) -> AdaptiveConfig:
    """Reconstruct AdaptiveConfig from harness.yaml, falling back to defaults."""
    raw = harness_data.get("adaptive")
    if not isinstance(raw, dict):
        return AdaptiveConfig()
    try:
        return AdaptiveConfig.model_validate(raw)
    except (ValueError, TypeError):
        return AdaptiveConfig()


def _last_audit_path(project_dir: Path) -> Path:
    return project_dir / ".claude" / "observability" / "adaptive" / "last-audit.txt"


def _read_last_audit(project_dir: Path) -> datetime | None:
    """Read ISO timestamp from the last-audit marker; return None if absent or
    unparseable (treated as "never run" by L3)."""
    path = _last_audit_path(project_dir)
    if not path.is_file():
        return None
    try:
        text = path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    try:
        ts = datetime.fromisoformat(text)
    except (TypeError, ValueError):
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=UTC)
    return ts


def _profile_total_recommendations(profile: ProjectProfile | None) -> int:
    """Approximate ``total_recommendations`` from the cached ProjectProfile.

    Each entry in ``detection_confidence`` represents one axis the
    recommendation framework had a confidence reading for — the closest
    available proxy for "total recommendations issued"."""
    if profile is None:
        return 0
    return len(profile.detection_confidence)


# ── Public entrypoint ──────────────────────────────────────────────────────


def run_audit(
    project_dir: Path,
    *,
    rubric_path: Path | None = None,
    now: datetime | None = None,
) -> PersonalizationPlan:
    """Compute composite-score per ADR-011 and return a PersonalizationPlan."""
    rubric = _load_rubric(rubric_path)
    current = now if now is not None else datetime.now(UTC)
    if current.tzinfo is None:
        current = current.replace(tzinfo=UTC)

    overrides = load_overrides(project_dir)
    harness_data = _read_harness_yaml(project_dir)
    adaptive = _read_adaptive_config(harness_data)
    profile = load_or_run(project_dir)
    harness_yaml_path = project_dir / ".claude" / "harness.yaml"
    yaml_text = harness_yaml_path.read_text(encoding="utf-8") if harness_yaml_path.is_file() else ""

    # ── L1: conversion ─────────────────────────────────────────────────
    high_silent = _count_high_silent_lines(yaml_text)
    medium_accepted = sum(1 for r in overrides if r.source == "configure-exit")
    total_recs = max(
        _profile_total_recommendations(profile),
        high_silent + medium_accepted,
    )
    l1 = compute_l1_conversion(medium_accepted, high_silent, total_recs)

    # ── L2: stability ──────────────────────────────────────────────────
    l2_window = int(rubric["layers"]["l2_stability"].get("window_days", 30))
    penalty = int(rubric["layers"]["l2_stability"].get("penalty_factor", 5))
    recent = _filter_recent(overrides, current, l2_window)
    l2 = compute_l2_stability(len(recent), penalty)

    # ── L3: cadence ────────────────────────────────────────────────────
    l3_window = int(rubric["layers"]["l3_cadence"].get("window_days", 14))
    last_audit = _read_last_audit(project_dir)
    days_since = (current - last_audit).total_seconds() / 86400.0 if last_audit else None
    l3 = compute_l3_cadence(days_since, adaptive.disable_telemetry, window_days=l3_window)

    # ── Composite + tier ──────────────────────────────────────────────
    weights = rubric.get("layer_weights")
    w = weights if isinstance(weights, dict) else None
    composite = compute_composite(l1, l2, l3, weights=w)
    tier = assign_tier(composite, rubric["tiers"])

    # ── Actions ────────────────────────────────────────────────────────
    actions: list[PersonalizationActionItem] = []
    axis_counts: Counter[str] = Counter(r.axis_path for r in recent)
    for axis_path, count in axis_counts.most_common():
        if count < 3:
            continue
        # contributing paths = the same axis path repeated; we surface the
        # axis itself plus its parent components as a top-3 hint.
        parts = axis_path.split(".")
        contrib = [axis_path]
        for i in range(len(parts) - 1, 0, -1):
            ancestor = ".".join(parts[:i])
            if ancestor and ancestor not in contrib:
                contrib.append(ancestor)
            if len(contrib) >= 3:
                break
        item = _action_for_frequent_axis(axis_path, count, contrib)
        if item is not None:
            actions.append(item)

    l3_action = _action_for_l3_failure(
        l3,
        days_since,
        adaptive.disable_telemetry,
        l3_window,
    )
    if l3_action is not None:
        actions.append(l3_action)

    # ADR-011 drop_when: enforced at construction (n=0 or empty signals
    # would already have been caught by _action_for_frequent_axis), but
    # we apply the same filter defensively here so any future code path
    # that builds an item directly cannot violate the contract.
    actions = [
        a for a in actions if a.evidence.n_observations > 0 and len(a.evidence.top_3_signals) > 0
    ]

    # Rank: P0 → P1 → P2 then by descending observation count.
    rank = {"P0": 0, "P1": 1, "P2": 2}
    actions.sort(key=lambda a: (rank.get(a.priority, 9), -a.evidence.n_observations))

    # ── Persist last-audit timestamp ───────────────────────────────────
    atomic_write(_last_audit_path(project_dir), current.isoformat())

    return PersonalizationPlan(
        composite_score=composite,
        tier=tier,
        layer_scores={"l1_conversion": l1, "l2_stability": l2, "l3_cadence": l3},
        actions=actions,
    )


def render_personalization_summary(
    plan: PersonalizationPlan,
    *,
    max_actions: int = 10,
) -> str:
    """Mirror render_terminal_summary from ai_readiness — concise stdout text."""
    l1_score = plan.layer_scores["l1_conversion"]
    l2_score = plan.layer_scores["l2_stability"]
    l3_score = plan.layer_scores["l3_cadence"]
    lines = [
        f"personalization-audit: {plan.composite_score} / 100  (tier: {plan.tier})",
        "",
        "Layer scores:",
        f"  l1_conversion : {l1_score:>3}  (detection→recommendation conversion)",
        f"  l2_stability  : {l2_score:>3}  (override frequency, 30d window)",
        f"  l3_cadence    : {l3_score:>3}  (adaptive opt-in + audit cadence)",
        "",
    ]
    if not plan.actions:
        lines.append("No actions — personalization looks healthy.")
        return "\n".join(lines)

    lines.append(f"Top {min(max_actions, len(plan.actions))} of {len(plan.actions)} actions:")
    for a in plan.actions[:max_actions]:
        lines.append(f"  [{a.priority}] {a.dimension} :: {a.summary}")
        lines.append(f"        → {a.suggestion}")
        lines.append(
            f"        evidence: n={a.evidence.n_observations}, "
            f"confidence={a.evidence.confidence.value}, "
            f"signals={a.evidence.top_3_signals}"
        )
    if len(plan.actions) > max_actions:
        lines.append(f"  … {len(plan.actions) - max_actions} more")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """Module entrypoint: ``python -m harness_maker.personalization_audit``."""
    args = argv if argv is not None else sys.argv[1:]
    target = Path(args[0]).resolve() if args else Path.cwd().resolve()
    plan = run_audit(target)
    print(render_personalization_summary(plan))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
