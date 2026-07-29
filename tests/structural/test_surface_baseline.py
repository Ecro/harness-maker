"""Phase 0 — the frozen shipped-surface baseline and the generator that produced it.

PLAN-workflow-step-audit Phase 0's exit criterion is not "a file exists". It is that the
file **parses**, is **non-empty**, carries the **render SHA**, and was produced by the
**committed generator** — the same generator Phase 6 re-invokes, so both sides compute
the identical quantity. A bare ``… > <file>`` redirection is explicitly not acceptable
evidence: the shell creates the file even when the command errors, so a well-shaped file
full of zeros would satisfy a mere-existence check and then make Phase 0.5's aggregate
arm and Phase 6's comparison subtract against nothing — a permanently-passing ratchet.

Four properties, each aimed at a different way the baseline can be wrong, and each
chosen to keep binding after HEAD moves past Phase 0 (values legitimately drift as later
phases cut; nothing below depends on them not drifting):

* **the committed numbers are real** — asserted on ``doc["surface"]`` itself, never on a
  live render. This is the arm the reviewer's first blocking issue was about: the file's
  positive controls previously all pointed at the live generator output, so no assertion
  ever read an integer out of the artifact.
* **the numbers came from the generator** — a ``payload_digest`` over the canonical
  ``surface`` JSON. Set-equality on variants and command names does not diverge when
  someone edits ``chars: 121782`` to ``chars: 99999``; the digest does.
* **the generator is portable on its own** — exercised through a **subprocess**, with
  pytest's autouse pin deliberately out of scope. ``tests/structural/conftest.py``
  monkeypatches ``synthesize._compute_install_ref`` for every test in this directory, so
  an in-process portability assertion measures the fixture, not the generator — and the
  generator is the thing that actually writes the artifact, standalone.
* **the counting rule that travels with the numbers is the rule that produced them** —
  named tokens plus a round-trip of the counter over a synthetic text with known counts.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from ._surface_baseline import (
    BASELINE_PATH,
    CLAUDE_VARIANT,
    CODEX_VARIANT,
    COUNTING_RULE,
    build_baseline,
    count_round_trips,
    load_baseline,
    measure_surface,
    payload_digest,
)
from .conftest import pin_install_ref

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SHA = re.compile(r"^[0-9a-f]{40}$")


@pytest.fixture(scope="module")
def measured() -> dict[str, dict[str, dict[str, int]]]:
    """The pin is applied HERE, not left to the autouse fixture.

    A module-scoped fixture is set up before any function-scoped autouse fixture runs
    (`conftest.py:30-37`, `test_command_size_budget.py:113-117`), so without this the
    render backing every comparison below would be unpinned while a sibling test asserts
    the render is pinned — two assertions that cannot both describe the same measurement.
    """
    with pytest.MonkeyPatch.context() as mp:
        pin_install_ref(mp)
        return measure_surface()


@pytest.fixture(scope="module")
def frozen() -> dict[str, object]:
    return load_baseline()


# ── the committed file parses, and its numbers are real ────────────────────────


def test_baseline_exists_parses_and_is_non_empty(frozen: dict[str, object]) -> None:
    assert BASELINE_PATH.exists(), f"Phase 0 baseline missing: {BASELINE_PATH}"
    raw = BASELINE_PATH.read_text(encoding="utf-8")
    assert raw.strip(), "baseline is empty — a redirection that captured a failed command"
    assert json.loads(raw) == frozen
    assert frozen["surface"], "baseline carries no measurements"


def test_the_committed_numbers_are_not_zeros(frozen: dict[str, object]) -> None:
    """The arm that makes `… > <file>` unusable as evidence.

    Every assertion here reads the **artifact**, so a baseline that is well-shaped but
    measured nothing fails — which is the state a redirected-over-a-failed-command file
    is actually in. The concrete floors are anchored to today's render (verify: 13 `!`
    lines in the Claude command, 12 `Bash(` call sites in the Codex skill) and stated
    well below it, so they survive this PLAN's own cuts without going vacuous.
    """
    surface = frozen["surface"]
    assert isinstance(surface, dict)
    entries = [(v, n, e) for v, cmds in surface.items() for n, e in cmds.items()]
    assert len(entries) >= 25, f"only {len(entries)} commands measured"
    for variant, name, entry in entries:
        assert isinstance(entry["chars"], int), (variant, name, entry)
        assert entry["chars"] > 0, (variant, name, entry)
        # No per-entry `> 0` floor on round_trips: `help` and the Codex stage-trigger
        # skills legitimately mandate none. `>= 0` would be vacuous — a counter cannot
        # be negative — so the real floor is the corpus sum below.
        assert isinstance(entry["round_trips"], int), (variant, name, entry)
    assert sum(e["round_trips"] for _, _, e in entries) >= 100, "the counting rule found nothing"
    assert surface[CLAUDE_VARIANT]["verify"]["round_trips"] >= 4
    assert surface[CLAUDE_VARIANT]["verify"]["chars"] > 10_000
    assert surface[CODEX_VARIANT]["hm-verify"]["round_trips"] >= 4
    aggregate = frozen["aggregate_chars"]
    assert isinstance(aggregate, dict)
    for variant, cmds in surface.items():
        assert aggregate[variant] == sum(e["chars"] for e in cmds.values()), variant


def test_baseline_carries_a_render_sha_that_is_a_real_commit(frozen: dict[str, object]) -> None:
    """Checked against the object database: a fabricated 40-hex string pins nothing.

    `assert_sha_is_durable` refuses at freeze time to record a SHA that a squash-land
    would delete, so this stays satisfiable in CI after the task branch is gone.
    """
    sha = frozen["render_sha"]
    assert isinstance(sha, str), f"render_sha is not a string: {sha!r}"
    assert _SHA.match(sha), f"render_sha is not a full SHA: {sha!r}"
    proc = subprocess.run(
        ["git", "cat-file", "-e", f"{sha}^{{commit}}"],
        cwd=_REPO_ROOT,
        capture_output=True,
        timeout=30,
    )
    assert proc.returncode == 0, f"render_sha {sha} is not a commit in this repo"


# ── the numbers came from the generator ────────────────────────────────────────


def test_the_committed_numbers_carry_the_generators_digest(frozen: dict[str, object]) -> None:
    """A narrowing arm against careless hand-edits, and nothing more.

    sha256 over the payload is recomputable by anyone editing the file, so this proves
    **self-consistency, not authorship** — it must not be cited in Phase 6 as evidence
    that the committed generator produced these numbers. That claim is carried by
    `test_the_generator_reproduces_the_committed_baseline_across_processes`. What this
    does catch, and the set-equality arm does not, is an edit that changes a value while
    preserving every key.
    """
    surface = frozen["surface"]
    assert isinstance(surface, dict)
    assert frozen["payload_digest"] == payload_digest(surface), (
        "the committed surface does not hash to its recorded digest — a value was "
        "edited without regenerating"
    )


def test_baseline_shape_matches_the_generator(
    frozen: dict[str, object], measured: dict[str, dict[str, dict[str, int]]]
) -> None:
    """Narrowing arm — a generator that stops measuring a variant or a command diverges
    here, which is the failure that would silently shrink Phase 6's aggregate."""
    surface = frozen["surface"]
    assert isinstance(surface, dict)
    assert set(surface) == set(measured), "variant set drifted from the generator"
    for variant, commands in measured.items():
        assert set(surface[variant]) == set(commands), f"{variant}: command set drifted"
        for name, entry in surface[variant].items():
            assert set(entry) == set(commands[name]), f"{variant}/{name}: metric set drifted"


def test_build_baseline_emits_the_documented_envelope() -> None:
    with pytest.MonkeyPatch.context() as mp:
        pin_install_ref(mp)
        doc = build_baseline()
    assert doc["generated_by"] == "tests/structural/_surface_baseline.py"
    assert _SHA.match(doc["render_sha"])
    assert set(doc) == {
        "schema_version",
        "generated_by",
        "render_sha",
        "counting_rule",
        "payload_digest",
        "aggregate_chars",
        "surface",
    }
    # Deliberately NOT `doc["payload_digest"] == payload_digest(doc["surface"])` — that
    # re-executes the very expression `build_baseline` used to set the key and cannot
    # fail. The digest is checked against the committed artifact instead, above.


# ── the generator is portable and reproducible ON ITS OWN ──────────────────────


@pytest.fixture(scope="module")
def standalone_payload() -> dict[str, object]:
    """Invoke the committed generator the way it is actually run to produce the artifact.

    A subprocess is the point, not an implementation detail: `conftest.py`'s autouse
    fixture pins `synthesize._compute_install_ref` for every test in this directory, so
    any in-process check of "the render carries no machine path" asserts a property the
    fixture injected. Only a process without that fixture can tell whether the generator
    pins itself — and if it does not, the committed numbers are a measurement of *this
    checkout's path*, wrong in CI and in base. That is `[fail:test]
    snapshot-regen-inside-worktree`, whose count is already 13.
    """
    inherited = os.environ.get("PYTHONPATH", "")
    env = {
        **os.environ,
        "PYTHONPATH": os.pathsep.join(p for p in (str(_REPO_ROOT), inherited) if p),
    }
    proc = subprocess.run(
        [sys.executable, "-m", "tests.structural._surface_baseline", "--print"],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        env=env,
        timeout=600,
    )
    assert proc.returncode == 0, f"generator failed standalone:\n{proc.stderr[-2000:]}"
    doc: dict[str, object] = json.loads(proc.stdout)
    return doc


def test_the_generator_pins_its_own_install_ref(
    standalone_payload: dict[str, object], measured: dict[str, dict[str, dict[str, int]]]
) -> None:
    """Compares the *un-pinned-by-pytest* subprocess against the explicitly pinned
    in-process render — which is the only thing that discriminates a self-pinning
    generator from one that has stopped pinning.

    Grepping the emitted payload for a machine path could not do this job, and the
    earlier revision of this test that did so was a tautology twice over: the payload
    carries only ints, hex digests, fixed strings and command stems — no rendered text —
    and `synthesize._portablize_ref` rewrites `/home/noel/…` to `$HOME/…` before the ref
    ever reaches the render, so a `/home/` pattern matches nothing even in principle.
    The install ref reaches the render as `harness_maker_src_path`, so what an unpinned
    run actually moves is the **character counts** — a longer worktree path makes every
    `chars` larger. That is what this equality catches, and it needs no committed
    artifact, so it stays independent of
    `test_the_generator_reproduces_the_committed_baseline_across_processes`.
    """
    assert standalone_payload["surface"] == measured, (
        "the standalone generator disagrees with the explicitly pinned in-process render "
        "— it is no longer pinning its own install ref, so the numbers it freezes are a "
        "measurement of the path it ran from ([fail:test] snapshot-regen-inside-worktree)"
    )


def test_the_standalone_generator_agrees_with_the_baseline_in_shape_and_direction(
    standalone_payload: dict[str, object], frozen: dict[str, object]
) -> None:
    """Exact equality to the frozen surface is **not** the contract, and asserting it was
    a design error in the first cut of this file.

    This PLAN's entire purpose is to make the render smaller, so an equality arm goes red
    on the first legitimate cut and can then only be satisfied by re-freezing — which
    ADR-011 forbids once a phase has cut. The arm would have converted the ratchet into a
    freeze.

    What must hold across processes is the **shape** (same variants, same commands) and
    the **ratchet direction** (no variant's total grew against the frozen baseline).
    Cross-process determinism of the measurement itself is asserted by
    `test_the_generator_pins_its_own_install_ref`, which compares the subprocess against
    the in-process render rather than against a file that is expected to age.
    """
    live = standalone_payload["surface"]
    base = frozen["surface"]
    assert isinstance(live, dict)
    assert isinstance(base, dict)
    assert set(live) == set(base), "variant set drifted across processes"
    for variant, commands in base.items():
        missing = set(commands) - set(live[variant])
        assert not missing, f"{variant}: commands vanished from the render: {sorted(missing)}"
        now = sum(live[variant][name]["chars"] for name in commands)
        was = frozen["aggregate_chars"][variant]  # type: ignore[index]
        assert now <= was, f"{variant}: shipped surface grew {now - was} chars ({was} → {now})"


def test_the_generator_is_deterministic_in_process(
    measured: dict[str, dict[str, dict[str, int]]],
) -> None:
    with pytest.MonkeyPatch.context() as mp:
        pin_install_ref(mp)
        assert measure_surface() == measured


# ── the recorded counting rule is the rule that was applied ────────────────────


def test_the_recorded_counting_rule_names_its_three_tokens(frozen: dict[str, object]) -> None:
    """ADR-011 states the rule concretely; a non-empty string describing a *different*
    rule is exactly the drift that makes the Phase 0 and Phase 6 sides incomparable."""
    rule = frozen["counting_rule"]
    assert isinstance(rule, str)
    assert rule == COUNTING_RULE, "the frozen rule drifted from the module constant"
    for token in ("^!", "Bash(", "Task("):
        assert token in rule, f"counting rule does not name {token!r}"


def test_the_counter_implements_the_rule_it_records() -> None:
    """Round-trips the counter over a text with known counts, including inside a fence —
    ADR-011's rule counts fenced examples on purpose, and a fence-aware counter would
    return 0 against the shipped templates and assert nothing."""
    text = "\n".join(
        [
            "prose",
            "!first --real",
            "```bash",
            "!second --inside-a-fence",
            "```",
            "  !third --indented",
            "Bash(x) and Bash(y)",
            "Task(subagent_type='x')",
        ]
    )
    assert count_round_trips(text, CLAUDE_VARIANT) == 3 + 1
    assert count_round_trips(text, CODEX_VARIANT) == 2 + 1
    with pytest.raises(ValueError, match="unknown target variant"):
        count_round_trips(text, "cursor")


def test_chars_is_characters_not_bytes(measured: dict[str, dict[str, dict[str, int]]]) -> None:
    """`test_command_size_budget.py:3-6` records that an earlier revision said "bytes"
    and was wrong: these renders carry —, ≥ and ✅, so `wc -c` and `len()` disagree and
    only one of them is what a model's context sees."""
    with pytest.MonkeyPatch.context() as mp:
        pin_install_ref(mp)
        from ._surface_baseline import render_surface

        rendered = render_surface()
    text = rendered[CLAUDE_VARIANT]["verify"]
    assert len(text.encode("utf-8")) > len(text), "fixture is pure ASCII — the arm is vacuous"
    assert measured[CLAUDE_VARIANT]["verify"]["chars"] == len(text)


# ── positive controls ──────────────────────────────────────────────────────────


def test_the_generator_measured_both_target_variants(
    measured: dict[str, dict[str, dict[str, int]]],
) -> None:
    """`.cursor/commands/` is dead code in `render.py` (:571-582 — no template feeds it),
    so Cursor reads the Claude render and there are exactly two distinct artifacts."""
    assert set(measured) == {CLAUDE_VARIANT, CODEX_VARIANT}
    assert len(measured[CLAUDE_VARIANT]) >= 15, "Claude render produced too few commands"
    assert len(measured[CODEX_VARIANT]) >= 10, "Codex render produced too few stage skills"
