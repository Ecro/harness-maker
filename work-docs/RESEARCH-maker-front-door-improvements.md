---
type: research
task_slug: maker-front-door-improvements
status: complete
created: 2026-10-03
tags: [harness-maker, research, python, jinja2, front-door, router, autopilot, token-economy]
mtime_warn_days: 7
libs_fetched: [code.claude.com/docs/en/skills, code.claude.com/docs/en/hooks, code.claude.com/docs/en/prompt-caching, cursor.com/docs/context/skills, learn.chatgpt.com/docs/build-skills, agentskills.io/specification]
sources:
  - https://code.claude.com/docs/en/skills
  - https://code.claude.com/docs/en/hooks
  - https://code.claude.com/docs/en/prompt-caching
  - https://cursor.com/docs/context/skills
  - https://learn.chatgpt.com/docs/build-skills
  - https://agentskills.io/specification
  - https://github.com/anthropics/claude-code/issues/12781
  - https://github.com/anthropics/claude-code/issues/19209
  - https://www.anthropic.com/engineering/building-effective-agents
  - https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents
  - https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills
  - https://www.langchain.com/blog/choosing-the-right-multi-agent-architecture
  - https://cognition.com/blog/dont-build-multi-agents
related_docs: ["[[PLAN-world-model-name]]", "[[PLAN-world-model-followups]]", "[[RESEARCH-world-model-name]]", "[[REVIEW-world-model-name-2026-10-02]]", "[[REVIEW-world-model-followups-2026-10-02]]"]
summary: "Keep Maker thin; fix the handoff (scope→autopilot), load-abort risk, and measurability first"
---

# RESEARCH — Maker front door: improvement candidates

## 🎯 Recommended Direction

**Keep Maker a thin router, and spend the next unit on the handoff, not the router body.**
Maker itself is cheap (3,745 chars rendered ≈ 1K tokens per load; digest capped at 1,500 B).
The stage it hands off to costs 7–25× more (`research.md` 25,220 chars, `spec.md` 50,387,
`execute.md` 65,797, `review.md` 90,919). So the leverage for the three principles sits at
the boundary Maker controls:

1. **Quality/UX — scope does not cross the handoff.** Maker's Start row enters a stage with
   "X as the topic" and drops the operator's scope. With `autonomy.autopilot_persistent: true`
   (this repo, default true) and research having *no mandatory gate*, "research this" runs
   research → spec → execute → … unattended. Observed in this very session: the operator
   asked for research only plus "ask me on conflicts", and the only thing preventing an advance
   into spec was the agent choosing to treat that sentence as a gate.
2. **Robustness — the `!` digest can abort Maker entirely.** Claude Code aborts the whole skill
   when a `!` command exits non-zero, before Claude sees the body (docs, H). The digest itself
   always exits 0, but `uv run --with <missing cache path>` exits 2 (measured). The fallback line
   "No JSON above? run …" is therefore unreachable in exactly the case it was written for.
3. **Measurability — adoption is unmeasured.** `telemetry.py:61-63` keeps only
   `path/file_path/command/target/database/url/query` from `tool_input`, so 268 recorded `Skill`
   rows carry no skill name; `!` runs are never logged; no span stage is `maker`. The founding
   commit lists "whether operators adopt /maker" as an *unknown*. Nothing can resolve it today.

Main impact: user-facing workflow value (1, 2), maintainer value (3). Router-body token trims
are second-order and should wait for (3) to produce data.

## 🔍 Refinement Decisions

Discovery lens: User-workflow (this session as a live dogfood trace + operator usage data),
Technical architecture (template, digest, telemetry), Risk (load abort, unattended advance).
No `--deep` interview — the topic and principles were given.

Operator decisions on the conflicting trade-offs (2026-10-03, after Phase 3):
- **Q1 handoff scope → Maker narrows autopilot** to the ask's end point (`hm autopilot on --pipeline …`). Accepts crossing the ADR-008 "routes only" boundary; spec must define misclassification handling.
- **Q2 session-start briefing → keep on-demand only** (prior decision stands; Approach C dropped).
- **Q3 research-only hygiene → keep the task worktree; digest marks stale research-only tasks `parked`.**
- **Q5 scope → include** the stage-side `memory_retrieve` relevance/size problem in this unit.
- **Q6 single entrance (2026-10-03, follow-up) → Maker is the only entrance.** A surface Maker
  routes to (`intent-layer`, `project-knowledge`, the `/hm:` stages) must not self-trigger from
  natural language; it runs only when Maker routes to it or the operator types its name
  explicitly. Today none of the rendered skills/commands carries `disable-model-invocation`
  (checked 2026-10-03), and `intent-layer`'s description is not name-gated, so "change the
  goal" reaches it without Maker.
  **Mechanism conflict for spec to resolve:** Claude Code's `disable-model-invocation: true`
  (docs, H) blocks auto-trigger *and* every model-side `Skill` call — which is how Maker hands
  off and how autopilot advances (`Skill(hm:<next_stage>)`). Candidates: (a) hard flag on
  `intent-layer`/`project-knowledge` with Maker reading their `SKILL.md` via Read instead of
  `Skill`, stages kept model-invocable for autopilot but description-gated; (b) description-only
  gating everywhere ("only when routed by Maker, typed by the operator, or advanced by
  autopilot") — soft, LLM-judged. Codex equivalent of the hard flag is
  `allow_implicit_invocation: false` in `agents/openai.yaml`; Cursor supports
  `disable-model-invocation`. Internal helper skills invoked by stages
  (`targeted-test-selection`, `second-opinion-gate`, …) are not entrances and stay as-is.

## 🛠️ Approaches Found

### A. Handoff contract (scope → stage/autopilot) — recommended first

| Field | Content |
|---|---|
| Approach | Maker classifies the ask's *end point* (research-only / spec-only / full build) and passes it: narrow the autopilot pipeline (`hm autopilot on --pipeline research …` already exists, `autopilot.py:1056`) or tell the operator in its one-line route statement that autopilot will advance to `<next>` |
| Assumption | The operator's phrasing ("리서치해봐", "조사만") reliably signals end point; LLM classification is accurate enough (Anthropic: routing works "where classification can be performed accurately") |
| Evidence | This session; `research.md` "No mandatory gate — research may auto-advance"; `harness.yaml:193 autopilot_persistent: true` |
| Trade-off | Re-arming changes a session-wide marker from inside a router whose ADR-008 says "routes only, never re-implements a gate". Informing-only is cheaper but relies on the operator reading one line |
| Compatibility | Uses existing CLI; no new verb. Touches ADR-008 boundary |
| Risk | medium — a wrong classification either stalls a full build or over-runs a research ask |

### B. Load robustness + cheap telemetry

| Field | Content |
|---|---|
| Approach | (1) make the injected command fail-soft: `… digest … 2>/dev/null \|\| echo '{"unavailable":"digest"}'` so the skill always loads and the existing fallback line becomes reachable; (2) add the skill name (`skill`/`command` key of the Skill tool input) to the telemetry allowlist so `/maker` vs `/hm:*` use becomes countable |
| Assumption | Skill tool input carries the name under a stable key (verify against a real row before coding) |
| Evidence | Docs (abort on non-zero, H); `uv run --with …/9.9.9` rc=2 (measured 2026-10-03); old caches 0.60.4–0.61.0 are currently retained, so the failure is latent, not live |
| Trade-off | None material; telemetry stays 100% local |
| Compatibility | Codex/Cursor unaffected (no `!` there; Codex branch already uses an explicit run block) |
| Risk | low |

### C. Session-start briefing (hook) instead of / in addition to on-demand Maker

| Field | Content |
|---|---|
| Approach | Inject the ≤1.5 KB digest via SessionStart `additionalContext` |
| Assumption | Most sessions want the briefing |
| Evidence | Hook output is cached after turn 1 and capped at 10K chars (docs, H); RESEARCH-world-model-name rejected it on purpose; Maker re-invocation with a changed briefing re-appends the full body (docs, H) |
| Trade-off | Pays ~400 tokens every session, including ones that never ask; on resume the replayed digest is stale. Gains zero-keystroke orientation |
| Compatibility | Cursor has `sessionStart`; Codex too; no `!` dependency → better cross-runtime parity |
| Risk | low technically; it reverses a prior decision — operator's call |

### D. Route-table coverage (deferred items from SPEC non-goals)

"Why did we decide X?" route, "failures since last session", stage STOP-text hints. All
listed as v1.1 non-goals (`SPEC-world-model-followups.md:121-127`). No usage data says which
is wanted; defer until B(2) produces data.

## ⚠️ Pitfalls

- **Unattended advance on a research ask** (this session). Treating free-text constraints as a
  gate is agent discretion, not mechanism.
- **Fallback that can't fire**: SKILL line 52-53 assumes the body loads when the `!` fails; Claude
  Code aborts instead (docs).
- **`!` in example text executes** even inside fences (GH #12781, #19209 open). Any future Maker
  doc example must not start a line with `!`.
- **Router double-load is real but small here**: LangChain measures ~15K vs 9K tokens for
  skill-accumulating vs subagent routing on multi-domain asks (vendor benchmark, M). For Maker the
  router share is ~1K of a ≥7K handoff — trimming Maker's body is low-yield.
- **Stage-side waste dwarfs Maker's**: this session's `memory_retrieve` returned ~30 KB (≥30K
  chars elided by the tool itself) of mostly test-gate failure entries for a Maker topic — the
  high-recurrence "count floor" admits them regardless of relevance. Out of Maker's scope but the
  largest token item observed in this trace.
- **Research-only tasks leave a task worktree** whose digest `next_stage` stays `spec` forever,
  so a "research only" habit fills the briefing's 5 task slots with stale rows (inference from
  `next_stage()` at `world_model_digest.py:152-180`; not yet observed).
- **Cursor**: `.cursor/rules/harness.mdc` here is stale (2026-05-09) without the pointer; `!` in
  Cursor undocumented; Cursor sessions are id-less so `other_session` is always `null`.

## ❓ Open Questions

1. **Handoff scope (UX vs control):** should Maker *narrow autopilot* to the ask's end point,
   *only announce* the advance, or *always ask* before a stage that will auto-advance?
2. **Session-start briefing (tokens vs UX):** keep on-demand only (prior decision), or add the
   ≤1.5 KB digest at SessionStart?
3. **Research-only task hygiene:** should a research-only Start skip the task worktree (write
   RESEARCH on base) or keep it and let the digest mark it `parked`?
4. Does the Skill tool's `tool_input` expose the skill name under a stable key? (verify in spec)
5. Is the stage-side `memory_retrieve` relevance problem in scope for this unit or its own task?

## 📚 Sources

- https://code.claude.com/docs/en/skills — `!` timing, abort on non-zero, permission, lifecycle, re-append on changed content
- https://code.claude.com/docs/en/hooks — SessionStart `additionalContext`, 10K cap, resume replay
- https://code.claude.com/docs/en/prompt-caching — skill content as user message; model switch re-reads uncached
- https://cursor.com/docs/context/skills — no `!` injection documented
- https://learn.chatgpt.com/docs/build-skills — Codex skills, static body, 2% listing budget
- https://agentskills.io/specification — open spec, no shell injection
- https://github.com/anthropics/claude-code/issues/12781 , https://github.com/anthropics/claude-code/issues/19209 — `!` in examples executed/permission-checked
- https://www.anthropic.com/engineering/building-effective-agents — routing when classification is accurate; start simple
- https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents — smallest high-signal token set
- https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills — progressive disclosure, separate rarely co-used paths
- https://www.langchain.com/blog/choosing-the-right-multi-agent-architecture — router/skill token accumulation (vendor numbers)
- https://cognition.com/blog/dont-build-multi-agents — prefer single-thread handoff over forked context

## 🔗 Related Internal Docs

- [[RESEARCH-world-model-name]] — origin, bibi model, SessionStart rejected (:197-199), token budget (:185-190)
- [[PLAN-world-model-name]] — ADR-001..011 (ADR-008 routes-only)
- [[PLAN-world-model-followups]] — digest ADR-001..008
- [[REVIEW-world-model-followups-2026-10-02]] — carried P2s: whole span ledger read, private `_freshness`, `index.lock` in `_verify_done`, vanishing worktree, English-only CLI errors
- `src/harness_maker/templates/skills/world-model/SKILL.md.j2`, `src/harness_maker/world_model_digest.py`, `src/harness_maker/telemetry.py:61-63`

## Feedback

| Evidence | Affected ID | Update status | Decision | Owner | Authority | Next action |
|---|---|---|---|---|---|---|
| this RESEARCH §Recommended Direction 3; commit 7aeb2f47 "unknown: whether operators adopt /maker" (2026-10-03) | intent_world_closed_loop_cycles | declined | Maker use is unmeasurable (Skill name dropped by telemetry), so front-door contribution to closed-loop cycles cannot be traced | agent | pending decision | wrapup Step 5.7 |
