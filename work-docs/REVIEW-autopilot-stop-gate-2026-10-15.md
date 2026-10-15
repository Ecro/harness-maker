---
type: review
task_slug: autopilot-stop-gate
status: APPROVED
created: 2026-10-15
reviewers_invoked: [code-reviewer, security-reviewer, test-reviewer]
consensus_method: cross-check
review_base: 031b2e6c
drift_verdict:
  result: clean
  scope_violations: []
  scenario_misses: []
  task_slug: autopilot-stop-gate
  computed_at: 2026-10-15T20:30:00Z
---

# REVIEW — autopilot-stop-gate

Lane `full`, preset Production. The review ran on the branch with no per-task worktree.
The diff is `031b2e6c..HEAD`, with the replay fixtures checked separately for leaked text.

**Procedure, so no step is inferred:**
- Round 1 ran three read-only lenses: code, security and tests.
- The main loop decided each finding.
- One read-only confirmation pass covered the round-1 fixes.
- The main loop fixed three residual P2s from that pass itself and re-ran the full local gate.
- The cross-model second opinion was skipped because the `codex` CLI is not installed. The rule is
  to warn and proceed.
- CI was not used, per the DRI's instruction of 2026-10-15. The gate was local.

## Round 1

No P0.

| Sev | Summary | Disposition |
|---|---|---|
| P1 | The heavy `autopilot` import at module top. A failing import would also disable the loop block, and every Cursor `pretooluse` call paid for it. | Fixed: lazy import inside the guarded path; an import failure fails open |
| P1 | The whole transcript was read into memory on every Stop with a pending authorization | Fixed: streamed with `errors="replace"`, early stop, a 256 MiB cap that fails open |
| P1 (tests) | The AC-002 differential never reached the new code | Fixed: 120 own-marker cells added (280 in total), all equal to the df070f6c reference |
| P1 (tests) | No row proved the Skill call must come after the authorization | Fixed: before and equal-instant rows both block |
| P2 | Only the exact spelling `hm:<stage>` counted as an invocation | Fixed: first token, leading `/` stripped, `hm:` / `hm-` / `harness-maker:` forms |
| P2 | Any TTL-fresh peer marker switched the gate off | Fixed: a peer must be id-bearing, not gated, and live (`idle_minutes` ≤ 30) |
| P2 | A future-dated ledger row could refuse every turn's first stop | Fixed: a row more than 5 min ahead of now is not pending |
| P2 | A strict utf-8 read made a partial write skip the check | Fixed: `errors="replace"` |
| P2 (tests) | Replays could pass through fail-open; manifest hashes unchecked; peer conditions untested; timestamp ordering unpinned | Fixed: no-warn asserts plus 89 one-ms-before controls that block; a manifest hash test; peer rows r15c–f; rows d1–d6 |
| P3 | Queued commands and untimed user records were not treated as a new turn | Fixed: both count as moved on |
| P3 | The autopilot logger could add stderr lines | Fixed: silenced in the hook and restored in `finally` |
| P3 | The manifest recorded an eval-host path | Fixed: neutral description |
| P3 | A Skill call stamped just before its ledger row is ignored | Declined: unlikely, and tolerating skew weakens the strictly-after rule |
| P3 | The ledger is re-read once per pipeline stage | Declined: the stamped SPEC pins `find_unconfirmed_authorization`, and ledgers are small |
| P3 | The pre-existing loop block prints its reason to stdout only, with exit 2 | Declined here: AC-002 requires it unchanged; a follow-up |

## Confirmation pass

Every round-1 fix is confirmed. The early stop cannot misclassify a transcript that has no Claude Code
record.

Residuals the main loop fixed after this pass:
- The Skill regex accepted a bare `execute` or `other:execute`. It now needs an `hm:`, `hm-` or
  `harness-maker:` segment (rows s7–s9).
- Ties between stages were broken by set iteration order. The key is now `(ts, name)`.
- A peer whose `last_seen` lies in the future dropped out of liveness. It now falls back to the
  TTL check (row r15g).

Residuals accepted, all failing open:
- A future-dated row hides a later authorization for the same stage.
- A peer idle for more than 30 minutes no longer defers the gate. The cost is at most one wrong
  refusal.
- A transcript near the cap may exceed the 10 s hook timeout. A Claude Code hook timeout does not
  block.

**SPEC text drift, not edited because editing voids the stamp:**
- S1 says "fresh" peer; the code means live, as in PLAN ADR-006.
- The text says `Skill(hm:<stage>)`; the code also accepts `hm-<stage>` and `harness-maker:<stage>`,
  as in ADR-009.

## Grade

**A** after round 1 and one confirmation pass. Status APPROVED.

The replay result is unchanged: of the 35 eval-2 runs with a ledger, exactly the 5 post-spec stalls
block. None of the 89 stage starts blocks.
