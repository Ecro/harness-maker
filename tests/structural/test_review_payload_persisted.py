"""Every review round from the cutoff on must have persisted its finding payload.

The persist step (ADR-006 part 2) is one line in the review stage's prose, and prose is
skippable. It was skipped on the very first review run after it shipped, and **nothing
noticed** — the round completed, the telemetry row was written, the grade was reported, and
the corpus stayed empty. A one-off manual backfill does not stop the next skip; this does.

**Why an allowlist and not a date.** A date cutoff silently forgives anything backdated, and
it would have let the author's own two misses disappear into "history". Each exemption is
named here with its reason, so the list is auditable and can only shrink. The date below is
used ONLY for the era in which the step did not exist, where compliance was impossible
rather than skipped.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]
_OBS = _REPO / ".claude" / "observability"
_PAYLOADS = _OBS / "review-payloads"

#: The persist step landed in the source templates on this date. Rounds before it could not
#: have complied — the instruction did not exist — so they are an era, not an exemption.
_STEP_LANDED = "2026-08-05"

#: (slug, round) pairs that ran on or after the cutoff WITHOUT persisting. Each needs a
#: reason. Adding an entry is the visible cost of skipping the step; removing one is free.
_KNOWN_MISSING: dict[tuple[str, int], str] = {
    ("workflow-loop-efficiency", 3): (
        "ran on the installed harness whose rendered review stage predated the persist "
        "line — the step was in source but not in the command that executed"
    ),
    ("validator-pass-cap-telemetry", 2): (
        "the auto-fix round was run and the persist step was skipped. Its findings are in "
        "REVIEW-validator-pass-cap-telemetry-2026-08-07.md, but reconstructing a payload "
        "from them now would put a SECOND post-hoc entry in a corpus whose value depends on "
        "entries being captures. Recorded as missing instead."
    ),
    **{
        ("mechanical-guards-from-backlog", n): (
            "all three rounds ran the merge and the id-stamp but never the Step 3.4 "
            "persist-payload line; the merged temp files were deleted with the rounds, so "
            "nothing survives to persist. Reconstructing from the REVIEW narrative would "
            "produce a post-hoc entry, which this corpus explicitly does not want. This "
            "gate landed on main WHILE that review was running and caught it on the "
            "rebase — the first time the step's absence was visible to anything."
        )
        for n in (1, 2, 3)
    },
}


def _telemetry_rounds() -> list[tuple[str, int, str]]:
    out: list[tuple[str, int, str]] = []
    for path in sorted(_OBS.glob("review-*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if isinstance(row, dict) and {"slug", "round", "ts"} <= row.keys():
                out.append((str(row["slug"]), int(row["round"]), str(row["ts"])))
    return out


def _has_payload(slug: str, round_n: int) -> bool:
    return any(_PAYLOADS.glob(f"{slug}/*-round{round_n}-*.json"))


def test_the_telemetry_is_readable() -> None:
    """Positive control, and the record of this gate's real scope.

    It asserted `>= 1` row and went red in CI on the first run, correctly: `review-*.jsonl`
    is churn and therefore gitignored, so a fresh clone has NO rows and there is nothing to
    correlate. **This gate cannot bind in CI** — it binds on the machine that holds the
    ledger, which is also the machine where a review runs and where the skip happens. That
    is a real limit, not a formality, and it is stated here rather than hidden behind a
    quiet skip.

    (Third instance in one day of `[fail:test] local-state-hides-fresh-clone-failure`, and
    the second AFTER that entry was written — checking locally is not evidence for any check
    that reads repository or observability state.)
    """
    rows = _telemetry_rounds()
    if not rows:
        pytest.skip(
            "no review telemetry in this checkout — the ledger is gitignored churn, so this "
            "gate only binds where reviews actually run (never in CI)"
        )
    assert rows


def test_every_round_since_the_step_landed_persisted_its_payload() -> None:
    """The gate. A skipped persist is now a red test naming the round that skipped it."""
    missing = [
        (slug, rnd, ts)
        for slug, rnd, ts in _telemetry_rounds()
        if ts >= _STEP_LANDED and (slug, rnd) not in _KNOWN_MISSING and not _has_payload(slug, rnd)
    ]
    assert not missing, (
        "review rounds with no persisted payload:\n"
        + "\n".join(f"  {slug} round {rnd} ({ts})" for slug, rnd, ts in missing)
        + "\n\nRun the Step 3.4 `stage_agent_ledger persist-payload` line for that round, or "
        "add it to _KNOWN_MISSING with a reason. Do NOT reconstruct a payload after the "
        "fact to clear this — the corpus is only useful if its entries are captures."
    )


def test_the_exemption_list_does_not_rot() -> None:
    """An entry naming a round that DID persist is a stale exemption hiding future skips."""
    stale = [k for k in _KNOWN_MISSING if _has_payload(*k)]
    assert not stale, f"exemptions for rounds that now have payloads: {stale}"


def test_every_exemption_carries_a_reason() -> None:
    """A bare exemption is indistinguishable from a forgotten one."""
    for key, reason in _KNOWN_MISSING.items():
        assert len(reason.strip()) > 40, f"{key}: reason is too thin to audit"
