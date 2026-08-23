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
# Telemetry and payloads have DIFFERENT writers with DIFFERENT roots, and this gate
# correlates the two — so each side must be read the way its own writer files it.
# `review_telemetry emit` writes cwd-relative (this checkout); `stage_agent_ledger
# persist-payload` writes to the base repo on purpose, so rows survive `task-land`.
_OBS = _REPO / ".claude" / "observability"


def _payloads_dir() -> Path:
    """Resolved the WRITER's way — the base repo, not this checkout.

    `stage_agent_ledger persist-payload` files at the base root deliberately, so rows
    survive `task-land`. Rooting the reader at `_REPO` instead meant that running from a
    task worktree the gate looked in `<worktree>/.claude/observability/review-payloads`,
    which does not exist, and reported "no persisted payload" for a round whose payload
    had just been written one level up. That is the exact failure `_ledger()`'s docstring
    below describes for the telemetry half — fixed there, missed here, one line apart.
    """
    from harness_maker.mutation_receipt import _base_root

    return _base_root(_REPO) / ".claude" / "observability" / "review-payloads"


#: The persist step landed in the source templates on this date. Rounds before it could not
#: have complied — the instruction did not exist — so they are an era, not an exemption.
_STEP_LANDED = "2026-08-05"

#: (slug, round) pairs that ran on or after the cutoff WITHOUT persisting. Each needs a
#: reason. Adding an entry is the visible cost of skipping the step; removing one is free.
_KNOWN_MISSING: dict[tuple[str, int], str] = {
    ("probe-envelope-contract", 2): (
        "Round 2 dispatched no reviewers, so there was no merged payload to capture. The "
        "auto-fix loop's churn gate skipped the re-review (`review_consensus plan` returned an "
        "empty `dispatches` with reason `churn 0.07 < 0.30`), and Step 3.4's persist-payload "
        "line sits after a merge that never happened. The round is visible to this gate only "
        "because the TERMINAL telemetry row numbers it — the same round-axis disagreement the "
        "`review-loop-ledger-fixes` entry above records for a confirmation pass, reached by a "
        "second route. Round 1 DID dispatch all seven lenses and its per-lens captures are on "
        "disk under `.claude/observability/.hm-lens-results/probe-envelope-contract/"
        "c488271901e1/1/`; its merged payload was NOT persisted, and this gate cannot see that "
        "because no round-1 telemetry row was emitted either — the gate's population is the "
        "telemetry rows, so a skipped row hides a skipped payload. That hole is the honest "
        "finding here and is recorded in `[fail:design] per-round-step-runs-only-in-round-1` "
        "(count 2). Nothing was reconstructed to clear this."
    ),
    ("review-loop-ledger-fixes", 3): (
        "There was no round 3 to capture. This slug's first /hm:review ran two rounds and "
        "then two CONFIRMATION passes, and the confirmation pass writes its lens results "
        "under a `confirm-1`/`confirm-2` pass-id directory, not a round number — Step 3.4's "
        "persist-payload is a per-ROUND line in the auto-fix loop and never fires for a pass. "
        "The `round: 3` the gate sees comes from the terminal telemetry row, which numbers "
        "the confirm-2 state so the ledger has one row per review; the two numbering schemes "
        "meet only there. Reconstructing a payload would fabricate a round that never "
        "dispatched, which is the non-capture this corpus exists to exclude. The confirm-2 "
        "findings, their dispositions and the five surviving P1s are in "
        "REVIEW-review-loop-ledger-fixes-2026-08-20.md; rounds 1 and 2 of that review, and "
        "round 1 of the second review, did persist. What this entry actually records is that "
        "the telemetry row's round axis and the payload corpus's round axis disagree for any "
        "review that reaches a confirmation pass — a gate-visible seam, not an orchestrator "
        "lapse, and the third distinct cause on this list."
    ),
    ("plan-interview-comprehension", 2): (
        "round 1 of this slug WAS re-captured rather than waived: the original /hm:review "
        "skipped Step 3.4 entirely, and when this gate surfaced it at wrapup the operator "
        "chose to re-run the review properly, so "
        "20260813T0700Z-round1-merged.json is a genuine capture (it found a P0 the first "
        "pass had missed — the golden's own durability check was pinned to `merge-base`, "
        "which returns HEAD once the branch lands, so it would have gone red on the very "
        "commit that shipped it). Round 2 cannot be recovered the same way and is recorded "
        "as missing: the re-run converged in a single round, because the round-2 findings "
        "had already been fixed. Manufacturing a second round purely to produce a file "
        "would be a round run for the gate rather than for the code — the exact non-capture "
        "this corpus exists to exclude. The round-2 findings, their tags and dispositions "
        "survive in REVIEW-plan-interview-comprehension-2026-08-13.md; what is lost is the "
        "replayable payload. This is the sixth slug to miss this line, and the fourth in a "
        "row; the entries above already conclude that is evidence about the step's "
        "placement rather than about the orchestrators — this one adds that a round-1-only "
        "recovery is possible while a later-round one is not, which is an argument for "
        "persisting at merge time rather than as a numbered step the round can skip."
    ),
    ("lens-and-review-fix-verification", 3): (
        "round 1 persisted (ea8087ff-20260817T0757Z-round1-merged.json) because the "
        "orchestrator ran Step 3.4 there; rounds 2 and 3 did not, and the round-3 merged "
        "voter state existed only in the orchestrator's context. `consensus.json` in the "
        "session scratchpad is round 1's payload, byte-identical to the persisted file; the "
        "only round-3 artifact that survives is `review_consensus finalize`'s 568-byte grade "
        "output, which is a verdict and not a findings payload. Building one now would be "
        "the manufactured non-capture the entry above rejects, and the precedent there is "
        "explicit that re-running a converged review to produce a file is a round run for "
        "the gate rather than for the code. Recorded as missing instead. Two adjacent gaps "
        "this gate structurally cannot see, both from the same run and both worth more than "
        "this waiver: round 2 emitted NO telemetry row at all (the gate only inspects rounds "
        "that appear in the ledger, so a round that never reported is invisible to it), and "
        "BOTH emitted rows carry `terminal: true` though only round 3 was terminal. With the "
        "four `churn_*` keys absent from every row in this repository and three others, that "
        "is four independent defects in one LLM-assembled record — the argument for moving "
        "the producer from prose into the CLI, not for a better-worded instruction."
    ),
    ("second-opinion-oracle-polyglot", 1): (
        "the orchestrator ran Pass 1, the cross-model voters and the consensus filter but "
        "skipped Step 3.4 entirely — neither `codex_adapter stamp-ids` nor persist-payload. "
        "The merged findings existed only in the orchestrator's context and were never written "
        "to a temp file, so there is no capture. Reconstructing one from "
        "REVIEW-second-opinion-oracle-polyglot-2026-08-10.md would be a post-hoc narrative "
        "entry in a corpus whose entire value is that its entries are captures — the one thing "
        "this gate's own message forbids. Recorded as missing. The findings themselves, their "
        "consensus tags and the codex ids survive in that REVIEW document; what is lost is the "
        "replayable per-round payload. This is the third consecutive slug to miss the same "
        "line, which is evidence about the step's placement, not about three orchestrators."
    ),
    ("second-opinion-oracle-polyglot", 2): (
        "same run as round 1 above — round 2 was the auto-fix iteration, whose findings list is "
        "the round-1 list minus what the fixes resolved. No separate capture was taken."
    ),
    ("workflow-time-token-savings", 3): (
        "Step 3.4's persist-payload was never run for any round of this review — the merged "
        "findings existed only in the orchestrator's context, so there is no capture to write. "
        "Reconstructing one from REVIEW-workflow-time-token-savings-2026-08-09.md would be a "
        "post-hoc entry in a corpus whose value is that its entries are captures, which this "
        "test's own message forbids. Recorded as missing. The round-3 findings themselves are "
        "in that REVIEW document; what is lost is the replayable per-round payload."
    ),
    ("workflow-loop-efficiency", 3): (
        "ran on the installed harness whose rendered review stage predated the persist "
        "line — the step was in source but not in the command that executed"
    ),
    ("antigravity-second-opinion-timeout", 1): (
        "the orchestrator ran the merge and the consensus filter but skipped the Step 3.4 "
        "persist-payload line; this gate is what surfaced the omission, one round later. "
        "The round-1 findings survive in REVIEW-antigravity-second-opinion-timeout-2026-08-08.md, "
        "but writing them out now would be a reconstruction from narrative, not a capture — "
        "the one thing this gate's own message forbids. Recorded as missing instead."
    ),
    **{
        ("multi-lens-review-round", n): (
            "round 1 persisted; the auto-fix rounds 2-4 ran the merge and the fixes but never "
            "the Step 3.4 persist-payload line. The findings themselves survive in "
            "REVIEW-multi-lens-review-round-2026-08-10.md (13 in round 3, with per-round "
            "attribution of which were fix-induced), but the merged payloads lived only in the "
            "orchestrator's context and are gone — writing them out now would be a "
            "reconstruction from narrative, which this gate's own message forbids. Recorded as "
            "missing. NOTE the shape: the step is written once, under 'Round 1', and rounds 2..N "
            "are described elsewhere as re-reading frozen state — so the orchestrator reads the "
            "persist line as a round-1 step. That is the fifth instance of this exact omission "
            "in this allowlist, which makes it a template defect rather than five operator "
            "lapses; tracked as [fail:process] per-round-step-runs-only-in-round-1."
        )
        for n in (2, 3, 4)
    },
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
    return any(_payloads_dir().glob(f"{slug}/*-round{round_n}-*.json"))


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
