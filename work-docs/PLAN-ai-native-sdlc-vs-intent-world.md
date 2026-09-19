---
type: plan
task_slug: ai-native-sdlc-vs-intent-world
status: complete
created: 2026-09-19
tags: [harness-maker, plan, python, jinja2, dri, spec-approval, autopilot, land-hold]
spec: "[[SPEC-ai-native-sdlc-vs-intent-world]]"
research_doc: "[[RESEARCH-ai-native-sdlc-vs-intent-world]]"
interview_rounds: 7
adrs: 8
validator_outcome: MAJOR_REVISION_RESOLVED
summary: "Hash-bound SPEC approval + nine-row state table, spec autopilot gate, land hold at 3 Python entries"
spec_need_verdict: add
spec_need_target: ai-native-sdlc-vs-intent-world
---

# PLAN — DRI acceptance: SPEC approval, irreversible decisions, land hold

## 🎯 Executive Summary

**TL;DR:** One state function in `spec_machine.py` decides, for a task's SPEC, a state out of a
nine-row table (`no_spec / malformed / invalid / exempt / approved / legacy / missing`) from a
deny-list content hash. Three consumers read it: the `approval-status` CLI, the autopilot spec
boundary (which no longer trusts the stage's own `clear`), and the three Python land entries
(`wrapup_land`, `worktree task-land`, `worktree finalize` success). Templates add the approval
act (the interview's final option), the Step 0 exemption, the irreversible-decision list, the
execute escalation rule and the wrapup approve-or-keep question.

**What / Why:** SPEC-ai-native-sdlc-vs-intent-world (approved, revision 1). The DRI's acceptance
of a SPEC becomes a recorded, content-bound fact, and nothing lands past an unaccepted SPEC
that carries irreversible decisions.

**Key decisions:** ADR-001 logic stays in `spec_machine.py` · ADR-002 deny-list hash · ADR-003
one state function + checkout resolution · ADR-004 boundary derives the spec gate · ADR-005 land
hold at three Python entries · ADR-006 approval UX + no-answer = hold · ADR-007 surface allowance
P4→P5 · ADR-008 `SCHEMA_VERSION` 3 with the templates.

**Impact:** ~+350 lines Python, 4 stage templates (spec, execute, wrapup, loop) + one partial,
4 new test files, golden/snapshot/round-trip regeneration. `plan` and `review` renders are
unchanged.

### Non-Goals (PLAN level; the SPEC's list also applies)
- Single-sourcing `_JUDGMENT_GATED_STAGES` into the render context (ADR-004 rejected refactor).
- Any change to the SPEC `status` field's semantics.
- Removing `/hm:plan` or `dev_mode`; vocabulary renames; `owners` roles.
- Fixing the broken mutation gate.

## 📚 Prior Work

- `world.py:1483-1503` objective `approve`: base-root identity, hash over record fields — the
  precedent for the stamp shape and the identity rule.
- `autopilot_caps.py:470-545` judgment gate + `auto_full` directive; the absent-flag rule
  (absence is un-clearable) is kept.
- `tests/render/test_judgment_gate_surface.py:42` already enforces parity between
  `_JUDGMENT_GATED_STAGES` and the rendered flag — updating both is mandatory.
- `PLAN-mission-context-loop.md` ADR-006: allowance declared in the growth phase, retired in the
  last phase with a BASELINE-DELTA doc; invariance tests pin plan/review.
- Memory: `[fail:process] peer-lands-mid-task-shared-files` (a peer landed during this task's
  planning — rebased at 7009771d); `project_rendered_harness_pins_released_plugin` (dogfood
  stages run 0.57.1 until release); `[fail:tooling] mutation-gate…` (mutmut collects 0 mutants
  — T1 mutation evidence will be manual).
- RESEARCH §"Codex cross-model review" — the source of the SPEC's revision 1.

## 🎙️ Interview Transcript

| # | Topic | Category | Question (1 line) | Options | Choice | Note | → ADR |
|---|---|---|---|---|---|---|---|
| 1 | Scope | Scope | SPEC scope | 1 / 1+2 / 1+2+withdrawal | 1+2 | spec Round 1 | — |
| 2 | auto_full | Contract | Unapproved SPEC under auto_full | pass w/o stamp / always stop / stamp for user | pass w/o stamp | spec Round 1 | ADR-004 |
| 3 | Approval act | UX | How a human approves | final interview answer / extra question / CLI only | final answer | spec Round 1 | ADR-006 |
| 4 | Escalation | Contract | Execute finds an irreversible decision | append→invalid / stop & ask / PLAN only | append→invalid | spec Round 2 | ADR-005 |
| 5 | Land hold | Risk | Enforcement point | templates + Python land entries / templates / split scope | templates + Python | after Codex review | ADR-005 |
| 6 | Revision | Scope | Accept Codex-driven SPEC revision ①–⑨ | all + re-approve / partial | all + re-approve | SPEC revision 1 | ADR-002/003/004 |
| 7 | Objective | Scope | Which objective | none / LOOP-OPT-IN / draft | none | Step 0.5 | — |
| 8 | Proceed | Scope | Case A lock-in | proceed / wait for surveys / arch questions | wait → surveys → Codex → proceed | Step 3.0 | — |
| 9 | C1 loop SPEC set | Contract | Which SPEC does loop finalize check | branch-diff SPEC set / slug required / accept risk | branch-diff SPEC set | validator critical | ADR-005 |
| 10 | C3 hash policy | Contract | Unknown keys + new defaulted fields | exclude_defaults + keep/hash unknown / reject unknown at v3 | exclude_defaults + keep/hash | validator + Codex | ADR-002 |
| 11 | C2/C4/C5/C6/C7/C9 | Mixed | Mechanical fixes bundle | all / some | all | validator | ADR-003/004/005/007 |
| 12 | C8/C10/C11 | Scope | SPEC → v3 with IRR list; stamp procedure; squash message; Non-Goals | all + re-approve / some | all + SPEC re-approved | validator | ADR-005 |

Defaults stated in the design brief and not contested: new fields are model fields (round-trip
safety); the partial's hard-coded stage list is updated in place (single-sourcing it is out of
scope); the land check precedes the Step 7 commit; the exemption is valid only with an empty
list.

## 📐 Architecture Decision Records

### ADR-001: Approval logic lives in `spec_machine.py`, not a new module
**Status:** Accepted (2026-09-19, via /hm:plan)
**Context:** The approved SPEC's `paths_to_mutate` names `spec_machine.py` and
`autopilot_caps.py`; the SPEC's own rule makes any edit to it an approval change.
**Decision:** Put the model fields, hash, state table and approve/status functions in
`spec_machine.py`; land entries and the boundary import them.
**Consequences:**
- ✅ The approved SPEC stays byte-valid; mutation scope matches the code.
- ⚠️ `spec_machine.py` grows from 1,518 lines by ~250.
**Rejected alternatives:**
- New `spec_approval.py` — rejected because it would require editing the approved SPEC's
  `paths_to_mutate` (a re-approval for a layout choice).
**Source:** Interview #6

### ADR-002: Deny-list content hash
**Status:** Accepted (2026-09-19, via /hm:plan)
**Context:** An allow-list missed `rubric_id` and `judgment_subject_paths` (Codex).
**Decision:** Both `SpecMachine` and `AcceptanceCriterion` get `model_config =
ConfigDict(extra="allow")` so unknown keys round-trip. `content_hash =
sha256(canonical_json(model_dump(mode="json", exclude_defaults=True)))` after removing
top-level `approval, spec_quality_score, spec_quality_score_at, last_mutation_run` and per-AC
`test_ids, pending_test, judgment_verdict, judged_at, judgment_evidence, judgment_subject_hash`.
Extras are included (hashed). `schema_version` is hashed (a v3→v2 downgrade invalidates).
Canonical JSON = sorted keys, no whitespace, UTF-8 (reuse `world.canonical_json` if its
contract matches, else a local one).
**Consequences:**
- ✅ Authored keys the model does not know are still hashed; adding a defaulted field in a
  later release leaves existing hashes unchanged (regression test with a subclassed model).
- ⚠️ A field explicitly set to its default hashes like an absent one (acceptable: same meaning).
- ⚠️ `extra="allow"` makes stray keys in existing machine.yaml files persist through
  `mark_tested` instead of being dropped.
- ⚠️ A future tooling-written field must join the deny-list or tooling will invalidate approvals.
**Rejected alternatives:** allow-list (Codex); plain `model_dump` (drops unknown keys, and a new
defaulted field invalidates every approval — validator C3); rejecting unknown keys at v3
(breaks mixed plugin versions); hashing SPEC.md prose.
**Source:** Interview #6, #10

### ADR-003: One state function, nine rows, one checkout rule
**Status:** Accepted (2026-09-19, via /hm:plan)
**Context:** CLI, boundary and three land entries must agree; the SPEC may live in `<WT>`.
**Decision:**
- `approval_state(base: Path, slug: str, checkout: Path | None = None) -> ApprovalState`
  (dataclass: `slug, state, land: "ok"|"hold", gate: "clear"|"pending"|"blocked",
  irreversible: list[str]` ids, `notice: str|None`). Checkout = explicit `checkout` if given,
  else `<base>/.worktrees/<slug>` if it exists, else `base`.
- `land_states(base: Path, checkout: Path, slugs: list[str] = []) -> list[ApprovalState]` for
  land entries: the union of `slugs` and every `specs/SPEC-*.machine.yaml` (and `SPEC-*.md`
  without a machine file, row 2) that `git diff --name-only <merge-base>..HEAD` plus
  `git status --porcelain` shows changed in `checkout`; empty set → `[]` (land ok).
- Spec dir from `harness.yaml spec.dir` (default `specs/`) via the existing config loader.
- Null policy: the state function reads through the model; `None` = absent for `approval` and
  `irreversible_decisions`; an invalid `approval` block fails `load` → row 2 (`malformed`).
  `_dump_machine_yaml` omits both keys when `None` (legacy files keep their shape).
- Rows evaluated in the SPEC's order. Every consumer calls these two functions.
**Consequences:**
- ✅ One table test covers all consumers; the loop's `execute-<uuid>` checkout is read
  directly; a leftover same-slug task worktree cannot shadow it.
- ⚠️ `land_states` needs git in the checkout; no git → "cannot enumerate" → **hold**
  (`hold: SPEC * is malformed … (git could not list the branch's SPECs)`).
  *Amended 2026-09-19 at review (DRI decision, Codex finding `ca2104efdf3aa515`):* this said
  "fall back to `slugs` only, with a stderr notice". On the finalize path `slugs` is empty, so a
  git failure dropped every check. An unknown SPEC set now holds.
- Spec dir: the **base's** configured dir is searched first, then the checkout's; a value that is
  absolute or contains `..` falls back to `specs/` (review confirm-1 P0 / confirm-2 P1). Change
  sets are listed with `-z` so non-ASCII SPEC names are seen.
**Rejected alternatives:** per-consumer checks; name-based checkout only (validator C2).
**Source:** Interview #6, #9, #11

### ADR-004: The spec boundary derives its gate from the SPEC
**Status:** Accepted (2026-09-19, via /hm:plan)
**Context:** The boundary trusts the caller's `--judgment-gate` (Codex).
**Decision:** Add `spec` to `_JUDGMENT_GATED_STAGES`. For `--current spec` with a resolvable
slug, compute `derived = approval_state(...).gate` and use the more restrictive of
(caller flag, derived) on the ladder `clear < pending < blocked`; an absent caller flag keeps
the existing un-clearable-everywhere rule. `auto_full` answers `pending` (writes
`gate_auto_answered`) and the directive for `spec` says "do not write an approval; the land
hold covers irreversible decisions". No slug → derived = `pending`.
**Placement:** the effective verdict is computed right after slug resolution
(`autopilot_caps.py:417-434`) and **before** the `blocked` check at `:470`, so a derived
`blocked` (malformed) halts at every level instead of reaching the `auto_full` auto-answer
branch at `:483-490`; the absent-flag case stays distinct (un-clearable).
The template half — `stage_end_summary.md.j2:35` → `["plan", "review", "spec"]` and the spec
gate text at `spec.md.j2:368` — ships in **P4** with the other render changes (validator C6),
so no phase renders judgment-gate prose next to "No mandatory gate".
**Consequences:**
- ✅ A stage cannot talk the boundary past an unaccepted SPEC.
- ⚠️ `auto_safe` sessions whose spec interview ended without approval now stop at spec.
**Rejected alternatives:** trust the caller (Codex finding); single-source the stage list from
Python into the render context (right fix, separate refactor).
**Source:** Interview #2, #6

### ADR-005: Land hold at three Python entries, pre-asked by the templates
**Status:** Accepted (2026-09-19, via /hm:plan interview)
**Context:** Land paths: `wrapup_land` (worktree on/off commit), `task-land` (captures pending
edits before squashing, `worktree.py:5254`), loop `finalize` success.
**Decision:** Each entry calls `land_states` (ADR-003) with its real checkout and exits
non-zero with `hold: <slug> <state> <ids>` on stderr if any state holds, leaving the checkout
intact:
- `wrapup_land.run` — after the legacy-ref scan, before staging; checkout = `--worktree`;
  `slugs = [--slug]`.
- `task_land` — after `_capture_pending_in_worktree`, before the squash; checkout = the task
  worktree; `slugs = [slug]`. `_branch_tip_message` skips `wip(execute): capture` commits so a
  hold-then-retry keeps the curated squash message and trailers (validator C10).
- `finalize` success — **one pass over all worktrees before the per-WT merge loop**
  (`worktree.py:3491`), after usage/strategy validation and before any capture/stash/merge, so a
  hold merges nothing in any repo (validator C7). No slug needed: the SPEC set comes from each
  branch diff, so an un-re-rendered loop template is covered too. `_cli_finalize`'s positional
  parser (`len(args) > 3` → usage) is not extended; no new flag.
- The templates ask first (ADR-006); the Python check is the backstop.
**Consequences:**
- ✅ No land path bypasses the hold — loop, worktree-off, post-check capture, old templates.
- ✅ A SPEC-less loop lands unchanged (empty set).
- ⚠️ Three existing commands gain a failure mode (IRR-004).
**Rejected alternatives:** templates only; a `--spec-slug` flag (the loop has no SPEC slug —
validator C1); aborting whenever the slug is unknown (fails every SPEC-less loop).
**Source:** Interview #5, #9, #11, #12

### ADR-006: Approval UX — final interview answer, exempt stamp, no answer = hold
**Status:** Accepted (2026-09-19, via /hm:spec + /hm:plan)
**Context:** The DRI's act must add no prompt for solo users and never be inferred.
**Decision:** spec Step 2's closing option becomes "Approve this SPEC and end interview";
choosing it records consent, and after Step 4 passes the stage runs
`hm spec_machine approve --yaml …`. Step 0 skip runs `approve --exempt`. Wrapup on `hold`
shows the ids + decisions and asks one closed question (approve → `approve`, then land;
keep → stop, keep the checkout). No question tool, no answer, or loop mode = hold stands.
Execute appends `{id: IRR-<max+1>, …, source: execute}` and, interactively, asks to re-approve.
**Consequences:**
- ✅ Zero new prompts on the normal path.
- ⚠️ The stamp records the flow, not a proven human (accepted limitation, SPEC non-goal).
**Rejected alternatives:** a separate approval question; CLI-only approval.
**Source:** Interview #3, #4

### ADR-007: Surface allowance declared in P4, retired in P5
**Status:** Accepted (2026-09-19, via /hm:plan default)
**Context:** spec/execute/wrapup/loop renders grow; the aggregate ratchet and the invariance
tests (`test_*_invariance.py`) bound them.
**Decision:** P0 pins sizes/shas per arm in `work-docs/BASELINE-DELTA-ai-native-sdlc-vs-intent-world.md`.
P4 declares `surface_allowance` (chars, commands, round_trips) in this PLAN's frontmatter in
the same commit as the growth, re-baselines `test_roundtrip_budget.py`'s tables naming each
added call, and re-captures `autopilot_gate_golden.json` with a docstring entry naming
spec/execute/wrapup/loop as the moved commands (validator C5). P5 re-freezes
`surface_baseline.json`, writes the delta attribution, deletes the allowance, and re-captures
the golden once more if P5 moved any render.
Any earlier invariance test that bounds a grown command is expected-red between P4 and P5.
New prose uses blockquotes/bullets, not new `Step/Phase/Check` headings, so
`step_sensitivity.REGISTRY` needs no entries unless a heading is unavoidable.
**Consequences:** ✅ main is green after land; ⚠️ a P4→P5 red window.
**Rejected alternatives:** regenerate the baseline in P4 (destroys attribution).
**Source:** precedent (PLAN-mission-context-loop ADR-006)

### ADR-008: `SCHEMA_VERSION` becomes 3 together with the templates
**Status:** Accepted (2026-09-19, via /hm:plan default)
**Context:** The field default stays the literal 1 (ADR-006 of spec-tetrad).
**Decision:** P1 adds v3 validation but leaves `SCHEMA_VERSION = 2`; P4 sets it to 3 in the
same commit that makes the spec template write `schema_version: 3` and the list.
**Consequences:** ✅ no window where the constant and the template disagree.
**Rejected alternatives:** bump in P1 (template/constant mismatch across phases).
**Source:** default

## 🏗️ Technical Design

**Current state:** `status: approved` is set by the spec prompt when Open Questions is empty;
`SpecMachine` ignores unknown keys and `mark_tested`/`mark_judged` rewrite the file via
`model_dump` (`spec_machine.py:613-681, 1003`); `spec_machine` verbs are guarded by
`command_registry.MODULES["spec_machine"]` (`command_registry.py:110`).

**Affected components**
- `src/harness_maker/spec_machine.py` — `IrreversibleDecision` model; `SpecMachine.approval`
  (`SpecApproval | None`, `kind: human|exempt`) and `irreversible_decisions`
  (`list[...] | None` — `None` = absent, distinct from `[]`); `approval_content_hash`;
  `approval_state`; `approve`; v3 validation; CLI verbs.
- `src/harness_maker/command_registry.py` — add `approve`, `approval-status` to `spec_machine`.
- `src/harness_maker/autopilot_caps.py` — `_JUDGMENT_GATED_STAGES`, derived gate, directive.
- `src/harness_maker/wrapup_land.py`, `src/harness_maker/worktree.py` (`task_land`,
  `_branch_tip_message`, `_cli_finalize` pre-merge pass) — hold backstop.
- Templates: `stages/spec.md.j2`, `stages/execute.md.j2`, `stages/wrapup.md.j2`,
  `commands/hm/loop.md.j2`, `agents/_partials/stage_end_summary.md.j2`.
- Tests: `tests/unit/test_spec_approval.py` (AC-001/002/004/005),
  `tests/unit/test_autopilot_spec_gate.py` (AC-003), `tests/unit/test_land_hold.py` (AC-006),
  `tests/render/test_spec_acceptance_render.py` (AC-007),
  `tests/structural/test_ai_native_sdlc_invariance.py` (plan/review byte pins).

**Data flow**
```
spec stage ──approve──► machine.yaml.approval ◄──append IRR── execute
      │                         │
      └─boundary(spec)──► approval_state ◄── wrapup template (ask) ──► wrapup_land / task-land / finalize
```

**API changes (IRR-002, IRR-004):** `hm spec_machine approve --yaml P [--exempt]`,
`hm spec_machine approval-status --root R --slug S [--checkout C]` (JSON); `wrapup_land`,
`worktree task-land` and `worktree finalize … success` gain a hold exit (no new flags).

## 📝 Implementation Plan

### Phase 0 — Pin the pre-change surface
- depends_on: []
- parallel_group: serial-0
- merge_hazards: none
- Scope in: `work-docs/BASELINE-DELTA-ai-native-sdlc-vs-intent-world.md` (§1 pins: per arm,
  char length + sha of rendered spec/execute/wrapup/loop, sha of plan/review; aggregate chars);
  `tests/structural/test_ai_native_sdlc_invariance.py` (plan/review byte pins).
  Scope out: any `src/` file.
- Exit: `uv run pytest tests/structural/test_surface_baseline.py tests/structural/test_command_size_budget.py tests/structural/test_ai_native_sdlc_invariance.py tests/structural/test_mission_context_loop_invariance.py` green on the rebased base.
- Risk: low · Rollback: n/a (docs + test only)
- **Status: DONE** (execute 2026-09-19) — pin in BASELINE-DELTA §1; exit suite 41 passed.

### Phase 1 — State machine and CLI in `spec_machine`
- depends_on: [0]
- parallel_group: serial-1
- merge_hazards: `spec_machine.py` (also touched by nobody else in this PLAN), `command_registry.py`
- Scope in: `spec_machine.py`, `command_registry.py`, `tests/unit/test_spec_approval.py`.
  Scope out: templates, autopilot, land entries; `SCHEMA_VERSION` stays 2.
- Exit: `uv run pytest tests/unit/test_spec_approval.py tests/unit/test_command_registry*.py -q` green; `uv run mypy --strict src/harness_maker/spec_machine.py`; AC-001/002/004/005 tests pass through `spec_machine.main()`.
- Risk: medium (round-trip + hash semantics) · Rollback: Phase 0
- **Status: DONE** — A.5 PASS round 2; exit suite 181 passed; ruff/mypy clean. T1 mutation gate deferred to P5 (mutmut known broken).

### Phase 2 — Autopilot spec gate (Python only)
- depends_on: [1]
- parallel_group: p2-p3
- merge_hazards: `test_judgment_gate_surface.py:42` asserts render/Python parity — it is
  expected-red from P2 until P4 renders the flag for spec (named in the delta doc)
- Scope in: `autopilot_caps.py` (`_JUDGMENT_GATED_STAGES`, derived gate placed before `:470`,
  spec directive), `tests/unit/test_autopilot_spec_gate.py`. Scope out: every template (the
  partial and spec gate text move in P4 — validator C6), land entries.
- Exit: `uv run pytest tests/unit/test_autopilot_spec_gate.py tests/unit/test_autopilot_judgment_gate.py` green, including the AC-003 row `auto_full × malformed × clear → halt` (placement check).
- Risk: medium · Rollback: Phase 1
- **Status: BLOCKED (execute, 2026-09-19) — Phase A.5 retry exhausted.** Round 1 FAIL: the
  boundary table did not assert S3's "marker preserved" → repaired. Round 2 FAIL (new finding
  on an unchanged test): `test_ac_003_spec_is_judgment_gated` asserts the private
  `autopilot_caps._JUDGMENT_GATED_STAGES` (banned pattern 8) and adds no discrimination beyond
  the golden-table test. Phase C not entered. `[boundaries] comparison not performed — blocked exit`.
  **Resolution (user, 2026-09-19): path B** — the private-constant test was deleted and the
  A.5 cap for this phase was raised to 3 rounds for one final review of the whole file.
  **Status: DONE** — A.5 PASS round 3; exit suite 39 passed; `tests/fixtures/autopilot_caps_baseline.json`
  re-captured (only the 6 `spec|*` cells moved, IRR-003) and two clean-path chain tests now
  supply an exempt SPEC + `clear`; all 1196 autopilot unit tests pass.

### Phase 3 — Land hold backstop
- depends_on: [1]
- parallel_group: p2-p3
- merge_hazards: `worktree.py` (5k lines, shared with every worktree change); `wrapup_land.py`
- Scope in: `wrapup_land.py`, `worktree.py` (`task_land`, `_branch_tip_message` WIP skip,
  `_cli_finalize` single pre-merge pass), `tests/unit/test_land_hold.py` (incl. execute-uuid +
  same-slug task worktree coexisting, SPEC-less loop, two-worktree finalize merging nothing,
  hold-then-approve squash message). Scope out: templates.
- Exit: `uv run pytest tests/unit/test_land_hold.py tests/unit/test_wrapup_land*.py tests/unit/test_worktree_task*.py tests/unit/test_worktree.py tests/unit/test_worktree_multi.py tests/unit/test_worktree_merge_fence.py tests/unit/test_worktree_stash.py tests/unit/test_worktree_finalize_commit_not_stash.py` green.
- Risk: high (land paths can lose work if the abort point is wrong) · Rollback: Phase 1
- **Status: BLOCKED (execute, 2026-09-19) — Phase A.5 retry exhausted.** Round 1 FAIL: hold
  reason checked only `hold:`; late edit not asserted landed → repaired. Round 2 FAIL: row 7
  (`merged_any`, no `reason_prefix`) would KeyError once the hold works; ok-path rows assert only
  `rc == 0`; the capture-before-hold order is not asserted after the first holding call. Phase C
  not entered. `[boundaries] comparison not performed — blocked exit`.
  **Resolution (user, 2026-09-19): path A** — the AC-006 golden table was strengthened to the
  prose (row 2 `captured`, row 4 `committed`, row 6 `merged`, row 7 `reason_prefix`; SPEC
  re-approved by that answer), the test repaired, and the A.5 cap for this phase raised to 3
  rounds; if round 3 fails, the phase's test design is re-planned rather than extended again.
  **Status: DONE** — A.5 PASS round 3; exit suites 243 passed; ruff/mypy clean.

### Phase 4 — Templates, schema v3, allowance
- depends_on: [1, 2, 3]
- parallel_group: serial-4
- merge_hazards: rendered command sizes, snapshots, invariance tests, `SCHEMA_VERSION`
- Scope in: `agents/_partials/stage_end_summary.md.j2:35` (+ spec), `stages/spec.md.j2`
  (closing option, approve/exempt calls, v3 machine.yaml + 🔒 section template, gate text at
  `:368`), `stages/execute.md.j2` (escalation rule, categories, narrowing questions, examples),
  `stages/wrapup.md.j2` (approval-status before the Step 7 bundle, approve-or-keep,
  no-answer = hold, Cursor `AskQuestion` / Codex `request_user_input`; approve re-run after the
  last `mark-tested`/`mark-judged`), `commands/hm/loop.md.j2` (halt, not converge, on a hold
  refusal), `SCHEMA_VERSION = 3`, surface allowance in this PLAN's frontmatter,
  `test_roundtrip_budget.py` tables re-baselined with named calls, `autopilot_gate_golden.json`
  re-captured with attribution, snapshot regeneration (worktree, `/home/` absolute paths),
  `tests/render/test_spec_acceptance_render.py`.
- Exit: `uv run pytest tests/render/ tests/snapshot/ tests/unit/test_spec_machine*.py tests/structural/test_autopilot_gate_render.py tests/structural/test_roundtrip_budget.py tests/render/test_judgment_gate_surface.py` green, except the expected-red invariance tests named in the delta doc.
- Risk: medium · Rollback: Phase 3
- **Status: DONE** — A.5 PASS round 2; exit run 1141 passed after fixing 5 (v3 fixture, version-constant test, delta-doc wording); golden re-captured (15 hashes, attributed), round trips re-baselined (spec 6→7, wrapup 32→33), removal allowlisted, mutation receipt for the new invariance gate.

### Phase 5 — Re-freeze, docs, full verification
- depends_on: [4]
- parallel_group: serial-5
- merge_hazards: `tests/structural/surface_baseline.json`
- Scope in: baseline re-freeze + delta §3 attribution, delete the allowance, re-capture
  `autopilot_gate_golden.json` if P5 moved any render, `docs/HOW-IT-WORKS.md` + `.ko.md` short
  section on SPEC approval and land hold, `CHANGELOG.md` entry.
- Exit: full `uv run pytest` (background, rc captured to file) green; `ruff check`, `ruff format --check`, `mypy --strict src/` clean; zero allowances in any PLAN.
- Risk: low · Rollback: Phase 4
- **Status: DONE** (execute 2026-09-19)
  - Baseline re-frozen at merge-base fb8bfaca (the generator refuses a task-branch HEAD):
    aggregate claude 444 697 / codex 378 032; `_ATOMIC_RATCHET` execute 50 383, spec 34 664;
    delta §1 re-pinned, §3 + §3.1 written; allowance deleted (0 active).
  - Docs: HOW-IT-WORKS (en/ko) "SPEC approval and the land hold"; CHANGELOG Unreleased entry.
  - Full suite: 8933 passed, 12 failed (rc=1 read from the output file; the background
    notification said exit 0). The 12 were the contract change's expected ripple — the e2e
    autopilot chain (spec now gated: exempt SPEC + `clear` + slug), the wrapup body-line pins
    (751/784 → 769/802), and 8 synthesize snapshots (regenerated in the worktree; only the 7
    spec/execute/wrapup/loop render hashes moved). Re-run green.
  - `ruff check .`, `ruff format --check .`, `mypy --strict src/harness_maker` clean.
  - T1 mutation gate: **broken run, zero mutants** (rc=1), the recurring mutmut failure
    (`[fail:tooling] mutation-gate…`); source verified unchanged afterwards and the 109 P1–P3
    unit tests re-run green. Mutation coverage for this SPEC remains unverified. Likely cause
    per the gate's own hint: `mutation_runner: null` runs the whole suite per mutant.
  - Step 4 boundaries: 45 changed paths, **0 crossings** (world.py, plan.md.j2, review.md.j2,
    .claude/intent.yaml untouched; only this task's SPEC under specs/; `SpecMachine`
    default stays literal 1). Beyond the phase scopes, the IRR-003 contract change required
    moving 8 existing test files/fixtures to the gated clean path (listed in §3.1 context).

## 🚧 Contract Boundaries

### Do not change
- `src/harness_maker/world.py` — objective approval is the precedent, not a subject
- `src/harness_maker/templates/stages/plan.md.j2` — plan render is byte-pinned by invariance tests
- `src/harness_maker/templates/stages/review.md.j2` — review render is byte-pinned
- `.claude/intent.yaml`
- Advisory: no existing SPEC file other than this task's is edited or stamped
- Advisory: `SpecMachine.schema_version` field default stays the literal 1

## 🧪 Testing Strategy

- **Unit:** state table (11 fixtures = AC-005 golden rows), property over every model field
  (AC-002), CLI through `main()` incl. registry routing (AC-001), boundary table (AC-003), land
  entries in temp git repos with a real task worktree (AC-006).
- **Render:** markers per stage × target (AC-007); judgment-gate parity test updated by
  construction.
- **Structural:** plan/review byte pins; surface baseline; step-sensitivity registry.
- **Dogfood stamp (wrapup):** this SPEC is already v3 with IRR-001..004. The rendered wrapup
  runs the released 0.57.1 `mark-tested`, whose model has no `approval` field, so the stamp is
  written **after** the last `mark-tested`/`mark-judged` write, from the worktree source
  (`uv run python -m harness_maker.spec_machine approve --yaml …`), then
  `approval-status` (worktree source) must report `approved`; record that output in the wrapup
  receipt. Note 0.57.1 `mark-tested` will also drop `irreversible_decisions` — re-check the key
  is present before stamping.
- Mutation: mutmut is known broken (0 mutants); record the attempt, do not block on it.

## ⚠️ Risks & Mitigation

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Land abort placed after a destructive step loses work | low | high | P3 tests assert branch, worktree and index untouched after abort |
| Older pinned plugin strips fields in a mixed-version window | medium | medium | row 3 → `malformed` → hold; loud, not silent |
| A peer lands on shared files mid-task (happened during planning) | medium | medium | rebase before P4; diff peer commits on shared files before regenerating goldens |
| `auto_safe` users surprised by a new stop at spec | low | low | stops only when the interview ended without approval |
| Deny-list misses a future tooling field | low | medium | property test enumerates model fields; comment at the deny-list |
| Surface growth exceeds budget | medium | low | allowance P4, retire P5 |

## ✅ Success Criteria

- [x] AC-001 approve records a content-bound stamp at the base-root identity
- [x] AC-002 approval is valid iff only deny-listed fields changed
- [x] AC-003 spec boundary follows the approval state, not the caller's claim
- [x] AC-004 schema v3 requires a well-formed irreversible-decision list
- [x] AC-005 approval-status follows the state table
- [x] AC-006 every land entry refuses on hold
- [x] AC-007 stage renders carry the acceptance flow
- [x] plan/review renders byte-identical; zero surface allowances after P5; full suite green

## 🔍 Plan Validation

**Pass 1 (only pass — user preference: plan-validator runs once, no re-validation; residual
findings move to execute A.5 and review).** Verdict: **MAJOR_REVISION** → resolved by the user
in follow-up rounds #9–#12 (all option A) → `validator_outcome: MAJOR_REVISION_RESOLVED`.

Cross-model second opinion: `codex` — **invoked**, 5 findings, all **accepted** by the
validator after verification (#1 → C1, #2 → C2, #3 → C3, #4 → C4 narrowed, #5 → C5).

| Id | Severity | Issue | Resolution |
|---|---|---|---|
| C1 | critical | loop finalize had no correct SPEC slug; missing arg skipped the check | ADR-003/005: SPEC set from branch diff; no flag; SPEC-less loop lands |
| C2 | major | name-based checkout ignored the real checkout | ADR-003: explicit checkout wins |
| C3 | major | model_dump hash dropped unknown keys; new defaulted field invalidates all | ADR-002: `extra="allow"` + `exclude_defaults` |
| C4 | major | null vs absent undefined; legacy files gain `approval: null` | ADR-003 null policy; dump omits None keys; round-trip test both ways |
| C5 | major | autopilot golden + round-trip budget not re-baselined | ADR-007, P4 + P5 scope and exit |
| C6 | major | partial edit grew spec in P2 with contradictory gate text | ADR-004: template half moved to P4; P2 Python only |
| C7 | major | finalize suites missing; parser; partial multi-repo land | ADR-005 single pre-merge pass; P3 exit lists the five suites |
| C8 | major | this SPEC v2 without list; released writer drops the stamp | SPEC migrated to v3 (re-approved); stamp procedure in Testing Strategy |
| C9 | minor | derived gate placement vs `blocked` check | ADR-004 placement; P2 exit names the row |
| C10 | minor | WIP capture changes the squash message on retry | ADR-005: `_branch_tip_message` skips WIP |
| C11 | minor | no Non-Goals | Executive Summary › Non-Goals |

Clean categories reported: risk register, ADR completeness, missing interview rounds,
rollback strategy.
