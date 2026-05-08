"""Tests for trajectory drift monitor (Phase 4)."""

from __future__ import annotations

from pathlib import Path

from harness_maker.drift_monitor import (
    DriftMonitor,
    SimpleHashEmbedding,
    cosine_similarity,
    resolve_baseline,
)

# ── cosine_similarity ────────────────────────────────────────────────────


def test_cosine_identical_vectors() -> None:
    v = [1.0, 2.0, 3.0]
    assert abs(cosine_similarity(v, v) - 1.0) < 1e-6


def test_cosine_orthogonal_vectors() -> None:
    a = [1.0, 0.0]
    b = [0.0, 1.0]
    assert abs(cosine_similarity(a, b)) < 1e-6


def test_cosine_empty_vectors() -> None:
    assert cosine_similarity([], []) == 0.0


def test_cosine_different_lengths() -> None:
    assert cosine_similarity([1.0], [1.0, 2.0]) == 0.0


# ── resolve_baseline ────────────────────────────────────────────────────


def test_resolve_baseline_spec_first(tmp_path: Path) -> None:
    spec = tmp_path / "spec.md"
    plan = tmp_path / "plan.md"
    spec.write_text("spec content", encoding="utf-8")
    plan.write_text("plan content", encoding="utf-8")
    text, source = resolve_baseline(spec_path=spec, plan_path=plan, prompt="prompt")
    assert source == "spec"
    assert "spec content" in text


def test_resolve_baseline_plan_fallback(tmp_path: Path) -> None:
    plan = tmp_path / "plan.md"
    plan.write_text("plan content", encoding="utf-8")
    text, source = resolve_baseline(plan_path=plan, prompt="prompt")
    assert source == "plan"


def test_resolve_baseline_prompt_fallback() -> None:
    text, source = resolve_baseline(prompt="user prompt here")
    assert source == "prompt"
    assert text == "user prompt here"


def test_resolve_baseline_none() -> None:
    text, source = resolve_baseline()
    assert source == "none"
    assert text == ""


def test_resolve_baseline_skips_empty_spec(tmp_path: Path) -> None:
    spec = tmp_path / "spec.md"
    spec.write_text("   \n", encoding="utf-8")
    text, source = resolve_baseline(spec_path=spec, prompt="fallback")
    assert source == "prompt"


# ── SimpleHashEmbedding ─────────────────────────────────────────────────


def test_hash_embedding_deterministic() -> None:
    emb = SimpleHashEmbedding()
    a = emb.embed("hello world")
    b = emb.embed("hello world")
    assert a == b


def test_hash_embedding_different_texts_differ() -> None:
    emb = SimpleHashEmbedding()
    a = emb.embed("hello")
    b = emb.embed("completely different text")
    assert a != b


def test_hash_embedding_dimension() -> None:
    emb = SimpleHashEmbedding(dim=32)
    v = emb.embed("test")
    assert len(v) == 32


# ── DriftMonitor.score ──────────────────────────────────────────────────


def test_score_identical_text_low_drift() -> None:
    monitor = DriftMonitor()
    result = monitor.score("implement auth module", "implement auth module")
    assert result["cos_sim"] == 1.0
    assert result["drift_score"] == 0.0
    assert result["used_llm"] is False


def test_score_empty_text_high_drift() -> None:
    monitor = DriftMonitor()
    result = monitor.score("", "something")
    assert result["drift_score"] == 1.0
    assert "warning" in result


def test_score_uses_llm_when_cos_below_threshold() -> None:
    class MockJudge:
        def judge_drift(self, baseline: str, current: str) -> float:
            return 0.8

    monitor = DriftMonitor(judge=MockJudge(), threshold=0.99)
    result = monitor.score("text A", "text B")
    assert result["used_llm"] is True
    assert result["drift_score"] == 0.8


def test_score_skips_llm_when_cos_above_threshold() -> None:
    monitor = DriftMonitor(threshold=0.0)
    result = monitor.score("text A", "text A")
    assert result["used_llm"] is False


def test_score_no_llm_fallback_to_cosine() -> None:
    monitor = DriftMonitor(judge=None, threshold=0.99)
    result = monitor.score("text A", "text B")
    assert result["used_llm"] is False
    assert result["drift_score"] > 0


# ── DriftMonitor.check ──────────────────────────────────────────────────


def test_check_with_spec_baseline(tmp_path: Path) -> None:
    spec = tmp_path / "spec.md"
    spec.write_text("Build a REST API for user management", encoding="utf-8")
    monitor = DriftMonitor()
    result = monitor.check(
        spec_path=spec,
        current_output="Build a REST API for user management",
    )
    assert result["baseline_source"] == "spec"
    assert result["drift_score"] == 0.0


def test_check_with_multilayer_fallback(tmp_path: Path) -> None:
    plan = tmp_path / "plan.md"
    plan.write_text("Plan for auth module", encoding="utf-8")
    monitor = DriftMonitor()
    result = monitor.check(
        plan_path=plan,
        current_output="Plan for auth module",
    )
    assert result["baseline_source"] == "plan"


def test_check_no_baseline_skips(tmp_path: Path) -> None:
    monitor = DriftMonitor()
    result = monitor.check(current_output="anything")
    assert result["baseline_source"] == "none"
    assert "skipped" in result.get("warning", "")


def test_check_warns_on_high_drift(tmp_path: Path) -> None:
    spec = tmp_path / "spec.md"
    spec.write_text("A" * 1000, encoding="utf-8")

    class MockJudge:
        def judge_drift(self, baseline: str, current: str) -> float:
            return 0.9

    monitor = DriftMonitor(judge=MockJudge(), threshold=0.99)
    result = monitor.check(
        spec_path=spec,
        current_output="B" * 1000,
        warn_threshold=0.5,
    )
    assert "warning" in result
    assert result["drift_score"] > 0.5
