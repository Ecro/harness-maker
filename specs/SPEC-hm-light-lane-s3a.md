---
type: spec
task_slug: hm-light-lane-s3a
status: approved
created: 2026-10-15
tags: [harness-maker, spec, autopilot, cost, light-lane, execute, review, verify]
test_framework: pytest
tier: 2
interview_rounds: 0
lane: full
intent: HM-LIGHT-LANE
research_doc: "[[RESEARCH-hm-light-lane]]"
summary: "Stage 3a of HM-LIGHT-LANE: the light lane runs spec → execute (+ one light check) → wrapup, without review and verify stage turns"
---

# SPEC — hm-light-lane-s3a (stage 3a, fewer light stages)

## 🎯 Intent

On the 2026-10-14 bench (after stage 2b) a completed /hm: run cost about ×17 a plain run on small
tasks. By stage the spend was review 30%, spec 22%, execute 20%, verify 18% and subagents 10%. No
stage dominates, because the carried context is paid again in every stage turn, so removing whole
stage turns is the largest simple lever left. On those tasks review and verify caught nothing the
plain arm missed (plain passed 15/15 hidden tests). The user decided on 2026-10-15 that the light
lane runs spec → execute → **one** combined check, without separate `/hm:review` and `/hm:verify`
stage turns. Stage 3b (light execute and verify in subagents) comes later and is out of scope.

## 🌅 Outcomes

- **A trusted lane.** `light_lane.lane_of` returns `light` only when the SPEC frontmatter's `lane`
  is exactly `light`, `spec_machine.approval_state` is `approved` or `exempt`,
  `irreversible_decisions` is empty, and the approval stamp's `lane` (IRR-005, recorded by
  `approve` from the `.md` at approval time, human and `--exempt` alike) is also `light`. The
  approval hash covers only the machine yaml, so without that field a `full` → `light` edit after
  approval would earn the skip. A stamp without the field is `full`. Anything else, including an
  unreadable SPEC, is `full`.
- **Light SPECs with no irreversible decisions are stamped exempt.** When the DRI was not asked
  (the level is `auto_full`, or there is no question tool), Step 4 passed and the SPEC is
  `status: approved` with no open questions, `/hm:spec` Step 5 stamps a `lane: light` SPEC whose
  `irreversible_decisions` is `[]` with the Step 0 skip path's command. It never stamps exempt over
  a DRI who was asked and did not approve. The command is
  `hm spec_machine approve --yaml … --exempt`, so the trust rule also holds on unattended
  `auto_full` runs. A DRI approval is still stamped `human`. A non-empty list still turns `light`
  into `full` before Step 3 writes it, and `approve --exempt` refuses a SPEC whose list is not
  empty, so an exempt stamp never covers an irreversible decision. Decided 2026-10-15 by the DRI
  ("Approve + exempt light", Refinement Decisions).
- **The light check.** On a trusted light lane, `/hm:execute` ends with a light check (new
  `### Step 4.2`) after all PLAN phases are GREEN. It is deterministic and dispatches no reviewer
  or other subagent. Its first line runs `hm spec_machine approval-status` and skips the check
  unless the state is `approved` or `exempt` with no irreversible ids, the same rule the boundary
  applies. It runs:
  - the `reviewers.mechanical_checks` commands, when configured (review Phase 0);
  - verify **Check 2** (regression smoke), **Check 4** (unresolved high security findings) and
    **Check 6** (SPEC requirement), from partials that verify's `verify_checks.md.j2` also
    includes, so verify renders byte-identical and the text has one source. Under the partials'
    `light_check` flag, Check 2 has no guessed-gates `mark-pass` path (exit 3 is not a pass), and
    Check 6 has no BLOCKED box or 6a/6b prose;
  - `hm cli security-scan <checkout> --force` first, uncached, against the checkout that holds
    the change (`<WT>` when worktree is on, else `.`), in the background and bounded, as Check 2
    runs. A non-zero exit, or no `Security scan:` summary line, is a failed gate. Check 4 then
    reads only this scan's rows: the last N lines of that checkout's
    `.claude/observability/security/findings-<today>.jsonl`, N being the scan's own count;
  - review **Step 2**'s drift rule, from partials review also includes. Review keeps the sentence
    "reviewers still run on the actual diff" in `review.md.j2`, outside the shared text.
- **The record.** When every check passes (Check 6 may report `WARN`) and drift is `clean`, the
  light check writes a light-check record `REVIEW-{slug}-{date}.md` under
  `<checkout>/work-docs/`, the name review uses, with frontmatter `type: review`,
  `review_kind: light-check`, `task_slug`, `status: PASSED`, `created`, `drift_verdict` (review
  Step 2's block, `computed_at` from `date -u +%Y-%m-%dT%H:%M:%SZ`), `verification_key` (the
  relevant skip key after Check 2, from `hm observability.verification_cache key --mode relevant`)
  and `checks` (`mechanical`, `regression`, `security`:
  `pass` or `n-a`; `spec_requirement`: `pass`, `warn` or `n-a`; `structural: not-run`). Wrapup
  Step 3 and verify Check 1 read its `drift_verdict` unchanged, and `wrapup_land` stages it through
  the existing optional `REVIEW-{slug}-*.md` path.
- **Any non-pass writes no record, and review runs next.** No record is written when the check is
  skipped (untrusted lane, loop mode, or a diff that review's own rule reads as `full`: "well over
  five files"), when a check fails, when drift is not `clean`, or when today's file name already
  holds a real review. There is no repair round and nothing is deleted: Python rejects a stale
  record (below).
- **The skip.** Under autopilot, only execute's `hm autopilot_caps boundary` call may skip `review`
  and `verify`. It does so when `light_lane.light_check_passed(base, slug, since=marker.created_at)`
  holds. That requires a trusted light lane; no real REVIEW for the slug in the checkout; a newest
  light-check record with `status: PASSED` for this slug, `drift_verdict.result: clean` with this
  slug's `task_slug`, and `checks` passing (`regression` and `security` `pass`, `mechanical` in
  {pass, n-a}, `spec_requirement` in {pass, warn, n-a}); `drift_verdict.computed_at` with a zone,
  at or after the marker's `created_at`; a `verification_key` equal to
  `compute_relevant_skip_key(checkout)`; and a fresh verification cache marker for that key written
  by `run`, not `mark-pass`. A narrowed marker (`restore_pipeline` set) is not skipped: the human
  asked for review. The checkout is resolved as
  `approval_state` resolves it: the per-task worktree, else the base. With the default pipeline
  execute's boundary then reports `next_stage: wrapup`, which is human-gated: `halt_kind:
  merge_gate` and the marker is cleared, as verify's boundary does today. The JSON keys do not
  change; `reason` names the skipped stages. The ledger gets one new `stage_skipped` row
  `{from, skipped, to, reason: "lane light"}`, written only on a path that advances or ends (never
  before an objective-gate halt).
- **Fails closed.** When `light_check_passed` is false, at any other stage, or with no slug, the
  boundary is byte-identical to `e7dd6648`: same JSON, same ledger rows, same marker.
- **Typed stages and the loop are untouched.** A user who types `/hm:review` or `/hm:verify` runs
  them as today; any real review then disables the skip for the slug. Their commands, wrapup's and
  the loop's are byte-identical to the `e7dd6648` render.
- **Maker agrees.** `hm world_model digest`'s `next_stage` is `wrapup` when `light_check_passed`
  holds (the digest reads no marker, so it passes no `since`; the cache check still applies).
- **`hm cli security-scan --force`** maps to `scan_all(force=True)`; without the flag the command
  behaves as today.
- `/hm:loop` is unchanged: its `--per-iter-stages` list is explicit and Gate 0 requires a receipt
  from every listed stage. The light check skips itself in loop mode.

## 📋 In-Scope Scenarios

### S1: A checked light task goes from execute to wrapup under autopilot
**Given** an armed session with the default pipeline, an approved light SPEC with no irreversible decisions, and a PASSED light-check record computed after the marker on a fresh verification cache
**When** execute runs its boundary
**Then** the JSON has `proceed: false`, `halt_kind: merge_gate`, `next_stage: wrapup`
**And** the ledger has a `stage_skipped` row naming `review` and `verify`, then `gate_blocked` for `wrapup`

### S2: Everything else is byte-identical to today
**Given** a full or absent lane, an untrusted light lane, a light lane without a passing record, or a PASSED record at a stage other than execute
**When** that stage runs its boundary at any level and judgment verdict
**Then** the JSON, the ledger rows and the marker equal the `e7dd6648` output for the same inputs

### S3: A stale or contradicted record does not skip
**Given** a light SPEC and a light-check record that is not PASSED, names another slug, predates the marker, sits beside any real REVIEW for the slug, was written for a tree that has changed since (its `verification_key` is not the current key, even when a later Check 2 marked the new tree), reports drift or a check that did not pass, or a cache marker written by `mark-pass`
**When** execute runs its boundary
**Then** the next stage is `review`, as today, and no `stage_skipped` row is written

### S4: The skip respects narrowed and custom pipelines
**Given** a passing light check and a pipeline that ends at `verify`, is narrowed to `review`, or lists `[execute, verify, wrapup]`
**When** execute runs its boundary
**Then** the skip continues to the first stage after execute that is neither `review` nor `verify`; with none left, the boundary returns `pipeline_complete`, as at a pipeline's last stage
**And** a narrowed marker is not skipped (next stage `review`), and no `stage_skipped` row precedes an objective-gate halt

### S5: The light check runs the gates that must not be lost
**Given** a rendered execute command (Claude Code) and execute stage skill (Codex)
**When** the light check's text is read
**Then** it runs the configured mechanical checks, the forced security scan on the change's checkout (background, bounded, with a failure clause), verify Checks 2, 4 (on this scan's rows) and 6, and review Step 2's drift rule, and records the verification key Check 2 marked
**And** it dispatches no reviewer or other subagent

### S6: Any non-pass writes no record
**Given** a light check that is skipped, fails a check (a scan without exit 0 or its `Security scan:` line included), finds drift, or meets a real review under today's file name
**When** it ends
**Then** it writes no record and says review runs next

### S7: Wrapup accepts the light-check record
**Given** a record written by the light check, with worktree on or off
**When** wrapup Step 3 and verify Check 1 read it
**Then** `drift_verdict` is present with this slug's `task_slug`, so both pass with their `e7dd6648` text

### S8: Typed stages and the loop are untouched
**Given** a render of these answers before and after the change
**When** the review, verify, wrapup and loop commands, their reference files and the Codex review, verify and wrapup skills are compared
**Then** each is byte-identical to its `e7dd6648` render

### S9: Maker routes a checked light task to wrapup
**Given** a trusted light SPEC, a PLAN, a PASSED light-check record and a fresh verification cache
**When** `hm world_model digest` computes `next_stage`
**Then** it is `wrapup`; the same artifacts on a full SPEC, or with a stale cache, route as today

### S10: An unattended light SPEC is stamped exempt
**Given** a rendered spec command (Claude Code) and spec stage skill (Codex), and a SPEC whose `irreversible_decisions` is not empty
**When** Step 5 is read, and `hm spec_machine approve --exempt` runs on that SPEC
**Then** Step 5 stamps a `lane: light` SPEC with an empty list `exempt` with Step 0's command only when Step 4 passed, the SPEC is `status: approved` with no open questions, and the DRI was not asked (`auto_full`, or no question tool), never over a DRI who was asked
**And** the command refuses the non-empty list, writes no approval and exits non-zero

### S11: The light lane is bound to the lane the SPEC was accepted on
**Given** a SPEC approved or stamped exempt on `lane: full` whose `.md` is later edited to `lane: light`, or a light SPEC whose stamp predates the `approval.lane` field
**When** `light_lane.lane_of` reads it
**Then** the lane is `full`; it is `light` only when the stamp's `lane` and the `.md` `lane` are both `light`

### S12: A record counts only for the tree it checked
**Given** a PASSED light-check record from an earlier run, a later change to the tree, and a later Check 2 that marked the new tree while its run failed security and wrote no record
**When** execute's boundary or the digest reads it
**Then** neither skips: the record's `verification_key` is not the current relevant key

## 🚫 Non-Goals

- Stage 3b: running light execute or verify through `stage-delegate`, and lens results as verdict + path.
- Changing the full lane: its stages, gates, rounds and dispatches.
- Changing `/hm:loop`, its default `execute,review` stage list, or Gate 0.
- Auto-entering wrapup. It stays human-gated (`_HUMAN_GATED_STAGES`) on every lane.
- Removing or rewording review or verify. Typed, they run their full text on any lane.
- A new stage, a new harness.yaml key, or a `lane` field in the machine SPEC.
- A repair round inside the light check, or a change to execute's auto-advance gate.
- Running a second-opinion model on light. Configured models run only when `/hm:review` is typed.
- Verify Check 3 (structural delta) and probe A1 on light. The record says `structural: not-run`.
- Reading `work_docs.dir` other than `work-docs/` for the record (the digest's accepted limitation).

## ⚠️ Constraints

| Constraint | Value | Rationale |
|---|---|---|
| Test framework | `pytest` | Project standard (CLAUDE.md) |
| One reader | `light_lane.lane_of` and `light_lane.light_check_passed` in Python, used by the boundary and the digest | Two readers would disagree on a malformed SPEC |
| Fail closed | Any read error, unknown value, untrusted lane, stale cache, early `computed_at` or real review means no skip | A missing or stale check must never remove two stages |
| Boundary JSON | Same keys and types; the skip shows only in `next_stage`, `reason` and the ledger | Rendered prompts and Codex branch on these keys |
| Placement | Only `--current execute`; applied where `next_stage` is computed, after the cap, slug and judgment checks | Every existing halt keeps its precedence; other stages stay byte-identical |
| Single source | Checks 2, 4 and 6 and review Step 2's drift rule move into partials that verify, review and the light check include | A copy would drift; verify and review render byte-identical |
| Reference file | The Claude Code light-check text renders in `.claude/hm/execute-light-check.md`, read from the project root, never from `<WT>`; missing → STOP naming it | Same rule as SPEC-hm-light-lane-s2b; full-lane runs never read it |
| Generated-file frontmatter | The new file carries `generated_by`, `content_hash`, `source_template`, `harness_maker_version` | CLAUDE.md security rule |
| Supersedes | PLAN-hm-light-lane ADR-003 ("review keeps every lens on light") holds only for a typed `/hm:review`; review Step 2 is no longer the only writer of a `drift_verdict` (the rule text still has one owner) | User decision 2026-10-15 |
| Size | The Claude execute command grows by at most 1,000 characters; the size baseline is re-frozen with a BASELINE-DELTA if the aggregate ratchet requires | Lever 2: full-lane runs carry only a pointer |
| Registry | New execute headings (Step 4.2 and the included Check headings in the Codex skill) are classified in `step_sensitivity.py` | `test_step_sensitivity_registry.py` fails on an unclassified heading |
| Compatibility | Python 3.12; existing harnesses re-render through `/hm:make` with no migration; an old render's execute writes no record, so its boundary never skips | Mixed versions fail closed |

## 🔒 Irreversible Decisions

| Id | Decision | Category | Rationale |
|---|---|---|---|
| IRR-001 | Add `stage_skipped` to the autopilot ledger's closed event vocabulary, with fields `from`, `skipped`, `to`, `reason` | schema/file format/storage layout | Once rows exist the name stays readable forever, as `advanced` and `objective_proposed` do; `/hm:health`'s smoke denominator counts every event |
| IRR-002 | The light-check record is `REVIEW-{slug}-{date}.md` under the change's checkout, with `review_kind: light-check`, `status: PASSED` and review's `drift_verdict` | schema/file format/storage layout | Wrapup commits it, so it persists in history. The boundary, the digest, wrapup Step 3 and verify Check 1 read it, and a reader may not later drop `review_kind` |
| IRR-003 | Add the generated file `.claude/hm/execute-light-check.md`, the name the execute command reads | schema/file format/storage layout | Renaming it needs a retire step for copies on disk (as SPEC-hm-light-lane-s2b IRR-001) |
| IRR-004 | Add `--force` to `hm cli security-scan`, mapping to `scan_all(force=True)` | public API/CLI contract | Rendered stage text calls it, so removing or renaming the flag breaks every harness rendered with it |
| IRR-005 | Add the optional field `lane` to the SPEC approval stamp (`approval.lane`), the `.md` `lane` when `approve` runs (human and `--exempt`) | schema/file format/storage layout | Every new stamp carries it and the light lane trusts only a `light` one; removing it later turns every light SPEC full. Additive and outside the content hash, so no stamp is released; a stamp without it reads `full` |

## ✅ Verification Criteria

| Scenario | Verification mode | Test name / manual step |
|---|---|---|
| S1 | unit (CLI) | `tests/unit/test_autopilot_caps_light_lane.py::test_light_execute_skips_review_and_verify` |
| S2 | unit (CLI, differential) | `tests/unit/test_autopilot_caps_light_lane.py::test_full_lane_boundary_matches_e7dd6648` |
| S3 | unit (CLI) | `tests/unit/test_autopilot_caps_light_lane.py::test_no_passing_record_no_skip` |
| S4 | unit (CLI) | `tests/unit/test_autopilot_caps_light_lane.py::test_skip_respects_pipeline_shape` |
| S5 | unit (render, CLI) | `tests/render/test_render_light_lane_s3a.py::test_light_check_runs_the_kept_gates`, `tests/unit/test_cli_security_scan_force.py::test_force_bypasses_the_fresh_scan_cache` |
| S6 | unit (render) | `tests/render/test_render_light_lane_s3a.py::test_light_check_fails_closed` |
| S7 | unit | `tests/unit/test_light_lane.py::test_record_satisfies_wrapup_and_verify` |
| S8 | unit (render, differential) | `tests/render/test_render_light_lane_s3a.py::test_typed_stages_and_loop_unchanged` |
| S9 | unit | `tests/unit/test_light_lane.py::test_digest_routes_checked_light_task_to_wrapup` |
| S11 | unit | `tests/unit/test_light_lane.py::test_lane_is_bound_to_the_approved_lane`, `tests/unit/test_light_lane.py::test_the_stamp_lane_releases_no_stamp_and_keeps_the_cli_output` |
| S12 | unit (CLI) | `tests/unit/test_autopilot_caps_light_lane.py::test_probe_b_a_later_failed_run_does_not_skip`, `tests/unit/test_light_lane.py::test_record_is_bound_to_the_checked_tree` |
| S10 | unit (render, CLI) | `tests/render/test_render_light_lane_s3a.py::test_spec_stamps_light_exempt`, `tests/unit/test_spec_approve_exempt.py::test_exempt_refuses_irreversible_decisions` |
| Outcome (reader) | unit | `tests/unit/test_light_lane.py::test_lane_of`, `tests/unit/test_light_lane.py::test_light_check_passed` |
| Outcome (pointer) | unit (render) | `tests/render/test_render_light_lane_s3a.py::test_execute_points_at_the_light_check` |
| Outcome (ledger) | unit | `tests/unit/test_autopilot_caps_light_lane.py::test_stage_skipped_is_a_ledger_event` |

### AC-001: The lane reader trusts light only on an accepted SPEC with no irreversible decisions
### AC-002: A passing light-check record is recognised only for its own slug and checkout, and never beside a real review
### AC-003: A checked light execute skips review and verify at the boundary
### AC-004: Every other boundary is byte-identical to e7dd6648
### AC-005: The skip respects narrowed and custom pipelines
### AC-006: A missing, stale or contradicted record does not skip
### AC-007: Execute points at the light check, which renders as a reference file
### AC-008: The light check runs the kept gates and dispatches no subagent
### AC-009: Any non-pass writes no record
### AC-010: The light-check record satisfies wrapup Step 3 and verify Check 1
### AC-011: Typed review, verify, wrapup and the loop are byte-identical
### AC-012: The digest routes a checked light task to wrapup
### AC-013: stage_skipped is a ledger event that does not count as an entered stage
### AC-014: A light SPEC with no irreversible decisions is stamped exempt, and an exempt stamp refuses irreversible decisions
### AC-015: The light lane is bound to the lane the SPEC was accepted on
### AC-016: A light-check record counts only for the tree it checked, with its own checks passing

## ❓ Open Questions

- `hm cli security-scan --force` walks the whole checkout, queries OSV.dev and may try an LLM pass
  for prompt injection (it falls back to regex). Uncached, its wall time on a large repo is
  unmeasured. (Check 4 in the light check reads only this scan's rows, the last N lines of today's
  findings file, N being the scan's own count; verify's Check 4 still reads the whole file.)
- Finding rows carry no timestamp, so "this scan's rows" is by count, not by time (review item K
  asked for `timestamp ≥ scan start`). A second scan of the same checkout appending at the same
  moment would interleave; nothing runs one there.
- Whether removing two stage turns moves `hm_cost_ratio_small` toward ≤ 5 is unmeasured until the
  stage 4 bench is re-run on this change.

## 🔍 Refinement Decisions

- Interview not re-run: the scope and the "one combined check, no review/verify turns" shape are
  the user's 2026-10-15 decision; the DRI said on 2026-10-14 to run each stage on the recommended
  option. Defaults below are agent decisions.
- Lane `full`: about 14 files, and four irreversible decisions.
- Q1, where the check lives: a final step of `/hm:execute` (Step 4.2), not a new stage. A new stage
  would add a stage turn, which is the cost being removed. No reviewer dispatch: on the baseline
  tasks review caught nothing plain missed, and the security lens's mechanical part is kept
  through a forced `security-scan` + Check 4.
- Q2, how the pipeline skips: in Python at execute's boundary only, gated on a record Python can
  check for freshness, not on the lane alone. A skipped, failed, stale or contradicted check
  falls back to today's review path. The skip is recorded as `stage_skipped`.
- Q3, what must not be lost: mechanical checks, regression (Check 2), security (forced scan +
  Check 4), SPEC requirement (Check 6) and the drift verdict run in the light check. Wrapup's own
  Step 2 re-verification, Step 3 drift check, Step 3.5 write-back with the judgment-AC binding, and
  the Step 6/7 land hold for an unapproved SPEC are unchanged. Dropped on light: Check 3 (the
  harness's structural score, not the change), probe A1, Check 5 (loop-only), every review lens,
  the second-opinion models.
- Q4, runtimes: Claude Code and Codex call the same boundary, so they skip alike; Codex inlines the
  light check. Cursor has no auto-advance (as today): it runs the same execute command, and its
  banner already offers `/hm:wrapup`. `/hm:loop` is deliberately unchanged, because its stage list
  is explicit and Gate 0 exists to catch a skipped review (`loop-body-skipping-review-stage`).
- Q5, wrapup: unchanged. It needs a `drift_verdict` (the record supplies it) and a fresh
  verification marker (Check 2 in the light check writes it; Step 2 re-runs the suite otherwise).
  It reads no verify receipt outside loop mode. Its sentence "Review is the single owner (ADR-006)"
  stays, since the light check runs review's own drift partials.
- spec-validator pass 1: MAJOR_REVISION (10 findings), all folded in on the coordinator's
  instruction. Stale records are rejected in Python (fresh cache, `computed_at` ≥ marker); the lane
  is trusted only on an approved or exempt SPEC with no irreversible decisions; the scan is forced
  on the change's checkout (IRR-004); any real review disables the skip; the record follows the
  worktree; Checks 2/4/6 and the drift rule are shared partials; Check 6 `WARN` still writes the
  record; the repair round, the deletion protocol, the execute-gate change (old AC-014) and the
  10-path threshold were dropped in favour of "any non-pass writes no record" and review's own
  diff-size rule; AC-004's domain gained a full lane with a PASSED record and a PASSED record at
  review or verify.
- Record status stays `PASSED`, not `APPROVED` (coordinator, 2026-10-15): nothing graded the
  change, and `APPROVED` would make every reader treat it as a review.
- Evaluated, not irreversible: the boundary's `next_stage` may now skip pipeline entries from
  execute. Its keys are unchanged, an old render's execute writes no record (so no skip), and a
  revert restores it. Dropping review lenses on light is not a permission-boundary change; it is a
  policy the revert undoes.
- Decided 2026-10-15 by the DRI ("Approve + exempt light" on the decision card): at `auto_full` an interviewed
  light SPEC was unapproved (the spec gate is answered without an approval, and only the skip path
  stamped `exempt`), so it read as `full` and the bench arm would see the saving only on skip-path
  tasks. The options were to accept that (the trust rule wins) or to stamp `exempt` on a light
  SPEC with an empty irreversible list. The DRI chose the second, the card's recommended option
  (Outcomes, AC-014): the four lane criteria and the empty list already say nothing needs a
  human, and `exempt` is the stamp Step 0 uses for exactly that. `approve --exempt` now refuses a
  non-empty list, which `approval_state` would have read as `invalid` anyway. Undoing it later is
  a revert of the amendment commit and the Step 5 sentence; nothing else depends on it.
- Evaluated, not irreversible: the exempt stamp on light. It is the existing `exempt` kind, no new
  format or key; a revert stops new stamps, and a stamp already written means what Step 0's does.
- Review of 2026-10-15 (two reviews, no P0; dispositions decided by the coordinator): the skip
  is bound to what was approved (IRR-005, AC-015) and to what was checked (`verification_key`,
  `checks`, a `run` marker, a zoned `computed_at`: AC-016); the forced scan has a failure clause
  and Check 4 reads its own rows; Step 5's exempt branch names its three conditions; the
  partials' `light_check` flag drops the guessed-gates and BLOCKED paths; a narrowed marker is
  not skipped; `stage_skipped` is written only on a path that advances or ends; the typed-run
  banner names wrapup after a passing light check. Deferred to the PLAN's follow-ups: a Python
  `hm light_check run` for the deterministic gates, and a `remeasure_on` note for "drop review on
  light". The DRI re-approves this SPEC: the amendment invalidates the 2026-10-15 stamp.
- Work stays on the session's designated branch instead of an `hm/<slug>` task worktree, as in
  stages 1, 2a and 2b.
