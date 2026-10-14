---
type: review
task_slug: hm-light-lane-s2
status: APPROVED
created: 2026-10-14
reviewers_invoked: [code-reviewer, security-reviewer, concurrency-reviewer, test-reviewer]
consensus_method: cross-check
run_id: ae330ed56749
review_base: e9b619847a097e9a688832a6dc44316e6cb2a393
drift_verdict:
  result: clean
  scope_violations: []   # round 1 found gate0_receipt.md.j2, CLAUDE.md's count and the BASELINE-DELTA doc; the PLAN scope line now names them
  scenario_misses: []
  task_slug: hm-light-lane-s2
  computed_at: 2026-10-14T15:00:00Z
---

# REVIEW — hm-light-lane-s2 (stage 2a of HM-LIGHT-LANE)

Run on the PR branch (no per-task worktree; `<WT>` = repo root). Lane `full`, preset Production.
Diff `review_base..HEAD` with regenerated outputs (snapshots, golden and baseline JSON, the stage-1
approval stamp files) excluded from the reviewer diff.

**Procedure deviations, stated so nobody infers a step that did not run:**
- Pass 2 was the main loop verifying each Pass 1 finding against the code and the SPEC, not a
  second dispatch of the four reviewers.
- The confirmation pass was one `code-reviewer` dispatch over the round-1 fix diff, not the
  four-dispatch C2 pass.
- The cross-model second opinion was skipped (`codex` CLI not installed; warn and proceed).

## 🎯 Round 1 Summary

Grade **B** before fixes (P0 0, P1 2). 7 lenses exercised, `lens_coverage` `blocks_approval:
false`. 21 findings: core 11, security 2, concurrency 2, tests 6. All P1 and P2 fixed in round 1
except where noted; P3s fixed or declined below.

## 🔍 Drift Findings

- P2 `scope_violation`: `gate0_receipt.md.j2`, CLAUDE.md's `unsourced:` count and
  `work-docs/BASELINE-DELTA-hm-light-lane-s2.md` changed outside PLAN Phase 1's scope line. All
  follow from the phase; fixed in the PLAN.
- Intent (Step 3.3): P2. HM-LIGHT-LANE's statement (`hm_cost_ratio_small` ≤ 5) is unmeasured
  here; stage 4 measures it. This stage cuts about 28K chars from the four carried stage bodies.

## ✅ Findings and dispositions (round 1)

| Sev | Lens | Location | Summary | Disposition |
|---|---|---|---|---|
| P1 | concurrency | `src/harness_maker/cli.py` | Turning the loop off under a live `/hm:loop` strands its `execute-<uuid>` worktree now that Step 5 is loop-only | fixed: `_refuse_loop_disable_while_live` reuses the worktree residue probe (siblings included); test with RED check |
| P1 | security | `src/harness_maker/modular_edit.py` | `hm make --add skill:<typed-only>` lost `disable-model-invocation` once the flag left the templates | fixed: same `_TYPED_ONLY_SKILL_PATHS` list; tests. `add skill:worktree-isolator` / `agent-quality-rubric` already failed before this change (`harness_maker_src_path` undefined on that path); carried as a follow-up |
| P2 | security | stub | Slug quoting rule lived only in the shared file; "unless in context" read as a hole | fixed: rule back in the stub's Step 2; always Read from the project root |
| P2 | functionality | `wrapup.md.j2` | Loop-off wrapup named execute Step 5 | fixed: both references qualified as `/hm:loop`-only |
| P2 | consistency | `autopilot-advance.md.j2` | Step 2 read as stitched fragments; `judgment_auto_answered` unscoped | fixed: lead sentence; key scoped to judgment stages. The double heading stays: AC-005 keeps old lines verbatim |
| P2 | consistency | `template_globals.py` | Lens comment orphaned above `loop_enabled` | fixed: comment on the `lens_dispatch` entry |
| P2 | design | `synthesize.py` / stub | Gated predicate written twice | fixed: one `autopilot_enabled(config)` global |
| P2 | consistency | `docs/HOW-IT-WORKS.md` | Described the removed Size and Complexity section | fixed |
| P2 | tests | `test_render_light_lane_s2.py` | Loop span extent unchecked | fixed: `test_loop_spans_hold_only_loop_instructions` |
| P2 | tests | `test_render_light_lane_s2.py` | Stub-local rules not required in the stub | fixed: `no active marker`, Step 2 order, slug rule, judgment tokens, pending stop |
| P2 | tests | `test_render_strictness_surface.py` | Whole autopilot block cut from the strictness oracle | fixed: block stops must match between warn and block |
| P2 | tests | `test_command_size_budget.py` | One-copy Gate 0 guard ran only where Gate 0 is absent | fixed: loop-on fixture keeps the `== 1` checks |
| P3 | functionality | `execute.md.j2` | `hm/<slug>` zero-finalize rule bundled into the loop-only line | fixed: split; test added after the confirmation pass |
| P3 | tests | C.0/D.5 test | Line cap only | fixed: char cap, D.5 stop and exit rule, C.0's three items |
| P3 | tests | `test_render_verify_spec_need.py` | Name contradicted assertion | fixed: renamed |
| P3 | consistency | `step_sensitivity.py` | Census did not name `loop.enabled` | fixed |
| P3 | robustness | `synthesize.py` | `_no_answers_dump` replaced the loop block | fixed: merge |
| P3 | concurrency | `synthesize.py` | Shared file written after the stubs | declined: fails closed to STOP, first-render window only; ordering in `_base_files` is not a write transaction |
| P3 | design | loop-only markers | Markers ship only for tests | declined: about 12 comment lines per loop-on render, and they make the S2 differential exact |
| P3 | consistency | `feedback_dispatcher.md.j2` | Still names silent-intent-miss | declined: opt-in maintainer dogfooding that also reads legacy files; follow-up |
| P2 | security | stub | No version pin between stub and file | declined: executed commands come from the stub and the CLI re-validates; a pin adds a cross-file contract for no change in what can run |

## Confirmation pass

`code-reviewer` over `54cde20..HEAD`: **PASS**, no new P0/P1. Its P2 (no test for the split
`hm/<slug>` line) and two P3s (sibling bases, stale-residue hint, comment placement) were fixed;
the Step 2 wording P3 is declined for the AC-005 reason above.

## Grade

**A** after round 1 + confirmation. Status APPROVED.
