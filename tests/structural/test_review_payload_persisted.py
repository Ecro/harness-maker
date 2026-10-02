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
import sys
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
#:
#: Churn-skipped rounds are not listed: the gate excludes them itself (`_churn_skipped`).
#: Two slugs whose terminal round was churn-skipped also skipped Step 3.4 on EVERY round that
#: dispatched, and those rounds emitted no telemetry row, so the gate cannot see them:
#: `mutation-survivors-and-approval-p2s` (run efae9d5dd1a9) and `withdrawal-criterion-window`
#: (run aeb96c3b0764). No copy survives on disk; nothing was reconstructed (2026-09-27 sweep).
_KNOWN_MISSING: dict[tuple[str, int], str] = {
    ("objective-gap-proposal", 2): (
        "Round 2 dispatched no reviewers: the churn gate skipped the re-review "
        "(`review_consensus plan` → empty `dispatches`, `churn < 0.30`), so no merged payload "
        "existed to capture — Step 3.4's persist line sits after a merge that never happened, "
        "the `probe-envelope-contract` shape above. Round 1's merged payload IS on disk "
        "(`objective-gap-proposal/<run>-round1-merged.json`). Two telemetry rows number the "
        "round (the terminal row plus the post-review-fix row of 2026-09-16), which is why the "
        "gate lists it twice. Nothing was reconstructed to clear this (`[fail:design] "
        "per-round-step-runs-only-in-round-1`)."
    ),
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
    ("render-observability-audit", 2): (
        "Operator error, not a structural impossibility — and unlike the two entries below, "
        "this round DID dispatch. The churn gate measured 1.00 and `review_consensus plan` "
        "returned a real dispatch (`code-reviewer`/`functionality`), which ran and returned "
        "findings. Step 3.4's persist-payload line simply was never invoked, and the merged "
        "findings temp file was not retained afterwards, so no capture exists to write. "
        "Reconstructing one now would fabricate a capture, which is the non-capture this "
        "corpus exists to exclude, so nothing was reconstructed. Round 1 is invisible to this "
        "gate for the reason the `probe-envelope-contract` entry already records: the gate's "
        "population is the telemetry rows, and only ONE terminal row was emitted for this "
        "review instead of one per round, so a skipped row hid a skipped payload. That makes "
        "this instance 3 of `[fail:design] per-round-step-runs-only-in-round-1` — the same "
        "class, reached by neither of the two routes already documented here."
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
    ("assumption-entry-and-evidence-locator", 3): (
        "the terminal telemetry row numbers a round that has no merged payload of its own — the "
        "round-axis disagreement recorded above: the review's later work was a confirmation "
        "pass or a churn-skipped re-review, which write lens files under a pass-id directory or "
        "nothing at all, never a `round<N>-merged.json`. Earlier rounds of the slug did "
        "persist. Recorded in the 2026-09-27 sweep from the telemetry rows and the corpus; "
        "nothing reconstructed."
    ),
    ("codex-plan-integration-repair", 1): (
        "no merged payload was persisted for ANY round of this slug (run 692c4c590fe5): the "
        "review ran — its REVIEW document and telemetry exist — but the Step 3.4 persist line "
        "was skipped throughout, and no copy survives anywhere on disk. Recorded in the "
        "2026-09-27 sweep; reconstructing from the REVIEW narrative would put post-hoc entries "
        "in a corpus of captures."
    ),
    ("understanding-handoff", 3): (
        "the confirm-1 repair round. Its findings came from the confirm-1 pass, which writes "
        "lens files under `confirm-1/`, not a merged payload, and the terminal telemetry row "
        "numbers the round 3. A payload reconstructed from those findings was committed in "
        "67faab2c to clear this gate and removed the next commit: a reconstruction is exactly "
        "what this corpus excludes, whatever its content."
    ),
    ("intent-feedback-continuity", 4): (
        "no round 4 dispatched in either run. Runs 01263f044f17 and 4ddd6e47b02f both ended on "
        "'Confirmation pass 2 — terminal' (REVIEW-intent-feedback-continuity-2026-09-28.md and "
        "its -rerun), and the terminal telemetry row numbers that pass round 4: the round-axis "
        "disagreement the `review-loop-ledger-fixes` entry records. The first run's round 2 was "
        "churn-skipped (0.077 < 0.30). Both runs' round 1 persisted. Recorded in the 2026-09-29 "
        "sweep; nothing reconstructed."
    ),
}


def _churn_skip_threshold() -> float | None:
    """Below this churn the loop skips the re-review, so the round has no payload to persist.

    Half the exemption list used to be this one shape, each entry hand-written after the gate
    went red on a round that by construction dispatched nothing. The row records the measured
    `churn_ratio` but not the threshold it was compared to, so the threshold comes from the
    live config; a review run under a different threshold still needs an explicit exemption.
    `None` = the gate is off and every repair round re-reviews.
    """
    from harness_maker.io_utils import load_harness_yaml
    from harness_maker.review_churn import churn_gate_enabled, resolve_churn_threshold

    reviewers = load_harness_yaml(_REPO / ".claude" / "harness.yaml").get("reviewers") or {}
    return resolve_churn_threshold(reviewers) if churn_gate_enabled(reviewers) else None


def _churn_skipped(churn: float | None) -> bool:
    threshold = _churn_skip_threshold()
    return threshold is not None and churn is not None and churn < threshold


def _telemetry_rounds() -> list[tuple[str, int, str, float | None]]:
    out: list[tuple[str, int, str, float | None]] = []
    for path in sorted(_OBS.glob("review-*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if isinstance(row, dict) and {"slug", "round", "ts"} <= row.keys():
                churn = row.get("churn_ratio")
                out.append(
                    (
                        str(row["slug"]),
                        int(row["round"]),
                        str(row["ts"]),
                        float(churn) if isinstance(churn, (int, float)) else None,
                    )
                )
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
    """The gate. A skipped persist is now a red test naming the round that skipped it.

    A churn-skipped round is out of scope: no reviewer ran, so there was no merged payload to
    persist. A round that DID dispatch (churn at or above the threshold) and skipped the persist
    line is still caught — `render-observability-audit` round 2 is that case.
    """
    missing = [
        (slug, rnd, ts)
        for slug, rnd, ts, churn in _telemetry_rounds()
        if ts >= _STEP_LANDED
        and not _churn_skipped(churn)
        and (slug, rnd) not in _KNOWN_MISSING
        and not _has_payload(slug, rnd)
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


def test_the_churn_rule_exempts_only_skipped_rounds(monkeypatch: pytest.MonkeyPatch) -> None:
    """Negative control on synthetic rows, so it binds in CI where the ledger is absent.

    Without it the exclusion could swallow a dispatched round that skipped its persist — the
    one miss this gate exists for — and every real-ledger run would still be green.
    """
    threshold = _churn_skip_threshold()
    if threshold is None:
        pytest.skip("rereview_churn_gate is off — no round is churn-skipped")
    rows = [
        ("zz-skipped", 2, "2099-01-01T00:00:00Z", threshold / 2),
        ("zz-dispatched", 2, "2099-01-01T00:00:00Z", threshold),
        ("zz-unmeasured", 2, "2099-01-01T00:00:00Z", None),
    ]
    monkeypatch.setattr(sys.modules[__name__], "_telemetry_rounds", lambda: rows)
    with pytest.raises(AssertionError) as caught:
        test_every_round_since_the_step_landed_persisted_its_payload()
    msg = str(caught.value)
    assert "zz-dispatched round 2" in msg
    assert "zz-unmeasured round 2" in msg
    assert "zz-skipped" not in msg


def test_no_exemption_duplicates_the_churn_skip_rule() -> None:
    """An entry the rule already covers is noise that makes the real waivers harder to audit."""
    rows: dict[tuple[str, int], list[float | None]] = {}
    for slug, rnd, _ts, churn in _telemetry_rounds():
        rows.setdefault((slug, rnd), []).append(churn)
    redundant = [k for k in _KNOWN_MISSING if k in rows and all(_churn_skipped(c) for c in rows[k])]
    assert not redundant, f"exemptions the churn-skip rule already covers: {redundant}"


def test_every_exemption_carries_a_reason() -> None:
    """A bare exemption is indistinguishable from a forgotten one."""
    for key, reason in _KNOWN_MISSING.items():
        assert len(reason.strip()) > 40, f"{key}: reason is too thin to audit"
