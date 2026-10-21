---
type: spec
task_slug: hm-cost-p3
status: approved
created: 2026-10-21
tags: [cost, spec-stage, hm-check, bench]
test_framework: pytest
interview_rounds: 3
intent: HM-LIGHT-LANE
summary: Cut the hm arm's tier-1 spend — defaults written into the SPEC so approval is a stamp, an explicit `hm check --reuse` for wrapup's gate, and batched execute shell steps — then re-measure against a 10.0x bar.
---

# SPEC — hm-cost-p3

## Intent

After hm-cost-p2 the hm arm costs 12.21x plain on tier 1 (transcript price, $0.786 vs $0.064 per run).
`work-docs/RESEARCH-hm-cost-p3.md` places the spend: the DRI's approval turn 20% (it rewrites the SPEC to
settle Open Questions, mostly spec-validator critiques), execute 34% over 15.5 calls, wrapup 14% (a second
full `hm check` on a tree only the REVIEW doc changed), spec-validator 7%. This task removes the avoidable
round trips without removing a quality device, toward the phase-2 8x target.

## Outcomes

- The spec stage settles what it can itself: each critique or open slot gets the recommended option written
  into the SPEC as a default; Open Questions holds only WHY/WHAT the agent cannot decide. Critical critiques
  are still surfaced to the DRI, and an irreversible-decision or oracle critique is never settled as a default.
- `hm check --reuse` prints the last passing verdict for an identical tree, slug and options without running
  the gates; wrapup Step 1 uses it, and execute always runs a final check after the REVIEW doc is written.
- Execute chains independent shell steps with `&&` into one Bash call, except `hm check`, the RED run and
  steps marked as their own call (their exit codes drive the next step).
- Tier-1 transcript ratio ≤ 10.0 with hm pass rate ≥ plain.

## In-Scope Scenarios

- **S1 (normal):** Given spec-validator returns three critiques, when the spec stage records them, then each
  appears under Refinement Decisions with its default, Open Questions is empty, and the DRI's approval turn
  only stamps. A critical critique is still shown to the DRI; one that names an unlisted irreversible
  decision or a circular oracle goes to `irreversible_decisions` or Open Questions, never to a default.
- **S2 (normal):** Given execute's last `hm check` passed after the REVIEW doc was written, when wrapup Step 1
  runs `hm check --slug <slug> --reuse` on the same tree, then it prints that verdict with `reused: true`
  and runs no gate command.
- **S3 (edge):** Given a passing record, when any listed file changes, a file is added, HEAD moves with the
  tree unchanged, any `check.Options` field other than `root` differs (`red`, `green_ok`, `mutation`,
  `offline`, `harness`, `full`), the slug differs or the harness-maker version differs, then `--reuse` runs
  the gates fresh.
- **S4 (failure):** Given the last fresh run exited non-zero (no record is written), a hand-left failing
  record, no record, or an unwritable git dir, then `--reuse` runs fresh; a write failure warns on stderr
  and never changes the exit.

## Non-Goals

- Skipping wrapup memory, docs or Second Brain steps when nothing applies (not exercised by the bench).
- Fresh sessions between stages, and a light lane that drops stages or documents (5x).
- Changing `scripts/bench_light_lane.py`, its DRI prompts or its tasks.
- Automatic reuse in every `hm check`.

## Constraints

| constraint | value | why |
|---|---|---|
| test framework | pytest | project standard |
| reuse is opt-in | only `--reuse` reuses; execute's checks always run fresh | a stale pass mid-fix is the risk |
| reuse only a pass | a record is written only for exit 0 and reused only when its exit was 0 | a failure must be re-examined |
| fingerprint | sha256 over HEAD's commit id, the gate command list and `check.snapshot(root)` (listed tracked + untracked files and their digests) | the verdict also depends on HEAD (changed paths, RED) and on which gates run |
| compared options | every `check.Options` field except `root`, plus slug and harness-maker version | a narrower set let `--mutation` reuse a non-mutation pass |
| final execute check | unconditional, after the REVIEW doc; exit 1 from unresolved rows after the review cap goes to the DRI, and a disposition is never changed to pass the gate | otherwise wrapup's tree differs and B saves nothing |
| batching | `&&` chains only; never chain `hm check`, the RED run or an own-call step | a chained gate's exit is hidden by the next command |
| record location | `git rev-parse --git-path hm/check-verdict.json`, outside the work tree | storing it must not change the fingerprint |
| record writes | atomic write; failure to write warns on stderr and keeps the exit | project atomic-write rule |
| measurement | tier 1, claude-sonnet-5-5, 3 runs per cell, `--jobs 4`, on the final committed code | feedback_bench_jobs_parallel |
| published rows | the re-run's rows replace `docs/evals/results.jsonl`; the hm-cost-p2 rows move to `docs/evals/history/hm-cost-p2.jsonl` and its bar test reads them there | `summarize` refuses mixed SHAs; p2's bar must stay green |
| surface growth | held as the PLAN's `surface_allowance`, folded on main after land | project_surface_allowance_expires_at_wrapup |

## Irreversible Decisions

| id | decision | category | rationale |
|---|---|---|---|
| IRR-001 | `hm check --reuse` flag and a `reused: true` key on a reused line | public API/CLI contract | wrapup recipes and any script will call it |
| IRR-002 | verdict record `hm/check-verdict.json` in the git dir: `{slug, options, head, fingerprint, exit, line, harness_maker_version, at}` | schema/file format/storage layout | a later reader must parse it |
| IRR-003 | frozen eval rows per task at `docs/evals/history/<slug>.jsonl` | schema/file format/storage layout | bar tests of earlier tasks read them |

## Acceptance Criteria

### AC-001: spec stage writes defaults, Open Questions only for the DRI
The rendered spec stage (Claude and Codex) tells the agent to write each spec-validator critique and each
slot it can decide as a default under Refinement Decisions, and to keep Open Questions for WHY/WHAT it
cannot decide; it still surfaces every critical critique, never settles an irreversible-decision or oracle
critique as a default, and no longer says to record the critiques under Open Questions. Required phrases:
"under Refinement Decisions as a default", "surface every critical critique", "an irreversible-decision or
oracle critique is never a default", "Open Questions holds only what you cannot decide".

### AC-002: `hm check --reuse` reuses only an identical passing verdict
Over the golden scenario table (17 rows: every S3/S4 case), `hm check --reuse` runs no gate command and
prints the stored line with `reused: true` exactly when a record exists for the same slug, options, HEAD,
fingerprint and harness-maker version with exit 0; every other scenario runs fresh. A fresh exit-0 run writes the record outside the work tree, leaving
`check.snapshot` unchanged.

### AC-003: wrapup reuses, execute gates after the REVIEW doc
The rendered wrapup Step 1 runs `hm check --slug <slug> --reuse`; the rendered execute Step 6 writes the
REVIEW doc and "then always run `hm check --slug <slug>`", and says "never change a disposition to pass the
gate".

### AC-004: execute batches shell steps
The rendered execute stage says "Chain independent shell steps with `&&` in one Bash call" and "except
`hm check`, the RED run and any step marked as its own call".

### AC-005: the tier-1 re-run is measured against the 10.0x bar and its result recorded
Counted rows (pinned in `tests/fixtures/hm_cost_p3/harness_shas.json`, squash aliases by tree hash):
`summarize` verdict not `suspect`/`no_data`, transcript ratio ≤ 10.0 (rounded to 3 places), 3 runs per
tier-1 cell, all rows claude-sonnet-5-5, hm pass rate (capped/leaked counted as failures) ≥ plain.
The pass-rate guard sits at a 15/15 ceiling and grades code only: a green AC-005 is evidence about cost, not
proof that A or C kept SPEC quality.

**Result (2026-10-22): missed.** Transcript ratio 11.36 (CLI 10.27), every other guard held. The DRI
landed the task with the miss recorded; the 10.0 bar is not moved. The test pins the one violation, so a later
run that changes it fails until the record is updated.

### AC-006: hm-cost-p2's bar stays green after the rows are replaced
`docs/evals/history/hm-cost-p2.jsonl` holds the rows committed in `docs/evals/results.jsonl` at 022d6f2a
byte for byte, and `tests/integration/test_hm_cost_p2_bar.py` reads it and passes.

## Verification

| scenario | mode | test |
|---|---|---|
| S1 | unit (render) | `tests/unit/test_hm_cost_p3_templates.py::test_ac_001_spec_defaults` |
| S2, S3, S4 | unit (CLI on a temp git repo) | `tests/unit/test_hm_cost_p3_reuse.py::test_ac_002_reuse` |
| S2 | unit (render) | `tests/unit/test_hm_cost_p3_templates.py::test_ac_003_reuse_wiring` |
| — | unit (render) | `tests/unit/test_hm_cost_p3_templates.py::test_ac_004_batching` |
| all | integration (live bench rows) | `tests/integration/test_hm_cost_p3_bar.py::test_ac_005_tier1_bar` |
| — | integration | `tests/integration/test_hm_cost_p3_bar.py::test_ac_006_p2_history` |

## Open Questions

None.

## Refinement Decisions

- **Defaults chosen by the agent (veto to change):** "testable AC" counts non-superseded, non-judgment ACs;
  options compared for reuse are every `check.Options` field except `root`; the record
  also stores `harness_maker_version`, and a different version runs fresh; one record per worktree (the
  latest pass), no history; IRR-003's history file is the chosen way to keep p2's bar green.
- Intent: HM-LIGHT-LANE (round 1). Record location, 10.0 bar: DRI, round 1. Explicit `--reuse`: DRI,
  round 2. C (skipping spec-validator on small SPECs) dropped from this task: DRI, round 3 — unmeasurable on
  the bench, and its skip condition switched off the check for its own omission.
- spec-validator critiques (round of 2026-10-21, MAJOR_REVISION, 9 critiques) were settled as defaults by
  this SPEC's own rule: compared options widened to all `Options` fields; HEAD and the gate list joined the
  fingerprint; golden table grew from 9 to 17 rows; AC-001 keeps critical critiques visible and IRR/oracle
  critiques out of defaults; the final execute check is unconditional; batching excludes exit-driving steps;
  exact phrases replace unnamed helpers; the AC-005 ceiling is noted. The one critique the DRI owns — whether
  C belongs in this task — was asked (round 3), and C was dropped.
- AC-005 missed its pre-registered bar (11.36 > 10.0). Options put to the DRI: land with the miss recorded,
  drop B, or discard the branch. DRI, 2026-10-22: land with the miss recorded and the bar unchanged; AC-005
  was reworded to that record and re-approved.
