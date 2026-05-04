"""Layer-1 readiness — 7-dim scoring with evidence-anchored signals."""

from __future__ import annotations

import json
from pathlib import Path

from harness_maker.models import Preset
from harness_maker.readiness import (
    DimensionScore,
    ReadinessResult,
    Signal,
    compute_readiness,
)

_DIM_NAMES = {
    "context_quality",
    "guardrails",
    "verification",
    "workflow_clarity",
    "memory_continuity",
    "observability_setup",
    "governance",
}


# ── shape ───────────────────────────────────────────────────────────────────


def test_returns_pydantic_model(tmp_path: Path) -> None:
    res = compute_readiness(tmp_path, Preset.SIDE)
    assert isinstance(res, ReadinessResult)
    assert isinstance(res.composite, int)
    assert set(res.dimensions.keys()) == _DIM_NAMES


def test_each_failing_dim_provides_at_least_one_action(tmp_path: Path) -> None:
    """An empty project must surface at least one actionable remediation per
    failing dimension. Individual redundant signals (e.g. line-limit when the
    file itself is missing) may legitimately omit an action — the dimension
    just needs one entry point for the user to act on."""
    res = compute_readiness(tmp_path, Preset.SIDE)
    for dim_name, dim in res.dimensions.items():
        assert isinstance(dim, DimensionScore)
        assert dim.name == dim_name
        for sig in dim.signals:
            assert isinstance(sig, Signal)
        # governance on Side is intentionally a no-op.
        if dim.score < 100 and dim_name != "governance":
            actions = [s.action for s in dim.signals if not s.passed and s.action]
            assert actions, f"{dim_name} has failures but no actions"


def test_weights_sum_to_one(tmp_path: Path) -> None:
    res_side = compute_readiness(tmp_path, Preset.SIDE)
    res_prod = compute_readiness(tmp_path, Preset.PRODUCTION)
    assert abs(sum(res_side.weights.values()) - 1.0) < 1e-9
    assert abs(sum(res_prod.weights.values()) - 1.0) < 1e-9


# ── empty project ───────────────────────────────────────────────────────────


def test_empty_project_low_score(tmp_path: Path) -> None:
    res = compute_readiness(tmp_path, Preset.SIDE)
    assert res.composite < 30
    # Most signals should fail.
    failed = sum(1 for d in res.dimensions.values() for s in d.signals if not s.passed)
    passed = sum(1 for d in res.dimensions.values() for s in d.signals if s.passed)
    assert failed > passed


# ── context_quality ─────────────────────────────────────────────────────────


def test_context_quality_with_claude_md(tmp_path: Path) -> None:
    (tmp_path / "CLAUDE.md").write_text("# project\n\nshort and sweet\n")
    (tmp_path / "README.md").write_text("# readme\n")
    res = compute_readiness(tmp_path, Preset.SIDE)
    cq = res.dimensions["context_quality"]
    sigs = {s.id: s for s in cq.signals}
    assert sigs["claude_md_present"].passed
    assert sigs["claude_md_within_limit"].passed
    assert sigs["readme_present"].passed
    assert cq.score >= 55  # 30+15+10 of 100


def test_context_quality_oversized_claude_md_fails_limit(tmp_path: Path) -> None:
    long_body = "\n".join(f"line {i}" for i in range(300))
    (tmp_path / "CLAUDE.md").write_text(long_body + "\n")
    res = compute_readiness(tmp_path, Preset.SIDE)
    sigs = {s.id: s for s in res.dimensions["context_quality"].signals}
    assert sigs["claude_md_present"].passed
    assert not sigs["claude_md_within_limit"].passed
    assert "Trim CLAUDE.md" in (sigs["claude_md_within_limit"].action or "")


def test_context_quality_agents_within_limit(tmp_path: Path) -> None:
    agent_dir = tmp_path / ".claude" / "agents"
    agent_dir.mkdir(parents=True)
    (agent_dir / "good.md").write_text(
        "---\nname: good\ndescription: good agent\n---\n# body\nshort\n"
    )
    res = compute_readiness(tmp_path, Preset.SIDE)
    sigs = {s.id: s for s in res.dimensions["context_quality"].signals}
    assert sigs["agents_within_limit"].passed
    assert sigs["agent_frontmatter_valid"].passed


def test_context_quality_agent_missing_frontmatter(tmp_path: Path) -> None:
    agent_dir = tmp_path / ".claude" / "agents"
    agent_dir.mkdir(parents=True)
    (agent_dir / "bare.md").write_text("# body without frontmatter\n")
    res = compute_readiness(tmp_path, Preset.SIDE)
    sigs = {s.id: s for s in res.dimensions["context_quality"].signals}
    assert not sigs["agent_frontmatter_valid"].passed


# ── guardrails ──────────────────────────────────────────────────────────────


def test_guardrails_with_full_setup(tmp_path: Path) -> None:
    claude = tmp_path / ".claude"
    (claude / "hooks").mkdir(parents=True)
    (claude / "hooks" / "hooks.json").write_text(
        json.dumps(
            {
                "PreToolUse": [
                    {"matcher": "Bash", "hooks": [{"type": "command", "command": "echo"}]}
                ],
                "PostToolUse": [
                    {"matcher": "*", "hooks": [{"type": "command", "command": "telemetry"}]}
                ],
            }
        )
    )
    (claude / "settings.json").write_text(
        json.dumps(
            {
                "permissions": {
                    "deny": [
                        "Bash(rm -rf:*)",
                        "Bash(curl * | sh)",
                        "Write(/etc/**)",
                        "Write(~/.ssh/**)",
                    ]
                }
            }
        )
    )
    res = compute_readiness(tmp_path, Preset.SIDE)
    g = res.dimensions["guardrails"]
    sigs = {s.id: s for s in g.signals}
    assert sigs["hooks_json_present"].passed
    assert sigs["hooks_defined"].passed
    assert sigs["permissions_deny_present"].passed
    assert sigs["deny_covers_dangerous"].passed
    assert g.score >= 85


def test_guardrails_high_severity_finding_fails_signal(tmp_path: Path) -> None:
    sec_dir = tmp_path / ".claude" / "observability" / "security"
    sec_dir.mkdir(parents=True)
    (sec_dir / "findings-2026-05-01.jsonl").write_text(
        json.dumps({"severity": "high", "category": "secret"}) + "\n"
    )
    res = compute_readiness(tmp_path, Preset.SIDE)
    sigs = {s.id: s for s in res.dimensions["guardrails"].signals}
    assert not sigs["no_high_security_findings"].passed
    assert "1 high-severity" in sigs["no_high_security_findings"].evidence


# ── verification ────────────────────────────────────────────────────────────


def test_verification_python_with_tests_and_ci(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n")
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_x.py").write_text("def test_one():\n    assert True\n")
    wf = tmp_path / ".github" / "workflows"
    wf.mkdir(parents=True)
    (wf / "ci.yml").write_text("jobs:\n  test:\n    steps:\n      - run: pytest\n")
    res = compute_readiness(tmp_path, Preset.SIDE)
    v = res.dimensions["verification"]
    sigs = {s.id: s for s in v.signals}
    assert sigs["stack_detected"].passed
    assert sigs["tests_present"].passed
    assert sigs["ci_workflow_present"].passed
    assert sigs["ci_invokes_tests"].passed
    assert v.score >= 85


def test_verification_no_stack_no_tests(tmp_path: Path) -> None:
    res = compute_readiness(tmp_path, Preset.SIDE)
    sigs = {s.id: s for s in res.dimensions["verification"].signals}
    assert not sigs["stack_detected"].passed
    assert not sigs["tests_present"].passed


# ── workflow_clarity ────────────────────────────────────────────────────────


def test_workflow_clarity_full_setup(tmp_path: Path) -> None:
    cmd_dir = tmp_path / ".claude" / "commands" / "hm"
    cmd_dir.mkdir(parents=True)
    (cmd_dir / "research.md").write_text("---\ncontent_hash: abc\n---\n# /hm:research\n")
    (cmd_dir / "exec-rev.md").write_text("---\ncontent_hash: def\n---\n# /hm:exec-rev\n")
    harness = tmp_path / ".claude" / "harness.yaml"
    harness.write_text("workflows:\n  dev: [research, plan]\ndefault_workflow: dev\n")
    res = compute_readiness(tmp_path, Preset.SIDE)
    w = res.dimensions["workflow_clarity"]
    sigs = {s.id: s for s in w.signals}
    assert sigs["commands_present"].passed
    assert sigs["fused_workflow_present"].passed
    assert sigs["commands_have_provenance"].passed
    assert sigs["harness_workflows_defined"].passed


def test_workflow_clarity_no_fused_workflow(tmp_path: Path) -> None:
    cmd_dir = tmp_path / ".claude" / "commands" / "hm"
    cmd_dir.mkdir(parents=True)
    (cmd_dir / "plan.md").write_text("# /hm:plan\n")
    res = compute_readiness(tmp_path, Preset.SIDE)
    sigs = {s.id: s for s in res.dimensions["workflow_clarity"].signals}
    assert sigs["commands_present"].passed
    assert not sigs["fused_workflow_present"].passed


# ── memory_continuity ───────────────────────────────────────────────────────


def test_memory_continuity_with_real_lessons(tmp_path: Path) -> None:
    mem = tmp_path / ".claude" / "memory"
    mem.mkdir(parents=True)
    failures_body = "\n".join(f"- 2026-{i:02d}: lesson {i}" for i in range(1, 15))
    (mem / "failures.md").write_text("# failures\n\n" + failures_body + "\n")
    (mem / "wiki.md").write_text("# wiki\n")
    (tmp_path / ".claude" / "harness.yaml").write_text("memory:\n  dir: memory/\n")
    res = compute_readiness(tmp_path, Preset.SIDE)
    m = res.dimensions["memory_continuity"]
    sigs = {s.id: s for s in m.signals}
    assert sigs["failures_md_present"].passed
    assert sigs["failures_md_has_content"].passed
    assert sigs["wiki_md_present"].passed
    assert sigs["harness_memory_configured"].passed


def test_memory_continuity_stub_failures_fails_content(tmp_path: Path) -> None:
    mem = tmp_path / ".claude" / "memory"
    mem.mkdir(parents=True)
    (mem / "failures.md").write_text("# failures\n\n(none yet)\n")
    res = compute_readiness(tmp_path, Preset.SIDE)
    sigs = {s.id: s for s in res.dimensions["memory_continuity"].signals}
    assert sigs["failures_md_present"].passed
    assert not sigs["failures_md_has_content"].passed


# ── observability_setup ─────────────────────────────────────────────────────


def test_observability_setup_full(tmp_path: Path) -> None:
    obs = tmp_path / ".claude" / "observability"
    obs.mkdir(parents=True)
    (obs / "metrics.jsonl").write_text("\n".join("{}" for _ in range(10)) + "\n")
    (obs / "dashboard.md").write_text("# dashboard\n")
    res = compute_readiness(tmp_path, Preset.SIDE)
    o = res.dimensions["observability_setup"]
    sigs = {s.id: s for s in o.signals}
    assert sigs["observability_dir_present"].passed
    assert sigs["metrics_jsonl_present"].passed
    assert sigs["dashboard_md_present"].passed
    assert sigs["metrics_has_samples"].passed
    assert o.score == 100


def test_observability_setup_metrics_too_few_samples(tmp_path: Path) -> None:
    obs = tmp_path / ".claude" / "observability"
    obs.mkdir(parents=True)
    (obs / "metrics.jsonl").write_text("{}\n{}\n")  # only 2 entries
    res = compute_readiness(tmp_path, Preset.SIDE)
    sigs = {s.id: s for s in res.dimensions["observability_setup"].signals}
    assert sigs["metrics_jsonl_present"].passed
    assert not sigs["metrics_has_samples"].passed


# ── governance ──────────────────────────────────────────────────────────────


def test_governance_side_skipped(tmp_path: Path) -> None:
    res = compute_readiness(tmp_path, Preset.SIDE)
    g = res.dimensions["governance"]
    assert g.score == 100  # weight 0; value irrelevant but full-marks for clarity
    sigs = {s.id: s for s in g.signals}
    assert "side_governance_skipped" in sigs


def test_governance_production_with_adr_and_contributing(tmp_path: Path) -> None:
    adr = tmp_path / "docs" / "adr"
    adr.mkdir(parents=True)
    (adr / "001.md").write_text("# ADR 001\n")
    (tmp_path / "CONTRIBUTING.md").write_text("# Contributing\n")
    res = compute_readiness(tmp_path, Preset.PRODUCTION)
    g = res.dimensions["governance"]
    sigs = {s.id: s for s in g.signals}
    assert sigs["adr_present"].passed
    assert sigs["contributing_present"].passed
    assert g.score == 100


def test_governance_weights_differ_side_vs_prod(tmp_path: Path) -> None:
    res_side = compute_readiness(tmp_path, Preset.SIDE)
    res_prod = compute_readiness(tmp_path, Preset.PRODUCTION)
    assert res_side.weights["governance"] == 0.0
    assert res_prod.weights["governance"] > 0.0


# ── ceremony penalty ────────────────────────────────────────────────────────


def test_ceremony_penalty_applied(tmp_path: Path) -> None:
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    for i in range(20):
        (claude_dir / f"user-doc-{i}.md").write_text(f"# Doc {i}\nbody\n")
    res = compute_readiness(tmp_path, Preset.SIDE)
    assert res.user_md_files == 20
    assert res.ceremony_penalty > 0


def test_ceremony_penalty_ignores_provenance_files(tmp_path: Path) -> None:
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    for i in range(20):
        (claude_dir / f"hm-{i}.md").write_text(
            f"---\ncontent_hash: deadbeef{i}\n---\n# generated\n"
        )
    res = compute_readiness(tmp_path, Preset.SIDE)
    assert res.user_md_files == 0
    assert res.ceremony_penalty == 0
