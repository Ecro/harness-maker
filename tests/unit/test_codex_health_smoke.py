"""Phase 1 — H4 positive Codex smoke check in /hm:health (PLAN-crossmodel-codex-gaps ADR-005)."""

from __future__ import annotations

from harness_maker.models import HarnessConfig
from harness_maker.render import _make_env
from harness_maker.synthesize import _HARNESS_MAKER_PKG_ROOT


def _render_health(*, codex_enabled: bool, is_codex: bool = False) -> str:
    env = _make_env()
    cfg = HarnessConfig().model_dump(mode="json")
    cfg["codex_second_opinion"]["enabled"] = codex_enabled
    return env.get_template("commands/hm/health.md.j2").render(
        config=cfg,
        harness_maker_src_path=_HARNESS_MAKER_PKG_ROOT,
        is_codex=is_codex,
        project_name="",
        feature="",
    )


def test_smoke_block_present_when_codex_enabled() -> None:
    out = _render_health(codex_enabled=True)
    assert "codex exec" in out
    assert "smoke" in out.lower()
    assert "--sandbox read-only" in out


def test_smoke_block_absent_when_codex_disabled() -> None:
    out = _render_health(codex_enabled=False)
    assert "codex exec" not in out


def test_smoke_block_surfaces_explicit_pass_fail() -> None:
    """The block must instruct a pass/fail report — a silent smoke is useless (H4)."""
    out = _render_health(codex_enabled=True)
    low = out.lower()
    assert "pass" in low
    assert "fail" in low
