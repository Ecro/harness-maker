---
type: research
task_slug: locale-and-command-observability
status: complete
created: 2026-06-17
tags: [harness-maker, research, locale, i18n, observability, templates, jinja2]
mtime_warn_days: 7
libs_fetched: []
sources: []
related_docs: ["[[llm-prose-invokes-python-module-the-wiring-is-the-bug]]", "[[hash-marker-syntax-not-start-end]]"]
summary: "Inject one shared locale directive + start/end summary banners at the wrapper layer; enforce via render-required input + /hm:health check"
---

# RESEARCH — Persistent locale + per-command start/end observability

## 🎯 Recommended Direction

**Both features are pure prompt-prose injected at the *wrapper template* layer, driven by `{{ config.locale }}`, and made non-skippable by reusing the proven `communication_variant` enforcement pattern (render-required input + `/hm:health` Layer-1 silent-miss check).**

Two gaps, one shared mechanism:

1. **Locale** — `config.locale` already reaches every template's render context, but it currently governs *only* interview/live-UX prose. **No instruction anywhere tells the AI to respond to the user in their locale.** Add one shared `output_language.md.j2` partial (English text + `{{ config.locale }}` variable — LLM translates on the fly, zero new locale-variant files) included by the command wrappers and the agent communication partials, plus a durable "Output Language" rule in generated CLAUDE.md (always in context → governs ad-hoc chat too).
2. **Observability** — the start-summary already exists as one shared partial (`step_manifest.md.j2`); the end-summary is hand-rolled per stage and inconsistent. Add one shared `stage_end_summary.md.j2` partial at the same wrapper layer so a uniform "what I did / artifacts / next" banner fires for every atomic stage, every fused workflow, both IDEs, in one edit.

The binding trade-off for **both** features: **single shared injection point (wrapper + partial, `{{ config.locale }}` interpolation) vs per-asset locale-variant duplication.** The single-injection path adds 0 new hand-translated files and 1–2 edits; the duplication path adds 24+ files (12 agents × 2 locales) and a permanent maintenance burden. Choose single-injection. The cost paid: enforcement is prompt-discipline, not runtime-forced — mitigated (not eliminated) by the `/hm:health` render-time check.

This is informational. `/hm:plan` makes the binding architectural decision, especially on the two open questions below (deliverable-language scope; autoloop summary suppression).

## 🔍 Refinement Decisions

`--deep` not set → Phase 0 / 0.5 refinement interview skipped.

**Discovery lens:** Technical architecture / implementation (primary). This is an internal harness-maker template/render-pipeline question, not a user-workflow or product-opportunity topic — Second Brain (`reference`/`project`) returned no notes; web search skipped because the answer is internal-authoritative (CLAUDE.md §"외부 소비자 파서 정합성", `synthesize.py`, `render.py`, the template tree).

## 🛠️ Approaches Found

### Feature 1 — "Always respond in the configured locale"

Current state (mapped): `config.locale` (free-text str, default `en`; `en`/`ko` first-class via `i18n`, others → `en`) is injected into **every** template's context as `config` (`synthesize.py:720,770`). `i18n.py` / `i18n_messages.py` are **Python runtime error messages only** (6 keys) — never injected into prompts. Stage templates use `{{ config.locale }}` **only** for interview/live-UX prose and explicitly state *"the persisted RESEARCH/PLAN document remains English"* (`research.md.j2:105-106`). Generated CLAUDE.md (dual hand-authored `.en`/`.ko` templates per preset) contains **no** "respond in locale" instruction. Agent bodies and the `communication_*` partials carry **no** output-language directive. Net: AI narrative output defaults to English everywhere → the "language only at onboarding" symptom.

| Field | A. CLAUDE.md durable rule | B. Wrapper partial (`output_language.md.j2`) | C. Agent communication partials |
|-------|---------------------------|----------------------------------------------|----------------------------------|
| Approach | One "## Output Language" section in generated CLAUDE.md (loaded every session) | One shared partial included by `atomic_command.md.j2` + `workflow_command.md.j2` + codex `stage_skill`/`workflow_skill` | Add a locale line to `communication_full/reframe/soft.md.j2` |
| Assumption | CLAUDE.md is in context for all interaction, incl. ad-hoc/non-hm chat | Coverage of `/hm:` commands is enough | Dispatched subagents are the gap |
| Evidence | CLAUDE.md loaded each session (observed in this very prompt's context); dual templates at `claude-md/*.{en,ko}.md.j2` | `step_manifest.md.j2` proves the wrapper-include pattern works uniformly | `communication_variant` system already wires these 3 partials to 14 agents |
| Trade-off | Edits 4 hand-authored files; user can delete the rule | Fires only for `/hm:` commands, not ad-hoc chat; doesn't reach subagents | Reaches only agents, not the main command loop |
| Compatibility | High — uses existing dual-template structure | High — same mechanism as the start preamble | High — slots into existing variant system |
| Risk | low | low | low |

**Recommended: layered A + B + C** (defense-in-depth, all off one `{{ config.locale }}` variable, zero new locale-variant files). A makes it durable/always-on; B reinforces per-command; C covers subagents. Must preserve the existing invariant — **code, identifiers, and persisted deliverables stay English** (see Open Question 1) — so the directive must read like `research.md.j2:105-106`: *"Respond to the user in {locale}; code, identifiers, and persisted PLAN/RESEARCH/REVIEW/SPEC documents stay English."*

### Feature 2 — Uniform start/end command summaries

Current state (mapped): **start** = single shared `agents/_partials/step_manifest.md.j2`, included by the wrappers `atomic_command.md.j2:1`, `workflow_command.md.j2:1`, codex `stage_skill.md.j2:6`, `workflow_skill.md.j2:6` — self-skips when `.hm-loop-active` exists. **end** = hand-rolled "Stage terminal" prose, *inconsistent* (research/plan/spec/verify have one; execute/review/wrapup don't). `gate0_receipt.md.j2` is the only universal end-partial but it's a **machine receipt**, not human prose. Communication Protocol is hand-rolled per stage (duplicated by design). Observability JSONL (`telemetry.py` → `.claude/observability/*.jsonl`) is **machine telemetry**, orthogonal to the human-facing prose the user is asking for.

| Field | A. Wrapper-layer shared banners | B. Promote per-stage "Stage terminal" to a shared macro | C. Hook-enforced |
|-------|----------------------------------|---------------------------------------------------------|------------------|
| Approach | Reuse `step_manifest` for start; add `stage_end_summary.md.j2`; both included by the 4 wrappers | Replace 7 hand-rolled terminals with one `{% macro %}` invoked per stage | `Stop`/`PreToolUse` hook checks a summary was emitted |
| Assumption | Wrapper is the single chokepoint (it is) | Stage-specific output detail is worth 7 edits | Runtime can enforce prose |
| Evidence | Agent-2 map: wrappers carry `stage`/`workflow_name` context already | Each stage knows its own artifact path | `telemetry.py` Stop hook exists |
| Trade-off | Banner is generic; LLM fills stage specifics | 7 files touched; in fused workflows fires per-stage (possibly noisy) | **Hooks cannot author prose** — can only detect/log absence |
| Compatibility | High — identical to start-preamble mechanism | Medium — more surface area | Low for the actual ask |
| Risk | low | medium | n/a (rejected as primary) |

**Recommended: A.** Keep `step_manifest` as the start banner (reframe it from a bare numbered manifest into a "🎯 goal / 📋 plan" banner); add a sibling `stage_end_summary.md.j2` ("✅ done / 📁 artifacts / ➡️ next") at the same wrapper layer. One edit covers atomic + fused + both IDEs. C is rejected as the *primary* mechanism (hooks can't generate prose) but is viable as a *detector* — see Enforcement below.

### Enforcement (cross-cutting, applies to both features)

Both features are prompt-prose, so a template alone cannot *force* compliance — the `[wiki:gotcha] llm-prose-invokes-python-module-the-wiring-is-the-bug` lesson applies: the defect would live in the prose↔render seam. The codebase already has the right pattern: **`communication_variant`** is a render-required input (missing → Jinja `UndefinedError`) plus a `/hm:health` Layer-1 sub-check that surfaces silent-miss + source↔output drift (CLAUDE.md §"Communication variant policy"). Reuse it: make the locale directive and the end-summary partial render-required, and add `/hm:health` sub-checks asserting the rendered commands actually contain them. This is the closest thing to "강제" available without runtime sandboxing.

## ⚠️ Pitfalls

- **Breaking the "deliverables stay English" invariant.** `research.md.j2:105-106` (and plan/spec/verify) explicitly keep persisted docs English for a public repo. A blanket "always answer in {locale}" that also flips deliverable language is a behavior change with portability cost (CLAUDE.md git policy: public repo, raw URLs). Scope the directive to *live user-facing output*, not artifacts — unless the user decides otherwise (Open Question 1).
- **"Always" vs autoloop suppression.** The start preamble is *deliberately* skipped under `.hm-loop-active` to avoid flooding the loop transcript; the loop relies on machine receipts instead. A literal "always emit summaries" would re-flood every iteration. The end-summary must inherit the same skip logic (Open Question 2).
- **Per-locale file explosion.** Authoring locale variants per agent/stage (24+ files) is the wrong path — it re-incurs the existing ~10-file translation burden many times over. Keep one English-with-`{{ config.locale }}` partial and let the model translate.
- **Marker-syntax footgun.** Any new partial using user-preservation markers must use `@hm:user:NAME` / `@hm:/user:NAME` (slash on close), not `:start:`/`:end:` — see `[[hash-marker-syntax-not-start-end]]`; the `:start:`/`:end:` form is inert and silently drops user content.
- **Pure-text consumers reject frontmatter.** If any locale directive lands in `settings.json` / `hooks.json` / `.cursor/*.mdc`, the consumer's strict parser may reject our metadata (CLAUDE.md §2). Keep the directive in markdown command/agent bodies and CLAUDE.md prose only.
- **Render-required inputs break old harnesses.** Like `communication_variant`, a newly-required render input fails re-render of older sources unless a default/migration is provided (CLAUDE.md checklist #6 schema-gap → default fallback). Default the locale directive to `en` and the summary partial to present.
- **Dogfood vs shipped scope.** Both features must ship in `templates/` (generated harnesses) *and* be re-rendered into this repo's own dogfood `.claude/` for the user to feel the change (the user is experiencing the gap via the dogfood harness).

## ❓ Open Questions

1. **Deliverable-language scope (binding).** Does "always respond in {locale}" cover only live chat + start/end summaries, or also persisted PLAN/RESEARCH/REVIEW/SPEC docs? Current invariant = English deliverables. Recommendation: keep deliverables + code English, locale governs live output + summaries — but this contradicts a literal reading of the user's "항상 이 언어로 답변," so `/hm:plan` must lock it.
2. **Autoloop summary behavior (binding).** Should start/end summaries fire inside autoloop iterations (transcript flood) or stay suppressed like the current preamble (machine receipts cover observability)? Recommendation: suppress in loop, keep machine receipts.
3. **Enforcement strength.** Prose-only instruction, or render-required input + `/hm:health` check (the `communication_variant` precedent)? Recommendation: the latter, to satisfy "강제."
4. **Summary format.** Free-form prose vs a fixed structured banner (emoji-keyed sections). Recommendation: fixed structure — consistency *is* the observability win.
5. **CLAUDE.md placement.** Add the durable locale rule to the 4 existing dual-templates, or factor it into one shared included partial? (Affects translation-duplication count.)

## 📚 Sources

No external sources — internal-authoritative. Key internal references (file:line):

- `src/harness_maker/models.py:25-34,583,742` — `locale` config field, `Locale` enum, free-text + en fallback.
- `src/harness_maker/i18n.py:1-52`, `i18n_messages.py` — runtime error messages only (6 keys), not prompt-injected.
- `src/harness_maker/templates/claude-md/{Side,Production}.{en,ko}.md.j2` — dual hand-authored CLAUDE.md; no output-language instruction.
- `src/harness_maker/templates/stages/research.md.j2:105-106` — interview-only locale + explicit "deliverable stays English."
- `src/harness_maker/synthesize.py:720,770` (config in every context), `:377-386` (`_localized()` dual-template select), `:161-179` / `:463-483` (atomic / fused assembly), `workflow_fuse.py:28-79` (`fuse()`).
- `src/harness_maker/templates/agents/_partials/step_manifest.md.j2:1-21` — shared start preamble.
- `src/harness_maker/templates/commands/hm/atomic_command.md.j2:1`, `workflow_command.md.j2:1`, `templates/codex/stage_skill.md.j2:6`, `workflow_skill.md.j2:6` — wrapper include points.
- `src/harness_maker/templates/agents/_partials/gate0_receipt.md.j2:1-37` — universal machine receipt.
- `src/harness_maker/templates/agents/_partials/communication_{full,reframe,soft}.md.j2` — variant precedent for render-required + `/hm:health` enforcement.
- `src/harness_maker/telemetry.py:1-97` — machine JSONL telemetry (orthogonal to human prose).
- CLAUDE.md §"Communication variant policy", §"무언가를 고치거나 개선하기 전에" checklist #2/#6.

## 🔗 Related Internal Docs

- `[[llm-prose-invokes-python-module-the-wiring-is-the-bug]]` — both features ship as prose; test/verify the rendered-output seam, not just modules.
- `[[hash-marker-syntax-not-start-end]]` — correct user-preservation marker syntax for any new partial.
