"""Phase 11 — B1+B3+B6 schema + Side defaults + schema_version migration.

0.16.0 (PLAN-deep-interview-question-criteria) replaced the 3-layer gate's
deep_gate.max_rounds/streak_target with a 5-term inequality schema
(eig_epsilon, confidence_tau, open_ended_cap_by_locale, common_ground.*).
ADR-007 made deep_gate uniform across presets and schema_versions; only
main_loop + max_review_rounds still diverge by preset/version.
"""

from __future__ import annotations

from pathlib import Path

from harness_maker.interview import _preset_extras, interview
from harness_maker.models import HarnessConfig, InterviewAnswers, Preset, ProjectProfile
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize


def _render_preset(tmp_path: Path, preset: Preset) -> Path:
    profile = (
        ProjectProfile(stack=["python"], scale="small", lifecycle="dormant")
        if preset == Preset.SIDE
        else ProjectProfile(stack=["python"], scale="medium", lifecycle="active")
    )
    a = interview(profile, autoloop_mode=True)
    bp = synthesize(profile, a, preset=preset)
    render(bp, tmp_path, freeze_time=DEFAULT_FREEZE_TIME)
    return tmp_path


def _expected_deep_gate() -> dict[str, object]:
    """The 5-term inequality gate schema introduced in 0.16.0 (ADR-007)."""
    return {
        "eig_epsilon": 0.5,
        "confidence_tau": 0.7,
        "open_ended_cap_by_locale": {"en": 2, "ko": 1, "ja": 1, "default": 1},
        "common_ground": {
            "llm_inference_threshold": 0.95,
            "llm_inference_enabled": True,
        },
    }


def test_side_defaults_new_fields_schema_v2(tmp_path: Path) -> None:
    """New Side harness (schema v2) renders the 5-term inequality gate schema
    and the preset-specific main_loop cap (5)."""
    out = _render_preset(tmp_path, Preset.SIDE)
    import yaml

    docs = list(yaml.safe_load_all((out / "harness.yaml").read_text(encoding="utf-8")))
    hy = [d for d in docs if d and isinstance(d, dict) and "preset" in d][0]
    assert hy["schema_version"] == 2
    dg = hy["interview"]["deep_gate"]
    assert dg["eig_epsilon"] == 0.5
    assert dg["confidence_tau"] == 0.7
    assert dg["common_ground"]["llm_inference_enabled"] is True
    assert dg["common_ground"]["llm_inference_threshold"] == 0.95
    assert dg["open_ended_cap_by_locale"] == {"en": 2, "ko": 1, "ja": 1, "default": 1}
    assert hy["interview"]["main_loop"]["max_rounds"] == 5


def test_side_defaults_old_fields_schema_v1_or_missing() -> None:
    """Side v1: deep_gate is uniform 0.16.0 schema (ADR-007); main_loop keeps
    the v1 default (max_rounds: None) and max_review_rounds stays at 3."""
    extras = _preset_extras(Preset.SIDE, schema_version=1)
    assert extras["interview"]["deep_gate"] == _expected_deep_gate()
    assert extras["interview"]["main_loop"]["max_rounds"] is None
    assert extras["max_review_rounds"] == 3


def test_prod_defaults_unchanged_across_schema_versions() -> None:
    """Production deep_gate identical regardless of schema_version (ADR-007 uniform)."""
    v1 = _preset_extras(Preset.PRODUCTION, schema_version=1)
    v2 = _preset_extras(Preset.PRODUCTION, schema_version=2)
    assert v1["interview"] == v2["interview"]
    assert v1["interview"]["deep_gate"] == _expected_deep_gate()


def test_interview_py_injects_side_v2() -> None:
    """interview() for Side v2 injects schema_version=2, new uniform deep_gate,
    main_loop.max_rounds=5, and max_review_rounds=2."""
    extras = _preset_extras(Preset.SIDE, schema_version=2)
    assert extras["schema_version"] == 2
    assert extras["interview"]["deep_gate"] == _expected_deep_gate()
    assert extras["interview"]["main_loop"]["max_rounds"] == 5
    assert extras["max_review_rounds"] == 2


def test_interview_py_preserves_side_v1_old_defaults() -> None:
    """Side v1 keeps v1-specific main_loop + review_rounds; deep_gate is uniform 0.16.0."""
    extras = _preset_extras(Preset.SIDE, schema_version=1)
    assert extras["schema_version"] == 1
    assert extras["interview"]["deep_gate"] == _expected_deep_gate()
    assert extras["interview"]["main_loop"]["max_rounds"] is None
    assert extras["max_review_rounds"] == 3


def test_prod_and_side_share_deep_gate_post_0_16_0() -> None:
    """ADR-007: deep_gate is uniform across presets in 0.16.0+."""
    side = _preset_extras(Preset.SIDE, schema_version=2)
    prod = _preset_extras(Preset.PRODUCTION, schema_version=2)
    assert side["interview"]["deep_gate"] == prod["interview"]["deep_gate"]


def test_schema_version_field_present_in_models() -> None:
    """Both HarnessConfig and InterviewAnswers should have schema_version.

    HarnessConfig bumped 1 → 2 per ADR-011 (PLAN-model-routing-multi-ide) for
    the agent_models + default_model rename; InterviewAnswers was already at 2.
    """
    hc = HarnessConfig()
    assert hasattr(hc, "schema_version")
    assert hc.schema_version == 2

    ia = InterviewAnswers()
    assert hasattr(ia, "schema_version")
    assert ia.schema_version == 2


def test_stage_template_reads_config_not_hardcoded(tmp_path: Path) -> None:
    """Stage templates render config values from harness.yaml.interview.deep_gate.

    Post-0.16.0 (PLAN F5): the 3-layer gate's "streak: {N}/{streak_target}"
    text is replaced by the 5-term inequality checklist (ADR-005). Templates
    must render the ε/τ/cap values FROM config, not hardcode them.
    """
    out = _render_preset(tmp_path, Preset.SIDE)
    research = (out / "stages" / "research.md").read_text(encoding="utf-8")
    # ADR-005 5-term checklist line — assert each term individually for clearer failure
    assert "EIG" in research
    assert "CLARITI" in research
    assert "common-ground" in research
    # Config-rendered ε / τ / locale cap (Side preset renders with default locale "en", cap=2)
    assert "ε = 0.5" in research
    assert "τ = 0.7" in research
    assert "5-Term Inequality Gate" in research

    out_prod = _render_preset(tmp_path / "prod", Preset.PRODUCTION)
    research_prod = (out_prod / "stages" / "research.md").read_text(encoding="utf-8")
    # Both presets render the same 5-term gate (ADR-007 uniformity)
    assert "ε = 0.5" in research_prod
    assert "τ = 0.7" in research_prod


def test_stage_template_no_3layer_remnants(tmp_path: Path) -> None:
    """0.16.0 cleanup guard: rendered stage outputs must not contain the
    old 3-layer gate text (Ambiguity Score / Layer 1-3 / N consecutive rounds).
    Regression-protection for ADR-001's 'full replacement' commitment."""
    out = _render_preset(tmp_path, Preset.SIDE)
    forbidden = (
        "Ambiguity Score",
        "Layer 1 — GCIC Gap Check",
        "Layer 2 — Implicit Probing",
        "consecutive rounds",
        "deep_gate.max_rounds",
        "deep_gate.streak_target",
    )
    targets = {
        "stages/research.md": out / "stages" / "research.md",
        "stages/spec.md": out / "stages" / "spec.md",
        "stages/plan.md": out / "stages" / "plan.md",
        "commands/hm/loop.md": out / "commands" / "hm" / "loop.md",
    }
    for label, path in targets.items():
        body = path.read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in body, (
                f"forbidden 3-layer remnant {token!r} found in rendered {label} "
                f"— PLAN F5 ADR-001 violation"
            )


def test_plan_template_reads_main_loop_config(tmp_path: Path) -> None:
    """Plan template still uses interview.main_loop.max_rounds (kept in 0.16.0)."""
    out = _render_preset(tmp_path, Preset.SIDE)
    plan = (out / "stages" / "plan.md").read_text(encoding="utf-8")
    assert "up to 5 rounds" in plan

    out_prod = _render_preset(tmp_path / "prod", Preset.PRODUCTION)
    plan_prod = (out_prod / "stages" / "plan.md").read_text(encoding="utf-8")
    assert "unlimited rounds" in plan_prod
