---
type: review
task_slug: hm-light-lane-s3a
status: APPROVED
created: 2026-10-15
reviewers_invoked: [code-reviewer, security-reviewer, test-reviewer]
consensus_method: cross-check
review_base: e7dd66484ad53be9211d936873195afd5ad15199
drift_verdict:
  result: clean
  scope_violations: []
  scenario_misses: []
  task_slug: hm-light-lane-s3a
  computed_at: 2026-10-15T04:20:00Z
---

# REVIEW — hm-light-lane-s3a (stage 3a of HM-LIGHT-LANE)

Run on the PR branch (no per-task worktree). Lane `full`, preset Production. Diff
`review_base..HEAD` with regenerated outputs (snapshots, goldens, surface baseline, fixture JSON)
excluded from the reviewer diff.

**Procedure deviations, stated so nobody infers a step that did not run:**
- Round 1 was two dispatches. The first covered the core lenses and had no shell. The second covered
  security and tests, ran with a shell, and re-captured the e7dd6648 boundary golden from a real
  detached e7dd6648 tree. All 1,074 cases matched.
- Pass 2 was the main loop deciding each finding, not a second dispatch.
- There were two confirmation passes, each one dispatch with a shell. They ran after round 1
  (db9f68b7, 6c0c3534) and after the follow-up (041a1d3f).
- The cross-model second opinion was skipped (`codex` CLI not installed; warn and proceed).
- The round-1 amendment added IRR-005, AC-015 and AC-016, which invalidated the approval stamp.
  The DRI re-approved on a card, and the stamp was written from that tap (0deef23a). The
  follow-up commit does not touch the SPEC.

## Round 1

No P0, 4 P1, about 10 P2, and P3s. The full lane and the typed and loop paths are byte-identical
to e7dd6648: 1,074 boundary cases and 32 render configs.

| Sev | Summary | Disposition |
|---|---|---|
| P1 | Editing `lane: light` into an approved full SPEC earned the skip, because the approval hash covers only the machine yaml | fixed: `approval.lane` is stamped by `approve()`, and the skip needs stamp lane == md lane == light (IRR-005, AC-015) |
| P1 | An old PASSED record plus a later Check 2 mark gave a skip on a changed tree | fixed: the record carries `verification_key`, which must equal the current relevant key (AC-016) |
| P1 | The reader ignored `checks:`, so a record with `security: fail` still skipped | fixed: required values per check |
| P1 | The forced scan had no failure clause, so stale findings could pass Check 4 | fixed: no exit 0 or no summary line means not a pass. The scan is run in the background and bounded |
| P2 | The exempt stamp fired over a DRI who declined, and on Step 4 failures | fixed: exempt only when Step 4 passed, the SPEC is approved, and the DRI was not asked |
| P2 | The degraded `mark-pass` path satisfied the cache | fixed: the marker writer must be `run`. A `light_check` partial flag drops mark-pass, BLOCKED and the 6a/6b prose, and verify stays byte-identical |
| P2 | Loop mode and a missing ref file were handled only inside the ref file | fixed: the stub carries the loop condition, and a missing file skips the check instead of STOP |
| P2 | `computed_at` was model-authored and could be naive | fixed: it comes from `date -u`, and naive or date-only values are rejected |
| P2 | Drift negatives and the AC-010 reader were untested or self-referential | fixed: negative kinds were added, and AC-010 reads wrapup Step 3 and verify Check 1 from the e7dd6648 golden |
| P3 | A `stage_skipped` row was written before an objective halt; a human `--until review` marker was skipped; the strictness excuse set was too broad; capture provenance; banner text | all fixed |

## Confirmation passes

**Pass 1:** A–P confirmed (K partial, not fail-open). New P2: a manual session still trusted a
lane flipped after approval. The light check took the lane from the `.md`, and the banner sent
the user to wrapup. Fixed in 041a1d3f: `approval-status` prints `trusted_lane` (the `lane_of`
answer), and Step 4.2 runs only on `light`. The P3 on K was also fixed in 041a1d3f: security gates
on the scan's own `Severity:` line, `high` and `P0` both fail, and a missing line fails.

**Accepted residuals, recorded as PLAN follow-ups:**
- `approval.lane` is not hash-bound (`lane_hash`). This is defence in depth: `approve` itself is
  unguarded.
- Verify's own Check 4 ignores `P0`. This gap predates this change and gets its own task.
- hm telemetry does not redact `tp_live_`-style tokens in Bash command text (found by the eval).
- A deterministic `hm light_check run` would replace the prompt-level gates.

## Grade

**A** after round 1 and two confirmation passes. Status APPROVED. Surface: Claude +1,310 chars,
Codex +8,380 chars over e7dd6648. Codex inlines the light check in `hm-execute`; the trims in
round 1 recovered part of that.
