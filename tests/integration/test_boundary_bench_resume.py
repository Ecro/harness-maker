"""SPEC-hm-eval-scripted-dri — the live `--resume` precondition of the scripted hm arm.

The runner reads each resumed turn's `total_cost_usd` as the session's running total and resumes
turn one's `session_id` (S4, S5). That rests on CLI behaviour that is observed, not documented,
so this checks it against the real `claude` CLI before a re-run: two tiny turns in one resumed
session keep the session id, the reported total does not fall, and the last total stays within
SUSPECT_GAP of the transcript price of the whole session.

Advisory and live: it runs only with INTEGRATION=1 and a `claude` on PATH, in a throwaway dir
outside any git work tree, and costs a few cents. It uses the bench's own argv and invoke helpers.
"""

from __future__ import annotations

import importlib.util
import os
import shutil
import sys
import tempfile
from pathlib import Path
from types import ModuleType

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = _ROOT / "scripts" / "bench_light_lane.py"
_TURN_BUDGET_USD = 0.2

pytestmark = pytest.mark.skipif(
    not os.getenv("INTEGRATION") or shutil.which("claude") is None,
    reason="live claude CLI call; set INTEGRATION=1 with claude on PATH",
)


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("bench_light_lane", _SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["bench_light_lane"] = module  # dataclasses resolve their module by name
    spec.loader.exec_module(module)
    return module


def test_resume_keeps_the_session_and_a_running_total() -> None:
    bench = _load()
    base = Path(tempfile.mkdtemp(prefix="hm-resume-smoke-", dir=os.getenv("HM_SMOKE_DIR")))
    try:
        work = base / "work"
        work.mkdir()
        model = os.getenv("HM_BENCH_MODEL", bench.DEFAULT_MODEL)
        first = bench.agent_argv(
            "claude", "Reply with the single word: one.", model, 2, _TURN_BUDGET_USD
        )
        pass_env = ("IS_SANDBOX",)
        out1, _err1, code1 = bench._invoke(first, work, 300, pass_env)
        one = bench.parse_cli_result(out1)
        assert code1 == 0, out1
        assert one is not None, out1
        session = one.get("session_id")
        assert isinstance(session, str), one
        second = bench.resume_argv(first, "Now reply with the single word: two.", session)
        out2, _err2, code2 = bench._invoke(second, work, 300, pass_env)
        two = bench.parse_cli_result(out2)
        assert code2 == 0, out2
        assert two is not None, out2
        assert two.get("session_id") == session, "a resumed turn keeps the session id"
        totals = [bench._cli_cost(one), bench._cli_cost(two)]
        assert None not in totals, totals
        assert totals[1] >= totals[0], f"the reported total fell: {totals}"
        transcript = bench.transcript_cost(work, bench.default_transcript_root()).usd
        cli = bench.dri_cli_cost(totals)
        assert cli is not None
        gap = abs(cli - transcript) / max(cli, transcript)
        print(f"totals={totals} transcript={transcript:.6f} gap={gap:.3f}")
        assert gap <= bench.SUSPECT_GAP, (totals, transcript)
    finally:
        shutil.rmtree(base, ignore_errors=True)
