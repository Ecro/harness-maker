"""AC-001 (SPEC-intent-layer-ops) — measured evidence references the definition, not the command.

Oracle: property. The expected string is built from the appended row's own `definition_hash`
and the fixture repo's `git rev-parse --short HEAD` — neither is read back from how the verb
formats evidence. For any padding length the evidence has the same length and carries no argv
token longer than 3 characters; the shipped argv-copying writer fails both. The padding filler
is `Z` — outside `[0-9a-f]` and outside the fixed words `auto/measure/exit/base/checkout`, so a
token cannot collide with the hash or the frame by construction.

The manual-record and pre-existing-row halves are golden: the operator's text is verbatim, and a
row the tool wrote before stays a byte prefix of the file after the next append (`_append_value`
re-dumps the file, so hand-written formatting is out of scope — SPEC S1).

Phase A.4: `test_ac_001_manual_record_keeps_the_operators_evidence_verbatim` passes before the
change on purpose — it is the negative invariant (manual evidence is never rewritten into the
hash form). It goes red the moment the new format leaks into `record_value`; its RED positive
sibling is `test_ac_001_measured_evidence_references_the_definition_not_the_command`.
"""

from __future__ import annotations

import os
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from harness_maker import world
from tests.unit import world_fixture as fx

settings.register_profile(
    "ci",
    derandomize=True,
    max_examples=6,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
settings.register_profile(
    "dev",
    max_examples=30,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "ci"))


@pytest.fixture(autouse=True)
def _python_on_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PATH", str(Path(sys.executable).parent) + os.pathsep + os.environ["PATH"])


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *args], check=True, capture_output=True, text=True, timeout=60
    ).stdout.strip()


def _committed(root: Path, *outcomes: dict[str, Any]) -> str:
    fx.build_root(root, intent=fx.intent_doc(*outcomes))
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "fixture")
    return _git(root, "rev-parse", "--short", "HEAD")


def _rows(root: Path) -> list[dict[str, Any]]:
    return list(fx.load(fx.outcomes_path(root))["values"])


@given(pad=st.integers(min_value=0, max_value=600))
def test_ac_001_measured_evidence_references_the_definition_not_the_command(
    tmp_path_factory: pytest.TempPathFactory, pad: int
) -> None:
    root = tmp_path_factory.mktemp("evref")
    cmd = "python -c 'print(7)' #" + "Z" * pad
    carry = fx.outcome("carry", measure={"cmd": cmd, "select": "last-number"})
    sha = _committed(root, carry)

    proc = fx.run_cli(["--root", str(root), "outcome", "measure", "carry", "--json"], cwd=root)
    assert proc.returncode == 0, proc.stdout + proc.stderr

    row = _rows(root)[-1]
    assert row["value"] == 7
    assert row["definition_hash"] == fx.definition_hash(carry)
    expected = f"auto: measure#{row['definition_hash'][:12]} @ {sha} exit=0 cwd=base"
    assert row["evidence"] == expected
    leaked = [t for t in shlex.split(cmd) if len(t) > 3 and t in row["evidence"]]
    assert not leaked, f"argv copied into evidence: {leaked}"
    # Constant length: the frame + 12 hex + the sha, whatever the command's length.
    assert len(row["evidence"]) == len("auto: measure# @  exit=0 cwd=base") + 12 + len(sha)


def test_ac_001_manual_record_keeps_the_operators_evidence_verbatim(tmp_path: Path) -> None:
    carry = fx.outcome("carry")
    _committed(tmp_path, carry)
    text = "read off the dashboard by hand — screenshot in #ops"
    proc = fx.run_cli(
        [
            "--root",
            str(tmp_path),
            "outcome",
            "record",
            "carry",
            "--value",
            "4",
            "--observed-at",
            "2026-09-18T00:00:00Z",
            "--evidence",
            text,
            "--json",
        ],
        cwd=tmp_path,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert _rows(tmp_path)[-1]["evidence"] == text


def test_ac_001_a_tool_written_row_is_a_byte_prefix_after_the_next_measure(tmp_path: Path) -> None:
    carry = fx.outcome("carry", measure={"cmd": "python -c 'print(3)'", "select": "last-number"})
    _committed(tmp_path, carry)
    world.record_value(
        tmp_path,
        outcome_id="carry",
        value=1,
        observed_at="2026-09-01T00:00:00Z",
        evidence="auto: python probe.py @ abc1234 exit=0 cwd=base",  # an old-format row
    )
    before = fx.outcomes_path(tmp_path).read_bytes()
    first = _rows(tmp_path)[0]

    proc = fx.run_cli(
        ["--root", str(tmp_path), "outcome", "measure", "carry", "--json"], cwd=tmp_path
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr

    after = fx.outcomes_path(tmp_path).read_bytes()
    assert after.startswith(before), "the earlier row was rewritten"
    assert _rows(tmp_path)[0] == first
    assert _rows(tmp_path)[-1]["evidence"].startswith("auto: measure#")
