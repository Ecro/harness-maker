---
type: research
task_slug: world-model-name
status: complete
created: 2026-10-02
tags: [harness-maker, research, python, jinja2, world-model, intent-layer, ux, skills, interview]
mtime_warn_days: 7
libs_fetched: []
sources:
  - https://agentskills.io/specification
  - https://code.claude.com/docs/en/skills
related_docs:
  - "[[RESEARCH-intent-world-model-objective-layer]]"
  - "[[SPEC-intent-world-model-objective-layer]]"
  - "[[SPEC-mission-context-loop]]"
  - "[[PLAN-world-intent-closed-loop-trial]]"
summary: "Name the world model at onboarding (default Maker) and render one thin router skill /maker as the dev front door"
---

# RESEARCH — Named world model ("Maker") as the development front door

## 🎯 Recommended Direction

**Ask for the world model's name right after locale in onboarding (default `Maker`), store it in
`harness.yaml`, and render one thin router skill named after it (`/maker`, `$maker`) that routes
plain-language requests to the machinery that already exists — stages, intent layer, project
knowledge, status — instead of building a new subsystem.**

Rationale. The user's request has two halves: (1) a name chosen up front so the world model is
easy to call, and (2) — added mid-research — "a structure where interacting with Maker makes
development easy; maximize the user's UX". Today the world model is spread across two skills
(`intent-layer`, `project-knowledge`), an `hm intent …` verb tree of ~20 subcommands, and seven
`/hm:` stages. The operator has to know which surface owns which request. The cheapest
high-value fix is a *single addressable entry point* whose body is an LLM routing table (per the
project's LLM-judgment principle), not new Python logic. The user already runs exactly this
pattern for their personal world model — the `bibi` skill: one name, an operation table
(no-arg → briefing, pasted facts → ingest, "어디까지?" → query), invoked by `/bibi` or by
calling "비비". Impact is **user-facing workflow value** (fewer surfaces to remember, one verb
to start/resume/record), with a small internal cost (one config key, one rendered skill, one
interview question, one configure dimension).

Informational only — `/hm:spec` locks the operation set and the name/slug rules.

## 🔍 Refinement Decisions

- Discovery lens: **User-workflow / product opportunity** (primary — the ask is UX) +
  **Technical architecture / implementation** (config schema, render path, skill naming rules).
- Mid-research scope change from the user: "Maker 와 상호작용하면서 개발을 편하게 할 수 있는
  구조 … 유저의 UX 를 최대한". The task is therefore not only "a name field" but "a named front
  door". Recorded as scope, not as a decision on how far the router reaches (Open Question 1).

### Local capability × User artifact

| User artifact / habit | Existing harness capability | Gap Maker closes |
|---|---|---|
| "Build/fix X" in plain words | `/hm:research` → … → `/hm:wrapup`, autopilot auto-advance | User must pick the entry stage and a slug |
| "Where are we?" | `hm intent status --json`, `hm autopilot status`, task worktrees `.worktrees/<slug>` | No single read-only briefing; three verbs, none advertised as one answer |
| "Remember: <fact>" / "that's wrong" | `project-knowledge` skill → `.claude/memory/wiki.md` | Works only if description matching fires; no name to address |
| Goals, metrics, open questions | `intent-layer` skill, `.claude/intent.yaml`, `intent/<ID>.md` | ~20 verbs; operator must know the skill exists |
| Personal world model with a name (`bibi`) | — (user's own vault skill) | Proves the named-router UX the user already prefers |

## 🛠️ Approaches Found

### A. Trigger word only (no new file)

| Field | Content |
|---|---|
| Approach | `world_model.name` in harness.yaml; render the name into the `intent-layer` and `project-knowledge` descriptions and into the always-loaded pointer ("Addressing Maker = …") |
| Assumption | Description matching reliably fires on the name; the operator is happy with natural language only |
| Evidence | Claude Code auto-invokes on description match ([skills docs]); but descriptions are **dropped under listing budget, least-invoked first** ([skills docs]) — a trigger word can silently stop working. Codex starts skills only on explicit `$name` mention (`project_knowledge_pointer.md.j2`) |
| Trade-off | Near-zero cost; no `/maker`, no briefing, routing split across two skills, fails the "maximize UX" half |
| Compatibility | Touches two skill templates + pointer partial (AC-005 caps the pointer at 300 chars/variant) |
| Risk | medium (silent non-firing) |

### B. Thin named router skill — **recommended**

| Field | Content |
|---|---|
| Approach | `world_model: {name: Maker}` in harness.yaml (display name, any Unicode) + derived ASCII handle (`maker`). Render `.claude/skills/<handle>/SKILL.md` (and `.agents/skills/<handle>/` for Codex). Body = operation table routing to existing surfaces; no new state, no new CLI verbs in v1 |
| Assumption | Routing is an LLM judgment over a short table; every destination already exists and keeps its own consent rules |
| Evidence | `bibi` skill (user's own, same shape); Claude Code `/skill-name` direct invocation + `$ARGUMENTS` ([skills docs]); `reconcile.sweep_orphans` already retires pristine generated files no longer in the render set, so a rename does not leave a stale `/maker` behind (`src/harness_maker/reconcile.py:684`) |
| Trade-off | +1 skill listing entry (~100 tokens/turn, [agentskills spec] progressive disclosure) + one pointer clause in CLAUDE.md/AGENTS.md (char budget); a dynamic directory name is new for this renderer |
| Compatibility | Fits "Python = types/storage/rails, prompt = judgment". Config: `HarnessConfig` is `strict=True, extra="forbid"` (`models.py:1116-1121`) → new sub-model with defaults; absent key ⇒ `Maker` |
| Risk | low-medium (naming/collision rules, snapshot + surface-baseline churn) |

Proposed v1 operation table (spec decides):

| Input to Maker | Route |
|---|---|
| no argument | read-only briefing: active task worktrees + their stage, autopilot state, `hm intent status` (open questions, metrics due) — changed things only |
| "build / fix / investigate X" | start the pipeline at `/hm:research X` (or `/hm:spec` when the ask is already concrete), deriving the slug; autopilot carries it |
| "continue / 이어서" | resume the most recent task's next stage (from worktree + autopilot marker) |
| "remember X" / "X is wrong" | `project-knowledge` |
| goal / metric / assumption talk | `intent-layer` (its consent rule unchanged) |
| "what next?" | present options from the briefing; **never** start a stage without the operator choosing |

### C. Maker as a full subsystem

| Field | Content |
|---|---|
| Approach | Maker subagent + persona file (bibi's `SOUL.md` analogue) + `hm maker brief/next` aggregator CLI + its own memory |
| Assumption | Briefing needs deterministic aggregation and a persistent persona |
| Evidence | Prior research on the same area already judged the intent layer "five subsystems where three would do" (`RESEARCH-intent-world-model-objective-layer.md:38`) |
| Trade-off | Most polished; contradicts the first goal ("avoid complex design"); persona voice conflicts with "no coaching/learning modes" in CLAUDE.md |
| Compatibility | New CLI verb is unusable in dogfood until the next release (rendered harness pins the released plugin) |
| Risk | high |

A `hm maker brief` aggregator is the natural **follow-up** to B if composing three read-only
verbs in-prompt proves slow or inconsistent — measure first.

## ⚠️ Pitfalls

1. **Skill name rules.** `name` must be 1-64 chars of `a-z 0-9 -`, no leading/trailing/double
   hyphen, and must match the parent directory ([agentskills spec]). "비비", "메이커", "Maker"
   are invalid as-is → the display name and the invocation handle must be two fields (or the
   handle derived with an ASCII fallback). Claude Code lets frontmatter `name` override the
   directory ([skills docs]) but the open spec forbids mismatch — Codex may enforce it.
2. **Collision.** The handle must not equal an existing rendered skill (`intent-layer`,
   `project-knowledge`, …), a Codex stage skill (`hm-<stage>`), or a host built-in slash command.
   Default `maker` is close to `/harness-maker:make` and the `hm:make` skill — fine for
   autocomplete, but the description must not fire on the verb "make".
3. **Absent-case black hole** (global learned correction 2026-06-08). Old harness.yaml has no
   key → must render `Maker`, not skip. Test the absent case, not only the present one.
4. **Silent description drop.** Under listing pressure Claude Code drops least-used descriptions
   ([skills docs]). The always-loaded pointer line is the robust path for the name; keep it
   inside AC-005's 300-char cap per variant (`tests/render/test_render_project_knowledge.py:110`).
5. **Router bypassing gates.** Prior research Pitfall 3: a read-only "next" does not secure
   human selection — the agent walks into the SPEC path itself while `auto_safe` +
   `autopilot_persistent` are armed (`RESEARCH-intent-world-model-objective-layer.md:355`).
   Maker must route *to* stages, not reimplement or skip their gates; "what next?" presents,
   never starts.
6. **Advertised-name integrity.** A prior fix had to require every advertised skill name to
   resolve against the rendered skills (`[fail:design] fix-introduced-defect-passes-all-gates`,
   2026-09-27 loop-opt-in). A dynamically named skill must join that check, and every pointer
   that says "call Maker" must resolve to the rendered handle.
7. **Surface baseline / snapshots.** A new rendered file moves the frozen surface baseline and
   snapshot fixtures (`project_surface_allowance_expires_at_wrapup`); plan the re-freeze.
8. **Forward compat of `extra="forbid"`.** A harness.yaml carrying `world_model:` is rejected by
   any older plugin CLI that loads it. Re-render updates the pin, so the window is "edited yaml,
   not yet re-rendered" — inference, verify in spec.

## ❓ Open Questions

1. **Router reach.** Does v1 Maker start/resume stages (full front door), or only briefing +
   knowledge + intent (world-model only)? The mid-research ask points to the former.
2. **Handle for non-ASCII names.** Separate interview question ("호출 핸들") vs. silent fallback
   to `maker` when the name has no ASCII slug?
3. **Config shape.** `world_model.name` (+ `world_model.handle`) vs. a top-level
   `assistant_name`. Is "world model" the term the user wants exposed in harness.yaml?
4. **Voice.** Does Maker answer with a fixed prefix/voice (like bibi's `🐦`), or plain harness
   voice ("concerns first, no flattery")? CLAUDE.md rules out coaching modes.
5. **Disable switch.** Can the operator opt out of the router skill (empty name), or is it always
   rendered?
6. **Interview placement.** Right after locale (user said "처음에") in both `/harness-maker:make`
   and the Python CLI interview, plus a `/hm:configure` dimension and a `--ci world_model_name=`
   flag — confirm all four surfaces.
7. **Cursor.** Cursor reads `.claude/skills/` natively; confirm `/maker` appears in Cursor's
   command list or only via description matching.

## 📚 Sources

- [agentskills spec] https://agentskills.io/specification — `name`/`description` constraints, progressive disclosure.
- [skills docs] https://code.claude.com/docs/en/skills — `/skill-name` invocation, `$ARGUMENTS`, 1,536-char listing truncation, least-used descriptions dropped under budget, `disable-model-invocation`.
- User's personal `bibi` skill (`~/.claude/skills/bibi/SKILL.md`) — named world-model router UX (user-workflow source).
- Internal: `src/harness_maker/models.py:1116` (HarnessConfig strict/forbid), `src/harness_maker/interview.py:130-154` (skill enable lists), `commands/make.md` §1 (locale is the first question), `src/harness_maker/templates/agents/_partials/project_knowledge_pointer.md.j2` (always-loaded pointer, Codex `$name` rule), `src/harness_maker/reconcile.py:684` (`sweep_orphans`), `src/harness_maker/intent.py:534-614` (intent verbs), `src/harness_maker/templates/commands/hm/configure.md.j2` (dimensions).

## 🔗 Related Internal Docs

- [[RESEARCH-intent-world-model-objective-layer]] — what the world model is; Pitfall 3 (human selection) applies to Maker's "next".
- [[SPEC-intent-world-model-objective-layer]] — S13: `intent-layer` exists because operators cannot remember the verbs; Maker is the next step of the same argument.
- [[SPEC-mission-context-loop]] — AC-005 pointer cap; `project-knowledge` routing.
- [[PLAN-world-intent-closed-loop-trial]] — `intent_world_closed_loop_cycles`; a front door that resumes the next stage bears on "without re-instruction".

## Feedback

| Evidence | Affected ID | Update status | Decision | Owner | Authority | Next action |
|---|---|---|---|---|---|---|
| This RESEARCH: Maker router would resume the next stage without the user re-stating the connection | intent_world_closed_loop_cycles | recorded | metric record intent_world_closed_loop_cycles = 1 (operator: yes) | DRI | wrapup Step 5.7 answer | wrapup Step 5.7 decides |

## 🧭 Addendum (2026-10-02) — Maker's information model and token budget

Asked mid-execute: "what must Maker hold to give the best UX while optimizing tokens; survey
current harnesses and SDLC techniques". Findings (measured in this repo + cited):

- **Measured cost of the first briefing draft:** `hm intent status --json` = 17,555 chars
  (~4.5–5K tokens), of which ~0.4 KB is actionable; `stage-spans.jsonl` = 193 KB / 627 rows with
  no cap in the prose; `wiki.md` 456 KB and `failures.md` 377 KB must never be loaded whole.
- **Tiers:** (a) always-loaded — the ≤200-char pointer + the skill description (~150 tokens,
  static, cache-safe); (b) on invocation — routing rules + a ≤1.5 KB state digest (~1.2K
  tokens; survives Claude Code's 5K-token per-skill compaction re-attach); (c) on demand —
  PLAN/SPEC/REVIEW by path, wiki/failures by capped grep.
- **Digest content:** tasks (≤5: slug, last stage, ended vs interrupted, next stage), autopilot
  one-liner, intents needing a decision (≤3 + counts), what changed since last session (landed
  commits / `Understanding:` blocks). No stored "next action" — derived, never persisted.
- **Techniques:** progressive disclosure (fact: Claude Code skills docs; Codex 2% / 8K skill
  list cap); stable prefix — never put live state in CLAUDE.md/AGENTS.md/pointer (fact: Claude
  Code prompt-caching lessons); SessionStart injection rejected for v1 (cost every session,
  inconsistent across Claude Code/Codex/Cursor — Cursor forum reports dropped context); hook-
  maintained digest file rejected (new store, staleness, multi-session races).
- **Field convergence (cited):** Anthropic long-running harness guidance (progress file + git
  log + feature list on session start), context engineering ("smallest set of high-signal
  tokens", just-in-time retrieval), BMAD `bmad-help`/`workflow-status` as universal entry
  point that recommends the next step, Kiro steering modes (always / fileMatch / manual), Amp
  Handoff and Factory `/handoff`, Devin Knowledge vs Playbooks, DORA 2025 AI Capabilities Model.
  Inference: one entry point that reads state and suggests the next step, with state in files
  and git, is the converging shape — Maker's tier split matches it.

Applied in v1 (template-only, within SPEC scope): capped briefing commands (intent status
filtered to 7 actionable keys → 401 chars measured; newest span per slug via `grep | tail -n 1`),
resume re-enters an interrupted stage, ≤8-line reply, never Read the big files.
Proposed follow-ups (need a SPEC change — new `hm` verb is a public CLI contract):
P1 `hm` digest verb (deterministic digest, interrupted-stage logic in code); v1.1 query route
("why did we decide X" → capped grep over wiki/failures/ADRs, Explore subagent >3 files),
failures-since-last-session in the digest, stage STOP text ending with "next: `/<handle> 이어서`".

Sources (addendum): https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents ·
https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents ·
https://www.anthropic.com/engineering/harness-design-long-running-apps ·
https://code.claude.com/docs/en/skills · https://code.claude.com/docs/en/hooks ·
https://claude.dev/blog/lessons-from-building-claude-code-prompt-caching-is-everything/ ·
https://developers.openai.com/codex/skills · https://developers.openai.com/codex/hooks ·
https://forum.cursor.com/t/sessionstart-hook-additional-context-is-never-injected-into-agents-initial-system-context/158452 ·
https://kiro.dev/docs/steering/ · https://developer.microsoft.com/blog/spec-driven-development-spec-kit/ ·
https://docs.bmad-method.org/how-to/established-projects/ · https://ampcode.com/news/handoff ·
https://docs.factory.ai/changelog/release-notes · https://docs.devin.ai/work-with-devin/devin-handoff ·
https://cloud.google.com/resources/content/2025-dora-ai-assisted-software-development-report
