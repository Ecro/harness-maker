---
type: spec
task_slug: mark-tested-scope
status: approved
created: 2026-11-10
tags: [correctness, spec-machine, binding, mark-tested]
test_framework: pytest
interview_rounds: 0
summary: mark-tested binds an AC with no recorded test_ids only to convention-named tests in the task's changed test files, the same tests the RED gate ran, instead of every same-numbered test in the repository.
---

# SPEC — mark-tested-scope

## Intent

`hm spec_machine mark-tested --ac AC-NNN` without `--test-id` binds the AC to the tests the name
convention gives it (SPEC-hm-cost-p4 IRR-001). The discovery behind it is a repo-wide
`pytest --collect-only`, so in a repository with more than one SPEC every `test_ac_001_*` of every SPEC
matches AC-001. Reproduced in this repository: binding a 10-AC SPEC by `--ac` recorded 866 test ids, and
binding hm-cost-p5 by `--ac` recorded 102 where 15 were its own (proposals-log NT-008). A wrong binding
is silent: the gate then runs other SPECs' tests as this AC's evidence, and the AC reads as tested by
tests that never looked at it.

The RED gate already has the right scope. `check.red_discovery` collects only the test files the task
changed (`git diff HEAD`, staged, untracked), because the task's tests are new. The execute stage runs
mark-tested in the same uncommitted tree, after the last phase and before the gate, so the two can use
the same discovery: the tests that were RED for an AC are the tests it is bound to.

## Outcomes

- `mark-tested --ac` in a repository with many SPECs records only the task's own tests.
- Binding and RED agree on which tests belong to an AC.
- No repo-wide collect runs on the bind path, so the bind is no slower than RED.

## In-Scope Scenarios

- S1: a committed test file of another SPEC has `test_ac_001_old`; the task adds an untracked file with
  `test_ac_001_new`. AC-001 binds to the new test only.
- S2: the task changed no test file that names AC-001. The call fails, the yaml is untouched, and the
  error says where it looked and names `--test-id`.
- S3: the task modified a committed test file (unstaged or staged) to add `test_ac_001_x`. It binds.
- S4: `--test-id AC-001=<node>` is given. It is recorded as before; discovery does not add to it.
- S5: a tree with no commit yet (no HEAD). Every listed test file counts as changed, as in RED today.
- S6: a parametric AC whose changed test file collects and reads `SPEC-<slug>.golden.json` but has no
  convention name. It binds nothing, as today: RED's golden-file fallback applies only to a file that
  fails to collect, which no longer happens after the last phase. The refusal names `--test-id`.

## Non-Goals

- `find_unbound_closed_type_acs` and `check._collectable_ac_tests` keep their repo-wide collect. They
  audit bindings across the repository, where a repo-wide view is the point.
- No change to the name convention (`ac_tests_for`), to `--test-id`, or to the rule-3 resolution
  pre-check.
- No change to `red_discovery` itself.

## Constraints

- Discovery stays outside the yaml write lock, as today: it runs a subprocess.
- A refused call leaves the yaml byte-identical (REVIEW C-P2c contract).

## Irreversible Decisions

| id | decision | category | rationale |
|---|---|---|---|
| IRR-001 | `mark-tested` discovery for an AC with no `test_ids` narrows from the whole repository to the task's changed test files (`check.red_discovery`) | public API/CLI contract | Narrows SPEC-hm-cost-p4 IRR-001. A caller that ran `--ac` after committing its tests now gets an error and must pass `--test-id` |

## Acceptance Criteria

### AC-001: binding is scoped to the changed test files
In a git repository, `spec_machine.mark_tested(yaml, md, {AC: []})` records, for an AC with no
`test_ids`, the convention-named tests found in changed test files only. The golden rows cover S1–S6
and record the bound ids or the refusal.

### AC-002: binding and RED discover the same tests
For every AC-001 row that binds, the recorded ids equal `check.red_discovery(root, SpecView, runner)`
for that AC on the same tree.

### AC-003: the bind path runs no repo-wide collect and the refusal names --test-id
With `spec_machine._pytest_collect_nodeids` replaced by a function that raises, `mark_tested` with empty
ids still binds S1, and on S2 returns one error that contains the AC id, `test_ac_001`, `changed test
files` and `--test-id`, with the yaml unchanged.

## Verification

| scenario | mode | test |
|---|---|---|
| S1–S6 | unit (tmp git repo) | AC-001, AC-002 |
| S1, S2 | unit | AC-003 |
| regression | unit | tests/unit/test_hm_cost_p4_binding.py stays green unchanged |

## Open Questions

none

## Refinement Decisions

- Approval (DRI standing instruction, 2026-11-10 13:26Z, this thread): "나에게 묻지말고 이제부터는 모두
  너의 추천대로 wrapup 후 push to. Main까지 진행해". The SPEC is approved on that instruction; no card.
- Default (agent): reuse `check.red_discovery` instead of a second scoped collect, so bind and RED cannot
  drift apart.
- Correction (agent, during execute): S6 first said a golden reader binds as in RED. RED binds one only
  when its file fails to collect, which a bind after the last phase never sees; S6 and its golden row
  now say it binds nothing, which is also today's behaviour. The SPEC was re-approved on the standing
  instruction above.
- Default (agent): no fallback to a repo-wide collect when nothing changed. That fallback is exactly the
  over-binding this task removes; the error points at `--test-id` instead.
- Default (agent): spec-validator skipped (3 live ACs; `validator: skip`).
