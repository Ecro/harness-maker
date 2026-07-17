---
type: plan
task_slug: human-bottleneck-auto-advance
status: complete
created: 2026-06-20
tags: [harness-maker, plan, autonomy, auto-advance, human-in-the-loop, hooks]
research_doc: "[[RESEARCH-human-bottleneck-auto-advance]]"
interview_rounds: 2
adrs: 9
validator_outcome: MAJOR_REVISION_RESOLVED
status_detail: "FEATURE COMPLETE 2026-06-21 (P0-P8 code+docs+e2e); ONLY the 5-file version bump is deferred to a coordinated 0.31.0 release (worktree-concurrency now also landed) — see Execution Log"
summary: "Pipeline auto-advance via prompt-driven runtime chaining + Stop-hook backstop; enforcement & caps land before live auto-advance"
---

# PLAN — Pipeline auto-advance (autonomy axis), Claude Code v1

## 🎯 Executive Summary

**What:** Add an `autonomy` axis to harness-maker so the 5-7 stage workflow auto-advances past inter-stage STOP boundaries **whenever no mandatory human confirmation is pending**, turning the human from a per-stage gate into an exception handler. Claude Code target first.

**Why:** Every atomic stage ends with a hard "STOP — do not proceed" boundary, forcing the user to type the next `/hm:` command. RESEARCH established this is not only a velocity cost but a *safety* cost (automation-bias: a STOP after every stage trains rubber-stamping, degrading the one gate that matters — the irreversible merge/push). The fix: auto-advance the two-way-door boundaries, keep a human only at the few one-way doors.

**Key decisions (ADRs):**
- Runtime chaining, NOT pre-fused (ADR-001) — but its feasibility is **unproven** and gated behind a go/no-go spike (ADR-008).
- Static enum `autonomy.level ∈ {gated, auto_safe, full}`, default `gated`, absent-case → `gated` (ADR-002).
- Always-on, **non-overridable** never-auto deny-list in `settings.json` deny + PreToolUse hook (ADR-003).
- Prompt-driven decision locus + reuse `loop_gate` Stop-hook as backstop (ADR-005); mandatory-gate predicates default to STOP on the absent case.
- Enforcement (P4) and runaway caps (P5) land **before** any phase that can fire live auto-advance (P6) — the validator's lead critical fix.

**Estimated impact:** ~9 phases. New schema (`models.py`), one new/extended hook, one new CLI subcommand, edits to all 7 stage terminals + the shared partial, a new observability ledger, settings.json deny baseline. Primary risk concentrated in P0 (mechanism feasibility) and P6 (template scope across 7 stages).

## 📚 Prior Work

- **RESEARCH-human-bottleneck-auto-advance.md** — two-axis model (reversibility × uncertainty), full human-bottleneck map, cross-vendor convergence (Claude auto-mode / Cursor Run Modes / Windsurf / AutoGen), the never-auto incident set (PocketOS, Cursor Plan Mode), and the worktree-reversibility keystone.
- `[wiki:pattern] loop-mechanical-receipt-gate` (memory) — the `iter_receipts` schema + `.hm-loop-active` marker + Stop-hook `loop_gate` pattern this plan reuses. **Critical constraint surfaced:** `iter_receipts.Verdict` reserves `"skipped"`; the new ledger MUST NOT reuse it (ADR-009).
- `[wiki:gotcha] worktree-finalize-conflicts-with-parallel-main-edits` — the wrapup merge is the one irreversible door; kept gated.
- CLAUDE.md §보안/권한 — agent-frontmatter `permissions` is silently ignored → enforcement MUST be `settings.json` + PreToolUse hook (drives ADR-003).
- CLAUDE.md checkpoint 6 + memory `[absent-case = feature black hole]` — every persisted key round-trips through `answers_from_harness_yaml`; absent-case must be tested explicitly.

## 🎙️ Interview Transcript

| # | Topic | Category | Question | Choice | → ADR |
|---|-------|----------|----------|--------|-------|
| R1.1 | Chaining mechanism | Architecture | fused command vs runtime chaining vs both | **Session-level runtime chaining** | ADR-001 |
| R1.2 | Autonomy engine | Architecture | static enum vs LLM ambiguity gate vs enum-then-gate | **Static enum gated/auto_safe/full** | ADR-002 |
| R1.3 | never-auto enforcement depth | Risk | settings+hook always-on vs design-only+ledger | **settings.json deny + PreToolUse hook always-on** | ADR-003 |
| R1.4 | v1 target scope | Scope | Claude first vs all-three | **Claude Code first** | ADR-004 |
| R2.1 | Decision locus | Architecture | prompt-driven+backstop vs hook-driven state file | **Prompt-driven + Stop-hook backstop** | ADR-005 |
| R2.2 | Chain definition / "ask at start" | Architecture | session-start picker+yaml default vs yaml-fixed+toggle | **Session-start picker (once) + harness.yaml default** | ADR-006 |
| R2.3 | Runaway guards | Risk | loop-grade step/time cap (token deferred) vs +token budget vs none | **Reuse loop step/time cap; token budget deferred** | ADR-007 |

5-term inequality gate exited after R2: remaining slots (precedence rule, marker schema, mandatory-gate list, never-auto contents, default pipeline membership) reached confidence ≥ τ from RESEARCH + existing code patterns and the plan-validator pass — no further high-EIG user questions. Defaults recorded as ADR-006/008/009 below.

## 📐 Architecture Decision Records

### ADR-001: Runtime chaining (not pre-fused)
**Status:** Accepted (2026-06-20, via /hm:plan interview R1.1)
**Context:** The user's bottleneck is typing the next `/hm:` command after each atomic stage's STOP. Two ways to remove it: a single pre-fused mega-command, or making atomic stages auto-re-invoke the next stage at runtime.
**Decision:** Session-level runtime chaining — at a stage's terminal, when autonomy permits and no mandatory gate is pending, the stage invokes the next pipeline stage at runtime.
**Consequences:**
- ✅ Preserves the atomic-stage mental model; user keeps invoking single stages but the session continues automatically.
- ⚠️ The runtime invocation mechanism is unproven in this codebase (loop uses fused concatenation, not runtime Skill invocation) → gated behind ADR-008's go/no-go spike.
**Rejected alternatives:** Pre-fused mega-command — rejected by the user; would change the invocation model and is opaque per-stage.
**Source:** Interview R1.1

### ADR-002: Static enum autonomy engine
**Status:** Accepted (2026-06-20, R1.2)
**Context:** Need a legible control for "how far does the workflow auto-advance."
**Decision:** `harness.yaml.autonomy.level ∈ {gated, auto_safe, full}`. Default `gated`. Old yaml without the key → `gated` (absent-case). `auto_safe` auto-advances two-way boundaries but ALWAYS stops at: plan architecture interview, review `CHANGES_REQUESTED`, wrapup merge/push. `full` ≈ existing `/hm:loop` autonomy.
**Consequences:**
- ✅ Deterministic, predictable, testable; 3 memorable levels (Windsurf Off/Auto/Turbo legibility).
- ⚠️ Coarser than an LLM ambiguity gate (deferred per RESEARCH Approach 2 to an opt-in later tier).
**Rejected alternatives:** Per-turn LLM ambiguity gate as the v1 engine — deferred (LLM confidence miscalibration risk, arXiv 2502.13069).
**Source:** Interview R1.2

### ADR-003: Non-overridable never-auto deny-list, enforced by a marker-gated PreToolUse hook
**Status:** Accepted (2026-06-20, R1.3; refined by validator #7/#10/#11; **mechanism refined 2026-06-20 P4-impl — user-confirmed**)
**Context:** Prose rules do not stop tool calls (PocketOS, Cursor Plan Mode incidents); agent-frontmatter `permissions` is silently ignored by Claude Code.
**Decision:** A code/template-fixed never-auto list (git push / force-push, git reset --hard, git stash drop|clear, `rm` outside `.worktrees/`, publish/release/deploy, edits to `.claude/settings*`/permission files) is enforced by a **`autopilot_guard` PreToolUse hook that fires ONLY while the `.hm-autopilot` marker is active** (reuses `autopilot.active_marker`). The list is **non-overridable** (user config may only ADD via `autonomy.extra_deny`, never subtract).
> **P4-impl refinement (user-confirmed):** the original "always-on `settings.json` deny independent of autonomy.level" reading conflated *non-overridable* with *always-firing*. A static session-wide `settings.json` deny would block the user's own manual `git push`/`rm` even with autopilot OFF — a footgun (the maintainer manually `git push`es every wrapup). Since never-auto exists *because auto-advance removes the human* (RESEARCH risk lens), it must fire only when autopilot is active. The hook reads the runtime marker (which static settings.json cannot); the list stays code-fixed. Net: autopilot OFF (default/gated) → hook is a no-op → manual workflows unchanged; autopilot ON → never-auto blocked. The hook also covers path-predicates (`rm` outside `.worktrees/`) settings-deny cannot express.
**Consequences:**
- ✅ Survives prompt injection / a hostile or stale yaml; an active autopilot can never reach an irreversible op; **zero behavior change for solo/manual users** (autopilot off).
- ⚠️ Patterns must be surgical (no blanket `Bash(python:*)` ban — would block the harness's own `python -m harness_maker` self-calls). Hook is Claude-Code-only (ADR-004); Cursor/Codex parity deferred.
**Rejected alternatives:** static always-on `settings.json` deny — rejected (breaks manual workflows); design-only (rely on gated merge) — rejected R1.3; agent-frontmatter permissions — non-functional per CLAUDE.md.
**Source:** Interview R1.3 + validator #7/#10/#11 + P4-impl mechanism refinement (user-confirmed 2026-06-20)

### ADR-004: Claude Code first; Cursor/Codex stay gated/advisory
**Status:** Accepted (2026-06-20, R1.4; refined by validator #17)
**Context:** The Stop-hook backstop and `defaultMode` are Claude-Code-specific; Cursor's `loop_gate` path is advisory-only (always exit 0); agents/skills/commands are single-source across IDEs (leak risk).
**Decision:** Implement live auto-advance for Claude Code only. Cursor/Codex rendered templates MUST remain gated/advisory — no Skill auto-invoke branch reaches them — proven by a cross-IDE negative snapshot.
**Consequences:**
- ✅ Dogfoddable on the maintainer's own IDE first; no false "guarded" claims on IDEs without the backstop.
- ⚠️ Cursor/Codex parity is a deferred follow-up.
**Rejected alternatives:** All-three in v1 — rejected R1.4 (3× design/test burden, divergent enforcement paths).
**Source:** Interview R1.4 + validator #17

### ADR-005: Prompt-driven decision locus + Stop-hook backstop; absent-case = STOP
**Status:** Accepted (2026-06-20, R2.1; refined by validator #4)
**Context:** "Advance vs stop" needs a decision point. Either each stage's prompt decides (LLM judgment) or a hook computes it from a state file.
**Decision:** Prompt-driven — each stage's terminal block reads the autopilot marker and the stage LLM judges whether a mandatory gate is pending; if none, it invokes the next pipeline stage. The existing `loop_gate --mode stop-hook` (returns `decision:block` + exit 2 while marker present, `stop_hook_active` guard) is reused as a backstop preventing premature termination. **Mandatory-gate predicates default to STOP on any absent/ambiguous signal** (a review that failed to emit its status string must be read as "blocked," never "clear").
**Consequences:**
- ✅ Fits CLAUDE.md "LLM 판단 우선"; minimal new infra; backstop catches the LLM "forgetting."
- ⚠️ Prompt-judged detection can mis-detect → mitigated by absent-case=STOP + per-gate fixtures (P6).
**Rejected alternatives:** Hook-driven state file — rejected R2.1 (hook would encode workflow logic under a 5s timeout + need state coordination).
**Source:** Interview R2.1 + validator #4

### ADR-006: Session marker schema, lifecycle & precedence; default pipeline membership
**Status:** Accepted (2026-06-20, R2.2; refined by validator #1/#9/#13)
**Context:** Three control surfaces (config / ask-once / on-demand) and the question of which stages the pipeline includes.
**Decision:**
- **Two persistence mechanisms, three logical surfaces.** The session-start AskUserQuestion answer is **persisted into the marker** — so precedence `session-marker > session-start-answer > harness.yaml` collapses to: marker (carries the session answer) wins, else `harness.yaml.autonomy` default.
- **Marker `.hm-autopilot`** is JSON: `{session_uuid, level, pipeline: [stages], created_at}`. Atomic write (`atomic_write`); a `read-API` (`autopilot.load()/clear()`). **Any invalid / corrupt / stale / uuid-mismatch / pipeline-complete state resolves to OFF (gated)** and clears the marker (mirrors worktree layer-3 session-UUID defense). Gitignored via `_HARNESS_CHURN_PREFIXES`.
- **Default pipeline** = `[research, spec, plan, execute, review, verify, wrapup]`. `verify` is INCLUDED (it is a safety check, not a human confirmation — skipping it before an auto wrapup is the dangerous case). User overrides the sequence in `harness.yaml.autonomy.pipeline`.
**Consequences:**
- ✅ Eliminates the "3 surfaces / 2 mechanisms" ambiguity; corrupt/stale markers fail safe.
- ⚠️ Default pipeline is a defensible default (not a user round); user must opt out of `verify` explicitly.
**Rejected alternatives:** yaml-fixed pipeline + bare on/off toggle — rejected R2.2 (no per-session pipeline choice).
**Source:** Interview R2.2 + validator #1/#9/#13

### ADR-007: Runaway caps land before live auto-advance
**Status:** Accepted (2026-06-20, R2.3; refined by validator #6)
**Context:** A chained interactive session currently inherits NO iteration/time cap (those exist only in `autoloop_driver` for `/hm:loop`).
**Decision:** Reuse `autoloop_driver`-style `step_cap` + `time_cap_min` for the chained session; kill switch = marker removal (+ forced worktree cleanup if engaged). Token/cost budget deferred to a follow-up. **The caps phase (P5) is a dependency of the live-auto-advance phase (P6)** — auto-advance is never rendered live before caps exist.
**Consequences:**
- ✅ No uncapped runaway window, even during dogfooding.
- ⚠️ No token/cost ceiling in v1 (RESEARCH pitfall #5 — accepted risk, follow-up tracked).
**Rejected alternatives:** Token budget in v1 — deferred R2.3; no caps — rejected (runaway risk).
**Source:** Interview R2.3 + validator #6

### ADR-008: Mechanism feasibility is a go/no-go gate (NEW — validator finding #3/#5)
**Status:** Accepted (2026-06-20, validator-driven)
**Context:** Runtime chaining (ADR-001/005) is unproven: (a) Skill-tool mid-turn invocation of a `/hm:` stage is unverified; (b) the pivot "Stop-hook-only re-injection" is NOT free — `loop_gate.py` currently emits only a STATIC `reason` and has no next-command injection mechanism.
**Decision:** P0 is a binary go/no-go spike evaluating **Mechanism A** (stage invokes next stage via the Skill tool mid-turn) and, only if A fails, **Mechanism B** (extend `loop_gate` to emit a dynamic `reason` carrying the next-stage command). P3/P6 are gated on P0. If BOTH fail, **HALT and escalate to the user** — runtime chaining is infeasible and the only remaining path is the fused fallback the user declined in R1.1, which requires a new decision. The spike result is recorded as an implementation note and, if A works, converted into the P8 INTEGRATION e2e (not discarded).
**Consequences:**
- ✅ No downstream phase builds on an unproven mechanism; the pivot is explicitly scoped, not assumed-free.
- ⚠️ A failed spike blocks the feature pending a user re-decision.
**Rejected alternatives:** Treat the pivot as a proven fallback — refuted by `loop_gate.py:60-65` (static reason only).
**Source:** validator findings #3, #5, #18

### ADR-009: Ledger event vocabulary disjoint from iter_receipts.Verdict (NEW — validator #2/#14)
**Status:** Accepted (2026-06-20, validator-driven)
**Context:** `iter_receipts.py` reserves `"skipped"` as a verdict literal that Gate 0 treats as non-pass; "skipped" is the natural word for a not-advanced event.
**Decision:** The auto-advance ledger (`observability/auto-advance.jsonl`) uses a disjoint event enum: `advanced` (inter-stage STOP bypassed), `gate_blocked` (mandatory gate held the chain), `halted_cap` (runaway cap fired). `"skipped"` is FORBIDDEN. A regression test asserts the ledger never emits any `iter_receipts.Verdict` literal.
**Consequences:**
- ✅ No false Gate 0 / `/hm:health` non-pass classification from benign auto-advance events.
- ⚠️ Two vocabularies to keep mentally distinct (documented in the ledger module docstring).
**Rejected alternatives:** Reuse `skipped` — refuted by `iter_receipts.py:36-38` + Gate 0 `:292-303`.
**Source:** validator findings #2, #14

## 🏗️ Technical Design

**Current State:** Atomic stages each end with a prose "Stage terminal" STOP boundary (`research.md.j2:275`, `spec.md.j2:331`, `plan.md.j2:449`, `execute.md.j2:386`, `review.md.j2:495`, `verify.md.j2:230`, `wrapup.md.j2:415`) AND a `summary_next` line in the shared `_partials/stage_end_summary.md.j2` (which already self-skips under `.hm-loop-active`). Fused workflows chain stages with no inter-stage STOP; `/hm:loop` runs autonomously via the `loop_gate` Stop hook. No `autonomy` axis exists in `HarnessConfig`.

**Affected Components:**
- `src/harness_maker/models.py` — new `AutonomyConfig` + `HarnessConfig.autonomy` + `InterviewAnswers` mirror.
- `src/harness_maker/interview.py` — `answers_from_harness_yaml` reverse-mapper.
- `src/harness_maker/hooks/loop_gate.py` (or new `autoadvance_gate.py`) — marker-aware termination block.
- `src/harness_maker/autopilot.py` (NEW) — marker schema, atomic read/write/clear, precedence resolver, fail-safe validation.
- `src/harness_maker/cli.py` — `autopilot` write/clear subcommand.
- `src/harness_maker/render.py` — settings.json deny baseline via existing `_merge_permissions`; never-auto PreToolUse hook render.
- `src/harness_maker/templates/agents/_partials/stage_end_summary.md.j2` + all 7 `templates/stages/*.md.j2` terminals — conditional advance branch.
- `src/harness_maker/templates/.../settings*.json.j2`, `hooks.json.j2` — deny baseline + guard hook.
- `src/harness_maker/observability` + `templates/commands/hm/health.md.j2` — new ledger + smoke-test.
- `worktree._HARNESS_CHURN_PREFIXES` — add `.hm-autopilot`.

**Data Flow (auto_safe):** session-start eligible stage runs → no marker → AskUserQuestion picks pipeline → write `.hm-autopilot` → stage completes → terminal block reads marker (uuid match) + LLM evaluates mandatory-gate predicate → if clear, invoke next pipeline stage via Skill; if a gate is pending, STOP + write `gate_blocked` ledger event → Stop-hook backstop blocks premature termination while marker present + pipeline incomplete → caps abort via `halted_cap` if step/time exceeded → final stage clears marker.

**API Changes:** none external. New CLI: `harness-maker autopilot {on --pipeline … | off}`. New harness.yaml block `autonomy: {level, pipeline, time_cap_min, step_cap, extra_deny}`.

## 📝 Implementation Plan

### Phase 0 — Mechanism feasibility go/no-go spike
- `depends_on`: []
- `parallel_group`: serial-spike
- `merge_hazards`: none (throwaway / note only)
- Scope (in): a throwaway Claude Code session proving Mechanism A (stage invokes next `/hm:` stage via Skill tool mid-turn) or, if A fails, designing Mechanism B (`loop_gate` dynamic-reason next-command injection). (out): production code.
- Exit criterion: **binary** — a documented session shows `research → spec` auto-chaining under one mechanism, OR a recorded HALT escalation if both fail. Result captured as an implementation note in this PLAN.
- Risk: high
- Rollback: n/a (spike)

### Phase 1 — AutonomyConfig schema + reverse-mapper
- `depends_on`: []
- `parallel_group`: serial-spike (parallel with P0)
- `merge_hazards`: `models.py` (shared with no other phase in this group)
- Scope (in): `AutonomyConfig {level: Literal default gated, pipeline: list default 7-stage, time_cap_min: int, step_cap: int, extra_deny: list}`; `HarnessConfig.autonomy` + `InterviewAnswers` mirror; `answers_from_harness_yaml` round-trip. never-auto BASELINE is NOT a config field (code-fixed). (out): rendering, hook logic.
- Exit criterion: `uv run mypy --strict` clean AND `uv run pytest` covering: absent-key→gated, partial-config→gated-defaults, invalid-enum (`level: yolo`)→reject-or-gated, default-pipeline preserved on round-trip, full round-trip through `answers_from_harness_yaml` (write→read→write identical).
- Risk: medium
- Rollback: revert models.py/interview.py

### Phase 2 — Session marker, state contract, CLI, gitignore
- `depends_on`: [1]
- `parallel_group`: serial-2
- `merge_hazards`: `cli.py`, `worktree.py` (_HARNESS_CHURN_PREFIXES)
- Scope (in): `autopilot.py` — marker JSON schema, `atomic_write`, `load()/clear()`, precedence resolver, fail-safe validation (corrupt/stale/uuid-mismatch/complete → gated + clear); CLI `autopilot on/off`; add `.hm-autopilot` to churn prefixes. (out): hook block, templates.
- Exit criterion: `pytest` — CLI write/clear test; marker test matrix {valid-match→active, uuid-mismatch→gated, corrupt-json→gated, stale→gated, concurrent-second-session→gated} all resolve safe; idempotent-gitignore append test.
- Risk: medium
- Rollback: revert autopilot.py/cli.py

### Phase 3 — Stop-hook backstop (+ Mechanism-B injection if P0 selected it)
- `depends_on`: [0, 2]
- `parallel_group`: serial-3
- `merge_hazards`: `hooks/loop_gate.py`
- Scope (in): block termination while `.hm-autopilot` present AND session_uuid matches AND pipeline incomplete; honor `stop_hook_active`; corrupt marker → no-block + stderr diagnostic. If P0 chose Mechanism B, the dynamic next-command `reason` injection lands here. (out): the prompt-side advance branch.
- Exit criterion: `pytest` hook unit tests — block on match; no-block on {absent, uuid-mismatch, complete, corrupt}; `stop_hook_active` short-circuits; (if B) reason carries the correct next stage.
- Risk: medium
- Rollback: revert loop_gate.py

### Phase 4 — never-auto enforcement (always-on, non-overridable)
- `depends_on`: [1]
- `parallel_group`: serial-4
- `merge_hazards`: `render.py`, `settings*.json.j2`, `hooks.json.j2` (shares render path with P6/P7 — serialize)
- Scope (in): code-fixed baseline deny rendered into settings.json deny via `render._merge_permissions` (preserve user settings, idempotent, no-dup); PreToolUse guard hook for path-predicates (rm outside `.worktrees/`); surgical patterns only. User `extra_deny` additive-only. (out): autonomy enum behavior.
- Exit criterion: render snapshot shows deny+hook; `pytest` — one block-test PER deny class incl disguised forms (`push --force-with-lease`, `reset --hard HEAD`, `rm -rf ../x`, release/publish/deploy, `.claude/settings*` edit) + negative (`uv run`, `pytest` allowed); settings-preservation + idempotency + no-dup test; "yaml cannot subtract baseline" test.
- Risk: medium
- Rollback: revert render.py + templates

### Phase 5 — Runaway caps + kill switch
- `depends_on`: [3]
- `parallel_group`: serial-5
- `merge_hazards`: none (new cap helper; reuses autoloop_driver constants)
- Scope (in): `step_cap` + `time_cap_min` for the chained session reusing `autoloop_driver` cap pattern; kill switch = marker removal aborts at next boundary. (out): token/cost budget (deferred).
- Exit criterion: `pytest` — chain halts after N steps; halts after T minutes; marker removal aborts at next boundary; each cap-halt writes a `halted_cap` ledger event.
- Risk: medium
- Rollback: revert cap helper

### Phase 6 — Stage terminal conditional advance + session-start picker + mandatory-gate predicates
- `depends_on`: [0, 1, 2, 3, 4, 5]  ← gated on feasibility (0), enforcement (4), AND caps (5)
- `parallel_group`: serial-6
- `merge_hazards`: `_partials/stage_end_summary.md.j2` + all 7 `stages/*.md.j2` (the largest blast radius; render path shared with P4/P7)
- Scope (in):
  - Edit the shared partial AND each stage's prose "Stage terminal" block (enumerated lines above) — `gated` branch keeps the compaction-surviving STOP wording verbatim; `auto` branch invokes the next pipeline stage via Skill.
  - **Mandatory-gate predicates (absent-case = STOP):** plan = an architecture AskUserQuestion round is pending/unresolved; review = `Status == CHANGES_REQUESTED` (grade < threshold); wrapup = at the merge/push boundary; verify = any check FAIL. Each gate gets a positive + negative fixture.
  - Session-start AskUserQuestion pipeline picker (fires once when an eligible stage runs with no marker).
  - Cross-IDE: Cursor/Codex renders stay gated/advisory (no Skill auto-invoke branch reaches them).
  - (out): ledger/health (P7), docs (P8).
- Exit criterion: golden snapshot PER stage (gated vs auto render) — all 7; per-gate predicate fixtures (positive advances, negative/absent stops); cross-IDE negative snapshot (Cursor/Codex have no auto branch); `context-linter` within Production thresholds.
- Risk: high
- Rollback: revert templates (P0-P5 remain inert without this phase)

### Phase 7 — Audit ledger + /hm:health smoke-test
- `depends_on`: [6]
- `parallel_group`: serial-7
- `merge_hazards`: `templates/commands/hm/health.md.j2` (render path)
- Scope (in): `observability/auto-advance.jsonl` writer with event enum `advanced|gate_blocked|halted_cap` (ADR-009); `/hm:health` positive smoke-test = "autonomy enabled in yaml but zero ledger entries across recent sessions → surface degradation." (out): none.
- Exit criterion: `pytest` — ledger write test; **collision regression test** (ledger never emits an `iter_receipts.Verdict` literal); health surfaces the no-entry degradation signal.
- Risk: low
- Rollback: revert ledger + health edit

### Phase 8 — Docs, runtime e2e, version bump
- `depends_on`: [0, 1, 2, 3, 4, 5, 6, 7]
- `parallel_group`: serial-8
- `merge_hazards`: 5 version files (must stay in sync)
- Scope (in): INTEGRATION-guarded e2e asserting a live `research → spec → plan` chain advances + writes `advanced` receipts + Stop-hook continuation (built from the P0 spike if Mechanism A worked); manual cross-IDE checklist (Cursor Stop-event caveat) in `tests/cursor-compat/`; CHANGELOG; **5-file version bump** — `.claude-plugin/plugin.json`, `.cursor-plugin/plugin.json`, `.codex-plugin/plugin.json`, `pyproject.toml`, `src/harness_maker/__init__.py` — + a version-sync consistency check. (out): none.
- Exit criterion: `INTEGRATION=1 uv run pytest tests/e2e` green; 5-file version-sync check passes; `ruff check` + `mypy --strict` clean.
- Risk: medium
- Rollback: revert docs/version (feature already landed in P0-P7)

## 🧪 Testing Strategy

- **Unit (mock-first):** schema round-trip incl. absent/partial/invalid (P1); marker fail-safe matrix (P2); hook block/no-block (P3); per-deny-class block tests (P4); cap-halt (P5); per-gate predicate fixtures (P6); ledger collision regression (P7).
- **Snapshot:** per-stage gated-vs-auto render (P6); cross-IDE negative (P6); settings deny render (P4).
- **Integration (`INTEGRATION=1`):** live stage-chain e2e (P8) — the only test that proves the runtime behavior snapshots cannot (CLAUDE.md checkpoint 8).
- **Manual:** cross-IDE checklist for the Cursor Stop-event caveat (P8).

## ⚠️ Risks & Mitigation

| Risk | Severity | Mitigation |
|------|----------|------------|
| Runtime chaining mechanism infeasible | high | P0 go/no-go gate (ADR-008); HALT+escalate if both mechanisms fail |
| Live auto-advance ships before enforcement | critical→resolved | P6 `depends_on` includes P4 (validator lead fix) |
| Ledger `skipped` collides with Gate 0 | critical→resolved | ADR-009 disjoint enum + regression test |
| Uncapped runaway chain | high→resolved | P6 `depends_on` includes P5 (caps before live advance) |
| User yaml weakens never-auto baseline | high→resolved | baseline code-fixed, `extra_deny` additive-only, subtraction test |
| Mandatory gate mis-detected (advances past CHANGES_REQUESTED) | high | absent-case=STOP default (ADR-005) + per-gate negative fixtures |
| Stale/corrupt marker silently enables autopilot | medium | fail-safe→gated + clear (ADR-006) + matrix test |
| Template edit leaks enforcement claim to Cursor/Codex | medium | cross-IDE negative snapshot (ADR-004) |
| settings.json render clobbers user config | medium | reuse `render._merge_permissions` + preservation test |

## ✅ Success Criteria

- [x] `autonomy.level=auto_safe` auto-advances research→spec→plan-entry / execute→review→wrapup-entry without a typed command.
- [x] The chain ALWAYS stops at: plan architecture interview, review `CHANGES_REQUESTED`, wrapup merge/push.
- [x] never-auto baseline blocks every listed destructive class at every autonomy level; a hostile yaml cannot remove it.
- [x] Old harness.yaml (no `autonomy` key) renders identically to today (gated).
- [x] Corrupt/stale/foreign-session marker → gated, never a runaway.
- [x] A live INTEGRATION e2e shows a real chain advancing + writing `advanced` receipts.
- [x] Cursor/Codex renders contain no live auto-advance enforcement (negative snapshot).
- [x] `ruff` + `mypy --strict` + full `pytest` green; context-lint within Production thresholds.

## 🔍 Plan Validation

**Codex second opinion:** `codex_status: invoked` (gpt-5.5, confidence 0.91). 18 findings — all reconciled by plan-validator (16 accepted, 2 merged as duplicates).

**plan-validator outcome:** **MAJOR_REVISION → RESOLVED in-place.** 3 critical + 11 warning + 3 suggestion, all KEEP, all grounded in cited code. Resolution mapping:

| Validator finding | Severity | Resolution in this PLAN |
|---|---|---|
| P5(now P6) missing dep on P4 enforcement | critical | P6 `depends_on` now includes P4 |
| Ledger `skipped` collides with iter_receipts.Verdict | critical | ADR-009 disjoint enum + P7 regression test |
| P0 spike no exit + pivot undesigned (loop_gate static reason only) | critical | ADR-008 binary go/no-go + Mechanism B scoped in P3 + P3/P6 gated on P0 |
| Caps ordered too late | warning | P6 `depends_on` includes P5 |
| never_auto user-overridable | warning | ADR-003 baseline code-fixed, additive-only, subtraction test |
| Mandatory-gate predicates unspecified | warning | ADR-005 + P6 per-gate predicate + absent-case=STOP + fixtures |
| No runtime acceptance test | warning | P8 INTEGRATION e2e |
| Marker schema/lifecycle undefined | warning | ADR-006 marker JSON schema + fail-safe matrix (P2) |
| P6 template scope ambiguous | warning | P6 enumerates partial + all 7 prose terminals + per-stage golden snapshot |
| Pipeline membership (verify in/out) | warning | ADR-006 default pipeline = 7-stage incl. verify |
| P1 schema exit too narrow | warning | P1 exit adds absent/partial/invalid/default-preservation via real mapper |
| settings merge/idempotency | warning | P4 reuses `_merge_permissions` + preservation/idempotency/no-dup test |
| Security tests incomplete | warning | P4 one block-test per deny class incl. disguised forms |
| Cross-IDE leak | warning | ADR-004 + P6 cross-IDE negative snapshot |
| P8 version files unlisted | suggestion | P8 lists the 5 files + sync check |
| /hm:health vague | suggestion | P7 names health template + degradation signal |
| P0 spike not operationalized | suggestion | ADR-008 captures spike as note + P8 e2e |

**Why resolved in-place rather than re-validated:** every critical maps to a concrete plan edit that implements the validator's own recommendation verbatim and changes no locked ADR. A second validator+Codex pass is available on request but was judged disproportionate given the 1:1 recommendation-to-edit correspondence.

## 🚧 Execution Log

| Phase | Status | Notes |
|-------|--------|-------|
| P0 spike | not started | go/no-go feasibility gate; needs a throwaway Claude Code session |
| **P1 schema** | **DONE (2026-06-20)** | `AutonomyConfig` (level/pipeline/step_cap/time_cap_min/extra_deny) + `HarnessConfig.autonomy` + `InterviewAnswers.autonomy` mirror + synthesize wiring + both harness-yaml templates emit + `interview._parse_autonomy` reverse-mapper. 12 new tests (absent→gated, partial, invalid-enum reject, default-pipeline preserved, yaml round-trip, synth→render→reload). ruff + mypy --strict clean; snapshots regenerated (8 expected.yaml — harness.yaml sha drift). never_auto baseline deliberately NOT a config field (ADR-003); only `extra_deny` additive. |
| **P2 marker/CLI** | **DONE (2026-06-20)** | `src/harness_maker/autopilot.py` — `AutopilotMarker` (session_uuid/level/pipeline/created_at) + write/clear/load/active_marker/effective_level; reuses `worktree._current_session_uuid` for session identity (project-scoped, same as worktree layer-3). Fail-safe: absent/corrupt-json/schema-invalid/foreign-uuid → None (gated); `load()` uses `model_validate(strict=False)` so JSON pipeline strings coerce to AtomicStage while level Literal + uuid pattern still reject. `effective_level` = active-marker > yaml precedence (ADR-006). CLI `autopilot on/off` (flag-driven, `--level`/`--pipeline`/`--root`). `.claude/.hm-autopilot` added to `worktree._HARNESS_CHURN_FILES` (gitignore + both dirt-filters). 14 tests incl. fail-safe matrix + CliRunner boundary. ruff+mypy+full-suite green. |
| **P4 never-auto enforcement** | **DONE (2026-06-20)** | `src/harness_maker/hooks/autopilot_guard.py` — PreToolUse hook enforcing the code-fixed never-auto list (git push/force-push, reset --hard, stash drop|clear, rm escaping `.worktrees/`, publish/deploy, settings-surface edits) **only while `.hm-autopilot` is active** (ADR-003 P4-impl refinement, user-confirmed: marker-gated, not static settings.json deny — so manual workflows with autopilot OFF are untouched). `autonomy.extra_deny` additive-only; baseline non-overridable. Surgical patterns (no blanket interpreter ban — `python -m harness_maker` allowed). Wired into `hooks.json.j2` PreToolUse (Bash + Write\|Edit\|MultiEdit matchers); Claude-only (ADR-004, PermissionRequest/Codex passes through). 16 tests (off→no-op keystone, on→block per class, surgical-allow, extra_deny additive, main() exit-2). 8 snapshots regenerated (hooks.json sha). ruff+mypy+full-suite green. |
| **P3 stop-hook backstop** | **DONE + REVIEWED Grade A (2026-06-20)** | `autopilot_guard --mode stop-hook` (`_stophook_reason` + main() argparse dispatch) blocks session termination (`decision:block`+exit 2) while the `.hm-autopilot` marker is active; `stop_hook_active` guard checked FIRST (no infinite Stop loop); worktree-aware root via `_resolve_root`. Wired into `hooks.json` Stop event alongside `loop_gate` (Claude-only). Review (k-of-3: 2 code + Codex) Grade A; voluntary fixes applied: isatty guard in main() (TTY-hang), `_stophook_reason` softened to descriptive-only (false-imperative pre-P6); declined `--mode required=True` (PreToolUse entry relies on default). +4 review tests (corrupt/non-dict stdin fail-open, stop_hook_active e2e via main(), default→pretooluse, exit-codes workspace). ruff+mypy+full-suite green; 8 snapshots regen (hooks.json Stop sha). **Pre-existing memory-retrieve red root-caused as wiki.md lost close-marker (P4-wrapup overwrite) → fixed in separate commit 5d5ea1e (`fix(memory)`), not folded here.** |
| **P5 caps + kill switch** | **DONE + REVIEWED Grade A (2026-06-20)** | `src/harness_maker/autopilot_caps.py` — `evaluate_boundary` (PURE): kill_switch (active_marker None/foreign/stale) → step_cap (`steps >= step_cap`) → time_cap (`elapsed_min >= time_cap_min`), kill-switch wins over caps so a user `autopilot off` aborts mid-chain. `record_cap_halt` writes a `halted_cap` event; rejects non-cap kinds. New `src/harness_maker/autopilot_ledger.py` (minimal — P7 extends): `append_event` + `EVENTS` frozenset disjoint from `iter_receipts.Verdict` (ADR-009; rejects pass/fail/skipped) via O_APPEND atomic line (codex_ledger pattern). Review (k-of-3: 2 code + Codex) Grade A; **Codex caught a P1 both Claude reviewers missed** — `fields` could overwrite the validated `event` (ADR-009 bypass) → fixed by setting authoritative ts+event LAST. Other applied fixes: ledger_path absolute-dir containment guard (codex_ledger mirror, R2 P1), `EVENTS = frozenset(get_args(LedgerEvent))` + import-time `assert EVENTS.isdisjoint(get_args(Verdict))` (structural ADR-009), tz-normalize record_cap_halt, +exact-boundary/precedence tests. 18 tests. A.5 test-reviewer PASS. ruff+format+mypy(109)+full-suite green. **No template change → no snapshot impact.** |
| **P6 stage-terminal advance** | **DONE (2026-06-20) — live auto-advance ON** | `autopilot_caps.main` `boundary` CLI (single entrypoint: active_marker→kill_switch, counts ledger `advanced`-since-marker as steps, evaluate_boundary, records halted_cap on cap-halt, on proceed appends `advanced{to}` + reports next_stage, clears marker at pipeline end) + `next_stage` helper + `autopilot_ledger.count_events`. Templates: shared `stage_end_summary` partial gains a Claude-only auto-advance block (runs the boundary CLI → on proceed+gate-clear invokes `Skill(hm:<next>)` instead of STOP) gated `{% if is_codex is defined and not is_codex %}`; all 7 stages set `summary_stage` + per-stage `summary_autopilot_gate` (plan=arch-Q pending, review=CHANGES_REQUESTED, wrapup=push boundary, verify=FAIL, others=none); session-start picker in `step_manifest` (Claude-only + `autonomy.level != gated` render-gate). Cross-IDE (ADR-004): the `is_codex is defined` guard excludes the auto-branch from the Codex stage_skill render (verified by test). 14 new tests (boundary CLI 9 + render/cross-IDE 5). Determinism fix: proceed/pipeline-complete tests arm with live clock (CLI reads real time). 8 manifest snapshots regen. ruff+mypy(109)+full-suite green. **The feature is now functionally live** — `autopilot on` (or the picker) + a non-gated session auto-advances through the pipeline, halting at caps/kill-switch/mandatory-gates. |
| **P7 ledger + health** | **DONE (2026-06-20)** | `gate_blocked` call-site: `autopilot_caps gate-blocked --root --stage` appends a `gate_blocked` event (the partial's Step-1 gate-stop path records WHY the chain stopped, distinct from a cap halt). `/hm:health` positive smoke: `autopilot_ledger.smoke_check` + `smoke` CLI → degraded when `autonomy.level != gated` AND the auto-advance ledger has 0 entries (armed-but-never-fired = H4 silent-degradation); wired into `health.md.j2` as a render-gated (`level != gated`) Layer-1 ActionItem. `advanced`/`halted_cap` writers already shipped (P5/P6). 6 tests (gate_blocked write, smoke 3-case + CLI JSON full-surface, ADR-009 collision regression checking BOTH on-disk bytes + write-boundary reject). A.5 PASS. ruff+mypy(109)+full-suite green; snapshots regen (partial gate-blocked line). |
| **P8 docs + e2e** | **DONE except version bump (2026-06-21)** | `tests/e2e/test_autopilot_chain_e2e.py` — mechanical full-pipeline chain via the boundary CLI (arm → advance each stage + record `advanced` → last stage pipeline_complete + marker cleared; + step_cap-halts-mid-chain). The LIVE Skill-chain is manually verified (P0 spike + cross-IDE checklist) — not pytest-drivable. **e2e caught a real bug**: `_utc_now_iso` was second-truncated while marker `created_at` is microsecond-resolution → a same-second `advanced` event sorted BEFORE created_at → since-filter dropped it → step under-count → step_cap never fired. Fixed `_utc_now_iso` → `isoformat()` (matches marker). Docs: README "Autopilot (pipeline auto-advance)" section + `tests/cursor-compat/MANUAL_CHECKLIST.md` autopilot cross-IDE caveat. ruff+mypy(109)+full-suite green. **5-file version bump DEFERRED to a coordinated release** (user decision — worktree-concurrency was concurrently in-flight; it has since landed FINAL, so a coordinated 0.31.0 release is now unblocked). |
| **P0 spike** | **DONE — GO (2026-06-20)** | Runtime stage chaining is feasible. **Mechanism A (Skill-tool mid-turn invocation) proven LIVE**: `Skill(hm:help)` executed mid-`/hm:execute` and returned output → a stage terminal can `Skill(hm:<next>)` to chain, no new infra. **Mechanism B (Stop-hook backstop) available** via `loop_gate` (proven by /hm:loop). ADR-005 (prompt-driven + backstop) confirmed feasible → P3/P6 unblocked. Caveats for P6: one growing turn (caps load-bearing), mandatory-gate carve-out BEFORE the Skill call (absent=STOP), Claude-only (ADR-004 — no live branch into cursor/codex). Full record: `work-docs/SPIKE-autonomy-p0-runtime-chaining-2026-06-20.md`. |

**This execute pass scoped to P1** (complete verified foundation slice). P2's marker module has session-uuid + fail-safe-matrix depth warranting its own `/hm:execute` pass rather than an oversized single changeset. Changes staged on the worktree branch, no commit (wrapup owns the commit).
