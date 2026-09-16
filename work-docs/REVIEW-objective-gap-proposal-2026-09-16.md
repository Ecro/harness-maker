---
type: review
task_slug: objective-gap-proposal
status: APPROVED
human_review_needed: false
final_grade: A
exit_reason: converged
confirm_pass_ran: true
confirm_pass_new_severe_n: 0
created: 2026-09-16
run_id: 9009090fca0a
review_base: 3edcca62d640708c2f5afbd931457a1eb72f5470
reviewers_invoked: [code-reviewer (design+functionality+robustness+consistency), security-reviewer, concurrency-reviewer, test-reviewer, codex (second opinion)]
consensus_method: cross-check
drift_verdict:
  result: clean
  scope_violations: []
  scenario_misses: []
  task_slug: objective-gap-proposal
  computed_at: 2026-09-16T13:50:00Z
second_opinion_results:
  - model: codex
    status: invoked
    reason: null
    findings_n: 5
---

# REVIEW — objective-gap-proposal

Diff under review: the worktree diff — 35 changed paths (28 modified, 7 new): `world.py`
(`gap_report`, `gap` verb, `new_objective --from-proposal/--candidates/--declined`,
`_record_proposal`), `autopilot_ledger.py` (`objective_proposed`), `command_registry.py`,
`step_sensitivity.py`, the `intent-layer` skill and `plan.md.j2` (Step 0.5 consent, Step 4.9),
both baselines (inherited fold + own retirement), the gate golden, the round-trip table, eight
snapshots, tests, docs and the four deliverables.

> `review_base` resolved to `3edcca62` (two commits back — the merge-base recipe), so the
> confirmation-pass span `review_base..freeze` includes the already-reviewed playbook-alignment
> commit `2fd69df7`; the confirmation briefs name it as out of scope.

## 🎯 Round 1 Summary

- Grade **B** — 1 consensus-passed P1, 0 P0. Coverage: all 7 lenses exercised
  (`blocks_approval: false`).
- Fixes pending: 1 (P1). Manual items: 7 P2 + 2 P3 lens findings (P2/P3 do not enter the auto-fix
  queue at B), 3 cross-model manual-only (2 accepted, 1 unresolved) + 2 cross-model duplicates.
- `human_review_needed: false` (no manual-only / weak-consensus P0/P1).

## 🔍 Drift Findings

None. Every changed path is in a PLAN phase scope or in its Phase 0/4/6 notes (`CLAUDE.md`
`unsourced` count and `MATRIX-native-redundancy.md` row are the registry's docs mirror the
step-sensitivity gate requires). Step 2.5: no `common_ground_marks`. Step 3.3: the PLAN frontmatter
carries no `objective:` link (`[intent] no objective link — skipping`).

## ✅ Consensus Findings

### P1

| id | Lens | File:line | Summary |
|---|---|---|---|
| 3dcbfe378028c1a7 | tests | `tests/unit/test_intent_doc_new.py:177` | `_real_base_rows_before()` compares the real shared `auto-advance.jsonl` before/after — vacuous for the path under test (the fixture root is its own git toplevel, so `resolve_base_root(root) == root`) and flaky under a concurrent session; the shape `test_ledger_isolation.py` explicitly rejects. Replace with a linked-worktree fixture. |

### P2

| id | Lens | File:line | Summary |
|---|---|---|---|
| 0a2499c3a32ef07d | design | `templates/stages/plan.md.j2:105` | The draft-consent question is reachable only after "Which objective does this task serve?", which the zero-objective early exit skips — a filled-in project with no objectives never reaches Step 4.9 from `/hm:plan` (the skill route still covers cold start). |
| def6e233535c0c86 | security | `templates/stages/plan.md.j2:729` | Step 4.9 interpolates LLM-derived `<title>`/`<hypothesis>` into an agent-executed Bash line with no escaping rule (same class as the previous review's `--claim`, P2). |
| 833320fadde3f3a6 | security | `templates/skills/intent-layer/SKILL.md.j2:60` | Same sink for `--declined "<title>"` with LLM-proposed titles. |
| 70612e6161e03557 | concurrency | `world.py:1140` | Ledger row at base before the record reaches base (ADR-003 accepted limit); the promised "rows ÷ proposed+approved files" read is prose-only — no code computes it. |
| 0414f390d824bc7a | concurrency + codex | `world.py:784` | `gap_report` loads the world twice (`status_report` then `load_world`) and merges fields from two snapshots. Strong consensus (lens + codex 3079e9ee). |
| 99cf44b51d9f19b9 | concurrency | `world.py:1104` | `new_objective` exists()-then-write TOCTOU, now more reachable via the deterministic `OBJ-<SLUG>` id (prior open item d64291c7). |
| e83ab2ec3e9127ad | tests | `tests/unit/test_world_gap.py:132` | The objective-row test never bounds the key set — widening `_GAP_OBJECTIVE_KEYS` to include `approval` (an identity) would pass. |

### P3

| id | Lens | File:line | Summary |
|---|---|---|---|
| 9fa711848d7a3fd4 | consistency | `templates/skills/intent-layer/SKILL.md.j2:53` | Code span `observed: missed` split across a line wrap. |
| 7b549f6d0328b81b | consistency | `tests/unit/test_render_intent_layer.py:223` | `GAP_SKILL_PHRASES_CLAUDE` is asserted on both arms — misleading name. |

## ⚠️ Weak Consensus

None.

## 📝 Manual-Only Findings

| id | Sev | File:line | Summary | Disposition |
|---|---|---|---|---|
| 9d91e51417ca34e6 | P2 | `templates/stages/plan.md.j2:724` | "the outcome the interview named" has no producer — no plan step elicits an outcome id, so a consented draft may have no outcome to name. | accepted (single cross-model voice) |
| 22d6fb0d30c24ec5 | P2 | `world.py:1147` | `resolve_base_root` falls back to cwd on a git failure, so the row lands in the worktree ledger, the append succeeds and the warning never fires; `task-land` then drops it. | accepted (single cross-model voice) |
| aff57685de2da7ee | P2 | `templates/skills/intent-layer/SKILL.md.j2:56` | The proposal flow's "show the arguments, run" may conflict with the skill's general ask-then-write rule (an extra ask per accepted candidate, or a write without an argument-level consent). | unresolved (`no-contract`; PIDA had no `.j2` oracle) — provenance exception, does not set `human_review_needed` |
| 3079e9ee69e43983 | P2 | `world.py:787` | Duplicate of 0414f390 (two-snapshot gap report). | duplicate |
| c3680af200cff5cc | P2 | `tests/unit/test_intent_doc_new.py:174` | Duplicate of 3dcbfe37 (real-base guard watches the wrong ledger). | duplicate |

## 🤝 Disagreements

- **security P1 → P2 (Pass 2).** Pass 1 rated the Step 4.9 sink P1 over its skill sibling on
  operator-visibility grounds; Pass 2 found both sinks share the same source (derived free text)
  and the same print-only gate, and the prior review rated the class P2 — normalized.
- **concurrency P1 → P2 (Pass 2).** The worktree/base row split is an ADR-003 accepted limit
  with alternatives rejected; kept as P2 because the stated mitigation is unimplemented, not
  because the race was missed.
- **core design P2 on SPEC S5 → dropped (Pass 2).** Restated the plan.md.j2:105 finding as a
  SPEC contradiction; the SPEC's "both" proposer decision means the skill owns cold start.
- **tests P1 vs codex P2 on the same guard.** Same defect, different tiers — not bridged;
  the codex row is recorded as a duplicate of the lens finding.

## 🧊 Cross-model findings (frozen @ round 1)

`frozen_at_round: 1` · `models: [codex]` · invoked once (`status: invoked`, 63 s) · PIDA
(code-verifier mode B; oracle = ruff/mypy/pytest over the changed `.py` paths, none for `.j2`)
→ 4 accepted, 1 unresolved; dispositions ledgered (5 rows).

| id | source | severity | file:line | summary | evidence | needs_relaxation | disposition | oracle_result | status | invalidation_reason |
|---|---|---|---|---|---|---|---|---|---|---|
| 3079e9ee69e43983 | codex | P2 | `world.py:787` | gap report combines two filesystem snapshots | status_report + load_world | false | accepted → duplicate of 0414f390 | two loads, no caching | pending | — |
| aff57685de2da7ee | codex | P2 | `SKILL.md.j2:56` | proposal flow vs the general answer-gating rule | steps 4–5 vs rule 2 | false | unresolved | no `.j2` toolchain; prose tension, possibly intended | pending | — |
| 9d91e51417ca34e6 | codex | P2 | `plan.md.j2:724` | consent without an outcome ever being elicited | "the outcome the interview named" has no producer | false | accepted | confirmed: no step elicits an outcome id | pending | — |
| 22d6fb0d30c24ec5 | codex | P2 | `world.py:1147` | git failure sends the row to the worktree ledger silently | resolve_base_root cwd fallback | false | accepted | append succeeds, warn path never fires | pending | — |
| c3680af200cff5cc | codex | P2 | `test_intent_doc_new.py:174` | real-base guard watches the wrong ledger | `_REAL_BASE = parents[2]` is this worktree | false | accepted → duplicate of 3dcbfe37 | vacuous guard | pending | — |

## Auto-fix loop

### Iteration 2 (Grade: B → A)
Fixes applied: 1

| # | Severity | Summary | File | Status |
|---|----------|---------|------|--------|
| 1 | P1 | Dropped `_REAL_BASE` / `_real_base_rows_before()` and both uses; added `_git()` + `test_ac_003_a_linked_worktree_writes_the_row_at_base_and_the_record_in_the_worktree` (throwaway base repo, `git worktree add -b hm/t`, verb run inside the linked worktree; record only in the worktree, `objective_proposed` row only under the base's ledger, worktree ledger empty). | `tests/unit/test_intent_doc_new.py` | Applied · caused_by=none |

Verification: ruff/format/mypy strict clean; `test_intent_doc_new.py` 14 passed (the new fixture
exercises `resolve_base_root`'s linked-worktree branch for the first time — it would fail if
`_record_proposal` wrote to `root`).

Re-review: churn 1.0 (max: the REVIEW document itself, new; `test_intent_doc_new.py` 0.14) ≥ 0.30 →
`review_consensus plan` named one `code-reviewer` functionality dispatch; it returned no findings
(the new test discriminates the base/worktree split; no assertion AC-003 needs was lost; no
production code changed). Finding 3dcbfe37 → `resolved`; codex duplicate c3680af2 follows it.

Remaining: 7 P2 + 2 P3 lens (consensus-passed, not grade-bearing at A) + 2 cross-model manual-only
accepted + 1 unresolved | New issues introduced: 0
Churn: 1.0 (max: work-docs/REVIEW-objective-gap-proposal-2026-09-16.md, measured 2, excluded 0)
Complexity: `tests/unit/test_intent_doc_new.py` LOC 278 → 294, cyclomatic 57 → 60, nesting 1 → 1 (measured).

## Confirmation pass

### confirm-1 — `review_base..eee332bd` (frozen working tree), 4 dispatches

All 7 lenses exercised (`blocks_approval: false`). The span includes the already-reviewed
playbook-alignment commit `2fd69df7`; briefs named it out of scope. Cross-model voters re-read
from section 7 (not re-invoked). New findings: **zero at P0/P1**; two P2:

| id | Lens | Sev | File:line | Summary | Disposition |
|---|---|---|---|---|---|
| (confirm-1 core) | design | P2 | `world.py:1152` | `accepted: 1` on the `objective_proposed` row has no reader — the row's presence already says it. SPEC S3/AC-003 name the field, so dropping it is a SPEC change. | accepted, not fixed (P2) |
| (confirm-1 tests) | tests | P2 | `tests/unit/test_intent_doc_new.py:229` | The four refusal parametrizations share one OR-substring assertion; an unrelated error mentioning "candidates" would pass. Assert the literal refusal text per id. | accepted, not fixed (P2) |

security and concurrency returned no findings (yaml.safe_dump on `rejected[]`, id regex gates the
path before the new flags, `_git` helper uses list argv + timeout; the linked-worktree fixture
lives entirely under `tmp_path`, xdist-safe; O_APPEND ledger line unchanged).

Outcome: **APPROVED** — every mandatory lens exercised and no new severe finding. Ledger:
`confirmation-pass --pass 1 PASS --terminal`. Freeze refs reaped. Run `9009090fca0a` closed.

## 🔁 Oscillation

`review_churn oscillation --rounds 2` → `[]`.

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | B     | —             | 15 (1 P1 · 7 P2 · 2 P3 · 5 cross-model) | — |
| 2         | A     | 1             | 14 (none grade-bearing) | 0 |
| confirm-1 | A     | —             | 16 | 2 (P2) |

Final grade: **A**
Iterations used: 2 / 3
Exit reason: converged

## 📏 Size & Complexity

| File | LOC | Cyclomatic | Max nesting | Status |
|------|-----|------------|-------------|--------|
| `tests/unit/test_intent_doc_new.py` (round 2) | 278 → 294 | 57 → 60 | 1 → 1 | measured |
| `work-docs/REVIEW-objective-gap-proposal-2026-09-16.md` | null → 122 | null | null | not-python |

Status: **APPROVED**
human_review_needed: **false**
Counters (see §5): unreviewed 0 (the one fix was re-reviewed) · prior-fix 0 · unattributed 0

## Open items for wrapup / follow-up (not grade-bearing)

- ~~P2 `0a2499c3`~~ — **fixed after the review at the user's direction (post-verify, before
  wrapup):** Step 0.5 now skips the pick and asks the consent question directly when the intent
  is filled in but no objective exists; AC-005 pins the branch (both arms); SPEC S5 widened;
  plan +166/arm re-folded into both baselines, the gate golden and both delta-doc pins.
- P2 `def6e233` / `833320fa` — escaping rule for LLM-derived text in the Step 4.9 and skill
  `objective new` lines (same class as the open `--claim` item from playbook-alignment).
- P2 `70612e61` — the "rows ÷ proposed+approved files" adoption read is prose-only; no code
  computes it. P2 (confirm-1) — `accepted: 1` has no reader (SPEC-named field).
- ~~P2 `0414f390` (+ codex 3079e9ee)~~ — **fixed after the review at the user's direction:**
  `gap_report` loads the world once and shares `_status_payload(world)` with `status_report`
  (`_invalid_payload` shared too); `status` output unchanged (golden test green).
- P2 `99cf44b5` — `new_objective` exists-then-write TOCTOU (carried from playbook-alignment).
- P2 `e83ab2ec` — bound the objective-row key set in `test_world_gap.py`. P2 (confirm-1) —
  tighten the refusal assertions per parametrize id.
- Cross-model P2 `9d91e514` — Step 4.9 says "the outcome the interview named" but nothing
  elicits one; add an outcome pick to the consent question or to Step 4.9.
- Cross-model P2 `22d6fb0d` — `resolve_base_root`'s cwd fallback can route the row to the
  worktree ledger silently.
- Cross-model `aff57685` (unresolved) — reconcile the skill's general ask-then-write rule with the
  proposal section's "show the arguments, run".
- P3 `9fa71184` split code span; P3 `7b549f6d` rename `GAP_SKILL_PHRASES_CLAUDE`.
