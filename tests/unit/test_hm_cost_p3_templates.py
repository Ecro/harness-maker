"""SPEC-hm-cost-p3 AC-001/003/004: what the rendered spec, execute and wrapup stages say."""

from __future__ import annotations

from typing import Any

from harness_maker.models import HarnessConfig
from harness_maker.render import _make_env
from harness_maker.synthesize import _HARNESS_MAKER_PKG_ROOT


def _render(stage: str, *, is_codex: bool = False) -> str:
    cfg: dict[str, Any] = HarnessConfig().model_dump(mode="json")
    return (
        _make_env()
        .get_template(f"stages/{stage}.md.j2")
        .render(
            stage=stage, workflow_context="", project_name="", feature="", config=cfg,
            harness_maker_src_path=_HARNESS_MAKER_PKG_ROOT, is_codex=is_codex,
        )
    )  # fmt: skip


def _step(text: str, number: str) -> str:
    head = f"## Step {number} "
    assert head in text, f"no {head!r}"
    body = text.split(head, 1)[1]
    return body.split("\n## ", 1)[0]


def test_ac_001_spec_defaults() -> None:
    for is_codex in (False, True):
        text = _render("spec", is_codex=is_codex)
        step = _step(text, "4.6")
        for phrase in (
            "under Refinement Decisions as a default",
            "surface every critical critique",
            "an irreversible-decision or oracle critique is never a default",
        ):
            assert phrase in step, (is_codex, phrase)
        assert "Open Questions holds only what you cannot decide" in _step(text, "3")
        assert "record the critiques under Open Questions" not in text


def test_ac_003_reuse_wiring() -> None:
    for is_codex in (False, True):
        assert "hm check --slug <slug> --reuse" in _step(_render("wrapup", is_codex=is_codex), "1")
        step6 = _step(_render("execute", is_codex=is_codex), "6")
        final = "then always run `hm check --slug <slug>`"
        assert final in step6
        assert step6.index("REVIEW-<slug>") < step6.index(final)
        assert "never change a disposition to pass the gate" in step6


def test_ac_004_batching() -> None:
    for is_codex in (False, True):
        text = _render("execute", is_codex=is_codex)
        assert "Chain independent shell steps with `&&` in one Bash call" in text
        assert "except `hm check`, the RED run and any step marked as its own call" in text
