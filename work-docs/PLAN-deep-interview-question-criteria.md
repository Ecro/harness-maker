---
type: plan
task_slug: deep-interview-question-criteria
status: planning
created: 2026-05-18
tags: [harness-maker, plan, deep-interview, preference-elicitation, inequality-gate]
research_doc: "[[RESEARCH-deep-interview-question-criteria]]"
interview_rounds: 5
adrs: 12
validator_outcome: MAJOR_REVISION_RESOLVED
summary: "Replace 3-layer gate with 5-term inequality across 4 stages; aggressive common-ground inference + telemetry safety net"
---

# PLAN — Deep-Interview Question Selection Criteria

## 🎯 Executive Summary

**What.** Replace the 3-layer deep-interview gate (5-rubric + GCIC + CLARITI + 5 implicit probes + weighted Ambiguity Score) with a single inequality:

```
ask(Q) iff  EIG(Q) ≥ ε  ∧  TaskRel·UserAns ≥ 0.7  ∧  slot ∉ common_ground  ∧  confidence < τ  ∧  open_ended < cap_locale
```

across all 4 stages (`research`, `spec`, `plan`, `loop`) simultaneously, matching the ADR-004 precedent in [[PLAN-deep-interview-llm-delegation]].

**Why.** RESEARCH established that the current 3-layer gate's magic numbers (Goal×0.4+Constraint×0.3+SC×0.3, streak=2, max_rounds=3) lack theoretical grounding. The 5-term inequality is grounded in BED-LLM, GATE/STaR-GATE, Clark/Grice common-ground pragmatics, and Calibrate-Then-Act — each term is citable. The user's stated core goal ("당연한 선택을 묻지 않도록") maps directly to the **common-ground** term.

**Key decisions (12 ADRs):**
- ADR-001: Full replacement, 4 stages simultaneous.
- ADR-002: EIG = LLM self-report proxy (~1 call/Q, ε=0.5).
- ADR-003: Common-ground includes LLM inference at ≥0.95 confidence (aggressive — user explicitly accepts elevated silent-miss risk).
- ADR-004: 5 implicit probe types deleted from gate logic.
- ADR-005: 5-term condition checklist replaces visual Ambiguity Score.
- ADR-006: No backward compat for `work-docs/loop-context/*.yaml` — hard break.
- ADR-007: Single ε=0.5 / τ=0.7; locale-aware open-ended cap (en=2, ko=1, ja=1).
- ADR-008: Primary observability target = silent-intent-miss detection.
- ADR-009: Common-ground persisted to PLAN frontmatter + `.claude/observability/cg-marks-{slug}.jsonl` audit log.
- ADR-010: Post-hoc LLM classifier in Phase 7 detects coverage-kind regression (5-types reborn as telemetry-only labels).
- ADR-011: harness.yaml old keys → warn-and-ignore on render.
- ADR-012: User override surface = single kill-switch `common_ground.llm_inference_enabled` (default true).

**Estimated impact.** 11 phases. Touches 4 stage templates + 4 new modules + interview.py + harness.yaml schema. Version bump 0.15.3 → 0.16.0 (breaking loop-context format change). No mid-loop migration; users on 0.15.x lose active loop state on upgrade.

## 📚 Prior Work

- [[RESEARCH-deep-interview-question-criteria]] — synthesizes BED-LLM, GATE/STaR-GATE, Calibrate-Then-Act into the 5-term inequality form.
- [[PLAN-deep-interview-llm-delegation]] — origin of the 3-layer gate this PLAN replaces (ADR-004 4-stage-simultaneous precedent is reused).
- [[PLAN-loop-interview-intensity]] — autoloop interview adaptivity; informs Side vs Production calibration discussion (resolved as single ε/τ in ADR-007).
- [[PLAN-antisycophancy-2026-05]] — communication-variant pattern; orthogonal to gate but shares "decisions reach disk via marker-bound channels" precedent (informs ADR-009 PLAN-frontmatter persistence).
- Memory: `feedback_pytest_background.md` ("pytest 항상 background, full suite 30-60s") — drives Phase 7 background-test convention.
- Memory: `feedback_ask_thoroughly_when_planning.md` ("Plan 단계엔 AskUserQuestion 적극 활용") — drove 5-round interview for this PLAN.

## 🎙️ Interview Transcript

| # | Round | Topic | Cat | Choice | → ADR |
|---|-------|-------|-----|--------|-------|
| 1 | 1 | Adoption scope | Scope | Full replacement, 4 stages at once | ADR-001 |
| 2 | 2 | EIG mechanism | Arch | A. Self-report proxy (~1 call/Q) | ADR-002 |
| 3 | 2 | Common-ground source | Arch | D. + LLM inference ≥0.95 | ADR-003 |
| 4 | 2 | 5 probe types fate | Arch | A. Delete entirely | ADR-004 |
| 5 | 3 | Score visualization | Style | A. 5-term condition checklist | ADR-005 |
| 6 | 3 | Backward compat (loop-ctx) | Contract | None at all (user free-form override) | ADR-006 |
| 7 | 3 | Preset calibration | Arch | C. Single ε/τ + locale-cap | ADR-007 |
| 8 | 4 | Primary failure mode | Risk | A. Silent-intent-miss | ADR-008 |
| 9 | 5 | CG persistence contract | Contract | D. Hybrid (PLAN frontmatter + JSONL audit) | ADR-009 |
| 10 | 5 | Coverage-kind detection | Risk | A. Post-hoc LLM classifier | ADR-010 |
| 11 | 5 | harness.yaml migration | Contract | A. Warn-and-ignore old keys | ADR-011 |
| 12 | 5 | Override surface | Arch | C. Single kill-switch | ADR-012 |

**Gate trajectory:** Round 1-4 produced 8 substantive decisions; Step E gate score 0.91 → 1.0 (2-round PASS streak). Round 5 was follow-up from `plan-validator` MAJOR_REVISION (10 critiques: 3 critical → interview-resolved, 6 warnings → 4 direct-fix + 2 interview-resolved, 1 suggestion → direct-fix).

**Disagreement log.** PM AI (me) leaned hybrid (Round 1 Option C) and conservative common-ground source (Round 2 Option A). User overrode toward full replacement + aggressive LLM-inference. Disagreement resolved in user's favor; primary risk (silent-intent-miss) is mitigated by ADR-008 telemetry + ADR-012 kill-switch.

## 📐 Architecture Decision Records

### ADR-001: Replace 3-layer gate with 5-term inequality, 4 stages simultaneously
**Status:** Accepted (2026-05-18, via /hm:plan interview)
**Context:** Current 3-layer gate just shipped via ADR-004 of [[PLAN-deep-interview-llm-delegation]]. RESEARCH grounds the inequality form in BED-LLM, GATE, Calibrate-Then-Act, Clark/Grice common-ground pragmatics.
**Decision:** Replace Phase 0.5 / Layer 1-3 blocks in `templates/commands/hm/{research,spec,plan,loop}.md.j2` with a single inequality-driven gate in one PLAN. Matches the 4-stage-simultaneous precedent.
**Consequences:**
- ✅ Theoretical grounding for every term (cite-able sources per RESEARCH).
- ✅ Cross-stage consistency immediate, no migration window.
- ⚠️ Large blast radius: 4 templates + interview.py + harness.yaml schema + loop-context format.
**Rejected alternatives:**
- Hybrid (3-layer + common-ground patch) — Rejected: loses theoretical grounding; doesn't justify the cost of opening this work twice.
- Spike on research stage only — Rejected: delays cross-stage consistency, telemetry signal across one stage is noisy.
- No adoption / threshold tuning — Rejected: doesn't solve user's stated "당연한 것 안 묻기" goal.
**Source:** Interview #1.

### ADR-002: EIG mechanism = LLM self-report proxy
**Status:** Accepted (2026-05-18)
**Context:** Per-candidate-Q LLM cost vs accuracy trade-off. RESEARCH identified 3 mechanisms (self-report, answer-disagreement, full MC).
**Decision:** For each candidate Q, one LLM call: "If user answered Q, would the implementation plan change? Rate 0.0-1.0." Threshold ε = 0.5.
**Consequences:**
- ✅ Cheapest (~1 call/Q vs 3-5 for disagreement vs 10+ for MC).
- ✅ Public interface `score_eig(q, ctx) -> float` is mechanism-agnostic — swap is module-internal (enforced in Phase 3 exit).
- ⚠️ Unvalidated for this domain; model may over/under-rate own counterfactual reasoning.
**Rejected alternatives:**
- Answer-disagreement sampling — Rejected: 3-5 calls/Q multiplies interview latency by candidate-pool size.
- Full BED-LLM MC — Rejected: 10+ calls/Q is prohibitive for interactive UX.
**Source:** Interview #2.

### ADR-003: Common-ground includes LLM inference at ≥0.95 confidence
**Status:** Accepted (2026-05-18)
**Context:** Silent-intent-miss vs ask-the-obvious trade-off. User's core stated goal is "당연한 선택을 묻지 않도록" — aggressive option preferred.
**Decision:** Common-ground source = explicit evidence (CLAUDE.md, harness.yaml, prior answers, SPEC/RESEARCH frontmatter, same-slug PLAN/REVIEW history) PLUS LLM-inferred slots when self-reported confidence ≥ 0.95, ALWAYS logged with provenance per ADR-009.
**Consequences:**
- ✅ Strongest "don't ask the obvious" behavior — matches user goal.
- ⚠️ Highest silent-intent-miss risk (LLM may be overconfident). Mitigation: ADR-008 telemetry + ADR-012 kill-switch.
- ⚠️ Threshold 0.95 is uncalibrated empirically — Phase 2 false-positive guard fixture is a synthetic check, not real-world calibration.
**Rejected alternatives:**
- Minimal (explicit-only) — Rejected: doesn't solve user's stated goal.
- Slug-history only / project-memory only — Rejected: asymmetric without LLM inference.
**Source:** Interview #3.

### ADR-004: Delete 5 implicit probe types from gate logic
**Status:** Accepted (2026-05-18, amended by ADR-010 for telemetry retention)
**Context:** 5-types (WRONG/METHOD/STAKEHOLDER/STYLE/PERF) provided coverage breadth + no-repeat tracking. EIG ranking by pure info-gain is orthogonal to question-kind diversity.
**Decision:** Delete 5-types from gate generation logic. GCIC 4-axis provides slot-dimension breadth. EIG ranking generates Q content freely.
**Consequences:**
- ✅ Cleanest architecture — single ranking criterion.
- ⚠️ STYLE/PERF/STAKEHOLDER-type Qs may never be picked if EIG ranks them low. Mitigation: ADR-010 post-hoc classifier surfaces coverage gaps via telemetry.
**Rejected alternatives:**
- Retain as labeled candidate pool — Rejected: keeps two ranking systems in tension.
- No-repeat-tracking only — Rejected: same complexity, partial benefit.
**Source:** Interview #4. Amended: Interview #10 retains as telemetry labels.

### ADR-005: 5-term condition checklist replaces Ambiguity Score visualization
**Status:** Accepted (2026-05-18)
**Context:** Current `Ambiguity Score 0.8/1.0 (Goal×0.4+...)` gives smooth-progress affordance but its derivation is the magic-number RESEARCH set out to remove.
**Decision:** Per-round display: `✅ EIG ✅ CLARITI ❌ common-ground ✅ confidence ✅ open-ended → 4/5 met (NEEDS or PASS)`. Transparent mapping to inequality terms.
**Consequences:**
- ✅ No magic number; user sees exactly which term fails.
- ⚠️ Binary per-term display loses smooth-progress feel.
**Rejected alternatives:**
- Derived single score from 5 terms — Rejected: reintroduces magic weighting.
- Per-round elimination funnel — Rejected: too busy for typical case.
**Source:** Interview #5.

### ADR-006: No backward compatibility for work-docs/loop-context/*.yaml
**Status:** Accepted (2026-05-18, user override of presented options)
**Context:** Old format has weighted-sum `ambiguity_score`; new format has 5-term results. Loop-context is local-only (gitignored).
**Decision:** Hard break. No migration logic. No deprecation notice. Active loops on upgrade abort with whatever schema error surfaces. Version bump 0.16.0 (semver minor for breaking change pre-1.0) is the only signal.
**Consequences:**
- ✅ Zero migration debt in code.
- ⚠️ Any user mid-loop on 0.15.x→0.16.x upgrade loses state.
**Rejected alternatives:**
- Lossy migration, dual-write, additive — All Rejected: maintenance debt > user value for local-only file.
**Source:** Interview #6.

### ADR-007: Single ε / τ + locale-aware open-ended cap
**Status:** Accepted (2026-05-18)
**Context:** RESEARCH suggested per-preset calibration; locale-aware cap was a candidate per memory feedback (user prefers "직접적, no preamble").
**Decision:** ε = 0.5, τ = 0.7 uniform across Side and Production presets. Open-ended cap is a locale function: en=2, ko=1, ja=1, default=1.
**Consequences:**
- ✅ Simplest calibration story.
- ✅ ko/ja users get at most 1 open-ended Q per turn — matches "직접적" preference.
- ⚠️ May under-fit Side preset's lightweight philosophy. Revisit if telemetry shows.
**Rejected alternatives:**
- Per-preset multiplier / explicit values — Rejected: more surface, low evidence base.
- Defer all to telemetry — Rejected: needs *some* shippable defaults.
**Source:** Interview #7.

### ADR-008: Primary observability target = silent-intent-miss
**Status:** Accepted (2026-05-18)
**Context:** ADR-003 aggressive common-ground inference is the largest user-visible risk; telemetry must surface failures empirically.
**Decision:** Instrument `silent_intent_miss` counter. Increment when:
- REVIEW stage flags a mis-specification on a slot previously marked common-ground at LLM-inference ≥0.95, OR
- Same-session user reopens a slot marked common-ground.
Surface via `/hm:health` Layer 1 sub-check `silent_intent_miss_rate < {threshold TBD per telemetry}`.
**Consequences:**
- ✅ Aggressive-inference failures are observable, not silent.
- ⚠️ Adds cross-stage data flow (REVIEW reads PLAN frontmatter — see ADR-009).
**Source:** Interview #8.

### ADR-009: Common-ground persistence = PLAN frontmatter + JSONL audit
**Status:** Accepted (2026-05-18)
**Context:** ADR-008 telemetry requires REVIEW to know which slots were marked common-ground. Need a concrete data contract.
**Decision:** Two sinks:
- **PLAN frontmatter** array `common_ground_marks: [{slot, source, confidence, inferred_by, timestamp}]`. Runtime data path: REVIEW.md.j2 reads from here.
- **`.claude/observability/cg-marks-{slug}.jsonl`** append-only audit log. Drift analytics path: `/hm:health` reads here for threshold-drift detection.
Schema: `source` ∈ {`CLAUDE.md`, `harness.yaml`, `prior-answer:{round_n}`, `SPEC-frontmatter`, `RESEARCH-frontmatter`, `PLAN-history:{slug}`, `REVIEW-history:{slug}`, `LLM-inferred:{model}`}. `inferred_by` ∈ {`explicit`, `llm-inference:{confidence}`}.
**Consequences:**
- ✅ REVIEW has a deterministic file to read (PLAN frontmatter); telemetry has audit history (JSONL).
- ⚠️ Two write paths for one fact — race conditions possible (mitigated by atomic write per CLAUDE.md atomic_write pattern).
**Rejected alternatives:**
- PLAN frontmatter only — Rejected: no historical drift signal.
- JSONL only — Rejected: REVIEW would have to parse a separate file every check.
- In-memory only — Rejected: no cross-process telemetry.
**Source:** Interview #9.

### ADR-010: Coverage-kind detection = post-hoc LLM classifier (telemetry only)
**Status:** Accepted (2026-05-18; amends ADR-004)
**Context:** Validator Critical #3 — deleting 5-types removes the taxonomy needed to detect coverage regression. ADR-004's "STYLE/PERF/STAKEHOLDER never picked" risk becomes undetectable without re-introduction in some form.
**Decision:** New module `src/harness_maker/observability/coverage_classifier.py` with `classify_q(asked_q: str) -> Literal["WRONG","METHOD","STAKEHOLDER","STYLE","PERF","OTHER"]` (1 LLM call). Phase 7 integration fixture runs 10+ synthetic interviews; assertion: each label appears ≥1 across the fixture OR raises warning. Gating logic unchanged (5-types stay deleted).
**Consequences:**
- ✅ Coverage regression is detectable; ADR-004 telemetry gap closed.
- ⚠️ Classifier adds LLM cost in CI fixture (mitigated by mock LLM in unit tests; real call only on INTEGRATION=1 e2e).
**Source:** Interview #10.

### ADR-011: harness.yaml old keys → warn-and-ignore on render
**Status:** Accepted (2026-05-18)
**Context:** Validator Warning #7 — ADR-006 "no backward compat" applied to loop-context (local-only). harness.yaml is user-edited; strict reject would foot-shoot every existing user.
**Decision:** Phase 1 render emits warning: `"deprecated key interview.deep_gate.max_rounds ignored — see CHANGELOG-0.16.0 migration note"` and proceeds. Same for `streak_target`. New keys get defaults if absent.
**Consequences:**
- ✅ Existing users upgrade without manual intervention.
- ⚠️ Warning may be ignored; user-perceived behavior changes silently.
**Rejected alternatives:**
- Error with migration hint — Rejected: too aggressive for user-edited file.
- Auto-rewrite — Rejected: invasive write to user file.
- Strict reject — Rejected: worst UX.
**Source:** Interview #11.

### ADR-012: Override surface = single kill-switch
**Status:** Accepted (2026-05-18)
**Context:** Validator Warning #8 — multiple ADRs reference "user can override" without enumerating keys; surface area = future maintenance.
**Decision:** Only `interview.deep_gate.common_ground.llm_inference_enabled: bool` (default `true`) is user-tunable in harness.yaml. When `false`, common-ground reverts to explicit-evidence-only (ADR-003 minimal variant). ε / τ / inference_threshold / locale-cap are constants in code (revisited via PLAN if telemetry demands).
**Consequences:**
- ✅ Minimal surface, single rollback lever for the highest-risk ADR (ADR-003).
- ✅ Power-user need for finer control → defer to future PLAN, evidence-driven.
- ⚠️ Inflexible if ε/τ tuning is needed urgently.
**Source:** Interview #12.

## 🏗️ Technical Design

### Current state (disk-verified 2026-05-18 amendment)
- **Stage templates** at `src/harness_maker/templates/stages/{research,spec,plan,review,execute,verify,wrapup}.md.j2` (7 files).
- **Command templates** at `src/harness_maker/templates/commands/hm/{loop,health,configure,uninstall,make,atomic_command,workflow_command}.md.j2`. **NOTE:** `loop.md.j2` lives here, NOT in `stages/`.
- Phase 0.5 / Layer 1-3 blocks (GCIC, CLARITI, 5 probes, weighted Ambiguity Score, 2-round streak) appear in: `stages/research.md.j2`, `stages/spec.md.j2`, `stages/plan.md.j2` (8 matches), `commands/hm/loop.md.j2` (11 matches).
- `src/harness_maker/interview.py:994-1050` (`_preset_extras()`) defines preset-level `deep_gate.max_rounds` / `streak_target` defaults (Production=3/2, Side-v1=3/2, Side-v2=1/1).
- `src/harness_maker/models.py` lines 590-591, 725-726 hard-code `"deep_gate": {"max_rounds": 3, "streak_target": 2}` in `InterviewAnswers` defaults (no separate `schema.py`).
- `src/harness_maker/templates/harness-yaml/{Production,Side}.yaml.j2` render the user's `harness.yaml` per preset; both reference `config.interview.deep_gate.max_rounds` / `streak_target` (Production line 11-12; Side parallel).
- `work-docs/loop-context/*.yaml` persists `ambiguity_score` weighted-sum results across interview rounds.

### New components
| Module | Responsibility |
|--------|----------------|
| `src/harness_maker/common_ground.py` | `detect_common_ground(slot, sources, *, llm_inference_enabled) -> CGMark \| None`. Reads explicit evidence sources; optional LLM-inference path returns mark only at confidence ≥ 0.95. Writes to PLAN frontmatter (caller-supplied accumulator) AND `.claude/observability/cg-marks-{slug}.jsonl`. |
| `src/harness_maker/eig.py` | `score_eig(q, ctx) -> float` — mechanism-agnostic public signature. Internal mechanism: LLM self-report proxy with hash-keyed cache. Module-private symbols. |
| `src/harness_maker/inequality_gate.py` | `apply_inequality_gate(candidates, slots, config) -> list[GateResult]`. Composes 5-term filter; ranks remaining by EIG descending; enforces locale-aware open-ended cap. |
| `src/harness_maker/observability/intent_miss.py` | `record_intent_miss(slot, mark, trigger) -> None`. Increments counter; emits structured telemetry event. |
| `src/harness_maker/observability/coverage_classifier.py` | `classify_q(asked_q) -> Literal["WRONG",...,"OTHER"]` — telemetry-only post-hoc classification. |

### Modified components (disk-verified)
- **4 templates split by directory**:
  - `src/harness_maker/templates/stages/research.md.j2`
  - `src/harness_maker/templates/stages/spec.md.j2`
  - `src/harness_maker/templates/stages/plan.md.j2`
  - `src/harness_maker/templates/commands/hm/loop.md.j2`

  Each: Phase 0.5 / Layer 1-3 blocks replaced with inequality invocation + 5-term checklist render.
- `src/harness_maker/templates/stages/review.md.j2`: hook added to read PLAN frontmatter `common_ground_marks:` and call `record_intent_miss()` on flagged mis-specification.
- `src/harness_maker/templates/commands/hm/health.md.j2`: Layer 1 sub-check `silent_intent_miss_rate < threshold` added.
- `src/harness_maker/interview.py:994-1050` (`_preset_extras()`): remove `max_rounds` / `streak_target` preset logic; wire new gate config defaults; add warn-and-ignore for deprecated keys.
- `src/harness_maker/models.py` lines 590-591, 725-726: replace hard-coded `"deep_gate": {"max_rounds": 3, "streak_target": 2}` with new defaults dict.
- `src/harness_maker/templates/harness-yaml/{Production,Side}.yaml.j2`: remove `deep_gate.max_rounds` / `streak_target` render lines; add new key renders (`eig_epsilon`, `confidence_tau`, `open_ended_cap_by_locale`, `common_ground.llm_inference_threshold`, `common_ground.llm_inference_enabled`).

### Common-ground persistence contract (ADR-009)
PLAN frontmatter excerpt:
```yaml
common_ground_marks:
  - slot: "Database engine"
    source: "CLAUDE.md"
    confidence: 1.0
    inferred_by: "explicit"
    timestamp: "2026-05-18T14:32:11Z"
  - slot: "MQTT topic format"
    source: "LLM-inferred:claude-opus-4-7"
    confidence: 0.97
    inferred_by: "llm-inference:0.97"
    timestamp: "2026-05-18T14:33:02Z"
```
JSONL audit log line schema: identical fields per mark, append-only.

### Data flow per interview round
1. Stage template enters gate with current GCIC 4-axis slot inventory + LLM-generated candidate Qs.
2. For each candidate Q:
   - `common_ground.detect_common_ground(slot)` → mark or None. If marked, append to `common_ground_marks` accumulator + JSONL.
   - If marked → filter out (skip).
   - Else: `eig.score_eig(q, ctx)` → EIG score; CLARITI inline; check `confidence < τ`; locale-cap check.
3. Surviving Qs ranked by EIG descending; top-K presented via `AskUserQuestion` (Claude Code) or `AskQuestion` (Cursor).
4. 5-term checklist rendered post-round.
5. Exit when all relevant slots have `confidence ≥ τ` OR user picks "end interview" OR max 3 rounds.

## 📝 Implementation Plan

### Phase 1 — Schema (models.py) + harness.yaml preset templates + old-key warn-and-ignore
**Scope (in):**
- `src/harness_maker/models.py` lines 590-591 + 725-726 (InterviewAnswers default dict): replace `"deep_gate": {"max_rounds": 3, "streak_target": 2}` with new defaults
- `src/harness_maker/templates/harness-yaml/Production.yaml.j2` lines 9-14
- `src/harness_maker/templates/harness-yaml/Side.yaml.j2` (parallel deep_gate block)
- `src/harness_maker/interview.py` `_preset_extras()` warn-and-ignore code path
- `tests/unit/test_models.py` + `tests/unit/test_synthesize.py` updates for new defaults
- `tests/unit/test_harness_yaml_migration.py` (new) — covers warn-and-ignore for deprecated keys
- `tests/unit/test_synthesize_snapshot.py` may need regen for harness.yaml render output

**Scope (out):** template stages/commands, observability modules.
**Schema changes:** Remove `interview.deep_gate.max_rounds`, `streak_target`. Add `eig_epsilon: float = 0.5`, `confidence_tau: float = 0.7`, `open_ended_cap_by_locale: dict[str, int] = {"en": 2, "ko": 1, "ja": 1, "default": 1}`, `common_ground.llm_inference_threshold: float = 0.95`, `common_ground.llm_inference_enabled: bool = True`. Default literals updated in models.py AND interview.py `_preset_extras()`.
**Exit:**
- `uv run pytest tests/unit/test_models.py tests/unit/test_synthesize.py tests/unit/test_harness_yaml_migration.py -q` green.
- Warn-and-ignore paths covered (both `max_rounds` and `streak_target` deprecated-key scenarios).
- `uv run mypy --strict src/harness_maker/models.py src/harness_maker/interview.py` green.
- `uv run pytest tests/unit/test_synthesize_snapshot.py -q` green (regen if needed).
**Risk:** low.
**Rollback point:** Phase 0 (no change).

### Phase 2 — common_ground.py + false-positive guard
**Scope (in):** `src/harness_maker/common_ground.py` (new), `tests/unit/test_common_ground.py` (new), `tests/unit/test_common_ground_false_positive_guard.py` (new).
**Scope (out):** templates, EIG/gate modules.
**Sub-exits:**
- Explicit-evidence path tested across all `source` schema values.
- LLM-inference path tested with mock returning calibrated confidence distributions; mark emitted iff ≥ 0.95.
- False-positive guard: 10+ hand-crafted "should-ask" slots (e.g., "what database engine?", "what error log format?", "preferred logging library?"); for each, the mock LLM-inference path must NOT return ≥0.95. If any returns ≥0.95, test fails → signals threshold uncalibrated.
- PLAN-frontmatter writer + JSONL writer both atomic (uses `harness_maker.io_utils.atomic_write`).
**Exit:** `uv run pytest tests/unit/test_common_ground*.py -q` green; mypy strict green.
**Risk:** medium (LLM inference correctness is ADR-008 primary risk).
**Rollback point:** Phase 1.

### Phase 3 — eig.py + mechanism-agnostic interface
**Scope (in):** `src/harness_maker/eig.py` (new), `tests/unit/test_eig.py` (new), `tests/unit/test_eig_interface_stability.py` (new).
**Sub-exits:**
- Public symbol: ONLY `score_eig(q: str, ctx: ScoringContext) -> float`. Mechanism is module-internal (private functions).
- `test_eig_interface_stability` uses `inspect.signature` to assert signature stability — guards ADR-002 rollback path.
- Cache hit rate measurable in test (hash-keyed by `(q_hash, ctx_summary_hash)`).
- Boundary tested: ε = 0.5 inclusive cutoff.
**Exit:** `uv run pytest tests/unit/test_eig*.py -q` green; `inspect.signature` assertion documented in module docstring.
**Risk:** medium.
**Rollback point:** Phase 2.

### Phase 4 — inequality_gate.py
**Scope (in):** `src/harness_maker/inequality_gate.py` (new), `tests/unit/test_inequality_gate.py` (new).
**Sub-exits:**
- Full 5-term filter table-tested (each term independently passes/fails; combined outcomes).
- Ranking order verified across multiple EIG distributions.
- Locale-cap enforcement: en=2, ko=1, ja=1, default=1.
- Edge cases: zero candidates, all-common-ground, all-low-EIG, all-low-confidence.
**Exit:** `uv run pytest tests/unit/test_inequality_gate.py -q` green; mypy strict green.
**Risk:** medium.
**Rollback point:** Phase 3.

### Phase 5 — Stage templates (4 sub-exits, per-template rollback) — **disk-verified paths**
**Scope (in):**
- `src/harness_maker/templates/stages/research.md.j2`
- `src/harness_maker/templates/stages/spec.md.j2`
- `src/harness_maker/templates/stages/plan.md.j2`
- `src/harness_maker/templates/commands/hm/loop.md.j2`  ← **lives in commands/, not stages/**

Each: remove Phase 0.5 / Layer 1-3 blocks; insert inequality_gate invocation + 5-term checklist render block.
**Scope (out):** `stages/review.md.j2` (Phase 8c), `commands/hm/health.md.j2` (Phase 8b), interview.py.
**Sub-exits (snapshot convention: `tests/unit/test_render*.py`; no `tests/snapshots/` dir exists):**
- 5.1 stages/research.md.j2: `uv run pytest tests/unit/test_render.py -q` green for research-related render; manual Cursor verified (`tests/cursor-compat/MANUAL_CHECKLIST.md`).
- 5.2 stages/spec.md.j2: same — render test green; Cursor verified.
- 5.3 stages/plan.md.j2: same.
- 5.4 commands/hm/loop.md.j2: `uv run pytest tests/unit/test_synthesize_snapshot.py tests/unit/test_render_manifest.py -q` green (manifest render covers commands/hm/); Cursor verified.
- Grep proves absence of `Ambiguity Score`, `Layer 1 — GCIC Gap Check`, `Layer 2 — Implicit Probing` literals in all 4 modified .j2 files.
- Per-template rollback: revert single .j2 file, leave others intact.

**Risk:** low (deterministic Jinja2 render).
**Rollback point:** Phase 4.

### Phase 6 — interview.py adaptation
**Scope (in):** `src/harness_maker/interview.py` (lines 994-1050 + caller sites), `tests/unit/test_interview.py`.
**Scope (out):** observability modules, templates.
**Exit:** `uv run pytest tests/unit/test_interview.py -q` green; mypy strict green; ruff green.
**Risk:** low.
**Rollback point:** Phase 5.

### Phase 7 — Snapshot regeneration + e2e + coverage classifier — **path-corrected**
**Scope (in):**
- Snapshot regen via existing convention: `tests/unit/test_render.py`, `tests/unit/test_synthesize_snapshot.py`, `tests/unit/test_render_manifest.py`, `tests/structural/test_snapshot_exclusions_effective.py` (run + accept new outputs)
- `tests/integration/test_inequality_gate_e2e.py` (new)
- `src/harness_maker/observability/coverage_classifier.py` (new — `observability/` dir already exists with `dashboard.py`, `verification_cache.py`)
- `tests/integration/test_coverage_kind.py` (new)

**Sub-exits:**
- All 4 modified stage/command templates produce regenerated snapshots; existing `test_render*.py` tests pass with new outputs.
- `test_inequality_gate_e2e.py` decorated with `@pytest.mark.skipif(not os.getenv("INTEGRATION"), reason="requires Claude subscription")`.
- `test_coverage_kind.py` uses mock LLM (NO `INTEGRATION` gate; runs in CI). Fixture: 10+ synthetic interviews; assertion: each of `{WRONG, METHOD, STAKEHOLDER, STYLE, PERF}` appears ≥1 OR raises pytest warning.
- `uv run pytest tests/` runs unit + mock-integration only.
- `INTEGRATION=1 uv run pytest tests/integration/` runs gated e2e.
**Risk:** low.
**Rollback point:** Phase 6.

### Phase 8a — intent_miss.py
**Scope (in):** `src/harness_maker/observability/intent_miss.py` (new), `tests/unit/test_intent_miss.py` (new).
**Sub-exits:** Counter increments on both triggers (REVIEW-mismatch path, same-session reopen path); structured event emitted with provenance.
**Exit:** `uv run pytest tests/unit/test_intent_miss.py -q` green.
**Risk:** low.
**Rollback point:** Phase 7.

### Phase 8b — health.md.j2 sub-check — **path-corrected**
**Scope (in):** `src/harness_maker/templates/commands/hm/health.md.j2` Layer 1 sub-check `silent_intent_miss_rate < threshold`; existing-convention snapshot test (extend `tests/unit/test_render.py` or `test_render_manifest.py` to cover the new check).
**Exit:** existing render tests green after the change; rendered health.md contains the new sub-check string.
**Risk:** low.
**Rollback point:** Phase 8a.

### Phase 8c — review.md.j2 hook + scripted integration test — **path-corrected**
**Scope (in):**
- `src/harness_maker/templates/stages/review.md.j2`  ← **lives in stages/, not commands/hm/**
  (reads PLAN frontmatter `common_ground_marks:` on mis-spec flagging; calls `intent_miss.record_intent_miss`)
- `tests/integration/test_review_intent_miss.py` (new — scripted, mock LLM, deterministic)

**Sub-exits:**
- Snapshot regen for stages/review.md (this is the FINAL template-touching phase — no later regen invalidates it).
- Scripted integration test: synthetic mis-spec fixture (mocked REVIEW agent output) + synthetic PLAN frontmatter with common_ground_marks; assertion: counter incremented exactly once per marked-slot mis-spec.
- Test decorated with `@pytest.mark.skipif(not os.getenv("INTEGRATION"))` for real Claude path; mock variant runs in CI.
**Exit:** `uv run pytest tests/integration/test_review_intent_miss.py -q` green (mock); existing render tests green for stages/review.md.
**Risk:** medium (cross-stage data flow contract).
**Rollback point:** Phase 8b.

### Phase 9 — Docs + version bump
**Scope (in):** `CHANGELOG.md` (new entry: BREAKING — loop-context format, deprecated harness.yaml keys, etc.), `CLAUDE.md` §"Communication variant policy" sibling section: new "Deep-Interview Gate (v2)", `docs/HOW-IT-WORKS.md` §11.21 rewritten, 5-file version bump: `.claude-plugin/plugin.json`, `.cursor-plugin/plugin.json`, `.codex-plugin/plugin.json`, `pyproject.toml`, `src/harness_maker/__init__.py`.
**Exit:** Field-specific Python assertions:
```python
import tomllib, json, re
assert tomllib.load(open('pyproject.toml','rb'))['project']['version'] == '0.16.0'
for p in ['.claude-plugin/plugin.json', '.cursor-plugin/plugin.json', '.codex-plugin/plugin.json']:
    assert json.load(open(p))['version'] == '0.16.0'
m = re.search(r'__version__\s*=\s*"([^"]+)"', open('src/harness_maker/__init__.py').read())
assert m.group(1) == '0.16.0'
```
**Risk:** low.
**Rollback point:** Phase 8c.

## 🧪 Testing Strategy

**Unit (mock LLM, deterministic, in CI):**
- `test_harness_yaml_schema.py`, `test_harness_yaml_migration.py` — schema + warn-and-ignore.
- `test_common_ground.py`, `test_common_ground_false_positive_guard.py` — explicit + LLM-inference paths; 10+ should-ask FP guard.
- `test_eig.py`, `test_eig_interface_stability.py` — score logic + signature stability.
- `test_inequality_gate.py` — 5-term composition + ranking + locale-cap.
- `test_interview.py` — preset wiring.
- `test_intent_miss.py` — both increment paths.

**Integration (mock LLM, in CI):**
- `test_coverage_kind.py` — 10+ synthetic interview fixture; kind distribution assertion.
- `test_review_intent_miss.py` (mock variant) — scripted PLAN frontmatter + synthetic REVIEW; counter increment verified.

**Integration (real Claude, `INTEGRATION=1` gated, NOT in default CI):**
- `test_inequality_gate_e2e.py` — full interview loop with realistic candidates.
- `test_review_intent_miss.py` (real variant) — real REVIEW agent.

**Snapshot (CI, deterministic via `freeze_time` + `normalize_for_snapshot`) — existing convention reused:**
- Snapshot tests live in `tests/unit/test_render*.py` + `tests/structural/test_snapshot_exclusions_effective.py`; there is NO `tests/snapshots/` directory.
- 3 stage templates (research, spec, plan) + 1 command template (loop) per Phase 5 sub-exits.
- `health.md` (Phase 8b) and stages/`review.md` (Phase 8c) covered by existing render tests; extend the same test files if a focused assertion on the new content is needed.

**Manual:**
- `tests/cursor-compat/MANUAL_CHECKLIST.md`: render-correctness in Cursor 2.4+ for all 4 stage commands + health + review.
- Codex render: AGENTS.md + .codex/agents/*.toml.

## ⚠️ Risks & Mitigation

| Risk | Severity | Likelihood | Mitigation |
|------|----------|------------|------------|
| Silent-intent-miss (ADR-008 primary) | high | medium | ADR-008 counter; `/hm:health` sub-check (Phase 8b); ADR-012 kill-switch (`common_ground.llm_inference_enabled=false` reverts to explicit-only). Phase 2 false-positive guard catches uncalibrated 0.95 threshold pre-ship. |
| Coverage-kind regression (STYLE/PERF/STAKEHOLDER never asked) | medium | medium | ADR-010 post-hoc classifier (Phase 7); fixture asserts each kind ≥1 across 10+ synthetic interviews; warning raised if absent. |
| EIG self-report proxy invalid for domain (ADR-002) | medium | low | Phase 3 enforces mechanism-agnostic public interface (`score_eig(q,ctx)->float`); rollback to answer-disagreement is module-internal swap with signature stability test as guard. |
| Backward compat break disrupts active users mid-loop (ADR-006) | low | low | CHANGELOG-0.16.0 BREAKING note; semver minor bump pre-1.0; loop-context aborts loudly. |
| harness.yaml deprecated keys silently ignored (ADR-011) | low | medium | Warning emitted on render; CHANGELOG migration note; users see warning at least once. |
| Locale cap (en=2, ko=1) confuses bilingual users | low | low | ADR-012 kill-switch doesn't affect cap, but cap is in code (not user-tunable per ADR-012) — future PLAN if telemetry signals. |
| LLM-inference threshold 0.95 uncalibrated empirically | medium | medium | Phase 2 false-positive guard fixture (10+ should-ask slots) catches over-confident model pre-ship. Post-ship: `/hm:health` surfaces silent-intent-miss rate. |
| Common-ground marks race condition (two write sinks) | low | low | Atomic write per CLAUDE.md `atomic_write` pattern for both PLAN frontmatter (full-file rewrite) and JSONL (append with O_APPEND). |

## ✅ Success Criteria

- [ ] 4 templates use single 5-term inequality gate (no 3-layer remnants in `src/harness_maker/templates/stages/{research,spec,plan}.md.j2` + `src/harness_maker/templates/commands/hm/loop.md.j2`); grep proves `Ambiguity Score`, `Layer 1 — GCIC Gap Check`, `Layer 2 — Implicit Probing` strings absent.
- [ ] `silent_intent_miss` counter wired; `/hm:health` Layer 1 surfaces `silent_intent_miss_rate` (via `src/harness_maker/templates/commands/hm/health.md.j2`).
- [ ] 5-term checklist visible in every stage's interview output (`✅ EIG ✅ CLARITI ❌ common-ground ✅ confidence ✅ open-ended → N/5 met`).
- [ ] Locale cap enforced: en→2, ko→1, ja→1 open-ended Q max per turn (verified in unit + render snapshot).
- [ ] `common_ground.llm_inference_enabled: false` in harness.yaml reverts ADR-003 to minimal explicit-only (kill-switch landed in `harness-yaml/{Production,Side}.yaml.j2` + `models.py`).
- [ ] PLAN frontmatter `common_ground_marks:` populated by `common_ground.detect`; `stages/review.md.j2` reads it.
- [ ] `.claude/observability/cg-marks-{slug}.jsonl` audit log written append-only with provenance.
- [ ] Phase 2 false-positive guard fixture (10+ should-ask slots) green — none return common-ground at ≥0.95.
- [ ] Phase 7 coverage-kind fixture (10+ synthetic interviews) — all 5 kinds present.
- [ ] `uv run pytest` green (unit + mock-integration); `uv run mypy --strict` green; `uv run ruff check . && uv run ruff format --check .` green.
- [ ] `INTEGRATION=1 uv run pytest tests/integration/` green (gated e2e).
- [ ] Render snapshot tests green (existing `tests/unit/test_render*.py` + `tests/structural/test_snapshot_exclusions_effective.py`); no separate `tests/snapshots/` dir created.
- [ ] Manual Cursor 2.4+ verification: all 4 modified template commands render correctly (3 stages + 1 command).
- [ ] Version bumped to 0.16.0 across 5 files; field-specific assertions pass.
- [ ] CHANGELOG-0.16.0 entry flags BREAKING (loop-context format + deprecated harness.yaml keys).

## 🔍 Plan Validation

**Pass 1:** `plan-validator` returned **MAJOR_REVISION** with 10 critiques (3 critical, 6 warnings, 1 suggestion). Resolution:
- 3 critical → Round 5 interview rounds (Q1 CG persistence → ADR-009, Q2 coverage → ADR-010, plus Phase 8 split direct fix).
- 6 warnings → 4 direct fixes (Phase 5 sub-exits, EIG interface, FP guard, INTEGRATION gate) + 2 interview rounds (Q3 harness.yaml → ADR-011, Q4 override → ADR-012).
- 1 suggestion → direct fix (field-specific version assertions).

**Pass 2:** `plan-validator` returned **APPROVED** (no remaining critiques; all categories clean).

**Pass 3 — Disk-verification amendment (2026-05-18, post-`/hm:loop` iter 1 halt):**
First /hm:loop launch halted at F1 inspection. Worktree inspection revealed multiple path mismatches between PLAN and disk that neither /hm:plan synthesis nor `plan-validator` caught (validator can't fs-check from prompt alone). Corrections applied to §Technical Design + §Implementation Plan (Phases 1, 5, 7, 8b, 8c) + §Testing Strategy + §Success Criteria:

| Was in PLAN | Disk reality |
|-------------|--------------|
| `src/harness_maker/schema.py` | does not exist; schema in `models.py` (InterviewAnswers defaults lines 590, 725) |
| `templates/harness.yaml.j2` | `src/harness_maker/templates/harness-yaml/{Production,Side}.yaml.j2` (per-preset) |
| `templates/commands/hm/{research,spec,plan,loop}.md.j2` | research/spec/plan in `templates/stages/`; loop in `templates/commands/hm/` |
| `templates/commands/hm/health.md.j2` | `src/harness_maker/templates/commands/hm/health.md.j2` (prefix added) |
| `templates/commands/hm/review.md.j2` | `src/harness_maker/templates/stages/review.md.j2` (different dir) |
| `tests/snapshots/test_render_*.py` | no such dir; existing `tests/unit/test_render*.py` + `tests/structural/` convention reused |

ADR set (001-012) unchanged — architectural decisions intact. Only file-layer paths corrected. Loop resumes from F1 with corrected scope.
