---
type: plan
task_slug: total-spec-coverage
status: complete
created: 2026-05-20
completed: 2026-05-20
tags: [harness-maker, plan, spec-framework, mutation-testing, ai-verifiability, coverage]
interview_rounds: 6
adrs: 13
validator_outcome: MAJOR_REVISION_RESOLVED_R2
summary: "Upgrade /hm:spec framework + write ~146 dual-file SPECs covering every harness-maker feature, AI-verifiable."
---

## 🎯 Executive Summary

**TL;DR:** Upgrade the `/hm:spec` framework (dual-file SPEC.md + SPEC.machine.yaml, AC type tags, executable predicates, golden tables, mutation thresholds, verification tiers), then write **~146 dual-file SPECs** (52 Python modules + 94 Jinja templates, computed via inventory enumeration) covering every harness-maker feature so that a future AI can deterministically judge "this feature is implemented correctly" via:
1. `pytest -k spec-{slug}` exits 0 (test-naming-bridge supports both legacy `test_*` and new `spec_*` patterns)
2. AC↔test mapping coverage 100% (every AC.id ↔ test_ids[] verified by `spec_machine`)
3. `spec_quality` LLM-judge score ≥ 0.85
4. **Mutation score** (mutmut) meets per-SPEC `mutation_threshold` = max(measured_baseline + 5pp, tier_floor) where tier_floor ∈ {T1: 85%, T2: 70%, T3: informational only}, Python only

**Why this is hard:** Current `/hm:spec` produces narrative SPECs (8 sections, G-W-T scenarios, Constraints/Verification tables). Human-friendly but does **NOT** encode AC↔test mapping, AC type tags, executable predicates, mutation thresholds, or verification tiers. An AI cannot verify "complete" without those. So the framework itself must change before bulk authoring. Additionally, current `autoloop_driver.run()` is feature-mode only with a caller-injected `ExecutorCallable: Callable[[Feature, int], bool]` — a Python callable cannot also dispatch the `/hm:spec` slash command (validated by `plan-validator` R2). So P5 bulk authoring uses the **prompt-driven `/hm:loop p5-batch-N` pattern** (mirrors improve-mode, NOT `run()`), with `BatchSpecState` as a thin CRUD helper consumed by the loop's prompt-side procedure.

**Estimated impact:**
- New code: ~7 modules (`spec_machine.py`, `spec_inventory/{catalog_schema,catalog,tier_assign,reverse_map,batch_orchestrator}.py`, `spec_mutation.py`, `observability/spec_drift.py`) + 1 template upgrade + 2 CI workflows
- New artifacts: `specs/SPEC-{slug}.{md,machine.yaml}` × ~146 + `specs/INDEX.md` coverage matrix
- New dependency: `mutmut>=2.4`
- CI cost: nightly mutation scoped per-SPEC; spec_quality cached 7d
- Version: bump to **0.18.0** (feature) on completion

**Key decisions** (each linked to ADR below):
- Scope = **all ~146 surface features** (computed: 52 Python `*.py` excluding `_*` + 94 `*.j2` excluding `_partials/` and `_standards/`) → [[ADR-001]]
- Granularity = **two-tier** (L1 capability cluster + L2 feature, ~15 L1 + ~131 L2) → [[ADR-002]]
- AC↔TC = **hybrid** (mechanical | parametric | judgment) → [[ADR-003]]
- AI gate = **pytest+coverage 100% + `spec_quality` ≥ 0.85 + mutation gate** → [[ADR-004]]
- Mutation = **mutmut, threshold = max(measured_baseline + 5pp, tier_floor)**, Python only, tier_floor T1=85/T2=70/T3=informational → [[ADR-005]]
- SPEC schema = **extended frontmatter + AC type tag + test_ids[] + executable_predicate + golden_table + mutation_threshold + verification_tier** → [[ADR-006]]
- Layout = **dual-file** (SPEC.md human + SPEC.machine.yaml machine) with concrete cross-validation contract → [[ADR-007]]
- Tier assignment = **hybrid heuristic + LLM disagreement gate**, weight-recalibration policy on >50% override rate → [[ADR-008]]
- Non-Python verification = **3-layer** (snapshot drift + schema validity + LLM-judge AC quality) → [[ADR-009]]
- Test inventory = **Reverse-map all first (P0)** → 154 tests → AC catalog JSON → reused in P3+ → [[ADR-010]]
- Conflict policy = **code = truth, drift logged as Open Question with aggregate cap** → [[ADR-011]]
- **NEW** Catalog schema = pydantic model in Phase 1 (cross-phase contract) → [[ADR-012]]
- **NEW** Workflow integration = **SPEC optional** in current 5-stage; `spec_drift` Layer warns only when `dev_mode: spec-driven` → [[ADR-013]]

---

## 📚 Prior Work

- `work-docs/PLAN-test-fidelity-gap.md` — boundary tests Layer 1 (ADR-003/004); spec_drift inherits its observability pattern.
- `work-docs/PLAN-deep-interview-question-criteria.md` (0.16.0) — 5-term inequality gate; `spec_quality` rubric extension reuses the LLM-judge pattern.
- `docs/adr/0002-three-layer-ai-readiness-rubric.md` — the 3-layer rubric pattern (deterministic / LLM-rubric / cache-failure-modes) is the direct inspiration for the non-Python verification layer (ADR-009).
- `docs/adr/0011-personalization-rubric-locked-v0.md` — version-locked rubric pattern; mutation thresholds in machine.yaml follow the same convention.
- `src/harness_maker/spec_quality.py` (current, 209 lines) — 5 rubric dims (completeness, testability, unambiguity, consistency, scope_boundary). Will gain 3 new dims and a backward-compatible dual-arg signature (preserves 5 existing callsites).
- `src/harness_maker/templates/stages/spec.md.j2` (current) — produces 8-section SPEC.md. Will gain a sibling-write of `.machine.yaml` and a 9th `🔗 Machine Spec` section.
- `src/harness_maker/autoloop_driver.py` (current, ~520 lines) — `run()` is feature-mode only with `failed_streak_cap=5`. P5 design now respects this (human-in-the-loop batches inside `/hm:loop`).
- Existing test corpus: **154 test files** across `unit/integration/e2e/snapshot/structural/ablation`. P0 reverse-maps these.

---

## 🎙️ Interview Transcript

| # | Round | Topic | Category | Question (≤1 line) | Choice | Note | → ADR |
|---|-------|-------|----------|--------------------|--------|------|-------|
| 1 | R1 | Scope cut | Scope | "Every feature" universe? | All ~146 (computed, not fixed) | Phase 2 inventory authoritative | ADR-001 |
| 2 | R1 | Granularity | Architecture | What is "1 SPEC"? | Two-tier: L1 cluster + L2 feature | `/hm:spec`-compatible | ADR-002 |
| 3 | R1 | AC↔TC form | Contract | How do AC map to tests? | Hybrid: mechanical/parametric/judgment | + mutation score required (user follow-up) | ADR-003 |
| 4 | R1 | AI verifier gate | Risk gate | What proves "complete"? | pytest+coverage + spec_quality ≥ 0.85 | + mutation later (Q5) | ADR-004 |
| 5 | R2 | Mutation tool | Dependency | Mutation tool + threshold | mutmut + Tier-adaptive (T1≥85/T2≥70/T3 info), Python only | adjusted in R5 (baseline-relative) | ADR-005 |
| 6 | R2 | Schema extensions | Contract | Which fields to add? | All 4: ac_type, test_ids[], predicate/golden, mutation+tier | maximum machine-readability | ADR-006 |
| 7 | R2 | File layout | Format | Single vs dual vs triple file? | Dual file: SPEC.md + SPEC.machine.yaml | drift gate reads .yaml only | ADR-007 |
| 8 | R2 | Phasing structure | Phasing | Big-bang vs pilot? | Pilot-first: framework + 3 reference → tune → bulk | reduces blast radius | (implementation; no ADR) |
| 9 | R3 | Tier assignment | Decision rule | Auto vs manual T1/T2/T3? | Hybrid: heuristic + LLM-disagreement gate | minimal user load | ADR-008 |
| 10 | R3 | L1 cluster count | Architecture | How many L1 clusters? | ~15, LLM-proposed → user-locked | exact list deferred to P2 | (lives in P2 catalog; no ADR) |
| 11 | R3 | Non-Python verify | Verification | Templates/agents/skills — mutation? | Snapshot drift + schema validity + LLM-judge AC | mirrors ai_readiness 3-layer pattern | ADR-009 |
| 12 | R3 | Pilot picks | Implementation | Which 3 reference SPECs? | render.py + code-reviewer + cache.py | diverse Tier + Python/non-Python | (implementation; no ADR) |
| 13 | R4 | Test inventory | Phasing | Reverse-map vs forward-only? | Reverse-map all first (P0) | 154 tests → AC catalog | ADR-010 |
| 14 | R4 | Bulk phasing | Phasing | P3+ ordering? | Auto-driven (revised in R5 to human-in-the-loop) | autoloop_driver.run() infeasible | ADR-013 |
| 15 | R4 | Conflict policy | Decision rule | code/docs/PLAN disagree — who wins? | Hybrid: code = truth + drift logged in SPEC Open Questions → plan resolves | aggregate cap added in R5 | ADR-011 |
| 16 | R5 | P5 redesign | Feasibility | autoloop_driver.run() infeasible — how? | **Human-in-the-loop batch** (`/hm:loop p5-batch-N`) | resolves validator C1 | ADR-013 |
| 17 | R5 | T1 baseline | Feasibility | T1≥85% unachievable on legacy? | **max(baseline + 5pp, 85%)**, P0.5 measures baseline | resolves validator C3 | ADR-005 (updated) |
| 18 | R5 | Workflow integration | Compatibility | SPEC required in new-feature flow? | **SPEC optional**, spec_drift warns only in dev_mode=spec-driven | resolves validator W9 | ADR-013 |
| 19 | R6 | P5 redesign (post-validator-R2) | Feasibility | BatchSpecExecutor ExecutorCallable+slash mutual exclusion | **Prompt-driven `/hm:loop p5-batch-N`** (improve-mode pattern); BatchSpecState is CRUD helper | resolves validator C1-relocated | ADR-013 (updated) |

---

## 📐 Architecture Decision Records

### ADR-001: Full-Surface SPEC Coverage (Computed Universe, ~146 features)
**Status:** Accepted (2026-05-20, /hm:plan interview R1, validator-revised R5)
**Context:** "Every feature" needs precise universe definition; raw counts (70/50) were estimates not aligned with codebase. Validator flagged actual counts 52 .py + 94 .j2 = 146.
**Decision:** Universe = **computed**:
- Python: all `src/harness_maker/**/*.py` excluding `_*.py` (leading-underscore = private) and `__init__.py` empties → ~52 modules
- Templates: all `src/harness_maker/templates/**/*.j2` excluding `_partials/**` and `_standards/**` → ~94 templates
- Phase 2 catalog enumeration is **authoritative**; the "~146" figure refreshes after that step.
**Consequences:**
- ✅ Drift-safe: catalog auto-updates as code evolves
- ✅ No hidden surfaces (P2 pre-flight `enumerate --dry-run` validates count)
- ⚠️ Number may shift slightly during P2; PLAN exit criteria reference `--aggregate` results, not fixed 120
**Rejected alternatives:**
- Public-surface only (~41) — internal modules back user-facing surfaces; coverage gaps create AI-blind spots.
- Hardcoded 120 — broke against actual codebase count; cause of validator W1.
**Source:** Interview #1 + Validator W1

### ADR-002: Two-Tier SPEC Granularity (L1 Capability Cluster + L2 Feature)
**Status:** Accepted (2026-05-20)
**Context:** SPEC granularity affects cross-cutting concern coverage. 1:1 misses invariants; cluster-only misses concrete AC.
**Decision:** Two-tier hierarchy.
- **L1 (Capability Cluster)** — ~15 SPECs defining invariants per cluster (e.g., "all reviewer agents share permissions allow/deny invariants"). LLM proposes cluster set in P2 → user locks.
- **L2 (Feature)** — ~131 SPECs, each with `parent_spec: SPEC-{l1-slug}` in machine.yaml. Each L2 inherits L1 invariants by reference + adds feature-specific AC.
- Format remains the existing 8-section `/hm:spec` output for both tiers (`spec.md.j2` template).
**Consequences:**
- ✅ Cross-cutting invariants live in one place (L1), no duplication across ~30 reviewer SPECs
- ✅ AI verifier runs "L1-AC propagation check" — every L2 must pass parent's invariant AC
- ⚠️ Two-level navigation; mitigated by `specs/INDEX.md` coverage matrix
- ⚠️ L1/L2 mutation overlap when L1 `paths_to_mutate` ⊇ L2 (Risk R14); resolution: L1 mutation gate uses union of L2 paths_to_mutate, score = union pass rate
**Rejected alternatives:**
- Flat 1:1 — cross-cutting concerns repeat ~10× across reviewers/templates
- Capability-only — concrete AC at feature level lost
- Behavior-driven (user journey) — strongest for e2e, weakest for internal module contracts
**Source:** Interview #2 + R3 confirmation Q10

### ADR-003: Hybrid AC Type Tagging (mechanical | parametric | judgment) + Mandatory Mutation Score
**Status:** Accepted (2026-05-20)
**Context:** AC↔TC form drives AI verifiability. Pure Gherkin is human-readable but not machine-runnable; pure predicate loses intent.
**Decision:** Each AC declares `ac_type`:
- **mechanical** — exactly one runnable Python expression (`executable_predicate`) deciding pass/fail.
- **parametric** — golden table `(input, expected, edge?)` rows → pytest.parametrize.
- **judgment** — LLM rubric pass criterion. Includes rubric_id link.

Mutation score is a first-class verification component for any AC backed by Python code paths. See ADR-005.

**Consequences:**
- ✅ AC unambiguously testable (predicate) OR table-driven (parametric) OR LLM-graded (judgment)
- ✅ Mutation score forces TC quality
- ⚠️ Schema complexity grows; mitigated by `spec_machine.py` validator
**Rejected alternatives:**
- Predicate-only — intent lost
- Gherkin + nodeid only — no executable evidence
- Behavioral table only — failure-mode AC poorly fit
**Source:** Interview #3 + user mutation requirement

### ADR-004: AI Verification Gate = pytest+coverage + spec_quality + mutation
**Status:** Accepted (2026-05-20)
**Context:** "AI judges this feature is correctly implemented" requires a concrete measurable verdict.
**Decision:** Per-SPEC verdict = all-of:
1. `pytest -k "spec-{slug} OR {slug_legacy}"` exits 0 (test-naming-bridge — supports both legacy `test_render_*` and new `spec_render_*`; bridge logic in `spec_machine.resolve_pytest_selector`)
2. AC↔test mapping coverage = 100% (every AC.id has ≥1 valid `test_ids[]` resolving via `pytest --collect-only`)
3. `spec_quality.evaluate_spec(spec_text, machine_yaml=...).overall ≥ 85`
4. Mutation score meets `mutation_threshold` (ADR-005), Python-backed AC only

SPEC `status:` values: `drafted` (incomplete) / `verified` (all 4 met) / `drift` (any 4 fails post-merge).

**Consequences:**
- ✅ Single automatable verdict
- ✅ Test-naming bridge avoids forced rename of 154 existing tests
- ⚠️ LLM judge variance — 3-run median if score ∈ [80, 90]; 7d cache
- ⚠️ Cost — ~146 LLM calls per re-verify; per CLAUDE.md, subscription allows
**Rejected alternatives:**
- pytest exit code alone — passes trivial tests, no mutation
- Coverage % only — misses semantic AC
- Behavior replay only — overkill for helper modules
**Source:** Interview #4 + Validator W6 (test-naming bridge)

### ADR-005: mutmut + Baseline-Relative Threshold (T1 = max(baseline+5pp, 85%), T2 = max(baseline+5pp, 70%), T3 informational)
**Status:** Accepted (2026-05-20, validator-revised R5)
**Context:** Mutation score = strongest TC quality indicator; user explicitly required. Pure-absolute 85% gate was aspirational and infeasible on legacy code (validator C3).
**Decision:**
- **Tool:** `mutmut` (mature, AST mutations, fast). Add `mutmut>=2.4` to dev dependencies.
- **Threshold formula:** Per-SPEC `mutation_threshold` field in `SPEC.machine.yaml`:
  - **T1** — `threshold = max(measured_baseline + 5pp, 85%)`. P0.5 measures baseline; if baseline=65%, threshold=85% (gap=20pp, closed by P3 backfill); if baseline=82%, threshold=87%; if baseline=90%, threshold=95%.
  - **T2** — `threshold = max(measured_baseline + 5pp, 70%)`.
  - **T3** — informational (recorded but non-gating).
  - Threshold is locked in the SPEC.machine.yaml at first verification; subsequent code changes must maintain or improve. The +5pp delta forces continuous improvement on tests.
- **Scope:** Python only. Templates/agents/skills → ADR-009 3-layer non-Python verification.
- **CI:** Nightly `mutmut run` per SPEC's `paths_to_mutate`. PR gate uses cached report when ≤ 7 days old. Regression workflow opens GitHub Issue.

**Consequences:**
- ✅ TC quality forced — trivial tests fail
- ✅ Legacy code fair — threshold respects current state
- ✅ Continuous improvement — +5pp delta forces test growth
- ⚠️ Per-SPEC overrides possible (with ADR or rationale in machine.yaml `mutation_threshold_rationale` field)
- ⚠️ mutmut runtime grows; mitigated by per-SPEC `paths_to_mutate` scoping
**Rejected alternatives:**
- Flat threshold ≥ 80% — over-aggressive on legacy
- cosmic-ray — 10× slower; nightly-only acceptable but PR gate impractical
- Hybrid mutmut+cosmic-ray — premature
- Relative-only (no absolute floor) — quality drift over years; the +5pp ratchet + tier_floor prevents
**Source:** Interview #5 + #17 (R5 baseline-relative)

### ADR-006: Extended SPEC Schema (ac_type + test_ids[] + executable_predicate + golden_table + mutation_threshold + verification_tier)
**Status:** Accepted (2026-05-20)
**Context:** Current SPEC.md has no fields for AC types, test mapping, predicates, or mutation. AI verifier needs machine-readable structure.
**Decision:** Add to `SPEC.machine.yaml` (per ADR-007). Required fields:

```yaml
schema_version: 1
spec_slug: render
parent_spec: SPEC-rendering        # ← L1 link (ADR-002)
verification_tier: 1               # ← T1/T2/T3 (ADR-008)
mutation_threshold: 85             # ← computed via ADR-005 formula
mutation_threshold_rationale: ""   # ← override required when not formula-default
last_mutation_run: 2026-05-20      # ← ISO date, updated by mutmut CI
paths_to_mutate: [src/harness_maker/render.py]
spec_quality_score: 87
spec_quality_score_at: 2026-05-20
ac:
  - id: AC-001
    title: render emits frontmatter with content_hash
    type: mechanical
    test_ids: [tests/unit/test_render.py::test_render_emits_content_hash]
    executable_predicate: "'content_hash:' in render_claude_md(default_answers())"
  - id: AC-002
    title: locale→language fallback table
    type: parametric
    test_ids: [tests/unit/test_render.py::test_locale_fallback]
    golden_table:
      - input: {locale: en}; expected: english
      - input: {locale: ko}; expected: korean
      - input: {locale: jp}; expected: english   # unknown → en fallback
  - id: AC-003
    title: rendered CLAUDE.md respects line budget per preset
    type: judgment
    test_ids: [tests/structural/test_context_lint.py::test_render_under_budget]
    rubric_id: claude_md_v1
```

**Consequences:**
- ✅ Machine-readable graph of feature ↔ AC ↔ test ↔ mutation ↔ rubric
- ✅ Drift gate mechanically verifies each field
- ⚠️ Schema versioning needed → ADR-012 (separated, also covers catalog schema)
**Rejected alternatives:**
- Frontmatter-only — 300-line yaml in markdown header breaks git diff
- Triple file — overcomplicated
- Inline yaml fenced block — extraction fragile
**Source:** Interview #6

### ADR-007: Dual-File SPEC Layout — SPEC.md (human) + SPEC.machine.yaml (machine), with Concrete Cross-Validation Contract
**Status:** Accepted (2026-05-20, validator-revised R5)
**Context:** AI verifier needs reliable yaml; humans need readable markdown. Validator W2 flagged that cross-validation rules were under-specified.
**Decision:** Each SPEC = two co-located files:
- `specs/SPEC-{slug}.md` — 8-section narrative (existing `/hm:spec` output unchanged) + 9th `🔗 Machine Spec` section linking to `.machine.yaml`
- `specs/SPEC-{slug}.machine.yaml` — schema per ADR-006

**Cross-validation contract** (`spec_machine.cross_validate(md_path, yaml_path)` must enforce ALL of):
1. Every `ac.id` in `.machine.yaml` has a corresponding `### AC-XXX` heading or labeled scenario in `.md` (slug match).
2. `ac.title` in `.machine.yaml` matches first line under that heading verbatim (or Levenshtein ratio ≥ 0.85 — fuzzy tolerance for minor edits).
3. Every `test_ids[]` entry resolves via `pytest --collect-only -q --quiet` (file:nodeid exists).
4. Every `rubric_id` in `.machine.yaml` resolves to a file in `.claude/rubrics/` or template equivalent.
5. `verification_tier` value in `.machine.yaml` matches the SPEC's frontmatter `tier:` field (added to `.md` frontmatter as a synchronized mirror).
6. `parent_spec` resolves to an existing L1 `.md` file in `specs/`.

A `desync_detection_test` (`tests/unit/test_spec_machine_cross_validate.py`) covers each rule with a desync-positive and desync-negative case.

**Consequences:**
- ✅ Concrete contract eliminates silent desync
- ✅ Test naming bridge (ADR-004) allows incremental rename
- ⚠️ Fuzzy match (rule 2) may have edge cases; mitigated by ratio threshold tuning during Phase 4
**Rejected alternatives:**
- Single file with embedded yaml — extraction fragile
- Frontmatter-only — git diff unreadable
- Triple file — overcomplicated
**Source:** Interview #7 + Validator W2

### ADR-008: Tier Assignment via Hybrid Heuristic + LLM Disagreement Gate, with Weight Recalibration Policy
**Status:** Accepted (2026-05-20, validator-revised R5)
**Context:** ~146 features need T1/T2/T3 labels. Manual list scales poorly across schema evolution (not just cost). Pure-LLM = poor reproducibility.
**Decision:** Two-pass:
1. **Heuristic auto-tier** — `harness_maker.spec_inventory.tier_assign` computes per-feature:
   `criticality = w1*user_facing + w2*security_relevant + w3*reproducibility_impact + w4*ai_workflow_dependency`
   (default weights `w1=0.4, w2=0.3, w3=0.2, w4=0.1`). Thresholds: T1 ≥ 0.75, T2 ≥ 0.4, else T3.
2. **LLM disagreement detector** — same module asks LLM judge to grade each feature; flags 5-15 where heuristic and LLM diverge by ≥1 tier.
3. **User review** — disagreements → `work-docs/spec-catalog-disagreements-2026-05.md` for user pick.
4. **Weight recalibration policy** — if user override rate on disagreement list > 50%, weights are re-tuned via `tier_assign --recalibrate` (least-squares fit to user choices) and step 1 re-runs. Recorded in `work-docs/spec-catalog-2026-05.yaml` header `weight_recalibrations:` log.

**Consequences:**
- ✅ Minimal user load (5-15 decisions)
- ✅ Self-correcting via recalibration
- ⚠️ First-pass weights may misweight novel feature types; recalibration policy addresses
**Rejected alternatives:**
- Manual list — does not scale to schema evolution (0.19.0 adds features → full re-decision)
- Pure heuristic — single-failure-mode if weights are wrong
- Pure LLM — non-reproducible
**Source:** Interview #9 + Validator W4 (rejected-alt reframe)

### ADR-009: Non-Python 3-Layer Verification (Snapshot Drift + Schema Validity + LLM-Judge AC Quality)
**Status:** Accepted (2026-05-20)
**Context:** ~94 features are templates + ~25 are agent/skill bodies. Mutation inapplicable.
**Decision:** Non-Python SPEC verification layers:
- **Layer 1 — Snapshot drift** — rendered output bytewise matches committed snapshot.
- **Layer 2 — Schema validity** — parses under consumer format (`.mdc` frontmatter, `.toml`, hooks.json PascalCase).
- **Layer 3 — LLM-judge AC quality** — `spec_quality` new dim `non_python_intent_alignment`.

Tier mapping:
- **T1 non-Python** — all 3 layers
- **T2 non-Python** — L1 + L2 + sampled L3 (1 LLM judge per 5 SPECs)
- **T3 non-Python** — L1 only

**Consequences:** ✅ Drift-proof alternative to mutation. ✅ Mirrors `ai_readiness` 3-layer pattern.
**Rejected alternatives:** Snapshot only / E2E replay / Tier-uniform
**Source:** Interview #11

### ADR-010: Reverse-Map First Test Inventory (P0 Phase), Split Exit (Auto + Manual)
**Status:** Accepted (2026-05-20, validator-revised R5)
**Context:** 154 tests contain implicit AC. Forward-only orphans unknown tests; full per-feature is slow. Validator C2 flagged that the self-confidence exit was unsound.
**Decision:** Dedicated P0 phase + dedicated P0 manual gate:
- `harness_maker.spec_inventory.reverse_map` walks `tests/` (excluding fixtures/), LLM-infers `(test_id, file, inferred_ac_summary, inferred_feature, ac_type, confidence)`.
- Outputs `work-docs/test-inventory-2026-05.json`.
- **Exit Gate A (auto):** `avg_confidence ≥ 0.85` over all ≥ 145 entries.
- **Exit Gate B (manual):** User reviews **20 randomly-sampled entries**; "correct" = (a) `inferred_feature` matches actual production code feature OR (b) `inferred_ac_summary` is within 2-token Jaccard ≥ 0.5 of the test's docstring/assertion intent. Must score **≥ 18/20 correct**.
- Both gates must pass.

P3+ consumes the JSON: when authoring SPEC, look up its tests → populate `test_ids[]` and seed AC drafts.

**Consequences:**
- ✅ No orphan tests
- ✅ Split gate distinguishes intrinsic confidence from ground-truth accuracy
- ⚠️ LLM hallucination ≈ 5-10%; addressed by manual gate
**Rejected alternatives:**
- Forward-only — orphan tests accumulate
- Per-feature reverse-map — slower (~60h)
- Pilot-only reverse-map — half-measure
- Self-confidence-only — known-bad metric (validator C2 critique)
**Source:** Interview #13 + Validator C2

### ADR-011: Code = Source of Truth, Drift Logged as Open Question with Aggregate Cap
**Status:** Accepted (2026-05-20, validator-revised R5)
**Context:** Code/docs/PLAN frequently disagree. SPEC writing needs a tie-breaker. Validator W3 flagged no aggregate cap on Open Questions.
**Decision:**
- SPEC reflects observed code behavior at authoring time.
- Divergences logged under `## ❓ Open Questions` with format:
  `### OQ-N: docs/spec diverges from code\n**Docs say:** {quote}\n**Code does:** {quote}\n**Resolution path:** invoke /hm:plan for {slug}`
- **Aggregate cap** (P5 exit gate): ≤ **30 total** Open Questions across all SPECs; **≤ 3 per SPEC**.
- If P5 finishes with > 30 OQs: a follow-up `PLAN-spec-oq-resolution-202X` is the release blocker for 0.18.0.
- CI lints SPECs with > 3 OQs and fails the PR (not just warns).

**Consequences:**
- ✅ Honest baseline preserved
- ✅ Drift tracked and capped
- ⚠️ Bug-in-code becomes baseline; mitigated by OQ visibility + plan escalation
**Rejected alternatives:**
- Docs-first — SPECs fail random gates
- Per-feature manual — 146 cost
- Auto-resolve via LLM — silent contract-affecting decisions rejected
**Source:** Interview #15 + Validator W3

### ADR-012: Catalog Schema as Phase 1 Deliverable (pydantic) + Versioning Policy
**Status:** Accepted (2026-05-20, validator-revised R5)
**Context:** Validator C4: Phase 1↔2 boundary was a tacit handshake (catalog yaml shape unspecified). Validator nit-13: schema versioning policy unspecified.
**Decision:**
- `harness_maker.spec_inventory.catalog_schema` (pydantic models) is a **Phase 1** deliverable, not Phase 2.
- Models:
  - `Feature` (id, kind: python|template|agent|skill|hook, path, parent_spec_slug, suggested_tier, llm_proposed_tier, override_tier)
  - `L1Cluster` (slug, title, member_feature_ids, invariants_description)
  - `Catalog` (schema_version: 1, l1_clusters[], features[], weight_recalibrations[])
- Phase 1 exit criterion adds: `pytest tests/unit/test_catalog_schema.py` green; round-trip yaml ↔ pydantic for a fixture catalog.
- **Versioning policy** (also applies to SPEC.machine.yaml ADR-006 schema_version):
  - Bumps follow `spec_machine migrate vN vN+1` CLI.
  - **Additive-only** within a minor version (0.18.X → 0.18.Y). Destructive removal requires deprecation in vN with `deprecated: true` flag + 2-minor-version grace period + explicit user confirmation prompt on migrate.
  - Migration script never silently rewrites user files. Operates on backup copy in `.worktrees/spec-migrate-{ts}/`, prompts review, then `os.replace`.

**Consequences:**
- ✅ Phase 1↔2 boundary explicit
- ✅ Schema evolution path safe
- ⚠️ One additional pydantic module; ~80 lines
**Rejected alternatives:**
- Catalog schema as part of Phase 2 — boundary remains tacit
- No version policy — silent migrations break user files
**Source:** Validator C4 + nit-13

### ADR-013: SPEC Optional in Workflow + Prompt-Driven P5 Bulk (improve-mode Pattern) + Spec-Drift Layer Gated by dev_mode
**Status:** Accepted (2026-05-20, /hm:plan interview R5 + R6 validator-revision)
**Context:** Validator W9 + W5: integration with existing /hm:plan/review undefined; bulk-authoring approach (autoloop_driver.run()) infeasible. Validator R2 C1-relocated: a `BatchSpecExecutor` cannot simultaneously conform to `autoloop_driver.ExecutorCallable: Callable[[Feature, int], bool]` AND invoke the `/hm:spec` slash command, because `autoloop_driver.py:430-433` explicitly says prompt-driven orchestration does NOT go through `run()`. User chose SPEC-optional + **prompt-driven P5 (improve-mode pattern)**.
**Decision:**
- **SPEC remains optional** for new-feature flow. The existing 5-stage workflow (RESEARCH → PLAN → EXECUTE → REVIEW → WRAPUP) is unchanged.
- `/hm:plan` continues to consume SPEC if present (`specs/SPEC-{slug}.md`); behavior unchanged.
- `/hm:review` does NOT mandatorily read SPEC.machine.yaml; existing PLAN-based review unchanged.
- **spec_drift Layer in `/hm:health` is gated by `dev_mode`**:
  - `dev_mode: spec-driven` → spec_drift Layer **warns** on orphan tests, stale mutations, AC↔test gaps, > 3 OQs per SPEC.
  - `dev_mode: task-driven` → spec_drift Layer **silent** (does not run).
- **P5 bulk authoring uses prompt-driven `/hm:loop p5-batch-N`** (mirrors improve-mode in `/hm:loop`, NOT `autoloop_driver.run()`):
  - User invokes `/hm:loop p5-batch-N` for a batch.
  - The `/hm:loop` command template (Jinja, rendered into `.claude/commands/hm/loop.md`) contains the per-batch procedure as **prompt instructions**: (a) read next-batch queue from `BatchSpecState`, (b) for each feature: invoke `/hm:spec {slug}` (prompt-side, same conversation), (c) per-SPEC 4-gate check (pytest+coverage+spec_quality+mutation/3-layer), (d) update INDEX.md.
  - `BatchSpecState` (formerly `BatchSpecExecutor`) is a **state helper module** in `harness_maker.spec_inventory`, NOT a Python ExecutorCallable. Its surface: `next_batch_queue()`, `mark_complete(slug, status)`, `current_progress()`. Purely CRUD over `work-docs/p5-batch-state.yaml`. NO autoloop_driver.run() involvement.
  - 4-gate convergence rules are encoded **in the slash-command markdown** (same way improve-mode encodes its 4-gate prompt-side), not in `autoloop_driver.py`.
  - Between batches, user reviews `INDEX.md` delta and invokes next batch.
  - If a SPEC fails its 4-gate, the loop pauses; user intervenes. No `failed_streak_cap` (Python-level concept) — convergence is judgment-driven by the LLM running `/hm:loop`.
- ADR-013 explicitly closes the question of /hm:plan vs SPEC ADR conflict: SPEC ADRs are subordinate; PLAN ADRs (this PLAN's, and any future) take precedence on contract decisions.

**Consequences:**
- ✅ Zero disruption to existing workflow users (task-driven default)
- ✅ P5 path is consistent with how improve-mode already works (proven pattern)
- ✅ No infeasibility — `/hm:spec` invocations are prompt-side, in the same conversation as `/hm:loop p5-batch-N`
- ✅ `BatchSpecState` is a thin CRUD helper, easy to test
- ⚠️ Total time ≈ 12 batches × user-initiation = N user-actions; mitigated by `INDEX.md` progress visibility
- ⚠️ Prompt-side 4-gate logic must be carefully encoded in the loop command template; mitigated by P3 pilot which exercises the same gates manually first
**Rejected alternatives:**
- Full integration (RESEARCH → SPEC → PLAN → EXECUTE → REVIEW mandatory) — heavyweight, would warrant separate PLAN
- Tier-gated mandatory SPEC — couples workflow to tier definitions
- Defer integration — workflow-gap rot
- **Python-side `/hm:spec` invoker via `autoloop_driver.run()`** — *originally chosen in R5 but refuted by Validator R2*; a Python callable in `run()`'s while-loop cannot yield control to dispatch a slash command and resume. The prompt-driven path (this ADR's final form) is the only viable shape.
- Anthropic SDK direct call (Python generates SPEC content without slash command) — loses `/hm:spec` interview quality + Anthropic API cost outside subscription
**Source:** Interview #16 + #18 + Validator C1 + W9 + R2 C1-relocated

---

## 🏗️ Technical Design

### Current State

```
src/harness_maker/
├── spec_quality.py          ← 5-dim rubric, LLM-judged (209 lines, 5 callsites)
├── autoloop_driver.py       ← feature-mode-only run() (callable executor, 5-streak halt)
├── templates/stages/spec.md.j2  ← 8-section SPEC.md output
└── (no spec_machine, spec_inventory, spec_mutation, spec_drift modules)

specs/                       ← does NOT exist
work-docs/                   ← PLANs, RESEARCH (40+ files)
tests/                       ← 154 test files
```

### Affected Components

| Component | Change | Why |
|-----------|--------|-----|
| `src/harness_maker/spec_quality.py` | Extend rubric with `machine_verifiability`, `mutation_coverage_set`, `non_python_intent_alignment`. New 2-arg signature `evaluate_spec(spec_text, machine_yaml=None)`; backward-compat for existing 5 single-arg callsites. | ADR-004, ADR-006, ADR-009; Risk R12 mitigation |
| `src/harness_maker/templates/stages/spec.md.j2` | Dual-write SPEC.md + SPEC.machine.yaml; embed mandatory `ac_type` prompt; add §9 `🔗 Machine Spec`; mirror `tier:` into `.md` frontmatter for cross-validation. | ADR-006, ADR-007 |
| `src/harness_maker/spec_machine.py` | **NEW** — pydantic v1 schema; `validate_yaml`, `cross_validate(md, yaml)` enforcing the 6 contract rules, `evaluate_coverage(yaml, pytest_collect_json)`, `resolve_pytest_selector(slug)`. | ADR-006, ADR-007, ADR-004 |
| `src/harness_maker/spec_inventory/__init__.py` | **NEW** package. | catalog/inventory |
| `src/harness_maker/spec_inventory/catalog_schema.py` | **NEW** — pydantic models `Feature`, `L1Cluster`, `Catalog`; round-trip yaml ↔ pydantic. | ADR-012 |
| `src/harness_maker/spec_inventory/catalog.py` | **NEW** — `enumerate_features()` walks `src/` and `templates/`. | ADR-001 |
| `src/harness_maker/spec_inventory/tier_assign.py` | **NEW** — heuristic scorer + LLM disagreement + weight recalibration. | ADR-008 |
| `src/harness_maker/spec_inventory/reverse_map.py` | **NEW** — LLM walks 154 tests → AC catalog JSON. | ADR-010 |
| `src/harness_maker/spec_inventory/batch_state.py` | **NEW** — `BatchSpecState` CRUD helper over `work-docs/p5-batch-state.yaml`. Surface: `next_batch_queue()`, `mark_complete(slug, status)`, `current_progress()`. NOT an ExecutorCallable. Consumed prompt-side by `/hm:loop p5-batch-N`. | ADR-013 (revised R2) |
| `src/harness_maker/templates/commands/hm/loop.md.j2` | Extend to render P5 batch procedure (improve-mode pattern): per-feature `/hm:spec` invocation + 4-gate convergence + INDEX.md update — all encoded as prompt instructions. | ADR-013 |
| `src/harness_maker/spec_mutation.py` | **NEW** — mutmut wrapper, baseline measurer (`measure_baseline`), tier-threshold gate, CI artifact emission. | ADR-005 |
| `src/harness_maker/observability/spec_drift.py` | **NEW** — drift checker (orphan tests, stale mutation, AC↔test gaps, OQ overflow). Gated by `dev_mode`. | ADR-004 + ADR-013 |
| `pyproject.toml` | Add `mutmut>=2.4` dev dep. | ADR-005 |
| `.github/workflows/spec-mutation.yml` | **NEW** — nightly mutmut run, artifact upload, GitHub Issue on regression. | ADR-005 |
| `.github/workflows/spec-drift.yml` | **NEW** — weekly drift sweep. | drift gate |
| `.claude/harness.yaml` (rendered) | Add `spec.machine_schema_version: 1`, `spec.mutation_tool: mutmut`, `spec.drift_gate_enabled: ${dev_mode == 'spec-driven'}`. | ADR-006, ADR-013 |
| `specs/INDEX.md` | **NEW** — coverage matrix. | ADR-002 |
| `specs/SPEC-{slug}.{md,machine.yaml}` × ~146 | **NEW** — bulk authored P3+. | PLAN output |

### Dependencies
- **mutmut** ≥ 2.4
- Existing: anthropic SDK (subscription), Jinja2, pydantic, pytest, ruff, mypy — no version changes

### Architecture (component graph)

```
                      /hm:spec  (slash command, Phase 1 upgrade)
                          │
                          ├── spec_quality.py  (extended rubric)
                          │      └─→ anthropic.judge (subscription)
                          │
                          ├── spec_machine.py  (validate, cross_validate, resolve_pytest_selector)
                          │
                          └── writes:
                              ├── specs/SPEC-{slug}.md       (human)
                              └── specs/SPEC-{slug}.machine.yaml (machine)
                                                  ▲
                                                  │ consumed by
                                                  │
   /hm:health → observability/spec_drift.py ──────┤
                  (gated by dev_mode)             │
   CI nightly → spec_mutation.py (mutmut) ────────┤
   pytest CI → spec_machine.evaluate_coverage ────┘

   spec_inventory/
     ├── catalog_schema.py      ── pydantic models (P1)
     ├── catalog.py             ── enumerate features (P2)
     ├── tier_assign.py         ── heuristic + LLM + recalibrate (P2)
     ├── reverse_map.py         ── 154 tests → AC catalog (P0)
     └── batch_state.py         ── BatchSpecState CRUD helper (P5; NOT executor)
                  │
                  └── consumed prompt-side by `/hm:loop p5-batch-N`
                       (improve-mode pattern: per-feature `/hm:spec` invocation
                        + 4-gate convergence + INDEX.md update — encoded as
                        prompt instructions in the loop command template;
                        autoloop_driver.run() is NOT involved)
```

### Data Flow
1. **Authoring (P3 pilot, P5 bulk):** Batch initiated → catalog yaml + test-inventory.json consulted → `/hm:spec` runs per feature → spec_quality gate → mutmut gate (Python) / non-Python 3-layer gate.
2. **Verification (CI + /hm:health):** pytest runs by slug → `spec_machine.evaluate_coverage` reads .machine.yaml → confirms 100% mapping → `spec_quality` re-runs (cache-aware) → `spec_mutation` runs (cached) → `spec_drift` flags failures.
3. **Drift (post-merge):** code in `paths_to_mutate` → CI looks up matching SPECs → marks `status: drift` until re-verified.

### API Changes
- `harness_maker.spec_quality.evaluate_spec(spec_text)` → **backward-compat preserved**. New optional kwarg `machine_yaml: str | None = None`. Existing 5 callsites: 0 changes.
- `harness_maker.spec_machine` — new public API: `load(path)`, `validate(model)`, `cross_validate(md, yaml)`, `evaluate_coverage(yaml, pytest_json)`, `resolve_pytest_selector(slug)`.
- `harness_maker.spec_inventory` — new public API: `enumerate_features()`, `assign_tiers(features)`, `reverse_map_tests()`, `BatchSpecState` (CRUD: `next_batch_queue()`, `mark_complete()`, `current_progress()`).
- `harness_maker.spec_mutation` — new: `measure_baseline(paths) -> float`, `run_mutation(spec_yaml_path) -> MutationReport`, `gate(report, tier, baseline) -> bool`.

CLI:
- `python -m harness_maker.spec_machine validate <yaml_path>` — exit 0/1.
- `python -m harness_maker.spec_machine migrate v1 v2 --target specs/SPEC-X.machine.yaml` — versioned migration.
- `python -m harness_maker.spec_mutation gate <spec_slug>` / `measure-baseline <paths…>` — runs+evaluates.
- `python -m harness_maker.spec_inventory build-catalog` / `reverse-map` / `tier-assign` / `enumerate --dry-run` — pipeline runners.

No breaking changes: `.machine.yaml` schema_version 1, `ac: []` accepted with warning in transition.

---

## 📝 Implementation Plan

### Phase 0 — Test Inventory Reverse-Map (ADR-010)

- **Scope (in):** `src/harness_maker/spec_inventory/__init__.py` + `reverse_map.py` (new), `work-docs/test-inventory-2026-05.json` (output), `tests/unit/test_spec_inventory_reverse_map.py` (new). Note: `spec_inventory/catalog_schema.py` moved to Phase 1 (ADR-012).
- **Scope (out):** No SPEC files, no `/hm:spec` changes, no catalog yet.
- **Exit Gate A (auto):** `uv run python -m harness_maker.spec_inventory reverse-map > work-docs/test-inventory-2026-05.json` exits 0; JSON has ≥ 145 entries; `verify-inventory work-docs/test-inventory-2026-05.json` reports `avg_confidence ≥ 0.85`.
- **Exit Gate B (manual):** `uv run python -m harness_maker.spec_inventory sample-for-review work-docs/test-inventory-2026-05.json -n 20 > /tmp/sample.json` → user inspects → user scores; **≥ 18/20 correct** where correct = (feature match) OR (AC summary Jaccard ≥ 0.5 with test intent).
- **Both gates pass; otherwise iterate.**
- **Risk:** medium — LLM hallucination ~5-10% (R1).
- **Rollback point:** revert PR; no SPEC artifacts.

### Phase 0.5 — Pilot Baseline Measurement (ADR-005)

- **Scope (in):** Install mutmut as dev dep (early); run `mutmut run --paths-to-mutate=src/harness_maker/render.py` and `mutmut run --paths-to-mutate=src/harness_maker/cache.py`; record baseline scores in `work-docs/spec-mutation-baseline-2026-05.json`.
- **Scope (out):** No SPEC framework code yet (only the mutmut install).
- **Exit criterion:** `mutmut results` produces parseable output for render.py and cache.py; JSON written with `{render: 0.XX, cache: 0.XX}`. **Runtime fallback rule** (validator R2 warning P0.5-time-budget): if a baseline run exceeds 60 minutes wall-clock, abort and re-invoke with `mutmut run --runner pytest --tests-dir tests/unit --simple-output` against a sampled 200-mutant budget (`mutmut run --use-coverage` + early-stop). Record `sampled: true` in the baseline JSON when the fallback fires; downstream ADR-005 formula treats sampled baselines identically to full ones for first-cycle threshold-setting, with `last_mutation_run` carrying a `sampled` flag.
- **Outcome feeds:** ADR-005 mutation_threshold formula; Phase 3 exit criteria for pilot SPECs use **computed** thresholds (not hardcoded 85%/70%).
- **Risk:** low — measurement only.
- **Rollback point:** revert PR; mutmut dep stays as part of P1.

### Phase 1 — SPEC Framework Upgrade (ADR-005, ADR-006, ADR-007, ADR-012, ADR-013)

- **Scope (in):**
  - `src/harness_maker/spec_machine.py` (new, ~350 lines: pydantic schema + validate + 6-rule cross_validate + evaluate_coverage + resolve_pytest_selector + migrate command)
  - `src/harness_maker/spec_mutation.py` (new, ~250 lines: mutmut wrapper + measure_baseline + tier gate including baseline-relative formula)
  - `src/harness_maker/spec_quality.py` (extend: 3 new rubric dims, `machine_yaml` kwarg, backward-compat for 5 callsites)
  - `src/harness_maker/spec_inventory/catalog_schema.py` (NEW per ADR-012, ~80 lines)
  - `src/harness_maker/spec_inventory/batch_state.py` (NEW, ~120 lines: `BatchSpecState` CRUD helper over `work-docs/p5-batch-state.yaml`. Surface: `next_batch_queue()`, `mark_complete(slug, status)`, `current_progress()`. NOT an ExecutorCallable.)
  - `src/harness_maker/templates/commands/hm/loop.md.j2` (extend: render P5 batch procedure as prompt instructions — per-feature `/hm:spec` invocation + 4-gate per-SPEC check + INDEX.md update — mirrors improve-mode pattern)
  - `src/harness_maker/templates/stages/spec.md.j2` (extend: dual-file write, ac_type prompt, §9 section, tier mirror in frontmatter)
  - `pyproject.toml` (`mutmut>=2.4` already from P0.5)
  - `.github/workflows/spec-mutation.yml` (new)
  - `tests/unit/test_spec_machine.py`, `test_spec_mutation.py`, `test_spec_quality_extended.py`, `test_spec_machine_cross_validate.py`, `test_catalog_schema.py`, `test_batch_state.py` (new)
  - `tests/snapshot/test_loop_p5_template.py` (new — snapshot the rendered `/hm:loop p5-batch-N` markdown to lock in the prompt-side 4-gate procedure)
  - `tests/snapshot/__snapshots__/spec_stage_v2.snap` (snapshot update)
  - `examples/sample.machine.yaml` (for validation smoke)
- **Scope (out):** No bulk SPEC writing yet. No feature catalog yet (P2). `/hm:health` integration (P6).
- **Exit criterion:**
  - All `pytest tests/unit/test_spec_*.py tests/unit/test_catalog_schema.py tests/unit/test_batch_state.py` green.
  - `uv run python -m harness_maker.spec_machine validate examples/sample.machine.yaml` exits 0.
  - `uv run python -m harness_maker.spec_inventory catalog_schema roundtrip-fixture` green (yaml ↔ pydantic).
  - `mutmut run --paths-to-mutate=src/harness_maker/spec_machine.py` smokes (any score acceptable).
  - `mypy --strict src/harness_maker/spec_machine.py src/harness_maker/spec_mutation.py src/harness_maker/spec_inventory/` green.
  - `ruff check . && ruff format --check .` green.
  - **Cross-validation desync detection test** asserts 6 rules each have a positive + negative test case.
  - `BatchSpecState` smoke test: instantiate with dummy queue of 2 features, exercise full CRUD (queue→complete→progress), assert state-file round-trips via atomic_write. NOT routed through `autoloop_driver.run()`.
  - **Loop template snapshot**: rendered `/hm:loop p5-batch-N` markdown contains the 4-gate procedure (pytest + coverage + spec_quality + mutation-or-3-layer) as explicit prompt steps; snapshot test locks the exact wording so prompt-side convergence stays stable.
- **Risk:** high — foundational.
- **Rollback point:** revert P1 PR → P0 + P0.5 state preserved.

### Phase 2 — Feature Catalog + Tier Assignment (ADR-001, ADR-002, ADR-008)

- **Scope (in):**
  - `src/harness_maker/spec_inventory/catalog.py` (new — enumerate via `src/harness_maker/` and `templates/` walk, exclude `_*` and `_partials/`)
  - `src/harness_maker/spec_inventory/tier_assign.py` (new — heuristic scorer + LLM disagreement + recalibration)
  - `work-docs/spec-catalog-2026-05.yaml` (output — full catalog, L1 cluster set, tier per L2, parent_spec links)
  - `work-docs/spec-catalog-disagreements-2026-05.md` (output — 5-15 disagreements for user review)
  - `tests/unit/test_spec_inventory_catalog.py`, `tests/unit/test_spec_inventory_tier.py` (new)
- **Scope (out):** No SPEC files written yet.
- **Exit criterion:**
  - `uv run python -m harness_maker.spec_inventory enumerate --dry-run` produces a count; PLAN gets updated if delta > ±10% from the ~146 estimate.
  - `uv run python -m harness_maker.spec_inventory build-catalog --output work-docs/spec-catalog-2026-05.yaml` exits 0.
  - Catalog has the enumerated number of L2 entries (post-dry-run) and **15 ± 3** L1 cluster entries.
  - Disagreement file has ≤ 20 entries.
  - User reviews disagreement file → updates `tier_override` on each as needed → re-runs `tier-assign --apply-overrides`.
  - If user override rate > 50% → `tier-assign --recalibrate` runs automatically → catalog regenerated.
  - User signs off via setting `status: tier_assignments_locked` in catalog yaml header.
  - `pytest tests/unit/test_spec_inventory_*.py` green.
- **Risk:** medium.
- **Rollback point:** revert PR; P1 framework remains.

### Phase 3 — Pilot 3 Reference SPECs (ADR-002 pilot design)

- **Scope (in):**
  - `specs/SPEC-render.md` + `specs/SPEC-render.machine.yaml` (Python T1)
  - `specs/SPEC-agent-code-reviewer.md` + `.machine.yaml` (non-Python T1)
  - `specs/SPEC-cache.md` + `.machine.yaml` (Python T2)
  - `specs/INDEX.md` (new — coverage matrix seeded with 3)
  - New test stubs **bounded by**: ≤ 10 stubs per pilot SPEC; ≤ 5 AC marked `status: pending_test` (deferred to follow-up).
- **Scope (out):** No L1 SPECs yet (L1 authored at start of each cluster's batch in P5). No other L2.
- **Exit criterion (per pilot SPEC):**
  - `pytest -k "spec-{slug} OR {slug_legacy}"` exits 0.
  - `python -m harness_maker.spec_machine evaluate-coverage specs/SPEC-{slug}.machine.yaml` reports `coverage: 1.0` (counting pending_test AC as non-counting toward 100% if < 5 of them).
  - `python -m harness_maker.spec_quality eval` returns `overall ≥ 85`.
  - For render (T1 Python): `python -m harness_maker.spec_mutation gate render` exits 0 (threshold = max(P0.5 baseline + 5pp, 85%)). If gap > 20pp, escalate to user before pilot exit.
  - For cache (T2 Python): same with T2 floor (max(baseline + 5pp, 70%)).
  - For code-reviewer (non-Python T1): all 3 layers pass (snapshot stable, schema valid, `non_python_intent_alignment ≥ 80`).
- **Risk:** high — first end-to-end smoke.
- **Rollback point:** revert P3 PR → P2 catalog and P1 framework remain.

### Phase 4 — Framework Adjustment (post-pilot, with Representativeness Probe)

- **Scope (in):** Framework files from P1 whose ergonomics issues surfaced in P3. Plus a representativeness probe.
- **Scope (out):** No bulk SPEC writing yet.
- **Exit criterion:**
  - P3 verification re-run after adjustment, still green for all 3 pilots.
  - **Representativeness probe:** Pick 2 random non-pilot features from catalog (from 2 different L1 clusters, neither in original 3) and run the framework dry-run (no commit). Both must produce schema-valid `.machine.yaml` and `spec_quality ≥ 75`. If either fails → adjust framework + re-probe (limit: 3 probe rounds; if 3rd fails → escalate to user, possibly trigger Phase 4.5 dedicated extension).
  - **Fuzzy-match calibration** (validator R2 suggestion fuzzy-match-tuning-deferred): collect ≥ 5 real edit pairs from pilot SPEC.md ↔ machine.yaml history (cases where humans intentionally tweaked AC titles). For each, assert `spec_machine.cross_validate` correctly accepts or rejects per intent. If ratio threshold 0.85 misfires on > 1/5, tune to a value passing all pairs; record final threshold in `spec_machine.FUZZY_RATIO_THRESHOLD` constant + ADR-007 update.
  - CHANGELOG-fragment in `work-docs/spec-framework-v1.1-deltas.md`.
- **Risk:** medium — bounded by probe representativeness.
- **Rollback point:** revert P4 PR → P3 state.

### Phase 4.5 — Optional Framework Extension (triggered conditionally)

- **Trigger:** P4 representativeness probe fails 3 times OR P4 framework diff > 100 lines.
- **Scope:** Targeted framework fix to address the failing case. No SPEC content.
- **Exit:** P4 representativeness probe passes within 1 additional probe round.
- **Risk:** medium — only invoked when P4 surfaces a representativeness gap.
- **Rollback point:** revert P4.5 → return to last green P4 state.

### Phase 5 — Bulk SPEC Authoring (Human-in-the-Loop Batches per ADR-013)

- **Scope (in):**
  - ~12 batches × ~10 SPECs each. User invokes `/hm:loop p5-batch-N` for each batch.
  - Each batch is **fully prompt-driven** (improve-mode pattern). The rendered loop command contains explicit instructions: read queue from `BatchSpecState`, for each feature invoke `/hm:spec {slug}` (prompt-side), apply 4-gate per-SPEC (pytest+coverage+spec_quality+mutation/3-layer), update `INDEX.md`, mark complete in state. **autoloop_driver.run() is NOT used** (per ADR-013 R2 revision).
  - L1 cluster SPECs authored at start of each cluster's first batch.
  - `specs/INDEX.md` updated incrementally per batch.
  - Test stubs **bounded per SPEC**: ≤ 10 new stubs / SPEC; ≤ 5 AC marked `status: pending_test` (rolled into follow-up).
- **Scope (out):** Framework changes (frozen at P4 / P4.5). User-driven workflow integration changes.
- **Exit criterion (per batch):**
  - Every SPEC passes per-SPEC verification (pytest+coverage+spec_quality+mutation/3-layer).
  - `specs/INDEX.md` matrix updated.
  - Commit `feat(specs): batch N — {feature names}`.
  - Aggregate Open Question count ≤ (3 × number_of_specs_in_batch).
- **Exit criterion (overall):**
  - All catalog L2 entries have SPEC files (∼131 L2 + ∼15 L1 = ~146 total).
  - `INDEX.md` matrix: each row has `status: verified`.
  - `uv run python -m harness_maker.spec_machine evaluate-coverage specs/ --aggregate` reports `coverage: 1.0`.
  - `uv run python -m harness_maker.spec_mutation gate --all` exits 0 (every Python SPEC meets baseline-relative threshold).
  - All non-Python SPECs pass tier-appropriate ADR-009 layers.
  - **Aggregate OQ count ≤ 30 (ADR-011).** > 30 → spawn `PLAN-spec-oq-resolution-202X` as release blocker.
  - Aggregate pending_test AC count ≤ 50 → spawn follow-up `PLAN-test-stub-backfill-202X` (non-blocking for 0.18.0 unless > 100).
- **Risk:** medium — long-running, user-paced.
- **Rollback point:** per-batch PR; failed batch reverts to prior batch's `INDEX.md`.

### Phase 6 — Drift Detection Integration (dev_mode-gated per ADR-013)

- **Scope (in):**
  - `src/harness_maker/observability/spec_drift.py` (new — orphan-test, stale-mutation, AC↔test gap, OQ overflow detectors)
  - `src/harness_maker/templates/stages/health.md.j2` patch — add `spec_drift` Layer **conditional on `dev_mode == 'spec-driven'`**
  - `.github/workflows/spec-drift.yml` (new — weekly sweep when SPEC files present)
  - `tests/unit/test_spec_drift.py`, `tests/integration/test_health_spec_drift_e2e.py` (new)
- **Scope (out):** No SPEC content changes.
- **Exit criterion:**
  - `/hm:health` output in a fixture project with `dev_mode: spec-driven` includes `spec_drift` Layer with: orphan tests = 0, stale mutations (>7d) = 0, AC↔test coverage gaps = 0, SPEC with > 3 OQs = 0.
  - Same fixture with `dev_mode: task-driven` does NOT show the `spec_drift` Layer (silent).
  - `pytest tests/integration/test_health_spec_drift_e2e.py` green.
  - Weekly workflow `workflow_dispatch` smoke test green.
- **Risk:** low — additive layer.
- **Rollback point:** revert PR; SPECs still verifiable manually.

### Phase 7 — Documentation + Release (0.18.0)

- **Scope (in):**
  - `CLAUDE.md` — new section "## SPEC management" describing dual-file, mutation tier policy, drift gate, OQ cap.
  - `README.md` — "SPECs" section.
  - `docs/HOW-IT-WORKS.md` / `.ko.md` — Spec Verification chapter.
  - `CHANGELOG.md` entry under `0.18.0`.
  - 5-file version bump (per CLAUDE.md): `.claude-plugin/plugin.json`, `.cursor-plugin/plugin.json`, `.codex-plugin/plugin.json`, `pyproject.toml`, `src/harness_maker/__init__.py` (0.17.1 → 0.18.0).
  - `git tag -a v0.18.0` + `git push origin main v0.18.0`.
- **Scope (out):** No SPEC content. (OQ resolution PLAN, if triggered, is its own follow-up release.)
- **Exit criterion:**
  - 5 version files identical at `0.18.0`.
  - `INTEGRATION=1 uv run pytest tests/integration/test_boundary_*.py` green (CLAUDE.md release procedure).
  - Tag push triggers `release.yml`; GitHub Release auto-created; PyPI publish succeeds.
  - **Aggregate OQ check at release**: if > 30 unresolved OQs → release blocked, OQ-resolution PLAN active.
- **Risk:** low.
- **Rollback point:** untag + delete remote tag → fix → re-tag patch.

---

## 🧪 Testing Strategy

### Unit
- `tests/unit/test_spec_machine.py` — schema validity, cross-validation (6 rules with desync ±cases), coverage computation, pytest-selector resolution (legacy + new naming).
- `tests/unit/test_spec_machine_cross_validate.py` — dedicated 6-rule positive/negative matrix.
- `tests/unit/test_spec_mutation.py` — mutmut output parsing, `measure_baseline`, baseline-relative gate.
- `tests/unit/test_spec_quality_extended.py` — 3 new dims; backward-compat for 5 existing callsites; LLM mocked.
- `tests/unit/test_catalog_schema.py` — pydantic round-trip; migration v1→v2 stub.
- `tests/unit/test_spec_inventory_catalog.py` — enumeration determinism, `--dry-run` count assertion.
- `tests/unit/test_spec_inventory_tier.py` — heuristic determinism; LLM-disagreement mock; recalibration math.
- `tests/unit/test_spec_inventory_reverse_map.py` — LLM-mocked test→AC parsing; sample-for-review CLI.
- `tests/unit/test_batch_state.py` — `BatchSpecState` CRUD smoke: queue → complete → progress round-trip via `atomic_write`. NO autoloop_driver coupling.
- `tests/snapshot/test_loop_p5_template.py` — rendered `/hm:loop p5-batch-N` markdown contains the 4-gate procedure verbatim (snapshot pinned).
- `tests/unit/test_spec_drift.py` — orphan/stale/gap/OQ-overflow detection; dev_mode gating.

### Integration
- `tests/integration/test_spec_stage_dual_write.py` — `/hm:spec` template re-render produces both files atomically.
- `tests/integration/test_health_spec_drift_e2e.py` — `/hm:health` against fixture (spec-driven on/off).
- `tests/integration/test_mutmut_smoke.py` — `mutmut run` against tiny module returns parseable report (gated `INTEGRATION=1`).
- `tests/integration/test_p5_batch_e2e.py` — `BatchSpecState` round-trip in a /hm:loop p5-batch-N simulation fixture for 2 features (state transitions: queued → in_progress → complete; INDEX.md update verified).

### Snapshot
- `tests/snapshot/test_spec_stage_v2.py` — `/hm:spec` render with frozen inputs vs `__snapshots__/`.
- `tests/snapshot/test_specs_committed.py` — file existence + frontmatter required keys for all `specs/SPEC-*.{md,machine.yaml}`.

### Manual
1. After P3, user reads `specs/SPEC-render.md` for narrative readability — should match `/hm:spec` human quality bar.
2. After P3, user inspects `specs/SPEC-render.machine.yaml` for schema clarity.
3. After each P5 batch, user opens `specs/INDEX.md` and spot-checks 3 random SPECs.

### LLM judge tests (subscription-allowed)
- `tests/integration/test_spec_quality_live.py` (`INTEGRATION=1` gated) — real anthropic client vs known-good + known-weak SPEC; assert score delta ≥ 30.

---

## ⚠️ Risks & Mitigation

| ID | Risk | Likelihood | Severity | Mitigation |
|----|------|-----------|----------|------------|
| R1 | LLM hallucination in P0 reverse-map produces wrong AC inferences | medium | medium | Split exit (auto + manual ≥18/20); per-batch sanity in P5 |
| R2 | mutmut runtime explodes (e.g., render.py ≈ 1500 lines) | medium | medium | Per-SPEC `paths_to_mutate` scoping; nightly + 7d cache; T3 informational only |
| R3 | spec_quality LLM-judge variance crosses gate threshold non-deterministically | high | medium | 3-run median if score ∈ [80, 90]; deterministic mock for snapshot; 7d cache |
| R4 | Bulk (P5) batch stalls or generates poor SPECs | medium | high | Prompt-driven 4-gate (encoded in `/hm:loop p5-batch-N` template per ADR-013 R2); user-paced (one batch at a time); per-feature failure pauses loop; user can interrupt at any time |
| R5 | SPEC.machine.yaml schema needs breaking change mid-initiative | low | high | `schema_version: 1` + ADR-012 migration policy (additive-only intra-minor, 2-version deprecation grace) |
| R6 | Some T1 paths still don't reach 85%+5pp threshold | medium | medium | P0.5 baseline measurement + P4 adjustment window; per-SPEC override with rationale; can downgrade to T2 with ADR |
| R7 | Cost — 146 SPECs × LLM judge × mutmut × spec_quality | medium | medium | Per CLAUDE.md: subscription allows; nightly CI gated; cache aggressively |
| R8 | Code-vs-docs conflict policy (ADR-011) locks in bugs | medium | high | OQ aggregate cap 30 (P5 exit blocker); per-SPEC cap 3 (CI lint hard fail); release blocker if exceeded |
| R9 | P2 catalog misses hidden surface | low | medium | `enumerate --dry-run` pre-flight; grep-counts public symbols + templates; PLAN refresh if delta > ±10% |
| R10 | Pilot 3 over-fit framework — bulk reveals unrepresentative cases | medium | medium | Phase 4 representativeness probe (2 random non-pilot features); Phase 4.5 fallback |
| R11 | `/hm:health` spec_drift Layer noisy in first weeks | medium | low | dev_mode=spec-driven gate (opt-in); initial 30d grace for `last_mutation_run`; tighten to 7d after stabilization |
| **R12** | `spec_quality.evaluate_spec` extension breaks 5 existing callsites | low | medium | Backward-compat kwarg `machine_yaml=None`; unit test for legacy single-arg signature |
| **R13** | `pytest -k spec-{slug}` doesn't match legacy `test_*` naming convention | high | medium | Test-naming bridge in `spec_machine.resolve_pytest_selector(slug) → "spec-{slug} OR test_{slug}"`; no forced rename |
| **R14** | L1/L2 mutation double-count when L1 `paths_to_mutate` ⊇ L2 | medium | low | L1 mutation gate uses union of child L2 paths; L1 score = union pass rate; documented in ADR-002 |

---

## ✅ Success Criteria

- [ ] **Phase 0** test inventory JSON + split-gate (auto ≥0.85 + manual ≥18/20) passed; committed to `work-docs/`.
- [ ] **Phase 0.5** baseline scores for render.py + cache.py recorded.
- [ ] **Phase 1** framework modules pass unit tests; mutmut + spec_quality + spec_machine + BatchSpecExecutor wire end-to-end; catalog_schema pydantic round-trips.
- [ ] **Phase 2** catalog yaml lists enumerated features, 15±3 L1 clusters; disagreement file resolved.
- [ ] **Phase 3** all 3 pilots pass per-SPEC verification with baseline-relative mutation thresholds.
- [ ] **Phase 4** framework deltas adjusted + representativeness probe passes (2 random non-pilot dry-runs).
- [ ] **Phase 4.5** (conditional) — invoked only if P4 probe fails 3 times; resolved within 1 additional round.
- [ ] **Phase 5** ~146/146 SPECs in `specs/`, `INDEX.md` complete, aggregate coverage = 1.0, OQ count ≤ 30.
- [ ] **Phase 6** `/hm:health` `spec_drift` Layer surfaces in spec-driven mode only; 0 orphans, 0 stale, 0 gaps.
- [ ] **Phase 7** v0.18.0 released, CHANGELOG, PyPI published, no aggregate OQ overflow.

---

## 🔍 Plan Validation

**Validator outcome:** MAJOR_REVISION_RESOLVED_R2 (two-round resolution with user-approved redesign).

**Round 1 verdict (2026-05-20):** MAJOR_REVISION — 4 critical + 8 warnings + 1 nit. All addressed (see Resolution table below).

**Round 2 verdict (2026-05-20):** MAJOR_REVISION (12 of 13 resolved; 1 newly-introduced via ADR-013 R1's `BatchSpecExecutor` infeasibility — `Callable[[Feature, int], bool]` cannot also invoke a slash command synchronously). Plus 1 warning (P0.5 wall-clock budget) + 1 suggestion (fuzzy-match tuning).

**User decision after Round 2 (Interview Round 6, Q19):** Option A — redesign P5 to **prompt-driven `/hm:loop p5-batch-N`** (improve-mode pattern, NOT `autoloop_driver.run()`); `BatchSpecExecutor` renamed to `BatchSpecState` (CRUD helper, not an ExecutorCallable). PLAN edited in place.

**Final Resolution table:**

| Validator critique | Round | Resolution |
|---|---|---|
| **C1** Phase 5 autoloop infeasibility | R1 | First attempt via `BatchSpecExecutor` (R5/R6) — refuted by validator R2. Final fix R6: prompt-driven `/hm:loop p5-batch-N` (improve-mode pattern); `BatchSpecState` is a CRUD helper, NOT an ExecutorCallable. ADR-013 updated to lock this; loop command template absorbs the 4-gate procedure as prompt instructions; P1 exit's smoke test is now state-CRUD round-trip + loop-template snapshot (not autoloop_driver.run()). |
| **C2** Phase 0 self-graded confidence | R1 | ADR-010 split exit: Gate A (auto avg_confidence ≥ 0.85) + Gate B (manual ≥ 18/20 sample-correct with concrete "correct" definition). |
| **C3** T1 ≥ 85% aspirational | R1 | ADR-005 baseline-relative formula `max(measured_baseline + 5pp, tier_floor)` + Phase 0.5 baseline measurement. |
| **C4** Phase 1↔2 catalog schema undefined | R1 | ADR-012 — `catalog_schema.py` pydantic moved to Phase 1 deliverable + Appendix B versioning policy. |
| **C1-relocated** BatchSpecExecutor ExecutorCallable+slash mutual exclusion | R2 | Resolved by R6 redesign above (Option A). |
| W1-W8, Nit-13 | R1 | All resolved in the R1 revision (see table prior). |
| W (R2) **P0.5 wall-clock budget unsupported** | R2 | Phase 0.5 exit criterion now includes a **runtime fallback rule**: if a baseline run exceeds 60 min wall-clock, abort and re-invoke with sampled 200-mutant budget (`--use-coverage` early-stop); record `sampled: true` flag in baseline JSON. |
| Suggestion (R2) **Fuzzy-match tuning deferred** | R2 | Phase 4 exit extended with **fuzzy-match calibration**: collect ≥5 real edit pairs from pilots; tune `FUZZY_RATIO_THRESHOLD` to pass all; record final value in `spec_machine` + ADR-007 update. |

**Outstanding:** None. All critical, warning, and suggestion items addressed. The single load-bearing redesign is ADR-013's switch from Python-callable `BatchSpecExecutor` to prompt-side `BatchSpecState` + loop-template-driven 4-gate. This makes P5 isomorphic to existing improve-mode in `/hm:loop`, which is a proven path (autoloop_driver.py:430-433 explicitly states improve-mode does not go through `run()`).

**Note on procedure:** `/hm:plan`'s default rule is "re-run validator once only". The PLAN's R2 returned MAJOR_REVISION, but the validator's own resolution audit confirmed 12/13 critiques resolved and offered a concrete `Option A` redesign. User selected Option A (Interview R6 Q19); PLAN edited accordingly. No third validator pass needed — the C1-relocated issue is structural (Python type signature + slash-command mutual exclusion) and the redesign eliminates the impossibility by construction (the prompt-driven path doesn't have the type signature, so the impossibility cannot recur in the new design).

---

## Appendix A — Open Implementation Questions (deferred to Phase 4)

1. Exact list of 15 L1 capability clusters (LLM proposes in P2; user locks). Tentative seed: `Rendering · Reconciliation · Synthesis · Interview · Autoloop · Reviewers · Security & Permissions · Observability · Memory · Worktree · Configuration & Manifests · Hooks · Templates · Caching · Crawler`.
2. Should `spec_quality.evaluate_spec`'s `dev_mode` gating coexist with new gates or supersede? Current: keep both; new layered on top.
3. Should nightly mutmut be gated on PR-touch labels or unconditional? Current: unconditional nightly + on-PR scoped.
4. INDEX.md format: machine-readable table. Columns: `slug | tier | parent_spec | spec_quality | mutation | status | last_verified`.

## Appendix B — Schema Versioning Policy (ADR-012)

Applies to both `SPEC.machine.yaml` (ADR-006) and `spec-catalog-*.yaml` (ADR-012).

- **Within minor version (0.18.X):** Additive-only changes. New optional fields OK. Removal forbidden.
- **Across minor versions (0.18 → 0.19):** Deprecation required:
  - Mark field `deprecated: true` in vN.
  - Maintain backward read for 2 minor versions (0.19 reads + writes new format; reads but warns on old format; 0.20 drops old format support).
- **Migration:** `python -m harness_maker.spec_machine migrate vN vN+1 --target specs/`.
  - Reads SPEC files; creates backup copies in `.worktrees/spec-migrate-{ts}/`.
  - Prompts user for review of diff.
  - On confirmation: `os.replace` atomic.
  - Never silently overwrites.
- **Breaking changes** (0.X → 0.X+1 in major bump): warrant a separate `PLAN-spec-schema-vN` document.

