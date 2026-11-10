---
type: review
task_slug: hm-cost-p5
status: complete
created: 2026-11-10
spec: "[[SPEC-hm-cost-p5]]"
plan: "[[PLAN-hm-cost-p5]]"
summary: One review round by code-reviewer (codex second opinion skipped, CLI not installed). No P1; one P2 and three P3 fixed, one P2 and one P3 rejected with an authority.
---

# REVIEW — hm-cost-p5

Reviewer: `code-reviewer` on the staged diff against fe6fada6, with the SPEC, the PLAN and the tests.
Second opinion: `codex` → `skipped` ("CLI not installed: codex"); warn and proceed.

## Findings

| id | severity | file:line | finding | disposition | authority |
|---|---|---|---|---|---|
| R1-1 | P2 | src/harness_maker/templates/stages/spec.md.j2 (Step 5) | A DRI who picked "Approve after spec-validator" was stamped right after the pass even when it raised a critical critique, so the approval predated the critique. Fixed: Step 5 stamps the validator choice only "with no critical critique"; otherwise the SPEC stays unstamped and the critique is surfaced | accepted | SPEC S6 |
| R1-2 | P2 | src/harness_maker/templates/stages/spec.md.j2 (Step 4.6) | "It gates nothing" and the dispatch note "it returns JSON critiques" were cut to pay for the new text | rejected | SPEC AC-003 (the stage may not grow) and PLAN ADR-003; the step still opens "One advisory pass", Step 5 reads no verdict, and the agent body keeps "You never block" (spec-validator_body.md.j2:11); the output format is the agent's own contract |
| R1-3 | P3 | src/harness_maker/templates/stages/spec.md.j2 (Step 4.5) | "Read its `quality`." has a looser referent than "from that output" | rejected | same referent as the base text (the command Step 4 just ran); AC-003 budget |
| R1-4 | P3 | tests/unit/test_hm_cost_p5_templates.py | No test covered Step 5 for S6. Fixed: the stage test asserts the Step 5 clause and that it precedes the stamp command | accepted | SPEC S6 / AC-003 |
| R1-5 | P3 | tests/integration/test_hm_cost_p5_bar.py | The ratio was matched anywhere in the SPEC; the counted batch's path was asserted without a reason. Fixed: the regex captures the ratio on the Result line; the path assertion stays with its reason (the counted batch is what RESULTS.md is published from) | accepted | SPEC AC-006 |
| R1-6 | P3 | src/harness_maker/step_sensitivity.py | `measure_cmd` ran tier 1 only while the evidence cites tier 2. Fixed: `--tier all` | accepted | SPEC AC-004 |

## Re-pins forced by the change (found by the full suite, not by the reviewer)

| test | why it moved |
|---|---|
| tests/unit/test_spec_machine_check_all.py | the one-line payload gains `validator`; the test now asserts its value |
| tests/unit/light_lane_s3c_fixture.py, tests/unit/test_overhaul_p1_kept.py (`_without_approval`) | goldens captured from older modules; the additive key is dropped before comparing, as `approval` already was |
| tests/unit/test_bench_light_lane.py (two verdict cases, the recorded-value case) | boundary cases moved from 5 to 8 with the same shape (8.004 missed; CLI 7.0 vs transcript 8.2 missed) |
| tests/unit/test_bench_tier3.py (report pin) | "target 5" → "target 8"; test_hm_cost_p5_target.py proves the old pin is recovered by putting the 5 back |
| tests/unit/test_agent_body_partials.py (spec-validator sha) | Triggers reworded |
| tests/unit/test_hm_cost_p4_bench.py | "spec-validator" now also appears in Step 2's approval label, so the arm test checks the removed step (`## Step 4.6`) and its dispatch instead of the bare name |
| four synthesize snapshots | regenerated (`tests/snapshot/regenerate.py`) |

`tests/render/test_spec_validator_dispatch.py::test_ac_007_approval_cannot_read_the_verdict` failed on
the first full run because `spec_machine`'s new comments named the critic. The comments were reworded;
the test is unchanged. `validator_verdict` decides a dispatch and `approve` still takes nothing from the
critic.

## Found at Bind, outside this SPEC

`hm spec_machine mark-tested --ac AC-NNN` with empty `test_ids` (SPEC-hm-cost-p4's discovery) collects the
whole repository and binds every test named `test_ac_NNN*`, whichever SPEC it belongs to: it recorded
102 tests for AC-001 here, 10 of them this SPEC's. The bench projects have one SPEC each, so p4's
measurement could not show it. The yaml was restored and each AC bound with explicit `--test-id`. The
discovery needs a scope (the task's changed test files, as `check --red` already uses); that is a
follow-up fix, not part of this SPEC.

## Gate

GATE_PLACEHOLDER
