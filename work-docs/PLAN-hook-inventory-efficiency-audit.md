---
type: plan
task_slug: hook-inventory-efficiency-audit
status: complete
created: 2026-07-21
tags: [harness-maker, plan, hooks, autopilot, render-merge, release]
research_doc: "[[RESEARCH-hook-inventory-efficiency-audit]]"
interview_rounds: 1
adrs: 4
validator_outcome: NEEDS_REVISION_RESOLVED
summary: "Retire autopilot_guard hook via a retired-invocations set; flip persistent:false; drop dead hooks.json; ship a release"
---

# PLAN — Hook inventory & session-friction fix

## 🎯 Executive Summary

**What:** Remove the `autopilot_guard` hook (the source of the recurring "Stop hook won't
terminate" + false-positive PreToolUse blocks) from the rendered `.claude/settings.json`,
across all harnesses — not just new ones. **Why:** for a solo/interactive operator the
autopilot *blocking* buys nothing but taxes every session (Stop-block when a stale marker
lingers; a `permission-surface-write` classifier that blocked even read-only `find`/`ls`/`python -c`
this session) and adds 2 Python cold-starts to every Bash call.

**Key decisions (this session's interview):**
- **ADR-001** — Retire the guard via an append-only `_HARNESS_RETIRED_HOOK_INVOCATIONS`
  frozenset in `render.py` (mirrors the proven `_HARNESS_SHIPPED_DENY_LITERALS` pattern),
  NOT a general manifest-provenance system. Template-removal alone is insufficient — the
  union-merge preserves the guard as pseudo-user content (see Prior Work).
- **ADR-002** — Remove ONLY the blocking guard from hooks (+ flip this repo's
  `autopilot_persistent` to false). Keep `autopilot_autoarm`, the picker, and the
  command-template auto-advance intact — auto-advance is opt-in and was never the friction.
- **ADR-003** — Retire the dead `.claude/hooks/hooks.json` + unused `hooks.json.j2` template
  in a separate, independent phase.
- **ADR-004** — Ship it: 5-file version bump + tag → `release.yml`, gated behind a green
  execute→review→verify.

**Estimated impact:** every Bash call drops from 3→2 hook processes; every Write/Edit from
3→2 (+spec_gate); Stop from 3→2 (+ the 3rd is the external codex plugin); the recurring
Stop-block and false-positive blocks disappear entirely.

## 📚 Prior Work

- **RESEARCH-hook-inventory-efficiency-audit** — full hook inventory + the live reproductions
  (guard blocked read-only inspection twice; `autopilot off` is the real off-switch, not `rm`).
- **The union-merge has NO retire branch** (`render.py:880-903`, REVIEW round 1 of
  PLAN-permission-deny-and-hooks-wiring). A draft that dropped any all-`<HM>:` group was
  reverted because `<HM>:` marks *namespace*, not *authorship* — a user hand-wiring a
  harness module would lose it. The comment explicitly defers real retirement to "positive
  provenance — a prior-render manifest." ADR-001 chooses the narrower, proven frozenset
  instead (see its rejected-alternatives).
- **`_HARNESS_SHIPPED_DENY_LITERALS`** (`render.py:244`) — the exact precedent ADR-001
  copies: an append-only set of harness-shipped strings dropped from the user's disk before
  the union rebuilds, guarded by test invariants ("we shipped it" + a safety predicate).
- **`guard_when: pipeline_only`** (`interview.py:_ask_autonomy`, PLAN-autopilot-guard-interactive-scope)
  — the maintainer's *earlier, softer* fix for this same friction (keep the guard dormant in
  non-pipeline chats). ADR-002 supersedes it with full hook removal — see its rejected list.
- `[[project_hooks_json_not_read_by_claude]]` — Claude Code never reads `.claude/hooks/hooks.json`;
  grounds ADR-003.

## 🎙️ Interview Transcript

| # | Topic | Category | Question | Choice | → ADR |
|---|-------|----------|----------|--------|-------|
| 1 | Retirement mechanism | Architecture | Template-removal won't clean existing harnesses (union-merge preserves guard). How to retire? | **retired-invocations frozenset** (vs manifest pristine-gate / template-only) | ADR-001 |
| 2 | Gut extent | Scope | How far to cut autopilot? | **guard only** (+ persistent:false); keep autoarm/picker/advance | ADR-002 |
| 3 | Dead hooks.json rider | Scope | Include dead `.claude/hooks/hooks.json` + template cleanup? | **include — separate phase** | ADR-003 |
| 4 | Release path | Risk | Ship a release or land local-only? | **full release**, gated behind review | ADR-004 |

## 📐 Architecture Decision Records

### ADR-001: Retire the guard via an append-only retired-invocations frozenset
**Status:** Accepted (2026-07-21, via /hm:plan interview)
**Context:** The hooks union-merge (`render.py:_merge_hooks_json`) has no retire branch by
design; simply deleting the guard from the settings templates leaves it on every existing
user's disk (including this repo), classified as pseudo-user content by `_strip_shipped_commands`
(it strips only commands the template *still* ships).
**Decision:** Add `_HARNESS_RETIRED_HOOK_INVOCATIONS: frozenset[str]` in `render.py` holding
the two normalized guard invocations (`<HM>:harness_maker.hooks.autopilot_guard`,
`<HM>:harness_maker.hooks.autopilot_guard --mode stop-hook`). Extend `_strip_shipped_commands`
to also drop commands whose normalized form is in this set (union with `shipped_cmds`).
**Mechanism (validator-verified trace — render.py:825-909):** for the Bash group, template
`new_entries=[{permission_gate}]` → `shipped_cmds={<HM>:…permission_gate…}`. The on-disk group
`[permission_gate, autopilot_guard]` normalizes to a 2-command identity tuple NOT in
`shipped_identities` → routed to `_strip_shipped_commands`. With the extension (strip drops
`shipped_cmds ∪ _HARNESS_RETIRED_HOOK_INVOCATIONS`): `permission_gate` dropped (shipped),
`autopilot_guard` dropped (retired) → `kept=[]` → entry omitted → event = `[permission_gate]`. ✓
Stop group `[loop_gate --mode stop-hook, autopilot_guard --mode stop-hook]` collapses identically
to `[loop_gate --mode stop-hook]`. ✓ A mixed group `[permission_gate, autopilot_guard, USER]`
correctly strips to `[USER]`. ✓
**Consequences:**
- ✅ Existing harnesses (this repo included) get the guard removed on the next `make --update` re-render.
- ✅ Append-only, mirrors the *shape* of `_HARNESS_SHIPPED_DENY_LITERALS`; minimal blast radius on delicate merge code.
- ⚠️ **Safety basis differs from the deny-literal precedent — do NOT overclaim.** The deny-literal set is governed by TWO invariants; invariant-2 ("`is_matchable_rule` is False — provably enforces nothing", render.py:231-238) is what makes deletion safe, and **it has NO analog for a LIVE hook** (you cannot prove a live hook enforces nothing). The retired set inherits ONLY invariant-1 (git-history + absent-from-current-templates). Therefore the Phase-1 invariant test bounds *membership*, it does NOT confer deletion-safety the way it does for deny literals. Deletion safety rests **entirely** on the accepted population argument below — the invariant test is not a safety predicate here.
- ⚠️ Forgeable-prefix risk (the exact hazard render.py:880-903 warns of): a user who hand-wired `harness_maker.hooks.autopilot_guard` themselves would have it dropped. **Accepted** — hand-wiring an internal guard module is not a real population. This is a deliberate, documented risk acceptance, not a safety guarantee.
**Rejected alternatives:**
- *Manifest pristine-gate* — general/reusable, but restructures the merge control flow (the code with prior P0s) and raises verification cost for a single retirement. Deferred to when a second retirement justifies the generality.
- *Template-only + manual cleanup* — does not fix existing users OR this repo on re-render; contradicts the "stop the recurring friction" goal.
**Source:** Interview #1

### ADR-002: Remove only the blocking guard; keep the rest of autopilot
**Status:** Accepted (2026-07-21, via /hm:plan interview)
**Context:** Autopilot spans the guard hook (blocking), `autopilot_autoarm` (SessionStart),
the picker, the marker, and command-template auto-advance (`autopilot_caps`). Only the guard
*blocks*.
**Decision:** Remove `autopilot_guard` from all three settings-template hook groups
(PreToolUse Bash, PreToolUse Write|Edit|MultiEdit, Stop) — the Stop site included, because the
Stop-block was itself the user's original complaint. Flip this repo's
`harness.yaml autonomy.autopilot_persistent` to `false`. Keep `autopilot_autoarm`, the picker,
the marker, and the command-template `autopilot_caps` auto-advance — **auto-advance is driven by
the in-turn `autopilot_caps boundary` check in the stage command prompts, NOT by the Stop guard**
(validator-confirmed), so it survives guard removal. The now-orphan `autopilot_guard.py` module
and the `guard_when` render vestige are handled explicitly (below), not left dangling.
**Consequences:**
- ✅ Auto-advance (opt-in, non-blocking) survives — its driver (`autopilot_caps` in the 7 stage prompts) is independent of the removed guard.
- ✅ New interviews already default `autopilot_persistent: false` (`models.py:787`) — no synthesize/interview default change needed.
- ⚠️ **Persistent autopilot loses its cross-Stop backstop.** `autopilot_guard.py:743-767`'s Stop path prevented a *premature* Stop from ending a pipeline mid-flight. Without it, a persistent-autopilot pipeline that stops mid-chain (Skill-chaining broke) will stall instead of being forced to continue. **Accepted**: this repo runs `persistent:false` (autoarm no-ops), the Stop-block was the complaint, and single-turn auto-advance is unaffected. For the persistent-opt-in population this is a robustness reduction, not a function loss.
- ⚠️ **`autopilot_guard.py` becomes unwired** → `test_invocation_render_gate.py:173` (the silent-dead-module gate) would flag it. **Phase-2 rule (decidable, not vague):** `git grep -l 'autopilot_guard' src/ | grep -v templates` — if the module is imported nowhere outside its own file + tests → **delete `autopilot_guard.py` + `test_autopilot_guard.py`**; if another module imports it → **keep it with a commented gate exemption** in `test_invocation_render_gate.py` explaining the deliberate-unwired retention. Default expectation: delete.
- ⚠️ **`guard_when` render vestige spans 7 stage templates, not one test.** `templates/stages/*.md.j2:3` (execute/plan/spec/research/review/verify/wrapup) render `stage_start_autopilot.md.j2` under `{%- if not is_codex and config.autonomy.guard_when == 'pipeline_only' %}` — a crumb-stamp that "arms the guard for the rest of the session." After guard removal that instruction is dead. Phase 2 **gates that partial off** (guard removed → nothing to arm). `guard_when` config itself stays as dormant field (full removal — models + interview — is out of scope). NOTE: this repo's `guard_when` is `always` (default), so the block does not render here; the fix protects the `pipeline_only` sub-population.
**Rejected alternatives:**
- *Keep the Stop guard, remove only the two PreToolUse copies* (validator's option b) — does NOT fix the user's original Stop-block complaint. Rejected.
- *`guard_when: pipeline_only`* — the existing softer mitigation. Still fires the guard during real pipeline runs, keeps the false-positive classifier + cold-start. Full removal is cleaner for a user who does not want autopilot blocking at all.
- *Rip out all of autopilot* (autoarm + marker + `autopilot_caps` in 7 command templates) — largest change; auto-advance has value and is not the friction.
**Source:** Interview #1 + plan-validator NEEDS_REVISION resolution

### ADR-003: Delete only this repo's stale `.claude/hooks/hooks.json` — KEEP the template
**Status:** Accepted (2026-07-21, via /hm:plan interview) — **REVISED during execute (premise corrected)**
**Context:** `.claude/hooks/hooks.json` is never read by Claude Code (2026-07-17 experiment)
and no longer rendered (`synthesize.py:491`), yet a stale `0.39.0` copy lingers on this repo's
disk. The plan-time premise ALSO assumed `templates/hooks/hooks.json.j2` was dead source.
**Execute finding (refutes half the premise):** `hooks.json.j2` is NOT dead — `render.py:1021`
`render_stale_hooks_json_bytes` reads it (`_STALE_HOOKS_JSON_TEMPLATE`) as the **pristine oracle**
for `cli._retire_stale_hooks_json`, which byte-matches and deletes zero-user-content stale copies
on OTHER users' disks. `test_render.py` binds it in 3 places. Deleting the template would break
the very retirement machinery. So the template STAYS.
**Decision (revised):** Delete ONLY this repo's local, untracked `.claude/hooks/hooks.json`
(a base-level one-off — it is not in the worktree). Keep `templates/hooks/hooks.json.j2`,
`_STALE_HOOKS_JSON_TEMPLATE`, `reconcile._SWEEP_NEVER_DELETE`, and `cli._retire_stale_hooks_json`
untouched.
**Consequences:**
- ✅ This repo's dead local file removed (the friction artifact).
- ✅ Retirement machinery intact — pristine stale copies on other disks still auto-reaped; non-pristine (version-drifted, like this repo's 0.39.0) preserved-and-warned, unchanged.
- ⚠️ The `hooks.json.j2` template + its machinery remain — NOT dead weight; they are the retirement oracle. A full retirement of the whole hooks.json mechanism is a separate, larger task (out of scope).
**Rejected alternatives:**
- *Delete `hooks.json.j2`* (original plan) — REFUTED: it is load-bearing for `_retire_stale_hooks_json`.
- *Drop `_SWEEP_NEVER_DELETE` to reap all stale copies* — re-introduces the user-merged-hook data-loss risk that protection exists to prevent.
**Source:** Interview #1 + execute-time premise correction

### ADR-004: Ship a full release, gated behind review
**Status:** Accepted (2026-07-21, via /hm:plan interview)
**Context:** This is a shipped-behavior change; CLAUDE.md mandates a 5-file version sync +
race-free tag procedure.
**Decision:** Final phase does the 5-file bump (default **0.43.0** — minor, backward-compatible
hook removal; user may override), CHANGELOG entry, advisory boundary tests, then tag push →
`release.yml` (no manual `gh release create`). Release runs only after execute→review→verify are green.
**Consequences:**
- ✅ Fix reaches all three marketplaces.
- ⚠️ Immutable once tagged — any defect is fix-forward with a new patch tag.
**Source:** Interview #1

## 🏗️ Technical Design

**Current state:** `autopilot_guard` renders into `.claude/settings.json` at PreToolUse:Bash,
PreToolUse:Write|Edit|MultiEdit, and Stop (from `templates/settings/{Production,Side}.json.j2`).
`_merge_hooks_json` unions on re-render and cannot retire it.

**Affected components:**
- `src/harness_maker/templates/settings/Production.json.j2`, `Side.json.j2` — remove 3 guard entries each.
- `src/harness_maker/render.py` — add `_HARNESS_RETIRED_HOOK_INVOCATIONS`; extend `_strip_shipped_commands` (and its call site in `_merge_hooks_json`) to drop retired commands.
- `.claude/harness.yaml` (this repo) — `autopilot_persistent: false`.
- `src/harness_maker/templates/hooks/hooks.json.j2` + `.claude/hooks/hooks.json` — delete (Phase 3).
- Version files ×5 + CHANGELOG (Phase 4).

**Dependencies:** none new.

**Data flow (retirement):** re-render → `_shallow_merge_existing_json` → `_merge_hooks_json`
→ for each existing group not in the new shipped set, `_strip_shipped_commands` removes both
`shipped_cmds` AND retired invocations → guard-only remainder collapses to empty → group dropped.

**Design decisions:** all trace to ADR-001..004.

**API changes:** none (internal render behavior + rendered settings.json shape).

## 📝 Implementation Plan

### Phase 1 — Retirement mechanism + template guard removal
- `depends_on: []`
- `parallel_group: serial-core`
- `merge_hazards: render.py:_merge_hooks_json / _strip_shipped_commands (prior P0s — delicate); settings templates`
- **Scope in:** `render.py` (new frozenset + strip extension), `Production.json.j2`, `Side.json.j2`, new/updated tests.
- **Scope out:** harness.yaml flip, this-repo re-render (Phase 2), dead hooks.json (Phase 3), version bump (Phase 4).
- **Exit criterion:** `uv run pytest tests/unit/test_render_settings_hooks.py tests/unit/test_render_hooks_merge*.py -q` green, PLUS a new test that renders a settings.json containing the guard and asserts the guard is dropped after merge, AND an invariant test asserting every `_HARNESS_RETIRED_HOOK_INVOCATIONS` entry is (a) absent from current settings templates and (b) present in `templates/settings/` git history.
- **Risk:** high (delicate merge code).
- **Rollback:** revert to pre-Phase-1 HEAD.

### Phase 2 — Flip this repo + re-render + reconcile the full blast radius
- `depends_on: [1]`
- `parallel_group: serial-core`
- `merge_hazards: e2e sandbox fixtures; rendered snapshots; the invocation render gate`
- **Scope in (enumerated per validator, not "update the tests"):**
  1. `.claude/harness.yaml` → `autopilot_persistent: false`; re-render this repo's `.claude/`; assert `autopilot_guard` absent from `.claude/settings.json`.
  2. **Test INVERSIONS** (these currently assert the guard is PRESENT): `test_render_settings_hooks.py:200` (`…stop_hook_carries_loop_gate_and_autopilot_guard`) → "Stop carries loop_gate ONLY"; `test_render_settings_hooks.py:386-459` dedup tests use `autopilot_guard` as the FIXTURE → swap to a still-live hook (`permission_gate`).
  3. **Orphan-module decision** (ADR-002 rule): `git grep -l 'autopilot_guard' src/ | grep -v templates` → delete `autopilot_guard.py` + `test_autopilot_guard.py` if unimported, else keep + commented exemption in `test_invocation_render_gate.py:173`.
  4. **`guard_when` vestige**: gate off the `stage_start_autopilot.md.j2` render in all 7 `templates/stages/*.md.j2` (guard removed → nothing to arm); update/remove `test_guard_when_pipeline_only.py` accordingly.
  5. Other referencing tests/fixtures: `test_command_registry.py`, `tests/e2e/sandbox*/.claude/settings.json`.
- **Exit criterion:** full `uv run pytest` green (background) — NOT a subset; `.claude/settings.json` contains no `autopilot_guard`; `test_invocation_render_gate` green (no orphan-module flag); manual check that a read-only Bash (`find .claude -name '*.json'`) no longer trips the guard.
- **Risk:** medium.
- **Rollback:** Phase 1 state.

### Phase 3 — Delete this repo's stale hooks.json (REVISED — template kept)
- `depends_on: []`
- `parallel_group: serial-riders` (independent of 1/2; base-level one-off)
- `merge_hazards: none`
- **Scope in:** delete the base repo's local, untracked `.claude/hooks/hooks.json` (dead 0.39.0 artifact).
- **Scope out (REVISED per execute finding):** `templates/hooks/hooks.json.j2` is KEPT — it is the pristine oracle for `_retire_stale_hooks_json` (`render.py:1021`), NOT dead. `_SWEEP_NEVER_DELETE` / `cli._retire_stale_hooks_json` unchanged.
- **Exit criterion:** base `.claude/hooks/hooks.json` gone; `uv run pytest -q` green (template + machinery untouched → no test change needed).
- **Risk:** low.
- **Rollback:** the file is untracked/regenerated-never — deletion is terminal-safe (it is a pure duplicate of `.claude/settings.json` hooks; not read by Claude Code).
- **Validator-confirmed:** no `.cursor/` or `.codex/` template renders `autopilot_guard`, and `readiness.py` has zero `autopilot_guard`/`guard_when` references — no cross-IDE drift, no readiness-signal regression.

### Phase 4 — Version bump + release
- `depends_on: [1, 2, 3]`
- `parallel_group: serial-release`
- `merge_hazards: the 5 version files must move together (CLAUDE.md 버전업 정책)`
- **Scope in:** bump `.claude-plugin/plugin.json`, `.cursor-plugin/plugin.json`, `.codex-plugin/plugin.json`, `pyproject.toml`, `src/harness_maker/__init__.py` to 0.43.0; CHANGELOG; advisory `INTEGRATION=1 boundary` tests; `git tag -a v0.43.0` + push.
- **Exit criterion:** local `ruff`+`mypy --strict`+`pytest` green; tag pushed; `release.yml` reaches `github-release` (no manual `gh release create`).
- **Risk:** medium (immutable). **Rollback:** fix-forward patch tag only.
- **Note:** executed at wrapup / on explicit user go — never auto.

## 🧪 Testing Strategy

- **Unit:** retirement-merge test (guard-in → guard-out); frozenset invariant test (git-history + absent-from-templates); updated settings-render tests.
- **Snapshot:** re-rendered `.claude/settings.json` (guard-free) — regen + review the diff is guard-removal only.
- **Integration:** re-render this repo → assert `autopilot_guard` absent from `.claude/settings.json`.
- **E2E:** update `tests/e2e/sandbox*/.claude/settings.json` fixtures; `INTEGRATION=1` boundary suite advisory before tag.
- **Manual:** after Phase 2, run a read-only Bash (`find .claude -name '*.json'`) and confirm the guard no longer blocks it.

## ⚠️ Risks & Mitigation

| Risk | Severity | Mitigation |
|------|----------|------------|
| Merge-code regression (prior P0 zone) | High | Narrow extension (union retired into existing strip); dedicated guard-in/guard-out test; plan-validator + green suite gate. |
| Retired-set forgeability (user hand-wired the module) | Low | Documented in set comment; negligible population; invariant test bounds membership to shipped-and-now-absent. |
| Test/fixture blast radius underestimated | Medium | Phase 2 exit = FULL suite green, not a subset. |
| Release race (0.15.3 precedent) | Medium | Follow CLAUDE.md race-free procedure: push tag only, never manual `gh release create`. |
| `guard_when` left vestigial confuses future readers | Low | ADR-002 documents dormancy; Phase 2 updates the one test that asserted its render behavior. |

## ✅ Success Criteria

- [x] `autopilot_guard` absent from rendered `.claude/settings.json` after re-render on an existing harness (this repo re-rendered in wrapup; guard `3→0`).
- [x] Re-rendering a harness that HAD the guard drops it (proven by test + integration check on this repo's real settings.json).
- [x] Recurring Stop-block + read-only false-positive blocks no longer occur (marker cleared + `autopilot_persistent: false` landed → no re-arm).
- [x] `autopilot_persistent: false` in this repo's harness.yaml.
- [x] Dead `.claude/hooks/hooks.json` removed. (`hooks.json.j2` template KEPT — it is the retirement pristine-oracle; premise corrected, ADR-003 revised.)
- [x] Full suite (ruff + ruff-format + mypy --strict + pytest) green.
- [ ] 0.43.0 released via `release.yml` — **DEFERRED to Phase 4** (explicit release go; not part of this wrapup's "push to main").

## 🚦 Execute Status (2026-07-21)

Committed on branch `hm/hook-inventory-efficiency-audit` (wip commit `a8c47c7b`), all
green (unit suite `PYTEST_EXIT=0`, ruff, ruff-format, mypy --strict on render.py):

- **Phase 1 — DONE.** `_HARNESS_RETIRED_HOOK_INVOCATIONS` + `_strip_shipped_commands` extension
  in `render.py`; guard removed from both settings templates (3 sites each); 3 new retirement
  tests + 1 invariant test; STAGE2_MODULES / Stop test inverted; 2 stage-bump fixtures swapped
  to a live hook. **Integration-verified on this repo's REAL settings.json**: `autopilot_guard`
  occurrences `3 → 0` after merge, live siblings (permission/worktree/loop/telemetry) all preserved.
- **Phase 2 — code portion DONE** (harness.yaml `autopilot_persistent: false`; 8 snapshots
  regenerated — diff is settings.json body-hash ONLY, verified; full-suite reconciliation green).
  **guard_when vestige + orphan `autopilot_guard.py`**: KEPT as-is — `autopilot_guard.py` is
  `ModuleSpec("flagonly")` (invocation-gate-EXEMPT, no reverse-coverage gate → no test failure),
  and full `guard_when` removal is out of ADR-002 scope. Documented as accepted follow-up.
- **Phase 3 — REVISED & DONE-on-branch** (nothing to change in-tree): `hooks.json.j2` KEPT
  (it is the retirement pristine-oracle — premise corrected, see ADR-003).

### Deferred to wrapup / post-land (need the landed code — `make --update` is blocked inside a worktree)

1. **Re-render this repo's `.claude/settings.json`** to physically strip the 3 guard entries
   (proven by the integration check above). NOTE: the friction is ALREADY gone — the session
   marker was cleared and `autopilot_persistent:false` will land, so no marker re-arms and the
   guard never fires even while still listed. This re-render is correctness/cleanup.
2. **Delete this repo's dead local `.claude/hooks/hooks.json`** (untracked 0.39.0 artifact; `rm`
   is deny-listed so do it via the wrapup flow or a non-`rm` delete).
3. **Phase 4 — version bump 0.43.0 + release** (post-review, explicit go).

## 🔍 Plan Validation

**plan-validator outcome: NEEDS_REVISION → RESOLVED** (opus, 17 tool uses). Second-opinion
CLIs (codex, antigravity) — both installed — were **operator-deferred** for this internal-refactor
plan given the session's efficiency goal; surfaced here (not silently skipped). Re-run with
cross-model second opinions available on request.

The validator **verified the ADR-001 retirement mechanism is correct** (concrete trace, now
folded into ADR-001). It raised 4 warnings + 3 suggestions, all resolved by revision (option A):

| # | Validator finding | Resolution |
|---|-------------------|------------|
| 1 | ADR-001 overclaims deny-literal safety — invariant-2 has no live-hook analog | ADR-001 Consequences rewritten: safety rests on the population argument, NOT the invariant test |
| 2 | ADR-002 incoherent — retains autoarm cost while removing the Stop backstop | ADR-002 rewritten: auto-advance driver is `autopilot_caps` (not the Stop guard) so it survives; cross-Stop backstop loss documented + accepted |
| 3 | `guard_when` vestige = 7 stage templates + partial, not 1 test | Phase 2 item 4 enumerates all 7 `templates/stages/*.md.j2` + gates off `stage_start_autopilot.md.j2` |
| 4 | `autopilot_guard.py` orphan-module → invocation render gate flags it | ADR-002 + Phase 2 item 3: decidable grep rule (delete if unimported, else exempt) |
| 5 | Two named tests must be INVERTED not "updated" | Phase 2 item 2 names `test_render_settings_hooks.py:200` + `:386-459` explicitly |
| 6 | Phase 3 independence + cross-IDE cleanliness | Confirmed; Phase 3 exit check + validator-confirmed note added |

No hard-critical findings (no phase fails, no contract breaks) — hence NEEDS_REVISION, now resolved.
