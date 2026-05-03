---
generated_by: harness-maker
harness_maker_version: 0.1.0
generated_at: '2026-01-01T00:00:00+00:00'
source_template: skills/conditional-router/SKILL.md.j2
provenance: official
content_hash: 6d9efd8820c20841575f0da107401f7083f8a9a21d98c7b563a3e8a510bf7f59
---
---
name: conditional-router
description: Selects which reviewer agents to invoke based on the changed-file paths in the current diff. Use when /hm:review runs with `routing: conditional` to avoid invoking every reviewer on every change.
---

# conditional-router

Maps changed-file path patterns to reviewer specialities so a small change
only invokes the relevant reviewers. Reduces token cost + review latency
without hiding HIGH-severity findings (security-, performance-, ux-, and
concurrency-relevant paths still trigger their owners).

## When to Invoke

- `/hm:review` is running and `harness.yaml.reviewers.routing == 'conditional'`
- A pre-commit hook needs to pick a minimal reviewer set for fast feedback
- An autoloop iteration finishes and we need a quick targeted review

## Routing Rules

Path-substring match (case-insensitive). A single file may match multiple rules.

| Pattern (substring)                    | Reviewer               |
|----------------------------------------|------------------------|
| `.env`, `/auth/`, `/secret`            | security-reviewer      |
| `/perf/`, `benchmark`, `hot`           | performance-reviewer   |
| `.tsx`, `.jsx`, `/ui/`                 | ux-reviewer            |
| `thread`, `isr`, `worker`, `async`     | concurrency-reviewer   |
| (always)                               | code-reviewer          |

If `routing != 'conditional'`, every reviewer in `reviewers.list` runs.

## Selection Constraints

1. `code-reviewer` is always included (it's the always-on baseline).
2. The router NEVER invents a reviewer the preset omits — Side preset
   only has `code-reviewer`, so conditional routing on Side reduces to
   `code-reviewer` regardless of the diff.
3. Result ordering matches `preset_reviewers` for stable iteration.
4. If no rules match, fall back to `['code-reviewer']` (never empty).

## Implementation

`harness_maker.conditional_router.route_reviewers(changed_files, preset_reviewers, routing)`.
Pure function, no IO, no side effects — easy to unit-test.

## Output

A list of reviewer agent names, e.g. `["code-reviewer", "security-reviewer"]`,
to be passed to the orchestrator that fans out the review work.
