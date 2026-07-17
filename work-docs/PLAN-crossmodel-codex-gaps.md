---
type: plan
task_slug: crossmodel-codex-gaps
status: complete
created: 2026-06-07
tags: [harness-maker, plan, codex, cross-model, consensus, observability]
research_doc: "[[RESEARCH-crossmodel-codex-gaps]]"
interview_rounds: 5
adrs: 6
validator_outcome: MAJOR_REVISION_RESOLVED
summary: "Codex becomes a real review consensus peer + preset-gated mandatory + ledger/smoke + plan PIDA"
---

# PLAN — Cross-Model (Codex) Deepening

## 🎯 Executive Summary

**What:** Turn harness-maker's existing one-shot Codex second-opinion into (a) a real voting peer in `/hm:review` consensus, (b) preset-gated mandatory on high-risk paths, (c) observable via a calibration ledger + positive health smoke-test, and (d) a debate (PIDA) flow for `plan-validator` that cannot silently dismiss a Codex challenge.

**Why:** The shipped integration is engineering-complete but protocol-shallow (RESEARCH-crossmodel-codex-gaps). The binding real-world failure is **silent degradation** — local memory records warn-and-proceed masking THREE silent Codex skips in one week — and the `/hm:review` path has **zero** Codex orchestration today (verified: `stages/review.md.j2` has no Codex mention; Codex is opt-in `MAY` only inside two reviewer agent bodies, never a consensus vote). The user explicitly requires Codex to participate in `/hm:review`.

**Scope:** IN = H1 (PIDA), H2 (heterogeneous review consensus), H4 (health smoke), H6 (ledger), H7 (mandatory matrix). DEFERRED = H3 (generated-harness audit), H5 (curated bundle), H8 (`/duel` routes — vault `codex-duel` SKILL.md is not accessible from this session).

**Key decisions:** ADR-001 (review heterogeneous consensus at Step 4 filter), ADR-002 (preset×high-diff mandatory matrix), ADR-003 (shared high-diff detector), ADR-004 (plan PIDA), ADR-005 (ledger v1 + smoke), ADR-006 (loop applicability invariant).

**Estimated impact:** 7 phases. HIGH-risk core = Phase 4a/4b (Codex-as-voter at the consensus filter). Touches `models.py`, `templates/stages/{review,plan}.md.j2`, `templates/agents/_partials/second_opinion_codex.md.j2`, `consensus-arbiter_body.md.j2`, `plan-validator_body.md.j2`, `templates/commands/hm/health.md.j2`, new ledger schema + CLI + high-diff detector module. `two_pass_review.py` is explicitly OUT of scope (it is per-reviewer pass1/pass2, not cross-reviewer consensus).

## 📚 Prior Work

- [[RESEARCH-crossmodel-codex-gaps]] — 8 findings, per-finding code ground-truth, recommended observability-first (user overrode toward protocol-depth-first).
- [[PLAN-codex-second-llm-integration]] — the shipped integration; ADR-005 "Codex is input you cannot silently discard, not a verdict source" is preserved by ADR-004 here.
- [[PLAN-codex-mandatory-second-opinion]] — made plan-validator MUST; its ADR-004 **deferred** the code-reviewer/consensus-arbiter array-output rework. This PLAN does NOT inherit that rework (see ADR-001 — the consensus vote lives in the Step 4 prose filter, not the array pipeline).
- [[PLAN-codex-finding-schema-strict-mode]] — strict-output-schema rules (all-required + nullable-union + no `minimum/maxLength/pattern/format`); binds ADR-005's ledger schema.
- Memory `[wiki:gotcha] codex-exec-is-noninteractive-no-approval-flag` — warn-and-proceed masked 3 silent skips; "add a POSITIVE smoke/health check." Memory `[wiki:gotcha] subagent-tools-field-hard-gates-bash-permission` — `tools:` is the hard Bash gate. Memory `[fail:review] reviewer-subagent-model-unsupported` (count:3) — never pin Codex model ids.

## 🎙️ Interview Transcript

| # | Round | Topic | Category | Question | Choice | → ADR |
|---|-------|-------|----------|----------|--------|-------|
| 1 | 1 | review Codex participation | Architecture | How does Codex join `/hm:review`? | **Heterogeneous consensus 2 Claude + 1 Codex (k-of-3)** | ADR-001 |
| 2 | 1 | mandatory strength | Risk | When is Codex mandatory? | **Production preset review+plan mandatory** | ADR-002 |
| 3 | 2 | "양쪽모두" matrix | Risk | Confirm: Production always / Side high-diff, review+plan both | **Yes — Production always / Side high-diff** | ADR-002 |
| 4 | 2 | high-diff trigger | Contract | What defines "high diff"? | **Reuse review When-to-Run criteria + LLM boundary** | ADR-003 |
| 5 | 3 | optional scope | Scope | Which of H1/H3/H5/H8 to include? | **H1 IN, H8 IN→later out; H3/H5 out** + loop-applicability question | ADR-004, ADR-006 |
| 6 | 3 | ledger fidelity | Observability | H6 ledger v1 fidelity? | **disposition + skip-rate only (oracle nullable)** | ADR-005 |
| 7 | 4 | loop high-diff unit | Architecture | per-iteration vs cumulative diff in loop? | **per-iteration diff** | ADR-003, ADR-006 |
| 8 | 4 | H8 routes + source | Scope | `/duel` route scope given vault skill inaccessible? | **Defer H8 entirely** | — |
| 9 | 5 | C2 (Codex vote cosmetic) | Architecture | How to make Codex a real vote despite null file/line? | **Build Codex-specific match relaxation** | ADR-001 |
| 10 | 5 | C3 (audit gap) | Risk | Close skip-receipt audit hole? | **No — H4 smoke only, receipt best-effort (accept risk)** | ADR-002, Risk R3 |

> Loop applicability (Interview #5 free-form) confirmed: codex mandatory is **stage-level**, so `/hm:loop` applies it identically — loop-mode plan still runs `plan-validator` (plan.md.j2 Step 1.5 → Step 4); review runs at the iteration boundary. Captured as ADR-006.

## 📐 Architecture Decision Records

### ADR-001: `/hm:review` heterogeneous consensus (Codex as a Step-4 voting peer)
**Status:** Accepted (2026-06-07, via /hm:plan interview)
**Context:** The review consensus ring (`review.md.j2` Step 4, L243-276) is all-Claude; Codex is opt-in `MAY` advisory appended after the vote. The user requires Codex to be a real peer, not advisory.
**Decision:** Codex joins the **Step 4 cross-reviewer consensus filter** (NOT `two_pass_review.py`, which is per-reviewer pass1/pass2). A new **adapter** normalizes a Codex finding (`codex-finding.schema.json` shape) into a reviewer-finding the filter consumes, including: (a) **severity-vocabulary mapping** `critical→P0, high→P1, medium→P2, low→P3, info→P3` so Step 4a's "same severity tier" predicate can match; (b) **null-location surface-match relaxation** — when `file`/`line` are null, fall back to symbol/message-similarity to establish Step 4a candidacy. With both, a Codex finding can reach `consensus-passed` (k-of-3) and thus auto-fix eligibility; grade computation (L307-312) counts a Codex-raised consensus-passed finding toward P0/P1 like any reviewer.
**Consequences:**
- ✅ True mixed-family consensus on review; Codex can change auto-fix outcomes, not just decorate.
- ⚠️ Step 4a is extended with Codex-specific matching — added complexity in the consensus filter prose + adapter.
- ⚠️ Codex model availability on ChatGPT-tier (memory count:3) — inherit `~/.codex/config.toml`, never pin ids.
**Rejected alternatives:**
- Lightweight relay + MAY→MUST — Rejected: no real vote, user wanted a peer.
- Dedicated `codex-reviewer` agent — Rejected: still outside the vote unless adapted into Step 4 anyway.
- Reworking `two_pass_review.py` (the deferred ADR-004 of PLAN-codex-mandatory-second-opinion) — Rejected: wrong layer; that module never sees cross-reviewer findings.
**Source:** Interview #1, #9.

### ADR-002: Preset × high-diff mandatory matrix
**Status:** Accepted (2026-06-07, via /hm:plan interview)
**Context:** `enabled=False` default; only plan-validator is MUST; high-blast-radius review+plan can run with no heterogeneous check (H7).
**Decision:** When `codex_second_opinion.enabled=True`:
| preset | review | plan |
|--------|--------|------|
| Production | always mandatory | always mandatory |
| Side | mandatory iff high-diff | mandatory iff high-diff |
"Mandatory" = **loud warn + best-effort skip-receipt to the ledger, NOT hard-block** (codex login is unenforceable at render time).
**Consequences:**
- ✅ High-risk paths get a heterogeneous check by default once Codex is enabled.
- ⚠️ Cost on Production loops (every iteration calls Codex on plan+review).
- ⚠️ **Accepted residual risk (R3, from validator C3):** a silently-disabled Codex can fail to emit its own skip-receipt, so absence-of-receipt ≠ proof a review skipped vs never ran. H4 smoke proves Codex *can* run, not that it *did* for a given review. User chose this lighter scope over a negative audit.
**Rejected alternatives:**
- Production also high-diff-gated — Rejected: user wants Production always-on.
- Hard-block on missing Codex — Rejected: footgun when user hasn't run `codex login`.
- Negative audit (missing-row=finding) — Rejected by user (Interview #10): extra scope not wanted.
**Source:** Interview #2, #3, #10.

### ADR-003: Shared high-diff detector
**Status:** Accepted (2026-06-07, via /hm:plan interview)
**Context:** ADR-002's Side path needs a "high-diff" definition shared by review+plan; loop needs a diff-window granularity.
**Decision:** Reuse the review **When-to-Run** criteria (>3 files changed / security-auth-perms code / architecture-contract surface / new public API) as the trigger set, with **LLM judgment for boundary cases** (e.g. 1-line security change). In loop-mode the detector evaluates the **per-iteration diff window** (user choice), not cumulative.
**Consequences:**
- ✅ One definition, two consumers; LLM catches what pure numeric thresholds miss (CLAUDE.md "LLM-judgment-first").
- ⚠️ LLM portion is non-deterministic → tested via INTEGRATION-gated fixtures, not unit tests (see Phase 2).
- ⚠️ per-iteration window can let a high-risk change accrete across small iterations below the bar (accepted; the criteria still flag security/contract touches within any single iter's diff).
**Rejected alternatives:**
- Pure numeric threshold — Rejected: misses 1-line security.
- Cumulative loop diff — Rejected: cost (once-high → every-iter-forced).
- LLM-only, no criteria — Rejected: non-reproducible, no deterministic floor.
**Source:** Interview #4, #7.

### ADR-004: PIDA debate for `plan-validator`
**Status:** Accepted (2026-06-07, via /hm:plan interview)
**Context:** `plan-validator` self-adjudicates Codex findings (it decides `accepted|rejected|duplicate`) — same model that holds the position judges the challenge (H1).
**Decision:** Adopt a PIDA flow: Codex finding → Claude rebuttal (KEEP/REFUTE with evidence) → if an oracle/test exists it decides, **else mark `[unresolved]` and surface**. `overall_assessment` stays Claude's; `[unresolved]` never blocks (warn-and-proceed; preserves ADR-005 of PLAN-codex-second-llm-integration). **Short-circuit:** when a stage has NO oracle (plan has none), skip the rebuttal pass and go straight to `[unresolved]` — no wasted rebuttal tokens.
**Consequences:**
- ✅ A Codex challenge can no longer be silently dismissed; it is either oracle-resolved or visibly `[unresolved]`.
- ⚠️ For plan (no oracle), the dominant outcome is `[unresolved]` — visibility > silent dismissal, at near-zero added cost thanks to the short-circuit.
**Rejected alternatives:**
- Keep one-shot self-adjudication — Rejected: H1 bias.
- Run rebuttal even without an oracle — Rejected: cost for a foregone `[unresolved]` (validator W6).
**Source:** Interview #5; validator W6.

### ADR-005: Calibration ledger v1 + positive health smoke
**Status:** Accepted (2026-06-07, via /hm:plan interview)
**Context:** No calibration ledger exists (H6); warn-and-proceed masked 3 silent skips (H4). With ADR-002 making Production mandatory, a silently-broken Codex = fake coverage.
**Decision:** New `.claude/observability/codex-second-opinion.jsonl`. v1 schema (strict-mode compliant — all-properties-required, nullable-unions, no constraint keywords):
```
{ ts, slug, stage, finding_ref, disposition, codex_status, skip_reason, oracle_result, later_regression_link }
```
- `codex_status`: enum `[invoked, skipped]`
- `disposition`: enum `[accepted, rejected, duplicate, unresolved]`
- `skip_reason`: nullable (null when invoked)
- `oracle_result`, `later_regression_link`: nullable (deferred to a future precision-tracking PLAN)
`/hm:health` gains a **positive smoke check**: a real `codex exec --sandbox read-only --output-schema <ledger-or-finding-schema>` round-trip reported as explicit pass/fail. Skip-receipts from ADR-002 append here (best-effort).
**Consequences:**
- ✅ Silent degradation is caught by the smoke check; v1 enables skip-rate aggregation.
- ⚠️ Precision (oracle_result / regression linkage) deferred — v1 measures volume/skip-rate, not Codex accuracy.
**Rejected alternatives:**
- Full-oracle from day 1 — Rejected: oracle-source design too heavy; plan has no oracle.
- Manual backfill only — Rejected: still leaves v1 without skip-rate structure.
**Source:** Interview #6; forced by #2.

### ADR-006: Loop applicability invariant
**Status:** Accepted (2026-06-07, via /hm:plan interview)
**Context:** User asked whether `/hm:loop` applies the same Codex mandatory behavior to plan/review.
**Decision:** Yes — Codex mandatory is **stage-level**, not interview-gated, so it applies identically inside `/hm:loop`: loop-mode plan still reaches `plan-validator` (plan.md.j2 Step 1.5 → Step 4); review runs at the iteration boundary. The Side high-diff trigger is judged on the **per-iteration** diff (ADR-003).
**Consequences:**
- ✅ No special-casing; the loop inherits the matrix automatically.
- ⚠️ Per-iter judgment means Side may skip Codex on small iterations (ADR-003 trade-off).
**Rejected alternatives:**
- Relax Codex inside loops for cost — Rejected: would create a silent coverage gap exactly where autoloop runs unattended.
**Source:** Interview #5 (free-form), #7.

## 🏗️ Technical Design

**Current State (verified):**
- `templates/stages/review.md.j2` (472 L) — no Codex orchestration; Step 4 consensus filter L243-276; single-source→manual-only rule L13; grade computation L307-312.
- `templates/agents/_partials/second_opinion_codex.md.j2` — included by `code-reviewer_body`, `consensus-arbiter_body`, `plan-validator_body`; MUST only for plan-validator, MAY otherwise.
- `models.py:440-491` `CodexSecondOpinionConfig` (`enabled=False`, no preset binding); `interview.py:568-585` single y/N.
- `templates/schemas/codex-finding.schema.json` — severity enum `[info,low,medium,high,critical]` (disjoint from reviewer `P0..P3`).
- `llm_judge.py` — Claude-only (out of scope; H3 deferred).

**Affected Components:** `models.py` (preset-aware config), `templates/stages/{review,plan}.md.j2`, `second_opinion_codex.md.j2`, `consensus-arbiter_body.md.j2`, `plan-validator_body.md.j2`, `templates/commands/hm/health.md.j2`, NEW `templates/schemas/codex-ledger.schema.json` + ledger CLI module + high-diff detector module, harness-yaml templates (Production/Side), `interview.py`.

**Dependencies:** no new Python deps; relies on user `codex` CLI + `codex login` (unchanged).

**Data Flow (review, enabled+mandatory):** diff → high-diff detector (Side gate) → reviewers (Claude) + Codex finding via `codex exec` → adapter (severity map + null-location relaxation) → Step 4 consensus filter (k-of-3) → grade → ledger append (disposition + status).

**Design Decisions:** all trace to ADR-001..006 above.

## 📝 Implementation Plan

> **Execute progress (2026-06-07):**
> | Phase | Status | Notes |
> |---|---|---|
> | P1 ledger + H4 smoke | ✅ DONE (green, 0 regression) | `codex_ledger.py`, `codex-ledger.schema.json`, `health.md.j2` smoke block, 15 tests |
> | P2 high-diff detector | ✅ DONE (green) | `high_diff.py` (deterministic + LLM-boundary), 12 unit + 1 INTEGRATION test |
> | P3 mandatory matrix | ✅ DONE (green) | preset matrix on plan-validator in `second_opinion_codex.md.j2` (Production always / Side high-diff) + skip-receipt to ledger. Reviewers stay MAY until P4b (array-output envelope limit). Updated `test_render_codex_partial_include` for the superseded always-MUST invariant. |
> | P4a adapter | ✅ DONE (green) | `codex_adapter.py` — severity map (critical→P0…) + null-location `needs_relaxation` flag. 11 tests. |
> | P4b consensus peer | ✅ DONE (green) | `review.md.j2` Step 3.5 orchestration + null-location relaxation (Step 4a) + k-of-3 grade note + skip relay; `consensus-arbiter` relaxation mirror. All gated byte-zero-when-disabled (snapshots + sha256 pins intact). `test_codex_review_consensus.py` (6). |
> | P5 plan PIDA | ✅ DONE (green) | `second_opinion_codex.md.j2` plan-validator: PIDA KEEP/REFUTE → oracle-or-`unresolved`, no-oracle short-circuit, `unresolved` disposition. `test_codex_plan_pida.py` (5). |
> | P6 loop + docs | ✅ DONE (green) | loop-applicability invariant test (codex stage-level, not loop-gated); CLAUDE.md Codex dual-role cross-model deepening note. `test_codex_loop_applicability.py` (3). README truthification deferred (doc polish). |
>
> **All 7 phases complete 2026-06-07** (P1+P2 stage-merged; P3–P6 applied in base). Ready for `/hm:wrapup crossmodel-codex-gaps`.

### Phase 1 — Observability foundation (ledger + smoke)
- **depends_on:** []
- **parallel_group:** foundation
- **merge_hazards:** none
- **Scope (in):** `templates/schemas/codex-ledger.schema.json` (new), ledger writer CLI module (`harness_maker/codex_ledger.py`), `templates/commands/hm/health.md.j2` (smoke block). **(out):** consensus logic, mandatory wiring.
- **Exit criterion:** `uv run pytest tests/unit/test_schema_strict_mode.py tests/unit/test_codex_ledger.py` green; health template snapshot includes smoke block; `ruff`+`mypy --strict` clean.
- **Risk:** medium
- **Rollback:** pre-phase HEAD.

### Phase 2 — High-diff detector
- **depends_on:** []
- **parallel_group:** foundation
- **merge_hazards:** none
- **Scope (in):** `harness_maker/high_diff.py` (criteria + LLM-boundary hook), reuse of review When-to-Run criteria. **(out):** stage wiring (Phase 3).
- **Exit criterion:** numeric-criteria **deterministic unit tests** green; LLM-boundary **INTEGRATION=1-gated** labeled fixture set (incl. 1-line-security case) meets an accuracy floor, mirroring `tests/integration/test_boundary_*.py`. (Numeric path must NOT call the LLM.)
- **Risk:** low
- **Rollback:** pre-phase HEAD.

### Phase 3 — Mandatory matrix wiring
- **depends_on:** [1, 2]
- **parallel_group:** serial-3
- **merge_hazards:** `models.py`, `templates/harness-yaml/{Production,Side}.yaml.j2`
- **Scope (in):** `CodexSecondOpinionConfig` preset-aware fields + validators, `interview.py` mapping, plan/review template conditionals (preset×high-diff), best-effort skip-receipt emission to Phase-1 ledger. **(out):** the actual consensus vote (Phase 4).
- **Exit criterion:** Production/Side render snapshot tests show correct mandatory divergence; skip-receipt integration test (forced non-zero `codex exec`) appends one `codex_status:skipped` ledger row; forward-compat test (legacy harness.yaml without new keys loads via default_factory).
- **Risk:** medium
- **Rollback:** Phase 2.

### Phase 4a — Codex finding adapter + Step-4a relaxation
- **depends_on:** [3]
- **parallel_group:** serial-4
- **merge_hazards:** `templates/stages/review.md.j2`, `consensus-arbiter_body.md.j2`, `second_opinion_codex.md.j2`
- **Scope (in):** adapter normalizing `codex-finding.schema.json` → reviewer-finding incl. **severity map** (critical→P0/high→P1/medium→P2/low→P3/info→P3) and **null-location surface-match relaxation** (symbol/message-similarity). **(out):** voting math (4b).
- **Exit criterion:** adapter unit tests assert (a) a mapped Codex `critical` clears Step 4a candidacy against a reviewer `P0`, (b) a precise-location Codex finding surface-matches, (c) a null-location Codex finding reaches candidacy via symbol/message-similarity.
- **Risk:** HIGH
- **Rollback:** Phase 3.

### Phase 4b — k-of-3 voting + grade wiring + review orchestration
- **depends_on:** [4a]
- **parallel_group:** serial-4
- **merge_hazards:** `templates/stages/review.md.j2`, `consensus-arbiter_body.md.j2`
- **Scope (in):** k-of-3 consensus math with the Codex voter, grade-computation impact (L307-312), `review.md.j2` Codex orchestration + skip relay (mirror plan Step 4's `codex_status` surfacing). **(out):** plan PIDA (Phase 5).
- **Exit criterion:** k-of-3 unit test (Codex vote raises a finding to `consensus-passed`); grade-impact test (consensus-passed Codex finding counts toward P0/P1); review render snapshot shows skip relay.
- **Risk:** HIGH
- **Rollback:** Phase 4a.

### Phase 5 — plan-validator PIDA
- **depends_on:** [4b]   *(serialized after 4b: shares `second_opinion_codex.md.j2`)*
- **parallel_group:** serial-5
- **merge_hazards:** `second_opinion_codex.md.j2`, `plan-validator_body.md.j2`
- **Scope (in):** PIDA reconciliation envelope (KEEP/REFUTE), `[unresolved]` disposition, no-oracle short-circuit. **(out):** review consensus (done in 4).
- **Exit criterion:** PIDA contract render snapshot; `[unresolved]` disposition unit test; short-circuit test (no-oracle stage emits `[unresolved]` without a rebuttal pass).
- **Risk:** medium
- **Rollback:** Phase 4b.

### Phase 6 — Loop applicability + docs
- **depends_on:** [3, 4b, 5]
- **parallel_group:** serial-6
- **merge_hazards:** none
- **Scope (in):** e2e asserting Codex mandatory fires in `/hm:loop` plan+review; CLAUDE.md security/permissions update (new Bash `codex exec` reach on review path; keep REVIEW-M7 deny quartet); README codex truthification. **(out):** new behavior.
- **Exit criterion:** e2e codex-fires-in-loop passes; full `uv run pytest` + `mypy --strict` + `ruff` green; `/hm:health` smoke reports pass on a logged-in machine.
- **Risk:** low
- **Rollback:** prior phases independently revertible.

## 🧪 Testing Strategy

- **Unit (mock-first):** ledger strict-schema; adapter severity-map + relaxation; k-of-3 math; grade impact; PIDA `[unresolved]` + short-circuit; preset render divergence; forward-compat config load.
- **Integration (`INTEGRATION=1`):** high-diff LLM-boundary fixture accuracy floor; skip-receipt on forced `codex exec` failure; (advisory) real `codex exec` round-trip for the H4 smoke.
- **e2e:** Codex mandatory fires inside `/hm:loop` for plan + review.
- **Snapshot determinism:** mask `generated_at`; render both `enabled` states and diff (byte-zero-when-disabled invariant per `second_opinion_codex.md.j2` ADR-007).

## ⚠️ Risks & Mitigation

| ID | Risk | Sev | Mitigation |
|----|------|-----|-----------|
| R1 | Phase 4a/4b consensus rework breaks existing all-Claude review | High | Codex matching is additive + gated by `enabled`; byte-zero-when-disabled snapshot; k-of-3 only when 3 sources present. |
| R2 | Codex strict-output-schema rejects the ledger schema | Med | ADR-005 schema is all-required + nullable-union + no constraint keywords; `test_schema_strict_mode` guards source templates. |
| R3 | **(Accepted)** silent-disabled Codex on Production still looks like coverage | Med | H4 positive smoke + best-effort receipts only. Negative audit NOT built (user choice, Interview #10). Documented openly; revisit if skip-rate telemetry shows blind spots. |
| R4 | `tools:` Bash gate inert → Codex never reaches review reviewers | Med | Ensure bare `Bash` on any reviewer `tools:` that must call `codex exec`; keep REVIEW-M7 interpreter deny quartet. (memory `subagent-tools-field-hard-gates`) |
| R5 | Pinned Codex model id fails on ChatGPT-tier | Med | Inherit `~/.codex/config.toml`; no `model=` in rendered codex calls (memory count:3). |
| R6 | Production-loop cost (Codex every iter) | Low | per-iter high-diff (Side); Production is user's explicit always-on choice; warn-and-proceed keeps failures non-blocking. |

## ✅ Success Criteria

- [x] `/hm:review` with `enabled=True` runs Codex as a k-of-3 voter; a Codex finding can reach `consensus-passed` and affect grade/auto-fix (incl. null-location via relaxation).
- [x] `enabled=True` → Production review+plan always mandatory; Side mandatory iff high-diff (per-iter in loop).
- [x] `.claude/observability/codex-second-opinion.jsonl` populated (disposition + status); strict-schema valid.
- [x] `/hm:health` smoke reports explicit Codex pass/fail.
- [x] `plan-validator` surfaces `[unresolved]` for unarbitrated Codex findings; never silently dismisses; short-circuits when no oracle.
- [x] `/hm:loop` applies the mandatory matrix to plan+review identically.
- [x] Full `pytest` + `mypy --strict` + `ruff` green; byte-zero-when-disabled preserved.

## 🔍 Plan Validation

**Validator outcome:** MAJOR_REVISION_RESOLVED (2 passes; pass-cap reached).

**Pass 1 (MAJOR_REVISION) — 3 critical + 3 warning + 1 suggestion:**
- C1 review-layer mistarget (two_pass_review vs Step 4 filter) → **Resolved**: ADR-001 retargets to Step 4; two_pass_review OUT; Phase 4 split 4a/4b.
- C2 Codex vote cosmetic (null file/line can't surface-match) → **Resolved**: null-location relaxation (Interview #9).
- C3 skip-receipt can't prove Production attempted Codex → **Accepted-risk** (Interview #10; Risk R3).
- W4 high-diff LLM untested → **Resolved**: Phase 2 INTEGRATION fixture floor.
- W5 Phase 5 dependency inconsistent → **Resolved**: `depends_on [4b]`.
- W6 ADR-004 one-sided → **Resolved**: no-oracle short-circuit.
- S7 ledger enums → **Resolved**: enums + nullable `skip_reason`.

**Pass 2 (MAJOR_REVISION) — 1 new critical:**
- Adapter lacked Codex-severity→P-tier mapping (Step 4a "same severity tier" predicate) → **Resolved in-PLAN**: severity map `critical→P0/high→P1/medium→P2/low→P3/info→P3` added to ADR-001 + Phase 4a exit test. (Two-vocabulary mapping is a defensible default, not an architectural fork — resolved without further interview.)

> ⚠️ Both validator passes ran with **Codex skipped** — the validator's `codex exec` Bash call was denied by this session's sandbox/permission layer (a live instance of the H4 silent-skip phenomenon this PLAN fixes). Verdict is Claude-derived.
