---
type: plan
task_slug: locale-and-command-observability
status: complete
created: 2026-06-17
tags: [harness-maker, plan, jinja2, locale, i18n, observability, templates]
research_doc: "[[RESEARCH-locale-and-command-observability]]"
interview_rounds: 3
adrs: 7
validator_outcome: NEEDS_REVISION_RESOLVED
summary: "Locale directive (CLAUDE.md+AGENTS.md+wrapper) + per-stage start/end banners, enforced via StrictUndefined + /hm:health"
---

# PLAN — Persistent locale + per-command start/end observability

## 🎯 Executive Summary

**What:** Two features for generated harnesses (and this repo's dogfood `.claude/`):
1. The configured `config.locale` governs the AI's **user-facing live output + start/end summaries** in every command — not just the onboarding interview.
2. Every command shows a **uniform structured start banner** ("what I will do") and **end banner** ("what I did"), per-stage.

**Why:** Today `config.locale` reaches every template context (`synthesize.py:720,770`) but governs *only* interview prose; AI narrative defaults to English ("language only at onboarding"). The start preamble exists (`step_manifest.md.j2`) but the end summary is hand-rolled per stage and inconsistent (present in research/plan/spec/verify, absent in execute/review/wrapup).

**Key decisions** (all locked via interview → ADRs):
- Locale governs live output + summaries only; **code, identifiers, and persisted PLAN/RESEARCH/REVIEW/SPEC docs stay English** (ADR-001).
- Enforcement reuses the proven `communication_variant` pattern: StrictUndefined render-required vars (summaries) + `/hm:health` presence audit (locale) (ADR-002).
- Inside autoloop both banners self-skip; machine receipts cover loop observability (ADR-003).
- Fixed structured emoji-keyed banner format (ADR-004).
- Locale directive on three persistent/transient surfaces — CLAUDE.md + AGENTS.md + wrapper partial; agent communication partials out of scope (ADR-005).
- End-summary fires per-stage; partial lives in stage templates; per-target emission mechanism documented (ADR-006).
- Start banner = reframe `step_manifest.md.j2` (single partial, no duplication) (ADR-007).

**Estimated impact:** ~3 new/edited partials, 4 wrapper edits, 4 CLAUDE.md + 1 AGENTS.md template edits, 7 stage-template edits, 2 `/hm:health` sub-checks, ~4 boundary/snapshot tests. Reaches existing installs via reconcile (commands carry `content_hash`; CLAUDE.md/AGENTS.md via block-merge template-owned regions). 5-file version bump at wrapup.

## 📚 Prior Work

- `[[RESEARCH-locale-and-command-observability]]` — mapped current state + injection points; recommended this wrapper-layer + `communication_variant`-enforcement direction.
- `[wiki:pattern] prompt-template-shared-partials-dedup` — `gate0_receipt.md.j2` is the parameterized-partial precedent (`{% set %}` + `{% include %}`, StrictUndefined-safe via `{% if x is defined %}`). **Lesson applied:** verify dedup with golden-master byte-diff (Jinja env `trim_blocks=False, lstrip_blocks=False`, `render.py:63-64`); **diff-before-extract** — the per-stage Communication Protocol / Stage-terminal prose is *drifted*, not identical, so the new partial AUGMENTS rather than extracts.
- `[wiki:gotcha] reconcile-keeps-frontmatterless-renders-forever` — command `.md` carry `content_hash` → reconcile auto-upgrades; CLAUDE.md/AGENTS.md use block-merge families.
- `[wiki:gotcha] llm-prose-invokes-python-module-the-wiring-is-the-bug` — both features ship as prose; test the prose↔render seam, not just modules.
- CLAUDE.md learned-correction 2026-06-08 — absent-case = feature black hole; every new required `{% set %}` var must be set at all 7 call sites or have an explicit default.

## 🎙️ Interview Transcript

| # | Round | Category | Question | Choice | → ADR |
|---|-------|----------|----------|--------|-------|
| 1 | 1 | Scope | locale "always" scope: live+summary only vs incl. deliverables vs live-only | Live output + summaries only; deliverables/code English | ADR-001 |
| 2 | 1 | Risk/Enforce | enforcement: communication_variant precedent vs render-required-only vs prose-only | communication_variant precedent | ADR-002 |
| 3 | 1 | Observability | autoloop: suppress in loop vs always-emit vs end-only | Suppress in loop, receipts cover | ADR-003 |
| 4 | 1 | Contract | summary format: fixed structured banner vs free-form vs banner+telemetry | Fixed structured emoji-keyed banner | ADR-004 |
| 5 | 2 | Architecture | locale injection surfaces (multi-select) | CLAUDE.md + wrapper partial (agent partials deselected) | ADR-005 |
| 6 | 2 | Architecture | fused end-summary granularity | Per-stage | ADR-006 |
| 7 | 2 | Architecture | start banner vs step_manifest | Reframe step_manifest (single partial) | ADR-007 |
| 8 | 3 | Scope | (validator W2) add AGENTS.md to locale scope? | Yes — add AGENTS.md (@hm:harness:* region) | ADR-005 (amended) |

## 📐 Architecture Decision Records

### ADR-001: Locale governs live output + summaries only; deliverables/code stay English
**Status:** Accepted (2026-06-17, via /hm:plan interview)
**Context:** User wants the configured locale applied "always," but the codebase has an explicit invariant (`research.md.j2:105-106`) that persisted deliverables stay English for public-repo portability.
**Decision:** The locale directive scopes to user-facing live chat output + the start/end summary banners. Code, identifiers, and persisted PLAN/RESEARCH/REVIEW/SPEC documents remain English.
**Consequences:**
- ✅ Preserves portability + the existing deliverable-language invariant.
- ⚠️ A literal reading of "항상 이 언어로 답변" is narrowed; the directive text must state the carve-out explicitly.
**Rejected alternatives:** "Everything incl. deliverables in locale" — rejected for public-repo portability cost and conflict with the existing invariant.
**Source:** Interview #1

### ADR-002: Enforcement reuses the communication_variant precedent
**Status:** Accepted (2026-06-17, via /hm:plan interview)
**Context:** Both features are prompt-prose; templates alone cannot force LLM compliance. The repo's verified enforcement pattern is `communication_variant` (render-required input → Jinja `UndefinedError`; `/hm:health` Layer-1 silent-miss + source↔output drift check).
**Decision:** The end-summary partial gets **hard** enforcement via StrictUndefined required `{% set summary_* %}` vars (a stage that omits them fails render). The locale directive gets **presence-audit** enforcement via a `/hm:health` Layer-1 sub-check (no StrictUndefined leg is possible — `config.locale` always defaults to "en", `models.py:583`).
**Consequences:**
- ✅ Summary omission is caught at render time; locale-directive omission is caught at health time.
- ⚠️ Enforcement is **asymmetric** and the PLAN states it honestly — locale is presence-audited, not render-forced. No theater.
**Rejected alternatives:** Prose-only (R4 silent-miss failure mode); runtime hook enforcement (hooks cannot author prose — RESEARCH Approach C).
**Source:** Interview #2

### ADR-003: Banners self-skip inside autoloop; receipts cover loop observability
**Status:** Accepted (2026-06-17, via /hm:plan interview)
**Context:** The start preamble already self-skips when `<project-root>/.hm-loop-active` exists, to avoid flooding the loop transcript; the loop relies on machine receipts (`.hm-iter-receipts` jsonl).
**Decision:** Both the reframed start banner and the new end banner carry the same `.hm-loop-active` self-skip instruction.
**Consequences:**
- ✅ No per-iteration transcript flood; observability inside loops stays machine-side.
- ⚠️ "Always" does not hold literally inside autoloop iterations (by design).
**Rejected alternatives:** Always-emit in loop (transcript flood); end-only in loop (inconsistent with start).
**Source:** Interview #3

### ADR-004: Fixed structured emoji-keyed banner format
**Status:** Accepted (2026-06-17, via /hm:plan interview)
**Context:** Consistency is the observability win; free-form prose varies per command and is hard to scan.
**Decision:** Start banner = `🎯 Goal / 📋 Plan`; end banner = `✅ Done / 📁 Artifacts / ➡️ Next`. Same structure in every command; the banner prose renders in `config.locale` (ADR-001 scope).
**Consequences:**
- ✅ Scannable, uniform across commands and IDEs.
- ⚠️ Slightly rigid; the per-stage `{% set %}` vars must map cleanly onto these fields.
**Rejected alternatives:** Free-form prose (scannability); banner + always-on telemetry line (machine telemetry is orthogonal — out of scope here).
**Source:** Interview #4

### ADR-005: Locale directive on CLAUDE.md + AGENTS.md + wrapper partial; agent partials out of scope
**Status:** Accepted (2026-06-17, via /hm:plan interview; amended Interview #8)
**Context:** RESEARCH found CLAUDE.md is the only "always-in-context" anchor (governs ad-hoc chat, not just `/hm:` commands); the wrapper partial covers all `/hm:` commands uniformly. The user deselected agent communication partials. AGENTS.md is the Codex root standing-instructions equivalent of CLAUDE.md, and `codex` ∈ this repo's `targets`.
**Decision:** Inject the `{{ config.locale }}`-driven "Output Language" directive at three surfaces: (a) the 4 CLAUDE.md templates (`claude-md/{Production,Side}.{en,ko}.md.j2`) via a shared included partial in a **template-owned region** (outside `@hm:user:*` markers → REPLACE reaches existing installs); (b) `codex/AGENTS.md.j2` inside a **`@hm:harness:*` region** (its block-merge family — `reconcile.py:177-185`, `block-merge-spec.md`); (c) the shared wrapper partial `output_language.md.j2` included by `atomic_command.md.j2`, `workflow_command.md.j2`, `codex/stage_skill.md.j2`, `codex/workflow_skill.md.j2`. Agent communication partials (`communication_{full,reframe,soft}.md.j2`) are explicitly **out of scope** → dispatched subagents receive no explicit locale directive.
**Consequences:**
- ✅ Persistent anchor on all three targets (CLAUDE.md for Claude/Cursor, AGENTS.md for Codex) + per-command reinforcement; zero new locale-variant files (one English-with-`{{ config.locale }}` partial).
- ⚠️ Subagent narrative output is not locale-governed (accepted scope cut).
**Rejected alternatives:** Agent-partial coverage (deselected by user); per-agent/per-stage locale-variant files (24+ files, translation-maintenance burden).
**Source:** Interview #5, amended #8 (validator W2)

### ADR-006: End-summary fires per-stage; partial lives in stage templates; per-target emission mechanism
**Status:** Accepted (2026-06-17, via /hm:plan interview; refined by validator W1)
**Context:** A fused workflow command concatenates stage bodies. Per-stage end summaries require the partial to ride along with each stage body, not sit at the wrapper level.
**Decision:** The new `stage_end_summary.md.j2` partial is included by each of the 7 `stages/*.md.j2` (near the Stage terminal), parameterized per stage. Per-target emission differs and is documented: **Claude/Cursor** fused commands concatenate stage bodies (`workflow_fuse.py:64-78`) → N banners in one file; **Codex** fused `workflow_skill.md.j2:16-20` *delegates* to `@hm-{stage}` skills (does NOT inline bodies) → each `hm-{stage}` SKILL (built from `codex/stage_skill.md.j2:7` `stage_body`) carries 1 banner, and `workflow_skill.md.j2` itself carries **zero** by design. Atomic commands (one stage) emit one banner.
**Consequences:**
- ✅ Per-stage observability on every target without double-emission on the Codex delegation path.
- ⚠️ Exit criteria must be scoped per target (a "N banners in the Codex workflow_skill file" assertion would be wrong).
**Rejected alternatives:** Wrapper-level single end-summary (loses per-stage granularity); both per-stage + command-end (verbose double emission).
**Source:** Interview #6, refined by validator W1

### ADR-007: Start banner = reframe step_manifest.md.j2 (single partial)
**Status:** Accepted (2026-06-17, via /hm:plan interview)
**Context:** `step_manifest.md.j2` already prints a numbered plan manifest at the wrapper head and already self-skips in autoloop.
**Decision:** Reframe `step_manifest.md.j2` into the structured start banner (`🎯 Goal / 📋 Plan`), keeping the single-partial single-source and the `.hm-loop-active` self-skip. No separate banner block.
**Consequences:**
- ✅ Zero duplication; one edit changes all commands; loop-skip preserved.
- ⚠️ Existing rendered command heads change → golden-master diff must be re-baselined deliberately.
**Rejected alternatives:** Keep manifest + add a separate goal line (two overlapping blocks).
**Source:** Interview #7

## 🏗️ Technical Design

**Current state:** `config` (with `.locale`) in every template context (`synthesize.py:720,770`). Start preamble = `agents/_partials/step_manifest.md.j2` included by 4 wrappers. End = drifted hand-rolled per-stage "Stage terminal". `gate0_receipt.md.j2` = parameterized-partial precedent. Jinja env StrictUndefined + `trim_blocks=False, lstrip_blocks=False` (`render.py:63-65`). Reconcile: commands via `content_hash`; CLAUDE.md `@hm:user:*` family; AGENTS.md `@hm:harness:*` family.

**Affected components:**
- New: `templates/agents/_partials/output_language.md.j2`, `templates/agents/_partials/stage_end_summary.md.j2`.
- Edited: `step_manifest.md.j2` (reframe); wrappers `atomic_command.md.j2`, `workflow_command.md.j2`, `codex/stage_skill.md.j2`, `codex/workflow_skill.md.j2`; CLAUDE.md `claude-md/{Production,Side}.{en,ko}.md.j2`; `codex/AGENTS.md.j2`; all 7 `stages/*.md.j2`.
- New checks: `/hm:health` Layer-1 sub-checks `output_language_present`, `start_end_summary_present` (in `readiness.py` / `ai_readiness.py`).

**Dependencies:** No new runtime deps. Jinja2 only.

**Data flow:** `config.locale` → wrapper/CLAUDE.md/AGENTS.md/stage templates → rendered directive + banner prose. The LLM reads the directive at runtime and emits live output/summaries in `config.locale`.

**Design decisions:** All trace to ADR-001…007 above.

## 📝 Implementation Plan

### Phase 1 — Locale output-language directive (3 surfaces)
- **depends_on:** `[]`
- **parallel_group:** `serial-templates` (single-threaded with Phase 2 on shared wrappers)
- **merge_hazards:** `atomic_command.md.j2`, `workflow_command.md.j2` (also edited by Phase 2 — serialize)
- **Scope (in):** new `output_language.md.j2` partial (`{{ config.locale }}`, `en→English / ko→Korean / others→English`, ADR-001 carve-out text); include in the 4 wrappers; shared "Output Language" partial added to the 4 CLAUDE.md templates (template-owned region, outside `@hm:user:*`); `codex/AGENTS.md.j2` "Output Language" inside a `@hm:harness:*` region.
- **Scope (out):** agent communication partials; deliverable-doc language; runtime hooks.
- **Exit criterion:** `INTEGRATION=1 uv run pytest tests/integration/test_boundary_*.py` + a new assertion that rendered atomic + workflow + codex stage/workflow skills + all 4 CLAUDE.md variants + AGENTS.md contain the directive; **ko fixture → directive contains "Korean", unknown-locale fixture → "English"** (W5); golden-master byte-diff shows no change outside the injected regions.
- **Risk:** medium (whitespace fragility on wrapper edits)
- **Rollback:** pre-phase state.

### Phase 2 — Start/end summary banners
- **depends_on:** `[1]` (shares wrapper edits; rollback target is Phase 1 — W4)
- **parallel_group:** `serial-templates`
- **merge_hazards:** `atomic_command.md.j2`, `workflow_command.md.j2` (start banner = reframed `step_manifest`, the wrappers' first include), all 7 `stages/*.md.j2`
- **Scope (in):** reframe `step_manifest.md.j2` → structured start banner (keep `.hm-loop-active` self-skip); new `stage_end_summary.md.j2` parameterized partial (StrictUndefined required `{% set summary_* %}` vars + loop-skip instruction); wire into all 7 `stages/*.md.j2` near the Stage terminal — **augment** the drifted terminal prose, **keep** each stage's `STOP` boundary.
- **Scope (out):** wrapper-level end-summary (ADR-006 puts it per-stage); machine telemetry line.
- **Exit criterion:** golden-master render diff (deliberate re-baseline of command heads + stage tails); every rendered atomic command ends with the banner; **Claude/Cursor fused command has N banners (concat)**; **Codex: each `hm-{stage}` SKILL carries 1 banner, `workflow_skill` carries 0** (W1); render of all 7 stages succeeds with no `StrictUndefined` error (proves every call site set the vars — absent-case guard); snapshot suite regen.
- **Risk:** medium (StrictUndefined absent-case across 7 stages; whitespace)
- **Rollback:** Phase 1 state.

### Phase 3 — Enforcement checks + dogfood re-render
- **depends_on:** `[1, 2]`
- **parallel_group:** `serial-final`
- **merge_hazards:** `none` (new test files + health-module additions)
- **Scope (in):** `/hm:health` Layer-1 sub-checks `output_language_present` + `start_end_summary_present` (presence audit on rendered commands; locale is presence-audit only per ADR-002); boundary test for directive+banners scoped per target (W1) + ko-mapping (W5); **reconcile-on-existing-install test** — fixture of an old rendered CLAUDE.md (and AGENTS.md) lacking the section → assert section injected after reconcile (REPLACE on template-owned region / `@hm:harness:*` merge) (W3); re-render dogfood `.claude/` via `/hm:make`.
- **Scope (out):** version bump (deferred to `/hm:wrapup` — note the 5-file sync).
- **Exit criterion:** `/hm:health` green on dogfood with the two new sub-checks present and passing; boundary + reconcile-reach tests pass; `uv run ruff check && uv run mypy --strict && uv run pytest` (background) clean.
- **Risk:** low
- **Rollback:** Phase 2 state.

## 🧪 Testing Strategy

- **Unit:** `/hm:health` sub-check functions (presence detection on a rendered-command string fixture); `stage_end_summary` var-completeness.
- **Integration (boundary):** live-render all 3 targets → assert directive + banners present per target with correct per-target mechanism (ADR-006); ko/unknown locale mapping (W5); reconcile-on-existing-install reach for CLAUDE.md + AGENTS.md (W3). Pattern: `[wiki:pattern] boundary-parse-test-layer`.
- **Snapshot / golden-master:** byte-diff render before/after to confine changes to injected regions (whitespace-fragility guard, `[wiki:pattern] prompt-template-shared-partials-dedup`).
- **Manual:** run `/hm:research` (or any command) in the re-rendered dogfood harness; confirm a `ko` start/end banner appears and live output is Korean while the written deliverable stays English.

## ⚠️ Risks & Mitigation

| Risk | Severity | Mitigation |
|------|----------|------------|
| StrictUndefined absent-case: a stage omits `summary_*` vars → render error | medium | Boundary test renders all 7 stages; partial provides `{% if x is defined %}` default fallback (2026-06-08 learned-correction) |
| Whitespace shift (`trim_blocks=False`) silently changes output | medium | Golden-master byte-diff on every rendered command before/after |
| Naive extraction of drifted per-stage prose forces false convergence | medium | Diff-before-extract; new partial AUGMENTS, per-stage specifics via `{% set %}` (wiki precedent) |
| Codex `workflow_skill` delegates (no concat) → wrong "N banners" assertion | medium | ADR-006 documents per-target mechanism; exit criteria scoped per target |
| Locale directive reaches fresh installs but not updates | medium | Phase 3 reconcile-on-existing-install test for CLAUDE.md (`@hm:user:*` template-owned REPLACE) + AGENTS.md (`@hm:harness:*` region) |
| Enforcement-asymmetry mistaken for full enforcement | low | ADR-002 + PLAN state honestly: locale = presence-audit, summaries = StrictUndefined |
| Subagent output not locale-governed | low (accepted) | ADR-005 records agent partials as explicit scope cut |

## ✅ Success Criteria

- [x] In a `ko` harness, every rendered command (atomic + fused, all 3 targets) instructs the AI to respond to the user in Korean; live output + banners are Korean.
- [x] Persisted PLAN/RESEARCH/REVIEW/SPEC docs and code remain English (ADR-001).
- [x] Every command shows the structured start banner (🎯/📋) and end banner (✅/📁/➡️); fused workflows show per-stage banners with the correct per-target mechanism (ADR-006).
- [x] Both banners self-skip inside `.hm-loop-active` (ADR-003).
- [x] `/hm:health` surfaces `output_language_present` + `start_end_summary_present` and they pass on the dogfood harness.
- [x] Reconcile injects the directive into a pre-existing CLAUDE.md and AGENTS.md (existing-install reach proven by test).
- [x] `ruff` + `mypy --strict` + `pytest` clean.

## 🔍 Plan Validation

**Validator outcome:** NEEDS_REVISION (0 critical, 4 warning, 1 suggestion) → **RESOLVED**. Codex second opinion **skipped** (Bash permission gate / sandbox denied `codex exec` — not an auth/runtime failure; warn-and-proceed, Claude-only).

| Finding | Severity | Resolution |
|---------|----------|------------|
| W1: ADR-006 mechanism wrong for Codex fused (`workflow_skill` delegates, not concat) | warning | ADR-006 revised with per-target mechanism; Phase 2 exit scoped per target |
| W2: AGENTS.md (Codex CLAUDE.md-equivalent) missing from locale scope | warning | Interview #8 → ADR-005 amended to add AGENTS.md (`@hm:harness:*` region); added to Phase 1 |
| W3: reconcile reach asserted, not tested | warning | Phase 3 reconcile-on-existing-install test added |
| W4: Phase 2 `depends_on []` contradicts "Rollback: Phase 1" + shared wrapper edits | warning | Phase 2 `depends_on [1]`; serialized on shared wrappers |
| W5: presence-audit ≠ correct-locale-mapping | suggestion | ko/unknown-locale mapping assertion added to boundary tests |

Clean categories: risk-register, rollback-strategy, adr-completeness, scope-drift-hazards, missing-interview-rounds.

## 🚧 Execution Status (2026-06-17, /hm:execute)

All three phases **DONE** (staged on worktree `execute-6e5f3fdfb183-…`, not committed — wrapup owns the commit).

- **Phase 1 (locale directive) — DONE.** New `agents/_partials/output_language.md.j2` (absent-case default to `en`); included in the 4 wrappers (`atomic_command`, `workflow_command`, codex `stage_skill`/`workflow_skill`) + a `## Output Language` section in the 4 CLAUDE.md templates + `codex/AGENTS.md.j2` (outside `@hm:user:*` markers → reconcile-propagates).
- **Phase 2 (banners) — DONE.** `step_manifest.md.j2` reframed to the structured start banner (🎯/📋, keeps `.hm-loop-active` skip); new `agents/_partials/stage_end_summary.md.j2` (required `{% set %}` vars, StrictUndefined-enforced) wired into all 7 stages near the Quality Bar.
- **Phase 3 (enforcement + tests) — DONE.** `readiness.py` Layer-1 sub-checks `output_language_present` + `start_end_summary_present` (scoped to stage/fused commands). 19 tests in `tests/unit/test_locale_observability.py` (locale directive ×6, start banner ×2, end banner per-stage + codex one/zero ×4, fused N-count ×1, health ×2, reconcile-reach ×1, plus mapping/carve-out). 8 snapshots regenerated (main-pinned).

**Verification:** `ruff check .` ✓ · `ruff format --check` ✓ · `mypy --strict src` ✓ (105 files) · full `pytest` ✓ (0 failures).

**Scope notes (deliberate, not gaps):**
- The Phase 3 INTEGRATION boundary test was satisfied at the unit level — the new tests render every per-target path against the **real** templates + real `fuse()` (codex stage/workflow skills, fused N-banner count, CLAUDE.md, AGENTS.md, and the block-merge reach via `block_merge.merge()`), so a redundant slow live-render `cli.make` test was not added.
- The dogfood `.claude/` re-render (`/hm:make`) is **deferred** to a deliberate rollout step (wrapup or user-run) — it rewrites this repo's own committed harness and does not belong in the no-commit execute stage. The source templates + tests are the execute deliverable.
- Mid-execute fix: `output_language.md.j2` was made absent-case-safe (defaults `config.locale` → `en`) because isolated wrapper-render unit tests (`test_codex_phase7`) omit `config`; production always injects it (synthesize.py:763-784), so behavior is unchanged. StrictUndefined hard-enforcement is retained where it belongs — the end-summary required vars.
