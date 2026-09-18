"""AC-001, AC-002, AC-013 (SPEC-assumption-entry-and-evidence-locator) — `hm world assume add`.

Every assertion is on the reloaded file or on the shipped CLI's output (`world_fixture.run_cli`,
a subprocess — the seam rule), never on a return value. Expected records are hand-written from
SPEC S1 / S2, not read back from the writer.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.unit import world_fixture as fx

TS = "2026-09-18T09:30:00+09:00"
TS_UTC = "2026-09-18T00:30:00Z"


def _root(tmp_path: Path) -> Path:
    return fx.build_root(tmp_path, assumptions=[fx.assumption("existing", claim="E")])


def test_ac_001_add_creates_record(tmp_path: Path) -> None:
    root = _root(tmp_path)
    proc = fx.run_cli(["assume", "add", "x", "--claim", "C", "--status", "assumed"], root)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    proc = fx.run_cli(
        [
            "assume",
            "add",
            "y",
            "--claim",
            "D",
            "--status",
            "known",
            "--text",
            "seen in the log",
            "--observed-at",
            TS,
        ],
        root,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    doc = fx.load(fx.assumptions_path(root))
    assert doc == {
        "schema_version": 1,
        "assumptions": [
            fx.assumption("existing", claim="E"),
            {"id": "x", "claim": "C", "status": "assumed", "evidence": [], "history": []},
            {
                "id": "y",
                "claim": "D",
                "status": "known",
                "evidence": [
                    {"text": "seen in the log", "observed_at": TS_UTC, "relation": "confirms"}
                ],
                "history": [],
            },
        ],
    }


def test_ac_001_add_creates_the_file_and_envelope_when_absent(tmp_path: Path) -> None:
    root = _root(tmp_path)
    fx.assumptions_path(root).unlink()
    proc = fx.run_cli(["assume", "add", "x", "--claim", "C", "--status", "unknown"], root)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert fx.load(fx.assumptions_path(root)) == {
        "schema_version": 1,
        "assumptions": [
            {"id": "x", "claim": "C", "status": "unknown", "evidence": [], "history": []}
        ],
    }


#: Refusal layers (PLAN "CLI shape"): `--status conflict` is argparse `choices` (exit 2, stderr);
#: every other refusal is a `WorldError` emitted on stdout as `error: {field: …}` (exit 1).
_NAIVE = "2026-09-18T00:00:00"


@pytest.mark.parametrize(
    ("args", "channel", "needle"),
    [
        (["existing", "--claim", "C", "--status", "known"], "stdout", "field: id"),
        (
            ["x", "--claim", "C", "--status", "conflict"],
            "stderr",
            "argument --status: invalid choice",
        ),
        (["x", "--claim", "   ", "--status", "known"], "stdout", "field: claim"),
        (["Bad-Id", "--claim", "C", "--status", "known"], "stdout", "field: id"),
        (
            ["x", "--claim", "C", "--status", "known", "--text", "t", "--observed-at", _NAIVE],
            "stdout",
            "field: observed_at",
        ),
        (
            ["x", "--claim", "C", "--status", "known", "--locator", "a.py:1-1"],
            "stdout",
            "field: text",
        ),
        (["x", "--claim", "C", "--status", "known", "--text", "t"], "stdout", "field: observed_at"),
        (["x", "--claim", "C", "--status", "known", "--observed-at", TS], "stdout", "field: text"),
        (["x", "--claim", "C", "--status", "known", "--locator", ""], "stdout", "field: text"),
        (["x", "--claim", "C", "--status", "known", "--observed-at", ""], "stdout", "field: text"),
    ],
)
def test_ac_002_add_refusals_write_nothing(
    tmp_path: Path, args: list[str], channel: str, needle: str
) -> None:
    root = _root(tmp_path)
    before = fx.assumptions_path(root).read_bytes()
    proc = fx.run_cli(["assume", "add", *args], root)
    assert proc.returncode != 0
    assert needle in (proc.stdout if channel == "stdout" else proc.stderr)
    assert fx.assumptions_path(root).read_bytes() == before


def test_ac_002_a_refusal_on_an_absent_file_leaves_it_absent(tmp_path: Path) -> None:
    root = _root(tmp_path)
    fx.assumptions_path(root).unlink()
    proc = fx.run_cli(["assume", "add", "x", "--claim", "", "--status", "known"], root)
    assert proc.returncode != 0
    assert "field: claim" in proc.stdout
    assert not fx.assumptions_path(root).exists()


def test_ac_013_add_prints_changed_line(tmp_path: Path) -> None:
    root = _root(tmp_path)
    ok = fx.run_cli(["assume", "add", "x", "--claim", "C", "--status", "known"], root)
    refused = fx.run_cli(["assume", "add", "x", "--claim", "C", "--status", "known"], root)
    assert "changed: assumptions.yaml" in ok.stdout
    assert refused.returncode != 0
    assert "changed:" not in refused.stdout
