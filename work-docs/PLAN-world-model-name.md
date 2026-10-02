---
type: plan
task_slug: world-model-name
status: complete
created: 2026-10-02
tags: [harness-maker, plan, python, jinja2, world-model, ux, skills, interview]
spec: "[[SPEC-world-model-name]]"
research_doc: "[[RESEARCH-world-model-name]]"
interview_rounds: 0
adrs: 11
validator_outcome: NOT_RUN
summary: "world_model {name, handle} config + /<handle> router skill + onboarding/configure/pointer wiring"
intent: WORLD-INTENT-CLOSED-LOOP
spec_need_verdict: add
spec_need_target: world-model-name
---

# PLAN — Named world model ("Maker") as the development front door

## 🎯 Executive Summary

Add `world_model: {name, handle}` to `harness.yaml` (default `Maker` / `maker`), render one
router skill from a fixed template `skills/world-model/SKILL.md.j2` at the dynamic path
`skills/<handle>/SKILL.md` (and `.agents/skills/<handle>/SKILL.md` for Codex), add a short
always-loaded `## World model` pointer, and ask for the name right after locale in every
onboarding surface (Python interview, `commands/make.md`, `--ci`, `/hm:configure`). The router
only routes to existing surfaces (stages, `intent-layer`, `project-knowledge`, read-only status).
Scope and irreversible decisions come from the approved SPEC; the spec-validator findings recorded
in the SPEC's `🔎 Spec Validation` section are resolved here as ADRs and extra tests without
editing the approved ACs.

## 📚 Prior Work

- `SPEC-loop-opt-in` / `tests/unit/test_loop_opt_in.py` — the closest precedent: a config sub-model
  (`LoopConfig`) that gates rendered files, absent-key default, preset-switch allowlist carry,
  orphan-sweep keep-edited test (`test_ac007_disable_sweeps_pristine_keeps_edited`).
- `SPEC-mission-context-loop` AC-005 — always-loaded pointer partial and its 300-char cap test.
- `[fail:design] fix-introduced-defect-passes-all-gates` (count:18) — advertised names must resolve to
  rendered skills; review fixes need a focused delta review.
- Absent-case black hole (global learned correction) — absent key must default, tested.
- `project_surface_allowance_expires_at_wrapup` — re-freeze baselines inside this task if they move.

## 📐 Architecture Decision Records

### ADR-001: `WorldModelConfig` validates at load, not only at prompts
**Decided by:** agent (resolves spec-validator critical #1)
`WorldModelConfig(name="Maker", handle="maker")`, `strict=True, extra="forbid"`. Field validators:
name is stripped, single line, no control characters, 1–40 chars; handle matches
`^[a-z0-9]+(-[a-z0-9]+)*$`, ≤ 64 chars, and is not reserved. A `model_validator(mode="before")`
derives a missing handle from the name (partial key `{name: Atlas}` → `atlas`) and falls back to
`maker` when no handle can be derived. Every entry point (yaml load, CLI flags, interview) goes
through this model, so a hand-edited reserved handle is rejected before render.

### ADR-002: reserved handles live in `world_model.py`, with a drift test
**Decided by:** agent
`models.py` cannot import `synthesize` (cycle). `world_model.RESERVED_HANDLES` lists every fixed
rendered skill name, and any `hm-` prefix is reserved. A unit test asserts
`set(synthesize._ALL_SKILLS) <= RESERVED_HANDLES` so a new shipped skill cannot silently become a
legal handle.

### ADR-003: handle derivation is NFKD → ASCII slug, `None` when empty or reserved
**Decided by:** agent
`derive_handle(name)`: NFKD-normalise, drop non-ASCII, lowercase, non-alphanumerics → `-`, collapse
and strip hyphens, trim to 64 at a hyphen boundary; return `None` if the result is empty, invalid or
reserved. `비비` → `None` (ask), `Maker` → `maker`, `My Bot!` → `my-bot`.

### ADR-004: router skill = one fixed template, dynamic output dir, not in `skills.enabled`
**Decided by:** agent
`tests/unit/test_enabled_names_resolve.py` requires enabled names to match a template dir, so the
handle never enters `skills.enabled`. `synthesize._world_model_skill_files()` appends the spec in
`_base_files` and `_codex_target_files`; the `config_dump=None` path falls back to the default.
Frontmatter `name` = handle; `description` is emitted with `tojson` so any display name stays
valid YAML.

### ADR-005: the pointer is its own `## World model` section, ≤ 200 chars
**Decided by:** agent
A new partial `world_model_pointer.md.j2`, included right after the project-knowledge pointer in
the four CLAUDE.md variants, `AGENTS.md` and `harness.mdc`. Separate heading keeps the AC-005
project-knowledge cap untouched. Claude arm: `/<handle>`; Codex arm: `$<handle>`; Cursor
(`harness.mdc`): `/<handle>` named as the Claude Code form plus "address <Name> by name" —
Cursor's slash listing of project skills is unverified (spec-validator warning, RESEARCH OQ7).

### ADR-006: CLI flags `--world-model-name` / `--world-model-handle`; underivable name without handle exits 1
**Decided by:** agent (resolves spec-validator warnings on IRR-002 and `--ci 비비`)
Falls inside IRR-002 (the `--ci world_model_name=` contract dispatches to exactly these flags), so
no new IRR. Name only → handle derived; derivation impossible and no handle → exit 1 naming
`--world-model-handle`, never a silent `maker` mismatch. Flags are carried through the
`--preset` rebuild allowlist.

### ADR-007: rename relies on `sweep_orphans`; the emptied skill dir is removed
**Decided by:** agent
`sweep_orphans` already deletes pristine generated files and keeps edited ones. After deleting a
`SKILL.md`, remove its parent directory when it is now empty (no other change to the sweep).

### ADR-008: router body routes; it never re-implements a gate
**Decided by:** user (source: SPEC S7, interview rounds 1–2)
Six request classes → existing surfaces. Briefing is read-only (`git worktree list`, last
`stage-spans.jsonl` row per slug when present, `hm autopilot status`, `hm intent status --json`).
"What next?" presents options and starts nothing. Description triggers on the display name or
handle only, never on bare make/build/fix.

### ADR-009: no `schema_version` bump
**Decided by:** agent
The key is additive with a default; old files load unchanged (absent → default). A bump would add a
migration branch with no reader.

### ADR-010: help listing deferred
**Decided by:** agent
`/hm:help` is surface-measured and pinned by invariance tests; the always-loaded pointer and the
onboarding confirmation already advertise the handle. Follow-up, not this task.

### ADR-011: the briefing is capped; resume re-enters an interrupted stage
**Decided by:** agent (from the mid-execute research addendum in RESEARCH-world-model-name)
The intent status is piped through a 7-key filter (17.5 KB → ~0.4 KB measured), the span log is
read one row per slug via `grep | tail -n 1`, the reply is ≤ 8 lines, and the skill forbids
reading `wiki.md` / `failures.md` / the span log whole. Resume: interrupted (newest span is a
`start`) → same stage; ended → next stage. A deterministic digest verb is deferred: it is a new
public CLI contract and needs a SPEC change.

## 🏗️ Technical Design

- **Config:** `src/harness_maker/world_model.py` (new: `derive_handle`, `handle_error`,
  `RESERVED_HANDLES`, `DEFAULT_NAME/HANDLE`); `models.WorldModelConfig` + field on `HarnessConfig`
  and `InterviewAnswers`; `interview._build_answers(world_model=…)`;
  `answers_from_harness_yaml` parses `world_model`; harness-yaml templates write the block;
  `synthesize()` passes `world_model` into `HarnessConfig`.
- **Render:** `templates/skills/world-model/SKILL.md.j2`; `synthesize._world_model_skill_files`;
  `templates/agents/_partials/world_model_pointer.md.j2` + 6 includes; `reconcile.sweep_orphans`
  empty-dir cleanup.
- **Surfaces:** `interview._ask_world_model` after `_ask_locale`; `cli.make` flags +
  `_apply_dimension_overrides` + preset-switch carry; `commands/make.md` §0/§1/dispatch;
  `templates/commands/hm/configure.md.j2` dimension + dispatch; i18n messages.

## 📝 Implementation Plan

### Phase 1 — Config core
- depends_on: none · parallel_group: A · merge_hazards: models.py / interview.py shared with Phase 3
- scope in: `world_model.py`, `models.py`, `interview.py` (build/parse only), `synthesize.py` (HarnessConfig field), `templates/harness-yaml/*.yaml.j2`, `tests/unit/test_world_model.py`
- scope out: render templates, CLI, slash prose
- exit: `uv run pytest tests/unit/test_world_model.py`
- risk: medium · rollback: drop the field + module

### Phase 2 — Router skill + pointer + sweep
- depends_on: Phase 1 · parallel_group: B · merge_hazards: snapshot fixtures, count tests
- scope in: `templates/skills/world-model/SKILL.md.j2`, `synthesize.py`, `templates/agents/_partials/world_model_pointer.md.j2`, 6 always-loaded templates, `reconcile.py`, `tests/render/test_render_world_model.py`
- exit: `uv run pytest tests/render/test_render_world_model.py`
- risk: medium · rollback: remove the two synthesize helpers and includes

### Phase 3 — Onboarding surfaces
- depends_on: Phase 1 · parallel_group: B (serial after Phase 2 — shared test module) · merge_hazards: cli.py allowlist
- scope in: `interview.py` (`_ask_world_model`), `cli.py`, `i18n_messages.py`, `commands/make.md`, `templates/commands/hm/configure.md.j2`
- exit: `uv run pytest tests/unit/test_world_model.py tests/render/test_render_world_model.py`
- risk: medium · rollback: revert flags and prose

### Phase 4 — Retire: fixtures and counts
- depends_on: Phases 1–3 · parallel_group: C · merge_hazards: generated fixtures
- scope in: `tests/snapshot/*.expected.yaml` (regenerate), count assertions listed in Risks, surface/instruction baselines if they move, this repo's own rendered harness is NOT re-rendered here
- exit: full suite green (`uv run pytest -n auto`), `ruff check`, `ruff format --check`, `mypy --strict src`
- risk: low · rollback: re-run regenerate at base

## 🚧 Contract Boundaries

### Do not change
- `src/harness_maker/templates/skills/intent-layer/` — Maker routes to it; its consent rules stay as they are
- `src/harness_maker/templates/skills/project-knowledge/` — routed to, unchanged
- `src/harness_maker/templates/stages/` — stage gates are not touched by the router
- `src/harness_maker/templates/agents/_partials/project_knowledge_pointer.md.j2` — AC-005 cap belongs to mission-context-loop
- `specs/SPEC-world-model-name.machine.yaml` — approved; authored fields stay as approved
- `.claude/` — this repo's own rendered harness; re-render belongs to a release, not this task

## 🧪 Testing Strategy

- Unit (`tests/unit/test_world_model.py`): derivation property (AC-003), reserved/grammar/name
  validation incl. load-time rejection (AC-006 + critical #1), round-trip property (AC-008), CLI
  flags incl. underivable-name exit (AC-009), interview default + non-ASCII handle prompt (AC-001),
  partial key, reserved ⊇ `_ALL_SKILLS` drift.
- Render (`tests/render/test_render_world_model.py`): router path/frontmatter/codex (AC-002),
  absent ≡ explicit default tree (AC-004), rename sweep × {pristine, edited} × {.claude, .agents}
  (AC-005), pointer rows incl. non-default handle and `/maker` absence + ≤ 200 chars (AC-007),
  router body routing anchors (AC-010 support), make.md §0/§1/dispatch and configure dispatch text
  (AC-001/AC-009/AC-011 slash halves).
- Manual: dogfood `/maker` after the next release re-render (AC-010 judgment).

## ⚠️ Risks & Mitigation

| Risk | Likelihood | Mitigation |
|---|---|---|
| Count tests (`test_synthesize_codex.py:83`, `test_codex_phase7.py:177`, `test_synthesize.py:45`, `test_unwired_components.py:246`) break | high | Update in Phase 4 with the reason |
| Snapshot fixtures drift | high | `uv run python tests/snapshot/regenerate.py` from the worktree; grep output for `/home/` |
| Preset switch drops `world_model` | medium | Allowlist carry + test |
| A user's own `.claude/skills/maker/` collides | low | reconcile treats an un-provenanced existing file per its existing rules; covered by a test |
| Description over-triggers on "make" | medium | Description wording + test asserting the guard sentence |

## ✅ Success Criteria

- [x] AC-001 onboarding asks name after locale, default Maker (Python + make.md)
- [x] AC-002 router skill at handle path, codex dual-render
- [x] AC-003 derived handles valid or None
- [x] AC-004 absent key ≡ explicit default
- [x] AC-005 rename sweeps pristine, keeps edited (.claude + .agents)
- [x] AC-006 invalid/colliding handles rejected, yaml untouched
- [x] AC-007 pointer in every always-loaded file, ≤ 200 chars, follows rename
- [x] AC-008 round-trip
- [x] AC-009 CLI/ci flags
- [x] AC-010 router routes per S7 (judgment + dogfood)
- [x] AC-011 configure dimension + dispatch

## Feedback

| Evidence | Affected ID | Update status | Decision | Owner | Authority | Next action |
|---|---|---|---|---|---|---|
| SPEC S7(c): "continue" resumes the next stage without the user re-stating the connection | WORLD-INTENT-CLOSED-LOOP / intent_world_closed_loop_cycles | recorded | metric record intent_world_closed_loop_cycles = 1 (operator: yes) | DRI | wrapup Step 5.7 answer | wrapup Step 5.7 decides |

## Phase status

### Phase 1 — BLOCKED (Phase A.5 retry exhausted)
- A.5 round 1 FAIL (5 blocking: two false-GREEN negative invariants, configure dispatch anchor,
  AC-006 rule class/locale message unasserted, S1 persisted default unasserted) — all repaired.
- A.5 round 2 FAIL (1 blocking: S2 only exercised via private `_ask_world_model`; no public
  `interview()` path test). Repaired after the round closed:
  `test_s2_interview_carries_non_ascii_name_into_answers` (RED, verified). Not re-reviewed —
  the 2-round budget is spent.
- Phase C not entered. `[boundaries] comparison not performed — blocked exit`
- `stuck` escalation recommended Path B; **DRI chose Path A (2026-10-02)**: one extra A.5
  dispatch, scoped to `test_s2_interview_carries_non_ascii_name_into_answers` (plus the private
  test it supplements). Recorded as an exception to the 2-round budget, granted by the user.
- A.5 round 3 (scoped, user-granted): PASS. Phase B RED confirmed (55 failed for missing
  implementation). Phase C implemented; Phase 1 **DONE**.

### Phase 2 — DONE · Phase 3 — DONE
Router skill, pointer, sweep empty-dir removal, interview question, CLI flags + load-time
validation, make.md §0/§1.5/dispatch, configure dimension. Feature suite 56/56 green.

### Phase 4 — DONE
Snapshots regenerated (no machine paths), autopilot golden re-captured (`configure` only),
loop-ON CLAUDE.md re-captured with verification note, count tests, interview scripted inputs,
doc skill lists, redundancy matrix row, fast-path axis classification, surface baseline
re-frozen with `BASELINE-DELTA-world-model-name.md`. Full suite: 9785 passed + the 3 attribution
tests fixed after (7/7 green); ruff, format, `mypy --strict` clean.

Boundary comparison (45 changed paths): no crossing — none of the `Do not change` entries was
touched; the machine SPEC is unchanged since approval (approval-status `approved`).

### Follow-ups (DRI decision 2026-10-02: separate task, not this one)
- P1: deterministic `hm` digest verb for the briefing (needs a SPEC: new public CLI contract).
- v1.1: "why did we decide X" query route (capped grep over wiki/failures/ADRs); failures since
  last session in the digest; stage STOP text ending with "next: `/<handle> 이어서`".
- `/hm:help` listing of the router (ADR-010).

### Post-review (DRI request) — REVIEW 6d3f14ad fixed
Router span lookup now reads the base-root ledger via `git rev-parse --git-common-dir`.
Newly reachable window: invocation from a task worktree or a base subdirectory (previously
"stage unknown"); covered by `test_span_lookup_reads_the_base_ledger_from_inside_a_worktree`,
which executes the rendered command in both a base and a worktree. Absent case (no git):
`dirname ""` → `.`, i.e. the prior cwd-relative behaviour.
