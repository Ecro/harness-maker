"""Batch SPEC generator (P5 skeleton authoring).

Walks the catalog, matches test inventory by feature name, and emits a valid
``SPEC-{slug}.md`` + ``SPEC-{slug}.machine.yaml`` pair per Feature. Output
SPECs pass schema_validate but use ``pending_test=true`` on all AC — they
are skeletons meant to be refined per-batch via `/hm:loop p5-batch-N`.

L1 cluster SPECs also emitted as minimal stubs so cross_validate rule-6
(parent_spec exists) is satisfied without manual authoring of 15 L1 files.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from harness_maker.io_utils import atomic_write
from harness_maker.spec_inventory.catalog import SEED_L1_CLUSTERS
from harness_maker.spec_inventory.catalog_schema import (
    Catalog,
    Feature,
)

# Heuristic feature_id token → L1 cluster slug. Order matters: first match wins.
L1_ASSIGNMENT_RULES: tuple[tuple[tuple[str, ...], str], ...] = (
    (("render", "synthesize", "reconcile"), "rendering"),
    (("reconcile", "block-merge", "block_merge"), "reconciliation"),
    (("synthesize", "harness-yaml"), "synthesis"),
    (("interview", "eig", "common-ground", "common_ground", "inequality"), "interview"),
    (("autoloop", "trajectory"), "autoloop"),
    (
        (
            "reviewer",
            "code-reviewer",
            "security-reviewer",
            "performance-reviewer",
            "concurrency-reviewer",
            "test-reviewer",
            "ux-reviewer",
            "consensus-arbiter",
            "plan-validator",
            "code-verifier",
            "executor",
            "stuck",
        ),
        "reviewers",
    ),
    (("security", "secscan", "permission", "gate"), "security-permissions"),
    (
        (
            "observability",
            "telemetry",
            "health",
            "drift",
            "intent-miss",
            "coverage-classifier",
            "dashboard",
            "verification-cache",
        ),
        "observability",
    ),
    (
        ("memory", "episodic", "semantic", "second-brain", "second_brain", "memory-retrieve"),
        "memory",
    ),
    (("worktree",), "worktree"),
    (
        ("plugin", "manifest", "harness-yaml", "harness_yaml", "config", "configure", "cli"),
        "configuration-manifests",
    ),
    (
        ("hook", "loop-gate", "loop_gate", "flush", "post-write", "post_write", "sessionstart"),
        "hooks",
    ),
    (
        ("template", "tpl-", "claude-md", "claude_md", "codex", "cursor", "settings", "rubric"),
        "templates",
    ),
    (("cache", "detection-cache", "detection_cache", "cache-diagnostics"), "caching"),
    (("crawler", "anthropic-blog", "arxiv", "github-releases", "osv"), "crawler"),
    (("agent-",), "reviewers"),  # generic agent fallback
    (("skill-",), "templates"),  # generic skill fallback
    (("hook-",), "hooks"),
)


def _assign_l1(feature: Feature) -> str:
    """Pick the best L1 cluster for a feature via name tokens."""
    fid = feature.id.lower()
    name_tokens = set(fid.replace("-", "_").split("_"))
    for keywords, cluster in L1_ASSIGNMENT_RULES:
        for kw in keywords:
            kw_clean = kw.replace("-", "_").rstrip("_")
            if kw in fid or kw_clean in name_tokens:
                return cluster
    # Fallback: most generic
    return "configuration-manifests"


_TIER_FLOOR: dict[int, int | None] = {1: 85, 2: 70, 3: None}


def _match_tests_for_feature(feature: Feature, inventory: list[dict[str, Any]]) -> list[str]:
    """Return up to 5 valid pytest nodeids (file::test) from inventory."""
    fid = feature.id.replace("-", "_")
    matches: list[str] = []
    for entry in inventory:
        tid = entry.get("test_id", "")
        if "::" not in tid:
            continue  # Only accept proper pytest nodeids; reject bare file paths.
        if fid in entry.get("inferred_feature", "") or fid in tid:
            matches.append(tid)
            if len(matches) >= 5:
                break
    return matches


@dataclass(frozen=True)
class GeneratedSpec:
    slug: str
    md_text: str
    yaml_text: str


def _make_ac_for_python(feature: Feature, test_ids: list[str]) -> list[dict[str, Any]]:
    """One mechanical AC seeded with suggested test_ids (always pending_test=true).

    test_ids[] is a hint from the P0 reverse-map heuristic — not a verified
    pytest-collect resolution. Skeletons stay pending_test=true so cross_validate
    rule-3 doesn't enforce against unverified suggestions; a later /hm:spec
    refinement run flips this to false once the AC↔test contract is validated.
    """
    return [
        {
            "id": "AC-001",
            "title": f"{feature.id} public API behaves per documented contract",
            "type": "mechanical",
            "test_ids": test_ids[:3],  # capped suggestion list
            "executable_predicate": f"# placeholder — refine in /hm:spec {feature.id}",
            "pending_test": True,
        }
    ]


def _make_ac_for_template(feature: Feature, test_ids: list[str]) -> list[dict[str, Any]]:
    """Three-layer AC per ADR-009 for non-Python features."""
    return [
        {
            "id": "AC-001",
            "title": "rendered output snapshot-stable (Layer 1)",
            "type": "mechanical",
            "test_ids": [t for t in test_ids if "snapshot" in t][:2] or [],
            "executable_predicate": (
                f"rendered_bytes('{feature.path}') == read_snapshot(matching_snap_path)"
            ),
            "pending_test": True,
        },
        {
            "id": "AC-002",
            "title": "rendered output parses under consumer schema (Layer 2)",
            "type": "mechanical",
            "test_ids": [],
            "executable_predicate": (
                f"consumer_parser('{feature.path}').parse(rendered) is not None"
            ),
            "pending_test": True,
        },
        {
            "id": "AC-003",
            "title": "rendered prompt fulfills SPEC intent (Layer 3, LLM-judged)",
            "type": "judgment",
            "test_ids": [],
            "rubric_id": "agent_prompt" if feature.kind == "agent" else "skill",
            "pending_test": True,
        },
    ]


def render_skeleton_spec(
    feature: Feature,
    catalog: Catalog,
    inventory: list[dict[str, Any]],
) -> GeneratedSpec:
    """Render one Feature → (SPEC.md text, SPEC.machine.yaml text)."""
    parent_slug = feature.parent_spec_slug or _assign_l1(feature)
    parent_full = f"SPEC-{parent_slug}"
    test_ids = _match_tests_for_feature(feature, inventory)
    tier_int = int(feature.effective_tier)
    floor = _TIER_FLOOR[tier_int]

    if feature.kind == "python":
        ac_dicts = _make_ac_for_python(feature, test_ids)
        paths_to_mutate = [feature.path]
        mutation_threshold = floor
    else:
        ac_dicts = _make_ac_for_template(feature, test_ids)
        paths_to_mutate = []
        mutation_threshold = None

    today = date.today().isoformat()

    # Build YAML structure
    machine: dict[str, Any] = {
        "schema_version": 1,
        "spec_slug": feature.id,
        "parent_spec": parent_full,
        "verification_tier": tier_int,
        "mutation_threshold": mutation_threshold,
        "mutation_threshold_rationale": (
            f"T{tier_int} floor; baseline pending P0.5 measurement"
            if mutation_threshold is not None
            else f"non-Python ({feature.kind}); uses ADR-009 3-layer verification"
        ),
        "last_mutation_run": None,
        "paths_to_mutate": paths_to_mutate,
        "ac": ac_dicts,
    }
    yaml_text = yaml.safe_dump(machine, sort_keys=False, allow_unicode=True)

    # Build MD with headings + frontmatter
    md_lines = [
        "---",
        "type: spec",
        f"task_slug: {feature.id}",
        "status: drafted",
        f"created: {today}",
        f"tier: {tier_int}",
        f"tags: [harness-maker, spec, {feature.kind}, skeleton]",
        "test_framework: pytest",
        f"parent_spec: {parent_full}",
        f'summary: "Auto-generated skeleton SPEC for {feature.kind} feature {feature.id}."',
        "---",
        "",
        "## 🎯 Intent",
        "",
        f"`{feature.path}` provides the **{feature.id}** {feature.kind} feature. "
        "This skeleton SPEC seeds AC slots for refinement via `/hm:spec` in a follow-up batch.",
        "",
        "## 🌅 Outcomes",
        "",
        f"Consumers of {feature.id} can rely on the AC below holding "
        "under the SPEC's verification regime.",
        "",
        "## 📋 In-Scope Scenarios",
        "",
    ]
    for ac in ac_dicts:
        md_lines.append(f"### {ac['id']}: {ac['title']}")
        md_lines.append("")
        md_lines.append("**Given** the feature is loaded under default configuration")
        md_lines.append(f"**When** the contract surface of {feature.id} is exercised")
        md_lines.append(f"**Then** AC ({ac['type']}) holds per its predicate / table / rubric")
        md_lines.append("")
    md_lines.extend(
        [
            "## 🚫 Non-Goals",
            "",
            "- Cross-feature integration (covered by sibling SPECs)",
            "- UX-only concerns (covered by user-facing documentation)",
            "",
            "## ⚠️ Constraints",
            "",
            "| Constraint | Value | Rationale |",
            "|---|---|---|",
            "| Test framework | pytest | project default |",
        ]
    )
    if mutation_threshold is not None:
        md_lines.append(f"| Mutation gate | ≥ {mutation_threshold}% | T{tier_int} floor (ADR-005)")
    md_lines.extend(
        [
            "",
            "## ✅ Verification Criteria",
            "",
            "| Scenario | Verification mode | Test reference |",
            "|---|---|---|",
        ]
    )
    for ac in ac_dicts:
        if ac["type"] == "mechanical":
            mode = "unit (predicate)"
        elif ac["type"] == "parametric":
            mode = "unit (parametrize)"
        else:
            mode = "LLM judge (rubric)"
        refs = ", ".join(ac.get("test_ids", [])) or "(pending — backfill in P5 batch)"
        md_lines.append(f"| {ac['id']} | {mode} | {refs} |")

    md_lines.extend(
        [
            "",
            "## ❓ Open Questions",
            "",
            "(Auto-generated skeleton — refine via `/hm:loop p5-batch-N` "
            "to fill AC depth + open questions.)",
            "",
            "## 🔍 Refinement Decisions",
            "",
            f"- {today}: skeleton SPEC seeded by `batch_generator` "
            f"(parent={parent_slug}, tier={tier_int}, kind={feature.kind}).",
            "",
            "## 🔗 Machine Spec",
            "",
            f"See [SPEC-{feature.id}.machine.yaml](./SPEC-{feature.id}.machine.yaml).",
            "",
        ]
    )
    md_text = "\n".join(md_lines)
    return GeneratedSpec(slug=feature.id, md_text=md_text, yaml_text=yaml_text)


def render_l1_stub(slug: str, title: str) -> GeneratedSpec:
    """Minimal L1 cluster SPEC pair (parent_spec target for L2 features).

    The AC title must match the md heading exactly (within fuzzy 0.85) so
    use the slug-derived deterministic title, NOT the cluster's free-form
    title which can contain prose like "/hm:health layers + telemetry".
    """
    today = date.today().isoformat()
    ac_title = "cluster invariants hold across members"
    yaml_text = yaml.safe_dump(
        {
            "schema_version": 1,
            "spec_slug": slug,
            "verification_tier": 2,
            "mutation_threshold": None,
            "paths_to_mutate": [],
            "ac": [
                {
                    "id": "AC-001",
                    "title": ac_title,
                    "type": "mechanical",
                    "test_ids": [],
                    "executable_predicate": (
                        f"all(member_passes('{slug}') for member in cluster_members)"
                    ),
                    "pending_test": True,
                }
            ],
        },
        sort_keys=False,
    )
    md_text = "\n".join(
        [
            "---",
            "type: spec",
            f"task_slug: {slug}",
            "status: drafted",
            f"created: {today}",
            "tier: 2",
            "tags: [harness-maker, spec, l1-cluster, skeleton]",
            "test_framework: pytest",
            f'summary: "L1 cluster invariants for {title}."',
            "---",
            "",
            "## 🎯 Intent",
            "",
            f"L1 cluster `{slug}` groups member L2 SPECs sharing invariants.",
            "",
            "## 🌅 Outcomes",
            "",
            "All L2 children pass their per-feature gates AND respect this cluster's invariants.",
            "",
            "## 📋 In-Scope Scenarios",
            "",
            f"### AC-001: {ac_title}",
            "",
            "**Given** every L2 member of cluster `" + slug + "`",
            "**When** their AC are evaluated",
            "**Then** the cluster-level invariant predicate holds",
            "",
            "## 🚫 Non-Goals",
            "",
            "- Member-specific AC (lives in L2 SPECs)",
            "",
            "## ⚠️ Constraints",
            "",
            "| Constraint | Value | Rationale |",
            "|---|---|---|",
            "| Test framework | pytest | default |",
            "",
            "## ✅ Verification Criteria",
            "",
            "| Scenario | Verification mode | Test reference |",
            "|---|---|---|",
            "| AC-001 | aggregated unit | (pending — P5 cluster batch) |",
            "",
            "## ❓ Open Questions",
            "",
            "(L1 stub — refine in cluster's first P5 batch.)",
            "",
            "## 🔍 Refinement Decisions",
            "",
            f"- {today}: L1 stub seeded by `batch_generator`.",
            "",
            "## 🔗 Machine Spec",
            "",
            f"See [SPEC-{slug}.machine.yaml](./SPEC-{slug}.machine.yaml).",
            "",
        ]
    )
    return GeneratedSpec(slug=slug, md_text=md_text, yaml_text=yaml_text)


def write_specs(
    catalog: Catalog,
    inventory: list[dict[str, Any]],
    specs_dir: Path,
    *,
    skip_existing: bool = True,
) -> dict[str, int]:
    """Write skeleton SPECs for every catalog feature + every L1 cluster.

    Order is L2 first, L1 last so a colliding slug (e.g., ``interview``,
    ``worktree`` — both an L1 cluster and an L2 module) resolves to the L1
    stub. L2 features whose slug equals an L1 slug get a ``-module`` suffix
    so they remain represented under a distinct slug. Existing pilot files
    are skipped by default to preserve hand-authored content.
    """
    counts = {"l1_written": 0, "l1_skipped": 0, "l2_written": 0, "l2_skipped": 0}
    specs_dir.mkdir(parents=True, exist_ok=True)

    # Resolve L1 set first so L2 can be renamed to avoid collisions.
    l1_titles: dict[str, str] = {c.slug: c.title for c in catalog.l1_clusters}
    for slug, title in SEED_L1_CLUSTERS:
        l1_titles.setdefault(slug, title)
    l1_slugs: set[str] = set(l1_titles.keys())

    # Pass 1: L2 features.
    for f in catalog.features:
        original_slug = f.id
        write_slug = f"{original_slug}-module" if original_slug in l1_slugs else original_slug
        md_path = specs_dir / f"SPEC-{write_slug}.md"
        yaml_path = specs_dir / f"SPEC-{write_slug}.machine.yaml"
        if skip_existing and md_path.exists() and yaml_path.exists():
            counts["l2_skipped"] += 1
            continue
        # Apply L1 assignment if not set; refresh feature.id to the (possibly
        # renamed) write_slug so render_skeleton_spec produces consistent yaml.
        f.id = write_slug
        if f.parent_spec_slug is None:
            f.parent_spec_slug = _assign_l1(
                # Use original slug for assignment heuristic — the rename is
                # cosmetic, the conceptual feature is unchanged.
                Feature(
                    id=original_slug,
                    kind=f.kind,
                    path=f.path,
                    suggested_tier=f.suggested_tier,
                )
            )
        gen = render_skeleton_spec(f, catalog, inventory)
        atomic_write(md_path, gen.md_text)
        atomic_write(yaml_path, gen.yaml_text)
        counts["l2_written"] += 1

    # Pass 2: L1 stubs — written last so they "win" any name collision.
    for slug, title in l1_titles.items():
        md_path = specs_dir / f"SPEC-{slug}.md"
        yaml_path = specs_dir / f"SPEC-{slug}.machine.yaml"
        if skip_existing and md_path.exists() and yaml_path.exists():
            counts["l1_skipped"] += 1
            continue
        gen = render_l1_stub(slug, title)
        atomic_write(md_path, gen.md_text)
        atomic_write(yaml_path, gen.yaml_text)
        counts["l1_written"] += 1

    return counts


def load_catalog_and_inventory(
    catalog_path: Path, inventory_path: Path
) -> tuple[Catalog, list[dict[str, Any]]]:
    """Load both the P2 catalog yaml and P0 test inventory JSON."""
    catalog_data = yaml.safe_load(catalog_path.read_text(encoding="utf-8")) or {}
    catalog = Catalog.model_validate(catalog_data)
    inventory_raw = json.loads(inventory_path.read_text(encoding="utf-8"))
    inventory: list[dict[str, Any]] = inventory_raw if isinstance(inventory_raw, list) else []
    return catalog, inventory


__all__ = [
    "GeneratedSpec",
    "L1_ASSIGNMENT_RULES",
    "load_catalog_and_inventory",
    "render_l1_stub",
    "render_skeleton_spec",
    "write_specs",
]
