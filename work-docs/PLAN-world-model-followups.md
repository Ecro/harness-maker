---
type: plan
task_slug: world-model-followups
status: complete
created: 2026-10-02
tags: [harness-maker, plan, python, jinja2, world-model, cli, hardening]
spec: "[[SPEC-world-model-followups]]"
research_doc: "[[RESEARCH-world-model-name]]"
interview_rounds: 0
adrs: 8
validator_outcome: NOT_RUN
summary: "hm world_model digest (artifact-based next stage) + router/help/pointer + review leftovers"
intent: WORLD-INTENT-CLOSED-LOOP
spec_need_verdict: add
spec_need_target: world-model-followups
---

# PLAN — Maker follow-ups

## 🎯 Executive Summary

Add a read-only, capped, always-succeeding `hm world_model digest` whose `next_stage` comes from
task artifacts (SPEC approval → REVIEW existence → REVIEW APPROVED → verification marker), switch
the router to brief from it (`!` injection + fallback on Claude Code, one Bash line on Codex),
list the router in `/hm:help`, shorten the pointer so it fits 200 chars at max name/handle, and
fix the review findings SPEC-world-model-name carried. Scope and IRR-001 come from the approved
SPEC; the span-`end`-is-a-turn-end finding (spec-validator critical) is why spans never advance.

## 📚 Prior Work

- SPEC/PLAN/REVIEW-world-model-name — router, pointer, carried P2/P3 list.
- RESEARCH-world-model-name addendum — digest tiers and sizes.
- `[fail:test] assertion-invariant-over-named-dimension` (count:22) — pin tests on non-default values.
- `[fail:design] fix-introduced-defect-passes-all-gates` (count:18) — D.5 windows for each fix.
- `mypy-strict-local-scope-narrower-than-ci` — run `mypy --strict src tests` locally.

## 📐 Architecture Decision Records

### ADR-001: digest lives in `world_model_digest.py`; `world_model.py` gets a thin `main()`
**Decided by:** agent
`models.py` imports `world_model` (pure rules); a digest that imports spec_machine / intent /
worktree helpers there would create an import cycle. `world_model.main()` imports the digest
lazily; `hm` dispatch (`_DISPATCHABLE`, `command_registry.MODULES`) registers `world_model` with
subcommand `digest`.

### ADR-002: autopilot is read from the marker file, not `autopilot.status`
**Decided by:** agent
`status()` runs legacy takeover and stale-marker GC (writes). The digest must be read-only, so
it reads `marker_path(root, session_id)` and validates with `AutopilotMarker` + `_freshness`.
Cost: a marker still under the legacy filename reads as inactive until the next stage's
`autopilot status` migrates it.

### ADR-003: task worktrees are found by reading `.worktrees/*/.git` → `gitdir` → `HEAD`
**Decided by:** agent
No public lister exists for `hm/<slug>` worktrees (`_list_worktrees` filters them out). File
reads avoid one subprocess per worktree; a worktree whose HEAD is not `refs/heads/hm/<slug>` is
skipped.

### ADR-004: next-stage signals (per SPEC S2)
**Decided by:** user (source: SPEC Round 4)
spec ← `spec_machine.approval_state(base, slug).state in {approved, exempt}`; execute ← any
`work-docs/REVIEW-<slug>-*.md`; review ← newest REVIEW (by name) `status: APPROVED`; verify ←
verification marker fresh for the task worktree (`compute_relevant_skip_key` + `is_fresh`), only
evaluated when review is done; research ← none of RESEARCH/SPEC/PLAN/REVIEW present.

### ADR-005: size cap by per-field truncation then dropping `recent`, then tasks
**Decided by:** agent
Serialize compact with `ensure_ascii=False`; truncate commit subjects to 60 chars and intent ids
to 40; if still > 1500 bytes drop `recent`, then trim `tasks` from the tail (incrementing
`more`), then return `{"unavailable": "too-large"}`.

### ADR-006: pointer text shortened to fit 200 chars at name 40 / handle 64
**Decided by:** agent
Fixed text per arm ≤ ~70 chars: e.g. "**{name}** (`/{handle}`): briefing, start/resume work, facts, goals."

### ADR-007: interactive messages localized via new i18n keys; locale passed to `_ask_world_model`
**Decided by:** agent

### ADR-008: `--add/--remove skill:world-model` refused in `modular_edit`, excluded from `_available`
**Decided by:** agent

## 🏗️ Technical Design

- New `src/harness_maker/world_model_digest.py`: `digest(root: Path, session_id: str|None) -> dict`
  (never raises), `classify_next_stage(...)`, `last_stage_and_session(rows, session_id)`,
  `render(dict) -> str` with the size cap.
- `world_model.py`: `main(argv)` with argparse `digest --root --session-id`; prints JSON; exit 0.
- `hm.py` `_DISPATCHABLE` + `command_registry.MODULES["world_model"]`.
- Router template: briefing = `!` digest (Claude) + fallback line; Codex = one Bash line;
  Resume uses `next_stage` / `other_session`; keep cap, Never-Read, routing rows; flag-OFF note.
- Help en/ko: one router row (`/{handle}` or `$handle`).
- Pointer partial shortened. Interview: locale-aware messages. modular_edit refusal.
- reconcile `_remove_emptied_skill_dir` docstring scope; make.md dispatch test selector.

## 📝 Implementation Plan

### Phase 1 — Digest
- depends_on: none · parallel_group: A · merge_hazards: hm registry
- scope in: `world_model_digest.py` (new), `world_model.py`, `hm.py`, `command_registry.py`, `tests/unit/test_world_model_digest.py`
- exit: `uv run pytest tests/unit/test_world_model_digest.py`
- risk: medium · rollback: drop the module and registrations

### Phase 2 — Router, help, pointer
- depends_on: Phase 1 · parallel_group: B · merge_hazards: snapshots, surface baseline, autopilot golden
- scope in: `templates/skills/world-model/SKILL.md.j2`, `templates/commands/hm/help.{en,ko}.md.j2`, `templates/agents/_partials/world_model_pointer.md.j2`, `tests/render/test_render_world_model_followups.py`
- exit: `uv run pytest tests/render/test_render_world_model_followups.py tests/render/test_render_world_model.py`
- risk: medium · rollback: revert templates

### Phase 3 — Review leftovers
- depends_on: none · parallel_group: B (serial with Phase 2: shared test module)
- scope in: `interview.py`, `i18n_messages.py`, `modular_edit.py`, `world_model.py` (name rule), `reconcile.py` (docstring), `tests/render/test_render_world_model.py` (dispatch selector)
- exit: feature tests green
- risk: low · rollback: revert

### Phase 4 — Retire
- depends_on: 1–3 · scope in: snapshots, golden/baseline re-freeze + BASELINE-DELTA, count/registry tests
- exit: `uv run ruff check . && uv run ruff format --check . && uv run mypy --strict src tests && uv run pytest -n auto`
- risk: low · rollback: re-run regenerate

## 🚧 Contract Boundaries

### Do not change
- `src/harness_maker/templates/stages/` — STOP-text hints are v1.1, out of scope
- `src/harness_maker/templates/harness-yaml/` — `world_model` schema is SPEC-world-model-name IRR-001
- `src/harness_maker/autopilot.py` — read via its public/private readers only (ADR-002)
- `src/harness_maker/stage_spans.py` — consumed, not changed
- `specs/SPEC-world-model-followups.machine.yaml` — approved
- `.claude/` — this repo's rendered harness

## 🧪 Testing Strategy

Unit (`tests/unit/test_world_model_digest.py`): AC-001..006, 009 incl. Hypothesis properties and
a real git worktree for AC-006. Render (`tests/render/test_render_world_model_followups.py`):
AC-007, 008, 010..015. Full suite + mypy on src+tests at Phase 4.

## ⚠️ Risks & Mitigation

| Risk | Mitigation |
|---|---|
| Verification-marker key computation is slow (tool --version subprocesses) | Only when review is done; per task ≤ 5 |
| Help change moves invariance/surface tests | Phase 4 re-freeze with attribution |
| `!` injection unsupported in some runtime | Fallback line (AC-007) |

## ✅ Success Criteria

- [x] AC-001 … AC-015 green
- [x] mypy --strict src tests, ruff, format, full pytest green

## Feedback

| Evidence | Affected ID | Update status | Decision | Owner | Authority | Next action |
|---|---|---|---|---|---|---|
| SPEC S2/S6: artifact-derived resume removes a re-instruction point on every runtime | WORLD-INTENT-CLOSED-LOOP / intent_world_closed_loop_cycles | recorded | verdict yes → 2 (metric record 2026-10-02T05:26Z); intent kept open (2/3) | DRI | DRI | wrapup 5.7 | next task decides cycle 3 |

## Phase status

### Phase 1 — A.5
- Round 1 FAIL (3 blocking: AC-003 lacked newest-REVIEW / stale-marker / PLAN-only cases;
  AC-004 single-row + last_seen; ordering coincided with slug order) — repaired (7 tests, RED).
- Round 2 FAIL (1 blocking: AC-004 newest test passed a first-row-wins impl).
- `stuck`: the newest row coincided with other attributes; fixture rewritten so only the
  timestamp marks it (file order [older, newer, oldest]; stage/event/session decoys).
- **DRI chose Path A (2026-10-02):** one scoped A.5 round on
  `test_ac004_newest_of_several_rows_wins`. **Pre-registered stopping rule: a FAIL there is
  accepted as residual risk and carried to /hm:review; there is no round 4.**

### Phase C note — AC-010 binding
The approved AC-010 predicate starts with an empty answer, which the interview accepts as the
default name, so stdout alone is empty in both locales. `ko_prompts`/`en_prompts` are bound to
everything the operator sees (question prompts + re-prompt messages), and the name/handle
question prompts are now localized (`world_model_prompt_name/handle`) — consistent with S8.
- Superseded tests updated: `test_router_routes_resolve_to_rendered_surfaces` now asserts the
  digest invocation; `test_span_lookup_reads_the_base_ledger_from_inside_a_worktree` (pinned
  the removed prose grep) is replaced by `test_ac006_root_resolves_to_base`.

### Phase D.5 — newly reachable windows (repairs in this task)
| Repair | Window newly reachable | Test (same commit) |
|---|---|---|
| make.md: world-model flags on every `make "$(pwd)"` dispatch (incl. multi-line) | `--ci world_model_name=` on an existing harness (Update path), preset / strictness / second-brain dispatches | `test_ac009_every_dispatch_forwards_world_model_flags` (selector = the make invocation, ≥ 6 blocks) |
| SKILL description YAML-escaped by hand instead of `tojson` | astral-plane names (emoji, 𝔐, U+10000) in the router frontmatter | `test_ac012_names_round_trip` (Hypothesis incl. astral samples) |
| U+FFFE/U+FFFF rejected by `name_rule` | names carrying YAML noncharacters (previously accepted, then unloadable) | `test_ac012_noncharacters_rejected` |
| interview messages via i18n | `ko` interactive name/handle rejections and prompts | `test_ac_010_interactive_messages_follow_locale`, `test_ac010_name_error_is_localized` |
| modular add/remove refusal | `--add/--remove skill:world-model` and `skill:<handle>` | `test_ac_011_modular_add_refused`, `test_ac011_modular_remove_of_router_refused` |
Absent case: a harness.yaml without `world_model` → handle `maker` (refusal and help fall back to it).

### Phases 1–4 — DONE
Digest + `hm world_model digest` (registered, console-script test), router briefing/resume,
pointer, help row, interview locale, noncharacters, modular refusal, make.md forwarding, YAML
description escaping, reconcile docstring. Feature tests green; snapshots regenerated (no
machine paths); autopilot golden (`help` only) and loop-ON (`CLAUDE.md`, `help.md`) re-captured
with dated notes; surface baseline re-frozen with BASELINE-DELTA-world-model-followups.md;
ruff, format, `mypy --strict src tests` clean.

Boundary comparison (28 changed paths): no crossing — `templates/stages/`,
`templates/harness-yaml/`, `autopilot.py`, `stage_spans.py`, the approved machine SPEC and
`.claude/` are untouched.
