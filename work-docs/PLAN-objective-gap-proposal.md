---
type: plan
task_slug: objective-gap-proposal
status: complete
created: 2026-09-16
tags: [harness-maker, plan, python, jinja2, intent-layer, objectives, outcomes, llm-judgment]
spec: "[[SPEC-objective-gap-proposal]]"
research_doc: "[[RESEARCH-objective-gap-proposal]]"
interview_rounds: 2
adrs: 9
validator_outcome: MAJOR_REVISION_RESOLVED
summary: "Read-only hm world gap + on-demand candidate proposal (skill + plan Step 0.5/4.9); writes only via objective new --from-proposal; allowance retired at close-out"
spec_need_verdict: add
spec_need_target: objective-gap-proposal
# surface_allowance retired at Phase 6 (ADR-008): the +1 215/+1 222 plan growth is folded into
# tests/structural/surface_baseline.json with its attribution in BASELINE-DELTA-objective-gap-proposal.md §3.1.
---

# PLAN — Objective gap & proposal

## 🎯 Executive Summary

**TL;DR.** Add one read-only verb, `hm world gap --json`, that prints the deterministic gap table
(`world.gap_report`), make the `intent-layer` skill able to turn it into at most three objective
candidates on request, and let `/hm:plan` offer a draft after "none" (consent at Step 0.5,
creation at a new Step 4.9 after the interview). Every write goes through `objective new` with a
new `--from-proposal` flag that pre-fills `rejected[]` with the declined candidates and appends
one `objective_proposed` ledger event. The gate, review Step 3.3 and wrapup 5.7 do not change;
`approve` stays human. The task also owns its surface accounting end-to-end: it folds the
previous task's expired +67 first (main is red today) and retires its own allowance at close-out.

**What / Why.** The intent layer starts from an empty file. The first RESEARCH rejected a derived
"`hm next`" view for re-proposing rejected work and unstable rankings; the user withdrew that
lock-in on 2026-09-16 for an on-demand, read-only, never-gating form. This PLAN feeds the
rejection history explicitly (ADR-001), never ranks (skill prose), collects every candidate
answer before the first write (ADR-003), and keeps the only write on the existing answer-gated
path.

**Key decisions.** ADR-001 separate `gap_report`, `status` payload frozen, invalid world mirrored ·
ADR-002 `--declined` takes titles · ADR-003 proposal flags are proposal-only; `--from-proposal`
is the sole event emitter; collect-then-write · ADR-004 `objective_proposed` joins `LedgerEvent`
with an explicit destination · ADR-005 plan surface via allowance, review/help pinned · ADR-006
unmeasured outcomes proposed with a label · ADR-007 pin in a new delta doc · ADR-008 allowance
retirement is a phase, not a hope · ADR-009 consent at Step 0.5, creation at Step 4.9.

**Estimated impact.** ~140 lines in `world.py`, 1 enum member, 2 template edits, 6 test files,
one delta doc, two baseline re-freezes (one inherited, one own). No behaviour change for a project
whose `intent.yaml` is `not_filled_in`.

## 📚 Prior Work

- [[RESEARCH-objective-gap-proposal]] — Approaches A (verb + skill) and B (plan draft) chosen; C (slash command) and D (persisted candidates) rejected; pitfalls 1–7.
- [[RESEARCH-intent-world-model-objective-layer]] — Approach D counter, pitfall 3 (control at the recommendation → executable boundary = human `approve`), pitfall 4 (candidate lists rot).
- [[PLAN-playbook-alignment]] — `surface_allowance` + delta-doc precedent; its phase-4 row records the same "main was already red" crossing this PLAN now closes structurally (ADR-008).
- `src/harness_maker/surface_allowance.py:13-21` — "On completion the growth is folded into the baseline once, with its BASELINE-DELTA attribution"; nothing performs it today (verified: `wrapup.md.j2` has no such step; main fails `test_surface_baseline` by +67 at 2fd69df7).
- `[wiki:architecture] intent-doc-is-the-objective-record`; `[fail:tooling] mutation-gate-timeout-leaves-source-mutated-on-disk` (count 2); `[fail:test] splitter-non-mapping-bom-body-slice-miss`.

## 🎙️ Interview Transcript

| # | Topic | Category | Question (1 line) | Options | Choice | Note | → ADR |
|---|---|---|---|---|---|---|---|
| 1 | Unmeasured outcomes | scope | Refuse or propose with a label when every outcome is `never_measured`? | refuse / label | **label** | user overrode the recommendation | ADR-006 |
| 2 | Proposer location | architecture | Skill only / plan only / both? | 3 | **both** | plan surface via allowance | ADR-005 |
| 3 | Adoption metric | observability | Ledger event on `--from-proposal` / none? | 2 | **ledger event** | `{objective, candidates, accepted}` | ADR-003, ADR-004 |
| 4 | Declined candidates | contract | Pre-fill accepted record's `rejected[]` / keep nothing? | 2 | **rejected[]** | no persisted candidate list | ADR-002 |
| 5 | Step 3.0 | phasing | Proceed to phase decomposition or lock a how-question first? | 4 | **proceed** | five defaults recorded as ADR-001/002/004/005/007 | — |
| 6 | Validator follow-up | scope | 12 critiques: revise all / accept C6 as risk? | A / B | **A — revise all** | Phase 6 retire + fold of the inherited +67 added | ADR-008 |
| 7 | C8 flag semantics | contract | `--candidates`/`--declined` without `--from-proposal`: refuse / tolerate? | 2 | **refuse** | S3 last clause reworded | ADR-003 |
| 8 | C9 draft timing | architecture | Consent at 0.5 + create at 4.9 / create at 0.5 from RESEARCH only? | 2 | **consent 0.5, create 4.9** | id carried to Step 5; AC-005 asserts ordering | ADR-009 |

Rounds 1–4 were `/hm:spec`'s interview; round 5 the Case-A lock-in; rounds 6–8 the
plan-validator follow-up (single validator pass, per the project's one-pass rule).

## 📐 Architecture Decision Records

### ADR-001: `gap_report` is a separate reader; the `status` payload is frozen; the invalid world is mirrored
**Status:** Accepted (2026-09-16, via /hm:plan interview)
**Context:** `status_report` already computes per-outcome `gap` and `fired_revisits` but omits closed/dropped objectives and `rejected[]`, and folds `never_measured` and `stale_definition` into one `unevaluable`. Three consumers read `status`. On an invalid `intent.yaml` `status_report` returns `{state: invalid, error, errors}` with no other keys (world.py:708-716).
**Decision:** Add `world.gap_report(root)` beside `status_report`, sharing `load_world`/`last_value`/`gap`/`derive`/`revisit`. Success payload: `state`, `mission`, `outcomes{id: {last, target, observed_at, gap, reason, how_measured, higher_is_better}}`, `objectives{id: {state, title, hypothesis, outcome_id, observed, rejected, scope, non_scope}}` for **every** loadable objective, `conflicts`, `unknowns`, `fired_revisits`, `broken_references`. `reason` = `never_measured` when `last_value` is None, `stale_definition` when `LastValue.stale_definition`, else `measured`. **Invalid world: return `status_report`'s invalid payload verbatim** (one shape for both readers; the skill/plan prose branch on `state`). `status_report` is byte-for-byte unchanged (a golden test pins HEAD's output).
**Consequences:**
- ✅ `status` consumers cannot break; `gap` can grow without a compatibility argument; the invalid branch has one shape.
- ⚠️ Two readers share helpers — AC-001's differential check on the shared `gap` key catches divergence.
**Rejected alternatives:**
- Extend `status --json` — rejected: SPEC constraint; the gate-adjacent reader should not grow with every proposer need.
- Full skeleton with empty maps on invalid — rejected: a second invalid shape for consumers to learn.
**Source:** Interview #5 (default 1), validator C4

### ADR-002: `--declined` takes candidate titles, repeated
**Status:** Accepted (2026-09-16, via /hm:plan interview)
**Context:** `rejected[]` is a list of strings; the SPEC pre-fills it with the declined candidates of the same turn.
**Decision:** `objective new … --declined "<title>"` (repeatable, order preserved) writes `rejected = [titles]`. No JSON, no candidate ids.
**Consequences:**
- ✅ Zero schema change; `rejected[]` keeps its meaning.
- ⚠️ Provenance is the title only (accepted: candidate lists rot).
**Rejected alternatives:**
- `--declined-json <path>` — rejected: a second file format nothing reads back.
**Source:** Interview #5 (default 2)

### ADR-003: proposal flags are proposal-only; `--from-proposal` is the sole event emitter; collect every answer before the first write
**Status:** Accepted (2026-09-16, via /hm:plan interview)
**Context:** Adoption must be measurable without persisting candidates; SPEC S3 requires an accepted P2 record to carry a decline (P3) that arrives after the yes; `new_objective` refuses to overwrite, so there is no update path.
**Decision:**
1. `new_objective(..., from_proposal=False, candidates=None, declined=None)`. `--candidates N` and `--declined T` are **refused before any write** unless `--from-proposal` is present (argparse-level check + function-level `WorldError("from_proposal", …)`). With the flag, `candidates ≥ len(declined)+1`.
2. With the flag, after the atomic record write, exactly one `objective_proposed` event `{objective, candidates, accepted: 1}` is appended via `autopilot_ledger.append_event(base_root, …, observability_dir=<explicit>)`, where `base_root = resolve_base_root(root)` (the same base-root rule `second_opinion_invoke`'s ledger row uses — the previous PLAN's "same as `approve`" was wrong: `approve` writes no row). A failed append after the record write prints `[world] objective_proposed NOT recorded: <reason>` to stderr and exits 0 — the record stands, no retry (retry would hit the id-exists refusal).
3. The skill and plan prose **collect every candidate's answer first**, then run one `objective new` per accepted candidate with the complete ordered `--declined` list; two accepted candidates produce two records with the same declined list and two events.
**Consequences:**
- ✅ One row per accepted proposal; `status.proposed` + rows give adoption without a candidate store; a wrong flag combination cannot pass silently.
- ⚠️ Known limits, recorded: a declined-everything turn leaves no row; in a task worktree the record lands in the worktree while the row lands at base, so an abandoned task leaves a row with no objective (biases adoption upward — read adoption as rows ÷ `proposed`+approved files, not rows alone); a failed append is a warning, not a retry.
**Rejected alternatives:**
- Tolerate the flags without `--from-proposal` — rejected by the user (Interview #7).
- Emit the event from prose — rejected: prose has no execution surface.
- Write the row in the worktree's observability dir — rejected: `task-land` drops it (the same row-loss `codex_ledger` had).
**Source:** Interview #3, #5, #7; validator C6/C7/C8; codex f44e4/00a3c/3aeac

### ADR-004: `objective_proposed` joins `LedgerEvent`; the writer names its destination
**Status:** Accepted (2026-09-16, via /hm:plan interview)
**Context:** `append_event` rejects any event outside `EVENTS` (derived from the Literal, asserted disjoint from `iter_receipts.Verdict`) and already takes `observability_dir`. The suite once leaked 150 rows into the live second-opinion ledger (`tests/unit/test_ledger_isolation.py`).
**Decision:** Add `"objective_proposed"` to the Literal with a comment. `new_objective` passes `observability_dir` explicitly (default `base_root/.claude/observability`), and AC-003 asserts rows land under the test's tmp root and none under the real base. No test asserts an exact `EVENTS` set (verified), so the member is additive.
**Consequences:**
- ✅ No new file, no new reader; isolation is asserted, not assumed.
- ⚠️ Health/e2e tests that enumerate event names are run in Phase 2 (`test_autopilot_ledger*`, `test_health_evidence_surface.py`, `tests/e2e/test_autopilot_chain_e2e.py`).
**Rejected alternatives:**
- A separate `world-proposals.jsonl` — rejected: one writer, no reader.
**Source:** Interview #5 (default 3); validator C6/C10

### ADR-005: plan surface moves by a declared allowance; review and help are pinned
**Status:** Accepted (2026-09-16, via /hm:plan interview)
**Context:** Step 0.5 gains one question and Step 4.9 one call; `test_command_size_budget` pins `plan: 62703` (2 % band) and honours an in-flight PLAN's `surface_allowance`; the round-trip arm of `test_surface_baseline` is an **exact** comparison; playbook-alignment's AC-005 pins plan/review/help hashes at the same version and fails on a plan move.
**Decision:** Declare `surface_allowance.commands.plan/hm-plan: 700` + `round_trips.plan/hm-plan: 1` (this frontmatter) for Phases 1–5 only; Phase 0 pins the pre-change plan/review/help sha256 + plan length per arm into the new delta doc; AC-007 reads that pin. Playbook-alignment's invariance pin is re-taken for `plan` only in Phase 4 with an attribution row. Over budget → compact the prose first; only if compaction fails re-declare with a delta-doc row.
**Consequences:**
- ✅ The move is attributed, bounded and reviewable; review/help stay byte-identical.
- ⚠️ Two invariance tests pin the same commands; the older one's `plan` entry is rewritten (documented crossing).
**Rejected alternatives:**
- Skill-only proposer — rejected by the user (Interview #2).
**Source:** Interview #2, #5; validator C12(b)

### ADR-006: unmeasured outcomes are proposed with a label
**Status:** Accepted (2026-09-16, via /hm:plan interview)
**Context:** The recommendation was to refuse and print `how_measured` when every outcome is `never_measured`; the user chose to propose anyway.
**Decision:** The skill always opens with a "measure first" block listing each `never_measured`/`stale_definition` outcome and its `how_measured`; candidates for such outcomes carry `evidence: none — hypothesis only`. No refusal branch. On `state: invalid` the skill prints the error and stops (no candidates).
**Consequences:**
- ✅ Usable the day `mission` is written.
- ⚠️ Invented gaps are possible; the label and the human `approve` are the guards (R3).
**Rejected alternatives:**
- Refuse when all unmeasured — rejected by the user (Interview #1).
**Source:** Interview #1

### ADR-007: the pre-change pin lives in a new delta document
**Status:** Accepted (2026-09-16, via /hm:plan interview)
**Context:** `BASELINE-DELTA-playbook-alignment.md` holds that task's pin; `test_baseline_delta_attribution._current_delta_doc()` picks the first sorted `BASELINE-DELTA-*.md` that quotes the current aggregate figures, and the new name sorts before `playbook-alignment`.
**Decision:** Phase 0 writes `work-docs/BASELINE-DELTA-objective-gap-proposal.md` with (§1) the fenced JSON pin `{harness_maker_version, arms{arm: {plan, review, help}}, plan_len{arm}}`, (§2) the re-freeze table, (§2.1) attribution rows for every moved baseline key — the inherited +67 fold in Phase 0 (owning phase "Phase 0", direction "larger", "ADR-010", "ratchet-rebaselined-by-its-own-subject"), this task's own growth in Phase 6 — and (§3) the measured delta. Because the doc quotes the current aggregate from Phase 0 on, it is the doc the attribution gate reads; Phase 0's exit runs that gate.
**Consequences:**
- ✅ One pin per task; the attribution gate reads the right doc from the first commit.
- ⚠️ Both pins skip loudly at the next version bump (known).
**Rejected alternatives:**
- Append to the older delta doc — rejected: two pins in one regex-parsed fence.
**Source:** Interview #5 (default 5); validator C11

### ADR-008: allowance retirement is a phase of this task, and the inherited red is folded first
**Status:** Accepted (2026-09-16, via /hm:plan interview)
**Context:** `surface_allowance` only holds headroom while the PLAN is `planning`/`blocked`; wrapup Step 4 sets `complete` **after** Step 2 ran the suite, so every task that declared an allowance has left main red by its delta (verified 2026-09-16: +67 from playbook-alignment). The module's own docstring says completion is "the legitimate re-freeze moment", but no stage performs it.
**Decision:** (a) **Phase 0** folds the inherited +67 into `tests/structural/surface_baseline.json` from the base checkout (`python tests/structural/_surface_baseline.py --out …`) with an attribution row, so main is green before this task adds anything. (b) **Phase 6** (last) re-freezes `surface_baseline.json` and `instruction_baseline.json` from the worktree, moves `_ATOMIC_RATCHET['plan']` only if the render leaves the 2 % band, writes the attribution rows, **deletes the `surface_allowance` block** from this frontmatter, and its exit is `pytest tests/structural` green with zero in-flight allowances (AC-008). (c) Wrapup then flips `complete` on a PLAN that has nothing to expire.
**Consequences:**
- ✅ Main is green after the land; the next task does not inherit a crossing.
- ⚠️ This task edits `surface_baseline.json` twice (inherited, own) — both attributed; Contract Boundaries phrase the file as frozen *between* Phase 0 and Phase 6, not absolutely.
- ⚠️ The structural fix (wrapup performing the fold, or Step 2 running with `complete` already set) is a follow-up, recorded in memory `project_surface_allowance_expires_at_wrapup` — out of scope here.
**Rejected alternatives:**
- Leave retirement to "the next task" — rejected: that is the count-2 pattern this PLAN was caught repeating.
**Source:** Interview #6; validator C1/C2; codex f46f9

### ADR-009: consent at Step 0.5, creation at Step 4.9
**Status:** Accepted (2026-09-16, via /hm:plan interview)
**Context:** Step 0.5 runs before Step 1's draft and the interview; a draft built there would persist a hypothesis/scope the interview then changes, in a record that refuses overwrite. A re-run `/hm:plan` (routine after a validator MAJOR_REVISION) would hit the id-exists refusal.
**Decision:** Step 0.5, after "none": ask once **"Draft an objective for this task?"**; on yes record consent in the turn (no write). New **`### Step 4.9 — Objective draft (consented at Step 0.5)`** placed after Step 4.5 and before Step 5: derive `id` (the task slug upper-cased, `[a-z0-9-]` → `[A-Z0-9-]`, prefixed `OBJ-`), `title`, `hypothesis`, `scope`, `non_scope`, `outcome_id` (the outcome the interview named; if none fits, print "no outcome fits — draft skipped" and continue) from the interview + RESEARCH; show the exact arguments; run `objective new … --from-proposal --candidates 1` once; Step 5 writes `objective: <id>`. If the verb refuses (id exists, outcome unknown): **print the refusal and continue** without a link — never retry with a mutated id. An orphan `proposed` record from an abandoned plan is retired with `objective drop` (R6). Step 5's frontmatter comment notes the `proposed` link halts autopilot with `not_active` until a human approves + activates. AC-005 asserts ordering (question < Step 4.9 heading < call < Step 5), not phrases alone.
**Consequences:**
- ✅ The record reflects the interview; re-runs are safe; the id reaches Step 5 by construction.
- ⚠️ One more heading in the plan command → `step_sensitivity` registry entry (class INV — human lock-in) in Phase 4.
**Rejected alternatives:**
- Create at Step 0.5 from RESEARCH only — rejected by the user (Interview #8).
**Source:** Interview #8; validator C5/C9; codex 2fdc3

## 🏗️ Technical Design

**Current state.** `world.status_report` (world.py:706) computes outcomes `{last,target,observed_at,gap,stale_definition}`, `active`/`proposed`, `fired_revisits`, and an invalid early-return; `last_value` (630) exposes `stale_definition`; `gap` (656) returns `unevaluable` for both None and stale. `new_objective` (1009) writes the INTENT skeleton with `rejected: []` and refuses an existing path. `autopilot_ledger.LedgerEvent` has six members; `append_event` takes `observability_dir`. plan.md.j2:91-118 is Step 0.5, :738 the `objective:` frontmatter comment. Main at 2fd69df7 fails two structural tests by +67 chars.

**Affected components.** `src/harness_maker/world.py` (gap_report, gap verb, new_objective flags, parser, ledger call), `src/harness_maker/autopilot_ledger.py` (Literal member), `src/harness_maker/command_registry.py` (`gap`), `src/harness_maker/step_sensitivity.py` (Step 4.9 entry), `templates/skills/intent-layer/SKILL.md.j2`, `templates/stages/plan.md.j2`, `tests/structural/surface_baseline.json` + `instruction_baseline.json` (Phase 0 inherited fold, Phase 6 own fold), `tests/structural/test_command_size_budget.py` (only if outside the band), `work-docs/BASELINE-DELTA-playbook-alignment.md` (plan pin re-take), tests, `CHANGELOG.md`, `docs/HOW-IT-WORKS.md`.

**Data flow.** load_world → gap_report (pure) → `hm world gap --json` → skill / plan Step 4.9 (LLM) → collect all answers → per accepted: `hm world objective new <ID> … --from-proposal --candidates N [--declined T]…` → INTENT-<ID>.md (proposed) + ledger row at base.

**API changes.** New: `world.gap_report(root)`, CLI `world gap [--json]`, `new_objective(from_proposal=, candidates=, declined=)`, flags `--from-proposal --candidates --declined`, ledger event `objective_proposed`. Unchanged: `status_report`, every existing verb, gate, review 3.3, wrapup 5.7.

## 📝 Implementation Plan

### Phase 0 — Green main + pin
- `depends_on`: [] · `parallel_group`: serial-0 · `merge_hazards`: `tests/structural/surface_baseline.json` (inherited fold), `work-docs/BASELINE-DELTA-*.md` (attribution-gate doc selection)
- **Scope (in):** (1) From the **base** checkout at 2fd69df7 run `uv run python tests/structural/_surface_baseline.py --out <WT>/tests/structural/surface_baseline.json` (folds the inherited +67; `instruction_baseline.json` only if `python -m tests.structural._instruction_baseline --out` differs). (2) Write `work-docs/BASELINE-DELTA-objective-gap-proposal.md`: §1 fenced JSON pin (sha256 of plan/review/help per arm from `tests/structural/_instruction_baseline.AXES` + `_render_atomic` and `test_command_size_budget._render` for `ask@flag_on/off`, `harness_maker_version`, per-arm plan length — the same recipe `test_playbook_alignment_invariance._live_arms` uses), §2 re-freeze table (claude 431477→431544, codex unchanged unless measured), §2.1 attribution rows (owning phase, "larger", "ADR-010", "ratchet-rebaselined-by-its-own-subject", note "inherited from playbook-alignment's expired allowance"), §3 placeholder. **Out:** any template, any `src/`.
- **Exit:** `cd <WT> && uv run pytest tests/structural/test_surface_baseline.py tests/structural/test_command_size_budget.py tests/structural/test_baseline_delta_attribution.py tests/structural/test_playbook_alignment_invariance.py -q` green (was red on the delta-doc-missing error and the +67); `git diff --stat` shows the baseline + the new doc only.
- **Risk:** low · **Rollback:** `git checkout tests/structural/surface_baseline.json`, delete the doc, remove the allowance block.

### Phase 1 — `gap_report` + `hm world gap`
- `depends_on`: [0] · `parallel_group`: serial-1 · `merge_hazards`: `src/harness_maker/world.py` (shared with Phase 2)
- **Scope (in):** `world.gap_report` (ADR-001 payload; invalid mirror), `_reason(lv)` helper, `gap` subparser (`--json`, `--root`), `command_registry` world name `gap`, `tests/unit/test_world_gap.py`: AC-001 differential vs `status_report`/`load_world`; AC-002 Hypothesis property over `world_fixture.build_root` (ci/dev profiles); reason matrix none/stale/measured; closed+dropped objectives present with `rejected`; **invalid world returns `status_report`'s payload**; `status_report` golden from HEAD unchanged. **Out:** `new_objective`.
- **Exit:** `uv run pytest tests/unit/test_world_gap.py tests/unit/test_world_status_and_revisit.py -q` green; `uv run mypy --strict src/harness_maker/world.py`; `uv run python -m harness_maker.world gap --json` on the dogfood root prints `state: not_filled_in`; `git status` shows no new file after that run.
- **Risk:** low · **Rollback:** Phase 0.

### Phase 2 — `--from-proposal`, `--declined`, ledger event
- `depends_on`: [1] · `parallel_group`: serial-1 · `merge_hazards`: `src/harness_maker/world.py`, `src/harness_maker/autopilot_ledger.py`
- **Scope (in):** `new_objective` kwargs + refusals (flags without `--from-proposal`; `candidates < len(declined)+1`; all before any write), `rejected` pre-fill, event append with explicit `observability_dir` at `resolve_base_root(root)`, stderr warning + exit 0 on append failure, `LedgerEvent` member + comment, `tests/unit/test_intent_doc_new.py` AC-003: record via `load_world`; exactly one row under the tmp observability dir and **none under the real base** (the `test_ledger_isolation` shape); no row without the flag; refusals on `out+err` with no file written; two accepted candidates → two records, same declined list, two rows; monkeypatched `append_event` raising → record exists, stderr line, exit 0. `tests/unit/test_autopilot_caps_objective_gate.py` AC-006: build the `proposed` record through the CLI, assert reason `not_active`. **Out:** templates.
- **Exit:** `uv run pytest tests/unit/test_intent_doc_new.py tests/unit/test_autopilot_ledger_health.py tests/unit/test_autopilot_ledger*.py tests/unit/test_health_evidence_surface.py tests/e2e/test_autopilot_chain_e2e.py tests/unit/test_autopilot_caps_objective_gate.py tests/unit/test_ledger_isolation.py -q` green.
- **Risk:** medium · **Rollback:** Phase 1.

### Phase 3 — `intent-layer` skill: gap situation + candidate rules
- `depends_on`: [2] · `parallel_group`: templates · `merge_hazards`: `tests/snapshot/*.expected.yaml` (regen in the worktree). The skill is **not** ratchet-measured (`_surface_baseline.py` measures `.claude/commands/hm/*.md` and `.agents/skills/hm-*/SKILL.md` only — verified).
- **Scope (in):** description gains "asks what to do next / where the gaps are"; new section "Proposing objectives": run `gap --json`; on `state: invalid` print the error and stop; open with the "measure first" block; read the codebase; propose **at most three** candidates with `title / hypothesis / scope / non_scope / outcome / evidence / overlaps-with`; `evidence: none — hypothesis only` for unmeasured outcomes; name overlaps with any `rejected[]` entry or `closed`+`missed` objective; **answer every candidate before the first write**; then one `objective new … --from-proposal --candidates N --declined …` per accepted candidate; "the proposer never runs `approve`". Both arms, ≤ 40 new lines. `tests/unit/test_render_intent_layer.py` AC-004 phrase pins (both arms). Snapshot regen. **Out:** plan template.
- **Exit:** `uv run pytest tests/unit/test_render_intent_layer.py tests/snapshot -q` green; skill ≤ 300 lines.
- **Risk:** low · **Rollback:** Phase 2.

### Phase 4 — plan Step 0.5 consent + Step 4.9 draft + pin re-take
- `depends_on`: [2] · `parallel_group`: templates · `merge_hazards`: `tests/structural/test_command_size_budget.py`, `tests/structural/autopilot_gate_golden.json`, `src/harness_maker/step_sensitivity.py`, `work-docs/BASELINE-DELTA-playbook-alignment.md`
- **Scope (in):** plan.md.j2 per ADR-009 (Step 0.5 consent question; `### Step 4.9 — Objective draft (consented at Step 0.5)` after Step 4.5, before Step 5; refusal line; "write nothing" on no; Step 5 comment); `step_sensitivity` entry for Step 4.9 (INV); measure the delta per arm; delta doc §3 measured plan growth; re-take `plan` in playbook-alignment's delta JSON with an attribution row; `tests/structural/test_objective_gap_proposal_invariance.py` AC-007 (review/help hashes vs pin; plan growth ≤ 700 per arm) + AC-005 in `test_render_intent_layer.py` (ordering assertions, both arms); `autopilot_gate_golden.json` re-captured if the plan text is part of it (check `test_autopilot_gate_render.py`). Over budget → compact first (ADR-005). **Out:** review/help/wrapup templates, `surface_baseline.json` (Phase 6 owns the own fold).
- **Exit:** `uv run pytest tests/structural tests/unit/test_render_intent_layer.py -q` green **with** the allowance active; measured plan growth ≤ 700 per arm recorded in the delta doc.
- **Risk:** medium · **Rollback:** Phase 3.

### Phase 5 — Lifecycle test, docs, CHANGELOG
- `depends_on`: [3, 4] · `parallel_group`: serial-5 · `merge_hazards`: `CHANGELOG.md` `[Unreleased]` top
- **Scope (in):** `tests/integration/test_intent_layer_lifecycle.py` — gap on an empty world → `new … --from-proposal` → gate `not_active` → approve → activate → gap shows the objective with `state: active`; `CHANGELOG.md` Added/Changed/Fixed (the inherited fold); `docs/HOW-IT-WORKS.md` §7.13 paragraph on `gap`, proposals and Step 4.9.
- **Exit:** `uv run --with … hm verification_plan commands --root .` suite green.
- **Risk:** low · **Rollback:** Phase 4.

### Phase 6 — Retire the allowance (ADR-008)
- `depends_on`: [5] · `parallel_group`: serial-6 · `merge_hazards`: `tests/structural/surface_baseline.json`, `tests/structural/instruction_baseline.json`, `tests/structural/test_command_size_budget.py`, this PLAN's frontmatter
- **Scope (in):** from `<WT>`: `uv run python tests/structural/_surface_baseline.py --out tests/structural/surface_baseline.json` and `uv run python -m tests.structural._instruction_baseline --out tests/structural/instruction_baseline.json`; move `_ATOMIC_RATCHET['plan']` only if the render is outside the 2 % band (expected: not); delta doc §2/§2.1 rows for every moved key ("Phase 6", "larger", "ADR-010", "ratchet-rebaselined-by-its-own-subject"); **delete the `surface_allowance` block** from this frontmatter; `test_objective_gap_proposal_invariance.py` AC-008 (frontmatter has no `surface_allowance`; delta-doc aggregate == baseline aggregate).
- **Exit:** `uv run pytest tests/structural -q` green with **zero** in-flight allowances (`hm`-free check: `grep -c surface_allowance work-docs/PLAN-objective-gap-proposal.md` → 0); full suite green.
- **Risk:** medium · **Rollback:** Phase 5 (restore the allowance block and the two baselines).

### Phase status

| Phase | Status | Notes (execute 2026-09-16) |
|---|---|---|
| 0 | done | inherited +67 folded from the base render into both baselines; delta doc §1 pin + §2/§2.1 rows; a premature `round_trips: 1` declaration failed the exact round-trip arm and was moved to Phase 4 |
| 1 | done | A.5 PASS (1 round); `gap_report` mirrors `status`'s invalid payload; dogfood `gap --json` → `not_filled_in`, no file written |
| 2 | done | A.5 PASS (2 rounds — round 1 asked the append-failure test to drive the CLI; now a filesystem fault, `rc == 0` asserted); `objective_proposed` added to `LedgerEvent`; rows land under the caller's `observability_dir` |
| 3 | done | A.5 PASS (2 rounds — round 1 asked for a distinct per-candidate-ask pin: `ask about each candidate in turn`); skill 65 lines; description trimmed to ≤ 200 chars |
| 4 | done | A.5 PASS (1 round); measured +1 654 → compacted to +1 049 per arm → allowance re-declared 1100 per ADR-005 (delta doc §3); gate golden re-captured for `plan` with a `rebases` entry; playbook-alignment's `plan` pin re-taken with a note; `step_sensitivity` Step 4.9 (INV) + matrix row; `unsourced` 39 → 40 |
| 5 | done | lifecycle test (gap → `--from-proposal` → no valid approval → approve → activate → `active`); CHANGELOG Added; HOW-IT-WORKS §7.13 paragraph; snapshots regenerated in the worktree |
| 6 | done | both baselines re-frozen from the worktree; `_CLAUDE_ROUND_TRIPS['plan']` 28 → 29 with attribution; allowance block deleted; §1 `plan` re-pinned at retirement; `pytest tests/structural` green with zero in-flight allowances (AC-008) |

**Phase C.0 / D.5:** every phase was new-feature work (no defect repair), so no repair
declaration and no newly-reachable-window paragraph applies. **T1 mutation gate:** zero mutants
again (known tool failure, `mutation-gate-timeout-leaves-source-mutated-on-disk` count 2 → 3 at
wrapup); `world.py` verified unmutated by diff + the world/intent suites; the AC-007 gate's
mutation receipt was recorded after a genuine probe (deleting `review.md.j2:381` turns it red).

**Post-review fixes (user-directed, before wrapup):** review P2 0a2499c3 (Step 0.5 cold-start
consent branch, plan +166/arm, both baselines / gate golden / both pins re-folded — the Phase 6
retirement repeated) and P2 0414f390 (`gap_report` single load via `_status_payload`).

## 🚧 Contract Boundaries

### Do not change
- `src/harness_maker/autopilot_caps.py` — the gate's reason table and precedence are pinned; AC-006 only re-asserts `not_active`
- `src/harness_maker/templates/stages/review.md.j2` — Step 3.3 untouched; hash pinned by AC-007
- `src/harness_maker/templates/stages/wrapup.md.j2` — 5.7 untouched; wrapup ratchet unchanged (the fold that wrapup should perform is a follow-up, not this task)
- `src/harness_maker/templates/commands/hm/help.en.md.j2`
- `src/harness_maker/templates/commands/hm/help.ko.md.j2`
- `tests/fixtures/autopilot_caps_baseline.json` — the 77-cell boundary baseline
- Advisory: `tests/structural/surface_baseline.json` and `instruction_baseline.json` are frozen between Phase 0 (inherited fold) and Phase 6 (own fold); Phases 1–5 declare growth via the allowance only
- Advisory: `world.status_report`'s payload keys and values are frozen (ADR-001); a golden test pins HEAD's output

## 🧪 Testing Strategy

- **Unit:** `test_world_gap.py` (AC-001 differential incl. invalid mirror, AC-002 Hypothesis read-only property, reason matrix, status golden), `test_intent_doc_new.py` (AC-003 incl. refusals, two-accept, append-failure, tmp-vs-base ledger isolation), `test_autopilot_caps_objective_gate.py` (AC-006 via CLI-built record), `test_render_intent_layer.py` (AC-004 phrases both arms; AC-005 ordering both arms).
- **Structural:** `test_objective_gap_proposal_invariance.py` (AC-007 pin, AC-008 retirement), existing ratchets with the allowance (Phases 1–5) and without it (Phase 6), attribution gate on the new delta doc, snapshot regen in the worktree.
- **Integration:** lifecycle extension.
- **Manual (dogfood):** `hm world gap --json` on this repo → `not_filled_in`; on a tmp copy with a throwaway mission+outcome, the skill path yields ≤ 3 candidates and one `proposed` file + one ledger row under the tmp base.

## ⚠️ Risks & Mitigation

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R1 | Ledger enum change breaks a reader that switches on names | low | medium | Phase 2 exit runs ledger, health-surface and e2e chain tests; member is additive (no exact-set assertion exists) |
| R2 | Ratchet/pin choreography (two folds, two invariance tests, attribution doc selection) | medium | medium | Phase 0 greens main first and runs the attribution gate; Phase 6 is the only own fold; both attributed |
| R3 | Invented gaps on unmeasured outcomes (ADR-006) | medium | low | label + "measure first" opener + human approve; withdrawal criterion counts `observed`, not files |
| R4 | Skill exceeds 300-line context lint | low | low | ≤ 40 new lines |
| R5 | Mutation gate still zero mutants | high | low | known tool failure (count 2); world tests re-run manually; receipt recorded; never diagnose with an interrupted run in the worktree |
| R6 | A `proposed` link in a PLAN halts autopilot mid-pipeline; orphan `proposed` records from abandoned plans | medium | low | by design (AC-006); Step 5 comment says so; `objective drop` retires orphans; adoption read as rows ÷ files |
| R7 | Adoption rows at base for records in an abandoned worktree | low | low | recorded limit (ADR-003); rows are a numerator only |
| R8 | Phase 6 fold conflicts with a concurrent task's baseline edit | low | medium | fold last, from the worktree, just before wrapup; `task-refresh` first if base moved |

## ✅ Success Criteria

- [x] AC-001 gap report carries measurement reason and every objective state (invalid mirrored)
- [x] AC-002 gap writes nothing (property)
- [x] AC-003 from-proposal prefills rejected and emits one event (refusals, two-accept, append failure, tmp-only rows)
- [x] AC-004 skill renders the gap situation and candidate rules (both arms, collect-then-write sentence)
- [x] AC-005 plan consent at 0.5, creation at Step 4.9 — ordering asserted (both arms)
- [x] AC-006 proposed link halts with not_active
- [x] AC-007 review, help pinned and plan within allowance
- [x] AC-008 allowance retired; structural suite green with zero in-flight allowances; main green after land
- [x] full suite + ruff + mypy green; snapshot regenerated in the worktree

## 🔍 Plan Validation

**Second opinion (codex):** `status: invoked` (63 s), 5 findings — f46f9 P1 allowance retirement, f44e4 P1 collect-then-write, 00a3c P2 flag semantics, 3aeac P2 partial failure, 2fdc3 P2 Step 0.5 timing. All five reconciled **accepted** by the validator (3aeac folded into C5/C6 rather than a standalone critique).

**plan-validator pass 1 (terminal — single pass by project rule):** `MAJOR_REVISION` — 1 critical, 8 major, 3 minor. `plan_rounds plan` scheduled all 12 rounds, none skipped. Ledger row `ogp-20260916-1` pass 1 terminal.

| id | Sev | Critique | Resolution (Interview #6–8) |
|---|---|---|---|
| C1 | critical | No allowance-retirement / fold step; boundaries forbid it; round-trip arm exact | A — ADR-008, Phase 0 inherited fold + Phase 6 own fold; boundaries reworded; AC-008 |
| C2 | major | delta_doc missing → every structural gate red | A — Phase 0 writes the doc first; Phase 0 exit runs the four structural tests |
| C3 | major | Phase 3 depends_on [1] but uses Phase 2 flags | A — `depends_on: [2]` |
| C4 | major | `gap_report` undefined for the invalid world | A — ADR-001 mirrors `status_report`'s invalid payload; test row added |
| C5 | major | No id rule / collision branch / orphan story | A — ADR-009: `OBJ-<SLUG>`, print refusal and continue, `objective drop` for orphans (R6) |
| C6 | major | Base-root ledger writer without isolation guard; worktree/base split | A — ADR-003/004: explicit `observability_dir`, tmp-only assertion; split recorded as limit (R7) |
| C7 | major | Write-per-yes cannot carry a later decline | A — ADR-003 collect-then-write; S3/AC-003/AC-004 updated |
| C8 | major | ADR-003 vs S3 last clause on flags | A — refuse (Interview #7); S3 reworded |
| C9 | major | Draft from interview answers that do not exist at Step 0.5 | A — ADR-009 consent at 0.5, create at 4.9 (Interview #8); AC-005 ordering |
| C10 | minor | Phase 2 exit omits health tests R1 promises | A — exit command lists them |
| C11 | minor | Phase 0 exit an ellipsis; attribution-doc selection | A — literal commands; doc quotes the aggregate from Phase 0 and the gate runs in Phase 0's exit |
| C12 | minor | Wrong `approve` precedent; no over-budget branch; deferred conditionals | A — ADR-003 cites the invoker; ADR-005 compact-first; conditionals resolved (skill not measured; health tests named; instruction-baseline keys expected only at Phase 6) |

`validator_outcome: MAJOR_REVISION_RESOLVED` — a human answered the follow-up rounds (all A). No pass 2 (project rule: validator runs once; findings that would have surfaced there are carried into execute A.5 / review).
