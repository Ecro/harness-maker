---
type: review
task_slug: dead-modules
created: 2026-11-10
spec: "[[SPEC-dead-modules]]"
plan: "[[PLAN-dead-modules]]"
rounds: 1
reviewers: [code-reviewer]
summary: "One code-reviewer round: 1 major, 6 minor, 1 nit. The major and four minor fixed; the closure-looseness, docs and nit findings rejected with reasons."
---

# REVIEW — dead-modules

One code-reviewer round. The live-path check came back clean: no import, `hm <name>` call or
computed-name import of a deleted module in `src/`, the templates, the plugin bundle, `scripts/`
or `.github/`. The one computed import (`step_sensitivity`'s python-kind knob) reads no deleted
module. `common_ground` in `models.py` and `interview.py` is a `harness.yaml` key, not the module.
The spec-validator was skipped (exempt SPEC, no irreversible decision). No `Do not change` path
was crossed.

## Findings

| id | severity | file:line | finding | disposition | authority |
|---|---|---|---|---|---|
| 1 | major | tests/integration/test_hm_console_script_resolves.py | The `INTEGRATION=1` console-script test still dispatched `hm test_dep_map`, so it would fail; a default run skips it. Fix: it dispatches `hm test_runners plan` and asserts the `workers` field | accepted | SPEC S2 |
| 2 | minor | src/harness_maker/template_globals.py:4, 120, 127 | The docstring named `foreign_config` as an Environment site, and two comments named `lens_coverage` as a consumer. Fix: both reworded | accepted | SPEC O1 |
| 3 | minor | src/harness_maker/spec_need.py:139 | "Mirrors observability/intent_miss.record_intent_miss" points at a deleted file. Fix: line removed. The other mentions in `src/` are measurement history in comments | accepted | SPEC O1 |
| 4 | minor | tests/structural/test_dead_modules.py | `not reached & set(DELETED)` can never fail. Fix: removed; AC-001's per-name tests carry it | accepted | SPEC AC-003 |
| 4b | minor | tests/structural/test_dead_modules.py (`_edges`, `_refs`) | The closure counts docstrings and prose `hm <word>` as edges, so a module that is only documented counts as reached | rejected | The over-approximation errs toward keeping a module, never toward deleting a live one, which is the failure this check exists to prevent. Tightening it would make a mention in a prompt template (a real call site) look dead |
| 5 | minor | tests/unit/test_command_surface_gate.py (`_rel_for`) | Still special-cased the deleted `spec_inventory`. Fix: removed | accepted | SPEC AC-001 |
| 7 | minor | tests/unit/spec_test_ids_known_dead.txt | The `[dead-modules]` group lists ids of deleted tests | rejected | That is the file's purpose: old SPECs still bind those ids, and the file is the established record for them (the PR-C Cursor group is the precedent). `test_known_dead_test_ids_are_still_dead` removes an entry once it resolves |
| 9 | minor | docs/ARCHITECTURE.md:461-470, docs/reference/autoloop-pattern.md:81, reviewer-fanout.md:14, block-merge-spec.md:152, pre-change-checklist.md:66; HOW-IT-WORKS en/ko | Docs still describe deleted modules | rejected | Out of this slice, moved to item 5 (the docs rewrite). pre-change-checklist.md:66 is a past-incident anecdote, not an instruction to run `high_diff` |
| 6 | nit | tests/ comments (conftest.py:72, test_env_isolation.py:35, and others) | Comments name deleted modules | rejected | Comments only; they record why a test was written and cannot break |

## Pins moved with this SPEC

| file | change |
|---|---|
| tests/unit/spec_test_ids_known_dead.txt | new `[dead-modules]` group: 49 ids of deleted tests still bound by older SPECs |
| tests/unit/test_spec_machine.py | the known-dead group set includes `dead-modules` |
| tests/structural/test_hm_entrypoint.py | the success-exit probe dispatches `test_runners plan` |
| tests/structural/test_template_globals_installed.py | at least 2 Environment sites (foreign_config was the third) |
| tests/unit/test_privacy_doc_schema.py | the two deleted telemetry schemas and their measure-C block test left with PRIVACY.md's sections |

## Verification

- The full suite under `hm check` found the remaining pins above; after the fixes, the affected
  files and `INTEGRATION=1` console-script test pass. ruff, format and mypy --strict are clean.
