---
type: review
task_slug: intent-world-model-objective-layer
status: APPROVED
human_review_needed: true
final_grade: A
exit_reason: converged
confirm_pass_ran: true
confirm_pass_new_severe_n: 2
created: 2026-09-16
run_id: 407d8829a51a
review_base: 3b215d4d9e27f6481cb33e2cb0ec8eb98eebf606
reviewers_invoked: [code-reviewer (design+functionality+robustness+consistency), security-reviewer, concurrency-reviewer, test-reviewer, codex (second opinion)]
consensus_method: cross-check
drift_verdict:
  result: scope_violation
  scope_violations: ["src/harness_maker/templates/rubrics/objective_candidate.yaml.j2"]
  scenario_misses: []
  task_slug: intent-world-model-objective-layer
  computed_at: 2026-09-16T05:20:00Z
second_opinion_results:
  - model: codex
    status: invoked
    reason: null
    findings_n: 5
---

# REVIEW — intent-world-model-objective-layer

Diff under review: `review_base..worktree` — 61 changed paths (32 modified, 29 new): `intent.py`,
`world.py`, the `objective_gate` in `autopilot_caps.py`, deliverable state paths, registrations,
three stage templates, the `intent-layer` skill, one rubric, tests and fixtures.

## 🎯 Round 1 Summary

- Grade **C** — 4 consensus-passed P1, 0 P0. Coverage: all 7 lenses exercised
  (`blocks_approval: false`).
- Fixes pending: 4 (all P1). Manual items: 6 P2 + 1 P3 + 3 cross-model P2 (see sections 5 and 7).
- `human_review_needed: true` — one cross-model P1 (`0fd4c1b3917670a8`) is `manual-only`; it was
  refuted against the SPEC (see section 7) but the unverified-severe scan counts it by rule.

## 🔍 Drift Findings

| id | Sev | Path | Finding |
|---|---|---|---|
| 47df1814f55e6333 | P1 | `src/harness_maker/templates/rubrics/objective_candidate.yaml.j2` | Untracked rubric withdrawn during the PLAN interview (rev 6.1 rejected the LLM candidate-quality rubric); outside every PLAN phase scope and referenced by nothing in `src/`, `tests/`, SPEC or PLAN. Wrapup stages `src/`, so it would ship inside the plugin. |

Incomplete phases: none. PLAN Phase 0–5 scope covers the other 60 paths. Step 2.5: the PLAN has
no `common_ground_marks`; nothing to record. Step 3.3: the PLAN frontmatter carries no
`objective:` link (`[intent] no objective link — skipping`).

## ✅ Consensus Findings

### P1

| id | Lens | File:line | Summary |
|---|---|---|---|
| 7ae176ec8649d584 | security | `templates/stages/review.md.j2:388` | Step 3.3 pastes the PLAN frontmatter `objective:` value into a live `!uv run … hm world objective show <id>` line with no charset check; the same file treats file-sourced text as untrusted at Step 3.4. |
| de7bd4a2688b4fe8 | consistency (+ codex `a747b9d6a9a09b8e`) | `world.py:887` | `validate_objective_record` claims file-validator parity but checks 5 of ~15 rules (no title/hypothesis type, scope element type, state, approval shape, closed-state triad); `edit_objective` can persist a record the next `load_world` reports broken. |
| 251c347738d55c61 | tests | `tests/unit/world_fixture.py:22` | Fixture and subject build the hash payload dicts in the same alphabetical order, so a subject that drops `sort_keys=True` still matches byte for byte; with the mutation gate broken this run (zero mutants), nothing else catches it. |
| 47df1814f55e6333 | main-loop | `templates/rubrics/objective_candidate.yaml.j2:1` | Scope drift — see above. |

### P2

| id | Lens | File:line | Summary |
|---|---|---|---|
| b06ddab117a1ec62 | design | `world.py:869` | `edit_objective` has no CLI verb, no skill mention and no caller outside `test_world_objectives.py`; either wire `objective edit` or drop it. |
| 0113599236b5eb09 | consistency | `world.py:52` | `HASHED_FIELDS` is declared and never read; `approval_hash` hardcodes the same list. |
| 6a0df4c87afe737d | concurrency | `world.py:822` | `transition()` derives `approval_valid` from a snapshot and writes without re-deriving (TOCTOU across files). Downgraded from P1: the SPEC Constraints row accepts last-writer-wins and disclaims cross-file write invariants; writers are operator-paced. |
| 64d492719e78a4a6 | concurrency | `intent.py:109` | `write_skeleton_if_absent` is `exists()` then write; two concurrent `make` runs can both pass the check. Content is identical, so the loss is a user-created placeholder in the gap. |
| 2b45640210bbf4fa | tests | `tests/unit/test_intent_update_invariance.py:38` | AC-003's make-wiring test greps `cli.py` source for `write_skeleton_if_absent(`; nothing asserts that `hm make` writes the file (the lifecycle fixture overwrites it immediately). |

### P3

| id | Lens | File:line | Summary |
|---|---|---|---|
| 87f7f55410df44cb | tests | `tests/unit/test_render_intent_layer.py:160` | AC-019 body assertions read only the Claude Code arm; the Codex arm is checked for existence only, and the `is_codex` branch sits exactly in the ORDERED_RULE region. |

## ⚠️ Weak Consensus

None.

## 📝 Manual-Only Findings

Cross-model findings with a single voice (section 7 holds the frozen record):

| id | Sev | File:line | Summary | Disposition |
|---|---|---|---|---|
| 0fd4c1b3917670a8 | P1 | `autopilot_caps.py:317` | Gate checks `approval_valid` only; an objective with `needs_revalidation: true` advances. | **rejected — AC-012** (SPEC S4 line 137: "the flag appears in no file, and it blocks nothing"; Gate precedence row fixes `reason ∈ {link_invalid, missing, not_active, approval_invalid}`). |
| 889c342883fae2a7 | P2 | `world.py:487` | `load_world` keeps every `values` row whose `outcome_id` exists even when `validate_outcomes` flagged it; a row without `value` makes `last_value` raise `KeyError` before `status_report` can report the error. | accepted |
| 0eadd6c9f6e3b3ef | P2 | `intent.py:239` | `schema_version: "1.0"` passes `validate_intent` (major parsed from the string) but `load_intent` does `int("1.0")` → `ValueError`. | accepted |
| a747b9d6a9a09b8e | P2 | `world.py:895` | In-memory validator omits scope element types / hypothesis / title. | duplicate of `de7bd4a2688b4fe8` (corroborating voice) |
| 5202e61acb247105 | P2 | `templates/stages/wrapup.md.j2:576` | 5.7 offers `supersedes` but the observe line carries no `--claim`; `world.observe` refuses `supersedes` without one, so that branch of the rendered command always fails. | accepted |

## 🤝 Disagreements

- **concurrency P0 → dropped.** Pass 1 rated the lock-free read-modify-write in every `hm world`
  writer P0. Pass 2 dropped it: SPEC Constraints line 264 names exactly this ("last-writer-wins
  per file, atomic; accepted loss") and every write is answer-gated. Recorded here because the
  finding is correct about the code and wrong about the contract.
- **tests P2 → P1.** The `sort_keys` blind spot was raised to P1 in Pass 2 on the ground that the
  mutation gate, the only other net for it, is recorded as broken in the PLAN.
- **security P2 (`yaml.safe_load` anchors) → dropped** in Pass 2: no code-execution vector,
  files are locally trusted by contract.

## 🧊 Cross-model findings (frozen @ round 1)

Model `codex` invoked once (`status: invoked`), 5 findings, ids stamped by the adapter. PIDA
(code-verifier mode B, oracle = read-only probes over the worktree) dispositions are ledgered
via `second_opinion_invoke --record-disposition` (5 rows).

| id | Sev | disposition | lifecycle | oracle |
|---|---|---|---|---|
| 0fd4c1b3917670a8 | P1 | rejected (AC-012) | stale | SPEC S4 "blocks nothing"; reason enum has four values |
| 889c342883fae2a7 | P2 | accepted | pending | `load_world` filters on `outcome_id` only; `last_value` reads `best["value"]` unguarded |
| 0eadd6c9f6e3b3ef | P2 | accepted | pending | `validate_intent` errors `[]`; `load_intent` raised `ValueError` |
| a747b9d6a9a09b8e | P2 | duplicate | resolved with `de7bd4a2688b4fe8` | in-memory validator lacked hypothesis/title/scope-element checks |
| 5202e61acb247105 | P2 | accepted | pending | observe raises on `supersedes` without claim; wrapup line has no `--claim` |

## Auto-fix loop

### Iteration 2 (Grade: C → A)
Fixes applied: 4

| # | Severity | Summary | File | Status |
|---|----------|---------|------|--------|
| 1 | P1 | `validate_objective` split into `_validate_objective_raw(path, raw, …)`; `validate_objective_record` now runs that same rule set over the in-memory record (docstring rewritten to say what it does). | `src/harness_maker/world.py` | Applied · caused_by=none |
| 2 | P1 | Step 3.3 requires `<id>` to match `[A-Z0-9-]+` before substitution; on mismatch prints `[intent] objective id malformed — skipping` and does not run the command. Snapshots regenerated; `autopilot_gate_golden.json` re-captured with attribution (`review` alone moved in all four arms). | `src/harness_maker/templates/stages/review.md.j2` | Applied · caused_by=none |
| 3 | P1 | Fixture hash payloads built in reverse key order so a subject without `sort_keys=True` no longer matches; docstring explains why. | `tests/unit/world_fixture.py` | Applied · caused_by=none |
| 4 | P1 | Withdrawn, unreferenced rubric deleted (`rg objective_candidate` → 0 hits). | `src/harness_maker/templates/rubrics/objective_candidate.yaml.j2` | Applied · caused_by=none |

Verification: `ruff check` / `ruff format --check` clean on the edited files; `mypy --strict world.py`
clean; targeted suites (world ×5, intent ×3, render, objective gate, lifecycle, roundtrip budget,
step-sensitivity registry, gate render golden, snapshots, codex phase7, synthesize codex,
deliverable single-source, surface baseline, plan net surface, redundancy matrix, CLI surfaces)
all green; `spec_machine check --all` ok. Full suite: see Final Summary.

Re-review: churn 0.74 ≥ 0.30 → `review_consensus plan` named one `code-reviewer` functionality
dispatch over the four hunks; it returned no findings (`_validate_objective_raw` parity traced
through `edit_objective`; fixture literals verified as exact reversals; zero references to the
deleted rubric).

Remaining: 6 lens (5 P2 + 1 P3) + 3 cross-model P2, all `accepted`, none grade-bearing | New issues introduced: 0
Churn: 0.744 (max: tests/structural/autopilot_gate_golden.json, measured 13, excluded 1 — the deleted rubric)

Full suite after round 2: 100 %, 0 failures, `rc=0` (recorded in the run's output file, not the
notification).

## Confirmation pass

### confirm-1 — `review_base..da2906d3` (frozen working tree), 4 dispatches, all 7 lenses exercised

Cross-model voters re-read from section 7, not re-invoked. New findings (ids absent from every
prior round's consensus-passed set):

| id | Lens | Sev | File:line | Summary | Disposition |
|---|---|---|---|---|---|
| 97152d052f242122 | tests | **P1** | `tests/unit/world_fixture.py:22` | The round-2 repair for `251c347738d55c61` did not discriminate: the fixture's `canonical_hash` sorts unconditionally and the subject's own literals are alphabetical, so reversing the fixture's key order changed nothing and its docstring made a false causal claim. | accepted — repaired below |
| 7528e43ebf147668 | functionality | **P1** | `src/harness_maker/world.py:810` | `approve()` reads `git config user.name` at the checkout root; SPEC Constraints "Approval provenance" says the base root, and `world.py` never called `resolve_base_root`. Inside a task worktree the wrong config can be stamped. | accepted — repaired below |
| c4302c15c4c8185b | consistency | P2 | `templates/stages/wrapup.md.j2:574` | 5.7 offers "one option per assumption id (from the status output)", but `status_report` carries only the `conflicts` ids. | accepted, not fixed (P2) |
| ada23fd3e4f1b1a4 | robustness | P2 | `autopilot_caps.py:309` | Bare `except Exception` around `load_world` relabels any crash (permissions, a bug) as `link_invalid`. | accepted, not fixed (P2) |
| 1fc12c0beb608d78 | consistency | P3 | `autopilot_caps.py:273` | `parse_error` is set for a successfully parsed non-mapping frontmatter, wider than the field's documented meaning. | accepted, not fixed (P3) |

security and concurrency: no new findings (Step 3.3 repair confirmed; `gate_blocked` append is a
`PIPE_BUF`-bounded `O_APPEND` line; `checkout_root`/`_git_user_name` carry `timeout=10` and the
three-exception matrix; the state globs land through the existing merge fence).

Outcome: two new consensus-passed P1 → **one repair round** (budgeted separately, does not
increment `iteration_count`), then confirm-2. Ledger row: `confirmation-pass --pass 1 FAIL`.

### Repair round (after confirm-1)

| # | Severity | Summary | File | Status |
|---|----------|---------|------|--------|
| 5 | P1 | Fixture key order reverted to the SPEC literal order; docstring now states the real limitation and names the closing test. New `test_ac_009_canonical_json_sorts_keys_it_was_not_handed_sorted` calls the subject's `canonical_json` with an out-of-order dict and asserts the sorted text (probe: a `sort_keys`-less canonicaliser fails it). Bound to AC-009 via `spec_machine mark-tested`. | `tests/unit/world_fixture.py`, `tests/unit/test_world_objectives.py`, machine SPEC | Applied · caused_by=#3 |
| 6 | P1 | `approve()` now calls `_git_user_name(resolve_base_root(root))` (import from `second_opinion_invoke`, no cycle). New `test_ac_009_approve_reads_the_name_at_the_base_root_from_a_linked_worktree` builds a real linked worktree and asserts the name lookup is asked at the base; bound to AC-009. | `src/harness_maker/world.py`, `tests/unit/test_world_objectives.py`, machine SPEC | Applied · caused_by=none |

Verification: ruff/format clean, `mypy --strict world.py` clean, world/intent/lifecycle/objective-gate/marker-API suites green, `spec_machine check --all` ok. Full suite re-run: see Final Summary.

### confirm-2 — `review_base..b0410f9f` (frozen after the repair round), 4 dispatches

All 7 lenses exercised (`blocks_approval: false`). **Zero new findings** on every lens: the
base-root provenance and the `canonical_json` oracle were re-verified (the linked-worktree test
calls the real `resolve_base_root`; only `_git_user_name` is stubbed), the objective-gate matrix
in `autopilot_caps.py` was traced against SPEC S7, and the rubric's single-line `target:` was
confirmed documentation-only (dual-target enforcement lives in the machine SPEC's
`judgment_subject_paths`). Cross-model voters re-read from section 7.

Outcome: **APPROVED** — every mandatory lens exercised and no new consensus-passed P0/P1.
Ledger row: `confirmation-pass --pass 2 PASS --terminal`. Freeze refs reaped (base, confirm-1,
confirm-2).

## 🔁 Oscillation

`review_churn oscillation --rounds 2,3` → `[]`. Nothing to report.

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | C     | —             | 15 (4 P1 · 6 P2 · 1 P3 · 4 cross-model, 1 rejected) | — |
| 2         | A     | 4             | 11 (none grade-bearing) | 0 |
| confirm-1 | —     | —             | +5 (2 P1 · 2 P2 · 1 P3) | 5 |
| repair    | A     | 2             | 14 (7 P2 · 2 P3 · 4 cross-model, 1 rejected, 1 duplicate) | 0 |
| confirm-2 | A     | —             | 14 | 0 |

Final grade: **A**
Iterations used: 2 / 3 (plus one separately budgeted confirmation repair round)
Exit reason: converged

## 📏 Size & Complexity

| File | LOC | Cyclomatic | Max nesting | Status |
|------|-----|------------|-------------|--------|
| `src/harness_maker/world.py` (round 2) | 1050 → 1057 | 233 → 226 | 5 → 5 | measured |
| `src/harness_maker/world.py` (repair) | 1057 → 1060 | 226 → 226 | 5 → 5 | measured |
| `tests/unit/world_fixture.py` | 228 → 234 → 234 | 17 → 17 | 2 → 2 | measured |
| `tests/unit/test_world_objectives.py` (repair) | 289 → 330 | 45 → 49 | null | measured |
| `tests/structural/test_autopilot_gate_render.py` | 303 → 305 | 28 → 28 | 3 → 3 | measured |
| `src/harness_maker/templates/stages/review.md.j2` | 1283 → 1283 | null | null | not-python |
| `src/harness_maker/templates/rubrics/objective_candidate.yaml.j2` | 52 → null | null | null | not-python (deleted) |
| 8 × `tests/snapshot/*.expected.yaml`, `autopilot_gate_golden.json`, machine SPEC | unchanged LOC / 115 → 121 / 843 → 845 | null | null | not-python |

Status: **APPROVED**
human_review_needed: **true** — the only unverified severe item is the cross-model P1
`0fd4c1b3917670a8` (`manual-only`, disposition `rejected` against AC-012 / SPEC S4). The scan
counts every manual-only P0/P1 except cross-model `unresolved`, so this flag is set by rule even
though the finding was refuted with a SPEC citation. The human question is one line: *is the
gate meant to stay blind to `needs_revalidation`?* The SPEC says yes (S4: "it blocks nothing").
Counters (see §5): unreviewed 0 · prior-fix 1 (`97152d052f242122` caused by fix #3) · unattributed 0

## Open items for wrapup / follow-up (not grade-bearing)

- P2 `889c342883fae2a7` — filter `values` rows that failed `validate_outcomes` before `world.values`, or guard `best["value"]`.
- P2 `0eadd6c9f6e3b3ef` — `load_intent` should parse the major the same way `schema_version_error` does (or refuse string versions in both).
- P2 `5202e61acb247105` — wrapup 5.7 needs a `--claim` prompt on the `supersedes` branch.
- P2 `c4302c15c4c8185b` — wrapup 5.7 "ids from the status output": add the full assumption id list to `status_report` or point at the file.
- P2 `b06ddab117a1ec62` / `0113599236b5eb09` — `edit_objective` has no caller; `HASHED_FIELDS` unread.
- P2 `6a0df4c87afe737d` / `64d492719e78a4a6` — accepted TOCTOU windows (SPEC line 264).
- P2 `ada23fd3e4f1b1a4` — narrow the `except Exception` around `load_world` in the gate.
- P2 `2b45640210bbf4fa` — make AC-003's wiring test observe the file after a real `make`.
- P3 `87f7f55410df44cb`, `1fc12c0beb608d78` — Codex-arm body check; `parse_error` semantics.
- AC-017 was judged PASS on the pre-fix render; Step 3.3 gained one sentence (id charset check). The subject hash in the machine SPEC still validates (`spec_machine check --all` ok); a re-judge is optional.
- Known gap carried from execute: `spec_mutation gate` collected zero mutants (mutmut 2.5.1); killing a direct `mutmut run` leaves the subject mutated on disk.
