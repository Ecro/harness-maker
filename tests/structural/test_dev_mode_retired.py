"""AC-004 / AC-005 (SPEC-dev-mode-removal): the retired axis leaves no reference and no arm.

AC-004 quantifies absence over EVERY text file under `src/` — templates included — rather than
sampling the sites this change edited. A sampled check passes on exactly the files the author
remembered; the tree does not.

The allowlist is the single migration site. It must spell the old key and its two values to
translate them, and nothing else may.

Document names (`SPEC-dev-mode-removal`, `PLAN-spec-optional-task-driven`, ...) are removed
before scanning: a provenance citation names a document, not the config axis, and forbidding
it would forbid citing the very SPEC that retired the axis. The strip is anchored on the
uppercase document prefix, so a bare `dev_mode` or `spec-driven` is still caught.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
MIGRATION_SITE = SRC / "harness_maker" / "io_utils.py"
TOKENS = re.compile(r"dev_mode|dev-mode|DevMode|spec-driven|task-driven")
_DOC_NAME = re.compile(r"\b(?:SPEC|PLAN|RESEARCH|REVIEW|BASELINE-DELTA|MUTATION)-[a-z0-9-]+")
_TEXT = {".py", ".j2", ".md", ".json", ".yaml", ".yml", ".toml", ".txt", ".mdc"}


def test_ac_004_no_dev_mode_reference_survives() -> None:
    hits = sorted(
        str(p.relative_to(ROOT))
        for p in SRC.rglob("*")
        if p.is_file()
        and p.suffix in _TEXT
        and TOKENS.search(_DOC_NAME.sub("", p.read_text(encoding="utf-8")))
    )
    assert hits == [str(MIGRATION_SITE.relative_to(ROOT))], (
        f"files still naming the retired axis: {[h for h in hits if not h.endswith('io_utils.py')]}"
    )


def snapshot_arms() -> list[Path]:
    return sorted((ROOT / "tests" / "snapshot").glob("*.expected.yaml"))


def instruction_baseline_keys() -> list[str]:
    data = json.loads((ROOT / "tests" / "structural" / "instruction_baseline.json").read_text())
    return list(data["commands"])


def test_ac_005_snapshot_arms_halve() -> None:
    from harness_maker import step_sensitivity as ss
    from harness_maker.models import Preset

    arms = snapshot_arms()
    assert len(arms) == 4, [a.name for a in arms]
    assert not any(a.name.endswith(("-spec.expected.yaml", "-task.expected.yaml")) for a in arms)
    assert not any(
        "@" in k and k.split("@")[1] in {"spec-driven", "task-driven"}
        for k in instruction_baseline_keys()
    )
    # One render arm per preset: the matrix is a function of `preset` alone.
    assert set(ss.ARMS) == set(Preset)
