"""Catalog schema (ADR-012) — pydantic models for spec-catalog yaml + SPEC.machine.yaml metadata.

This module is the Phase 1 cross-phase contract: Phase 2 produces a Catalog,
P3+ author SPECs whose machine.yaml fields (parent_spec, verification_tier)
flow from Catalog entries.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

SCHEMA_VERSION = 1


FeatureKind = Literal["python", "template", "agent", "skill", "hook"]
VerificationTier = Literal[1, 2, 3]


class Feature(BaseModel):
    """One L2 feature entry in the catalog."""

    id: str = Field(..., description="kebab-case slug, unique across the catalog")
    kind: FeatureKind
    path: str = Field(..., description="repo-relative source path")
    parent_spec_slug: str | None = Field(
        default=None,
        description="slug of the L1 cluster this feature belongs to (ADR-002)",
    )
    suggested_tier: VerificationTier
    llm_proposed_tier: VerificationTier | None = None
    override_tier: VerificationTier | None = Field(
        default=None,
        description="user-set override; takes precedence over heuristic + LLM",
    )

    @field_validator("id")
    @classmethod
    def _id_kebab(cls, v: str) -> str:
        if not v or not v.replace("-", "").replace("_", "").isalnum():
            raise ValueError(f"feature id must be kebab-case alnum, got {v!r}")
        return v

    @property
    def effective_tier(self) -> VerificationTier:
        """User override > LLM disagreement winner > heuristic."""
        return self.override_tier or self.llm_proposed_tier or self.suggested_tier


class L1Cluster(BaseModel):
    """One L1 capability cluster (~15 total per ADR-002)."""

    slug: str
    title: str
    member_feature_ids: list[str] = Field(default_factory=list)
    invariants_description: str = ""

    @field_validator("slug")
    @classmethod
    def _slug_kebab(cls, v: str) -> str:
        if not v or not v.replace("-", "").isalnum():
            raise ValueError(f"L1 slug must be kebab-case alnum, got {v!r}")
        return v


class WeightRecalibration(BaseModel):
    """One recalibration event in ADR-008's policy."""

    at: str  # ISO date
    override_rate: float
    new_weights: dict[str, float]
    triggered_by: str = "user_override_rate_>_50pct"


class Catalog(BaseModel):
    """Top-level Phase 2 deliverable: ``work-docs/spec-catalog-*.yaml``."""

    schema_version: int = SCHEMA_VERSION
    generated_at: str  # ISO date
    status: Literal["draft", "tier_assignments_locked"] = "draft"
    l1_clusters: list[L1Cluster] = Field(default_factory=list)
    features: list[Feature] = Field(default_factory=list)
    weight_recalibrations: list[WeightRecalibration] = Field(default_factory=list)

    def feature_by_id(self, feature_id: str) -> Feature | None:
        for f in self.features:
            if f.id == feature_id:
                return f
        return None

    def cluster_by_slug(self, slug: str) -> L1Cluster | None:
        for c in self.l1_clusters:
            if c.slug == slug:
                return c
        return None

    def features_in_cluster(self, slug: str) -> list[Feature]:
        cluster = self.cluster_by_slug(slug)
        if cluster is None:
            return []
        ids = set(cluster.member_feature_ids)
        return [f for f in self.features if f.id in ids]


# Re-exports for ergonomics.
__all__ = [
    "SCHEMA_VERSION",
    "Catalog",
    "Feature",
    "FeatureKind",
    "L1Cluster",
    "VerificationTier",
    "WeightRecalibration",
]
