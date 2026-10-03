---
type: plan
task_slug: maker-front-door-improvements
status: complete
created: 2026-10-03
tags: [harness-maker, plan, python, jinja2, front-door, autopilot, memory-retrieve]
spec: "[[SPEC-maker-front-door-improvements]]"
research_doc: "[[RESEARCH-maker-front-door-improvements]]"
interview_rounds: 0
adrs: 7
validator_outcome: NOT_RUN
intent: WORLD-INTENT-CLOSED-LOOP
summary: "Digest, autopilot narrow and retrieval engines in parallel, then one render phase for every surface"
spec_need_verdict: add
spec_need_target: maker-front-door-improvements
---

# PLAN — Maker as the only entrance and owner of the world model

## 🎯 Executive Summary

Implement SPEC-maker-front-door-improvements (17 ACs, 8 IRRs, approved 2026-10-03 02:03Z) in four
phases. Three engine phases touch disjoint modules and run in parallel: the digest
(`world_model_digest.py`), autopilot narrowing (`autopilot.py` + one branch of `autopilot_caps.py`),
and memory retrieval (`memory_retrieve.py`). The fourth phase changes every rendered surface (skill
frontmatter, Codex `openai.yaml`, stage descriptions, help, both always-loaded pointers, the Maker
template) and depends on the engines, because the templates call the new verb and read the new digest
fields. Key decisions come from the SPEC interview (Rounds 0–3); the reversible ones below are agent
decisions.

## 📚 Prior Work

- PLAN-world-model-name (ADR-008 routes-only, now reversed by IRR-005) and PLAN-world-model-followups
  (digest ADR-001..008: separate module, 1,500 B cap, marker read without migration).
- `[fail:test] snapshot-regen-inside-worktree`: regenerate snapshots from this worktree (regenerate.py pins paths).
- `[fail:design] fix-introduced-defect-passes-all-gates`: Phase D.5 applies to every repair round.
- `[fail:test] assertion-invariant-over-named-dimension`: AC tests quantify over targets/locales/stages, not one member.
- RESEARCH: `!` non-zero exit aborts the whole skill; Codex key `policy.allow_implicit_invocation` (docs, fetched 2026-10-03).

## 📐 Architecture Decision Records

### ADR-001: Narrow recomputes from the saved original
`hm autopilot narrow --until E` takes `base = marker.restore_pipeline or marker.pipeline`, writes
`pipeline = base[:index(E)+1]` and `restore_pipeline = base`, and changes nothing else (`level`,
`created_at`, `claude_session_id`, `task_slug`). E not in base, or base already ending at E → no
write, exit 0, JSON reason. No marker / not own / not active → no write, exit 0. Uses
`_write_if_unchanged`. A narrow that halts before E is therefore undone by the next narrow call.
**Decided by:** user (source: SPEC Round 2–3, S4/S5)
Amendment (Phase A, 2026-10-03): at level `gated` narrow writes nothing — a gated marker never
advances (every boundary halts at `kill_switch`), so the restore path could never fire and a write
would only leave a latent `restore_pipeline`. Maker announces the end point only. **Decided by:** agent

### ADR-002: Restore happens at the boundary that would have cleared the marker
In `autopilot_caps` boundary, the `nxt is None` branch (current is last stage) restores
`pipeline = restore_pipeline`, sets `restore_pipeline = None`, returns `proceed: false` with
`narrow_end: true` instead of `pipeline_complete`/clear when `restore_pipeline` is set. Other halts
keep their behaviour. **Decided by:** agent

### ADR-003: Digest gains four things; trim order is fixed
`intents.active` = list of `{id, metric_id, last, target, gap}` for active intents (min 3 shown),
values copied from `intent_cli.status_report` (`metrics[metric_id]`), `"—"` when absent. Tasks gain
`parked` and `latest_artifact: {name, at}` (mtime, ISO seconds). Parked tasks sort last. `render`
trims: `recent` → intents beyond 3 → `latest_artifact` clipping → tasks down to 3. A `maker_load`
row `{ts, event, session_id}` is appended to `.claude/observability/world-model.jsonl` by the CLI
entry, best-effort (never changes exit code). **Decided by:** agent (fields: user, SPEC S3/S7/S8/S11)

### ADR-004: memory_retrieve is lexical-first under one cap
Floor entries are admitted only into slots left after lexical hits (k − lexical); each dated entry
renders only its newest dated bullet (max parsed date; undated entries render their first paragraph);
the whole block ≤ 8,192 bytes, dropping whole floor entries first, then lowest-scored lexical entries,
never mid-codepoint. Existing count-floor tests that pin the old always-admit rule are updated, not
deleted (IRR-006). **Decided by:** user (SPEC Round 1, S9)
Amendment (Phase A, 2026-10-03): the floor keeps its cap of 3 (`DEFAULT_COUNT_FLOOR`) — it fills
min(k − lexical, 3) slots; a lexical hit dropped by the cap is never re-admitted under the floor label
(dedup against the eligible pool, not the emitted set); "undated" = an entry with no dated bullet —
headings without a date are still dropped by the parser (pre-existing, out of scope). **Decided by:** agent

### ADR-005: Codex `openai.yaml` is a pure-text render
`.agents/skills/{intent-layer,project-knowledge}/agents/openai.yaml` renders through
`_render_pure_text` (no provenance prefix — a YAML preamble would make it multi-document). The orphan
sweep already covers `.agents/` via the render-manifest hash. **Decided by:** agent

### ADR-006: The pointer carries routing, decision capture and the aside protocol
`world_model_pointer.md.j2` grows to ≤ 400 chars per variant (was 200) and carries: unnamed
goal/fact/status requests (mid-stage too) → Maker's procedure; build/fix excluded; decisions about an
in-flight task are written to its most downstream artifact before replying; mid-stage asides (≤ 6
lines, queue new work under `## Queued asks`, end with a resume line). `project_knowledge_pointer`
switches from "follow the skill" to "read the procedure file" because the skill is no longer
model-invocable. **Decided by:** user (SPEC Round 3)

### ADR-007: Injected briefing uses `|| echo` plus `allowed-tools`
The Claude-target Maker line becomes `` !`uv run … digest … 2>/dev/null || echo '{"unavailable":"digest"}'` ``
and the Maker frontmatter gains `allowed-tools` for `Bash(uv run:*)` and `Bash(echo:*)` so the
injection is pre-approved outside auto mode. The digest itself prints one line once at exit, so
partial-then-fail cannot come from our code; the test simulates it with a fake `uv` and Maker reads
the **last** JSON line. If that cannot meet AC-010's "exactly one JSON object" row, record it in
Phase 4 notes for the DRI rather than weakening the test. **Decided by:** agent

Amendment (Phase 4 Phase A, 2026-10-03): to meet AC-010's "exactly one JSON object" on a
partial-then-fail run, the injected line is
`` !`uv run … digest … 2>/dev/null | tail -n 1 | grep '^{.*}$' || printf '{"unavailable":"digest"}\n'` ``
(post-review, confirm-2 P2: the earlier `{ …; } | tail` group was replaced because a permission
matcher splits on `|`/`||` and a piece starting with `{` matches no rule)
and `allowed-tools` lists exactly `Bash(uv run --with <src> hm world_model:*)` (the module has only the read-only `digest`),
`Bash(uv run --with <src> hm autopilot narrow:*)`, `Bash(tail:*)`, `Bash(grep:*)`, `Bash(printf:*)` (review
round 2, REVIEW 24451777: the original `Bash(uv run:*)` pre-approved any `uv run`; confirm-1 P1:
the interim `Bash(uv run --with <src> hm *)` still pre-approved every `hm` verb — both
DRI-approved AC-010 literal changes). The
Codex run block uses the same command without the `!`. **Decided by:** agent; grant scope by DRI

### ADR-008: Phase 4 literal contract (tests and templates share these strings)
- **Skill flags:** `.claude/skills/{intent-layer,project-knowledge}/SKILL.md` frontmatter gains
  `disable-model-invocation: true` (not in the Codex `.agents/` copies). Codex gets
  `.agents/skills/<n>/agents/openai.yaml` = `policy:\n  allow_implicit_invocation: false\n`.
- **Stage descriptions** (6 atomic stages, Claude `_COMMAND_DESCRIPTIONS` and Codex
  `stage_skill.md.j2`): keep the summary, drop any "Invoke when"/"Use when"/"Use this when", append
  `Only when typed, or via <Name>, autopilot or /hm:loop.` (Codex: `$hm-loop`). `<Name>` =
  world-model name. Summaries are shortened so the whole line stays within the existing 120-char
  description cap (`tests/structural/test_command_descriptions.py`) at the default name — every
  description is in the always-loaded skill listing, so the cap is kept rather than raised.
- **Help rows** for intent-layer / project-knowledge contain `typed only` and name the Maker invocation.
- **World-model pointer** (≤ 400 chars at NAME_MAX/HANDLE_MAX, every variant: claude en, claude ko,
  cursor, codex): Maker invocation; goals/metrics/facts/status routed to Maker even unnamed or
  mid-stage; exclusion literal (en `not build/fix`, ko `만들기·고치기 제외`); decision rule (en
  `before replying`, ko `답하기 전`); aside opener (en ``asides start `<Name> —` ``, ko
  ``곁답은 `<Name> —`로 시작``), line bound (en `6 lines`, ko `6줄`), `` `## Queued asks` ``, `↩`.
- **Project-knowledge pointer** (≤ 300 chars, keeps `project-knowledge`, `auto-memory`): names the
  Maker invocation and the procedure path instead of "follow the skill".
- **Maker template** (≤ 4,500 chars rendered, every target), literal sentences:
  `Its consent rule applies unchanged.` ·
  `Answer read-only goal and status questions from the briefing; read a procedure only to change something.` ·
  a `Read` line naming `<skills-dir>/intent-layer/SKILL.md` and `<skills-dir>/project-knowledge/SKILL.md` ·
  `write it into that task's most downstream artifact (PLAN, else SPEC, else RESEARCH) before replying` ·
  `name its latest_artifact and time before entering` ·
  aside clauses ``Mid-stage asides start `<Name> —` ``, `at most 6 lines`, `` `## Queued asks` ``,
  `never start`, `↩` ·
  an end-stage table whose rows carry cues: research row `research`/`리서치`/`조사`, spec row
  `spec`/`스펙`, full row `build`/`만들어`/`고쳐`, plus `unclear → research` ·
  narrow command `hm autopilot narrow --until` · description adds "or the World model rule routes a
  goal, metric, fact or status request here".
**Decided by:** agent (strings), user (behaviour: SPEC S1–S12)

## 🏗️ Technical Design

- Digest: `digest()` builds the payload; `render()` enforces the cap; CLI entry in `world_model.py`
  (`hm world_model digest`) prints `render(digest(...))`.
- Autopilot: `AutopilotMarker` (strict, extra=forbid) gains `restore_pipeline: list[AtomicStage] | None = None`
  (absent-case: pre-upgrade markers validate). `main()` gains action `narrow` with `--until`.
  `command_registry` lists `narrow`.
- Retrieval: `render_candidates_block` + floor picking in `memory_retrieve.py`.
- Render: `_ALL_SKILLS` skill templates, `_codex_skill_files`, `_COMMAND_DESCRIPTIONS`,
  `codex/stage_skill.md.j2`, `help.{en,ko}.md.j2`, the two pointer partials, `skills/world-model/SKILL.md.j2`,
  `render._is_pure_text`.

## 📝 Implementation Plan

### Phase 1 — Digest: active intents, parked, latest artifact, maker_load
- depends_on: none · parallel_group: A · merge_hazards: none (sole owner of `world_model_digest.py`, `world_model.py` digest entry)
- Scope in: `src/harness_maker/world_model_digest.py`, digest CLI entry in `src/harness_maker/world_model.py`, `tests/unit/test_maker_digest.py`. Out: templates, autopilot.
- ACs: AC-006, AC-011, AC-012, AC-015
- Exit: `uv run pytest tests/unit/test_maker_digest.py tests/unit/test_world_model_digest.py`
- risk: medium · rollback: revert the two source files

### Phase 2 — Autopilot narrow + restore
- depends_on: none · parallel_group: A · merge_hazards: marker schema (IRR-008) — every marker reader must accept the field; checked by grep in exit
- Scope in: `src/harness_maker/autopilot.py`, the `nxt is None` branch of `src/harness_maker/autopilot_caps.py`, `src/harness_maker/command_registry.py`, `tests/unit/test_autopilot_narrow.py`. Out: caps, levels, gates.
- ACs: AC-008, AC-009
- Exit: `uv run pytest tests/unit/test_autopilot_narrow.py tests/unit -k autopilot`
- risk: high (autonomy state) · rollback: revert the three source files

### Phase 3 — memory_retrieve lexical-first, bounded
- depends_on: none · parallel_group: A · merge_hazards: none
- Scope in: `src/harness_maker/memory_retrieve.py`, `tests/unit/test_memory_retrieve_bounded.py`, existing `tests/unit/test_memory_retrieve*.py` assertions that pin the old floor rule. Out: callers' templates.
- ACs: AC-013
- Exit: `uv run pytest tests/unit -k memory_retrieve`
- risk: medium · rollback: revert `memory_retrieve.py` and the updated tests
- **Status: BLOCKED (2026-10-03)** — A.5 retry exhausted. Round 1 FAIL (no floor lower bound; huge-body
  test size-only), round 2 FAIL with one blocker: `test_ac013_huge_hangul_body_stays_under_cap_and_decodes`
  selected the shown entry by slug only. The reviewer's verbatim recommendation `assert not shown[0].floor`
  was applied after round 2 and has not been reviewed. `stuck` recommends Path A (accept, record,
  enter Phase C); B = one extra scoped A.5 round; C = A plus a separate gate-rule change.
  `[boundaries] comparison not performed — blocked exit`. Awaiting the DRI's choice.
- **Unblocked (2026-10-03):** DRI chose Path B — one extra A.5 round scoped to the edited function.
  Round 3 PASS (ledger run-id `maker-front-door-improvements-p3-dri-r3`, reason recorded). The
  residual (lexical+floor duplicate) is covered by `_check` in the other S9 tests. Phase C entered.

### Phase 3 status
- **DONE (Phase C/D GREEN, 2026-10-03)**: 100 passed (unit `-k memory_retrieve` + integration CLI).
  Agent decisions: `--floor-entry-bytes` / `--floor-byte-cap` removed (inert under one cap; now
  rejected by argparse — part of IRR-006), floor deduped against every entry with score > 0,
  single oversized entry cut in one exact budget step. Known gap: a topic so long the fence alone
  exceeds 8,192 still overflows. Three integration tests updated to the new contract.

### Phase 4 status
- **DONE (Phase C/D GREEN, 2026-10-03)**: 89/89 AC tests; render/structural/snapshot suites green.
  Rendered Maker (this worktree's 60-char install path): claude 4,392→~4,430 after the `hm` prefix
  line, codex ~4,250, cursor ~4,420 — under 4,500 at the default name; **over the cap at
  NAME_MAX/HANDLE_MAX (claude ~4,850)** — the SPEC bounds the pointer at max lengths but not Maker;
  surfaced to the DRI. Pointers at max name: world-model 397/400, project-knowledge 297/300.
  Agent decisions beyond ADR-008: one `_STAGE_SUMMARIES` table feeds Claude descriptions and Codex
  stage skills; `openai.yaml` routed to pure-text by name + `agents/` parent; Cursor pointer arm
  dropped "by name, or … in Claude Code" to fit 400; Maker route row says "add / fix / investigate X"
  (a "build" cue there would collide with the end-stage table); surface baseline re-frozen with
  `BASELINE-DELTA-maker-front-door-improvements.md` (claude +241, codex +68).
  Orchestrator fix after review: Claude Code replaces the `!` line with its output, so Maker never
  saw the `uv run --with … hm` prefix it needs for `narrow` and the digest fallback — one line now
  defines `hm`. Loop-ON recaptures for CLAUDE.md/help.md added to `test_loop_opt_in.py` after
  verifying the ON/OFF diff is still only the loop lines.
  Boundary crossing: `src/harness_maker/templates/stages/execute.md.j2` (lines ~76-78) — its
  memory-retrieval note described the old floor/excerpt behaviour that Phase 3 made false.

### Phase 1 status
- **DONE (Phase C/D GREEN, 2026-10-03)**: 72 passed (digest suites), 1228 passed in the targeted
  autopilot/world_model/digest/command_registry run. Agent decisions beyond ADR-003: `parked`
  computed for every task (sort needs it before the cut), base = base HEAD (`worktree._branch_drift`
  method), no `.claude/` → no `maker_load` row, latest_artifact clipping = name to 40 chars,
  below 3 tasks the old drop-then-`unavailable` fallback still runs (S3 floor of 3 is best-effort
  under extreme payloads), `render` never raises.

### Phase 2 status
- **DONE (Phase C/D GREEN, 2026-10-03)**: 60 passed across narrow/registry/autopilot/marker-key
  suites. Existing contracts updated for the new action: registry subcommands, Typer shim parity
  (`narrow` added to `harness-maker autopilot`), `KEYED_APIS` (`narrow`, `restore_narrowed`).
  Agent decisions: `narrow_end` key always present; a lost restore race still stops with the reason
  saying the restore was skipped; narrowed-at-verify stops without the merge_gate clear (ADR-002);
  `narrow` without `--until` is a JSON no-op with exit 0 on both shims.

### Phase 4 — Rendered surfaces
- depends_on: [1, 2] · parallel_group: B · merge_hazards: snapshot fixtures and structural baselines (regenerated in this worktree)
- Scope in: `src/harness_maker/templates/skills/{intent-layer,project-knowledge,world-model}/`, new `templates/skills/_codex/openai.yaml.j2` (or equivalent), `src/harness_maker/synthesize.py` (`_codex_skill_files`, `_COMMAND_DESCRIPTIONS`), `templates/codex/stage_skill.md.j2`, `templates/commands/hm/help.{en,ko}.md.j2`, `templates/agents/_partials/{world_model_pointer,project_knowledge_pointer}.md.j2`, `src/harness_maker/render.py` (`_is_pure_text`), `tests/render/test_render_maker_front_door.py`, existing render tests pinning the 200-char pointer cap, snapshot fixtures.
- ACs: AC-001, 002, 003, 004, 005, 007, 010, 014, 016, 017
- Exit: `uv run pytest tests/render tests/structural tests/unit -k "maker or world_model or command_descriptions or pointer"` then full suite once
- risk: medium · rollback: revert templates + synthesize/render edits, restore fixtures from git

## 🚧 Contract Boundaries

### Do not change
- `src/harness_maker/intent_cli.py` — intent verbs and consent rules are a non-goal
- `src/harness_maker/templates/stages/` — stage bodies; only descriptions move (synthesize table + codex stage_skill)
- `src/harness_maker/templates/skills/intent-layer/references/` — procedure content unchanged; only frontmatter moves
- Advisory: autopilot caps, levels, human-gated stages and judgment-gate semantics stay as they are; only the last-stage clear branch gains the restore path
- Advisory: no `skill` key in the PostToolUse telemetry allowlist (SPEC non-goal)

## 🧪 Testing Strategy

- Unit/property (pytest + hypothesis `ci` profile) for Phases 1–3; render tests parametrized over targets × locales for Phase 4.
- Snapshot regeneration in this worktree; structural surface baselines updated with the declared delta.
- Full suite once at the end (background, per memory: ~6 min).
- Manual (wrapup/dogfood): S1, S2, S4, S10, S11, S12 steps in the SPEC table.

## ⚠️ Risks & Mitigation

| Risk | Likelihood | Mitigation |
|---|---|---|
| Marker field breaks a reader with strict parsing | medium | grep every `.hm-autopilot` reader; absent-case default None; test pre-upgrade marker |
| `allowed-tools` ignored or rejected by Cursor | low | Cursor documents ignoring unknown keys? unverified — keep key Claude-only if the cursor render differs |
| Surface budget gate red after template growth | high | measure delta, update baseline with rationale in the same phase |
| Pointer at 400 chars still overflows at NAME_MAX in ko | medium | test at NAME_MAX/HANDLE_MAX for every variant |
| Floor tests encode old semantics | certain | update with IRR-006 citation, keep the cases |

## ✅ Success Criteria

- [x] AC-001 … AC-017 tests green
- [x] Existing world_model / autopilot / memory_retrieve / render suites green
- [x] Snapshots + structural baselines regenerated with declared delta
- [x] Full suite green once
- [x] No `git commit` from this stage

## Feedback

| Evidence | Affected ID | Update status | Decision | Owner | Authority | Next action |
|---|---|---|---|---|---|---|
| SPEC Feedback rows (2026-10-03) carried | intent_world_closed_loop_cycles, WORLD-INTENT-CLOSED-LOOP | recorded + readback | see SPEC §Feedback | agent | pending decision | wrapup Step 5.7 |
| interview 2026-10-03: operator asked that resume after a pause never loses progress and Maker stays the entrance mid-stage | WORLD-INTENT-CLOSED-LOOP | recorded + readback | S10–S12 added; directly targets "feedback reaches the next decision without re-instruction" | agent | pending decision | wrapup Step 5.7 |
| wrapup Step 5.7 2026-10-03: DRI verdict yes (feedback reached the next decision without re-instruction) | intent_world_closed_loop_cycles | recorded + readback | metric record 2 -> 3 (at_or_better) | user | DRI answer in wrapup batch | intent close question |
| wrapup Step 5.7 2026-10-03: questions q_maker_owns_intents, q_decision_capture_resume added (open) | WORLD-INTENT-CLOSED-LOOP | recorded + readback | question add x2 | user | DRI selection in wrapup batch | evidence at next tasks |
