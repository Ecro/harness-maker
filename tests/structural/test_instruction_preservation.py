"""Phase 0.5 — nothing leaves an atomic command without being named (ADR-011's floor arm).

This is the gate that makes Phase 0.5's exit criterion true. The character floor in
`test_command_size_budget.py` is `measured * 0.80`; one deleted runtime instruction is
well under half a percent of any atomic command, so the floor cannot see it. What the
floor catches is *gutting*. What this catches is *a deletion* — the failure the prior
plan's withdrawn ADR-017 actually shipped, where a trim described as documentation-only
removed runtime-behavioural instructions.

Entries are keyed `<command>@<dev_mode>` because a stage template has one rendering per
config arm that gates instructions, and the two arms must be guarded **separately** —
see `_instruction_baseline.py`'s docstring for why a union would hide exactly the
deletion this exists to catch, and which axes are knowingly not covered.

The contract is deliberately asymmetric:

* **Removing** a heading or a `!` line fails, unless the exact string is listed in
  `_ALLOWED_REMOVALS` under the phase that removed it, **against the exact entry key**.
  Listing `verify@spec-driven` does not bless a removal from `verify@task-driven`: if a
  cut was meant to hit both arms it must say so twice, and if it hit only one that is
  usually the bug. Each cutting phase adds its entries **in its own commit**, the same
  discipline [ADR-011](../../work-docs/PLAN-workflow-step-audit.md#adr-011) imposes on
  floors.
* **Adding** is not constrained here — growth is the character ceiling's job.

`_ALLOWED_REMOVALS` is also checked for **staleness**: an entry naming something still
present means the allowlist drifted from reality, and a drifting allowlist is how this
kind of gate quietly stops binding.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

from ._instruction_baseline import (
    ATOMIC_COMMANDS,
    AXES,
    BASELINE_PATH,
    entry_key,
    load_baseline,
    measure_instructions,
    payload_digest,
    unlisted_removals,
)

# ── the allowlist ──────────────────────────────────────────────────────────────
# phase label → `<command>@<dev_mode>` → the exact heading / `!` line it removes.
# Empty at Phase 0.5 by construction: it is frozen BEFORE any cutting phase runs, so a
# non-empty allowlist here would mean something was already deleted unguarded.
_ALLOWED_REMOVALS: dict[str, dict[str, list[str]]] = {}

_KINDS = ("headings", "executables")
_KEYS = tuple(entry_key(c, m) for c in ATOMIC_COMMANDS for m in AXES)
_REPO_ROOT = Path(__file__).resolve().parents[2]
_SHA = re.compile(r"^[0-9a-f]{40}$")
_MACHINE_PATH = re.compile(r"(?:/home/|/Users/|/root/|/tmp/)[\w.\-/]+")


@pytest.fixture(scope="module")
def doc() -> dict[str, object]:
    return load_baseline()


@pytest.fixture(scope="module")
def frozen(doc: dict[str, object]) -> dict[str, dict[str, list[str]]]:
    commands: dict[str, dict[str, list[str]]] = doc["commands"]  # type: ignore[assignment]
    return commands


@pytest.fixture(scope="module")
def current() -> dict[str, dict[str, list[str]]]:
    return measure_instructions()


def _allowed_for(key: str) -> set[str]:
    return {item for by_key in _ALLOWED_REMOVALS.values() for item in by_key.get(key, [])}


# ── positive controls — every arm below is vacuous against a partial snapshot ───


def test_the_frozen_baseline_is_real(frozen: dict[str, dict[str, list[str]]]) -> None:
    assert BASELINE_PATH.exists(), f"Phase 0.5 instruction baseline missing: {BASELINE_PATH}"
    assert set(frozen) == set(_KEYS), sorted(set(_KEYS) ^ set(frozen))
    for key, sets in frozen.items():
        assert set(sets) == set(_KINDS), (key, sorted(sets))
        assert len(sets["headings"]) >= 10, f"{key}: only {len(sets['headings'])} headings"
    # `wrapup` is the largest surface in the pipeline; if it froze small the snapshot was
    # taken against something other than the shipped render.
    assert len(frozen["wrapup@task-driven"]["executables"]) >= 20


def test_the_snapshot_actually_distinguishes_the_config_arms(
    frozen: dict[str, dict[str, list[str]]],
) -> None:
    """The whole reason for the `@<dev_mode>` key.

    If both arms froze identical sets, the second render was a no-op and the spec-driven
    instructions would be unguarded again while the file claimed to cover them. Named
    concretely rather than by count: `verify`'s Check 6 body is the specific pair the
    task-driven render omits.
    """
    task = set(frozen["verify@task-driven"]["executables"])
    spec = set(frozen["verify@spec-driven"]["executables"])
    only_spec = spec - task
    assert only_spec, "the two dev_mode arms froze identical executables for verify"
    assert any("spec_need" in x for x in only_spec), sorted(only_spec)
    assert not any("spec_need" in x for x in task), "task-driven should not carry spec_need"


def test_the_frozen_text_carries_no_machine_specific_path(
    frozen: dict[str, dict[str, list[str]]],
) -> None:
    """Unlike its Phase 0 sibling, this artifact commits RENDERED TEXT.

    Phase 0's payload is ints and digests, so it argued the machine-path concern did not
    apply. That argument does not carry over: an unpinned freeze would bake the
    checkout's path into every `!` line here. `[fail:test] snapshot-regen-inside-worktree`
    is already at count 13.
    """
    for key, sets in frozen.items():
        for kind in _KINDS:
            for item in sets[kind]:
                assert not _MACHINE_PATH.findall(item), f"{key}/{kind}: {item}"


def test_the_baseline_carries_a_durable_render_sha(doc: dict[str, object]) -> None:
    sha = doc["render_sha"]
    assert isinstance(sha, str), sha
    assert _SHA.match(sha), f"render_sha is not a full SHA: {sha!r}"
    proc = subprocess.run(
        ["git", "cat-file", "-e", f"{sha}^{{commit}}"],
        cwd=_REPO_ROOT,
        capture_output=True,
        timeout=30,
    )
    assert proc.returncode == 0, f"render_sha {sha} is not a commit in this repo"


def test_the_committed_instructions_carry_their_digest(doc: dict[str, object]) -> None:
    """Deleting a line straight out of the JSON is the frictionless allowlist bypass."""
    commands: dict[str, dict[str, list[str]]] = doc["commands"]  # type: ignore[assignment]
    assert doc["payload_digest"] == payload_digest(commands), (
        "the committed instruction sets do not hash to their recorded digest — an entry "
        "was edited by hand instead of being regenerated"
    )


# ── the gate ───────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("key", _KEYS)
@pytest.mark.parametrize("kind", _KINDS)
def test_no_unlisted_instruction_disappeared(
    frozen: dict[str, dict[str, list[str]]],
    current: dict[str, dict[str, list[str]]],
    key: str,
    kind: str,
) -> None:
    unlisted = unlisted_removals(frozen, current, key, kind, _allowed_for(key))
    assert not unlisted, (
        f"{key}: {len(unlisted)} {kind} removed without an allowlist entry — add them to "
        f"_ALLOWED_REMOVALS under the phase that removed them, keyed by this exact entry, "
        f"in that phase's own commit:\n" + "\n".join(f"  - {x}" for x in sorted(unlisted))
    )


@pytest.mark.parametrize("key", _KEYS)
def test_the_allowlist_carries_no_stale_entries(
    current: dict[str, dict[str, list[str]]], key: str
) -> None:
    """An entry naming something still present means the allowlist drifted from reality."""
    present = set(current[key]["headings"]) | set(current[key]["executables"])
    stale = _allowed_for(key) & present
    assert not stale, f"{key}: allowlist entries that were never actually removed:\n" + "\n".join(
        f"  - {x}" for x in sorted(stale)
    )


def test_every_allowlist_entry_names_a_known_entry_key() -> None:
    for phase, by_key in _ALLOWED_REMOVALS.items():
        unknown = set(by_key) - set(_KEYS)
        assert not unknown, (
            f"{phase}: unknown entry keys {sorted(unknown)} — the key is "
            f"'<command>@<dev_mode>', not a bare command name"
        )


# ── negative controls — the gate can fail, and the allowlist can excuse ────────


@pytest.mark.parametrize("key", ["verify@spec-driven", "execute@task-driven"])
def test_the_gate_flags_a_deleted_instruction(
    frozen: dict[str, dict[str, list[str]]],
    current: dict[str, dict[str, list[str]]],
    key: str,
) -> None:
    """Invokes `unlisted_removals` — the same function the gate calls — rather than
    re-deriving its expression inline.

    A control that recomputes `set(frozen) - set(current)` itself stays green when the
    gate is mis-wired: inverted subtraction, the allowlist looked up under the wrong key,
    a truncated parametrization. Then the only in-suite evidence for this phase's exit
    criterion certifies a gate that does not work.

    `verify@spec-driven` is deliberately one of the two cases: those instructions render
    only under the config arm this repo does *not* use, and they are inside Phase 1's
    declared scope.
    """
    victim = sorted(frozen[key]["executables"])[0]
    base = unlisted_removals(frozen, current, key, "executables", _allowed_for(key))
    # Without this precondition the arm passes for the wrong reason whenever the victim
    # is already absent: `victim in flagged` would hold with the mutation doing nothing.
    assert victim not in base, f"control broke — {victim} was already missing"
    mutated = {
        k: {kd: [x for x in v[kd] if x != victim] for kd in _KINDS} for k, v in current.items()
    }
    flagged = unlisted_removals(frozen, mutated, key, "executables", _allowed_for(key))
    assert victim in flagged, f"the gate did not flag a deleted instruction: {victim}"


def test_an_allowlisted_removal_is_excused(
    frozen: dict[str, dict[str, list[str]]], current: dict[str, dict[str, list[str]]]
) -> None:
    """The branch every phase from 1 onward actually exercises, and which nothing else
    covers: an allowlist entry must genuinely suppress the failure, or a cutting phase
    can never go green and the gate becomes something to delete rather than to use."""
    key = "verify@spec-driven"
    victim = sorted(frozen[key]["executables"])[0]
    mutated = {
        k: {kd: [x for x in v[kd] if x != victim] for kd in _KINDS} for k, v in current.items()
    }
    allowed = _allowed_for(key)
    base = unlisted_removals(frozen, current, key, "executables", allowed)
    flagged = unlisted_removals(frozen, mutated, key, "executables", allowed)
    assert victim in flagged, "control broke — the deletion was not flagged to begin with"
    excused = unlisted_removals(frozen, mutated, key, "executables", allowed | {victim})
    # Stated as a difference against `base`, not as emptiness: once a cutting phase
    # populates `_ALLOWED_REMOVALS`, an emptiness assertion would fail for reasons that
    # have nothing to do with the property under test.
    assert excused == base, sorted(excused ^ base)
    assert victim not in excused


def test_a_missing_entry_key_is_not_silently_forgiven(
    frozen: dict[str, dict[str, list[str]]],
) -> None:
    """A render that stops emitting a whole command must read as "everything removed",
    not as "nothing to compare" — `.get(key, {})` returning empty is fail-closed."""
    key = "verify@spec-driven"
    flagged = unlisted_removals(frozen, {}, key, "executables", set())
    assert flagged == set(frozen[key]["executables"])
