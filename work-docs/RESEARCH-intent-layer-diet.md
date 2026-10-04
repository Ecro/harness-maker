---
type: research
task_slug: intent-layer-diet
status: complete
created: 2026-10-04
tags: [harness-maker, research, python, intent-layer, simplification, dead-code, surface-budget]
mtime_warn_days: 7
libs_fetched: []
sources: []
related_docs: ["[[SPEC-intent-world-model-objective-layer]]", "[[SPEC-world-intent-closed-loop]]", "[[SPEC-world-intent-closed-loop-trial]]", "[[SPEC-intent-feedback-continuity]]", "[[PLAN-world-intent-closed-loop-trial]]", "[[SPEC-understanding-handoff]]", "[[REVIEW-source-plan-steps-2026-09-18]]"]
summary: "Cut leaf machinery first (trial, deprecated hm world CLI, dead rubrics, migrate); defer entangled core"
---

# RESEARCH — intent-layer-diet

## 🎯 Recommended Direction

**TL;DR — Remove the leaf machinery in one bounded task: `intent_trial` together with its five
`worktree.py` hooks, the deprecated `hm world` CLI and its dead helpers, the ten unrendered
rubrics, the `objective_proposed` ledger write that has no reader, and possibly `intent_migrate`.
Keep the core and the parts with real use (questions plus evidence locators, auto-measure, record
lifecycle, `hm intent status`). Defer the entangled internals (vocabulary translation, the
assumption-only branches) and the rendered-surface diet to separate decisions.**

Rationale. The layer has about 5,450 unique Python LOC. `world.py` (2,183) is the engine
behind `hm intent`, and `intent_cli` is a thin translator over it, so the layer cannot be
deleted module by module. Only one block is both large and dead: `intent_trial.py` (1,472 LOC
plus 2,598 test LOC). It never produced a verdict (frozen 2026-09-23 at 0/3 enrolled), and its
only intent, WORLD-INTENT-CLOSED-LOOP, closed `met` on 2026-10-04 through manual metric rows.
Removing the leaves cuts roughly a third of the layer's code. Run-time behaviour and the
rendered surface barely change. Shrinking the entangled parts costs more than it saves for
now. Consumers use questions (neuroTerm has 7 with evidence; spoton has 20), and the status
payload, the Maker digest and wrapup 5.7 all read the question fields. Dropping them breaks
existing user files unless the schema keeps accepting them. The main impact is
**internal maintainer value**: less code to reason about in the most dangerous module
(`worktree.py`). Consumer-facing impact is near zero. The rendered-surface cost (§Approach C)
is the consumer-facing lever, and it is a different decision.

Whole-layer removal is **not** recommended. LOOP-OPT-IN is the one end-to-end proof that the
layer works: a numeric prediction (21.7 → ≈9.2) was checked against reality (7.3) and closed.
Two consumer repos also use the layer actively. The pre-registered withdrawal criterion
(`intent.py:54`, 10 quiet wrapups) measures disuse, not value. It is not due
(`quiet_wrapups: 0`), and this research neither reinterprets nor invokes it.

## 🔍 Refinement Decisions

Discovery lens: Technical architecture / implementation (caller map and entanglement) + Risk
(user-state preservation, `worktree.py` invariants, surface ratchets). The user-workflow lens
was applied locally: usage evidence came from this repo and six consumer projects. No web or
paper lens was used because the question is internal and the codebase is authoritative.

Constraint carried from the operator: the in-flight UNDERSTANDING-HANDOFF measurement (the
wrapup Understanding block and ADR `decided_by`) is not touched. The operator decides the
deletion scope after reading this document.

## 🛠️ Approaches Found

### Usage evidence (basis for every approach)

| Sub-feature | Evidence of real use | Verdict |
|---|---|---|
| `hm intent status` | ~150 calls across 3 repos (63 here, 89 neuroTerm) | **Used** |
| Auto metric measure | 69 auto rows here (5 metrics × ~14), consumers have some | **Used** |
| Questions + evidence | `q_825d…` (7-lens fan-out) 4 real-review entries; neuroTerm 7/10 with evidence; spoton 1/20 | **Used, thin** |
| Record lifecycle (new/approve/activate/close) | 4 records here (1 met with real effect), 9 in consumers (7 left `proposed`) | **Used, thin** |
| Review Step 3.3 drift | 12 of 215 REVIEWs mention it; 2 real P2 findings; 1 P1 was a bug in 3.3 itself | **Marginal** |
| Feedback rows (`## Feedback`) | ~59 rows in 17 files, 09-22 → 10-03; ~35 point at the trial/closed-loop itself | **Mostly self-referential** |
| Trial (`intent_trial`) | Activated 09-22, frozen 09-23, 0/3, no verdict | **Never produced output** |
| Assumptions store / `hm world assume` | No `.claude/world/` here; verbs used only during mid-Sept development | **Unused** |
| `fired_revisits` / `needs_revalidation` / `conflicts` | 0 real firings in this repo and in consumers | **Never fired** |
| Autopilot objective halt (`autopilot_caps.py:301-339`) | 0 halts here; none of the 135 `gate_blocked` rows carries its reasons; consumers 0 | **Never fired** |
| Owners role map | `owners: {}` here; set in spoton and neuroTerm | **Consumer data exists** |
| `objective_proposed` ledger event | 2 writes (09-18); no reader in src | **Write-only** |

### Approach A — Leaf removal (recommended)

| Field | Content |
|---|---|
| Approach | Delete self-contained machinery; leave core semantics and the rendered stages unchanged |
| Scope | `intent_trial.py` + its 5 `worktree.py` sites (stash-restore fence 922-935, finalize 3653-3666, post-commit pop 3996-4001, `_trial_active` 5124-5131 → mandatory span emission at 5148, land 5445-5466) + the `trial/reconcile/record-decision` verbs (`intent.py:536-549`, `intent_cli.py:105-129`, `command_registry.py:54-77`) + the deprecated `hm world` CLI (`world.py:1983-2183`) plus helpers with no other src caller (`status_report`, `gap_report`, `resolve`, `edit_objective`, `validate_objective`) + the 10 unrendered rubrics (`rubrics/world_intent_*.yaml.j2`, `intent_feedback_continuity`, `objective_scope_drift`; not in `_ALL_RUBRICS`, `synthesize.py:637`) + `_record_proposal`'s ledger write (keep `--from-proposal` argument parsing, which `spec.md.j2:514-518` passes) |
| Optional add-ons | `intent_migrate.py` (148, leaf) plus the old-layout read paths (`world.py:146-256,741,765-775`), but only after confirming that no consumer still has `work-docs/INTENT-*.md` or a legacy layout. Owners: keep the schema key accepted and drop only the approval advisory (`world.py:1743-1750`) |
| Assumption | Nothing outside tests depends on trial output; `hm world` has no template caller (verified: only `hm world_model digest`, a different module) |
| Evidence | Caller map (2026-10-04): `intent_trial` imports only `worktree._flock_lock`; `hm world` deprecated since 09-21, with 2 stray calls after that |
| Trade-off | `worktree.py` edits land in the highest-risk module (multi-session invariants). Five call sites must come out without changing the stash/land paths for non-trial runs. ~2.6k test LOC and 13 `hm world` CLI test files are deleted or migrated |
| Compatibility | `PLAN-world-intent-closed-loop-trial.md` stays as a historical document; nothing reads it after removal. Stage renders are unchanged, so snapshots, ratchets and the UNDERSTANDING-HANDOFF window are unaffected unless the optional add-ons touch templates (`SKILL.md.j2:19` mentions migrate) |
| Risk | **medium**. Code-only and mostly deletion, but it runs through `worktree.py` land/finalize |
| Size | ≈ 1,472 + ~200 + ~150 helper + rubrics ≈ **1.9k src LOC**, ≈ 2.6k+ test LOC |

### Approach B — Core simplification (defer)

| Field | Content |
|---|---|
| Approach | Remove the assumption-only branches (`STATUSES` conflict, `revisit_when` on questions, `needs_revalidation`, `conflicts`, `fired_revisits`), simplify approval to "exists" instead of a content hash, and rename the internals so `intent_vocabulary` can go |
| Assumption | Questions survive as a plain list with evidence, and the features that never fired can go without loss |
| Evidence | Never-fired table above. Entanglement: `load_world` 706-720, `depends_on` validation 637-646, `derive` 793-804, `_gap_payload` 1268-1284 (= body of `hm intent status`), digest `_INTENT_KEYS` (`world_model_digest.py:33-38`), wrapup 5.7 (`wrapup.md.j2:579-584`), spec 0.5 (`spec.md.j2:89-96`), project-knowledge routing (`SKILL.md.j2:14,30`) |
| Trade-off | Touches the status JSON contract, the digest, three stage templates (moving every snapshot/ratchet) and user files. Removing a schema key makes existing consumer files fail validation as an "unknown top-level key" (`intent.py:308-310`) unless it is kept tolerated. Vocabulary removal means renaming internals, not deleting a file. Content-hash approval is the only thing that makes "approved X, then edited it" detectable. The gate never fired, but it is a safety rail, not dead code |
| Compatibility | Requires a deprecate-and-tolerate period for consumer `intent.yaml`/records; violates the "user state preservation" checklist item if done naively |
| Risk | **high** |
| Size | ≈ 330 LOC (questions/assumptions) + 143 (vocabulary) + 150 (locator) + ~195 (withdrawal) ≈ 0.8k, plus template/test churn |

### Approach C — Rendered-surface diet / opt-out (separate decision)

| Field | Content |
|---|---|
| Approach | Gate the intent prose on a `harness.yaml` toggle (default on), or shrink the stage blocks: drop the per-stage `feedback-entry`/`feedback-close` collection and keep a slimmer wrapup 5.7 |
| Evidence | ~14.6 KB per full pipeline (≈4.6% of 319 KB) is paid only when a stage runs, plus ~0.85 KB every turn (World-model pointer, Maker description, project-knowledge pointer). **No toggle exists** (`models.py:929-954`), and all of it renders even without `.claude/intent.yaml`. Three of six consumer repos have an empty or purpose-only `intent.yaml` and still pay it |
| Breakdown | feedback entry+close 4,443 B; wrapup 5.7 ~5,100 B; spec 0.5+4.9 ~3,470 B; review 3.3 1,304 B; execute ~350 B (each ×2 with the Codex duplicate) |
| Trade-off | This is the consumer-facing lever, but it moves every hash pin, `surface_baseline.json` (+ BASELINE-DELTA attribution), `test_roundtrip_budget.py` (6-8 `!` lines), `instruction_baseline.json` `_ALLOWED_REMOVALS`, and the `_ATOMIC_RATCHET` ceilings. A wrapup change during the UNDERSTANDING-HANDOFF window must not touch the Understanding block. A toggle adds a config axis, against the first goal's "simple" |
| Risk | **medium** (mechanical but wide) |

### Approach D — Remove the whole layer (rejected)

Loses the only mechanism that produced a measured, pre-registered removal (LOOP-OPT-IN). It
breaks neuroTerm and spoton, which use status and questions, and it breaks Maker's digest. The
pre-registered withdrawal rule does not authorize it (not due).

### Local capability × user artifact

| Capability | This repo | neuroTerm | spoton | edgelog / futureSelf / log_agent / strange_chess |
|---|---|---|---|---|
| purpose + metrics | filled, 8 metrics | 4 metrics | 9 metrics | partial / empty |
| auto measure | 69 rows | 1 row | 8 rows | none |
| questions + evidence | 10 (4 with evidence) | 10 (7 with evidence) | 20 (1 with evidence) | 3 / 0 |
| records | 4 | 1 active | 8 (7 proposed) | 0 |
| trial | frozen 0/3 | — | — | — |

## ⚠️ Pitfalls

- **`worktree.py` is where silent data loss happens.** The trial hooks sit in stash-restore,
  finalize, post-commit pop and land (`docs/reference/multi-session-worktree.md`). Removing
  them must leave non-trial behaviour byte-identical. Prove it with the existing land/finalize
  tests, not new ones written to pass. A fix can introduce a defect that passes every gate
  (`[fail:design] fix-introduced-defect-passes-all-gates`, count 18).
- **`_trial_active` makes stage-span emission mandatory (`worktree.py:5148`).** Removing it
  silently changes when spans are required. Check `task_lead_time_hours`, which reads
  `stage-spans.jsonl`, and the span emission paths, so the one metric everybody uses does not
  lose data.
- **Schema keys in user files.** Dropping a top-level key (`owners`, `open_questions`) makes
  consumer files fail validation (`intent.py:308-310`). Keep tolerating it or migrate it, and
  never break a filled consumer `intent.yaml`.
- **Vacuous assertions after deletion.** When tests are rewritten around removed code, assert
  the surviving invariant across real dimensions
  (`[fail:test] assertion-invariant-over-named-dimension`, count 22).
- **Rendered dogfood runs the released cache.** Templates in this repo call the 0.62.0 plugin
  cache. Removing a verb that a rendered template still calls only fails after the next
  release (`project_rendered_harness_pins_released_plugin`). Grep rendered templates for every
  removed verb before deleting it.
- **Surface allowance expires at wrapup.** Any template change in Approach C needs a terminal
  retire phase for the ratchet growth or shrink (`project_surface_allowance_expires_at_wrapup`).
- **Pre-registered rules.** UNDERSTANDING-HANDOFF's judgment window and the withdrawal
  criterion stay as written (`feedback_honor_preregistered_rules`). The diet is a separate
  decision and does not fire, reinterpret or reset either one.
- **Status-payload shrink is silent in the digest.** If Approach B removes fields, the digest
  counts quietly fall to 0 rather than failing (`world_model_digest.py:306-320`), so a
  regression would look like "all clear".

## ❓ Open Questions

1. **Scope:** Approach A only, A + the optional add-ons (`intent_migrate`, the owners
   advisory), or A + C in sequence? (B is recommended for later, or never.)
2. **`intent_migrate`:** do any consumer projects still hold a legacy layout
   (`work-docs/INTENT-*.md`, `world/objectives/`)? The backup copies in neuroTerm suggest
   repeated re-renders. Verify before deleting the migrate path.
3. **Span emission without the trial:** after `_trial_active` goes, should stage-span emission
   stay best-effort (the pre-trial behaviour) or become unconditionally mandatory? This decides
   whether `task_lead_time_hours` can lose rows.
4. **Review Step 3.3** (2 real P2s in 12 reviews; 1,304 B per copy): keep, shrink, or fold into
   the general reviewer brief? This is a C-side decision.
5. **Feedback collection** (~4.4 KB per pipeline, mostly self-referential rows): keep the
   per-stage collection, or collect only at wrapup 5.7?
6. **Approval content hash:** keep it as a rail although the gate never fired? (Recommended:
   keep. It is cheap and its value is in the case that never happened.)
7. **Release cadence:** ship A as a patch release on its own so consumers do not receive a
   mixed change?

## 📚 Sources

- No external sources. The codebase and local records are authoritative for this internal
  question.
- Caller map, rendered-surface measurement and usage evidence were gathered 2026-10-04 at
  `94916873` (main) by three read-only explorations. Key locators are cited inline.

## 🔗 Related Internal Docs

- [[SPEC-intent-world-model-objective-layer]] — original layer: intent.yaml, assumptions, objectives, content-hash approval
- [[SPEC-world-intent-closed-loop]], [[SPEC-world-intent-closed-loop-trial]], [[PLAN-world-intent-closed-loop-trial]] — the trial (frozen 0/3)
- [[SPEC-intent-feedback-continuity]] — cross-session trial collection
- [[SPEC-understanding-handoff]] — in-flight measurement; do not touch
- [[REVIEW-source-plan-steps-2026-09-18]] — one of the two real Step 3.3 findings
- `[wiki:architecture] intent-layer-withdrawal-instrument`, `[wiki:architecture] intent-vocabulary-and-owners`
- `docs/reference/multi-session-worktree.md` — must read before touching `worktree.py`

## Feedback

| Evidence | Affected ID | Update status | Decision | Owner | Authority | Next action |
|---|---|---|---|---|---|---|
| Usage census 2026-10-04: trial never produced a verdict (0/3); revisits, revalidation, conflicts and the autopilot objective halt never fired; status and auto-measure are the used parts | purpose ("remove devices that do not pay their way") | recorded | question add q_intent_layer_unfired_paths (confirmed) | operator | wrapup Step 5.7 | none |
