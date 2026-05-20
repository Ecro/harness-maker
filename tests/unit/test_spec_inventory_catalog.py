"""Tests for spec_inventory.catalog + tier_assign (P2, ADR-001/008)."""

from __future__ import annotations

from pathlib import Path

from harness_maker.spec_inventory.catalog import (
    SEED_L1_CLUSTERS,
    build_catalog,
    enumerate_features,
)
from harness_maker.spec_inventory.catalog_schema import Catalog, Feature
from harness_maker.spec_inventory.tier_assign import (
    DEFAULT_WEIGHTS,
    CriticalitySignal,
    apply_llm_proposals,
    assign_tiers,
    detect_disagreements,
    recalibrate_weights,
)


def test_seed_l1_clusters_15_entries() -> None:
    # ADR-002: ~15 clusters per PLAN
    assert 10 <= len(SEED_L1_CLUSTERS) <= 20


def test_seed_l1_slugs_are_kebab() -> None:
    for slug, _title in SEED_L1_CLUSTERS:
        assert slug.replace("-", "").isalnum()


def _make_fake_tree(tmp_path: Path) -> Path:
    root = tmp_path
    py = root / "src" / "harness_maker"
    py.mkdir(parents=True)
    (py / "render.py").write_text("# x\n")
    (py / "cache.py").write_text("# x\n")
    (py / "_private.py").write_text("# x\n")  # excluded
    (py / "__init__.py").write_text("")  # excluded
    tpl = py / "templates"
    (tpl / "agents").mkdir(parents=True)
    (tpl / "agents" / "code-reviewer.md.j2").write_text("# a\n")
    (tpl / "_partials").mkdir()
    (tpl / "_partials" / "snippet.md.j2").write_text("# x\n")  # excluded
    return root


def test_enumerate_features_includes_python(tmp_path: Path) -> None:
    root = _make_fake_tree(tmp_path)
    features = enumerate_features(root)
    ids = {f.id for f in features}
    assert "render" in ids
    assert "cache" in ids


def test_enumerate_features_excludes_private(tmp_path: Path) -> None:
    root = _make_fake_tree(tmp_path)
    features = enumerate_features(root)
    ids = {f.id for f in features}
    assert "private" not in ids


def test_enumerate_features_includes_templates(tmp_path: Path) -> None:
    root = _make_fake_tree(tmp_path)
    features = enumerate_features(root)
    kinds = {f.kind for f in features}
    assert "agent" in kinds


def test_enumerate_features_excludes_partials(tmp_path: Path) -> None:
    root = _make_fake_tree(tmp_path)
    features = enumerate_features(root)
    ids = {f.id for f in features}
    assert all("snippet" not in i for i in ids)


def test_build_catalog_returns_seeded_clusters(tmp_path: Path) -> None:
    root = _make_fake_tree(tmp_path)
    cat = build_catalog(root, generated_at="2026-05-20")
    assert isinstance(cat, Catalog)
    assert {c.slug for c in cat.l1_clusters} >= {s for s, _ in SEED_L1_CLUSTERS}
    assert len(cat.features) >= 3


# ---------------------------------------------------------------------------
# tier_assign
# ---------------------------------------------------------------------------


def test_criticality_signal_score_uses_weights() -> None:
    sig = CriticalitySignal(user_facing=1.0, security=0.0, reproducibility=0.0, ai_dependency=0.0)
    assert sig.score(DEFAULT_WEIGHTS) == 0.4


def test_assign_tiers_user_facing_path_yields_t2_or_better() -> None:
    cat = Catalog(
        generated_at="2026-05-20",
        features=[
            Feature(
                id="render",
                kind="python",
                path="src/harness_maker/render.py",
                suggested_tier=3,
            )
        ],
    )
    assign_tiers(cat)
    # render → user_facing + reproducibility hits → score 0.6 → T2
    assert cat.features[0].suggested_tier in (1, 2)


def test_assign_tiers_helper_module_yields_t3() -> None:
    cat = Catalog(
        generated_at="2026-05-20",
        features=[
            Feature(
                id="unrelated",
                kind="python",
                path="src/harness_maker/unrelated.py",
                suggested_tier=1,
            )
        ],
    )
    assign_tiers(cat)
    assert cat.features[0].suggested_tier == 3


def test_assign_tiers_security_path() -> None:
    cat = Catalog(
        generated_at="2026-05-20",
        features=[
            Feature(
                id="security-scanner",
                kind="python",
                path="src/harness_maker/security_scanner.py",
                suggested_tier=3,
            )
        ],
    )
    assign_tiers(cat)
    assert cat.features[0].suggested_tier in (1, 2)


def test_detect_disagreements_empty_when_aligned() -> None:
    cat = Catalog(
        generated_at="2026-05-20",
        features=[Feature(id="x", kind="python", path="x.py", suggested_tier=2)],
    )
    diff = detect_disagreements(cat, {"x": 2})
    assert diff == []


def test_detect_disagreements_is_pure_no_side_effect() -> None:
    """detect_disagreements must NOT mutate Feature.llm_proposed_tier (REVIEW C-P1-D)."""
    cat = Catalog(
        generated_at="2026-05-20",
        features=[Feature(id="x", kind="python", path="x.py", suggested_tier=2)],
    )
    diff = detect_disagreements(cat, {"x": 1})
    assert len(diff) == 1
    # Side effect removed: caller must explicitly invoke apply_llm_proposals.
    assert diff[0].llm_proposed_tier is None


def test_apply_llm_proposals_writes_back() -> None:
    """apply_llm_proposals is the explicit-mutation counterpart (REVIEW C-P1-D)."""
    cat = Catalog(
        generated_at="2026-05-20",
        features=[Feature(id="x", kind="python", path="x.py", suggested_tier=2)],
    )
    apply_llm_proposals(cat, {"x": 1})
    assert cat.features[0].llm_proposed_tier == 1


def test_recalibrate_weights_under_threshold_returns_none() -> None:
    cat = Catalog(generated_at="2026-05-20")
    assert recalibrate_weights(cat, override_rate=0.3) is None


def test_recalibrate_weights_above_threshold_returns_new() -> None:
    """Returns a dict whose weights changed in the documented direction.

    REVIEW T-P1-C: previously only asserted `sum > 0`, which passes even
    if recalibrate became a no-op. Now we verify the specific direction
    (user_facing up, ai_dependency down) per tier_assign.py's documented
    formula.
    """
    cat = Catalog(generated_at="2026-05-20")
    new = recalibrate_weights(cat, override_rate=0.7)
    assert new is not None
    assert new["user_facing"] > DEFAULT_WEIGHTS["user_facing"]
    assert new["ai_dependency"] < DEFAULT_WEIGHTS["ai_dependency"]
    # bounds enforced by the formula
    assert new["user_facing"] <= 0.55
    assert new["ai_dependency"] >= 0.05
