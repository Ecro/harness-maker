"""Phase 1 — H4 positive second-opinion smoke check in /hm:health
(PLAN-crossmodel-codex-gaps ADR-005, generalized by PLAN-second-opinion-multi-model ADR-011).
"""

from __future__ import annotations

from harness_maker.models import HarnessConfig
from harness_maker.render import _make_env
from harness_maker.synthesize import _HARNESS_MAKER_PKG_ROOT


def _render_health(*, models: list[str], is_codex: bool = False) -> str:
    env = _make_env()
    cfg = HarnessConfig().model_dump(mode="json")
    cfg["second_opinion"]["models"] = models
    return env.get_template("commands/hm/health.md.j2").render(
        config=cfg,
        harness_maker_src_path=_HARNESS_MAKER_PKG_ROOT,
        is_codex=is_codex,
        project_name="",
        feature="",
    )


def test_smoke_block_present_when_codex_enabled() -> None:
    out = _render_health(models=["codex"])
    assert "second_opinion_invoke --model codex --smoke" in out
    assert "smoke" in out.lower()
    # The raw CLI flags moved into the invoker, where a golden-argv test pins them.
    assert "codex exec --sandbox read-only" not in out


def test_smoke_block_absent_when_disabled() -> None:
    out = _render_health(models=[])
    assert "codex exec" not in out
    assert "second_opinion_invoke" not in out


def test_smoke_block_surfaces_explicit_pass_fail() -> None:
    """The block must instruct a pass/fail report — a silent smoke is useless (H4)."""
    out = _render_health(models=["codex"])
    low = out.lower()
    assert "pass" in low
    assert "fail" in low


def test_antigravity_smoke_block_calls_the_shared_invoker() -> None:
    """The smoke must go through the SAME entrypoint as the stage recipe (ADR-005).

    It used to render its own copy of the raw `agy` line. A copy can drift from the
    original, and this one did: the recipe ran inside a worktree while the smoke ran at
    the base, so the smoke validated a path the real invocation never took.
    """
    out = _render_health(models=["antigravity"])
    assert "second_opinion_invoke --model antigravity --smoke" in out
    assert "--stage health" in out
    assert "agy --print --sandbox" not in out
    low = out.lower()
    assert "pass" in low
    assert "fail" in low


def test_smoke_ledger_path_referenced() -> None:
    """The ledger cross-ref must point at the multi-model ledger filename, not the
    legacy single-vendor one."""
    out = _render_health(models=["codex", "antigravity"])
    assert ".claude/observability/second-opinion.jsonl" in out
    assert "codex-second-opinion.jsonl" not in out
