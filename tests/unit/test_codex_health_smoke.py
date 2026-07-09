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
    assert "codex exec" in out
    assert "smoke" in out.lower()
    assert "--sandbox read-only" in out


def test_smoke_block_absent_when_disabled() -> None:
    out = _render_health(models=[])
    assert "codex exec" not in out
    assert "agy --print --sandbox --print-timeout 120s" not in out


def test_smoke_block_surfaces_explicit_pass_fail() -> None:
    """The block must instruct a pass/fail report — a silent smoke is useless (H4)."""
    out = _render_health(models=["codex"])
    low = out.lower()
    assert "pass" in low
    assert "fail" in low


def test_antigravity_smoke_block_uses_timeout_wrapped_agy() -> None:
    """The antigravity smoke recipe must wrap `agy` in `timeout` (Phase-1 hang guard)."""
    out = _render_health(models=["antigravity"])
    assert "agy --print --sandbox --print-timeout 120s" in out
    assert "adapt --model antigravity" in out
    low = out.lower()
    assert "pass" in low
    assert "fail" in low


def test_smoke_ledger_path_referenced() -> None:
    """The ledger cross-ref must point at the multi-model ledger filename, not the
    legacy single-vendor one."""
    out = _render_health(models=["codex", "antigravity"])
    assert ".claude/observability/second-opinion.jsonl" in out
    assert "codex-second-opinion.jsonl" not in out
