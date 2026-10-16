"""Phase 4 contract: the rendered /hm:metrics carries the economics section.

These are render-GREP tests over the artifact actually written to disk. They prove the
instruction is PRESENT — they cannot prove the interpreting LLM obeys it. That asymmetry
is ADR-002's stated position: the data layer is enforced (schema test), the prose layer is
instructed.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from harness_maker.interview import interview
from harness_maker.profile import profile
from harness_maker.render import DEFAULT_FREEZE_TIME, render
from harness_maker.synthesize import synthesize


@pytest.fixture(scope="module")
def metrics_body(tmp_path_factory: pytest.TempPathFactory) -> str:
    fake_home = tmp_path_factory.mktemp("hm-home")
    out = tmp_path_factory.mktemp("hm-out")
    monkey = pytest.MonkeyPatch()
    monkey.setattr(Path, "home", lambda: fake_home)
    try:
        fix_dir = Path(__file__).parent.parent / "fixtures" / "prod-tauri-app"
        p = profile(fix_dir)
        a = interview(p, autoloop_mode=True)
        bp = synthesize(p, a)
        render(bp, out, dry_run=False, freeze_time=DEFAULT_FREEZE_TIME)
    finally:
        monkey.undo()
    rendered = out / "commands" / "hm" / "metrics.md"
    if not rendered.is_file():
        pytest.fail(f"metrics.md was not rendered at {rendered}")
    return rendered.read_text(encoding="utf-8")










def test_non_gate_framing_is_inherited(metrics_body: str) -> None:
    assert "never a gate" in metrics_body




# ------------------------------------------------------ Phase 3: retroactive classification




def test_the_classification_step_precedes_the_report_command(metrics_body: str) -> None:
    """Order is load-bearing, not cosmetic: verdicts recorded AFTER `economics report`
    runs do not reach that report, so the run appears to have recovered nothing and
    the operator concludes the feature does not work."""
    boundaries_at = metrics_body.index("run_classify boundaries")
    record_at = metrics_body.index("run_classify record")
    report_at = metrics_body.index("hm economics report")
    assert boundaries_at < record_at < report_at








