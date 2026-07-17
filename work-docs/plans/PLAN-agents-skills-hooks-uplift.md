---
type: plan
task_slug: agents-skills-hooks-uplift
status: planning
created: 2026-05-08
tags: [harness-maker, plan, python, agents, skills, hooks, audit]
spec: null  # research/spec skipped — direct plan from user prompt + uniep reference
research_doc: null
interview_rounds: 1
adrs: 0
validator_outcome: SELF_REVIEWED
summary: "Audit + gap-fill agents/skills/hooks vs uniep reference (post-commands uplift)"
---

# PLAN: Agents / Skills / Hooks uplift to match commands-stage parity

## 🎯 Executive Summary

> **TL;DR:** Bring agents/skills/hooks up to the same uniep-parity bar that commands reached in 0.6.0. Gap-fill what's missing, audit what's there.

### What We're Doing

Systematically compare every agent template, skill template, and hook in `harness-maker/templates/` against uniep's running `.claude/` equivalents. Where uniep's version is materially stronger, port the improvements. Where uniep has assets we lack and they're not domain-specific to embedded systems, add them.

### Why It Matters

The 0.6.0 release rewrote 7 atomic stages but only added 2 agents (plan-validator, test-reviewer) as fallout. The remaining 9 agent templates, all 11 skill templates, and the hooks layer were not audited. Quality drift between command templates (now uniep-parity) and the agents/skills they invoke leaves gaps where deep stages are wired to thin agents.

### Key Decisions (from interview, 2026-05-08)

- **Audit scope**: gap-fill **AND** audit existing (no shortcuts).
- **Multi-agent research**: single-agent research stays — research-critic / research-generator / research-verifier split is uniep-idea-finder-domain, not generally useful.
- **New agent**: `stuck` (escalation when blocked) — yes. `tester` — no (executor already covers it).
- **New hook**: `post-write-reminder` — yes. `pre-commit-check` — no (overlaps wrapup).

### Estimated Impact

- **Complexity**: Medium-High
- **Risk Level**: Medium (template surface only, no runtime behavior break)
- **Files Changed**: ~25-35 (11 existing agents + 1 new agent + 11 skills + 1 new hook + sandbox baselines)
- **Estimated Effort**: 3-5 hours for full sweep

---

## 🎙️ Interview Transcript

| # | Topic | Category | Question | Choice | Note |
|---|---|---|---|---|---|
| 1 | Audit scope | Scope boundaries | Gap-fill only / audit only / both | **Both** | full sweep accepted |
| 2 | Multi-agent research | Architecture | single / +critic / 3-agent split | **single** | uniep 3-agent is idea-finder domain, not applicable |
| 3 | New stuck/tester | Architecture | stuck / both / neither | **stuck only** | tester duplicates executor |
| 4 | Hooks | Architecture | post-write / +pre-commit / nothing | **post-write only** | pre-commit overlaps wrapup verification |

No ADRs promoted — this is execution work, not architectural lock-in.

---

## 📐 Architecture Decision Records (ADRs)

None — every decision in this PLAN is reversible execution work, no binding architectural commitment beyond what 0.6.0 already locked in.

---

## 🏗️ Technical Design

### Current State

Post-0.6.0:
- `templates/agents/` — 11 files (autoloop-coder, code-reviewer, concurrency-reviewer, consensus-arbiter, executor, performance-reviewer, plan-validator, security-auditor, security-reviewer, test-reviewer, ux-reviewer)
- `templates/skills/` — 11 dirs (agent-quality-rubric, ai-readiness-rubric, autoloop-driver, conditional-router, context-linter, refdocs-search, relevance-filter, research-crawler, security-scanner, verify-before-completion, worktree-isolator)
- `templates/hooks/hooks.json.j2` — single jinja file with PostToolUse / PreToolUse / PreCompact / SessionStart events
- Hook Python implementations under `src/harness_maker/hooks/` (flush_session.py, sessionstart_drift.py) and `src/harness_maker/gates/` (permission_gate, worktree_gate, spec_gate)

### Affected Files (writes)

```
templates/agents/<existing>.md.j2      [audit pass — improve content where gaps found]
templates/agents/stuck.md.j2           [NEW — escalation agent]
templates/skills/<existing>/SKILL.md.j2 [audit pass — improve content where gaps found]
templates/hooks/hooks.json.j2          [add post-write-reminder PostToolUse entry]
src/harness_maker/hooks/post_write_reminder.py  [NEW — hook implementation]
src/harness_maker/synthesize.py        [agents 11 → 12 add stuck]
.claude-verify.sh                      [Agents (11) → (12)]
tests/unit/test_synthesize.py          [SIDE_FILES upper bound 55 → 60]
tests/snapshot/*.expected.yaml         [regenerated]
tests/e2e/sandbox{,-plugin-test}/.claude/* [regenerated baselines]
.claude-plugin/plugin.json             [version 0.6.0 → 0.7.0]
.cursor-plugin/plugin.json             [version 0.6.0 → 0.7.0]
pyproject.toml                         [version 0.6.0 → 0.7.0]
src/harness_maker/__init__.py          [version 0.6.0 → 0.7.0]
```

### Dependencies

- uniep reference at `~/EDGE/qcells/uniep/.claude/agents/` and `.claude/hooks/` — read-only.
- harness-maker test suite — must pass at every phase boundary.

### Reference uniep agents that map to ours

| uniep agent | ours | mapping |
|---|---|---|
| autoloop-coder | ✅ autoloop-coder | already aligned |
| coder | ≈ executor | uniep's CODER is our executor (single role) |
| coding-standard-reviewer | ≈ code-reviewer | check uniep depth |
| concurrency-reviewer | ✅ concurrency-reviewer | direct mapping |
| plan-validator | ✅ plan-validator | added in 0.6.0 |
| reviewer | ≈ code-reviewer (umbrella) | merged into code-reviewer in our model |
| reviewer-triage | ≈ Conditional Router (M6) | not an agent in our model |
| stuck | ❌ MISSING | **add** |
| test-reviewer | ✅ test-reviewer | added in 0.6.0 |
| tester | ≈ executor | merged role; not added |
| walkthrough-reviewer | ≈ code-reviewer | uniep adds runtime-path walkthrough lens; consider porting prompt fragment to code-reviewer |
| side-effect-reviewer | ≈ security-reviewer / code-reviewer | check overlap |
| resilience-reviewer | ❌ none | uniep-domain (embedded uptime); skip generically |
| resource-lifecycle-reviewer | ❌ none | uniep-domain; skip |
| storage-wear-reviewer | ❌ none | uniep-domain (eMMC); skip |
| mqtt-contract-reviewer | ❌ none | uniep-domain; skip |
| idea-* (14+) | ❌ none | uniep idea-finder domain; skip |
| research-critic / generator / verifier | ❌ none | decision: keep single-agent research |

### Reference uniep skills that map to ours

| uniep skill | ours | mapping |
|---|---|---|
| concurrent-test-review | ❌ generic-useful | consider port |
| property-based-testing | ❌ generic-useful | consider port (skill that triggers when test files have boundary inputs) |
| roadmap | ≈ ai-readiness-rubric (P0/P1/P2 actions) | partial overlap |
| bsp-build / uniep-build / embedded-build / bsp-deploy / etc | ❌ uniep-domain | skip |
| target-devices / daemon-control | ❌ uniep-domain | skip |
| templates | ≈ harness-maker render itself | meta-skill, skip |

### Reference uniep hooks

| uniep hook | ours | mapping |
|---|---|---|
| post-write-reminder.sh | ❌ MISSING | **add** (Python implementation, PostToolUse Write/Edit) |
| pre-commit-check.sh | ≈ wrapup Step 2 verification | overlaps; skip |
| session-stop.sh | ≈ PreCompact flush_session.py | partial overlap; skip |
| lib/auto-retry-gate.py | ≈ harness_maker.gates.* | overlaps; skip |
| lib/agent-validator.sh | ≈ .claude-verify.sh agents check | covered; skip |
| lib/sync-todo.sh | ❌ vault-only | not applicable |

---

## 📝 Implementation Plan

### Phase 1: Inventory + audit gap-list (read-only, ~30 min)

**Scope:** Walk every agent/skill template in `src/harness_maker/templates/` once, read its uniep equivalent (via the mapping table above) when one exists, score the gap on a 0-3 scale (0 = no gap; 3 = major content overhaul needed). Output an audit table inline in this PLAN under `## 📊 Audit Results`.

Reading checklist per agent/skill:
- Communication Protocol header present?
- OBSERVE → INFER → CONCLUDE reasoning discipline?
- Banned-patterns / hard-rules section?
- Output JSON schema (for agents that return structured output)?
- Out-of-scope section?

**Exit criterion:** `## 📊 Audit Results` table appended to this PLAN, every existing agent/skill has a 0-3 score with one-line reason.

**Risk:** low. Read-only.

**Rollback:** none needed.

### Phase 2: Existing agents content uplift (write-heavy, ~60 min)

**Scope:** For every agent scored ≥1 in Phase 1, port the missing sections from uniep equivalent. Specifically:
- `code-reviewer` — likely needs walkthrough-reviewer-style runtime-path-walkthrough fragment.
- `security-reviewer` / `security-auditor` — check uniep's side-effect-reviewer for additional categories.
- `concurrency-reviewer` — verify against uniep's depth.
- `consensus-arbiter` — verify our 2/3 + reasoning-alignment matches review.md.j2 Step 4 contract.
- Shared partials (`agents/_partials/*.md.j2`) — uplift if multiple reviewers benefit.

**Exit criterion:**
- Every existing agent has Communication Protocol section.
- Every reviewer agent declares OBSERVE→INFER→CONCLUDE discipline.
- Every reviewer agent has an explicit Out-of-Scope section.
- `wc -l templates/agents/*.md.j2` total stays within ~150% of pre-phase total (cap creep).

**Risk:** medium — reviewer prompt regression risk if a section is over-aggressively pruned. Mitigation: snapshot tests catch frontmatter / structural regressions.

**Rollback:** `git checkout HEAD -- src/harness_maker/templates/agents/`.

### Phase 3: New `stuck` agent (write, ~20 min)

**Scope:** Author `templates/agents/stuck.md.j2` modeled on uniep's `stuck.md`. Adapt to harness-maker:
- Triggered by `/hm:execute` Phase A.5 retry exhaust, Phase D unfixable, ADR conflict.
- Triggered by `/hm:review` when consensus filter produces unresolvable disagreements.
- Read-only (Read/Grep/Glob/Bash(git diff:*) only).
- Output: structured escalation note with root-cause analysis + 2-3 unblock options + manual-review recommendation.

Update `synthesize.py` _ALL_AGENTS (11 → 12), `.claude-verify.sh` (Agents (11) → (12)), `tests/unit/test_synthesize.py` upper bound (55 → 60).

**Exit criterion:**
- `tests/e2e/sandbox*/.claude/agents/stuck.md` rendered.
- `bash .claude-verify.sh final_acceptance` passes (agent count check).
- New agent loads in Cursor + Claude Code (manual-checklist row added).

**Risk:** low. Additive.

**Rollback:** `git checkout HEAD -- src/harness_maker/templates/agents/stuck.md.j2 src/harness_maker/synthesize.py .claude-verify.sh`.

### Phase 4: Existing skills content uplift (write-heavy, ~45 min)

**Scope:** For every skill scored ≥1 in Phase 1, port missing structure. Skills are different from agents — they're invoked by trigger keywords, so uplift focuses on:
- `description:` field accuracy (controls trigger relevance).
- `Why this skill matters` section.
- `When to invoke vs skip` examples.
- Concrete usage signature.

Specifically watch:
- `worktree-isolator` — already documented in execute.md.j2 Step 0; verify no contradiction.
- `verify-before-completion` — must match new verify.md.j2 6-check contract (now with --force, JSONL).
- `conditional-router` — must match review.md.j2 Step 1.
- `context-linter` — verify thresholds match CLAUDE.md `Context Lint` section.

**Exit criterion:**
- Each skill SKILL.md.j2 has explicit "When to invoke vs skip" guidance.
- No skill contradicts the corresponding stage template.
- Production preset skill total stays ≤ 150 lines per skill (per CLAUDE.md context lint).

**Risk:** medium — skill description changes can shift trigger-match probability in unpredictable ways. Mitigation: keep description verbs aligned with current stable triggers.

**Rollback:** `git checkout HEAD -- src/harness_maker/templates/skills/`.

### Phase 5: post-write-reminder hook (write, ~30 min)

**Scope:**
1. Implement `src/harness_maker/hooks/post_write_reminder.py` — reads tool input from stdin (Claude Code hook protocol), checks the written file's path against domain rules in `harness.yaml.project.domains` and the `wiki.md` `[wiki:gotcha]` entries, surfaces a one-line reminder when matches.
2. Wire into `templates/hooks/hooks.json.j2` as a PostToolUse Write|Edit entry, with `timeout: 5` (must be lightweight).
3. Add unit test: `tests/unit/test_post_write_reminder.py` covering match / no-match / missing-config cases.

The reminder is **advisory only** — never blocks the tool call. Output goes to stdout so Claude sees it in the next prompt.

**Exit criterion:**
- Hook fires in sandbox e2e on a Write to a watched path.
- `uv run pytest tests/unit/test_post_write_reminder.py -q` green.
- `tests/e2e/sandbox/.claude/hooks/hooks.json` contains the new entry.

**Risk:** medium — hook execution adds latency to every Write/Edit call. Mitigation: 5s timeout cap, fast-path early-return when no domain matches.

**Rollback:** `git checkout HEAD -- src/harness_maker/hooks/post_write_reminder.py src/harness_maker/templates/hooks/hooks.json.j2 tests/unit/test_post_write_reminder.py`.

### Phase 6: Verify + version bump 0.7.0 (write, ~20 min)

**Scope:**
1. Bump version in 4 files (`.claude-plugin/plugin.json`, `.cursor-plugin/plugin.json`, `pyproject.toml`, `src/harness_maker/__init__.py`).
2. Regenerate sandbox baselines + snapshot fixtures.
3. Run full test suite + `bash .claude-verify.sh final_acceptance`.
4. Single wrapup commit.
5. Optional push.

Why minor (0.6.0 → 0.7.0): adds 1 new agent + 1 new hook + meaningful improvements to 11 existing agents and 11 skills. user-visible surface area grows.

**Exit criterion:**
- All 4 version files = `0.7.0`.
- `uv run pytest tests/ -q` green.
- `bash .claude-verify.sh final_acceptance` green.
- Single commit pushed (when user requests push).

**Risk:** low. Mechanical.

**Rollback:** `git checkout HEAD~1` (the wrapup commit).

---

## 🧪 Testing Strategy

### Unit Tests

- `tests/unit/test_synthesize.py` — agent count assertion bumped 55 → 60 (Phase 3).
- `tests/unit/test_post_write_reminder.py` — new (Phase 5): match / no-match / missing-config.
- Existing snapshot tests (`tests/unit/test_synthesize_snapshot.py`) regenerated each phase that touches templates.

### Integration Tests

- `tests/e2e/test_dogfood_sandbox.py` — runs after each phase that changes synthesizer output. Sandbox baselines regenerated.
- `bash .claude-verify.sh final_acceptance` — full asset enumeration check.

### Manual Testing

- After Phase 3: load rendered `stuck.md` agent in Cursor IDE 2.4+, verify it shows up in agent picker.
- After Phase 5: run a Write tool call in a sandbox project with a known-domain path, confirm the reminder surfaces in stdout.

---

## ⚠️ Risks & Mitigation

| Risk | Impact | Mitigation |
|---|---|---|
| Agent prompt rewrite degrades reviewer quality | High | Phase 2 keeps existing prompt as baseline; only ADD missing sections, never reword unrelated content. Snapshot tests catch structural regressions. |
| post-write-reminder hook adds latency | Medium | 5s timeout, fast-path early-return, opt-out via `harness.yaml.hooks.post_write_reminder.enabled: false`. |
| Skill description changes break trigger-match | Medium | Phase 4 changes verb only when current is demonstrably wrong; preserve verb tense + key noun phrases. |
| Sandbox baseline churn obscures real diffs | Low | Each phase commits sandbox regen separately so the diff is auditable. |
| 0.7.0 bump too soon after 0.6.0 | Low | Document the per-phase exit criteria; if any phase blocks, ship as 0.6.1 patch instead. |

---

## ✅ Success Criteria

- [ ] Phase 1 audit table inline in this PLAN with 0-3 score per asset
- [ ] All existing agents have Communication Protocol + OBSERVE/INFER/CONCLUDE + Out-of-Scope
- [ ] `templates/agents/stuck.md.j2` rendered to sandbox baseline
- [ ] All existing skills have explicit "When to invoke vs skip" guidance
- [ ] `templates/hooks/hooks.json.j2` includes post-write-reminder entry
- [ ] `src/harness_maker/hooks/post_write_reminder.py` implemented + tested
- [ ] All 4 version files at `0.7.0`
- [ ] Full test suite green
- [ ] Single wrapup commit per phase
- [ ] Sandbox baselines regenerated after each phase

---

## 📊 Estimated Effort

- **Complexity:** Medium-High
- **Estimated Time:** 3-5 hours
- **Files Changed:** 25-35

---

## 🔍 Plan Validation (self-reviewed)

Self-check (no plan-validator agent invoked — too granular for an audit-style PLAN):

- ✅ Each phase has a verifiable exit criterion (test command or manual checklist).
- ✅ Each phase has rollback (git checkout the affected paths).
- ✅ No phase silently changes scope — audit boundaries explicit.
- ✅ No deferred decisions in checklist form (the audit table itself is data, not a missed round).
- ⚠️ Phase 1 (audit) is read-only but required input for Phases 2/4. Skipping it would force speculation.
- ⚠️ Phase 5 (hook) introduces a runtime cost on every Write/Edit. Marked as Medium risk with explicit mitigation.

Status: **APPROVED for execution** by self-review (resolution: APPROVED).

---

## 🔗 References

- `0.6.0` commits: `012ee6b` (plan), `65ce647` (research), `a691fe9` (spec), `c6c4187` (execute), `4718eb0` (review), `2b0e81d` (wrapup), `404b985` (verify), `2f8df23` (release).
- uniep agents: `~/EDGE/qcells/uniep/.claude/agents/`.
- uniep skills: `~/EDGE/qcells/uniep/.claude/skills/`.
- uniep hooks: `~/EDGE/qcells/uniep/.claude/hooks/`.
- CLAUDE.md `버전업 정책` — 4-file invariant for the 0.6.0 → 0.7.0 bump.
