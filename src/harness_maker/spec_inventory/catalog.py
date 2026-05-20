"""Feature catalog enumeration (P2, ADR-001).

Walks ``src/harness_maker/`` and ``src/harness_maker/templates/`` to build
the per-feature list that P3+ authors SPEC files against. ``_*`` private
names and ``_partials/`` template directories are excluded per ADR-001's
computed universe.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from harness_maker.spec_inventory.catalog_schema import (
    Catalog,
    Feature,
    FeatureKind,
    L1Cluster,
)

# Anchor cluster slugs surfaced in PLAN Appendix A — LLM in tier_assign can
# refine, but the seed list keeps the catalog deterministic on first run.
SEED_L1_CLUSTERS: tuple[tuple[str, str], ...] = (
    ("rendering", "Rendering pipeline"),
    ("reconciliation", "Reconciliation + KEEP/REPLACE policy"),
    ("synthesis", "Harness.yaml synthesis"),
    ("interview", "Adaptive interview + 5-term gate"),
    ("autoloop", "Autoloop driver + convergence gates"),
    ("reviewers", "Reviewer agents (code/security/perf/concurrency/etc.)"),
    ("security-permissions", "Security scanner + permission gates"),
    ("observability", "/hm:health layers + telemetry"),
    ("memory", "Project memory (wiki/failures/episodic/semantic)"),
    ("worktree", "Worktree create/finalize/cleanup"),
    ("configuration-manifests", "Triple-plugin manifests + harness.yaml"),
    ("hooks", "Claude/Cursor/Codex hook schemas"),
    ("templates", "Jinja templates (claude-md/agents/skills/codex/cursor)"),
    ("caching", "LLM judge cache + detection cache"),
    ("crawler", "Anti-rot crawler (anthropic_blog/arxiv/github/osv)"),
)


_PYTHON_EXCLUDE_PREFIXES: tuple[str, ...] = ("_",)
_TEMPLATE_EXCLUDE_DIRS: tuple[str, ...] = ("_partials", "_standards", "__pycache__")


def _classify_python(path: Path) -> tuple[str, FeatureKind]:
    """Return ``(feature_id, kind)`` for a Python source file."""
    return path.stem.replace("_", "-"), "python"


def _classify_template(path: Path) -> tuple[str, FeatureKind]:
    """Return ``(feature_id, kind)`` for a Jinja template path."""
    # Derive slug from "templates/<dir>/<name>.<ext>.j2"
    parts = path.relative_to(path.parents[2]).parts  # under src/harness_maker
    stem = path.name.removesuffix(".j2").replace(".", "-").replace("_", "-")
    slug = f"tpl-{'-'.join(parts[2:-1])}-{stem}" if len(parts) > 3 else f"tpl-{stem}"
    # Specialize kind by parent dir.
    parent = path.parent.name
    kind: FeatureKind = "template"
    if parent == "agents":
        kind = "agent"
    elif parent == "skills":
        kind = "skill"
    elif parent == "hooks":
        kind = "hook"
    return slug, kind


def enumerate_features(repo_root: Path) -> list[Feature]:
    """Walk repo_root and return the full L2 feature list (ADR-001 computed universe).

    The default ``suggested_tier`` is 2 — tier_assign will re-score.
    """
    out: list[Feature] = []
    py_root = repo_root / "src" / "harness_maker"
    for py in sorted(py_root.rglob("*.py")):
        if any(py.name.startswith(p) for p in _PYTHON_EXCLUDE_PREFIXES):
            continue
        if py.name == "__init__.py":
            continue
        if "templates" in py.parts:  # template helper py files handled separately
            continue
        slug, kind = _classify_python(py)
        out.append(
            Feature(
                id=slug,
                kind=kind,
                path=str(py.relative_to(repo_root)),
                suggested_tier=2,
            )
        )

    tpl_root = py_root / "templates"
    if tpl_root.exists():
        for tpl in sorted(tpl_root.rglob("*.j2")):
            if any(d in tpl.parts for d in _TEMPLATE_EXCLUDE_DIRS):
                continue
            slug, kind = _classify_template(tpl)
            out.append(
                Feature(
                    id=slug,
                    kind=kind,
                    path=str(tpl.relative_to(repo_root)),
                    suggested_tier=2,
                )
            )
    return out


def build_catalog(
    repo_root: Path,
    *,
    generated_at: str | None = None,
) -> Catalog:
    """Construct an initial Catalog with seed L1 clusters + enumerated L2 features."""
    features = enumerate_features(repo_root)
    clusters = [
        L1Cluster(slug=slug, title=title, member_feature_ids=[])
        for slug, title in SEED_L1_CLUSTERS
    ]
    return Catalog(
        generated_at=generated_at or date.today().isoformat(),
        l1_clusters=clusters,
        features=features,
    )


__all__ = [
    "SEED_L1_CLUSTERS",
    "build_catalog",
    "enumerate_features",
]
