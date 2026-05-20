"""Tests for spec_inventory.catalog_schema (P1, ADR-012)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from harness_maker.spec_inventory.catalog_schema import (
    SCHEMA_VERSION,
    Catalog,
    Feature,
    L1Cluster,
    WeightRecalibration,
)


def test_schema_version_is_1() -> None:
    assert SCHEMA_VERSION == 1


def test_feature_minimal_construct() -> None:
    f = Feature(id="render", kind="python", path="src/harness_maker/render.py", suggested_tier=1)
    assert f.effective_tier == 1
    assert f.parent_spec_slug is None


def test_feature_override_takes_precedence() -> None:
    f = Feature(
        id="render",
        kind="python",
        path="src/harness_maker/render.py",
        suggested_tier=2,
        llm_proposed_tier=3,
        override_tier=1,
    )
    assert f.effective_tier == 1


def test_feature_llm_proposed_falls_through_when_no_override() -> None:
    f = Feature(
        id="render",
        kind="python",
        path="src/harness_maker/render.py",
        suggested_tier=2,
        llm_proposed_tier=3,
    )
    assert f.effective_tier == 3


def test_feature_id_must_be_kebab_alnum() -> None:
    with pytest.raises(ValidationError):
        Feature(
            id="bad slug with spaces",
            kind="python",
            path="x.py",
            suggested_tier=1,
        )


def test_l1_cluster_basic() -> None:
    c = L1Cluster(slug="rendering", title="Rendering pipeline")
    assert c.member_feature_ids == []


def test_l1_cluster_slug_validator() -> None:
    with pytest.raises(ValidationError):
        L1Cluster(slug="not!ok", title="x")


def test_catalog_round_trip() -> None:
    c = Catalog(
        generated_at="2026-05-20",
        l1_clusters=[L1Cluster(slug="rendering", title="Render", member_feature_ids=["render"])],
        features=[
            Feature(id="render", kind="python", path="src/harness_maker/render.py", suggested_tier=1)
        ],
    )
    blob = c.model_dump(mode="json")
    restored = Catalog.model_validate(blob)
    assert restored.features[0].id == "render"
    assert restored.l1_clusters[0].slug == "rendering"


def test_catalog_lookup_helpers() -> None:
    f = Feature(id="render", kind="python", path="x.py", suggested_tier=1)
    c = Catalog(
        generated_at="2026-05-20",
        features=[f],
        l1_clusters=[L1Cluster(slug="rendering", title="r", member_feature_ids=["render"])],
    )
    assert c.feature_by_id("render") is f
    assert c.feature_by_id("missing") is None
    assert c.cluster_by_slug("rendering") is not None
    assert c.features_in_cluster("rendering") == [f]
    assert c.features_in_cluster("missing") == []


def test_weight_recalibration_records() -> None:
    r = WeightRecalibration(
        at="2026-05-20",
        override_rate=0.6,
        new_weights={"w1": 0.5, "w2": 0.2, "w3": 0.2, "w4": 0.1},
    )
    assert r.triggered_by == "user_override_rate_>_50pct"
