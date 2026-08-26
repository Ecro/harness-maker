"""AC-001 + AC-002 — CLAUDE.md's second-opinion guidance and its line ceiling.

**AC-001 is a DIFFERENTIAL oracle, not a grep** (machine SPEC `oracle_evidence`: "cannot be
satisfied by rewording the doc alone"). The distinction is load-bearing here:
`[fail:test] assertion-invariant-over-named-dimension` instance (a) records three tests that
asserted "Pass 1.5 is active" and stayed green after its dispatch was deleted, because
`assert "Pass 1.5" in review` matched the sentence announcing the removal. A predicate over
prose is satisfiable by prose ABOUT the predicate. So this file EXECUTES the command CLAUDE.md
documents and compares its number to the shipped reader's on the same fixture ledger.

The fixture is built so the two numbers CANNOT agree by accident: 20 rows, 12 of them written
by a test suite and named by the fixture exclusions file. Hand-computing
`(skipped + failed) / total` over it yields **60%**; the exclusion-aware reader yields **0%**.
`test_the_fixture_actually_discriminates` pins that gap — without it every assertion below
would hold for a ledger with no excluded rows, i.e. decoratively.

Fixture, never the live ledger: the SPEC's Test-isolation constraint forbids touching the base
repo's ledgers, and a live read would be non-deterministic.

Wrong implementations these assertions reject:
  1. CLAUDE.md keeps the hand formula and never names the reader — no runnable command to
     extract, `test_guidance_documents_a_runnable_command` fails at extraction;
  2. CLAUDE.md names the reader in prose only ("use verifier_discrimination") — extraction
     finds no command line, same failure;
  3. CLAUDE.md documents a command that runs but computes something else — the differential
     compares numbers, not text;
  4. AC-002 satisfied by DELETING the oversize blocks instead of relocating them — the
     relocation fixtures are compared byte-for-byte against the docs/ targets;
  5. AC-002 satisfied by a dangling pointer — each pointer's path must resolve to a real file.

Phase A.4 — justified pass (1 of 9 in this file):
  `test_the_fixture_actually_discriminates` passes before the implementation because it asserts
  on the FIXTURE, not the subject. It is a fixture-validity guard, and the defect it detects is
  a different one: if the fixture is ever edited so the exclusions stop mattering, naive and
  reader converge and `test_claude_md_prescribes_shipped_second_opinion_reader` silently becomes
  a tautology. `[fail:test] assertion-invariant-over-named-dimension` names exactly that —
  "an unreachable fixture makes the assertion decorative". RED positive sibling whose value it
  protects: `test_claude_md_prescribes_shipped_second_opinion_reader`.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]
_CLAUDE_MD = _REPO / "CLAUDE.md"
_FIXTURES = _REPO / "tests" / "fixtures"
_LEDGER_FIXTURE = _FIXTURES / "second_opinion_excluded.jsonl"
_EXCLUSIONS_FIXTURE = _FIXTURES / "ledger_exclusions.json"
_RELOCATED = _FIXTURES / "claude_md_relocated_blocks"

_CEILING = 500  # harness-maker's own Production context-lint threshold (readiness.py).
_SUBSTANTIAL = 40  # min chars for a line to be evidence that a block did not move.
_WINDOW = 12  # lines either side of the documented command that count as its guidance.


def _claude_md() -> str:
    return _CLAUDE_MD.read_text(encoding="utf-8")


def _staged_ledger(tmp_path: Path) -> Path:
    """The fixture ledger beside its exclusions file, under the names the reader expects."""
    obs = tmp_path / "observability"
    obs.mkdir(parents=True)
    ledger = obs / "second-opinion.jsonl"
    shutil.copy(_LEDGER_FIXTURE, ledger)
    shutil.copy(_EXCLUSIONS_FIXTURE, obs / ".ledger-exclusions.json")
    return ledger


def _naive_loss_rate(ledger: Path) -> dict[str, float]:
    """`(skipped + failed) / total` per model, exactly as CLAUDE.md used to prescribe."""
    per: dict[str, list[int]] = {}
    for line in ledger.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("finding_ref") != "n/a" or row.get("stage") == "health":
            continue
        bucket = per.setdefault(str(row["model"]), [0, 0])
        bucket[0] += 1
        if row.get("status") != "invoked":
            bucket[1] += 1
    return {m: bad / total for m, (total, bad) in per.items() if total}


def _reader_loss_rate(ledger: Path) -> dict[str, float]:
    """The shipped reader, called in-process — the reference side of the differential."""
    import contextlib
    import io

    from harness_maker import verifier_discrimination

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        assert verifier_discrimination.main(["report", "--ledger", str(ledger)]) == 0
    payload = json.loads(buf.getvalue())
    return {m: float(v["loss_rate"]) for m, v in payload["models"].items()}


def _documented_command(text: str) -> list[str]:
    """The runnable command CLAUDE.md prescribes for the second-opinion loss metric.

    Extraction is deliberately strict — a prose mention is not a command. We take the first
    line anywhere in the file that both names the reader's `report` verb and looks like an
    invocation (starts with `hm ` or contains `verifier_discrimination report`).
    """
    for raw in text.splitlines():
        line = raw.strip().strip("`").strip()
        if "verifier_discrimination report" not in line:
            continue
        if not (
            line.startswith("hm ") or line.startswith("uv run") or line.startswith("python -m")
        ):
            continue
        return line.split()
    raise AssertionError(
        "CLAUDE.md documents no runnable command containing 'verifier_discrimination report'. "
        "A prose mention does not satisfy AC-001's differential oracle."
    )


# ── AC-001 ────────────────────────────────────────────────────────────────────────────────


def test_the_fixture_actually_discriminates(tmp_path: Path) -> None:
    """Without this gap the differential below would hold for any implementation."""
    ledger = _staged_ledger(tmp_path)
    naive = _naive_loss_rate(ledger)
    reader = _reader_loss_rate(ledger)
    assert naive["codex"] == pytest.approx(0.60)
    assert reader["codex"] == pytest.approx(0.0)
    assert naive["codex"] != reader["codex"]


def test_claude_md_prescribes_shipped_second_opinion_reader(tmp_path: Path) -> None:
    """AC-001: the documented procedure's number equals the shipped reader's."""
    argv = _documented_command(_claude_md())
    ledger = _staged_ledger(tmp_path)

    # Run the documented command as a SUBPROCESS against the fixture — the text has to work,
    # not merely mention the right module.
    cmd = [sys.executable, "-m", "harness_maker.verifier_discrimination"]
    cmd += [
        a for a in argv if a not in {"hm", "verifier_discrimination", "uv", "run", "python", "-m"}
    ]
    if "--ledger" not in cmd:
        cmd += ["--ledger", str(ledger)]
    else:
        cmd[cmd.index("--ledger") + 1] = str(ledger)

    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=_REPO, timeout=120)
    assert proc.returncode == 0, proc.stderr
    documented = {m: float(v["loss_rate"]) for m, v in json.loads(proc.stdout)["models"].items()}

    assert documented == _reader_loss_rate(ledger)


def test_guidance_names_the_exclusions_file() -> None:
    """The reader alone is not enough — the operator must know WHY the numbers differ.

    **Bound to the command's neighbourhood, not to the whole file** (review round 2, tests
    lens). A bare `".ledger-exclusions.json" in _claude_md()` is satisfiable by prose ABOUT
    the exclusions file anywhere on the page — and this document narrates the 30x misread at
    length, so that assertion passed while carrying no information about whether the
    PRESCRIBED RECIPE names the file. That is `[fail:test]
    assertion-invariant-over-named-dimension`'s canonical shape: a predicate over prose
    satisfied by prose about the predicate.

    Rejects: guidance that names the reader but never tells the operator the exclusions file
    is what makes the two numbers differ.
    """
    lines = _claude_md().splitlines()
    anchor = next(i for i, line in enumerate(lines) if "verifier_discrimination report" in line)
    window = "\n".join(lines[max(0, anchor - _WINDOW) : anchor + _WINDOW])
    assert ".ledger-exclusions.json" in window, (
        f"the exclusions file is not named within {_WINDOW} lines of the documented command"
    )


# ── AC-002 ────────────────────────────────────────────────────────────────────────────────


def test_claude_md_within_production_line_ceiling() -> None:
    lines = len(_claude_md().splitlines())
    assert lines <= _CEILING, f"CLAUDE.md is {lines} lines against the {_CEILING} ceiling"


@pytest.mark.parametrize("fixture", sorted(_RELOCATED.glob("*.md")), ids=lambda p: p.name)
def test_relocated_block_survives_byte_for_byte(fixture: Path) -> None:
    """Rejects implementation 4. The fixture is the INDEPENDENT reference, captured pre-move."""
    body = fixture.read_text(encoding="utf-8").rstrip("\n")
    targets = list((_REPO / "docs").rglob("*.md"))
    assert any(body in t.read_text(encoding="utf-8") for t in targets), (
        f"the block captured in {fixture.name} appears verbatim in no file under docs/ — "
        "AC-002 requires relocation, not deletion or summarisation"
    )


@pytest.mark.parametrize("fixture", sorted(_RELOCATED.glob("*.md")), ids=lambda p: p.name)
def test_claude_md_points_at_the_relocated_block(fixture: Path) -> None:
    """Rejects implementation 5. The pointer's path must resolve to the file holding the block."""
    body = fixture.read_text(encoding="utf-8").rstrip("\n")
    holders = [
        t.relative_to(_REPO).as_posix()
        for t in (_REPO / "docs").rglob("*.md")
        if body in t.read_text(encoding="utf-8")
    ]
    assert holders, f"no docs/ file holds {fixture.name}"
    text = _claude_md()
    assert any(h in text for h in holders), f"CLAUDE.md contains no pointer to any of {holders}"


def test_the_relocated_body_left_claude_md() -> None:
    """The move must actually reduce CLAUDE.md — a pointer ADDED beside the kept block is not it.

    **Assertion changed after Phase C, deliberately and in the STRICTER direction.** The first
    version asserted the section HEADING was gone. The requirement it encoded — "a heading left
    behind means the block was left behind" — is wrong: the heading and the body are separable,
    and the natural home for the pointer IS that heading. That sentence does not refer to the
    implementation, which is the test `[fail:test] assertion-amended-to-match-the-fix` gives for
    telling a legitimate correction from one written to accommodate a fix.

    The replacement is stronger where it matters: it pins the BODY, so a block kept under a
    renamed heading now fails too, which the old form would have missed. It is weaker only on
    the dimension that never mattered. `_SUBSTANTIAL` skips short lines (list markers, fences,
    blank-ish lines) whose recurrence across a document carries no information.
    """
    text = _claude_md()
    for fixture in sorted(_RELOCATED.glob("*.md")):
        body_lines = fixture.read_text(encoding="utf-8").splitlines()[1:]
        substantial = [line for line in body_lines if len(line.strip()) >= _SUBSTANTIAL]
        assert substantial, f"{fixture.name} has no line long enough to be evidence"
        still_present = [line for line in substantial if line in text]
        assert not still_present, (
            f"{len(still_present)} line(s) of {fixture.name} are still in CLAUDE.md, "
            f"e.g. {still_present[0][:70]!r}"
        )
