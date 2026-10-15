"""SPEC-hm-light-lane-s3c AC-008 — the other light-path CLIs keep their one a7403f2f success line.

A pin, not a change: each CLI already prints one JSON line on success. The oracle is each one's
stdout from the a7403f2f module on the same fixture (`cli_a7403f2f.json`, captured by
`tests/fixtures/light_lane_s3c/capture_a7403f2f.py.txt`), with the temp root, wall-clock numbers
and the per-machine verification key masked on both sides by the same function.
"""

from __future__ import annotations

import json
from typing import Any

from tests.unit import light_lane_s3c_fixture as fx

OLD: dict[str, dict[str, Any]] = json.loads(
    (fx.GOLDENS / "cli_a7403f2f.json").read_text(encoding="utf-8")
)["outputs"]
LIGHT_PATH_CLIS = (
    "autopilot status",
    "autopilot_caps boundary proceed",
    "autopilot_caps boundary merge-gate",
    "spec_machine approval-status",
    "spec_need record",
    "spec_need frontmatter-upsert",
    "spec_need op-check",
    "spec_need waiver-check",
    "observability.verification_cache run",
)


def test_light_path_clis_unchanged() -> None:
    new = fx.light_path_outputs()
    assert set(new) == set(LIGHT_PATH_CLIS) == set(OLD)
    for cli in LIGHT_PATH_CLIS:
        out = new[cli]["stdout"]
        assert new[cli]["exit"] == 0, (cli, out)
        assert out.count("\n") <= 1, (cli, out)
        assert out == OLD[cli]["stdout"], cli
        assert new[cli]["exit"] == OLD[cli]["exit"], cli
