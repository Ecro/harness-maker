---
type: review
task_slug: existing-parametrize-all
created: 2026-11-28
spec: "[[SPEC-existing-parametrize-all]]"
---

# REVIEW — existing-parametrize-all

One code-reviewer round over the SPEC, PLAN, diff and tests.

## Findings

| id | severity | file:line | finding | disposition | authority |
|---|---|---|---|---|---|
| F1 | P3 | src/harness_maker/templates/stages/execute.md.j2:45 | the general sentence says "its list" without "same columns"; the paste clause right after limits golden rows to a list with the same columns | rejected | the paste clause still governs parametric ACs; t7 ×3 at d0cdcc06 shows no confusion (all three extended the right lists) |

## Bench

t7 ×3, evidence judge vs plain + tests (`/mnt/project-files/hm-blog-cost/data/px-epa2-t7.json`): maintainability A / A / tie (before #94-era: B / A / A), overall A / A / tie, no decisive evidence against hm.
