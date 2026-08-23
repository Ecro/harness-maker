"""A NEW structural gate may not ship without a receipt naming the line that kills it.

This is the consumer `mutation_receipt` was missing. Until it existed the module was a
registered CLI that nothing called: the vocabulary was there, the storage was there, and the
obligation was still exactly as unenforced as before — which three reviewers and one
cross-model voter all said, correctly, in the same round.

**What is now enforced.** Every gate under `tests/structural/` that is not on the debt list
below must have a row in `.claude/observability/mutation-receipts.jsonl` whose `gate` node id
lives in that file. Filing the row forces the author to answer "which source line, when
deleted, turns this red?" — and `mutation_receipt.record` already refuses an answer that is
not a runnable node id and an openable `file:line`.

**What is still NOT enforced, and is the honest limit.** Nothing here re-runs the mutation.
A row asserts that the author deleted the line and watched the test die; this test asserts
only that the answer exists and is shaped like an answer. Deciding "does this assertion
reject the wrong implementation?" is not decidable in general (ADR-003), and a full mutation
run over the suite is out of scope for the same runtime reason `mutmut` is gated to
machine-SPEC paths. A false receipt is possible. An ABSENT one no longer is.

**Population is derived, debt is enumerated — and those are different things.** ADR-001's
"derive the population, never enumerate it" governs what is under guard, and that is a glob
of the directory. `git ls-files` is deliberately NOT used: the three gates this task added
were untracked when they were written, so a tracked-only population would have passed over
precisely the files the guard exists for — the same vacuity that let G1 ship without the
artifact class it was written for. The debt list below is the other kind of list: finite,
frozen, and allowed only to shrink.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
STRUCTURAL = REPO_ROOT / "tests" / "structural"


def _ledger() -> Path:
    """The ledger the WRITER writes, resolved the writer's way.

    `mutation_receipt.record` deliberately files at the BASE repo so rows survive
    `task-land` — the `codex_ledger` row-loss lesson. Rooting this reader at
    `REPO_ROOT` instead looked right and was wrong: run from a task worktree, the gate
    read an empty path while every receipt sat one level up, so the guard reported
    "no receipt" for gates that had one. Same resolver on both ends, or the two ends
    disagree about where the file is.
    """
    from harness_maker.mutation_receipt import _base_root

    return _base_root(REPO_ROOT) / ".claude" / "observability" / "mutation-receipts.jsonl"


#: Gates that predate this consumer. Every one is a real coverage gap: none of them has been
#: asked which line kills it. The list may SHRINK (file a receipt, delete the entry) and must
#: never grow — a new gate is exactly what this test exists to stop.
_UNRECEIPTED_DEBT: frozenset[str] = frozenset(
    {
        "test_autopilot_advance_render_gate.py",
        "test_autopilot_marker_api_session_key.py",
        "test_baseline_delta_attribution.py",
        "test_command_descriptions.py",
        "test_command_size_budget.py",
        "test_crossmodel_hoist.py",
        "test_documented_commands_exist.py",
        "test_gate_base_root_parity.py",
        "test_hm_entrypoint.py",
        "test_instruction_preservation.py",
        "test_loop_marker_prefix_is_exact.py",
        "test_loop_p5_batch_extraction.py",
        "test_make_fastpath_contract.py",
        "test_no_fused_workflow_axis.py",
        "test_no_positional_params_in_commands.py",
        "test_phase_d_reachable_window.py",
        "test_reasoning_chain_parity.py",
        "test_redundancy_matrix.py",
        "test_review_pass15_removed.py",
        "test_review_verify_uses_dep_map.py",
        "test_reviewer_outputs.py",
        "test_reviewer_prompts_contain_agentic_depth_clauses.py",
        "test_roundtrip_budget.py",
        "test_snapshot_exclusions_effective.py",
        "test_source_frontmatter_parses.py",
        "test_stage_agent_ledger_wiring.py",
        "test_step_manifest_injection.py",
        "test_surface_baseline.py",
        "test_telemetry_no_leak.py",
        "test_verifier_agent.py",
    }
)


def _gates() -> list[str]:
    """Filenames of every structural gate, tracked or not."""
    return sorted(p.name for p in STRUCTURAL.glob("test_*.py"))


def _receipted_files(ledger: Path) -> set[str]:
    """Source files named by the `gate` node id of each row: `tests/x/test_y.py::test_z`."""
    if not ledger.is_file():
        return set()
    out: set[str] = set()
    for line in ledger.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:  # pragma: no cover — a corrupt row is not a receipt
            continue
        gate = row.get("gate")
        if isinstance(gate, str) and "::" in gate:
            out.add(Path(gate.split("::", 1)[0]).name)
    return out


# --- population -------------------------------------------------------------------------


def test_the_gate_population_is_plausible() -> None:
    """A discovery test that discovers nothing is a green light over a blind spot."""
    gates = _gates()
    assert len(gates) >= 30, f"only {len(gates)} structural gates found — the glob broke"
    assert __name__.rsplit(".", 1)[-1] + ".py" in gates, "this file is not in its own population"


def test_the_debt_list_has_not_gone_stale() -> None:
    """A renamed or deleted gate must not keep a free pass under its old name.

    Without this, `git mv test_old.py test_new.py` silently converts a debt entry into an
    unguarded NEW gate — the evasion is not even deliberate, it is just a rename.
    """
    gates = set(_gates())
    stale = sorted(_UNRECEIPTED_DEBT - gates)
    assert not stale, (
        f"these are on the debt list but no longer exist: {stale}\n"
        "Delete the entries. A name that matches nothing grants a pass to nothing — or, "
        "after a rename, to the wrong file."
    )


# --- the guard --------------------------------------------------------------------------


def test_the_ledger_is_where_the_writer_puts_it() -> None:
    """Paired with the guard below, which would pass vacuously on an unreadable path.

    A guard whose input file is silently absent reports "nothing is receipted", which is
    indistinguishable from a real violation and sends the author to write a receipt that
    already exists. Assert the file, not just the verdict.
    """
    assert _ledger().is_file(), (
        f"no mutation-receipt ledger at {_ledger()} — the guard below cannot distinguish "
        "'no receipts filed' from 'reading the wrong path'"
    )


def test_every_new_structural_gate_has_a_mutation_receipt() -> None:
    receipted = _receipted_files(_ledger())
    missing = [g for g in _gates() if g not in _UNRECEIPTED_DEBT and g not in receipted]
    assert not missing, (
        "structural gates with no mutation receipt — nothing records which source line, "
        f"when deleted, turns them red: {missing}\n"
        "Delete a line you believe the gate depends on, run the gate, watch it FAIL, then:\n"
        "  uv run --with $HOME/harness-maker hm mutation_receipt record \\\n"
        "    --gate tests/structural/<file>.py::<test> --deletes <src/…/x.py:LINE>\n"
        "If no deletion turns it red, the gate asserts nothing and the fix is the gate "
        "([fail:test] assertion-invariant-over-named-dimension, count:8)."
    )


# --- ADR-002: demonstrated failure, both directions -------------------------------------
#
# The repo scan cannot show either direction: it is green today, and it would stay green if
# `_receipted_files` returned every filename in existence.


@pytest.fixture
def ledger(tmp_path: Path) -> Path:
    return tmp_path / "receipts.jsonl"


def _write(ledger: Path, *gates: str) -> None:
    ledger.write_text(
        "".join(json.dumps({"gate": g, "deletes": "src/x.py:1"}) + "\n" for g in gates),
        encoding="utf-8",
    )


def test_a_gate_with_a_receipt_is_recognised(ledger: Path) -> None:
    """The positive control. Without it every case below passes on a `_receipted_files`
    that returns nothing, which would make the guard un-satisfiable rather than strict."""
    _write(ledger, "tests/structural/test_thing.py::test_a")
    assert "test_thing.py" in _receipted_files(ledger)


@pytest.mark.parametrize(
    "rows",
    [
        (),  # empty ledger
        ("tests/structural/test_other.py::test_a",),  # a receipt for a DIFFERENT gate
    ],
)
def test_a_gate_without_its_own_receipt_is_not_recognised(
    ledger: Path, rows: tuple[str, ...]
) -> None:
    _write(ledger, *rows)
    assert "test_thing.py" not in _receipted_files(ledger)


def test_a_missing_ledger_is_not_silently_all_green(tmp_path: Path) -> None:
    """The absent case, named explicitly ([fail:design] absent-case-is-a-feature-black-hole,
    count:8). A reader that raised here would be caught in CI; one that returned "everything
    is receipted" would not, and that is the shape this rules out."""
    assert _receipted_files(tmp_path / "nope.jsonl") == set()


def test_a_row_without_a_node_id_is_not_a_receipt(ledger: Path) -> None:
    """`mutation_receipt.record` cannot write such a row, but the ledger is a plain file and
    a hand-edit can. A `gate` with no `::` names a file, not a runnable test."""
    _write(ledger, "tests/structural/test_thing.py")
    assert _receipted_files(ledger) == set()
