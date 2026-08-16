[🇰🇷 한국어](HOW-IT-WORKS.ko.md)

# harness-maker: How It Works — Complete Guide

> **Audience**: Developers new to harness-maker, or users who want a deep understanding of internal behavior.
> **Version**: 0.9.3. Focus is on **procedures, flow, and responsibilities** — not implementation details.

---

## Table of Contents

1. [What is harness-maker?](#1-what-is-harness-maker)
2. [Overall Architecture](#2-overall-architecture)
3. [The 7 Atomic Workflow Stages](#3-the-7-atomic-workflow-stages)
   - 3.1 [/hm:research — Exploration](#31-hmresearch--exploration)
   - 3.2 [/hm:spec — Acceptance Criteria](#32-hmspec--acceptance-criteria)
   - 3.3 [/hm:plan — Implementation Plan](#33-hmplan--implementation-plan)
   - 3.4 [/hm:execute — TDD Implementation](#34-hmexecute--tdd-implementation)
   - 3.5 [/hm:review — Code Review](#35-hmreview--code-review)
   - 3.6 [/hm:verify — Completion Verification](#36-hmverify--completion-verification)
   - 3.7 [/hm:wrapup — Commit Finalization](#37-hmwrapup--commit-finalization)
4. [Fusion Commands](#4-fusion-commands)
5. [/hm:loop — Automated Iteration Loop](#5-hmloop--automated-iteration-loop)
6. [Special Commands](#6-special-commands)
   - 6.1 [/hm:health — structural layer](#61-hmhealth--structural-layer)
   - 6.2 [/hm:health — personalization layer](#62-hmhealth--personalization-layer)
7. [Skills Reference](#7-skills-reference)
8. [Agent Reference](#8-agent-reference)
9. [Hook Details](#9-hook-details)
10. [Appendix](#10-appendix)
11. [What Makes harness-maker Different](#11-what-makes-harness-maker-different)
    - 11.1 [3-Tier Memory Hierarchy — Knowledge Persists Across Sessions](#111-3-tier-memory-hierarchy--knowledge-persists-across-sessions)
    - 11.2 [Failure Count → Auto-Improvement Proposal Loop](#112-failure-count--auto-improvement-proposal-loop)
    - 11.3 [PreCompact Hook + checkpoint:compaction — No Work Lost on Context Compression](#113-precompact-hook--checkpointcompaction--no-work-lost-on-context-compression)
    - 11.4 [Prompt Cache Diagnostics (Layer 3) — Classify Cache Miss by Root Cause](#114-prompt-cache-diagnostics-layer-3--classify-cache-miss-by-root-cause)
    - 11.5 [Context Linter — Prompt Size Control Is Cache Efficiency](#115-context-linter--prompt-size-control-is-cache-efficiency)
    - 11.6 [Conditional Router — Only Invoke the Reviewers You Need](#116-conditional-router--only-invoke-the-reviewers-you-need)
    - 11.7 [2-Pass Redaction (+47 pp Precision) — Block Metadata Anchoring](#117-2-pass-redaction-47-pp-precision--block-metadata-anchoring)
    - 11.8 [consensus-arbiter — Beyond "Same Location" to "Same Reasoning"](#118-consensus-arbiter--beyond-same-location-to-same-reasoning)
    - 11.9 [ADR-Based Decision Persistence — The WHY of Design Choices Lives in the Codebase](#119-adr-based-decision-persistence--the-why-of-design-choices-lives-in-the-codebase)
    - 11.10 [Generated File Fingerprint + Block-Merge Markers — Upgrades Don't Overwrite User Edits](#1110-generated-file-fingerprint--block-merge-markers--upgrades-dont-overwrite-user-edits)
    - 11.11 [Drift Gate + pending-drift.md — Scope Drift Is Forwarded to the Next Session](#1111-drift-gate--pending-driftmd--scope-drift-is-forwarded-to-the-next-session)
    - 11.12 [Reference Document 2-Tier Search — Only Read What's Relevant from a Large Knowledge Base](#1112-reference-document-2-tier-search--only-read-whats-relevant-from-a-large-knowledge-base)
        - 11.12.1 [Obsidian Second Brain — Typed R/W Memory with Project Namespaces](#11121-obsidian-second-brain--typed-rw-memory-with-project-namespaces)
    - 11.13 [Anti-Rot System — The Harness Itself Doesn't Go Stale](#1113-anti-rot-system--the-harness-itself-doesnt-go-stale)
    - 11.14 [7-Dimension AI Readiness + Extensible Rubric YAML](#1114-7-dimension-ai-readiness--extensible-rubric-yaml)
    - 11.15 [Deterministic Worktree Isolation](#1115-deterministic-worktree-isolation)
    - 11.16 [What Actually Enforces an Agent Boundary](#1116-what-actually-enforces-an-agent-boundary)
    - 11.17 [Single-Commit Contract + WHY-Focused Commit Messages](#1117-single-commit-contract--why-focused-commit-messages)
    - 11.18 [LLM-First Architecture — Avoid Rule-Based Systems](#1118-llm-first-architecture--avoid-rule-based-systems)
    - 11.19 [Atomic File Writes — Files Don't Corrupt on Interrupt](#1119-atomic-file-writes--files-dont-corrupt-on-interrupt)
    - 11.20 [100% Local Telemetry](#1120-100-local-telemetry)
    - 11.21 [Deep Interview (spec/plan) — Lock Architecture Through Dialogue, Not Assumptions](#1121-deep-interview-specplan--lock-architecture-through-dialogue-not-assumptions)
    - 11.22 [/hm:loop Adaptive Interview + Convergence Loop — Iterations Converge Toward the Goal](#1122-hmloop-adaptive-interview--convergence-loop--iterations-converge-toward-the-goal)
    - 11.23 [TDD Phase A.5 Gate — Verify Tests Are Genuinely RED Before Implementation](#1123-tdd-phase-a5-gate--verify-tests-are-genuinely-red-before-implementation)
    - 11.24 [`stuck` Escalation Agent — A Dedicated Analyst Intervenes on Repeated Blockers](#1124-stuck-escalation-agent--a-dedicated-analyst-intervenes-on-repeated-blockers)
    - 11.25 [6-Checkpoint Verify Gate — Dual Validation of "Done" via Diff and Health Metrics](#1125-6-checkpoint-verify-gate--dual-validation-of-done-via-diff-and-health-metrics)

---

## 1. What is harness-maker?

harness-maker is a multi-target harness generator for **Claude Code, Cursor IDE, and OpenAI Codex CLI**. Its core role is singular: **structure LLM-based development workflows** so that the same level of quality assurance (review, testing, security scanning) that applied when humans wrote code directly also applies to AI-driven development.

### What it provides

| Category | Content |
|----------|---------|
| **Commands** | 14 `/hm:` prefix slash commands (7 atomic + 4 fusion + 2 special + 1 loop) |
| **Skills** | 11 reusable capability modules invoked by commands |
| **Agents** | 12 sub-agents with specific roles |
| **Hooks** | 5 event handler types that run automatically before/after tool calls |

### Design principles

- **LLM judgment first**: LLM reads context and makes direct judgments rather than using pattern matching
- **Atomicity**: Each stage can be run independently. Coupling between stages is handled by
  `/hm:loop --per-iter-stages` or autopilot
- **Worktree isolation**: Implementation changes happen only inside `.worktrees/<name>-<ts>/` — protecting the main branch
- **Commit only in wrapup**: Even after multiple stages, a commit is created exactly once in wrapup
- **No external transmission**: All telemetry is 100% local

---

## 2. Overall Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                     User Slash Command Invocation                    │
│          /hm:research  /hm:spec  /hm:plan  /hm:execute  ...          │
└─────────────────────────┬────────────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────────────┐
│                  harness.yaml (Single Source of Truth)               │
│   locale, preset (Side/Production), dev_mode, targets (claude/cursor/codex) │
│   worktree.enabled, max_review_rounds, preferred_model, ...         │
└──────────┬───────────────────────────────────────┬───────────────────┘
           │                                       │
           ▼                                       ▼
┌─────────────────────┐               ┌────────────────────────────────┐
│   Skills (11)        │               │      Agents (12)               │
│  context-linter      │               │  code-reviewer                 │
│  worktree-isolator   │               │  plan-validator                │
│  conditional-router  │◄──invokes───►│  test-reviewer                 │
│  verify-before-      │               │  consensus-arbiter             │
│    completion        │               │  stuck (escalation)            │
│  security-scanner    │               │  autoloop-coder                │
│  refdocs-search      │               │  ...                           │
│  relevance-filter    │               └────────────────────────────────┘
│  research-crawler    │
│  ai-readiness-rubric │
│  agent-quality-rubric│
│  autoloop-driver     │
└─────────────────────┘
           │
           ▼
┌──────────────────────────────────────────────────────────────────────┐
│                     Hooks (5 Event Types)                            │
│  SessionStart → drift detection                                      │
│  PreToolUse   → permission gate / worktree gate                      │
│  PostToolUse  → telemetry / post-write reminder                      │
│  PreCompact   → session context flush                                │
│  Stop         → (currently empty)                                    │
└──────────────────────────────────────────────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────────────────────────────────┐
│                        Disk Artifacts                                │
│  work-docs/PLAN-{slug}.md     work-docs/RESEARCH-{slug}.md          │
│  specs/SPEC-{slug}.md         docs/REVIEW-{slug}-{date}.md          │
│  .claude/memory/{wiki,failures,session}.md                          │
│  .claude/observability/{metrics,security,refresh}/                  │
└──────────────────────────────────────────────────────────────────────┘
```

### File Structure Summary

```
<project>/
├── harness.yaml              ← Full harness configuration (targets, preset, locale, etc.)
├── .claude/
│   ├── commands/hm/          ← Slash command files
│   ├── skills/               ← Skill SKILL.md files
│   ├── agents/               ← Agent definition files
│   ├── settings.json         ← permissions + hook event definitions
│   ├── memory/               ← wiki.md / failures.md / session/
│   └── observability/        ← metrics.jsonl / security/ / refresh/
│       └── adaptive/         ← overrides.jsonl (0.12.0+: M18 yaml-override telemetry)
├── work-docs/
│   ├── PLAN-{slug}.md        ← Implementation plan
│   └── RESEARCH-{slug}.md    ← Research results
├── specs/
│   └── SPEC-{slug}.md        ← Acceptance criteria
└── .worktrees/               ← Isolated implementation workspace (gitignored)
    └── execute-<ts>/
```

### 0.12.0 source modules (recommendation + telemetry + audit)

Four new Python modules + one rubric YAML landed in 0.12.0 to support the personalization-depth track. They live next to the existing M1-M14 modules and follow the same conventions (typed contracts in `models.py`, atomic writes, tests in `tests/unit/`):

```
src/harness_maker/
├── recommendation.py          ← M16: Confidence-bucketed recommendation registry
├── detection_cache.py         ← M15: profile cache with manifest-mtime + 24h ceiling
├── foreign_config.py          ← M17: foreign AI config detect + LLM map + apply
├── personalization_audit.py   ← M19: composite-score rubric runner (/hm:health personalization layer)
└── rubrics/
    └── personalization.yaml   ← ADR-011 v0 rubric (locked formulas + tier boundaries)
```

---

## Render pipeline

`/harness-maker:make` (and the rendered `/hm:make`) turn `harness.yaml` into the on-disk
harness, then guide you all the way to a git decision. The flow is deliberately **not** run
inside a git worktree — `make` writes the real `.claude/`, and safety comes from a backup +
reconcile + a read-only preview, which also keeps non-git projects working.

**1. Resolve + preview (re-render only).** When `.claude/` already exists and is non-empty,
make runs `--dry-run` first and shows NEW / REPLACE / KEEP / MERGE counts (KEEP = files where
your edits are preserved verbatim; MERGE = `@hm:user:*` blocks block-merged into the new
template), then asks you to confirm before writing. A fresh install skips the preview and
applies directly. Existing generated state is copied to `.backup-<ts>/` (auto-gitignored)
before any overwrite.

**2. Apply + narrate.** Files are written; the CLI emits a stable `render-summary:` line
(`files= keep= merge= targets=`) that the slash command turns into a plain-language summary in
your locale — what changed, what was preserved, the current version. A fresh install is calm:
the structural-health scan is **quiet when clean** and only goes **loud when there are real
P0/P1 findings** (run `/hm:health` for the full scan any time).

**3. Git disposition — the last mile.** Render isn't "done" until the files are in git the way
you intend. `harness-maker git-status` inspects the rendered manifest across every selected
target root (`.claude/`, plus `.cursor/`, `.codex/`, `.agents/`, `AGENTS.md` for those
targets), minus operational churn, and reports one of:

| state | what make does |
|-------|----------------|
| not a git repo | tells you; suggests `git init` if you want tracking; runs no git commands |
| undecided (neither tracked nor ignored) | asks **neutrally** — *commit them* (share with your team) or *gitignore them* (keep local). No recommended option. |
| already committed | nothing — unless a re-render added new files, in which case it offers to stage just those (never a full re-prompt) |
| already gitignored | nothing |

The decision is **inferred from git state every run, never stored**, so re-rendering never
re-nags. Committing is clean because churn (`observability/`, iter-receipts, `.backup-*`) is
already gitignored; `git-ignore-roots` ignores the whole target roots and **fails loudly** if
the write doesn't take effect, so the slash command can't falsely report success.

---

## 3. The 7 Atomic Workflow Stages

Each of the 7 stages can be invoked as an independent slash command. Executing them in order produces a complete development cycle.

```
research → spec → plan → execute → review → verify → wrapup
```

Each stage has a **unique responsibility** and receives the output of the previous stage as input.

---

### 3.1 /hm:research — Exploration

**Purpose**: Systematically gather the information needed before implementing a new feature, choosing a product/user-workflow lens before papers or benchmarks when the topic is broad or opportunity-oriented.

#### Execution Procedure

**Phase 0 — Determine Exploration Depth**

Branches into two paths based on the presence of the `--deep` flag.

- Without `--deep`: Start gathering directly, but still calibrate the search lens.
- With `--deep`: First run the refinement interview and 3-layer deep interview gate.

**Phase 0.75 — Discovery Lens Calibration**

Every research run selects one or more lenses before gathering:

- User-workflow / product opportunity
- Technical architecture / implementation
- Research / benchmark / academic
- Risk / compliance / security

For trend, roadmap, "what should we add", or "would users use this" prompts, the user-workflow/product opportunity lens runs before arXiv, benchmark, or architecture-only searches. The research is incomplete unless it includes user-workflow evidence and a Local capability x User artifact mapping.

**Phase 1 — Information Gathering**

Parallel collection from the relevant sources:

1. **Codebase exploration**: Identify relevant files/modules, confirm existing patterns
2. **Memory exploration**: Check past failures and lessons in `.claude/memory/wiki.md` and `failures.md`
3. **Existing PLAN exploration**: Review precedents from similar tasks in `work-docs/PLAN-*.md`
4. **User-workflow/product discovery**: Search real user artifacts, adjacent tools, repeated handoff pains, ecosystem requests, and community prototypes
5. **External sources**: `refdocs-search` skill + Context7 MCP + web search when current docs or citations matter

The `refdocs-search` skill performs a 2-tier search on the reference document folders (`ref_folders`):
- Tier 1: Lightweight ripgrep index to narrow down candidate files
- Tier 2: Direct Read of the original files to confirm actual content

**Phase 2 — Analysis**

The `relevance-filter` skill scores collected items using LLM judgment:
- Default threshold: 0.7 (0–1.0)
- Automatically adjusts ±0.05 based on accept/reject ratio (adaptive threshold)
- Only items at or above the threshold are included in the RESEARCH document

**Phase 3 — Write RESEARCH Document**

Creates `work-docs/RESEARCH-{slug}.md` with 7 sections:
1. Summary (3–5 key conclusions)
2. Current Codebase State
3. Related Patterns and Precedents
4. External References (citations of collected libraries/documents)
5. Gap Analysis (current state vs. target state)
6. Recommended Approach
7. Open Questions (things to be addressed in spec)

**Phase 4 — Validation**

Confirms that the RESEARCH document has all 7 sections and that `libs_fetched` / `sources` fields are recorded in the frontmatter.

#### Outputs
- `work-docs/RESEARCH-{slug}.md` (frontmatter + 7 sections)
- Collected libraries and source list recorded in frontmatter

---

### 3.2 /hm:spec — Acceptance Criteria

**Purpose**: Clearly define "what should be built" before implementation. Writes a SPEC document through a 6-category interview.

#### Execution Procedure

**Step 0 — Check for Existing SPEC**

If `specs/SPEC-{slug}.md` already exists:
- `status: approved` + no open questions → Skip, notify that plan can proceed
- `status: draft` → Continue interview on unresolved questions only

**Step 1 — 6-Category Interview**

Converse with the user via the structured question tool (`AskQuestion` in Cursor, `AskUserQuestion` in Claude Code) to finalize 6 categories:

| # | Category | Content |
|---|----------|---------|
| 1 | **Intent** | What problem does this feature/change solve? |
| 2 | **Outcomes** | What state should exist when successful? |
| 3 | **In-Scope Scenarios** | Concrete Given/When/Then scenarios (S1, S2, …) |
| 4 | **Non-Goals** | Things explicitly out of scope |
| 5 | **Constraints** | Technical constraints (language, library, performance requirements, etc.) |
| 6 | **Verification** | How to verify each scenario (unit/integration/manual) |

In-Scope Scenarios use BDD format:
```
**Given** <precondition>
**When** <action>
**Then** <expected result>
```

**Step 2 — Write SPEC Draft**

Integrate 6-category answers into a SPEC document. Record `test_framework` in frontmatter (used by Phase A).

**Step 3 — Explicitly State Open Questions**

Record items not yet finalized in the `## ❓ Open Questions` section. Change to `status: approved` when all are resolved.

**Step 4 — SPEC Quality Gate (Step 4.5)**

Score 0–100 across 5 dimensions:
1. Scenario completeness (Given/When/Then structure)
2. Non-goal clarity
3. Verification method specificity
4. Constraint declaration
5. Open question resolution

Re-run the interview to supplement if score falls short.

**Step 5 — Save Final SPEC**

Save to `specs/SPEC-{slug}.md`. Frontmatter includes:
- `status: approved | draft`
- `test_framework: pytest | gtest | vitest | ...`
- `created: {date}`

#### Outputs
- `specs/SPEC-{slug}.md` (frontmatter + 6 categories + verification criteria table)

---

### 3.3 /hm:plan — Implementation Plan

**Purpose**: Decide "how to build it" before writing code. Finalize architecture decisions (ADRs) through a deep interview, and decompose implementation into stages.

#### Execution Procedure

**Step 0 — Skip Heuristic (skip interview if all 4 criteria are met)**

| Criterion | Skip Condition |
|-----------|---------------|
| Scope | Single file change, or configuration/documentation only |
| Architecture | No component boundary changes, no new modules |
| Contract | No API/IPC/DB schema/file format changes |
| Risk | Rollback possible within 1 hour, no user impact |

Proceed with interview if any one of the 4 applies.

**Step 1 — Internal Draft (not shown to user)**

Read the codebase and internally produce:
- Tentative architecture (components, boundaries, data flow)
- Candidate stage decomposition
- List of ambiguities sorted by blast radius

**Step 2 — SPEC Inheritance Check**

If a SPEC file exists, read it and check status:

- **Case A** — `status: approved` + no open questions: Skip interview, perform only Step 3.0 (light confirmation)
- **Case B** — `status: draft`: Do not re-ask categories resolved in SPEC; interview only remaining questions
- **Case C** — No SPEC: Full interview from scratch

**Step 3.0 — Light Confirmation in Case A**

Ask exactly one structured question (`AskQuestion` / `AskUserQuestion`):
- "Proceed directly to stage decomposition" vs "There are architecture decisions first" vs "There are several architecture questions"

**Step 3 — Interview Loop**

> **Language rule**: The live interview UI is conducted in the `harness.yaml.locale` language (ko→Korean, en→English, unsupported languages→English fallback). However, **PLAN documents saved to disk are always in English**. Free-text user answers are translated to English in Step 5 for archiving.

Unlimited rounds. Each round follows steps A through E:

**A. Visualize Current Plan State** (when needed):
- Default: prose/bullet format
- For comparison: tables
- For topology: ASCII boxes
- Mermaid: only in the final PLAN document (renders as raw text in terminal)

**B. Structured question** (in priority order):
1. Scope boundaries (in/out, whether breaking compatibility)
2. Architecture (component ownership, pattern selection)
3. Contract shape (API signature, schema, file format)
4. Risk tolerance (incremental vs big-bang, rollback strategy)
5. Testing depth (unit/integration/manual)
6. Implementation order (feature flags, dependencies)
7. Dependencies (add library vs implement directly)
8. Failure handling (retry policy, circuit breaker)
9. Observability (log level, metric names)

From round 2 onward, offer "Interview sufficient — end" option.

**C. Record Answer as Interview Entry**

| # | Topic | Category | Question | Choice | Notes | → ADR |

**D. ADR Promotion Check**

Create an official **ADR (Architecture Decision Record)** if any of the following apply:
- Component boundary/ownership change
- New contract (API, IPC, schema) introduced/changed
- Reasonable alternative explicitly rejected
- Decision with long-term impact
- Future flexibility restricted (framework, library lock-in)

ADR format:
```markdown
### ADR-{NNN}: {Title}
**Status:** Accepted ({date}, via /hm:plan interview)
**Context:** Why this decision was needed
**Decision:** What was chosen
**Consequences:**
- ✅ Positive outcomes
- ⚠️ Accepted trade-offs
**Rejected alternatives:** Rejected alternatives and reasons
**Source:** Interview #{N}
```

**E. Exit Check**

End interview when user selects "sufficient — end" or all high-impact ambiguities are resolved.

**Step 4 — Invoke plan-validator Agent**

After the interview ends, pass the completed PLAN draft to the `plan-validator` agent:

- `APPROVED` → Save PLAN as-is
- `NEEDS_REVISION` / `MAJOR_REVISION` → **the follow-up rounds are planned by CLI, not one per
  critique.** `hm plan_rounds plan` returns the critiques that earn a round and, for every one
  that does not, the reason. Then re-validate **once** (the cap is two passes); if the second
  pass is still `MAJOR_REVISION`, escalate to the user.

Two rules do the cutting, and both are transfers from `/hm:review`'s loop:

- **The progress invariant.** A critique the previous pass raised and this pass raises again is
  `unresolved`, not `pending` again — the revision did not answer it, and asking a second time
  is the round that produced nothing. Ids are computed from (section, title) rather than asked
  of the model: an LLM-minted id changes every run, which turns merge-by-id into "everything is
  new" and the invariant can then never fire.
- **Churn, INVERTED.** In `/hm:review` a *low* churn ratio skips the re-review. Copying that
  shape here would say "small edit, skip re-validation" — and this stage's own measurement
  refutes exactly that: twelve recorded `plan-validator` episodes, **none ever clean**, and one
  PLAN whose pass-2 criticals were *created by the pass-1 fixes*. What transfers is the other
  direction: once a revision has rewritten more than half the PLAN, the critiques still queued
  were raised against a document that no longer exists, so they go `stale` and cost no round.
  Nothing is lost — Step 4.5's terminal pass re-derives whichever still hold. An **unmeasured**
  ratio runs every round.

The lens axis does **not** transfer: `plan-validator` is a single agent, not a fan-out.

`hm plan_rounds outcome` then records `no-progress` separately from `cap-exhausted`. A bare
two-pass limit reports the same ending for both, hiding the one that means the revision step is
not working on this document at all.

**Step 5 — Write PLAN Document**

`work-docs/PLAN-{slug}.md` with 10 required sections:
1. 🎯 Executive Summary
2. 📚 Prior Work
3. 🎙️ Interview Transcript
4. 📐 Architecture Decision Records
5. 🏗️ Technical Design
6. 📝 Implementation Plan (each stage: scope / exit criterion / risk / rollback point)
7. 🧪 Testing Strategy
8. ⚠️ Risks & Mitigation
9. ✅ Success Criteria
10. 🔍 Plan Validation

Each implementation stage has **4 required fields**: scope, exit criterion (executable command), risk level (`low|medium|high`), rollback point.

**Step 6 — Post-Save Validation**

Read the file and verify: frontmatter present, Interview Transcript section exists, ADR count matches, all 4 fields present.

#### Outputs
- `work-docs/PLAN-{slug}.md` (frontmatter + 10 sections)
- ADR set (ADR-001, ADR-002, …)

---

### 3.4 /hm:execute — TDD Implementation

**Purpose**: Implement each PLAN stage using TDD. The 4-step cycle of writing tests first, verifying test quality, implementing, then validating is repeated for each PLAN stage.

> **0.12.0 scope expansion**: execute now covers the M16 recommendation registry (`src/harness_maker/recommendation.py`) and the M17 foreign-config apply path (`src/harness_maker/foreign_config.py`). When a PLAN stage touches either, the conditional router routes the diff to `code-reviewer` (plus `security-reviewer` for `foreign_config.py` because of LLM-mapped input handling).

#### Execution Procedure

**Step 0 — Worktree Isolation (Deterministic Execution)**

Directly execute what the `worktree-isolator` skill describes using the harness-maker CLI:

```bash
uv run python -m harness_maker.worktree create execute "$(pwd)"
```

Output branches:
- **Absolute path** (`/path/to/.worktrees/execute-20260509T0402Z`) → Isolation active. Use this path (`<WT>`) for all subsequent file access
- **Empty output** → `worktree.enabled` is false. Work in current directory without isolation

> **Note**: Each `!` block is an independent subshell, so shell variables do not persist. `<WT>` must be substituted with the literal absolute path each time.

**Step 1 — Parse PLAN and Flags**

Fully read `work-docs/PLAN-{slug}.md` and extract:
- Stage list (scope/exit-criterion/risk/rollback)
- ADRs (binding constraints — cannot be violated during implementation)
- `spec:`, `research_doc:` references from frontmatter

Set `tdd_active` based on presence of `--no-tdd` flag.

**Step 2 — Resolve SPEC and RESEARCH Cache**

If SPEC file exists, fully read it to extract:
- `test_framework` → used in Phase A
- `## 📋 In-Scope Scenarios` → Phase A test targets
- `## ✅ Verification Criteria` → Phase B RED gate commands

If RESEARCH file is older than `mtime_warn_days` (default 7 days): warn then proceed, record staleness in the PLAN.

**Step 3 — Per-PLAN-Stage TDD Machine**

For each PLAN stage, execute phases in order: A → A.5 → B → C → D

#### Phase A — Write Tests (skipped if `tdd_active=false`)

Write test files based on SPEC In-Scope Scenarios:

1. Write test files in the project's test directory using the `test_framework`
2. Include scenario ID in function name: `test_s1_<name>`, `test_s2_<name>`
3. Assertions exactly match the `**Then**` clause of each scenario
4. **Tests must initially be RED** — they depend on functions that don't yet exist

#### Phase A.5 — test-reviewer Gate (skipped if `tdd_active=false`)

Dispatch **three** `test-reviewer` calls **in one message**, one per lens:

```
Task(subagent_type="test-reviewer", prompt="<brief>\n\nYour lens: red-correctness — …")
Task(subagent_type="test-reviewer", prompt="<brief>\n\nYour lens: discrimination — …")
Task(subagent_type="test-reviewer", prompt="<brief>\n\nYour lens: coverage — …")
```

The lenses are disjoint detectors, not redundant voters: measured against a serially-retried
single reviewer that surfaced one failure category per round, the three concurrent lenses
surfaced 9 and 12 findings with **zero overlap between the two blocking lenses**.

Result handling — **merge all three before judging**; a lens passing its own rubric does not
end the round:
- `overall_assessment` is **recomputed**, never taken from a lens's own header: PASS iff every
  lens dispatched in THIS round returned PASS *and* the merged carriers are clean. Any FAIL,
  dead dispatch or unparseable JSON → round FAIL.
- `blocking_issues[]` — union, deduped on `test_file:test_function:category`, carrying the
  union of the `line`s. **Authoritative**: the repair rewrites exactly these.
- `scenarios_missing[]` — union by scenario id. `per_scenario[]` — worst `quality`, union
  `covered_by`. `passing_tests[]` — intersection, **advisory, it decides nothing** (bare
  function names cannot identify a test; there is no `passing_tests[]` freeze).
- Round FAIL → three repair arms, one per carrier: rewrite the functions in `blocking_issues[]`,
  author one test per `scenarios_missing[]`, retarget-or-delete for a `per_scenario[]` FAIL with
  no matching blocking entry. **If you repaired anything, re-dispatch all three lenses** (plus,
  unchanged, any lens whose dispatch died).
- Budget is **2 rounds**, not 2 attempts — no verdict carries between rounds. After 2 failing
  rounds: surface the merged verdict and escalate to user.

#### Phase B — RED Gate (skipped if `tdd_active=false`)

Execute the test commands from SPEC `## ✅ Verification Criteria`:

```bash
cd <WT> && <test_command>
```

Expected result: **FAIL for the right reason** (no implementation, not a syntax error).
If it accidentally PASSes → Return to Phase A for rewriting (false-RED should have been caught in Phase A.5).

#### Phase C — Implement to GREEN

Write implementation code. Constraints:
- **No untested code paths** — all public functions covered by Phase A tests
- **ADRs must not be violated** — ADR conflicts are recorded as Phase D blockers
- Compile/type-check after each edit (no batching)

#### Phase D — Post-GREEN Validation

```bash
cd <WT> && ruff check          # lint
cd <WT> && mypy --strict       # type check
cd <WT> && pytest tests/ -q    # full test suite
cd <WT> && <exit-criterion>    # PLAN stage exit criterion
```

Failure handling:
- Compile/type/lint failure → Return to Phase C to fix
- New test failures → Regression. Find and fix or rollback the offending change
- Exit criterion failure → PLAN stage incomplete. Fix or escalate

**Step 4 — Stage Completion (no commit)**

After all PLAN stages are GREEN:
1. Verify worktree working tree is clean (no out-of-scope edits)
2. **Leave changes as staged or unstaged — do not run `git commit`**
3. Update stage status in PLAN file (in-progress/done/blocked)

When a stage blocker occurs:
- Document the blocker in the relevant PLAN stage
- Display to user with exact failure output
- No silent scope changes allowed

**Step 5 — Finalize Worktree**

On success:
```bash
uv run python -m harness_maker.worktree finalize <WT> stage-only
```

On blocker:
```bash
uv run python -m harness_maker.worktree finalize <WT> fail
```

`stage-only`: stage-merge branch to main then delete worktree (commit is handled by wrapup).

#### Outputs
- Code + tests **staged but uncommitted** (commit happens in `/hm:wrapup`)
- PLAN file with updated stage status (likewise uncommitted)

---

### 3.5 /hm:review — Code Review

**Purpose**: Multiple specialist reviewers independently examine the implemented changes, reach consensus, and produce a quality grade. Automatically enters a fix loop if issues are found.

#### Execution Procedure

**Step 1 — 2-Pass Redaction (METADATA, not diff noise)**

> **Corrected.** This section previously described Pass 1 as structural removal of logs and
> lock files and Pass 2 as "semantic redaction" of the diff. That is not what the two passes
> do, and it mis-attributed the measured result: the +47 pp came from hiding **metadata**, not
> from trimming the diff. The diff is never redacted — reviewers need it whole.

The anchoring source is the PR title, description, author and commit message: a reviewer that
reads "small refactor, no behaviour change" grades the diff against that claim.

- **Pass 1 — rubric only.** `hm two_pass_review redact --file <path>` replaces those four
  fields with `[REDACTED]`; reviewers judge the code against the rubric alone. This is where
  the **+47 percentage-point precision gain** on anchoring-prone diffs was measured.
- **Pass 2 — contextual verdict.** The same reviewers run again with metadata restored and the
  raw Pass-1 findings, dropping any the context proves spurious and adjusting severity.
  Pass 2 is authoritative: a Pass-1 finding absent from Pass 2 is dropped.
- `hm two_pass_review merge --file <path>` merges them. **Both commands take a file path, never
  `echo '<json>' |`** — their inputs are the diff itself and reviewer prose about it, so one
  apostrophe in a changed line used to end the shell quoting and run the rest.

There is no verifier between the passes; that dispatch was removed after it dropped 5 of 261
findings (1.9 %) while costing a full serialized agent round-trip on every review.

**Step 2 — the lens axis (what runs), then routing (what is mandatory)**

Round 1 dispatches **seven lenses**, on both presets:

| Lens | Asks |
|---|---|
| `design` | Is the structure right — boundaries, coupling, needless complexity? |
| `functionality` | Does it do what it claims, including on the edges? |
| `robustness` | What happens when the inputs or the environment misbehave? |
| `consistency` | Does it match the conventions and the naming already here? |
| `security` | Secrets, injection, authz, unsafe permission grants |
| `concurrency` | Races, deadlocks, ISR safety, async correctness |
| `tests` | Do the tests discriminate, or would they pass a wrong implementation? |

Six textbook categories were merged to four core ones on **measured** redundancy — the share of
a lens's findings that another lens also raised: `consistency` 80 %, `design` 50 %,
`complexity` 40 %, `robustness` 40 %, `functionality` 33 %, `naming` 14 %, and `security`,
`concurrency`, `tests` all **0 %**. `complexity` folded into `design` and `naming` into
`consistency`; the three zero-overlap domain lenses were kept exactly because nothing else
sees what they see.

The conditional router decides which lenses are **mandatory**, not which are dispatched:
Production requires all seven, Side requires the four core ones and routes the three domain
lenses by path pattern (`.env` / `/auth/` → `security`, `thread` / `async` → `concurrency`, …).
**Both dispatch all seven** — a router can only drop what was dispatched, and a lens that never
ran cannot be routed back in.

`hm lens_coverage check` computes which lenses actually delivered, from result files keyed by
`<slug>/<run-id>/<round>/`. A missing file is the signal that a dispatch died; the coverage
verdict, not the executing model's self-report, is what the approval gate reads.

**Step 3 — Parallel Review Execution**

Lenses run simultaneously and independently in one message. Each reviewer is a **read-only**
agent — they return findings without modifying code, and each finding is stamped with the lens
that raised it plus a stable `id` computed by `hm codex_adapter stamp-ids` (a model-minted id
changes every round, which breaks the round-to-round merge).

Each finding structure:
```json
{
  "severity": "P0 | P1 | P2",
  "file": "path",
  "line": line_number,
  "summary": "what is wrong (≤80 chars)",
  "suggestion": "specific fix method (≤200 chars)",
  "reasoning": { "observe": "...", "trace": "...", "infer": "...", "conclude": "..." }
}
```

P0/P1 require 4-step reasoning (Observe → Trace → Infer → Conclude).

**Step 4 — consensus-arbiter Agreement Filter**

The `consensus-arbiter` agent integrates findings from multiple reviewers:

**Surface Match** (same file + line±5 + same severity tier):
- **One reviewer-lens voice is enough** → `consensus-passed`. Two lenses agreeing is
  corroboration, not the evidentiary bar: requiring it discarded precisely the findings only
  one specialist could have seen, and the three domain lenses have 0 % overlap with anything.
- K=2 still applies where a second voice is genuinely independent evidence: **cross-model**
  voters, and the same lens speaking more than once.
- No voice at all → `manual-only`. The tag table is monotonic in voices — adding a voice can
  never weaken a finding's tag.

**Reasoning Alignment** (step-by-step alignment of OBSERVE→INFER→CONCLUDE):
- Even at the same location, different reasoning means weak consensus
- Scope-limited findings (specific to one reviewer's domain) are exempt from cross-check → automatic consensus-passed

Consensus tags: `consensus-passed | weak-consensus | manual-only`

**Step 5 — Grade Calculation**

Grade based on P0/P1 count:

| P0 | P1 | Grade |
|----|-----|-------|
| 0 | 0 | **A** |
| 0 | 1–2 | **B** |
| 0 | ≥ 3 | **C** |
| 1–2 | * | **D** |
| ≥ 3 | * | **F** |

**Step 6 — Automatic Fix Loop**

If grade falls below `grade_threshold` (default A), enter the automatic fix loop:

```
review → fix → measure churn → (maybe) re-review → regrade → …
```

- The executor applies P0/P1 findings in order; a fix that breaks the build is reverted.
- **The re-review is gated on churn.** Each round's churn is measured between two pinned
  trees — the round's own pre-fix and post-fix state, never `HEAD`, because `/hm:review` does
  not commit and `HEAD..HEAD` would read 0.0 for every round. It aggregates as the **maximum
  across touched files**, so a one-line edit to a 5000-line file cannot mask a 30-line file
  rewritten whole. Below `reviewers.rereview_churn_ratio` (default 0.20) the re-review is
  skipped and the comparison recorded; at or above it, exactly **one** structured reviewer runs.
  A round whose churn could not be measured (all-binary diff) re-reviews anyway — unmeasured is
  not "below the threshold". `rereview_churn_gate: false` restores the pre-gate behaviour.
- **Three endings, reported as three different things:** the grade meets the threshold *and* a
  confirmation pass over a frozen artifact finds nothing new (`converged`); no lifecycle
  transition happened in a round (`no-progress`); or the rounds ran out (`cap-exhausted`).
  Reporting the cap for a no-progress stop hides the one that says the loop is not working.
- **Oscillation is reported, never graded.** A hunk one round removes and a later round
  restores — keyed on (path, normalized content, enclosing symbol) — is a `manual-only` P1
  `spec_gap`: two rounds disagreed about the same code, which is a gap in the SPEC rather than
  a defect in the diff, and it must not make grade A unreachable.

**Step 7 — Save REVIEW Document**

Save to `work-docs/REVIEW-{slug}-{date}.md`:
- Final grade
- Each finding with consensus tag
- Fix loop history

#### Outputs
- `work-docs/REVIEW-{slug}-{date}.md`
- Changes staged (if fixes were applied)

---

### 3.6 /hm:verify — Completion Verification

**Purpose**: The final gate before committing. Inspects 6 checkpoints in order and blocks on the first failure.

#### 6 Checkpoint Details

**Check 1 — PLAN/SPEC Fulfillment (Direct LLM Judgment)**

Human judgment. Not delegated to subprocess:
```bash
ls work-docs/PLAN-*.md        # find PLAN file
git diff HEAD~1 HEAD           # confirm changes
```
LLM directly cross-references each PLAN item against the diff. Checking a checkbox alone is not sufficient for PASS — actual code changes must exist.

Failure: `BLOCKED: check 1 (PLAN-fulfillment) — <item> not found in diff`

**Check 2 — Regression/Smoke Gate**

```bash
bash .claude-verify.sh phase_${CURRENT_PHASE}
```
Run the project-specific verification script.

**Check 3 — Health Score Within Baseline -5**

Calculate current composite score with `compute_readiness()`.
FAIL if score drops 5 or more points below baseline in `.claude/observability/metrics.jsonl`.

**Check 4 — Anti-Rot Pending Resolved**

```bash
test ! -f .claude/observability/refresh/pending.jsonl || \
  grep -q '"action":"defer"' .claude/observability/refresh/pending.jsonl
```
FAIL if there are unprocessed refresh proposals (deferred items are OK).

**Check 5 — No High-Severity Security Findings**

```bash
count=$(grep -c '"severity":"high"' .claude/observability/security/findings.jsonl)
[ "$count" -eq 0 ]
```

**Check 6 — Worktree Merge-Safe**

```bash
git diff --check
git merge-tree $(git merge-base HEAD main) HEAD main | grep -q "<<<<<<<" && exit 1
```
Confirm no conflict markers.

#### Failure Behavior

Stop immediately at the first failing check:
```
BLOCKED: check <N> (<name>) — <reason>
```

Remediation hints for each blocking check:
- PLAN unfulfilled → Display list of incomplete items
- Smoke failure → Re-run failing tests
- Health score drop → Display 6-dimension breakdown
- Stale-asset drift → guide the user to re-render with `/harness-maker:make`
- Security high → Display findings list
- Merge conflict → Display conflicting paths

With `--force` flag, continue without stopping at first failure (results recorded in jsonl).

#### Outputs
- Text result + `.claude/observability/verify-{date}.jsonl`

---

### 3.7 /hm:wrapup — Commit Finalization

**Purpose**: The final stage of the entire workflow. Creates exactly one commit, updates memory, and cleans up the work.

#### Execution Procedure

**Step 1 — Pre-Flight Check**

- Confirm staged changes exist
- Re-confirm type check, lint, and test passage
- Confirm no out-of-scope edits (vs PLAN scope)

**Step 2 — Final Verify Pass**

Execute the 6 checks from `verify-before-completion` skill. Abort commit if any FAIL.

**Step 3 — Drift Gate**

Confirm no unexpected file changes. Compare `git diff --stat` results against PLAN scope.

**Step 4 — Update PLAN Status**

Change `status:` in `PLAN-{slug}.md` from `planning` → `complete`.

**Step 5 — Update Memory**

Update two memory files (the session tier is checkpoint-only, written by the `flush_session` hook — not wrapup):
- `.claude/memory/wiki.md` — Add reusable patterns/conventions
- `.claude/memory/failures.md` — Failures encountered in this work and their solutions

**Step 6 — Create Commit**

```bash
git add <scope-files>
git commit -m "$(cat <<'EOF'
<type>: <short subject>

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

Exactly **one commit**. Even after multiple stages, the commit is always created here, exactly once.

Commit types: `feat | fix | chore | ci | test | docs | refactor`

#### Outputs
- git commit created
- Updated memory files
- PLAN file with `status: complete`

---

## 4. Fusion Commands

There is no fusion command. The seven atomic stages are chained by `/hm:loop` <!-- @hm:axis-removed -->
(`--per-iter-stages`, default `execute,review`) or by autopilot's `autonomy.pipeline`.
The fused-workflow axis was removed in 0.47.0 — see PLAN-harness-diet ADR-001/002/014. <!-- @hm:axis-removed -->

---

## 5. /hm:loop — Automated Iteration Loop

**Purpose**: Progressively improve toward a single goal through multiple iterations. Each loop uses one shared worktree, and safety rails prevent infinite loops.

> **Learned pattern (PLAN-personalization-depth-2026-05, validator W5)**: validator-driven phase merge. When two adjacent loop phases produce overlapping diffs that the validator can collapse without losing signal, the loop merges them — saving one iteration round and one set of reviewer spawns. This is now a default pattern, not an opt-in.

### Two Modes

| Mode | Usage | Behavior |
|------|-------|----------|
| **feature** | `/hm:loop --mode feature <description>` | Incrementally implement a new feature over multiple iterations |
| **improve** | `/hm:loop --mode improve <description>` | Review first, then iteratively improve existing code until exit criteria pass |

### Required Context + Loop Intensity

Before starting the loop, the `autoloop-driver` skill collects required dimensions and locks the loop intensity:

| Dimension | Content |
|-----------|---------|
| **purpose** | What this loop aims to achieve |
| **invariants** | Invariants that must never be broken |
| **priority** | What takes precedence: quality vs speed vs coverage |
| **test_reliability** | Are tests trustworthy? Are there flaky tests? |
| **stopping_criteria** | When to judge the loop complete |

The intensity tier (`quick`, `standard`, `thorough`, or `maximum`) determines which exit checks are required. **Coverage-based adaptive interview**: LLM reads the user's initial description, extracts already-answered dimensions, and asks questions about **only the missing dimensions**. No fixed script.

### Iteration Cycle

```
Loop start
│
├─ Create worktree (one per loop — not recreated per iteration)
│
└─ Iteration 1, 2, 3, ... (until safety rail is reached)
   │
   ├─ Load context (previous iteration results, current state)
   ├─ Set goal for this iteration
   ├─ Run the per-iter stages (default: execute → review)
   ├─ Run verify-before-completion skill
   ├─ Run 4-gate convergence check
   └─ If convergence streak >= 2 → end loop / If not → next iteration
│
└─ Run wrapup (exactly once for the entire loop)
```

### Safety Rails

| Rail | Default | Meaning |
|------|---------|---------|
| `max_iter` | 30 | Maximum number of iterations |
| `max_time` | 8 hours | Maximum execution time |
| `failed_streak` | 5 | Stop after repeated consecutive failures |
| `same feature retry` | 3 | Stop when feature mode keeps retrying the same feature |
| `ambiguity count` | 3 | Ask the user when an exit criterion remains ambiguous |

### Example Loop Scenario Trace (feature mode, 3 iterations)

```
1. /hm:loop feature "Add error handling to CSV parser"
2. autoloop-driver analyzes description → purpose confirmed, invariants/priority unconfirmed
3. Structured question: "What are the invariants and priority?"
4. User reply: "Maintain existing API, quality first"
5. Loop starts, worktree created: .worktrees/autoloop-20260509T0500Z
6. [Iteration 1] Implement error type classification logic + tests → review → Grade B
7. verify-before-completion → PASS
8. 4-gate convergence: mechanical PASS, criterion PARTIAL, regression PASS, streak reset
9. [Iteration 2] Add error message localization → tests → review → Grade A
10. 4-gate convergence: all pass, streak=1
11. [Iteration 3] Re-check without regression: all pass, streak=2
12. Loop ends, wrapup executed (single commit)
```

---

## 6. Special Commands

> **These three commands no longer exist as separate names.** ADR-0006 consolidated
> `hm:ai-readiness`, `hm:refresh`, and `hm:personalization-audit` into a single
> `/hm:health`, and ADR-0007 then collapsed that command to **two** layers.
>
> - `hm:ai-readiness` → `/hm:health`'s **structural** layer (§6.1). The rubric runner
>   `ai_readiness.py` is unchanged.
> - `hm:personalization-audit` → `/hm:health`'s **personalization** layer (§6.2).
>   `personalization_audit.py` is unchanged.
> - `hm:refresh` (anti-rot crawl) → **removed outright**, not renamed. ADR-0007 deleted
>   the crawler modules, the relevance filter, the stale-asset code, and the command
>   template after a production run surfaced 12 items of which 11 were rejected — 91%
>   noise. The one source worth keeping, OSV CVE detection, survives independently as
>   `secscan/dependency_cves.py`, consumed by `/hm:verify` Check 4. There is no
>   replacement command for the crawl; the section that described it was deleted rather
>   than rewritten, because the feature is gone.

---

### 6.1 /hm:health — structural layer

**Purpose**: Evaluate how suitable the current codebase is for AI-assisted development using a 3-layer rubric, and present an improvement roadmap.

#### 3-Layer Rubric Structure

```
Composite Score = 70% × readiness + 25% × llm_judge_avg + 5% × cache_score
```

**Layer 1 — Deterministic Signals (Automatic)**

Quantitative measurements:
- Documentation ratio (docstrings, README)
- Test coverage
- Type hint completeness
- Module coupling
- File size distribution

**Layer 2 — LLM Rubric Judgment**

LLM evaluates rubric YAML files:
- 0–100 score for each rubric item
- Includes OBSERVE→INFER→CONCLUDE reasoning chain
- `llm_judge_avg` = average of all rubric items

**Layer 3 — Cache Diagnostics**

Anthropic prompt cache efficiency analysis:
- Context hit rate
- TTL exhaustion patterns
- Cache inefficiency root cause analysis

#### Execution Procedure

**Step 1 — Structural Analysis**

```bash
uv run python -m harness_maker.cli ai-readiness .
```

Layer 1 (deterministic) + Layer 3 (cache) analysis. Returns results as structured JSON.

**Step 2 — LLM Rubric Evaluation**

Layer 2: LLM evaluates each rubric YAML in sequence.
Example rubrics: `readability.yaml`, `testability.yaml`, `modularity.yaml`

**Step 3 — Write Dashboard**

Integrate 3-layer scores to create `docs/ai-readiness-{date}.md`:
- Overall composite score
- 6-dimension breakdown
- Detailed rationale for each dimension

**Step 4 — Determine Improvement Priority**

Classify discovered issues into two categories:
- **AI-fixable**: Things that can be automatically improved with `/hm:loop improve`
- **Human-required**: Things requiring human involvement such as architecture decisions

Propose a `/hm:loop` command for each AI-fixable item.

#### Outputs
- `docs/ai-readiness-{date}.md` (dashboard)
- `ImprovementPlan` structure (can be passed to the loop)

---

### 6.2 /hm:health — personalization layer

**Purpose**: Compute a personalization fit score from accumulated telemetry (M18 overrides) + the current harness.yaml + the cached ProjectProfile, then emit a ranked list of action items so the user can see *which* harness axes are mis-tuned to their actual workflow.

Added in 0.12.0 as the final M19 mechanism. Local-only — zero network calls (asserted by `tests/unit/test_no_network.py`, per ADR-005).

#### 3-Layer Rubric Structure (per ADR-011 v0, locked)

```
Composite = L1 conversion × 0.4 + L2 stability × 0.3 + L3 cadence × 0.3
```

**Layer 1 — Conversion (recommendation acceptance)**

```
L1 = (medium_accepted + high_silent) / max(total_recommendations, 1) × 100
```

How often the M16 recommendation registry's HIGH-confidence silent defaults were left in place + how often MEDIUM-confidence prompts converted to acceptance. Low conversion means we are recommending things the user does not want.

**Layer 2 — Stability (override volatility)**

```
L2 = 100 - min(100, override_events_last_30d × 5)
```

Penalises projects where the user keeps flipping harness.yaml axes back and forth — that signals we got the recommendation wrong and they are working around it.

**Layer 3 — Cadence (audit + telemetry hygiene)**

```
100  if (audit run within last 14 days) AND (disable_telemetry == False)
 50  if exactly one of the two is true
  0  otherwise
```

#### Tier Boundaries

| Tier | Composite range |
|------|-----------------|
| **Bronze** | < 40 |
| **Silver** | 40 – 64 |
| **Gold** | 65 – 85 |
| **Platinum** | ≥ 85 |

#### Output

`PersonalizationPlan`:
- Composite score (0-100) + per-layer scores (L1, L2, L3)
- Ranked `PersonalizationActionItem` list, each with mandatory `evidence = {n_observations, top_3_signals, confidence}`

**Evidence-drop rule** (per ADR-010 mode C noise mitigation): action items lacking `n_observations` OR lacking `top_3_signals` are dropped before ranking. Recommendations whose justification is thinner than the recommendation itself never reach the user.

#### Execution Procedure

**Step 1 — Load inputs**

- `.claude/observability/adaptive/overrides.jsonl` (M18 telemetry, schema_version-aware)
- `harness.yaml` (current axis values)
- `~/.cache/harness-maker/profile-<repo-hash>.json` (M15 cached ProjectProfile)

**Step 2 — Compute layer scores**

`personalization_audit.run_audit()` reads `rubrics/personalization.yaml` and applies the locked formulas above. The same `rubric_loader` pattern from `ai_readiness.py` is reused — adding new layers later is just a YAML edit + a small Python change.

**Step 3 — Generate + filter action items**

Each layer can contribute action items. The evidence-drop rule (ADR-010) prunes any item missing `n_observations` or `top_3_signals`.

**Step 4 — Render report**

Composite score, tier, layer breakdown, and the surviving action items.

#### Local-only guarantee

`tests/unit/test_no_network.py` blocks all outbound socket calls during audit runs. ADR-005 makes this a positive obligation — the audit must work fully offline.

#### Outputs

- Stdout report (composite + tier + layer + action items)
- No file written — the audit is a read-only diagnostic. Re-running gives a fresh snapshot.

#### Calibration note

The v0 rubric is provisional. Tier boundaries and weight coefficients should be revisited once 30+ projects have accumulated audit runs (per ADR-011 deferred decision).

---

## 7. Skills Reference

Skills are reusable capability modules invoked by commands. Unlike agents, they have no independent execution context and run within the context of the invoking command.

### 7.1 agent-quality-rubric

**Role**: Evaluates the quality of agent files on a 4-tier scale.

**Tier grades**:
- 🥇 Platinum: Both static structure and Layer-2 LLM judgment are top-rated
- 🥈 Gold: Excellent static structure, average LLM judgment
- 🥉 Silver: Some structural issues
- 🟫 Bronze: Insufficient structure, automatically flagged for anti-rot

**Evaluation process**:
1. Static structure check (frontmatter completeness, section presence, permission declaration)
2. Layer-2 LLM rubric (prompt quality, reasoning guide clarity)
3. Composite score calculation
4. Bronze → register in anti-rot pending queue

**Triggers**: `/hm:health` (structural layer)

---

### 7.2 ai-readiness-rubric

**Role**: Core skill executing the 3-layer rubric for `/hm:health`'s structural layer. Entry point via `run_ai_readiness()` function.

**Input**: `Path` (project root), `Preset` (Side/Production)
**Output**: `ImprovementPlan` (scores + priority improvements + loop suggestions)

See [Section 6.2](#62-hmai-readiness--ai-readiness-analysis) for 3-layer details.

---

### 7.3 autoloop-driver

**Role**: Explains the WHY of the `/hm:loop` command and defines the method for collecting loop context, intensity, and exit criteria.

**Key contributions**:
- Define 5 required dimensions (purpose, invariants, priority, test_reliability, stopping_criteria)
- Coverage-based adaptive interview principle (extract first, ask later)
- Define the 4-gate convergence model and safety rails

This skill is a **documentation skill** — it does not execute code directly, but provides guidance on how the `/hm:loop` command should behave.

---

### 7.4 conditional-router

**Role**: Analyzes diff file paths to determine which specialist reviewers to invoke.

**Routing table**:

| File Pattern | Reviewer | Example Path |
|-------------|----------|-------------|
| `.env`, `/auth/`, `/secret` | security-reviewer | `src/auth/login.py` |
| `/perf/`, `benchmark`, `hot` | performance-reviewer | `tests/benchmark/sort.py` |
| `.tsx`, `.jsx`, `/ui/` | ux-reviewer | `src/ui/Button.tsx` |
| `thread`, `isr`, `worker`, `async` | concurrency-reviewer | `lib/async_worker.py` |
| **(always)** | code-reviewer | — |

code-reviewer is always included. Others are added based on pattern matching.

---

### 7.5 context-linter

**Role**: Checks that CLAUDE.md, agent, skill, and workflow files do not exceed per-preset line count limits.

**Per-preset limits**:

| Asset Type | Side Preset | Production Preset |
|-----------|------------|------------------|
| CLAUDE.md | ≤200 lines | ≤500 lines |
| Agent prompt | ≤300 lines | ≤300 lines |
| Skill SKILL.md | ≤300 lines | ≤300 lines |
| Workflow | ≤300 lines | ≤600 lines |
| `.cursor/rules/*.mdc` | ≤500 lines (Cursor recommended) | ≤500 lines |

When limit exceeded: renderer emits a warning. Automatically detected during `/hm:health`'s structural scan.

---

### 7.6 refdocs-search

**Role**: Performs a 2-tier search on user-registered reference document folders.

**Supported formats**: `.md`, `.txt` (ripgrep), `.pdf` (Read multimodal)
**Not supported**: DOCX (cannot search directly without conversion)

**2-tier search process**:
1. **Tier 1 (lossy index)**: keyword matching with ripgrep → narrows to candidate file list
2. **Tier 2 (source verification)**: directly Read candidate files to confirm actual content

For PDFs, process page-by-page with multimodal Read.

**Trigger**: When `/hm:research --deep` is executed

---

### 7.7 relevance-filter

**Role**: LLM reads the collected item list and assigns relevance scores for filtering.

**Adaptive threshold**:
- Starting value: 0.7
- If accept rate is high → threshold +0.05 (stricter, less noise)
- If reject rate is high → threshold -0.05 (more lenient, miss less)
- Range: 0.5 ~ 0.9

**Used in**: `/hm:research` (Phase 2)

---

### 7.8 research-crawler

**Role**: Crawls 4 external sources and saves results to a JSONL file.

**Crawler modules**:
```python
anthropic_blog.crawl()    # Anthropic blog/changelog
github_releases.crawl()   # GitHub releases (claude-code + referenced repos)
arxiv.crawl("cat:cs.SE OR cat:cs.CL OR cat:cs.CR")
osv_dev.crawl(packages=osv_dev.parse_uv_lock("uv.lock"))
```

**Behavioral characteristics**:
- All 4 sources are executed (if one fails, the rest continue)
- Skip crawl if raw file exists within 24 hours
- Offline state: silently skip + stderr warning
- **No direct changes** — only saves raw data. The consumer that applied it (`hm:refresh`) was removed by ADR-0007; only the OSV CVE path survives, read by `/hm:verify` Check 4

**Output**: `.claude/observability/refresh/raw-{date}.jsonl`

---

### 7.9 security-scanner

**Role**: Executes a 7-gate security scan and saves findings to JSONL.

**7 gates**:

| Gate | Content | Severity |
|------|---------|---------|
| 1. Secrets | API keys, tokens, passwords via regex | high |
| 2. Permissions | catch-all `Bash(*)`, excessive path patterns | high/medium |
| 3. Hook injection | `rm -rf`, `curl \| sh`, `eval`, reverse shell | high |
| 4. CVEs | OSV.dev-based dependency vulnerabilities (CVSS ≥7 → high) | high/medium/low |
| 5. Prompt injection | zero-width characters, "ignore previous", base64 blocks | medium/high |
| 6. Hallucination | non-existent imports detected without executing generated code | medium/high |
| 7. Prod-name guard | production resource names in dangerous tool-call sequences | high |

For gate 5 (Prompt injection):
- Regex first-pass filtering, then
- **LLM directly reads candidates** to judge if they are genuine injection attempts or false positives
- Severity adjustable based on LLM judgment

**Output**: `.claude/observability/security/findings-{date}.jsonl`
High-severity findings → block wrapup/verify

---

### 7.10 targeted-test-selection

**Role**: Owns the select-then-run recipe for a verify step that would otherwise run the
whole suite — **and, since 0.52.0, the run-it-well half for any language**.

§0 asks `hm test_runners plan --root .`, which names the project's runner, a worker count
already capped for the machine (about half the visible cores, floored at 1, never above
`cores - 1`), and which of the three levers that runner actually has: parallel, change-based
selection, re-run-only-failures. The distinction that makes this a table rather than a
sentence is `parallel_is_default`: `cargo`, `go`, `vitest`, `jest` and `flutter` are already
parallel, where a worker flag caps (`cargo --test-threads` *lowers* concurrency) or nests a
pool inside a pool, and `pytest` is the one common runner that is serial by default. A runner
the table does not know is answered with "use the project's own command" — **not an error**,
because for a table of ten runners that is the normal case and failing there would make the
stage skip the step that runs tests.

§1–§3 are the **Python** dep-map, and are skipped when the runner has none. They compute the
changed set as the NUL-delimited union of `git diff -z --name-only HEAD` and `git ls-files -z
--others --exclude-standard`, feed it to `hm test_dep_map` **inside the stage's own worktree**,
then run either the returned `node_ids` (`mode: targeted`) or the full suite (`mode: full`,
echoing `reason`). An empty changed set still invokes the selector with zero `--changed-file`
arguments — skipping the call would run no tests and report success. Before this, the skill
said only "for Rust or Node there is no dep-map, run the normal suite", which left every
non-Python harness with neither selection nor parallelism.

Lint and type checks stay unconditional: repo-wide, cheap, no selection concept.

**Called from**:
- The `/hm:review` auto-fix loop's **verify build** step (replacing an unconditional
  `uv run pytest -x` on every fix round). Deliberately named, not numbered — the round
  loop's step numbers move (`PLAN-review-round-inflation` inserted a grouping step and
  shifted verify from 3 to 5), and pinning the number is the
  `[fail:test] test-pins-retired-implementation-name` family.

The recipe lives in a skill rather than inline because
`test_aggregate_shipped_surface_does_not_grow` is a strict non-increase over the summed
command + codex-skill surface with zero headroom; skills outside the `hm-*` glob are not
counted, and the short reference that replaces the long command makes the aggregate
strictly decrease.

---

### 7.11 verify-before-completion

**Role**: A mandatory gate that executes 6 checkpoints before wrapup or at the end of each loop iteration.

See [Section 3.6](#36-hmverify--completion-verification) for 6-checkpoint details.

**Called from**:
- Step 2 of `/hm:wrapup`
- At the end of each iteration in `/hm:loop`
- Manually: `/hm:verify`

---

### 7.12 worktree-isolator

**Role**: Creates and manages worktrees for stages that require isolation, such as `/hm:execute`.

**4-step flow**:

1. **Check `harness.yaml.worktree.enabled`**: one boolean — isolate every /hm: stage, or none
2. **Call `worktree.create()`**: Create a new worktree at `.worktrees/<stage>-<UTC-ts>/`
3. **Execute workflow**: All agent Write/Edit operations happen only inside the worktree
4. **Exit handling**:
   - Success → `worktree.merge()` + `worktree.cleanup(on_success=True)`
   - Failure → `worktree.cleanup(on_success=False)` (preserve worktree for manual triage)

**Idempotent**: If already inside a worktree, returns existing path (no nested worktrees).

**Configuration**:
```yaml
worktree:
  enabled: true           # true = isolate every /hm: stage, false = isolate none
```

---

## 7a. Agent Models (per-agent model routing, 0.15.0+)

`harness.yaml` ships two model-related fields:

- `default_model: str` — floor fallback (default `opus`). Used
  when an agent has no preset entry and no explicit override.
- `agent_models: dict[str, AgentModelSpec]` — per-agent override map. Each
  spec carries optional `claude`, `cursor`, and `codex: {model,
  reasoning_effort}` fields.

### Resolution chain (3 tiers)

For every agent name the renderer asks `presets.resolve_agent_spec(name, config)`:

1. **Tier 1** — `config.agent_models.get(name)` (your explicit override)
2. **Tier 2** — `PRESET_AGENT_MODELS[config.preset].get(name)` (preset default
   for shipped agents — Production puts opus on `autoloop-coder`,
   `plan-validator`, `stuck`; sonnet on the 11 reviewer/structured agents)
3. **Tier 3** — `_spec_from_default_model(config.default_model)` (catch-all
   for user-authored custom agents — never KeyErrors)

### Per-IDE rendering

- **Claude** — `model: {{ claude_model }}` in agent `.md` frontmatter.
  Note: Anthropic [#43869](https://github.com/anthropics/claude-code/issues/43869)
  silently ignores subagent model frontmatter today; we render it anyway
  for forward-compatibility and surface the gap via `/hm:health` Layer-1
  `model_routing` advisory.
- **Cursor** — concrete IDs are emitted (works on 2.4+); aliases in
  `agent_models[*].cursor` are normalized via the `CURSOR_MODEL_IDS`
  canonical table at render boundary. Editing a single dict in `presets.py`
  upgrades every rendered file across a Claude version bump.
- **Codex** — `model_reasoning_effort = "..."` per agent (the dominant
  cost lever on reasoning models; `model =` stays omitted per
  ChatGPT-tier constraints). `.codex/config.toml` also gets
  `[profiles.cheap]` (`minimal`) and `[profiles.deep]` (`high`) blocks
  for invocation-time switching via `codex -p cheap` / `codex -p deep`.

### Worked example

A Production project that wants `autoloop-coder` on Haiku for cost-pinning,
keeps everything else on preset defaults:

```yaml
preset: Production
default_model: opus
agent_models:
  autoloop-coder:
    claude: haiku
    cursor: haiku          # alias; renderer normalizes to "claude-4-5-haiku"
    codex:
      reasoning_effort: minimal
```

Renders as:

- `.claude/agents/autoloop-coder.md` → `model: haiku`
  (Cursor 2.4+ reads this same file natively — single source, no separate
  `.cursor/agents/`.) For the Cursor-consumed value, the renderer normalizes
  the alias to a concrete ID via `CURSOR_MODEL_IDS` so the same template
  context emits `claude-4-5-haiku` in the cursor-side context variable.
- `.codex/agents/autoloop-coder.toml` → `model_reasoning_effort = "minimal"`

All other agents (`code-reviewer`, `plan-validator`, …) inherit
`PRESET_AGENT_MODELS[Preset.PRODUCTION]` defaults silently.

### Migration from `recommended_model:`

Existing v1 harness.yaml files with `recommended_model: ...` migrate
silently at re-render time. One INFO log per migration. The deprecated
key remains valid as a Pydantic `AliasChoices` input alongside
`default_model` until the 0.17.0 hard removal (ADR-012).

---

## 8. Agent Reference

Agents are sub-agents with independent contexts. When the main Claude context invokes them with the Task tool, a separate LLM call occurs and returns results.

### 8.1 autoloop-coder

**Role**: A limited-scope agent responsible for implementing each iteration within `/hm:loop`.

**Permissions (allowed)**:
- `Read(*)`, `Grep(*)`, `Glob(*)` — full read access
- `Write(.worktrees/**)`, `Edit(.worktrees/**)` — write only inside worktrees

**Scope (instruction only — NOT enforced)**: The agent is *told* to stay out of
`/etc/**`, `~/.ssh/**`, `~/.aws/**` and to avoid `curl | sh`, `eval`, and
destructive `rm`. Subagent frontmatter has no `permissions:` field, so Claude
Code ignores any such block silently — the real boundary is the agent's `tools:`
list (Write/Edit/Bash are granted without path restriction). See §11.16.

**Model**: Default model (opus recommended in autoloop context)

**Behavior**: Modifies files only inside worktrees. No open-ended exploration; limited-scope implementation only.

---

### 8.2 code-reviewer

**Role**: General-purpose code reviewer always included in every `/hm:review`.

**Permissions**: Read, Grep, Glob + `Bash(git diff:*)`, `Bash(git log:*)`, `Bash(git status:*)`
**Denied**: Write(*), Edit(*), all execution Bash (rm, curl, npm, eval, python, node, sh, bash)

**Review areas**: Correctness, readability, maintainability, basic security/performance hygiene

**Model**: sonnet

**Characteristic**: Included in every review (even when conditional-router selects additional specialist reviewers, code-reviewer is always present)

---

### 8.3 concurrency-reviewer

**Role**: Specialist reviewer for thread safety, deadlocks, ISR safety, and async correctness.

**Trigger** (selected by conditional-router): Files containing `thread`, `isr`, `worker`, `async`

**Review areas**:
- Shared mutable state access
- Lock acquisition order (deadlock potential)
- Safety in ISR context
- Correct use of async/await

**Permissions**: Same as code-reviewer (read-only)
**Model**: sonnet

---

### 8.4 consensus-arbiter

**Role**: Integrates findings from multiple reviewers and assigns consensus tags.

**Consensus algorithm**:

1. **Surface Match**: Same file + line±5 + same severity tier
2. **Reasoning Alignment**: Step-by-step alignment of OBSERVE→INFER→CONCLUDE chains
3. **Scope-limited findings**: Specific to one reviewer's domain → automatic consensus-passed without cross-check

**Output tags**:
- `consensus-passed`: 2 or more reviewers found the same thing, reasoning aligned
- `weak-consensus`: Same location but different reasoning, or only 1 reviewer found it
- `manual-only`: Cannot be automatically judged; requires human review

**Permissions**: Read, Grep, Glob (read-only)
**Model**: sonnet

---

### 8.5 executor

**Role**: Agent that actually fixes P0/P1 findings in the automatic fix loop of `/hm:review`.

**Permissions (allowed)**:
- `Read(*)`, `Grep(*)`, `Glob(*)` — full read access
- `Write(.worktrees/**)`, `Edit(.worktrees/**)` — write only inside worktrees
- `Bash(uv run:*)`, `Bash(pytest:*)`, `Bash(npm test:*)`, `Bash(cargo test:*)` — test execution
- `Bash(git diff:*)`, `Bash(git log:*)`, `Bash(git status:*)` — git read

**Told to avoid** (instruction, not enforced — see §11.16): system-path writes,
`curl | sh`, `eval`, destructive `rm`. The binding limit is the agent's `tools:` list.
**Model**: sonnet

---

### 8.6 performance-reviewer

**Role**: Specialist reviewer for hot-path regressions, allocation hotspots, and algorithm inefficiencies.

**Trigger** (conditional-router): Files containing `/perf/`, `benchmark`, `hot`

**Review areas**:
- Inefficient algorithms such as O(n²)
- Unnecessary allocations on hot paths
- Cache miss patterns
- I/O blocking

**Permissions**: Read-only (same as code-reviewer)
**Model**: sonnet

---

### 8.7 plan-validator

**Role**: Independently critiques the quality of a PLAN draft in Step 4 of `/hm:plan`.

**When invoked**: **Before** writing the PLAN file to disk — validates the draft while it's still temporary

**Judgment outcomes**:
- `APPROVED`: Save as-is
- `NEEDS_REVISION`: Includes list of warnings. Save after one interview round per warning
- `MAJOR_REVISION`: Serious issues. Re-validate after additional interview. If second attempt is also MAJOR, escalate

**Review items**: Verifiability of exit criteria, ADR count match, 4-field completeness per stage, Non-Goals presence, risk specificity

**Permissions**: Read, Grep, Glob (read-only)
**Model**: opus

---

### 8.8 security-auditor

**Role**: Deep 7-gate security audit. More thorough analysis than `security-reviewer`.

**Difference**: security-reviewer spot-checks only the changed portions of diff. security-auditor conducts a **complete 7-gate audit of the entire codebase**.

**7 gates (same as security-scanner skill)**:
1. Secrets (secrets in source/config)
2. Permission escalation (settings.json permissions)
3. Hook injection (dangerous patterns in hooks.json)
4. CVEs (OSV.dev dependencies)
5. Prompt injection (strings flowing to LLM)

**Gate 3 special case**: Also checks stdout → LLM injection class:
- If hook stdout is visible to LLM (PostToolUse, PreToolUse advisory)
- If content from user-writable files (`wiki.md`, `harness.yaml`) goes to stdout
- This is a stored prompt injection vector → triggers finding

**4-step reasoning**: OBSERVE→TRACE→INFER→CONCLUDE required for all P0/P1 findings

**Output**: JSON (overall_assessment, gates[], findings[])
**Permissions**: Read, Grep, Glob, Bash (read-only + Bash for scanning)
**Model**: sonnet

---

### 8.9 security-reviewer

**Role**: Conditional reviewer specialized in security-related diffs within `/hm:review`.

**Trigger** (conditional-router): Files containing `.env`, `/auth/`, `/secret`

**Review areas**:
- Plaintext secrets, hardcoded tokens
- Authentication flow vulnerabilities (TOCTOU, broken redirects)
- SQL injection, command injection, XSS, SSRF, path traversal
- CVEs in new dependencies
- Overly permissive `settings.json`
- Dangerous patterns in `hooks.json`

**Difference from security-auditor**: reviewer covers only diff scope; auditor covers entire codebase.

**Permissions**: Read-only
**Model**: sonnet

---

### 8.10 stuck

**Role**: Last-resort escalation analysis agent invoked when the workflow is blocked.

**Trigger conditions**:
- `/hm:execute` Phase A.5: test-reviewer FAIL retry budget exhausted
- `/hm:execute` Phase D: failure that cannot be resolved without PLAN scope change
- `/hm:execute` ADR conflict: implementation can only proceed by violating an ADR
- `/hm:review` consensus deadlock: 3 reviewers have conflicting CONCLUDE on the same issue
- `/hm:plan` plan-validator: 2nd MAJOR_REVISION

**Analysis process**:

1. Read full context (PLAN, SPEC, REVIEW, latest 3 reviewer outputs, failure logs)
2. Identify **single binding constraint** (not symptoms, but the root architectural/contract/time constraint)
3. Propose 2–3 concrete resolution paths (each with trade-offs + related ADR/Interview number)
4. Recommend the path most consistent with current decision context
5. Save escalation note to `.claude/memory/escalations/escalation-{slug}-{date}.md`

**Characteristic**: Does not fix problems directly — read-only advisor.
**Model**: opus (complex reasoning required)

---

### 8.11 test-reviewer

**Role**: Phase A.5 gate in `/hm:execute`. Validates the quality of test files written in Phase A.
Dispatched **three times concurrently**, once per lens (`red-correctness`, `discrimination`,
`coverage`); each call is accountable for its own lens but must still report a defect it notices
outside that lens — **in a carrier the schema below actually has**, never dropped and never
routed to a field that does not exist.

**3 review criteria**:

1. **SPEC alignment**: Is every In-Scope Scenario covered by a test?
2. **8 banned patterns**: FAIL if any of the following apply
   - Tautology (`assert True`, `assert len(x) >= 0`)
   - Stub-only (`pass`, `raise NotImplementedError`)
   - Framework-check-only (only verifies import success)
   - Over-mocking (mock the subject under test itself)
   - Scenario-ID mismatch
   - Magic value assertion (constants not in SPEC)
   - Failure suppression (`try...except: pass`)
   - Private/internal state assertion
3. **RED-correctness**: Does it actually fail before Phase C implementation?

**Output JSON**:
```json
{
  "overall_assessment": "PASS | FAIL",
  "per_scenario": [...],
  "scenarios_missing": [...],
  "blocking_issues": [...],
  "passing_tests": [...]
}
```

`passing_tests[]` is frozen — cannot be rewritten on retry.

**Permissions**: Read, Grep, Glob (read-only)
**Model**: sonnet

---

### 8.12 ux-reviewer

**Role**: Specialist reviewer for accessibility, consistency, and interaction quality of UI changes.

**Trigger** (conditional-router): Files containing `.tsx`, `.jsx`, `/ui/`

**Review areas**:
- Accessibility: keyboard navigation, ARIA, focus management, color contrast
- Consistency: use of design system components
- Missing states: loading/empty/error state handling
- Platform convention violations
- Text clarity and i18n readiness

**WCAG reference**: Include WCAG criterion code when reporting accessibility findings (e.g., `"WCAG 2.1 SC 2.4.7"`)

**Permissions**: Read-only
**Model**: sonnet

---

## 9. Hook Details

Hooks are Python modules that run automatically when specific events occur. For Claude Code they are defined in the `hooks` key of **`.claude/settings.json`** — the only place Claude Code reads project hooks from — and managed by harness-maker, which deep-merges so your own hooks survive a re-render. Cursor and Codex read their own files (`.cursor/hooks.json`, `.codex/hooks.json`) with their own schemas.

> `.claude/hooks/hooks.json` is **not** that location and is no longer rendered. It is a *plugin-bundle* path; anything placed there by an older version was inert in Claude Code. See `docs/ARCHITECTURE.md` for the experiment that refuted the older claim.

### Hook Definition Structure (the `hooks` key in settings.json)

```json
{
  "hooks": [
    {
      "type": "PostToolUse",
      "matcher": "Write|Edit|MultiEdit",
      "command": "python -m harness_maker.hooks.post_write_reminder"
    }
  ]
}
```

### 9.1 SessionStart

**Event**: Runs once when a Claude Code session starts

**Handler**: `harness_maker.hooks.sessionstart_drift`

**Behavior**:
1. Compare current harness state against `harness.yaml` baseline
2. Detect unexpected file changes since the last session (drift)
3. Include warning in session start message if drift is detected

**Purpose**: Immediately notice "oh, someone touched a config file" at session start

---

### 9.2 PreToolUse

**Event**: Runs **immediately before** a tool call. Can block tool execution.

**Two handlers**:

**1. permission_gate** (matcher: `Bash`)

```python
harness_maker.gates.permission_gate
```

- Compare Bash command against `permissions.allow/deny` in `harness.yaml`
- Block Bash commands that match the deny list
- Example: `Bash(eval *)`, `Bash(rm -rf /:*)` → BLOCK

**2. worktree_gate** (matcher: `Write|Edit|MultiEdit`)

```python
harness_maker.gates.worktree_gate
```

- **Protects peers, does not confine you.** Blocks a write **iff** the target is inside
  **another live session's** worktree. The base repo, `/tmp`, and everything outside the repo
  are allowed — writing outside your own worktree is *not* blocked.
- Reads per-session markers (`.claude/.hm-loop-*`, `.claude/.hm-task-<worktree>`) and sorts
  them three ways: **mine** (ignored), **peer** (non-empty, different `session_id` → block),
  and **unattributable** (empty header → ignored entirely; every standalone `/hm:execute`
  worktree writes one of these, and treating them as peers would block those sessions from
  their own work). If a path is in both your set and a peer's, **own membership wins**.
- **Fails open**: a PreToolUse payload with no `session_id` is allowed *before* any marker is
  read. Enforcement here was prompt-level only before this gate existed, so fail-open is a
  floor being added, not a wall being removed.
- Resolves the **base repo root first** — a `/hm:` stage's `cwd` is the worktree, and rooting
  there finds no `.claude/` markers at all, which would silently enforce nothing.
- **Accepted trade-off**: a drifting agent is no longer confined to its own worktree.
  Self-confinement is recoverable later as an opt-in.

---

### 9.3 PostToolUse

**Event**: Runs **after** a tool call completes.

**Two handlers**:

**1. telemetry** (matcher: `*` — all tools)

```python
harness_maker.telemetry
```

- Records all tool calls to `.claude/observability/metrics.jsonl`
- Records: tool name, input summary, result code, timestamp
- **100% local** — no external transmission
- Raw data for health score calculation

**2. post_write_reminder** (matcher: `Write|Edit|MultiEdit`)

```python
harness_maker.hooks.post_write_reminder
```

- Runs immediately after writing a file
- Reminds whether modified file meets certain conditions
- Example: After modifying `settings.json`, notify "verify permission policy compliance"

---

### 9.4 PreCompact

**Event**: Runs **immediately before** context compression. An opportunity to save important information before context loss.

**Two handlers** (one each for auto and manual):

```python
harness_maker.hooks.flush_session
```

**Behavior**:
1. Record important state from current session to `.claude/memory/session/<date>.md`
2. Save in-progress work, current stage, blockers as checkpoint
3. Enables resuming from next session even after context compression

If a `checkpoint:compaction` entry exists: previous session was interrupted → check `.claude-progress.json` and resume from the last in-progress stage.

**Two cases**:
- `matcher: auto` — when Claude automatically compresses context
- `matcher: manual` — when user manually runs `/compact`

---

### 9.5 Stop

**Event**: When a Claude session ends.

**Current state**: `[]` (empty array) — no handlers currently.

Future extension point: final cleanup tasks on session end, long-running worktree cleanup, etc.

---

### Hook Security Considerations

hooks.json is a target of security-auditor's **gate 3** inspection:
- Dangerous command patterns such as `rm -rf /`
- Remote execution via `curl ... | sh`
- Injection via `eval "$..."`
- User-writable file → stdout → LLM injection path

Always recommended to review with the security-scanner skill (or `/hm:verify` Check 4) when modifying hook code.

---

## 10. Appendix

### A. Key harness.yaml Settings

```yaml
# Language settings (language for interview and document output)
locale: ko               # en | ko | ja | others → en fallback

# Target IDEs (multi-select)
targets:
  - claude-code
  - cursor

# Preset (context size/permission strictness)
preset: Side             # Side | Production

# Development mode (spec-driven vs task-driven)
dev_mode: spec-driven    # spec-driven | task-driven

# Worktree isolation
worktree:
  enabled: false         # Side preset default. Production preset: true
                         # the only key on this axis: isolate every stage, or none

# Review settings
max_review_rounds: 3     # Maximum iterations of the auto-fix loop
grade_threshold: A       # Proceed to wrapup if this grade or higher (default A)

# Loop safety rails
loop:
  max_iter: 30
  max_time: 8h
  failed_streak: 3

# Reference document folders
ref_folders:
  - ./docs/reference
  - ~/knowledge-base

# Obsidian Second Brain folders
second_brain:
  enabled: true
  backend: filesystem
  vault_path: ~/vault
  project_id: my-app
  folders:
    - path: Projects/my-app
      read: true
      write: true
      note_types: [decision, preference, failure, project, reference, journal]
```

---

### B. Memory Structure

```
.claude/memory/
├── wiki.md           ← Reusable patterns, conventions, lessons
├── failures.md       ← Failure cases and solutions ([fail:] tags)
├── session/
│   └── <date>.md     ← Compaction checkpoints (checkpoint:compaction entries)
├── archive/
│   └── failures-<YYYY>.md  ← evicted stale count:1 entries (0.47.0+; archived, never deleted)
└── escalations/
    └── escalation-{slug}-{date}.md  ← stuck agent escalation notes
```

- **wiki.md**: Patterns to reference in future similar tasks. Auto-appended by wrapup.
- **failures.md**: Search with `rg -F "[fail:" .claude/memory/failures.md`. Used for warmup during execute. Since 0.47.0 `upsert-failure` evicts entries that are `count:1` **and** older than 90 days into `archive/failures-<YYYY>.md` at write time; `count>=2` is exempt at any age, because recurrence — not age — is what makes an entry worth keeping.
- **session/\<date\>.md**: Auto-saved by PreCompact hook. Resume interrupted sessions via `checkpoint:compaction` entries.

---

### C. Observability Structure

```
.claude/observability/
├── metrics.jsonl                    ← Tool call telemetry (collected by PostToolUse)
├── security/
│   └── findings-{date}.jsonl       ← security-scanner findings
└── refresh/
    ├── raw-{date}.jsonl             ← research-crawler raw data
    └── pending.jsonl                ← Unprocessed refresh proposals
```

---

### D. Worktree Lifecycle

```
Created: .worktrees/execute-20260509T0402Z/
  └─ New branch starting from HEAD
  └─ Name format: <stage>-<UTC-timestamp>
  └─ Before create, stale harness-owned markers/worktrees are pruned

Isolated execution:
  └─ All Write/Edit operations happen only inside worktree
  └─ Main branch working tree remains unchanged

On success (stage-only):
  └─ git: stage-merge branch to main
  └─ git worktree remove (delete worktree directory)
  └─ Commit handled by /hm:wrapup

On failure (fail):
  └─ Worktree preserved (.worktrees/execute-<ts>/ remains)
  └─ Manual triage possible
  └─ `worktree create` runs prune_stale, which deletes orphaned worktrees
```

---

### E. Permission Matrix Summary

| Agent Type | Read | Write | Edit | Bash |
|-----------|------|-------|------|------|
| Reviewers (code, security, perf, ux, concurrency) | ✅ all | ❌ | ❌ | git diff/log/status only |
| executor | ✅ all | ✅ .worktrees/** only | ✅ .worktrees/** only | uv/pytest/test execution |
| autoloop-coder | ✅ all | ✅ .worktrees/** only | ✅ .worktrees/** only | (similar to executor) |
| consensus-arbiter | ✅ all | ❌ | ❌ | ❌ |
| plan-validator | ✅ all | ❌ | ❌ | ❌ |
| test-reviewer | ✅ all | ❌ | ❌ | ❌ |
| stuck | ✅ all | escalation note only | ❌ | ❌ |
| security-auditor | ✅ all | ❌ | ❌ | Bash for scanning |

---

### F. Frequently Asked Questions

**Q: Don't multiple commits get created?**

A: No. The `execute` and `review` stages do not commit. `wrapup` creates exactly one commit. The same applies under `/hm:loop`, which defers wrapup to loop close.

**Q: What if worktrees accumulate too many?**

A: `worktree create` opportunistically removes orphan markers and dangling harness-owned worktree directories before queue guards run. Stale finalize-stash refs are preserved unless their tracked and untracked content is already in `HEAD`, and preserved stale refs do not count as live queue pressure. When an autoloop blocker occurs, `worktree.cleanup_all(force=True)` immediately cleans up registered harness-owned worktrees.

**Q: When should I use `--no-tdd`?**

A: (1) Pure refactoring — existing tests already cover it, (2) Only documentation/configuration changes, (3) Emergency fix — when SPEC+tests are already accurate. Otherwise, TDD by default.

**Q: What happens if the review grade falls below B?**

A: Enters the automatic fix loop (executor agent fixes P0/P1 findings). If target grade is not achieved within `max_review_rounds`, report to user and halt wrapup.

**Q: When is the stuck agent invoked?**

A: It is not invoked automatically on its own. Each stage invokes the stuck agent via `Task()` when it detects a blocking condition. Can also be used manually with something like "we're stuck at X, what's the minimum-regret unblock?"

**Q: How do I know which runtime target is active?**

A: `harness.yaml.targets` is the source of truth. Claude Code uses `.claude/`; Cursor adds `.cursor/` assets while reusing most `.claude/` files; Codex adds `AGENTS.md`, `.codex/`, and `.agents/skills/`. The workflow and reviewer model stays shared across targets.

---

## 11. What Makes harness-maker Different

> This section covers not "how it works" but **"why it was designed this way"**.
> Each differentiator explains what problem occurs without it (Before) and what happens with it (After).

### 11.1 3-Tier Memory Hierarchy — Knowledge Persists Across Sessions

**The limitation of a typical Claude session**: Every session starts on a blank page. Bug patterns solved yesterday, design decisions finalized last week, traps repeatedly fallen into — all must be explained again.

harness-maker solves this with a 3-tier memory:

```
Hot tier  → .claude/memory/session/<today>.md   (compaction checkpoint — execute resume)
Warm tier → .claude/memory/wiki.md              (reusable patterns and conventions)
          → .claude/memory/failures.md          (failure cases + solutions)
Cold tier → git log, work-docs/PLAN-*.md       (decision history)
```

**wrapup updates memory after every unit of work**:

- `wiki.md`: Classified with category tags like `[wiki:pattern]`, `[wiki:convention]`. Instantly searchable with `rg -F "[wiki:" wiki.md`.
- `failures.md`: Tags like `[fail:import]`, `[fail:hook]`. **Same slug increments count instead of creating duplicate section**. Track repeated patterns with `rg -F "[fail:" failures.md`.

When the next session's execute loads the Warm tier, it uses `rg -F "[fail:" failures.md` to target-search only failure patterns relevant to the current work area. No need to read the entire file.

---

### 11.2 Failure Count → Auto-Improvement Proposal Loop

**Typical workflow**: The same mistake is made 3 times and fixed manually 3 times. Nobody systematically asks "why do we keep getting this wrong?"

harness-maker has wrapup track the `count` of failure entries, and **automatically generates improvement proposals when count ≥ 3**:

```markdown
# .claude/memory/pending-proposals.md
## Proposal: {title} (2026-05-09)
**Triggered by:** [fail:hook] ws2-ntfs-edit (count: 3)
**Proposed mechanism:** New skill | Rule update | Agent addition | Hook modification
**Rationale:** 3 reasons this failure could have been prevented by an automated guard
```

When the user reviews and adopts a proposal, a new skill/agent/hook is added to the harness. **A feedback loop where harness-maker proposes its own upgrades**.

---

### 11.3 PreCompact Hook + checkpoint:compaction — No Work Lost on Context Compression

**Typical workflow**: When Claude's context fills up, automatic compaction occurs. In-progress work state is lost, and there's no way to know where to restart.

harness-maker's `PreCompact` hook fires **immediately before** compression:

```
PreCompact → flush_session → record state to .claude/memory/session/<today>.md
```

Saved content:
- Currently in-progress stage (e.g., execute Phase C)
- In-progress stage state in `.claude-progress.json`
- `checkpoint:compaction` marker

When the next session reads the Hot tier, it finds the `checkpoint:compaction` entry, refers to `.claude-progress.json`, and **resumes exactly from the last in-progress stage**. No need to manually ask "where were we?"

---

### 11.4 Prompt Cache Diagnostics (Layer 3) — Classify Cache Miss by Root Cause

**Background**: Anthropic prompt cache has a 5-minute TTL. Good cache hits reduce token costs and speed up responses. But there's typically no way to know why cache misses occur.

`ai-readiness-rubric`'s Layer 3 analyzes `metrics.jsonl` (all tool call logs) to **classify cache miss causes into 4 categories**:

| Category | Meaning | Response |
|----------|---------|----------|
| `min_threshold` | Prefix is below Anthropic cache-write minimum size | Increase context or use different cache strategy |
| `invalidation` | Prefix changed, invalidating cache | Improve context stability |
| `ttl` | More than 5 minutes elapsed since last use | Keep loop wait time within 270s |
| `first` | First use (expected miss) | Normal, no action needed |

This classification result constitutes 5% of the AI Readiness composite score (`cache` layer). **Many `ttl` misses indicate a loop timing problem; many `invalidation` misses indicate a context structure problem**.

---

### 11.5 Context Linter — Prompt Size Control Is Cache Efficiency

**Typical workflow**: Agent prompts, CLAUDE.md, and skill files gradually grow longer. The longer they get, the more model attention is dispersed, and the worse the prompt cache hit rate becomes.

`context-linter` enforces **per-preset line count limits** on all generated assets:

```
Side preset:    CLAUDE.md ≤200 lines, agent ≤300 lines, skill ≤300 lines
Production:     CLAUDE.md ≤500 lines, agent ≤300 lines, skill ≤300 lines
```

When limit exceeded: suggest "lines to trim + use external document links instead of inline".

**Why this connects to cache**: Smaller prefixes are easier to put in cache, and fewer changes means fewer `invalidation` misses. Context size control = prerequisite for cache hit rate optimization.

---

### 11.6 Conditional Router — Only Invoke the Reviewers You Need

**Typical workflow**: Invoking all specialist reviewers simultaneously when reviewing code increases token cost and latency.

The `conditional-router` skill analyzes changed file paths to **select only relevant reviewers**:

```
Analyze diff paths → security code?  add security-reviewer
                  → UI files?        add ux-reviewer
                  → concurrency?     add concurrency-reviewer
                  → performance?     add performance-reviewer
                  + always include code-reviewer
```

Setting `routing: always-all` always invokes all reviewers, but the default is conditional routing. **Skip unnecessary specialist reviewers → reduce token cost + review latency**.

---

### 11.7 2-Pass Redaction (+47 pp Precision) — Block Metadata Anchoring

**The trap of typical review**: If a PR title says "performance optimization", the reviewer LLM may anchor to that frame and miss security issues. Author name, commit message, and PR description all become "anchors".

harness-maker's 2-pass redaction:

```
Pass 1: PR title/author/description → [REDACTED]
        Reviewer sees only pure code, generates findings without forbidden biases

Pass 2: Restore metadata
        Apply context to Pass 1 findings → remove findings where context is dubious
        Pass 2 overrides Pass 1 findings (CP10 contract)
```

Ablation experiments confirmed **+47 percentage-point precision improvement**. Deterministic processing via CLI-based redaction (`python -m harness_maker.two_pass_review redact`).

---

### 11.8 consensus-arbiter — Beyond "Same Location" to "Same Reasoning"

**The problem with typical multi-reviewer approaches**: Even when 3 reviewers point to the same line, they may diagnose it differently as "race condition" vs "null deref" vs "wrong timeout". Simple location matching treats this as consensus, but they actually have different opinions.

consensus-arbiter's 2-step filter:

**Step 1 — Surface Match (candidate selection)**:
Same file + line±5 + same severity tier → candidate

**Step 2 — Reasoning Alignment (verification)**:
Compare OBSERVE → INFER → CONCLUDE chains:
- CONCLUDE points to the same execution risk → `consensus-passed` (strong consensus)
- OBSERVE matches, CONCLUDE differs → `weak-consensus` (preserve both, manual review)
- OBSERVE matches, reasoning missing from one side → `manual-only` (cannot auto-fix)

**Only `consensus-passed` gets automatic fixes**. Weak-consensus and manual-only are displayed separately to the user. Prevents wrong fixes being applied based on false consensus.

---

### 11.9 ADR-Based Decision Persistence — The WHY of Design Choices Lives in the Codebase

**Typical workflow**: The person who can answer "why SQLite instead of Redis?" disappears from the team and the answer is forever lost. The next AI session proposes the already-rejected alternative again.

harness-maker's `/hm:plan` formalizes all architecture decisions as ADRs (Architecture Decision Records):

```markdown
### ADR-001: Use SQLite instead of Redis
**Status:** Accepted (2026-05-09, via /hm:plan interview)
**Context:** Single-instance deployment, requirement to minimize external service dependencies
**Decision:** SQLite
**Consequences:**
- ✅ Operates without external infrastructure
- ⚠️ Limited concurrent write performance
**Rejected alternatives:** Redis — operational burden of external service
**Source:** Interview #2
```

ADRs become **binding constraints** in `/hm:execute`. If an implementation situation arises that requires violating an ADR, it escalates without silently proceeding. Future AI sessions read ADRs and do not repeat the same decisions or reconsider already-rejected alternatives.

---

### 11.10 Generated File Fingerprint + Block-Merge Markers — Upgrades Don't Overwrite User Edits

**The problem with typical generation tools**: When a template is upgraded, user-edited content gets overwritten.

harness-maker's two protection mechanisms:

**1. content_hash fingerprint** (in all generated file frontmatter):
```yaml
content_hash: ca17023045fbd8f5ef8ad569d25098c062bd31ffaacb89bda428dd1b80eb87bd
```
On re-render: hash matches → "ours" → safe to auto-upgrade
Hash mismatch → "user has edits" → KEEP (do not overwrite)

**2. Block-Merge Markers** (user customization zones):
```
<!-- @hm:user:extensions -->
Content directly added by user (this block is preserved during upgrade)
<!-- @hm:/user:extensions -->
```
Even when a template upgrade updates outside this block, the contents inside remain intact.

---

### 11.11 Drift Gate + pending-drift.md — Scope Drift Is Forwarded to the Next Session

**Typical workflow**: While working, files outside the PLAN scope get changed, or files specified in the PLAN accidentally get missed. Only discovered after committing.

wrapup's Drift Gate performs an **advisory check before commit**:

```
staged files ∉ PLAN scope          → record in pending-drift.md
PLAN scope files ∉ staged          → incomplete-phase warning
SPEC scenarios ∉ diff test coverage → missing-coverage warning
```

Does not block the commit (advisory). Instead, records in `.claude/memory/pending-drift.md` and references in the next session's Hot tier. Rather than passing over unknowingly, **converts to trackable debt**.

---

### 11.12 Reference Document 2-Tier Search — Only Read What's Relevant from a Large Knowledge Base

**Typical workflow**: When there are many relevant documents, either load everything into context, or don't search at all.

The `refdocs-search` skill performs a 2-tier search on reference folders registered in `harness.yaml.ref_folders`:

```
Tier 1 (lossy index): ripgrep → keyword matching to list candidate files
Tier 2 (source verify): Read   → directly read candidate files to verify actual content
```

PDFs are processed page-by-page with Read multimodal. DOCX is not supported (conversion required).

**Token efficiency**: Instead of loading the entire knowledge base into context, Tier 1 filters out irrelevant files and Tier 2 loads only actual content. `relevance-filter` further scores and removes items below 0.7.

---

### 11.12.1 Obsidian Second Brain — Typed R/W Memory with Project Namespaces

**Typical workflow**: A project either forgets durable user knowledge between sessions or treats a vault as read-only reference search.

`second_brain` connects a generated harness to an Obsidian-compatible Markdown vault as a typed graph of decisions, preferences, failures, projects, references, and journals. Notes use YAML frontmatter plus tags and `[[links]]`, so stages can retrieve targeted memory instead of loading the whole vault.

First install keeps this setup read-first and points advanced write-capable configuration to `/hm:configure`, where the user can review the allowlist, namespace, and writable-folder trade-offs deliberately.

Writes are intentionally full Markdown writes inside trusted allowlisted folders. To keep several projects from colliding in the same vault, any writable folder requires `second_brain.project_id`, and the writable folder path must include that project id as a path segment, such as `Projects/my-app`. Managed notes also warn when frontmatter omits the project namespace.

**Promotion pipeline (how the vault actually fills)**: local `.claude/memory/` (wiki/failures/session) is the project working memory; the Second Brain is the *curated cross-project durable* layer. `/hm:wrapup` runs a required **Step 5.6** that evaluates the local entries it just wrote and promotes the cross-project-durable subset (`failures.md` → `failure`, PLAN ADRs → `decision`, confirmed preferences → `preference`) via `second_brain promote`. Promotion is idempotent — the deterministic `<type>-<slug>.md` filename plus an `hm_source` link-back means re-promoting the same source updates the note in place rather than duplicating. The step prints a `promotion evaluated: N candidates, M promoted` receipt so under-promotion is visible. Because promotion fires only at wrapup, finishing a work unit with `/hm:wrapup` (not a bare commit) is what keeps the vault current.

---

### 11.13 Anti-Rot System — The Harness Itself Doesn't Go Stale

**The irony of typical AI development tools**: The AI tool fails to leverage new Claude features, uses dependencies with security vulnerabilities, or doesn't know that best practices have changed.

harness-maker periodically **checks its own freshness**:

```
research-crawler → crawl 4 sources (Anthropic blog/GitHub releases/arxiv/OSV.dev CVE)
relevance-filter → LLM relevance scoring (adaptive threshold: 0.5~0.9)
pending.jsonl   → unprocessed proposal queue
```

How the adaptive threshold works:
- Past acceptance rate > 80% → threshold +0.05 (stricter, reduce noise)
- Past acceptance rate < 50% → threshold -0.05 (more lenient, miss less)
- Range: 0.5 ~ 0.9 (user behavior learns the threshold)

**verify-before-completion uses pending.jsonl as a gate**: Warns before wrapup if there are unprocessed proposals. Only `defer`-processed ones are OK.

---

### 11.14 7-Dimension AI Readiness + Extensible Rubric YAML

**Typical approach**: Code quality measured by a single metric like test coverage.

harness-maker's Layer 1 **quantifies AI-assistedness across 7 dimensions**:

| Dimension | What Is Measured |
|-----------|----------------|
| `context_quality` | CLAUDE.md structure, clarity, size |
| `guardrails` | Permission deny rules, security gates |
| `verification` | Test presence, CI configuration |
| `workflow_clarity` | Slash command completeness, stage ordering |
| `memory_continuity` | wiki.md/failures.md presence + content |
| `observability_setup` | metrics.jsonl, security findings |
| `governance` | ADR presence, CONTRIBUTING.md |

Layer 2 rubrics are extensible:

```yaml
# .claude/rubrics/my-custom-rubric.yaml
dimension: api-documentation
target: "src/**/*.py"
rubrics:
  - id: docstring-present
    description: Public functions have docstrings
    severity: P1
    action: Add one-line docstring explaining WHY, not WHAT
```

Add a YAML file to `.claude/rubrics/` and it's automatically applied in the next `/hm:health`. **Express project-specific quality standards as code** — no need for humans to check manually.

---

### 11.15 Deterministic Worktree Isolation

**The risk of typical approaches**: When a skill uses trigger-based dispatch, it may run probabilistically depending on IDE environment. If a trigger is silently skipped in Cursor IDE, direct edits happen on the main branch.

harness-maker **always performs worktree isolation deterministically via direct CLI invocation**:

```bash
# Not delegated to a skill — CLI invoked directly regardless of IDE environment
uv run python -m harness_maker.worktree create execute "$(pwd)"
```

Since each `!` block is an independent subshell, shell variables do not persist → always use absolute paths as literals. Same isolation guaranteed whether in Cursor or Claude Code.

---

### 11.16 What Actually Enforces an Agent Boundary

> **Corrected 2026-07-17 (0.40.0).** This section used to document a "Write+Edit
> pairing invariant" for agent `permissions:` frontmatter. That invariant was
> cosmetic: **subagent frontmatter has no `permissions:` field**, so Claude Code
> ignored every one of those blocks silently. The blocks have been deleted rather
> than annotated — they had already misled one reader with the docs open.

Only two things bind a subagent:

1. **`tools:`** — a tool the agent does not have, it cannot use. This is the real
   boundary, and it is why read-only reviewers are read-only: they have no Bash,
   so `python -c "..."` is not available to bypass anything. Adding `Bash` back
   grants an unrestricted shell no frontmatter can narrow.
2. **`settings.json` `permissions`** — enforced, but **session-wide**: it applies
   to the main session and every agent alike. It cannot express "this agent may
   not run `rm`".

Per-agent command scoping is not expressible in frontmatter. When you need it,
the options are a PreToolUse hook keyed on agent identity, or a sandbox. Both are
defeated by `--dangerously-skip-permissions` / `bypassPermissions`.

**Rule shapes that silently do nothing** (`permission_syntax.is_matchable_rule`
is the oracle, and `test_permission_syntax.py` fails the build on a regression):

| Shape | Why it never fires |
|---|---|
| `Write(<path>)`, `NotebookEdit(<path>)`, `Glob(<path>)` | the file-permission check consults `Edit`/`Read` only — write `Edit(<path>)` |
| `Bash(curl * \| sh)` | Bash rules match per-subcommand after splitting on `&&`, `\|\|`, `;`, `\|`, `&` — a rule spanning a separator can never match, and warns about nothing |

harness-maker shipped three of these for 39 releases. The prose above them
claimed they closed a bypass; they had never run.

---

### 11.17 Single-Commit Contract + WHY-Focused Commit Messages

**Typical workflow**: execute → commit, review-fix → commit, memory update → commit... git log fills up with intermediate implementation states.

harness-maker has **wrapup create exactly one commit**:

```
staged (execute implementation)
+ memory updates (wiki + failures)
+ PLAN status update
= one commit
```

Commit messages are **WHY-focused**:
```
feat(csv-parser): handle malformed headers without crashing

Error scenarios weren't specified in original SPEC (ADR-002 accepted this
gap). Chose fail-fast over silent recovery per Interview #3 — preserves
data integrity at cost of usability for edge cases.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
```

The diff conveys WHAT. The commit message conveys **intent and context** to future readers (the on-call engineer at 2am). `git log` becomes a decision history.

---

### 11.18 LLM-First Architecture — Avoid Rule-Based Systems

Specific cases where harness-maker **uses LLM judgment instead of regex/rules**:

| Task | Bad Approach | harness-maker Approach |
|------|------------|----------------------|
| Judging "is this answer concrete enough?" | vague keyword regex | LLM evaluates actionability |
| Generating interview follow-up questions | Fixed question script | LLM reads context and generates dynamically |
| Scoring relevance of refresh items | Keyword matching | LLM judges by comparing against project stack |
| Judging prompt injection candidates | Regex alone | regex first → LLM removes false positives |
| Evaluating loop stopping condition | Rule-based checklist | LLM judges whether stopping_criteria is met |
| Detecting missing interview dimensions | Fixed checklist | LLM reads description and extracts already-answered dimensions |

This design principle is documented in CLAUDE.md: "Maximize quality by leveraging LLM judgment rather than rule-based systems."

---

### 11.19 Atomic File Writes — Files Don't Corrupt on Interrupt

All file writes use the `tempfile + os.replace` pattern:

```python
fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
# ... write content ...
os.replace(tmp, path)  # atomic on POSIX + Windows
```

If the process terminates in the middle:
- Before success: only `.tmp` file exists (original unchanged)
- After success: atomic replace (no intermediate state)

There is a known issue where the Edit tool can corrupt files in WSL2/NTFS environments, so harness-maker forces the use of `Write` (full file rewrite) in those environments.

---

### 11.20 100% Local Telemetry

The `PostToolUse` hook **captures all tool calls** (matcher: `*`):

```jsonl
{"tool": "Edit", "file": "src/parser.py", "ts": "2026-05-09T04:02:12Z", "result": "ok"}
{"tool": "Bash", "cmd": "pytest -x", "ts": "2026-05-09T04:02:45Z", "result": "pass"}
```

This data is reused for multiple purposes:

| Consumer | How Used |
|---------|---------|
| `verify-before-completion` Check 3 | Health baseline vs current score comparison |
| `ai-readiness-rubric` Layer 3 | Cache miss cause classification |
| `/hm:health` dashboard | observability_setup dimension score |

**Not transmitted externally**. Works identically in CI environments, private repos, and air-gapped systems.

---

### 11.21 Deep Interview (spec/plan) — Lock Architecture Through Dialogue, Not Assumptions

**Before**: Most AI workflows receive only a task description and jump into implementation. Ambiguous requirements are discovered during implementation, and the cost of backtracking to fix them accumulates.

**After**: `/hm:spec` and `/hm:plan` conduct deep interviews before implementation. Questions are not from a fixed script — the LLM reads the context and generates them dynamically.

#### /hm:spec's 6-Category Interview

The SPEC interview covers **6 categories in order**:

| Category | What Is Confirmed |
|----------|-----------------|
| Intent | Why this feature is needed, what it solves |
| Outcomes | Completion criteria, measurable metrics |
| In-Scope Scenarios | Concrete scenarios in "Given X, When Y, Then Z" format |
| Non-Goals | What is explicitly not included |
| Constraints | Technical and business constraints |
| Verification | How to prove completion |

A **completeness scorer** rates the 6-category coverage and scenario specificity on a 0–1 scale. If score falls short, asks additional questions about only the lacking categories. A completed SPEC is marked `status: approved` so subsequent `/hm:plan` skips re-asking (Case A — no duplicate interview).

#### /hm:plan's 9-Category Priority Interview

The PLAN interview decides "how to build it". Question categories proceed in **reverse order of impact**:

1. Scope boundaries — what is included/excluded
2. Architecture — component ownership, pattern selection
3. Contract shape — API signatures, DB schema, file formats
4. Risk tolerance — safe/incremental vs fast/bold, rollback strategy
5. Testing depth — unit/integration/manual scope
6. Implementation phasing — feature flags, ordering, dependencies
7. Dependencies — add library vs implement directly
8. Failure handling — retry, circuit-break, fallback
9. Observability — log level, metric names, alert thresholds

#### What the Interview Shows You While It Asks — `interview.comprehension.depth`

Both interviews build more than they show. `/hm:plan` Step 1 drafts the goal, a
component/data-flow sketch, a phase skeleton, and the ambiguities ranked by blast radius —
under a heading that says *"NOT shown to user"* — and then asks its architecture questions
without any of that on screen. `harness.yaml`'s `interview.comprehension.depth` decides how
much of that existing material is disclosed:

| `depth` | What the interview emits |
|---|---|
| `minimal` | nothing — byte-identical to the pre-0.52 commands |
| `standard` (default) | a **brief** before the questions (for `/hm:spec`: inherited scope, AC skeleton, which of the 6 categories remain open) + a **round-state** delta whenever the design picture changes between rounds |
| `deep` | + per question, what it decides · what it rewrites downstream · the recommended default and why · reversibility cost; then a closing **read-back** of what was locked (output only — no response asked, no gate) |

Nothing new is generated: this re-routes output the stages already produce. Both stages
include one shared partial, so the enabled block set cannot drift between them.

**Existing projects are retrofitted.** A `harness.yaml` with no `comprehension` key acquires
`standard` on its next `/harness-maker:make --update`, and its `/hm:plan` and `/hm:spec` grow
accordingly. Opt out with `/hm:configure` → Interview comprehension → `minimal`
(or `harness-maker make . --comprehension-depth minimal`), which restores the previous
output exactly. An unrecognized value warns and is rewritten to `standard`.

#### ADR Auto-Promotion — If Any of 5 Criteria Are Met

When an interview answer meets any of the following, that decision is automatically promoted to an **Architecture Decision Record**:
- Component boundary/ownership change
- New contract (API, IPC, schema, file format, protocol)
- Reasonable alternative explicitly rejected
- Long-term impact beyond this task (setting precedent)
- Future flexibility restriction (framework, library, protocol lock-in)

ADRs record `Context / Decision / Consequences / Rejected Alternatives`. `/hm:execute` treats these as **binding constraints** — if an implementation requires violating an ADR, it escalates as a blocker rather than silently proceeding.

#### plan-validator Agent Gate

After the interview ends, before writing the PLAN to disk, the `plan-validator` agent independently reviews:
- `APPROVED` → Save immediately
- `NEEDS_REVISION` → Save after one additional interview round per warning
- `MAJOR_REVISION` → Additional interview → re-validate once. If second attempt also fails, escalate to user

#### "No Unresolved Decisions" Rule

Before saving the PLAN, scan for expressions like "Accept?", "OK?", "Verify?", "Should we?" If such expressions remain, they represent **a missed interview round** — the PLAN should have no checklists; all judgments should already be recorded in the interview transcript or ADRs.

---

### 11.22 /hm:loop Adaptive Interview + Convergence Loop — Iterations Converge Toward the Goal

**Before**: Open-ended requests like "improve this code" either end in one turn, or each turn loses context and drifts in unrelated directions.

**After**: `/hm:loop` executes a **time-and-iteration bounded** loop. Each iteration reads the results of the previous iteration, then convergence is accepted only after mechanical checks, LLM criterion checks, regression comparison, and a two-iteration streak all pass.

#### Two Modes

| Mode | Command | Purpose |
|------|---------|---------|
| **feature** | `/hm:loop --mode feature "description"` | Incrementally implement toward a goal or SPEC file |
| **improve** | `/hm:loop --mode improve "description"` | Iteratively improve existing code, stop when exit criteria converge |

#### autoloop-driver's 5-Dimension Adaptive Interview

Before starting the loop, the `autoloop-driver` skill has the **LLM read the description to extract already-answered dimensions** and asks questions about only the missing ones:

| Dimension | Content |
|-----------|---------|
| purpose | What this loop should achieve |
| invariants | Invariants that must not be broken during iterations |
| priority | Which aspect is most important |
| stopping_criteria | When to consider it "sufficiently complete" |
| out_of_scope | What to explicitly not touch |

For a detailed description like "Add error handling to CSV parser", `purpose` is treated as already answered and only the remaining dimensions are asked. **No fixed script** — only necessary questions are asked based on LLM judgment.

#### Single Shared Worktree + autoloop-coder Permission Restrictions

The entire loop shares **a single worktree**. Creating a new branch per iteration accumulates checkout overhead; a single shared worktree prevents this.

Code writing is performed by the `autoloop-coder` agent:
- **write-tool-only**: Executes only specified tasks without exploration (no open-ended exploration)
- Write access restricted to within worktree boundaries
- CLAUDE.md + TECH_SPEC.md take priority — make autonomous decisions when ambiguous and log them; **user-facing questions are prohibited**

#### 4-Gate Convergence

At the end of each iteration, `autoloop-driver` checks convergence through four gates:

1. **Mechanical**: run each exit criterion command; required failures block convergence.
2. **LLM individual**: evaluate each criterion label against the current worktree state.
3. **Regression**: compare current test failures against the previous baseline.
4. **Streak**: require two consecutive all-pass checks before accepting completion.

The LLM still handles the language-heavy judgment, but it no longer acts as a single unchecked stop signal.

#### Time/Iteration Boundary + Evidence Preservation

To prevent infinite loops:
- `max_iterations` (default: per harness.yaml settings)
- `max_duration_minutes` (safe shutdown on timeout)

Failed iterations preserve the worktree (`fail` finalize) so users can see where execution stopped.

---

### 11.23 TDD Phase A.5 Gate — Verify Tests Are Genuinely RED Before Implementation

**Before**: AI writes tests and implementation together, or even when tests are written, writes tautology tests that always pass. Nobody verifies that the test actually catches the absence of implementation.

**After**: `/hm:execute` writes tests before implementation (Phase A), then the `test-reviewer` agent independently reviews the test files (Phase A.5). Implementation begins in Phase C.

#### 8 Banned Patterns — FAIL If Any Apply

When the `test-reviewer` agent detects any of these patterns, it issues a `FAIL` judgment:

| Pattern | Example | Problem |
|---------|---------|---------|
| Tautology | `assert True`, `assert len(x) >= 0` | Always passes regardless of implementation |
| Stub-only | `pass`, `raise NotImplementedError` | No substantive verification |
| Framework-check-only | `import mymodule; assert True` | Only verifies import success |
| Over-mocking | Mock the subject under test itself | Doesn't actually test the real code |
| Scenario-ID mismatch | `test_s3_foo` is not Scenario 3 | Cannot trace back to SPEC |
| Magic value assertion | Compare against constants not in SPEC | Test and SPEC are decoupled |
| Failure suppression | `try...except: pass` | Test ignores errors |
| Private state assertion | `._internal_state == x` | Coupled to implementation details |

#### passing_tests[] is advisory + RED-correctness

`passing_tests[]` is merged as an intersection across the three lenses and is **advisory — it
decides nothing.** There is no freeze: its entries are bare function names with no `test_file`,
so they cannot identify a test, while `blocking_issues[]` entries can. The authoritative carrier
is `blocking_issues[]`, and a repair re-dispatches all three lenses precisely because a rewrite
changes a file the other two had already judged — no verdict, PASS included, carries between
rounds.

After modifying tests, Phase B (RED gate) verifies that they actually FAIL. If they accidentally PASS (false-RED), return to Phase A for rewriting — tests that pass even without implementation are meaningless.

Retry budget: **2 rounds** (each round = three concurrent lens dispatches; worst case 3 + 3 = 6
dispatches). If 2 consecutive FAILing rounds, escalate to the `stuck` agent.

---

### 11.24 `stuck` Escalation Agent — A Dedicated Analyst Intervenes on Repeated Blockers

**Before**: When a workflow gets stuck, the user reads error messages and finds the cause manually. Requires synthesizing information scattered across multiple systems (PLAN, SPEC, REVIEW, ADR).

**After**: The `stuck` agent reads all context to find the **single binding constraint** and proposes 2–3 concrete resolution paths. Each path includes trade-offs and related ADR numbers.

#### Trigger Conditions

| Situation | Details |
|-----------|---------|
| Phase A.5 retry budget exhausted | 2 consecutive FAILing multi-lens rounds |
| Phase D cannot be fixed | Failure that cannot be resolved without changing PLAN scope |
| ADR conflict | Implementation can only proceed by violating an ADR |
| Review deadlock | 3 reviewers have conflicting CONCLUDE on the same issue |
| plan-validator 2nd MAJOR | Serious issues in both validation attempts |

#### Analysis Method

The `stuck` agent reads the full PLAN + SPEC + REVIEW + latest 3 reviewer outputs + failure logs, then:

1. **Separate symptoms from root constraints** — not "tests are failing" but rather "ADR-002 prohibits this API format but SPEC S3 requires it" type of root constraint
2. **Propose 2–3 resolution paths** — each with trade-offs and related ADR/Interview numbers
3. **Recommend the preferred path** — the path most consistent with current decision context
4. **Save escalation note** — `.claude/memory/escalations/escalation-{slug}-{date}.md`

`stuck` is a **read-only advisor** — it does not directly modify code. The decision returns to the user.

---

### 11.25 6-Checkpoint Verify Gate — Dual Validation of "Done" via Diff and Health Metrics

**Before**: "Tests pass" is considered done. Whether what was written in the PLAN was actually implemented, whether there are security vulnerabilities, and whether other quality metrics have regressed are not checked.

**After**: `/hm:verify` (= `verify-before-completion` skill) executes 6 checkpoints in order and **immediately blocks on the first failure**.

#### 6 Checkpoints

| # | Check | Judgment Method | On Failure |
|---|-------|----------------|-----------|
| 1 | PLAN fulfillment | **LLM directly cross-references diff against PLAN items** | Display list of unfulfilled items |
| 2 | Regression/smoke | Run `.claude-verify.sh` | Output failing tests |
| 3 | Health score within -5 | `compute_readiness()` vs baseline | 6-dimension breakdown |
| 4 | Harness freshness | Compare `harness.yaml.harness_maker_version` against the installed plugin | Guide to re-render with `/harness-maker:make` |
| 5 | No high-severity security | Check `findings.jsonl` count | Display findings list |
| 6 | Worktree merge-safe | `git diff --check` + conflict marker check | Display conflicting paths |

#### Why Check 1 Is LLM Judgment

PLAN fulfillment cannot be determined by checking a checkbox alone. Whether the "implement CSVParser.parse()" item in the PLAN is actually present in `git diff`, and whether the implementation matches the PLAN's intent, requires **LLM to read both documents simultaneously and judge**. Automated subprocess judgment would miss cases where someone only checked the PLAN without writing the code.

#### Why Check 3 Differs from Simply Passing Tests

Even when tests pass, the AI Readiness composite score can drop by 5 or more points. For example, if new code lowers the documentation ratio, increases module coupling, or omits type hints, tests still pass but Check 3 catches it. This check measures not "does it work correctly right now?" but "has the overall quality of the codebase not regressed?"

---

### Differentiators Summary Table

| Differentiator | Problem Solved | Related Component |
|----------------|---------------|-------------------|
| 3-tier memory | Knowledge lost between sessions | wiki.md / failures.md / session/ |
| Failure → improvement loop | Repeating the same mistakes | wrapup count≥3 / pending-proposals |
| PreCompact + checkpoint | Work lost during context compression | flush_session hook / .claude-progress.json |
| Cache miss cause classification | Not knowing why it's expensive | Layer 3 cache_diagnostics (reads Claude Code session transcripts) |
| Context Linter | Prompt bloat → cache inefficiency | context-linter skill |
| Conditional Router | Unnecessary reviewers → token waste | conditional-router skill |
| 2-pass redaction | Metadata anchoring | two_pass_review CLI (+47pp) |
| Reasoning Alignment | False consensus → wrong fixes | consensus-arbiter agent |
| ADR system | WHY of design decisions lost | /hm:plan interview / PLAN-*.md |
| Fingerprint + Block-merge | Upgrade overwrites customizations | content_hash / @hm:user:* markers |
| Drift Gate | Scope drift goes undetected | wrapup Step 3 / pending-drift.md |
| 2-tier refdocs search | Full load of large knowledge base | refdocs-search + relevance-filter |
| Anti-rot system | Harness itself goes stale | research-crawler / pending.jsonl |
| 7-dimension AI Readiness | Single metric for AI readiness | ai-readiness-rubric / rubrics/*.yaml |
| Deterministic worktree isolation | Isolation probabilistically fails by IDE | worktree CLI direct invocation |
| `tools:`-based agent boundary | frontmatter permissions is silent-ignored (fake boundary) | agent `tools:` allowlist / main-session settings.json deny |
| Single commit + WHY message | git log polluted with intermediate states | wrapup Step 7 |
| LLM judgment first | regex/rules false positives/negatives | Entire system |
| Atomic file writes | File corruption on interrupt | atomic_write pattern |
| 100% local telemetry | Concerns about external transmission | PostToolUse hook / metrics.jsonl |
| Deep Interview (spec/plan) | Implementation from assumptions → later rework | 6-category/9-category + ADR promotion + plan-validator |
| loop adaptive interview + convergence | Open requests diverge or lose context | autoloop-driver / autoloop-coder / stopping_criteria |
| TDD Phase A.5 test quality gate | Tautology tests create false-GREEN and proceed to implementation | test-reviewer ×3 lenses / 8-banned-patterns / merged blocking_issues[] |
| stuck escalation agent | Cause identification and resolution path exploration is user's burden when blocked | stuck / escalation-{slug}-{date}.md |
| 6-checkpoint verify gate | Tests passing ≠ done (PLAN fulfillment, health metrics, security unchecked) | verify-before-completion / Check1 LLM cross-reference / Check3 health regression |

---

*This document is current as of harness-maker 0.9.3. Generated via: `/hm:execute how-it-works-docs`*
