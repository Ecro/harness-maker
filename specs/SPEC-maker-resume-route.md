---
type: spec
task_slug: maker-resume-route
status: approved
created: 2026-11-26
tags: [maker, world-model, resume, routing]
test_framework: pytest
interview_rounds: 0
summary: Route an unnamed "continue / finish the interrupted work" ask to Maker, so a fresh session finds a task left in its worktree.
---

# SPEC — maker-resume-route

## Intent

The saga bench (2026-11-25, `/mnt/project-files/hm-blog-cost/saga-results-2026-11-25.md`)
killed each arm's S4 mid-implementation and opened a fresh session with "My last session was
cut off before it finished. Finish the work that was in progress." hm resumed 3/5 in the main
run (plain and plain+discipline 5/5). In 2 of 5 runs, the fresh session said there was no
unfinished work, because the task's SPEC, PLAN and tests sat in `.worktrees/tz-setting`.

Maker ran in **none** of the 7 resume sessions, main run and pilot together. Its
`hm world_model digest` does list that task with `next_stage: execute`: a replay on the
interrupted state shows it. Maker's Resume route exists. But nothing sends this ask there:
- The skill description admits Maker only when named, or when "the World model rule routes a
  goal, metric, fact or status request here".
- The always-loaded `## World model` pointer routes goal, metric, fact and status asks. It does
  not route a resume ask.

The DRI asked to fix it ("응 고쳐", 2026-11-26).

## Outcomes

- An unnamed ask to continue, resume or finish interrupted work reaches Maker's Resume route.
  The route lists its tasks from the digest, task worktrees included.
- Build and fix asks stay outside Maker, as they are today.

## In-Scope Scenarios

- **S1 (normal):** Given any rendered variant (Claude/Codex × en/ko, default and maximum name
  lengths), the `## World model` pointer routes resume asks to Maker. It stays ≤ 400 chars and
  keeps the build/fix exclusion.
- **S2 (normal):** Given any Maker render, the description's routing clause names resume
  requests. Maker stays ≤ 4,689 chars.
- **S3 (live, integration):** Given the saga's interrupted state (approved SPEC, PLAN and RED
  tests in `.worktrees/<slug>`, base clean), a fresh `claude -p` session with the bare resume
  prompt loads Maker, which is observable as a `maker_load` row.

## Non-Goals

- Routing build or fix asks to Maker.
- Changes to the digest, the Resume route body or worktree discovery: the digest already
  reports the task.
- A SessionStart hook or any new always-on injection.

## Constraints

| Constraint | Source |
|---|---|
| `## World model` ≤ 400 chars per variant; Maker SKILL.md ≤ 4,689 chars | CLAUDE.md "World model (Maker)" |
| Maker stays the only self-triggering entrance; intent-layer/project-knowledge untouched | CLAUDE.md |
| No `!` injection, no widened `allowed-tools` | CLAUDE.md |

## Irreversible Decisions

none

## Acceptance Criteria

### AC-001: the pointer routes resume asks

In every `test_ac014_pointer_routes_unnamed` variant, the `## World model` section contains
`resume` (en and Codex) or `재개` (ko), stays ≤ 400 chars and keeps the exclusion literal.

### AC-002: the description routes resume requests

On every Maker arm (claude-code/codex × en/ko), the frontmatter description contains `or the
World model rule routes a goal, metric, fact, status or resume request here`, and the file
stays ≤ 4,689 chars.

## Verification

| Scenario | Mode | Test |
|---|---|---|
| S1 | render | `tests/render/test_render_maker_front_door.py::test_ac014_pointer_routes_unnamed` |
| S2 | render | `tests/render/test_render_maker_front_door.py::test_ac005_maker_reads_procedures` |
| S3 | live, manual | a replay of the saga S4r state: `maker_load` row count before and after |

## Open Questions

none

## Refinement Decisions

- **Route through the existing pointer and description, not a new hook:** the digest and the
  Resume route already work, so the gap is the entrance. The pointer is loaded on every turn.
  Adding one word costs almost nothing, and the build/fix exclusion still holds.
- **The word is "resume", not "continue":** "continue" collides with ordinary mid-task asks
  ("continue the refactor"). "Resume" names the cross-session case, and the Maker route table
  already lists "continue", "이어서" and "resume" under Resume.
- **Approval:** the DRI's "응 고쳐" on the reported defect. This is a small fix with no
  irreversible decision.
