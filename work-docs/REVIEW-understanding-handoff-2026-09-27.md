---
type: review
task_slug: understanding-handoff
status: CHANGES_REQUESTED
human_review_needed: true
created: 2026-09-27
reviewers_invoked: [code-reviewer, security-reviewer, concurrency-reviewer, test-reviewer, codex]
consensus_method: cross-check
run_id: 60db41555ace
drift_verdict:
  result: clean
  scope_violations: []
  scenario_misses: []
  task_slug: understanding-handoff
  computed_at: 2026-09-27T00:25:00Z
---

# REVIEW — understanding-handoff

## 🎯 Round 1 Summary

Grade **B** (P0 0, P1 2). Coverage: all 7 lenses exercised, `blocks_approval: false`.
Codex second opinion invoked; both findings `accepted` by PIDA mode B. Security and concurrency
lenses returned no findings. Auto-fix loop entered for the two P1s (+ P2/P3 carried).

## 🔍 Drift Findings

None. Every changed path is in a PLAN phase scope (Phase 4 scope was extended during execute to
name the autopilot golden re-capture) or is a deliverable (SPEC/PLAN/BASELINE-DELTA/REVIEW).
Intent drift (Step 3.3, `UNDERSTANDING-HANDOFF`): no work outside `scope`, none inside
`out_of_scope`, the statement's subject is covered.

## ✅ Consensus Findings

| id | Sev | Lens / voices | File | Summary |
|---|---|---|---|---|
| 6457912149c67ba8 | P1 | design | `src/harness_maker/templates/stages/wrapup.md.j2` | `summary_done` asks to print the block "below" a banner documented as the final output — no defined place for it |
| f40fd0d000aa9cd7 | P1 | tests | `src/harness_maker/wrapup_land.py` | resume path untested, and the receipt classifies the message file, not HEAD's committed body |
| 069b35bd994ffdc2 | P2 | functionality + codex | `src/harness_maker/wrapup_land.py` | same resume defect at P2 (kept independent of the P1 — tiers are never bridged) |
| 789be9036c14d74e | P3 | design + codex | `src/harness_maker/wrapup_land.py` | blank-line skip re-slices the list — quadratic |
| f73d3cca15df1b78 | P3 | tests | `tests/unit/test_render_understanding_handoff.py` | AC-005 anchor detects rewording only; document the limitation |

All dispositions: `accepted`.

## ⚠️ Weak Consensus

None.

## 📝 Manual-Only Findings

None.

## 🤝 Disagreements

The resume-path defect was raised at P1 (tests) and P2 (functionality, codex). Kept as two
findings per Step 4c; one fix resolves both.

## 🧊 Cross-model findings (frozen @ round 1)

| id | model | severity | file:line | disposition | status | summary |
|---|---|---|---|---|---|---|
| 47990e072788d945 | codex | P2 | `src/harness_maker/wrapup_land.py:364` | accepted | resolved (round 2, Fix #2) | resume path classifies the edited message file while the existing commit (reused by task-land) lacks the block |
| 5c8cd231ab250bd7 | codex | P3 | `src/harness_maker/wrapup_land.py:77` | accepted | pending | blank-line skip is O(n²) |

### Iteration 2 (Grade: B → A)
Fixes applied: 2
| # | Severity | Summary | File | Status |
|---|----------|---------|------|--------|
| 1 | P1 | print the block before the closing banner; `Done` line points at it (6457912149c67ba8) | `src/harness_maker/templates/stages/wrapup.md.j2` | Applied · caused_by=none |
| 2 | P1 | classify the landed body — HEAD's on resume — after the commit decision; resume test added (f40fd0d000aa9cd7, also resolves 069b35bd994ffdc2 / codex 47990e072788d945) | `src/harness_maker/wrapup_land.py` | Applied · caused_by=none |

Not selected (grade B; P2/P3 only at D/F): 789be9036c14d74e (P3, codex 5c8cd231ab250bd7), f73d3cca15df1b78 (P3).
Size sites re-frozen for the extra wrapup prose (ratchet 51820, lines 845/847, baseline, golden, snapshots).
Re-review: 1 dispatch (functionality), churn 0.42 ≥ 0.30. New: 542b4c78b72ec41b P2 — warning text "(commit proceeds)" is stale now that it prints after the commit · caused_by=Fix #2.

Remaining: 3 (P2 1, P3 2) | New issues introduced: 1
Churn: 0.4167 (max: work-docs/BASELINE-DELTA-understanding-handoff.md, measured 14, excluded 0)

## Confirmation passes

- **confirm-1** (`5ba91a72..c353f0a6`, all 7 lenses): 1 new P1 — the print-before-banner
  instruction had no deterministic source (robustness). New P2s: TOCTOU between
  `_head_subject` and `_head_body` on resume (concurrency); AC-008 preservation cases omit
  `missing`/`none` (tests); AC-008 untested against git's default blank-line cleanup
  (functionality). → one repair round (not counted as a review round): re-read the block with
  `git log -1 --format=%B`. Churn 0.28.
- **confirm-2** (`5ba91a72..eef0820d`, all 7 lenses): 2 new P1 — (a) the bare-`HEAD` re-read
  races a peer session's land onto the shared base and can print a foreign task's block
  (concurrency); (b) the closing instruction assumes a valid block and never surfaces
  `steps.understanding`, so a missing/malformed block is claimed as printed (design). New P2:
  AC-005 does not anchor on the closing instruction itself (tests). **Dirty → review stops.**

## 🔁 Oscillation

None (rounds 2, 3).

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | B     | —             | 5         | —   |
| 2         | A     | 2             | 3         | 1   |
| confirm-1 repair | A | 1          | 7         | 4   |

Final grade: A (letter) — confirmation pass 2 dirty
Iterations used: 2 / 3 (+1 confirmation repair round)
Exit reason: converged, then confirm-2 dirty
Status: CHANGES_REQUESTED
human_review_needed: true
Counters (see §5): unreviewed 1 · prior-fix 2 · unattributed 0

## 📏 Size & Complexity

| File | LOC | Cyclomatic | Max nesting | Status |
|------|-----|------------|-------------|--------|
| `src/harness_maker/wrapup_land.py` | see `review_churn complexity` rows r2 | — | — | measured |
| templates / SPEC / docs | — | null | null | not-python |

## ⚠️ Post-review change under DRI instruction (not confirmation-reviewed)

The DRI's standing instruction for this task was to proceed to wrapup without stopping. After
the review closed `CHANGES_REQUESTED`, the two confirm-2 P1s and the AC-005 P2 were fixed outside
the review, and **no confirmation pass covers these edits**:

- `wrapup.md.j2`: the closing instruction branches on `steps.understanding.status` — `ok`/`none`
  print the block re-read from the `--message-file` (committed unchanged, AC-008), never from
  memory or a bare `HEAD`; any other status prints the `[wrapup_land] understanding:` warning and
  says no usable block landed. `summary_done` reads "…verbatim (or the warning) is printed above".
- `test_render_understanding_handoff.py::test_ac_005_…` now anchors on that instruction; it fails
  against the confirm-2 wording (4/4) and passes on the fix.
- Size sites re-frozen again (ratchet `wrapup` 52162, lines 848/850, baseline, golden, snapshots).

Carried open for a human sweep (P2/P3, not grade-bearing): stale warning wording
`(commit proceeds)` (542b4c78b72ec41b); TOCTOU subject/body read on resume; AC-008 lacks
`missing`/`none` and double-blank-line cases; quadratic blank-line skip (789be9036c14d74e /
codex 5c8cd231ab250bd7); AC-005 same-author literal note (f73d3cca15df1b78).

## Follow-ups after landing (2026-09-27)

- `67faab2c` — focused confirmation of the two confirm-2 P1 fixes found the closing print still
  re-read the message file (differs from the landed body on a resume) and had no branch for a
  receipt without the key. `wrapup_land` now records `steps.understanding_block`; the closing
  print uses it. Quadratic blank-line skip (789be9036c14d74e) fixed on the way.
- Carried P2s resolved: stale warning wording (542b4c78b72ec41b) → "(warning only — the commit
  is unaffected)"; resume TOCTOU → HEAD's subject and body come from one `git log` read;
  AC-008 gains `missing`/`none` and a git-cleanup case.
- The round-3 payload reconstructed in `67faab2c` was removed and recorded in
  `_KNOWN_MISSING` instead, with the other 12 pre-existing misses the local gate listed.
