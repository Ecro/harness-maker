---
type: review
task_slug: mutation-survivors-and-approval-p2s
status: CHANGES_REQUESTED
created: 2026-09-20
reviewers_invoked: [code-reviewer, security-reviewer, concurrency-reviewer, test-reviewer, codex]
consensus_method: cross-check
run_id: efae9d5dd1a9
review_base: a950a22c2ccf5e3ea21424c658b446e1530af97b
drift_verdict:
  result: scope_violation
  scope_violations:
    - src/harness_maker/worktree.py
  scenario_misses: []
  task_slug: mutation-survivors-and-approval-p2s
  computed_at: 2026-09-20T03:40:00Z
---

# REVIEW: mutation-survivors-and-approval-p2s

## 🎯 Round 1 Summary

Grade after round 1: **B** (2 consensus-passed P1). Grade after the round-2 repairs: **A**.
Grade after the terminal confirmation pass: **B** — the pass found new severe findings, so the
review ends `CHANGES_REQUESTED` rather than approving.

Seven lens-dispatches over two rounds and two confirmation passes, plus one Codex invocation
at round 1. Every lens exercised in every pass.

## 🔍 Drift Findings

**P1 — scope violation: `src/harness_maker/worktree.py`.** No PLAN phase names it. The change
adds `"MUTATION"` to `DELIVERABLE_PREFIXES`, closing a regression this author shipped in
`865e3ef5`: `.gitignore` gained `!work-docs/MUTATION-*.md` without the matching source entry,
and `tests/structural/test_deliverable_single_source.py` — which exists to keep those two in
step — was red on `main` as a result. The constant's own comment says to add a document type
"HERE and nowhere else". Reported rather than reverted; the alternative is landing with a red
structural test.

No scenario misses: every SPEC scenario S1–S5 has at least one test.

## ✅ Consensus Findings

### P1 — the detail cap had a third path (`spec_machine.py:1763`) — REPAIRED after the close

Raised independently by the **consistency** lens and the **security** lens in confirm-2, each
citing the same line.

`approval_state_of` returns `invalid` from three branches. The confirmation-pass repair capped
the content-hash-mismatch branch and its comment claims "the cap lives HERE". Three lines
below, the `spec_slug`-mismatch branch composes `f"approval is for {model.spec_slug!r}"` with no
cap, and `spec_slug` carries charset validation but no `max_length`. The detail reaches
`approval-status`'s JSON stdout and `hold_lines`' gate text unbounded.

This is the same bug class as the finding it was repairing, three lines away, in the same
function — the third instance of that shape in this review.

**Repaired in a post-close round the DRI asked for** (see the appendix). The cap moved out of
the composition sites and into `_state`, the sole constructor of `ApprovalState` — verified by
two lenses: `ApprovalState(` appears exactly twice in the file, the class definition and the one
call inside `_state`, so no branch (including one written later) can bypass it.

### P1 — the race caveat does not reach the reader who acts on it (`wrapup.md.j2:240`)

Raised by the **concurrency** lens in confirm-2.

The repair for its own confirm-1 P2 added a docstring saying that `cross_validate`, now outside
the lock, reports on the document as it is on disk rather than the one the call wrote. True,
and verified. But the reader exposed to that race is the rendered wrapup stage, whose prose
tells the agent that a non-zero `mark-tested` exit means a recorded test does not resolve. Under
a peer write in that window the agent misdiagnoses, and on the Production preset a foreign
transient mismatch becomes a fail-closed STOP.

**Not repaired, and not repairable here**: `src/harness_maker/templates/` is this PLAN's one
`Do not change` path, and a template edit re-captures `autopilot_gate_golden.json`, which
another session currently owns. This belongs to its own task.

### P2 — the symlink test covered one of the two widened handlers — REPAIRED after the close

Three lenses (consistency, concurrency, security). The repair widened both the `mark-tested`
and `mark-judged` `except` clauses to `OSError`; only `mark-tested` had a symlink test, so
narrowing `mark-judged`'s clause back would have passed the suite silently. The test is now
parametrized over both writers and asserts the errno text as well as the command prefix.

## ⚠️ Weak Consensus

None.

## 📝 Manual-Only Findings

None. Every finding reached at least one full lens voice.

## 🤝 Disagreements

**One, resolved by measurement.** Codex raised (P2) that `SpecMachine`'s `extra="allow"` lets a
SPEC carry a top-level key named `AC-001` or `ac_order`, which the synthetic digest keys would
overwrite. The round-1 **consistency** lens explicitly ruled the same hazard out, reasoning that
`AcceptanceCriterion`'s `^AC-\d{3,}$` format means an AC id can never equal a top-level field
name.

The two were answering different questions — the lens looked at the AC-id side, Codex at the
authored-extra-key side. Running it settled it:

```
content hash moved: True
any digest moved:   False
```

Codex was right. Editing such a field moves the hash while no digest changes, so the hold fires
and names nothing — the exact silence the digest map exists to remove, arriving through the door
the map itself opened. Repaired in round 2.

## 🧊 Cross-model findings (frozen @ round 1)

Codex was invoked once, at round 1, `status: invoked`, 37.7 s. Rounds 2–3 re-read this section
rather than re-invoking it.

| id | severity | disposition | summary |
|---|---|---|---|
| `581960f372cd4c11` | P2 | **accepted** | Digest keys overwrite an authored top-level `AC-001` / `ac_order`; the field's edit then reports "no field digest moved" |
| `e5b08ada432bef80` | P3 | **accepted** | Lock failures escape the `mark-tested` / `mark-judged` CLI handlers as tracebacks; `approve` already caught them |

Both were verified against source before acceptance. `e5b08ada432bef80` describes the same
defect as the round-1 consistency lens's P1 but at a different severity tier, so per the
consensus filter's no-tier-bridging rule they stayed independent rather than merging.

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | B     | —             | 7         | —   |
| 2         | A     | 5             | 2         | 1   |
| confirm-1 | A     | —             | 2         | 3   |
| 3 (repair)| A     | 3             | 2         | 1   |
| confirm-2 | B     | —             | 6         | 4   |

Final grade: **B**
Iterations used: 3 / 3 (one was the confirmation pass's dedicated repair round, which is
budgeted separately and did not consume a review round)
Exit reason: **confirm-2 dirty** — the terminal confirmation pass returned new severe findings

Churn: round 2 `0.105` (max `tests/unit/test_spec_approval.py`, 3 files measured) · round 3
`0.057` (2 files measured). Round 2's re-review was **skipped** by the churn gate:
`churn 0.11 < 0.30`, `dispatches: []`.

`unreviewed_fix_count`: 3 — the round-3 repairs were reviewed by confirm-2, so the only
unreviewed fixes are the three confirm-2 findings' absence of repair, which is the terminal
pass's defined behaviour rather than a gap.

## 📏 Size & Complexity

Not measured this review — `review_churn complexity` was not run. Recorded as absent rather
than reported as zero.

## 🔁 Oscillation

No hunk was removed by one round and restored by a later one.

## What this review is actually evidence of

Four findings in this review are the same shape: **an exception or a bound that the author
applied to the path in front of them and not to its siblings.**

1. Round 1 — `approve` caught `ApprovalError`; `mark-tested` and `mark-judged` did not.
2. Round 2 — the fix for the digest collision raised a new exception that `_run_approve`'s
   `except` clause did not list, reproducing (1) inside the repair for a different finding.
3. Confirm-1 — `O_NOFOLLOW` made `ELOOP` reachable, which is not a `LockTimeoutError`, so the
   two handlers repaired in (1) missed it.
4. Confirm-2 — the detail cap was applied to one `invalid` branch and not the sibling three
   lines below.

Each was caught by a different gate, and none by the one before it. That is the argument for
the confirmation pass existing at all: the terminal pass found (4) after two review rounds had
approved the file.

## Appendix — the post-close repair round (round 4)

The run was closed `CHANGES_REQUESTED` when confirm-2 came back dirty, which is the stage's
rule: a terminal pass records its findings rather than repairing them. The DRI then chose to
close the cheap one and defer the other. That decision is recorded here because it happened
**after** the automated flow terminated, and a reader should be able to tell the difference.

**Repaired:**
- the `spec_slug`-mismatch detail cap — moved into `_state` rather than added as a third
  per-branch slice, because the per-branch placement is what failed three times (224, 739 and
  234 characters, each measured by removing the cap and re-running);
- the symlink test's one-sided coverage.

**Verified by the two lenses that raised the P1** — a targeted re-review over the repair only,
not a fourth full 4-lens pass. That is a deliberate deviation from the stage's dispatch list,
recorded rather than hidden: the change was two files and `churn 0.06`, and both lenses were
asked the questions that would expose a bad repair (is there a path to `detail` that skips
`_state`; does any caller parse the detail rather than display it; is anything now
double-capped). Neither found a new defect.

**Two corrections came out of that verification, both applied:**
- the `slug-mismatch` test case did not reach the branch it names. `spec_slug` is hashed, so
  editing it in place returns at the hash-mismatch branch first. The fixture now approves under
  the long slug and presents the same bytes under another file name, and asserts
  `"approval is for"` is in the detail so a future drift is loud. Caught by the inversion check,
  not by a reviewer — it is `[fail:test] assertion-invariant-over-named-dimension` (count:16) in
  a test written to close a finding about exactly that class of mistake.
- a comment claiming the errno assertion separates a scoped `except (ApprovalError, OSError)`
  from an over-broad `except Exception` was wrong: both stringify the same ELOOP message. The
  comment now says what the assertion actually proves — that the caught object is the real
  `OSError`, not something else reaching the same output line.

**Still outstanding, by decision:** the `wrapup.md.j2` P1. It is prose in
`src/harness_maker/templates/`, this PLAN's one `Do not change` path, and a template edit
re-captures `autopilot_gate_golden.json`, which another session currently owns. Its own task.

Final grade after round 4: **B** (P0 0, P1 1, P2 1). `human_review_needed: false` from the
grade gate — the one remaining P1 is consensus-passed and accepted, not an unverified severe
finding — but the deferral above is a human decision already taken, not an open question.

Status: CHANGES_REQUESTED (the run closed there; round 4 was a DRI-directed repair after it)
human_review_needed: true — one P1 deferred to its own task
Counters: unreviewed 0 · prior-fix 1 · unattributed 0
