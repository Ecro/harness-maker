---
type: review
task_slug: hide-retired-cli
created: 2026-11-10
spec: "[[SPEC-hide-retired-cli]]"
plan: "[[PLAN-hide-retired-cli]]"
rounds: 1
reviewers: [code-reviewer]
summary: "One code-reviewer round plus one hm check failure: the runtime stderr notice broke a JSON-reading caller, so retirement moved into each command's own --help. Four reviewer findings, all accepted and fixed."
---

# REVIEW — hide-retired-cli

One code-reviewer round found no critical defect. The first `hm check` run then failed
`tests/unit/test_autopilot.py:203`: Click 8.3.3's `CliRunner` mixes stderr into `result.output`,
so the new "retired" stderr line broke the JSON read of `autopilot status`. A real script that
merges streams (`2>&1`) would break the same way, so the runtime notice was dropped. Each hidden
command's `--help` now opens with "Retired in 0.64.0" and what replaces it; running it behaves
exactly as before. The spec-validator was skipped (exempt SPEC, no irreversible decision). No
`Do not change` path (inert_keys.py, models.py, templates/) was crossed.

## Findings

| id | severity | file:line | finding | disposition | authority |
|---|---|---|---|---|---|
| 1 | major | src/harness_maker/cli.py (`--autonomy-level` help) | The rewritten help listed `full` (a legacy alias) and omitted `auto_full`, the only level that changes behaviour. Fix: it lists ask, gated, auto_safe and auto_full and says only `auto_full` lets the spec stage stamp a SPEC, and execute and `hm check` proceed on an unstamped one, without asking | accepted | SPEC O3 |
| 2 | minor | src/harness_maker/cli.py (`autopilot`, `verify`) | The stderr notice risks callers that parse output (confirmed by the hm check failure above), and the `autopilot` docstring still described a live feature. Fix: notices removed; both docstrings open with "Retired in 0.64.0" and the replacement | accepted | SPEC O2 (revised) |
| 3 | minor | tests/unit/test_hide_retired_cli.py | Help assertions depended on terminal width and Rich line wrapping. Fix: the runner pins `COLUMNS=200`, command names are read from the table rows, and the help-text checks join the whole output before matching | accepted | SPEC AC-001 |
| 4 | minor | specs/SPEC-hide-retired-cli.md (Non-Goals) | It said every retired key already warns through `inert_keys`; only `loop.enabled` and `autonomy.autopilot_persistent` do. Fix: the sentence names those two | accepted | IRR-006 of SPEC-hm-overhaul-p1 |
