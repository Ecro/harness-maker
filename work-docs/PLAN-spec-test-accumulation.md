---
type: plan
task_slug: spec-test-accumulation
status: complete
created: 2026-05-29
tags: [harness-maker, plan, spec-driven, testing, mutation, verification]
research_doc: "[[RESEARCH-spec-test-accumulation]]"
interview_rounds: 4
adrs: 9
validator_outcome: MAJOR_REVISION_RESOLVED
summary: "Bridge execute↔machine.yaml: forward-bind mechanical ACs to tests + wrapup write-back so machine.yaml becomes living"
---

# PLAN: spec-test-accumulation

## 🎯 Executive Summary

**What:** Make `/hm:execute` consume `SPEC-{slug}.machine.yaml` as the source of truth on the everyday TDD path, so the AC→test_id→mutation graph that `/hm:spec` writes accumulates *forward* instead of being reconstructed retroactively by the backfill loop (`reverse_map.py`).

**Why:** Today execute authors `test_s1_*` tests from SPEC.md prose scenarios and ignores `machine.yaml` entirely (RESEARCH-spec-test-accumulation). The rich verifiable spec graph is cosmetic during normal feature work — specs and tests never bind to each other unless the spec-coverage backfill loop runs. This is the root cause of "spec 과 test 가 정확히 안 쌓인다."

**Key decisions:**
- Execute reads `machine.yaml`, authors **predicate-bound tests for mechanical ACs only** (ADR-001, ADR-002).
- `executable_predicate` is **tightened to a parseable Python expression** so "predicate-bound" is real, not prose relabeled (ADR-007).
- Mutation on the hot path is **T1-only**; T2/T3 stay in the loop (ADR-003).
- Write-back (`pending_test→false` + `test_ids`) is **relocated to wrapup, in the base repo, after finalize** — this is what makes `machine.yaml` a *living* document and simultaneously kills the cwd + cross-session-race criticals (ADR-005).
- When no parseable-predicate mechanical AC exists, **silent fallback to the existing scenario path** (ADR-004); default-on, no back-compat shim (ADR-008).

**Estimated impact:** 3 template rewrites (spec/execute/wrapup), 1 new CLI subcommand, 1 validate tightening, 1 spec_drift detector. Fleet-wide (execute.md.j2 renders to every downstream user).

## 📚 Prior Work

- **[[RESEARCH-spec-test-accumulation]]** — surfaced the two-disjoint-pipeline root cause + the 3-approach fork; SOTA: "mutation is table stakes", "stop counting tests, define oracles" ([laracopilot], [totalshiftleft]); the oracle problem (AI tests mirror implementation).
- **[[PLAN-total-spec-coverage]]** — authored the dual-file SPEC contract (ADR-006/007 there), L1/L2 clusters, the 4-part AI gate, mutation tiers. This PLAN connects that contract to everyday execute.
- **[[PLAN-test-fidelity-gap]]** — precedent for advisory-vs-blocking gate decisions.
- **`[wiki:pattern] removal-task-no-tdd-interpretation`** — when AC/scenario test authoring is tautological (deletion/refactor phases); informs the fallback path.
- **`[fail:test] snapshot-regen-inside-worktree` (count:7)** — Phase 4 MUST regen snapshots from the main repo root, never inside a worktree.
- **CLAUDE.md Second Brain ADR-005** — precedent that wrapup-only steps silently never fire in manual/quick-commit workflows; directly informs ADR-009.

## 🎙️ Interview Transcript

| # | Round | Topic | Question | Choice | → ADR |
|---|---|---|---|---|---|
| 1 | 1 | Approach | A unify / hybrid / C drift-only | **A: execute↔machine.yaml full unification** | ADR-001 |
| 2 | 2 | Integration scope | all AC types / mechanical+parametric / mechanical-first | **mechanical-first** | ADR-002 |
| 3 | 2 | Mutation budget | T1-only / none-on-hotpath / all-tiers | **T1 only on hot path** | ADR-003 |
| 4 | 2 | Fallback | silent scenario / HALT / mode-agnostic | **silent scenario fallback when no machine.yaml** | ADR-004 |
| 5 | 3 | Write-back | living write-back / read-only | **Yes — flip pending_test + record test_ids** | ADR-005 |
| 6 | 3 | AC↔scenario | union(no-dup) / AC-only / both | **mechanical AC=predicate, unmapped scenarios=scenario test** | ADR-006 |
| 7 | 4 | Predicate determinism (validator C2) | Phase 0 tighten / demote claim / restrict to parseable | **Phase 0: tighten spec contract** | ADR-007 |
| 8 | 4 | Write-back location (validator C1+C3) | post-finalize base / serialize-in-WT / line-stable-merge | **post-finalize, base repo** | ADR-005 (amended) |
| 9 | 4 | scenario↔AC link (validator W4) | test-reviewer adjudicates / scenario_ids schema | **test-reviewer adjudicates union (accept)** | ADR-006 (amended) |
| 10 | 4 | Rollback / back-compat (validator W7) | flag default-off / default-on / opt-in | **default-on, no flag, no back-compat shim** | ADR-008 |

Validator-driven resolutions (2nd pass NEEDS_REVISION, resolved as "revise plan"):
- **W1** (execute-without-wrapup half-state) → ADR-009 + spec_drift "resolved-but-pending" detector (Phase 3).
- **W2** (Phase 1 cwd contract) → reworded to `md_path.parent.parent` semantics; no `cross_validate` signature change (Phase 1).

## 📐 Architecture Decision Records

### ADR-001: execute reads machine.yaml as source of truth
**Status:** Accepted (2026-05-29, via /hm:plan interview)
**Context:** execute ignores `machine.yaml`; the AC→test graph never binds forward.
**Decision:** execute Phase A reads `SPEC-{slug}.machine.yaml` and authors tests bound to its ACs.
**Consequences:**
- ✅ spec + tests accumulate forward through normal feature work.
- ⚠️ execute.md.j2 (fleet-wide rendered command) changes.
**Rejected alternatives:** C (drift-gate-only) — surfaces divergence but doesn't fix root cause; B (Tessl spec-as-source) — conflicts with [[feedback_domain_content_ownership]] (users own domain code).
**Source:** Interview #1

### ADR-002: mechanical-first integration scope
**Status:** Accepted (2026-05-29)
**Context:** ACs have three types (mechanical/parametric/judgment); doing all at once maximizes complexity.
**Decision:** Only mechanical ACs bind to `executable_predicate` now. parametric (`golden_table`) and judgment (`rubric_id`) stay on the scenario path, deferred to a follow-up PLAN.
**Consequences:**
- ✅ Smallest shippable forward-binding increment.
- ⚠️ A single machine.yaml can hold forward-bound mechanical ACs AND still-pending parametric/judgment ACs (half-state) — made visible by Phase 3's per-type coverage report.
**Rejected alternatives:** all-AC-types (verification burden); mechanical+parametric (golden_table authoring still nontrivial without demand).
**Source:** Interview #2

### ADR-003: T1-only mutation on the hot path
**Status:** Accepted (2026-05-29)
**Context:** mutmut is slow; running it on every AC in everyday execute is prohibitive.
**Decision:** execute Phase D runs the mutation gate for **T1 ACs only** (union of their `paths_to_mutate`). T2/T3 mutation stays in `/hm:loop` or sampling.
**Consequences:**
- ✅ Assertion quality is measured on the hot path for the most critical ACs (SOTA: mutation = table stakes).
- ⚠️ T2/T3 assertion quality still only measured in the loop.
**Rejected alternatives:** all-tier (impractical latency); none-on-hotpath (oracle problem unmeasured everyday).
**Source:** Interview #3

### ADR-004: silent scenario fallback when no usable machine.yaml
**Status:** Accepted (2026-05-29)
**Context:** task-driven / trivial / `--no-tdd` runs and SPECs without parseable-predicate mechanical ACs have nothing to forward-bind.
**Decision:** When `machine.yaml` is absent OR has zero mechanical ACs with a parseable predicate, execute silently uses the existing scenario-prose path.
**Consequences:**
- ✅ task-driven mode and `--no-tdd` behave exactly as today.
- ⚠️ "silent" — no signal that the richer path was skipped (acceptable; the path is opt-in by having a usable machine.yaml).
**Rejected alternatives:** HALT in spec-driven (footgun on trivial tasks); mode-agnostic-always (no behavior difference here, folded in).
**Source:** Interview #4

### ADR-005: write-back relocated to wrapup, base repo, post-finalize
**Status:** Accepted (2026-05-29; amended Interview #8 after validator C1/C3)
**Context:** Writing back inside the worktree fails `cross_validate` rule-3 (collection cwd is `md_path.parent.parent` = base, but the new test exists only in the worktree until finalize) AND races the 5-layer cross-session worktree defenses (machine.yaml is a committed deliverable, not churn-gitignored).
**Decision:** execute does NOT write back. The wrapup stage, running in the base repo AFTER finalize has merged the test files, calls `spec_machine mark-tested` to flip `pending_test→false` + record `test_ids` for ACs whose tests now resolve, then re-runs `cross_validate`.
**Consequences:**
- ✅ Collection cwd is correct by construction (spec file lives at `<base>/specs/`, so `md_path.parent.parent` = base root) and the test is already merged.
- ✅ Single-threaded on base — no finalize-stash / merge-fence / scope-guard race.
- ⚠️ Write-back is wrapup-gated (see ADR-009).
**Rejected alternatives:** serialize-in-worktree (forces serial parallel execute); line-stable-merge (merge complexity for no benefit once relocated).
**Source:** Interview #5, #8

### ADR-006: union coverage adjudicated by test-reviewer
**Status:** Accepted (2026-05-29; amended Interview #9 after validator W4)
**Context:** No machine-readable link binds an In-Scope Scenario (SPEC.md prose) to an AC-NNN; "no double coverage" cannot be computed deterministically.
**Decision:** mechanical AC → predicate test; scenarios not mapped to a mechanical AC → existing scenario test. The **test-reviewer gate adjudicates the union** (duplication / coverage holes). No `scenario_ids[]` schema change.
**Consequences:**
- ✅ No schema churn; reuses the existing test-reviewer.
- ⚠️ Union resolution is LLM-judgment, not deterministic (accepted as interview-resolved risk).
**Rejected alternatives:** add `scenario_ids[]` back-ref + 7th cross_validate rule (schema change + extra phase + spec contract change).
**Source:** Interview #6, #9

### ADR-007: executable_predicate tightened to a parseable expression
**Status:** Accepted (2026-05-29; via validator C2)
**Context:** `spec_machine.validate` only checks `executable_predicate` is non-empty; a prose string ("retries are bounded") makes "predicate-bound test authoring" indistinguishable from the current scenario-prose path.
**Decision:** Phase 0 tightens `spec_machine.validate` so a mechanical AC's `executable_predicate` must `ast.parse` to a Python expression and its referenced top-level symbols are checked; `spec.md.j2` instructs the LLM to author runnable predicates.
**Consequences:**
- ✅ "predicate-bound" becomes a real, mechanically-checkable contract.
- ⚠️ Existing prose-predicate `machine.yaml` files (83 of harness-maker's own specs carry placeholder predicates) will fail the tightened validate. **Accepted** (ADR-008 waives back-compat); a migration is a follow-up PLAN, and no current CI gate runs validate over the real `specs/` tree (validator suggestion #3 confirmed), so this PLAN's Phase 4 is unaffected.
**Rejected alternatives:** demote the "deterministic" claim (leaves the graph cosmetic); restrict-to-parseable-only without tightening spec authoring (predicates stay prose by default).
**Source:** Interview #7

### ADR-008: default-on, no feature flag, no back-compat shim
**Status:** Accepted (2026-05-29)
**Context:** Phase 2 rewrites the fleet-wide execute command.
**Decision:** The machine.yaml-present branch ships default-on with no harness.yaml flag and no back-compat handling for pre-existing all-pending specs (user direction: "default on, 하위호환 고려 필요 없음").
**Consequences:**
- ✅ Every spec-driven user gets forward-binding immediately.
- ⚠️ Rollback is re-release only (5-file version dance); a Phase 2 render bug is a fleet-wide regression. Mitigated by the silent fallback (ADR-004) — a SPEC without usable machine.yaml is untouched.
**Rejected alternatives:** flag default-off-one-release; permanent opt-in flag (both leave default users without the benefit).
**Source:** Interview #10

### ADR-009: mechanical write-back is wrapup-gated by design, surfaced by spec_drift
**Status:** Accepted (2026-05-29; via validator W1)
**Context:** Relocating write-back to wrapup (ADR-005) means a user who runs execute+review but commits manually (skips `/hm:wrapup`) leaves `pending_test=true` forever, and `evaluate_coverage` counts pending as covered → misleading 100%. Same class as the documented Second Brain promotion limitation (CLAUDE.md ADR-005).
**Decision:** Accept wrapup-gating as the design (consistent with Second Brain precedent), but make the gap **visible outside wrapup**: `observability/spec_drift.scan()` gains a "resolved-but-pending" detector — a mechanical AC whose `test_ids` resolve via `pytest --collect-only` yet is still `pending_test=true`. Surfaced in `/hm:health` and the spec gate.
**Consequences:**
- ✅ No silent permanent miss (aligns with the project's anti-silent-miss culture).
- ⚠️ The flip still only happens in wrapup; the detector flags, it does not auto-fix.
**Rejected alternatives:** auto-flip in a hook (out-of-band write to a committed deliverable — same race ADR-005 avoided); leave undocumented (silent miss).
**Source:** validator W1 resolution

## 🏗️ Technical Design

**Current State:** `/hm:spec` writes `SPEC-{slug}.md` + `SPEC-{slug}.machine.yaml` (cross-validated). `/hm:execute` authors `test_s{n}_*` from SPEC.md scenarios, gated by `test-reviewer`, ignoring `machine.yaml`. `spec_machine.cross_validate` scopes pytest collection to `md_path.parent.parent`; `validate` only non-empty-checks `executable_predicate`; `evaluate_coverage` counts `pending_test` as covered. `reverse_map.py` reconstructs AC↔test links retroactively.

**Affected Components:**
- `src/harness_maker/spec_machine.py` — tighten `validate`; new `mark-tested` operation.
- `src/harness_maker/cli.py` — wire `mark-tested` subcommand.
- `src/harness_maker/templates/stages/spec.md.j2` — instruct runnable predicates.
- `src/harness_maker/templates/stages/execute.md.j2` — machine.yaml-present authoring branch.
- `src/harness_maker/templates/stages/wrapup.md.j2` — post-finalize write-back + per-type coverage report.
- `src/harness_maker/observability/spec_drift.py` — "resolved-but-pending" detector.

**Dependencies:** none new (mutmut, ast, pyyaml already present).

**Data Flow (target):**
```
/hm:spec ──▶ machine.yaml (mechanical AC: parseable predicate, test_ids, pending_test=true)
/hm:execute (worktree) ──reads──▶ machine.yaml
   ├─ mechanical AC w/ parseable predicate → author predicate test at test_ids (RED→GREEN)
   ├─ unmapped scenario → scenario test (test-reviewer adjudicates union)
   ├─ no usable machine.yaml → scenario-prose fallback (silent)
   └─ Phase D → T1 mutation gate
finalize ──merges tests──▶ base repo
/hm:wrapup (base) ──▶ spec_machine mark-tested (flip pending_test→false + test_ids) + cross_validate + per-type coverage report
spec_drift.scan() ──▶ flags resolved-but-pending ACs (outside wrapup)
```

**Design Decisions:** all per ADR-001…009 above.

**API Changes:** new CLI `python -m harness_maker.spec_machine mark-tested --md <path> --yaml <path> --ac <AC-ID> [--ac ...]` (or a thin `cli.py` wrapper). Flips `pending_test→false` + sets `test_ids` for the named ACs whose tests resolve, atomic_write, re-runs cross_validate scoped to `md_path.parent.parent`.

## 📝 Implementation Plan

### Phase 0 — Tighten executable_predicate contract
- **depends_on:** []
- **parallel_group:** serial-0
- **merge_hazards:** `spec_machine.py`, `spec.md.j2`
- **Scope (in):** `validate` rejects mechanical ACs whose `executable_predicate` does not `ast.parse` to an expression or references undefined top-level symbols; `spec.md.j2` Step 3.5 guidance updated to demand runnable predicates.
- **Scope (out):** parametric/judgment predicate rules; migrating the 83 existing placeholder specs.
- **Exit criterion:** `uv run pytest tests/unit/test_spec_machine.py -k predicate` — validate REJECTS a prose predicate AND ACCEPTS a parseable expression (both asserted).
- **Risk:** medium
- **Rollback point:** revert to `main` (no prior phase).

### Phase 1 — spec_machine `mark-tested` CLI
- **depends_on:** [0]
- **parallel_group:** serial-1
- **merge_hazards:** `spec_machine.py`, `cli.py`
- **Scope (in):** `mark-tested` operation — flip `pending_test→false` + set `test_ids[]` for given AC ids via `atomic_write`, then re-run `cross_validate` (collection scoped to `md_path.parent.parent`, per the existing signature — NOT caller cwd).
- **Scope (out):** changing `cross_validate`'s signature to accept a cwd param.
- **Exit criterion:** `mark-tested` flips the field; `cross_validate` PASSES when `test_ids` resolve under the spec's base-repo tree AND FAILS when invoked with an `md_path` whose tests don't resolve (negative case asserted, so the gate provably fires — guards against the swallow-and-return-`[]` degrade path).
- **Risk:** medium
- **Rollback point:** revert to Phase 0 state.

### Phase 2 — execute.md.j2 machine.yaml-present authoring branch
- **depends_on:** [0]
- **parallel_group:** serial-2
- **merge_hazards:** `execute.md.j2` (single template; also touched by no other phase — but serial vs Phase 0's spec.md.j2 conceptually)
- **Scope (in):** Phase A branch — when `machine.yaml` present with ≥1 parseable-predicate mechanical AC: author a predicate-bound test at each such AC's `test_ids` (RED→GREEN, assert the predicate); union with scenario tests for scenarios not mapped to a mechanical AC; test-reviewer adjudicates the union. Phase D: T1 mutation gate over T1 ACs' `paths_to_mutate`. Silent scenario fallback otherwise. NO write-back here.
- **Scope (out):** write-back (Phase 3); parametric/judgment authoring.
- **Exit criterion:** rendered `execute.md` contains all three branches (predicate / scenario-union / fallback) + T1 mutation step; `uv run python tests/snapshot/regenerate.py` (from main repo) green; render deterministic across two runs.
- **Risk:** medium-high
- **Rollback point:** revert to Phase 0 state (execute.md.j2 unchanged → current scenario path).

### Phase 3 — wrapup write-back + per-type coverage + spec_drift detector
- **depends_on:** [1, 2]
- **parallel_group:** serial-3
- **merge_hazards:** `wrapup.md.j2`, `observability/spec_drift.py`
- **Scope (in):** wrapup.md.j2 — post-finalize step calling `mark-tested` in base repo for ACs whose tests now resolve; per-type coverage report block (mechanical forward-bound N / parametric+judgment still-pending M). `spec_drift.scan()` — "resolved-but-pending" detector (test_ids collect-resolve but pending_test=true).
- **Scope (out):** auto-flipping outside wrapup.
- **Exit criterion:** rendered `wrapup.md` has the write-back step + per-type coverage block; `spec_drift.scan()` flags a resolved-but-pending fixture; snapshot green.
- **Risk:** medium
- **Rollback point:** revert to Phase 2 state (forward authoring works; machine.yaml just stays pending — degraded but not broken).

### Phase 4 — tests, docs, version
- **depends_on:** [0, 1, 2, 3]
- **parallel_group:** serial-4
- **merge_hazards:** snapshot fixtures, the 5 version files (CLAUDE.md 버전업 정책)
- **Scope (in):** e2e both paths (spec-driven w/ parseable-predicate machine.yaml → AC tests + wrapup flips pending_test; task-driven no-machine → scenario tests); HOW-IT-WORKS / TECH_SPEC docs; CHANGELOG; 5-file version bump.
- **Scope (out):** migrating the 83 placeholder specs (follow-up PLAN).
- **Exit criterion:** full `uv run pytest` + `mypy --strict` + `ruff check`/`format` green; snapshots regenerated **from main repo root** (count:7 trap), not a worktree.
- **Risk:** low
- **Rollback point:** revert to Phase 3 state.

## 🧪 Testing Strategy

- **Unit:** `spec_machine.validate` predicate-tightening (Phase 0); `mark-tested` flip + cross_validate positive/negative cwd cases (Phase 1); `spec_drift` resolved-but-pending detector (Phase 3).
- **Render/snapshot:** execute.md three branches + wrapup write-back/coverage block; determinism; regen from main repo only.
- **e2e:** (a) spec-driven SPEC with a parseable-predicate mechanical AC → execute authors AC test, RED→GREEN, finalize, wrapup flips pending_test→false; (b) task-driven, no machine.yaml → scenario path unchanged.
- **Full gate:** pytest + mypy --strict + ruff before wrapup (verify-before-completion).

## ⚠️ Risks & Mitigation

| Risk | Severity | Mitigation |
|---|---|---|
| Phase 2 render bug breaks fleet-wide execute | high | Silent fallback (ADR-004) keeps non-machine.yaml SPECs on the proven path; snapshot determinism gate; rollback = re-release (ADR-008 accepted) |
| Tightened validate breaks existing 83 placeholder specs | medium | No CI gate runs validate over real `specs/` (confirmed); back-compat waived (ADR-008); migration is a follow-up |
| Write-back never runs (wrapup skipped) → stale pending_test | medium | spec_drift "resolved-but-pending" detector surfaces it outside wrapup (ADR-009) |
| Union coverage LLM-misjudges (dup tests / coverage hole) | low-medium | test-reviewer adjudicates with 2-attempt retry budget; accepted as interview-resolved risk (ADR-006) |
| Snapshot regen inside worktree corrupts hashes | medium | Phase 4 exit criterion mandates regen from main repo root (count:7 lesson) |

## ✅ Success Criteria

- [x] A spec-driven SPEC with a parseable-predicate mechanical AC drives execute to author a test at its `test_ids`, RED→GREEN.
- [x] After wrapup (base repo, post-finalize), that AC's `pending_test` is `false` and `test_ids` recorded; `cross_validate` passes.
- [x] `executable_predicate` for mechanical ACs is `ast.parse`-valid (validate rejects prose).
- [x] T1 ACs get a mutation gate in execute Phase D.
- [x] task-driven / no-machine.yaml runs behave exactly as before (scenario path).
- [x] `spec_drift.scan()` flags resolved-but-pending mechanical ACs.
- [x] Per-type coverage report distinguishes mechanical-forward-bound from parametric/judgment-pending.
- [x] full pytest + mypy --strict + ruff green; snapshots regenerated from main repo.

## 🔍 Plan Validation

- **Pass 1:** MAJOR_REVISION — 3 critical (C1 cross_validate cwd, C2 hollow predicate, C3 write-back races worktree defenses) + 4 warnings.
- **Resolution:** Interview Round 4 — C2→ADR-007 (Phase 0 tighten predicate); C1+C3→ADR-005 amended (write-back relocated to wrapup/base post-finalize); W4→ADR-006 amended (test-reviewer adjudicates); W7→ADR-008 (default-on, back-compat waived).
- **Pass 2 (re-run):** NEEDS_REVISION — 0 critical (all 3 confirmed addressed), 2 warnings + 1 suggestion. Resolved as "revise plan": W1→ADR-009 + spec_drift detector (Phase 3); W2→Phase 1 cwd wording corrected to `md_path.parent.parent` semantics; suggestion #3 (83 placeholder specs)→migration follow-up note, no CI impact confirmed.
- **Outcome:** MAJOR_REVISION_RESOLVED.
