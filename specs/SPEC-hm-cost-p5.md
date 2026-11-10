---
type: spec
task_slug: hm-cost-p5
status: approved
created: 2026-11-10
tags: [cost, spec-stage, spec-validator, spec-machine, bench, intent-target]
test_framework: pytest
interview_rounds: 1
intent: HM-LIGHT-LANE
summary: The spec check decides whether spec-validator runs by default (skipped for a SPEC of at most 8 live ACs unless the DRI picks it at approval), the cost target moves from 5x to 8x in the intent and the bench, and tier 1 is re-measured (plain / hm) against the 8.0x bar.
---

# SPEC — hm-cost-p5

## Intent

SPEC-hm-cost-p4 measured spec-validator for the first time. With the step removed (`hm-novalidator`), the
same harness cost 7.67x plain on tier 1 and 8.42x on tier 2, against 10.24x on both tiers with it; hidden
tests were 15/15 and 21/21 in every arm, and the blind judge tied (tier 1: 3.56 with, 3.67 without; tier 2:
3.33 with, 3.44 without). The 36 SPECs those hm runs wrote had 2 to 8 ACs, and 26 of them declared an
irreversible decision. So on a SPEC of that size the step costs about 2.6x (tier 1) and 1.8x (tier 2) of a
plain run and changed no measured outcome. Rows, table and the per-SPEC counts:
`/mnt/project-files/hm-cost-research/RESULTS-spec-validator-ab.md`.

The limit of that evidence, from the same file: both tiers are saturated on the hidden tests, so the
bench cannot show what the validator catches. In this repository it changed the SPEC both times it ran on
a real task: 11 critiques on SPEC-hm-cost-p4 (9 ACs), and 9 on this SPEC (6 ACs), one of them critical
(the target is bound to the HM-LIGHT-LANE approval and repeated in its rule text). What it caught both
times is what a hidden test cannot see: stale copies of a changed fact elsewhere in the repository, and
tests that cannot fail.

The DRI decided on 2026-11-10 (cards) to skip spec-validator by default on small SPECs while keeping it
one choice away at approval, to revise the HM-LIGHT-LANE cost target from 5x to 8x, and to record p4's
10.243.

The target is not a one-line edit: `scripts/bench_light_lane.py` mirrors it as `TARGET`; the verdict
tests, the pinned report and scorecard text and the published results carry "target 5"; and
`intent/HM-LIGHT-LANE.md` states it three times (statement "22 → 5 이하", proposed outcome "5배 이하",
the pre-registered rule "배수 ≤ 5") and binds its approval to it (`approved_target: 5`;
`world.derive` compares the approval hash against the metric's current target, so editing the target
alone leaves the objective unapproved).

This task makes the CLI decide the default, so the stage reads one field instead of applying a rule in
prose, gives the DRI an approval choice that runs the validator regardless, moves the target everywhere
it is mirrored, and re-measures tier 1.

## Outcomes

- `hm spec_machine check --all` prints `"validator": "skip"` or `"validator": "run"`. The spec stage's
  Step 4.6 dispatches spec-validator on `run`, or when the DRI chose "Approve after spec-validator".
- A SPEC with at most 8 live ACs gets `skip`; a larger one gets `run` and the advisory pass is unchanged.
- The interview's approval question offers both "Approve this SPEC and end interview" and "Approve after
  spec-validator", so running the validator on a small SPEC costs the DRI one tap and nothing by default.
- The rendered spec stage is not longer than it is today (no surface allowance).
- `.claude/intent.yaml` `hm_cost_ratio_small.target` is 8 and the bench's `TARGET` is 8.0; the report,
  scorecard and published results say "target 8".
- `intent/HM-LIGHT-LANE.md` says 8 wherever it said 5, its spec-validator scope line states the new rule,
  and its approval is valid again (`approved_target: 8`, re-stamped by the DRI).
- Tier 1 is re-measured once (plain and hm) and the verdict against the 8.0x bar is recorded in this SPEC,
  met or missed.
- `hm_cost_ratio_small` has p4's 10.243 and this task's value on record, both under the 8x definition.

## In-Scope Scenarios

- **S1 (normal, small SPEC).** Given a valid SPEC with 3 live ACs, when Step 4 runs
  `hm spec_machine check --all`, then the one-line result carries `"validator": "skip"` and the stage goes
  to Step 5 without dispatching spec-validator.
- **S2 (normal, larger SPEC).** Given a valid SPEC with 9 live ACs, when Step 4 runs the check, then the
  result carries `"validator": "run"` and Step 4.6 makes its one advisory pass as today.
- **S3 (edge, superseded ACs).** Given a SPEC with 11 ACs of which 3 are superseded, when the check runs,
  then the 8 live ACs give `skip`.
- **S4 (failure, unloadable yaml).** Given a machine.yaml that does not load, when the check runs, then it
  exits 1 as today and prints no `validator` field; the stage fixes and reruns before it reads one.
- **S6 (small SPEC, DRI asks for the validator).** Given a SPEC with 3 live ACs and a DRI who chose
  "Approve after spec-validator", when Step 4 prints `"validator": "skip"`, then Step 4.6 still makes its
  advisory pass, and the stamp follows it under the existing rule (a critical critique is surfaced first).
- **S5 (verdict boundary).** Given tier-1 rows whose judged hm/plain ratio is 8.000 with hm's pass rate at
  least plain's, when the bench reports, then the verdict is `met` and names target 8; at 8.004 it is
  `missed`.

## Non-Goals

- Removing the spec-validator agent, or the `hm-novalidator` bench arm (it stays for a later measurement
  on SPECs above the threshold).
- A `harness.yaml` knob for the threshold. One constant; a later measurement moves it.
- Changing what spec-validator checks, or making it blocking.
- Measuring spec-validator on SPECs above 8 ACs. No bench tier writes one yet.
- Fixing the eval judge's two artefacts (the golden file missing from the judge diff, every AC id redacted
  to one token). Reported to the DRI as a separate task.
- Tier 2 or tier 3 re-runs.

## Constraints

| Constraint | Source |
|---|---|
| Test framework: pytest; unit tests under `tests/unit/`, mock LLM calls | CLAUDE.md |
| Python only, `mypy --strict`, ruff, atomic writes | CLAUDE.md |
| The spec stage does not grow: no `surface_allowance` in the PLAN (another in-flight PLAN holds one, and two cannot coexist) | thread "토큰 외 hm 개선점 구현", 2026-11-10 |
| Rendered Claude and Codex variants change together | CLAUDE.md |
| `check --all` keeps printing one line when no gate failed (the caller re-reads every byte on later turns) | HM-LIGHT-LANE lever 4 |
| Eval: claude-sonnet-5-5, tier 1, 5 tasks × 3 runs per arm, arms plain and hm, same budget per arm | SPEC-hm-eval |
| The first complete batch counts; a miss is recorded, never rerun into a pass | DRI rule, hm-cost-p4 |
| Intent-layer writes are the DRI's. Approved on cards: target 8, recording 10.243. Still needing the DRI's yes, with the exact text or arguments shown: the HM-LIGHT-LANE text edits and `hm intent approve HM-LIGHT-LANE`, and recording this task's new value | intent layer |
| Record metric values after the target change (the definition hash includes the target) | `hm intent metric record` |

## Irreversible Decisions

| id | decision | category | rationale |
|---|---|---|---|
| IRR-001 | `hm spec_machine check --all` output gains a `validator` field with values `skip` and `run` | public API/CLI contract | The spec stage reads it; additive, but a consumer that pins the exact one-line output sees a new key |

Two DRI decisions this task carries out are reversible by a one-line change and so are not listed above:
the skip rule (one constant) and the target (one intent field). Both are under Refinement Decisions.

## Acceptance Criteria

### AC-001: the validator verdict follows the live AC count
`spec_machine.validator_verdict(model)` returns `skip` when the SPEC has at most 8 ACs that are not
superseded, else `run`. Irreversible decisions do not change it. The golden rows cover 0, 1, 8 and 9 live
ACs, superseded ACs, and a small SPEC with irreversible decisions.

### AC-002: check --all prints the verdict
When the yaml loads, `hm spec_machine check --all` includes `"validator"` in its output with the value
AC-001 defines. Key sets: the one-line passing form has its previous keys plus `validator`; the long form
for a loaded yaml has its previous keys plus `validator`; the long form for a yaml that does not load is
unchanged and has no `validator`. The passing form is still one line, every other value is what the same
fixture printed before, and exit codes are unchanged.

### AC-003: the stage and the agent state the new rule and the stage does not grow
In the rendered spec stage for Claude Code and for Codex:
- Step 2's approval question offers the two labels "Approve this SPEC and end interview" and "Approve
  after spec-validator".
- Step 4.6's body (heading excluded) makes the advisory pass conditional on the literal
  `"validator": "run"` from Step 4 or on the DRI's choice "Approve after spec-validator"; it no longer
  mentions Step 0 skipping the interview, and `irreversible_decisions: []` no longer conditions the
  dispatch.
- The stage has at most as many characters as the same render at main fe6fada6.

In the rendered spec-validator agent for both targets, Triggers names the same two conditions and no
longer says it runs "only when the SPEC declares or implies an irreversible decision, or is not a Step-0
skip-path SPEC"; the agent body has at most as many characters as at fe6fada6.

### AC-004: the sensitivity registry carries the measurement and the same threshold
The `step_sensitivity` entry for spec `Step 4.6` stays `TUNE`. Its evidence states the bench A/B with
`n=` per arm and the words "Side-preset only", and the two real-repository runs. Its note contains
"≤ 8 live ACs", where 8 is `spec_machine.VALIDATOR_SKIP_MAX_ACS`, and no longer says "conditional on
irreversible decisions". Its `measure_cmd` is the bench run that reproduces the A/B (arms `hm` and
`hm-novalidator`), not the stage-agent ledger.

### AC-005: the bench judges against target 8
`bench.TARGET` is 8.0 and equals `.claude/intent.yaml` `hm_cost_ratio_small.target`. `summarize` compares
the unrounded judged ratio with the target: `met` at 8.000, `missed` at 8.004, and both reasons name
target 8. The three pinned report texts under `tests/unit/fixtures/hm_eval/` (`RESULTS.md`,
`scorecard.txt`, `pre_eval_metric_block.txt`, all output of the current report code) equal their content
at main fe6fada6 with `target 5` replaced by `target 8` and nothing else changed; the report and
scorecard hash pins in `test_tier_one_and_two_hashes_are_unchanged` move by that replacement only. The
committed `docs/evals/RESULTS.md` and the README block equal what `publish` writes from the committed
rows. Texts that record a past result keep "5": SPEC-hm-cost-p4's recorded result and the CHANGELOG.

### AC-006: the tier-1 re-run is measured against the 8.0x bar and its result recorded
`tests/fixtures/hm_cost_p5/batches.json` lists every tier-1 batch run for this task in order; the first
complete one counts. Complete is mechanical: for plain and hm, every (task, arm) cell of the 5 tier-1
tasks has exactly 3 rows and none has an unusable status (claude-sonnet-5-5); the fixture's `complete`
flag must agree with that. An incomplete batch stays in the list with its rows, so what was discarded is
visible. The bar is the metric's own rule at target 8: `summarize(counted rows)` returns `met`, which
needs the unrounded judged ratio (the larger of the CLI and transcript ratios) ≤ 8.0, hm's pass rate ≥
plain's, and no capped or leaking run. Whatever the first complete batch returns is the result: `missed`,
`suspect` and `no_data` are recorded as such and not rerun (a rerun after `suspect` or `no_data` is a new
DRI decision). The test asserts that the result recorded below (verdict, and the ratio rounded to 3
places when there is one) matches the counted rows. p4's rows move to
`docs/evals/history/hm-cost-p4.jsonl` and p4's bar test reads them there. Recorded, not gated: how many
of the 15 hm runs dispatched spec-validator (expected 0), per-stage cost, judge scores.

**Result (2026-11-10): met.** Judged ratio 7.563 (transcript price; CLI 6.98) at harness 9bba5174cd88, down
from 10.243 at 3063ad33. Pass rate 15/15 in both arms, no capped or leaking run. The one batch run counts;
nothing was discarded or rerun. spec-validator was dispatched in 0 of the 15 hm runs (every SPEC had at
most 8 ACs and the scripted DRI does not pick the validator-first approval); code-reviewer ran in 15 of
15. Per stage, hm's spec fell from $0.206 to $0.130 per run and execute from $0.236 to $0.210; approve
($0.017) and wrapup ($0.069) did not move. Turns per run 19.1 → 15.1, wall time 141 s against plain's
15 s. Judge (blind, one sample per run, tier-1 rubric): overall plain 4.33, hm 3.73; the gap to plain
(−0.60) is where it was (−0.58). New lint and type errors per run: ruff 0.20 (plain 0.00), mypy 0.13
(plain 1.53). The number is the cost of the default path: a DRI who picks "Approve after
spec-validator" pays for the pass.

### AC-007: the HM-LIGHT-LANE objective states target 8 and its approval is valid
`intent/HM-LIGHT-LANE.md` reads "22 → 8 이하" in its statement, "8배 이하" in its proposed outcome and
"배수 ≤ 8" / "배수 > 8" in its pre-registered rule; no "5 이하", "5배" or "≤ 5" remains. Its scope line
on spec-validator reads "spec-validator: AC 8개 이하 SPEC 은 기본 생략, 승인 때 DRI 가 고르면 실행
(DRI 2026-11-10)" instead of "light 에서도 돈다". `world.derive` reports
its approval valid against the metric's target 8, and `approved_target` is 8.

## Verification

| scenario | mode | test |
|---|---|---|
| S1, S2, S3 | unit | AC-001, AC-002 |
| S4 | unit | AC-002 |
| S1, S2, S6 | unit (render, both targets) | AC-003 |
| — | unit | AC-004 |
| S5 | unit | AC-005 |
| — | unit (reads the committed intent file) | AC-007 |
| all | live eval (≈$10, run once) | AC-006 |
| metric records | manual, DRI-approved `hm intent metric record` | — |

## Open Questions

none

## Refinement Decisions

- spec-validator (DRI card, 2026-11-10): skip on small SPECs only; keep it otherwise.
- Skip mode (DRI card, 2026-11-10, after the validator pass on this SPEC): "기본 생략, 승인 때 선택" —
  default skip at ≤ 8 ACs, with a validator-first choice on the approval question. The DRI saw the
  alternatives "plain skip" and "never skip, cut the validator's cost instead".
- Criterion (DRI card, 2026-11-10): "AC 8개 이하면 생략" — at most 8 ACs, irreversible decisions do not
  matter. The DRI saw the alternative "no irreversible decision and at most 8 ACs" and that it would skip
  1 of 15 tier-1 SPECs.
- Bar (DRI card, 2026-11-10): 8.0, pre-registered before any code; the alternative was 9.0.
- Trade-off accepted with the criterion: on a SPEC of at most 8 ACs, an irreversible decision the ACs
  imply but do not list is caught only by the DRI's approval. Evidence for accepting it: 36 SPECs of 2–8
  ACs, no difference in hidden tests or judge with and without the step. Values recorded under target 5
  belong to the prior metric definition.
- Target (DRI card, 2026-11-10): 5x → 8x. p4's 10.243 is recorded (DRI card "기록").
- Default (agent): the CLI decides and the stage reads one field. The measured failure mode of prose rules
  in this harness is that the model does not apply them (eval 3: the light check procedure was followed in
  0 of 33 runs); a printed verdict is the cheaper thing to follow.
- Default (agent): the threshold is 8 because that is the largest SPEC the measurement covered; nothing
  above it was measured, so nothing above it is skipped.
- Default (agent): live ACs are counted, not all ACs, so a long-lived SPEC is judged by what is in force.
- Default (agent): the Step 0 clause is removed instead of kept beside the new one. Behaviour change: a
  Step 0 SPEC always has ≤ 1 AC, so it still skips.
- Default (agent): the bar is the metric's own verdict, so "met" in this SPEC and in the published report
  cannot disagree.
- spec-validator on this SPEC (9 critiques, 1 critical; settled here as defaults unless noted, the DRI may
  veto): AC-007 added for the HM-LIGHT-LANE text and approval (critical; the re-stamp itself is the
  DRI's); AC-003 extended to the agent's Triggers and tightened to literal tokens; AC-004 asserts the stale
  note is gone and moves `measure_cmd` to the bench; AC-005's pinned texts are checked against the base
  commit with one substitution; AC-006 defines completeness from the rows and records `suspect` /
  `no_data` instead of rerunning; AC-002 states the key sets; the Intent now quotes the bench's limit and
  the two real-repository runs, and the counts are in the cited file.
- Default (agent): the validator-first choice lives on the approval question, because that is the one
  point where the DRI is always asked, including when Maker advances into execute in the same session.
- Default (agent): no hm-novalidator arm in the re-run. On tier 1 it is now the same procedure as hm, and
  the arm would add about $5 for no information.
