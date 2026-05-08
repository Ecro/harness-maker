# Autoloop Pattern Reference

> Extracted and condensed from the vault `/autoloop` command (`/mnt/c/Users/euncheol.ro/Documents/obsidian-vault/.claude/commands/autoloop.md`).
> Reference for implementing `/hm:loop` (user-harness autoloop) in Phase 6. Cross-filesystem dependency removed; self-contained reference.

*Last reviewed against code: 2026-05-08 (0.7.1). `/hm:loop` supports `feature` and `improve` modes and uses a per-loop single worktree (0.5.5+); squash-merged at convergence (0.7.1+). Wrapup runs once at loop close, not per iteration.*

## Per-Phase 5-Stage Pipeline

Each phase runs the following 5 stages in sequence:

```
Phase N
  Stage 1: Research Detection (URL/marker/unknown-lib auto-detection)
  Stage 2: Plan Validation (3x parallel, 2/3 consensus, max 2 rounds)
  Stage 3: Execute (CODER → TESTER loop, max N retries with error context)
  Stage 4: Review (5-8 reviewers, 2/3 consensus, auto-fix P0-P2)
  Stage 5: Wrapup (git commit "autoloop({project}): phase N - {name}")
  ↓
Phase N+1
```

## Document Sharding (DD#3)

Each sub-agent receives only the minimum required context:

| Section | Included? | Reason |
|---|---|---|
| Section 2 (Technical Constitution) | Always | Code style and boundaries |
| Section 3 (Architecture) | Always | System design, data model, APIs |
| Current Phase block ONLY | Per-phase | Current phase task only (scope creep prevention) |
| Research Context | If triggered | Stage 1 output |
| All Other Phases | Never | Block future-phase leakage |
| Section 1 (Vision) | Never | Not relevant to implementation |
| Section 5 (Final Acceptance) | Final pass only | Final verification only |
| Section 6 (Risks) | Never | Orchestrator-only |

## Context Isolation (DD#4)

- Each phase is a separate sub-agent invocation (fresh context window)
- State handoff is via disk (`.claude-progress.json`) + git history
- Sub-agents do not read the progress file — they only implement and verify

## 2/3 Consensus Algorithm (Plan Validation + Code Review)

**Step A — Surface Matching:** Two findings are candidates when: ≥2 attributes match (file, line range ±10, category). Groups formed via transitive closure.

**Step B — Conclusion Alignment:** Compare CONCLUDE steps within each group. Verify same risk/impact rating.

**Step C — Consensus Decision:**
```
if agent_count >= 2 AND conclusions_aligned:
    tier = "strong" if agent_count == 3 else "standard"  # eligible for auto-fix
elif agent_count >= 2 AND NOT aligned:
    tier = "weak"  # manual review, no auto-fix
else:
    DROP  # single agent = noise
```

## Adaptive Reviewer Selection (DD#9)

**Always spawned (5):**
- 3x code-reviewer (parallel, OBSERVE→TRACE→INFER→CONCLUDE)
- 1x performance-reviewer
- 1x walkthrough-reviewer

**Conditional (0-3):**
- side-effect-reviewer: when public function signatures change
- concurrency-reviewer: when async/await/thread/mutex/lock is present
- test-quality-reviewer: when test files are modified

## Autonomous Decision Protocol (DD#8)

**All decisions inside autoloop are autonomous** — AskUserQuestion calls are forbidden.
When ambiguous, log the decision and proceed (do not block on user input).

| Situation | Autonomous Action | Log Required? |
|---|---|---|
| Hash mismatch on resume | Auto-continue with new spec, preserve completed phases | Yes, human_review_needed=true |
| Plan NEEDS_REVISION | Auto-apply validator's revised text | Yes |
| Plan MAJOR_REVISION (round 1) | Auto-revise + re-validate | Yes |
| Plan MAJOR_REVISION (round 2) | Proceed + human_review_needed=true | Yes |
| Review grade D/F | Proceed, set human_review_needed flag | Yes |
| Phase blocked (max retries) | HALT autoloop, record blocker | Yes |
| Final verification fails | Report only, do not HALT | Yes |

*0.7.1: `/hm:review` defaults to consensus filter (surface match + reasoning alignment) with grade gate A/B/C and auto-fix loop bounded by `max_review_rounds`.*

## State File Schema (`.claude-progress.json`)

```json
{
  "spec_file": "...",
  "spec_hash": "<SHA-256>",
  "input_mode": "TECH_SPEC",
  "project": "harness-maker",
  "repo_path": "/home/noel/harness-maker",
  "started": "<ISO-8601>",
  "current_phase": 1,
  "total_phases": 10,
  "phases": [
    {
      "id": 1,
      "name": "Project Scaffold + ...",
      "status": "pending|in_progress|retrying|completed|blocked",
      "started_at": null,
      "completed_at": null,
      "commit_hash": null,
      "iterations": 0,
      "stages": {
        "research":         { "status": "pending", "reason": null },
        "plan_validation":  { "status": "pending", "result": null, "rounds": 0 },
        "execute":          { "status": "pending", "iterations": 0 },
        "review":           { "status": "pending", "grade": null, "reviewers_spawned": 0 },
        "wrapup":           { "status": "pending", "commit_hash": null }
      },
      "autonomous_decisions": [],
      "verify_result": null,
      "last_error": null
    }
  ],
  "total_iterations": 0,
  "agents_spawned": 0,
  "blockers": [],
  "decision_log": []
}
```

**Atomic write:** Write to `path.tmp` then `os.rename(tmp, path)`. Zero corruption on interrupt.
(0.7.1 ADR-103: metrics are rotated daily as `metrics-YYYY-MM-DD.jsonl`; readers use `_metrics_io.iter_recent_entries` rather than reading the state file directly.)

## Error Handling

| Error | Autonomous Action |
|---|---|
| project-name missing | ERROR + STOP |
| TECH_SPEC.md absent | ERROR + STOP |
| Section 0 malformed | ERROR + STOP |
| Phase parse fail | ERROR + STOP |
| Verify script absent (TECH_SPEC mode) | TESTER-only fallback, log |
| CODER outputs PHASE_BLOCKED | Immediate HALT |
| Phase fails max retries | HALT all subsequent phases |
| Review grade D/F | Proceed, set human_review_needed |
| Hash mismatch on resume | Auto-continue, log |
| Global iter cap | HALT |
| Final verify fails | Report, do not HALT |
| Agent malformed JSON | Proceed with N-1 agents |

## What `/hm:loop` Adopts

- **5-stage pipeline** (research → plan-validate → execute → review → wrapup)
- **Document sharding** — atomic per-stage prompt fragments + per-workflow fused prompts
- **Adaptive reviewer selection** — integrated with Conditional Router (Phase 5)
- **Atomic state writes** — `.claude/observability/loop-state.json`
  (0.7.1 ADR-106: `_locking.exclusive_lock` is thread-re-entrant via `threading.local`, safe inside concurrent autoloop iterations)
- **Autonomous decision protocol** — all decisions autonomous except `--dry-run`; every decision logged
  (0.7.1 ADR-108: drift_monitor wraps LLM judge input in XML fences with both open and close tag defanging)

## Differences Specific to `/hm:loop`

- The vault autoloop runs inside the vault and targets that repo. `/hm:loop` runs inside the user's project and targets that same repo.
- The vault autoloop is TECH_SPEC.md-driven. `/hm:loop` is natural-language-goal-driven + workflow-driven.
- The vault autoloop is phase-based. `/hm:loop` is feature-based (parse_goal → feature_list).
- Permission separation enforced: `/hm:loop` workers are executor agents (write-in-worktree only).
- Security gate integrated: verify-before-completion runs immediately before each iter wrapup (zero high-severity security findings required).
