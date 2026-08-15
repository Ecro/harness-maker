---
type: spec
task_slug: review-loop-empirics
status: approved
created: 2026-08-15
tags: [harness-maker, spec, review-loop, lens-coverage, churn, disposition]
test_framework: pytest
tier: 2
research_doc: "[[RESEARCH-review-loop-empirics]]"
summary: "Adopt the six-category discovery axis, give each lens a vote, and gate re-review on churn."
---

# SPEC — Review loop: coverage diversity in, budget-exhausting repeat rounds out

## 🎯 Intent

`/hm:review` currently spends its round budget re-running the **same** work: rounds 2..N re-dispatch
reviewers over a moving target and stop on *issue exhaustion* (grade A = zero consensus-passed
P0/P1). Measurement on an isolated 200-call experiment
([[RESEARCH-review-loop-empirics]]) shows this is the wrong economy: at equal call budget, six
**category-distinct** calls found +52 % unique issues with 21 % fewer raw remarks than six
**identical** calls; repair-round yield tracks fix churn (r = 0.837), not reviewer convergence; and
40 rounds of review→fix produced zero compliance improvement.

Two structural facts follow, and this SPEC acts on both. First, the discovery axis should be the
six review categories the experiment used, not our incidental five. Second — and this is the part a
naive adoption gets wrong — the fan-out gain consists *by definition* of findings only one lens
raised. Under a K=2 consensus filter those are demoted to `manual-only`, neither graded nor fixed.
Adding lenses while keeping cross-lens consensus would pay the full cost and discard the entire
yield.

## 🌅 Outcomes

After this change an operator can, without reading the implementation:

- See round 1 and the confirmation pass dispatch the **same** six-category discovery axis —
  design · functionality · complexity · robustness · naming · consistency — plus the domain lenses
  the preset requires.
- See a finding raised by exactly one lens **counted and repaired**, because distinct lenses examine
  distinct axes and cannot corroborate one another by construction.
- See **every** finding carry an explicit `accepted` / `rejected` / `duplicate` / `unresolved`
  disposition, with a cited authority on rejection.
- Know that a rejection improves the grade **only** when it cites a SPEC acceptance criterion — an
  independent contract — so self-grading has no path to an undeserved `A`.
- See a repair round **skipped entirely** when the fix was small, with the measured churn ratio
  printed as the reason.
- Read `exit_reason: no-progress` with the measured churn ratio attached.
- See a `spec_gap` finding raised when the loop rewrites the same site in opposite directions,
  flagged for a human rather than fed back to the fixer that produced it.

## 📋 In-Scope Scenarios

### S1: Round 1 dispatches the six-category axis plus the preset's domain lenses
**Given** a Production-preset harness
**When** `/hm:review` runs round 1
**Then** it dispatches `design`, `functionality`, `complexity`, `robustness`, `naming`,
`consistency`, `security`, `concurrency` and `tests`, all mandatory
**And** a Side-preset harness dispatches the six core lenses as mandatory while `security`,
`concurrency` and `tests` are selected by the conditional router from the changed paths

### S2: Side's mandatory set is a subset of Production's
**Given** any configured lens set
**When** both presets are rendered
**Then** Side's mandatory lenses are a subset of Production's, and no lens exists on Side alone

### S3: The confirmation pass dispatches the same mandatory set as round 1
**Given** a Production harness whose mandatory set includes `naming`
**When** the confirmation pass runs
**Then** it dispatches that lens too and writes its result into the pass directory
**And** `lens_coverage check` for the pass does not report it missing

### S4: A missing mandatory lens blocks approval identically to the legacy five
**Given** a round whose `naming` lens produced no result file
**When** `hm lens_coverage check` runs
**Then** it reports `naming` in `missing` and `blocks_approval: true`

### S5: A single lens's finding has a full vote; cross-model voters keep K=2
**Given** a P1 finding raised by the `robustness` lens and by no other lens
**When** the consensus filter runs
**Then** the finding is treated as consensus-passed: it counts toward the grade and is auto-fix
eligible
**And** a finding raised only by `codex` or `antigravity` still requires a second agreeing voice,
because those voters review the same diff on the same axis rather than a distinct one

### S6: Low-importance findings do not move the grade
**Given** a round whose findings are all P2 naming and consistency remarks
**When** the grade is computed
**Then** the grade is `A` and the findings are still reported

### S7: Every finding carries a disposition, whatever its fate
**Given** a completed round containing findings that are P3, suggestion-less, drift-sourced,
confirmation-pass-sourced, or produced in an `auto_fix`-disabled run
**When** the round record is emitted
**Then** each carries exactly one of `accepted` / `rejected` / `duplicate` / `unresolved`
**And** a record with a null or unrecognized disposition is rejected as invalid

### S8: A rejection cites an authority, and has one available
**Given** a finding the fixer declines to apply
**When** it is recorded as `rejected`
**Then** it carries a SPEC acceptance-criterion id or a citation of the target code's own docstring
**And** when neither exists the finding is recorded `unresolved` with authority `no-contract`, and a
`rejected` record with no authority is invalid

### S9: Only an AC-cited rejection can improve the grade
**Given** two consensus-passed P0 findings, one rejected citing `AC-004` and one rejected citing a
docstring
**When** the grade is computed
**Then** the AC-cited rejection is excluded from `P0_count` and the docstring-cited one is not
**And** the docstring-cited rejection sets `human_review_needed`

### S10: A small fix skips the re-review
**Given** a repair round whose applied fixes changed 5 % of the touched files' LOC
**When** the loop reaches the re-review step with a threshold of 20 %
**Then** no reviewer is dispatched
**And** the iteration record states the measured ratio and the threshold that produced the skip

### S11: A large fix triggers exactly one structured reviewer
**Given** a repair round whose applied fixes changed 35 % of the touched files' LOC
**When** the loop reaches the re-review step
**Then** exactly one structured reviewer is dispatched over the changed hunks — sufficient because
S5 gives a single lens a full vote, and cheaper than the full set

### S12: The churn ratio is computed over pinned endpoints and survives degenerate files
**Given** a repair round that created a file, deleted another, renamed a third, and touched a binary
**When** the churn ratio is computed
**Then** the endpoints are the pinned pre-fix and post-fix trees, not the cumulative working diff
**And** the reported ratio is the **maximum across touched files**, so a small edit to a large file
cannot mask a small file rewritten whole
**And** a created file contributes 1.0, a deleted file is excluded from the denominator, and a
binary file is excluded with its exclusion recorded

### S13: The churn threshold is configurable and defaults when absent
**Given** a `harness.yaml` with no `reviewers.rereview_churn_ratio` key
**When** the threshold is read
**Then** it resolves to `0.20` without error
**And** an explicit value overrides it, and a non-numeric or out-of-range value is a load-time error

### S14: A stalled loop reports the churn behind the stall
**Given** a repair round that produced no counted lifecycle transition
**When** the loop terminates
**Then** `exit_reason` is `no-progress` — the existing value, precedence unchanged — with the
measured churn ratio attached, and no new exit reason is introduced

### S15: An oscillating site is reported to a human, not to the fixer
**Given** a hunk rewritten in round 3 and restored to its round-2 content in round 4
**When** the round-4 record is computed
**Then** a P1 finding with category `spec_gap` is emitted, identified by
(file path, normalized hunk content hash, nearest enclosing symbol)
**And** it is tagged `manual-only`, setting `human_review_needed` without becoming auto-fix eligible

### S16: The briefs carry the two prohibitions, and the test ban has its carve-out
**Given** a rendered `/hm:review`
**When** the `design` lens brief and the auto-fix loop text are read
**Then** the brief states that the public contract is fixed and out of scope
**And** the auto-fix text forbids editing a test file to resolve a finding whose target is **not**
that test, permits running tests, and permits fixing a finding whose target **is** the test — so a
mandatory `tests`-lens finding remains repairable

### S17: The axis pilot records per-lens exclusive yield
**Given** the nine-lens configuration and the current five-lens configuration
**When** both are run over the same three real diffs
**Then** the audit document records, per lens, the finding groups no other lens produced, with
severities and dispatch counts
**And** any lens with zero exclusive yield across the sample is named as a prune candidate — this
informs a future prune and does not gate this change

### S18: Turning the gate off is a configuration choice, not a finding
**Given** `reviewers.rereview_churn_gate: false`
**When** `/hm:health` runs
**Then** the churn-gate signals report `not_applicable` with no penalty, exactly as
`permissions.deny_dangerous` does when opted out

## 🚫 Non-Goals

- **Keeping cross-lens K=2 consensus for reviewer lenses.** Distinct lenses examine distinct axes,
  so requiring corroboration across them discards precisely the fan-out yield this change exists to
  capture. Consensus is retained where corroboration is meaningful: repeated instances of the *same*
  lens, and cross-model voters reviewing the same diff on the same axis.
- **Giving cross-model voters a solo vote.** Their findings carry no `suggestion` (vendor schema), so
  a solo-voting cross-model finding would block grade A with no repair path.
- **Retiring `performance-reviewer` / `ux-reviewer`.** They are outside the six-category axis and
  stay as conditionally-routed extras, unchanged.
- **Forcing a second confirmation pass on large terminal churn.** `confirm-1` already sweeps
  `review_base..freeze`, which includes the terminal round's fixes, so a forced `confirm-2` would
  re-review a byte-identical tree — an identical repeat of the kind this work eliminates.
- **A new `churn-converged` exit reason.** Zero churn implies zero counted transitions, so the
  pinned `no-progress` rule fires first; the ratio is attached to that exit instead.
- **Cross-round auto-fix suspension.** No such store exists. Oscillation is reported, not suppressed.
- **Runtime enforcement of the test-edit ban.** Prompt-level guidance, like the executor's worktree
  scope.
- **Cognitive-complexity or size measurement.** Cognitive complexity correlates r ≈ 0.81 with LOC and
  needs per-language tooling; the `complexity` lens covers the judgment, the metric is out of scope.
- **Changing `max_review_rounds` or removing the auto-fix loop.**

## ⚠️ Constraints

| Constraint | Value | Rationale |
|---|---|---|
| Test framework | `pytest` | CLAUDE.md — project-wide, non-negotiable |
| Language | Python 3.12+, no Bash | CLAUDE.md runtime decisions |
| Discovery axis | design, functionality, complexity, robustness, naming, consistency | Adopted verbatim from the source experiment's structured arm |
| Domain lenses | security, concurrency, tests — **mandatory on Production**, conditionally routed on **Side only** | User decision: the six-axis core is universal; the cost adjustment happens on Side |
| Consensus scope | A single reviewer lens votes alone; K=2 retained for same-lens repeats and for cross-model voters | Distinct lenses cannot corroborate one another; identical-axis voters can |
| Rejection effect | `rejected` keeps counting toward the grade unless the authority is a SPEC AC id | An AC is an independent oracle; a docstring is the fixer's own reading |
| Repair round | Exactly one structured reviewer above threshold, none below | A single voice now votes, so one dispatch is sufficient |
| Churn threshold | `reviewers.rereview_churn_ratio`, default `0.20`, **max across touched files** | Interview round 3; aggregation fixed after review found the dilution defect |
| Churn endpoints | Pinned pre-fix and post-fix trees | A cumulative working diff measures the whole review, not the round |
| Rejection authority | SPEC AC id, else target docstring, else `no-contract` → `unresolved` | Task-driven harnesses have no SPEC and docstrings are optional |
| Exit reasons | Unchanged four-value set | Adding a fifth would reorder a pinned invariant |
| Backward compat | Absent config keys resolve to documented defaults, never silent no-ops | CLAUDE.md learned correction 2026-06-08 |
| Determinism | Render output unchanged for unchanged inputs; snapshots regenerated in the worktree | CLAUDE.md testing policy |

## ✅ Verification Criteria

| Scenario | Verification mode | Test name |
|---|---|---|
| S1 | unit | `test_round1_lens_set_matches_preset` |
| S2 | unit | `test_side_mandatory_is_subset_of_production` |
| S3 | unit | `test_confirmation_pass_uses_same_mandatory_set` |
| S4 | unit | `test_missing_new_mandatory_lens_blocks_approval` |
| S5 | unit | `test_single_lens_votes_crossmodel_keeps_k2` |
| S6 | unit | `test_p2_only_findings_grade_a` |
| S7 | unit | `test_every_finding_has_disposition` |
| S8 | unit | `test_rejection_requires_authority` |
| S9 | unit | `test_only_ac_cited_rejection_clears_grade` |
| S10 | unit | `test_below_threshold_churn_skips_rereview` |
| S11 | unit | `test_above_threshold_dispatches_one_structured_reviewer` |
| S12 | unit | `test_churn_ratio_endpoints_and_degenerate_files` |
| S13 | unit | `test_churn_threshold_absent_and_explicit_and_invalid` |
| S14 | unit | `test_no_progress_records_churn_ratio` |
| S15 | unit | `test_oscillating_hunk_emits_manual_only_spec_gap` |
| S16 | unit | `test_render_briefs_and_test_edit_carve_out` |
| S17 | unit + manual | `test_audit_report_records_per_lens_yield` over the pilot's `AUDIT-lens-axis-2026-08.md`; the yield numbers themselves are read by a human |
| S18 | unit | `test_health_reports_gate_off_as_not_applicable` |

### AC-001: Round 1 renders the six-category axis plus the preset's domain lenses
The rendered round-1 dispatch names the six core lenses on both presets, with `security`,
`concurrency` and `tests` mandatory on Production and conditionally routed on Side.

### AC-002: Side and Production differ only in mandatory-ness, not in availability
Side's mandatory set is a subset of Production's; no lens exists on Side alone.

### AC-003: A missing mandatory lens blocks approval
`lens_coverage check` treats every mandatory lens identically to the legacy five.

### AC-004: A single reviewer lens votes alone; cross-model voters keep K=2
A finding raised by exactly one reviewer lens is consensus-passed; a finding raised only by a
cross-model voter is not.

### AC-005: P2 findings never move the grade
A round whose consensus-passed findings are all P2 grades `A`.

### AC-006: Every finding carries exactly one disposition, from a producer that sees them all
For any round record — including rounds with no fix step and `auto_fix`-disabled runs — the count of
findings equals the count of non-null dispositions from the four-value enum. The producer is the
round-record writer, not the fix-selection step.

### AC-007: A rejection carries an authority, with a defined fallback
A `rejected` disposition without a SPEC AC id or docstring citation is invalid; when neither is
available the record must be `unresolved` with authority `no-contract`.

### AC-008: Only an AC-cited rejection is excluded from the grade
A rejection citing a SPEC acceptance-criterion id is excluded from `P0_count`/`P1_count`; any other
rejection still counts and sets `human_review_needed`.

### AC-009: Dispositions are ledgered and aggregable without double-counting
Disposition rows are appended such that a rejection rate is computable per review, with
per-invocation rows excluded by `finding_ref`.

### AC-010: Below-threshold churn skips the re-review, with the reason recorded
No reviewer is dispatched and the iteration record names the measured ratio and the threshold.

### AC-011: At or above threshold, exactly one structured reviewer is dispatched
One dispatch over the changed hunks, not the full lens set.

### AC-012: The churn threshold resolves from config with a documented default
Absent key → `0.20`; explicit value honoured; malformed value is a load-time error.

### AC-013: The churn ratio is well-defined over pinned endpoints and degenerate files
Created file → 1.0; deleted file excluded from the denominator; binary excluded and recorded;
renamed file measured against its post-rename path; aggregation is the maximum across touched files.

### AC-014: A stalled loop records the churn ratio on `no-progress`
The existing exit reason is used and its precedence is unchanged; the measured ratio is attached.

### AC-015: The confirmation pass uses the same mandatory lens set as round 1
A lens mandatory in round 1 is dispatched by the pass and written to the pass directory.

### AC-016: An oscillating hunk raises a `manual-only` P1 `spec_gap`
Identified by (path, normalized hunk content hash, nearest enclosing symbol); tagged `manual-only`.

### AC-017: The briefs carry both clauses and the test ban carves out test-targeted findings
The `design` brief states the public contract is fixed and out of scope; the auto-fix text bans
editing a test to resolve a non-test finding and permits fixing a finding whose target is the test.

### AC-018: The axis pilot records per-lens exclusive yield and prune candidates
The audit document reports, per lens, the groups no other lens produced, with severities and
dispatch counts, and names any zero-yield lens as a prune candidate.

### AC-019: `/hm:health` treats a disabled gate as `not_applicable`
With `rereview_churn_gate: false` the churn signals report `not_applicable`, `passed=True`, no
penalty.

## ❓ Open Questions

None.

## 🔍 Refinement Decisions

- **Round 1** — All four change families in scope. Rejection authority: AC id preferred, docstring
  fallback.
- **Round 2** — Goal recorded as Intent: stop running identical rounds until the budget is
  exhausted. Round 1 fans out once; repair rounds re-review narrowly; churn below threshold skips
  re-review; threshold configurable; oscillation surfaces as `spec_gap`.
- **Round 3** — Preset split on the cost axis. Confirmation pass is the sole full-lens sweep after
  round 1. Default threshold 20 % of touched-file LOC.
- **Round 4 (post-validation)** — `rejected` does not silently clear the grade; `churn-converged`
  dropped in favour of a ratio on `no-progress`.
- **Round 5 (axis change)** — The discovery axis is replaced wholesale by the experiment's six
  categories. A **single reviewer lens votes alone**, because cross-lens consensus would discard the
  fan-out yield that motivated the axis change; K=2 is retained for same-lens repeats and for
  cross-model voters, whose findings carry no `suggestion` and could otherwise block grade A with no
  repair path. Repair rounds revert to **one** structured reviewer, since a single voice now votes.
  Only an **AC-cited** rejection clears the grade. Production takes all nine lenses as mandatory;
  the conditional routing of `security`/`concurrency`/`tests` applies on **Side only**.
- **Post-validation corrections applied without a round** (defects, not choices): forced `confirm-2`
  removed; confirmation-pass lens parity added; disposition producer moved to the round-record
  writer; `no-contract` authority fallback added; churn endpoints, degenerate files and
  max-across-files aggregation specified; test-edit ban carve-out added; oscillation reduced to a
  `manual-only` report with a defined site key; gate-off N-A branch specified.
