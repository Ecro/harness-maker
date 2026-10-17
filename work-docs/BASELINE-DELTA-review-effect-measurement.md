---
type: baseline-delta
task_slug: review-effect-measurement
created: 2026-10-17
plan: "[[PLAN-review-effect-measurement]]"
---

# BASELINE-DELTA — review-effect-measurement

**What changed.** `tests/structural/surface_baseline.json` was re-frozen inside the task worktree, under
PLAN ADR-006. It was measured after the last template edit of this task (review round 2). The
`/hm:metrics` step this task adds is the SPEC's own constraint ("`/hm:metrics` gains at most one step"),
which the DRI approved. The step was compacted once already, from 3 108 to under the 3 000-char
per-command budget, before this fold. No other prose was cut to fund it: "just trim something else" is the
near-miss that `ratchet-rebaselined-by-its-own-subject` records.

**Direction.** The surface grew by 493 chars on the claude variant. codex is unchanged, because Codex
renders no `/hm:metrics`. These figures were re-measured after rebasing onto `e2743fd7` (#41 folded
SPEC-choice-cards). That fold also took in the −36 `health` shrink from #39, which an earlier in-branch
freeze of this task had carried.

| key | was | now | why |
|---|---|---|---|
| `aggregate_chars`.claude | 47 181 | 47 674 | +493, all of it the metrics step |
| `aggregate_chars`.codex | 29 111 | 29 111 | unchanged: Codex renders no `/hm:metrics` |
| `metrics` (claude, chars) | 2 475 | 2 968 | +493: Step 1.4, review escapes (`hm review_effect escape-candidates` / `escape` / `report`) |
| `render_sha` | 03912b3c | e2743fd7 | mechanical: the rebase base. The numbers are post-change, measured from the rebased tree |
| `payload_digest` | 46bc372a… | 2298fe15… | mechanical, follows the surface |

**Ownership.** Under ADR-010 (PLAN-workflow-loop-efficiency), the task that moves the surface owns its
attribution. That is why this task writes its own document, not an earlier task's.

**Follow-up (optional).** Re-freeze from main after this task lands, so that `render_sha` names the commit
the numbers came from. That is the same fold PR #37 did for PR-S.
