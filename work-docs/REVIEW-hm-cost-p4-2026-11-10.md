---
type: review
task_slug: hm-cost-p4
created: 2026-11-10
spec: "[[SPEC-hm-cost-p4]]"
plan: "[[PLAN-hm-cost-p4]]"
rounds: 3
reviewers: [code-reviewer]
summary: "Three rounds. Round 1 raised 12 code-reviewer findings (14 rows, F3 split in three): 10 accepted and fixed, 3 rejected with authority, 1 confirmed by the DRI. Round 2 raised 2 (1 accepted, 1 rejected), round 3 none. AC-009's pre-registered 10.0 bar was missed at 10.243 (from 11.359) and is recorded as a miss; hm-novalidator measured 7.674."
---

# REVIEW — hm-cost-p4

Three code-reviewer rounds (12, 2 and 0 findings). The cross-model second opinion (`codex`) was
skipped: the CLI is not installed in this container (warn-and-proceed). No `Do not change` item was
crossed: `check.ac_section` full mode, the `AcceptanceCriterion` schema and `scripts/bench/tasks/`
are untouched.

## Findings

| id | severity | file:line | finding | disposition | authority |
|---|---|---|---|---|---|
| F1 | P2 | src/harness_maker/spec_machine.py:759 | The discovery collect ran inside `_mark_tested_locked`, under the spec write lock, so a slow repo-wide collect could outlast `_LOCK_TIMEOUT_S` and time out a concurrent writer. Fix: `mark_tested` collects before taking the lock and passes the node ids in | accepted | SPEC AC-002 |
| F2 | P2 | src/harness_maker/spec_machine.py:783 | A failed collect was reported as "no test named …", hiding the real cause. Fix: the error adds "pytest could not collect the suite" with the runner command to run | accepted | SPEC AC-002 |
| F3a | P2 | src/harness_maker/check.py:960 | The golden-file fallback runs only for a test file that fails to collect | rejected | SPEC AC-003: a file that collects binds by case id or function name; the fallback exists only for the import-RED case |
| F3b | P2 | src/harness_maker/check.py:960 | The fallback excluded functions named `test_ac_*`, so a shared `test_ac_001_golden` left AC-002 unbound in an import-RED. Fix: the exclusion is dropped | accepted | SPEC AC-003 |
| F3c | P2 | src/harness_maker/check.py:960 | The golden file is detected by its literal name, so a computed path is missed | rejected | SPEC AC-003 names the recipe's literal `SPEC-<slug>.golden.json`; the limit is stated in a code comment |
| F4 | P3 | src/harness_maker/spec_machine.py:803 | Discovery runs only when an AC's `test_ids` is empty, so recorded ids are not unioned with newly named tests | rejected | SPEC Non-Goals: recorded `test_ids` keep precedence over name discovery |
| F5 | P3 | src/harness_maker/check.py:946 | The node-line regex dropped node ids with `+`, `@` or a space, sending the file to the static fallback. Fix: any line containing `.py::` that is not an `ERROR`/`FAILED` line is a node id | accepted | SPEC AC-003 |
| F6 | P3 | src/harness_maker/spec_machine.py:1071 | A case id that is not the whole bracket (`[x-AC-001-0]`) falls through to the function-name rule silently. Fix: the docstring states the case id must be the bracket's leading token | accepted | SPEC AC-002 |
| F7 | P3 | src/harness_maker/check.py:497 | The static fallback ignored class-based tests. Fix: `Cls::test_x` methods are named | accepted | SPEC AC-003 |
| F8 | P3 | scripts/bench_light_lane.py:1530 | `drop_spec_validator` wrote with `path.write_text`. Fix: `atomic_write`; the rendered file's stale `content_hash` is accepted, nothing in a bench run reads it | accepted | docs/reference/implementation-patterns.md (atomic write) |
| F9 | P3 | scripts/bench_light_lane.py:3603 | CLI provenance was checked on the first hm template only. Fix: every hm template is checked | accepted | SPEC AC-008 |
| F10 | P3 | tests/unit/test_overhaul_p1_surface.py:248 | The AC-004 stage budgets rise (spec +100, execute +60) in a cost-cutting task under an agent-decided ADR. Put to the DRI as a card on 2026-11-10; the DRI chose to raise them, recorded in PLAN ADR-004 | accepted | DRI decision 2026-11-10 (PLAN ADR-004) |
| F11 | P3 | work-docs/PLAN-hm-cost-p4.md:25 | Phase 5's exit command named a test file that does not exist. Fix: it names `tests/integration/test_hm_cost_p4_bar.py` | accepted | PLAN Phase 5 |
| F12 | P3 | tests/integration/test_hm_cost_p4_bar.py:35 | The variant arm's rows were counted in total only. Fix: three rows per task are asserted; plain and hm coverage is `p2.bar_violations`' | accepted | SPEC AC-009 |
| R2-1 | P3 | src/harness_maker/templates/stages/execute.md.j2:56 | Dropping execute's `hm spec_machine validate` call leaves an IRR appended in Phase C unvalidated (`check` and `mark-tested` load the yaml but do not run `validate()`) | rejected | Base template (579e719) execute.md.j2:50: the call ran in Phase A, before Phase C's append, so it never covered that append; logged as a follow-up |
| R2-2 | P3 | src/harness_maker/check.py:497 | The static fallback took any top-level name starting with `test`, so `test_cases = [...]` became a fake node id that could read as RED. Fix: `_static_test_names` names function definitions only; `test_static_fallback_names_only_test_functions` | accepted | SPEC AC-003 |
| G1 | — | tests/unit/test_overhaul_p1_kept.py:94 | Found by the suite, not a reviewer: expectations pinned to the text this SPEC changes (execute's `spec_machine validate` call, the consensus-arbiter hash and trigger text, the four render snapshots, `ALL_ARMS`, the config-suite opt-out list) were re-pinned, each with the AC that moved it | accepted | SPEC AC-004, AC-007, AC-008 |

## Suite

`uv run pytest -n auto`: 11 226 passed, 3 failed. Two were the aggregate-surface tests, red only
because that run had the PLAN marked complete (see below); they pass again with it in-flight. The third is
`tests/unit/test_land_hold.py::test_ac_011_the_subject_hash_refuses_an_oversized_subject[unreadable]`,
which also fails on main at 579e719 in this container: it runs as root, and root ignores the `chmod`
the case relies on. `hm check --slug hm-cost-p4` therefore exits 1 here: approval, ac, review, security
and cve pass, ruff, format and `mypy --strict src tests` pass, and the pytest gate (`-x`) stops at that
test. The PLAN stays `status: planning` until the surface growth is folded into the baseline from main
after the merge (as SPEC-maker-advance did, #42 then #43); marking it complete earlier expires the
`surface_allowance` and turns the two aggregate-surface tests red.
