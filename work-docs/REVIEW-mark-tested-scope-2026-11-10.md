---
type: review
task_slug: mark-tested-scope
status: complete
created: 2026-11-10
spec: "[[SPEC-mark-tested-scope]]"
plan: "[[PLAN-mark-tested-scope]]"
summary: One review round by code-reviewer (codex second opinion skipped, CLI not installed). No P1; two P2 and four P3, none needing a code change; each rejected with an authority.
---

# REVIEW — mark-tested-scope

Reviewer: `code-reviewer` on the uncommitted diff against 9a0788a1, with the SPEC, the PLAN and the tests.
Second opinion: `codex` → `skipped` ("CLI not installed: codex"); warn and proceed.

## Findings

| id | severity | file:line | finding | disposition | authority |
|---|---|---|---|---|---|
| F1 | P2 | src/harness_maker/spec_machine.py (mark_tested) | A judgment AC named by `--ac` with no test_ids no longer binds by name, because `red_discovery` covers only testable ACs | rejected | execute.md.j2 Step 2 takes "the testable ACs (not superseded, not `type: judgment`)"; a judgment AC is judged, not test-bound; SPEC: bind uses RED's scope |
| F2 | P2 | src/harness_maker/spec_machine.py (refusal text) | After a commit, the refusal does not state why nothing was found | rejected | the message already says "in the changed test files; pass --test-id … for a test already committed"; SPEC IRR-001 names the case |
| F3 | P3 | src/harness_maker/spec_machine.py (mark_tested) | The "pytest could not collect the suite" suffix is gone; a total collect failure shows only "no test named" | rejected | PLAN ADR-001 (one scope with RED, which already falls back to static names on a failed collect); the rule-3 pre-check still refuses any id that does not resolve |
| F4 | P3 | src/harness_maker/spec_machine.py (mark_tested) | Discovery reads the yaml before the lock | rejected | PLAN ADR-003; the locked path re-checks unknown/superseded and applies discovery only to ACs still empty |
| F5 | P3 | tests/unit/test_mark_tested_scope.py (AC-003) | The patch proves only that one function is not called | rejected | duplicate of the S1 row, which asserts another SPEC's committed `test_ac_001_old` is not bound (`bound == [NEW]`) |
| F6 | P3 | tests/unit/test_mark_tested_scope.py (AC-002) | Bind and RED could drift together | rejected | AC-001 pins the golden rows independently of both |

## Changes outside the SPEC's files

`tests/unit/test_spec_machine.py::test_mark_tested_refuses_zero_test_ids` put its SPEC directly in
`tmp_path`, so discovery searched pytest's shared basetemp and, in some test orders, found a sibling
test's `test_ac_001_thing`. Its SPEC now lives in `tmp_path/specs`; the assertions are unchanged. The
old repo-wide collect over the same basetemp passed only because that collect errored out.

## Dogfood

`mark-tested --ac AC-001 --ac AC-002 --ac AC-003` on this SPEC with no `--test-id` bound 16 ids, all in
`tests/unit/test_mark_tested_scope.py` (hm-cost-p5: 102 ids for 15 before the fix).
