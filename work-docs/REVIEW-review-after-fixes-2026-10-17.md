---
type: review
task_slug: review-after-fixes
created: 2026-10-17
spec: "[[SPEC-review-after-fixes]]"
plan: "[[PLAN-review-after-fixes]]"
summary: "One code-reviewer pass over the reordered Step 6, the resume-after-Bind rule and the AC tests; 7 findings, 6 accepted and fixed, 1 rejected as the recorded trade-off"
---

# REVIEW — review-after-fixes

Reviewer: code-reviewer (read-only), against SPEC-review-after-fixes (approved eadb25fe) and
PLAN-review-after-fixes. This REVIEW was written after the fixes, as the change itself requires.

## Findings

| id | severity | file:line | finding | disposition | authority |
|---|---|---|---|---|---|
| F1 | P2 | src/harness_maker/templates/stages/execute.md.j2 resume rule | Vacuously true for a SPEC with no testable ACs: a first run would skip Phase C | accepted | Fixed: "at least one testable AC" |
| F2 | P2 | src/harness_maker/templates/stages/execute.md.j2 resume rule | "then Step 4" left unclear whether Steps 0-2 still run (PLAN and SPEC loads) | accepted | Fixed: "after Step 2, rerun Bind's gate, then Step 4" |
| F3 | P2 | src/harness_maker/templates/stages/execute.md.j2 hot tier | The clause sat in the bullet scoped to a compaction checkpoint, so a model could skip it | accepted | Fixed: its own `**Resume.**` paragraph before Session Context Loading |
| F4 | P2 | src/harness_maker/templates/stages/execute.md.j2 Step 6 | A compaction mid-loop loses earlier rounds' findings before the REVIEW is written | rejected | SPEC-review-after-fixes Refinement Decisions record this cost; adding a running-list rule would exceed execute's 7,000-char AC-004 budget |
| F5 | P2 | src/harness_maker/templates/stages/execute.md.j2 Step 6 | "(or `none`)" after "every round's findings" invites `none` when only the last round was empty; review_effect would count 0 | accepted | Fixed: "`none` if no round found any" |
| F6 | P3 | src/harness_maker/templates/stages/execute.md.j2 Step 6 | "the rest" has no clear referent after the round clause | accepted | Fixed: "what stays open" |
| F7 | P3 | specs/SPEC-review-after-fixes.md Refinement Decisions | The rationale for dropping "The PLAN holds no ACs" claimed a PLAN template that does not exist | accepted | Fixed: rationale corrected; the invariant stays in SPEC-hm-overhaul-p1 |
