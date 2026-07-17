---
type: plan
task_slug: llm-code-review-2026
status: complete
created: 2026-05-11
tags: [harness-maker, plan, review-stage, multi-agent, verifier, agentic-depth, telemetry]
research_doc: "[[RESEARCH-llm-code-review-2026]]"
interview_rounds: 6
adrs: 9
validator_outcome: NEEDS_REVISION_RESOLVED
summary: "Phase A library-only post ADR-008; Phase C verifier-dependent criteria replaced by prompt-only static guards (ADR-009); C2 walltime test eliminated."
---

# PLAN — LLM 코드 리뷰 정밀도 향상 (Verifier + Agentic Depth)

## 🎯 Executive Summary

**What:** Two-step upgrade to `/hm:review`:
1. **Phase A (0.10.0)** — Insert a **verifier sub-role at Pass 1.5** (between bug-find Pass 1 and contextual Pass 2) that reduces findings to those with verified reasoning chains. Adds built-in JSONL telemetry to `.claude/observability/review-{date}.jsonl` with labeled-fixture mode for automated WRONG-criterion verification.
2. **Phase C (0.11.0)** — Rewrite reviewer prompts to enable **agentic depth-on-demand** (investigate every suspicious pattern, use Read/Grep/git log dynamically). Determinism for reviewer outputs explicitly abandoned (ADR-003); structural tests replace snapshots on affected paths (ADR-005).

**Why:** RESEARCH-llm-code-review-2026 surfaced three 2026 SOTA deltas. A (verifier) has lowest risk + highest cited ROI (Anthropic <1% incorrect findings). C (agentic depth) is the second-largest delta (Cursor 0.4→0.7 bugs/run, 52%→70% resolution). B (repo-graph) deferred — FP 5.5x amplification risk too high without dedicated FP-management plan.

**Key decisions (ADR links):**
- Scope = A + C only; B deferred ([ADR-001](#adr-001))
- Verifier at Pass 1.5, redacted context ([ADR-002](#adr-002))
- Agentic depth via prompt-only framing, no token/tool cap ([ADR-003](#adr-003))
- Split release: A=0.10.0, C=0.11.0 ([ADR-004](#adr-004))
- Reviewer-output paths skip snapshot, use structural+labeled-fixture tests ([ADR-005](#adr-005))
- Built-in JSONL telemetry + labeled-fixture fields ([ADR-006](#adr-006))
- Cost variance intentionally unbounded; only wall-time tracked ([ADR-007](#adr-007))
- Anthropic-API-dependent verifier surface stripped post-0.10.0; wall-time baseline (A7) discarded ([ADR-008](#adr-008))
- Phase C verifier-dependent acceptance criteria replaced by prompt-only static guards; C2 (walltime CI test) eliminated ([ADR-009](#adr-009))

**Estimated impact:** Phase A complete in 0.10.0 (post ADR-008 strip leaves a library surface). Phase C ~3 days: 5 reviewer prompt rewrites + 1 grep-audit structural test + 0.11.0 ship.

## 📐 ADR-008 — API-dependent verifier surface stripped; A7 discarded (2026-05-11)

**Status:** Accepted (2026-05-11, post-0.10.0)

**Context:** 0.10.0 shipped Phase A with `AnthropicVerifierClient` (Anthropic SDK call), the `verify` CLI subcommand, the Pass 1.5 step in `templates/stages/review.md.j2`, and Phase A7 (wall-time baseline capture). The target environment for `/hm:review` is Claude Code as a subscription tool — no `ANTHROPIC_API_KEY` available to the harness's subprocess CLIs. Every real `/hm:review` invocation since ship has hit the `model_unavailable` fallback, meaning the verifier never actually ran. Wall-time measurement was specified as Phase A7 work but cannot be auto-tested in CI from the same env constraint.

**Decision:**
1. Strip the Anthropic-API surface from `two_pass_review.py`: remove `AnthropicVerifierClient`, `ModelUnavailableError`, and the `verify` CLI subcommand.
2. Remove the Pass 1.5 step from the review stage template; Pass 1 → Pass 2 directly. Replace the step with a deferral note pointing here.
3. Keep `verify_findings()` + `VerifierClient` Protocol as a library surface; callers supplying a custom client retain access to the reduce-only algorithm.
4. Keep the `code-verifier` agent definition as the role contract.
5. Discard Phase A7 entirely. Wall-time measurement, if/when needed, is manual and out-of-band. No auto-test, no baseline fixture.
6. Remove API-dependent tests (`test_verify_falls_back_on_model_unavailable`, `test_verify_cli_*`) and the structural wiring test (`tests/structural/test_review_stage_verifier_wiring.py`).

**Consequences:**
- ✅ The review pipeline no longer references a code path that always fails in the target env. Stage template prose is honest about what runs.
- ✅ Reduce-only verifier algorithm + agent contract preserved for future plug-ins (Claude Code Task-tool client, external service, etc.).
- ⚠️ ADR-002's verifier-precision invariant (verifier >5% incorrect findings ⇒ WRONG-criterion) becomes unenforceable until a callable client lands. C-phase's wall-time-3x WRONG-criterion (ADR-007) likewise becomes unenforceable.
- ⚠️ Telemetry JSONL records keep their schema (15 fields including `verifier_*` counts + `wall_time_ms`) but those fields are populated by the orchestrator manually, not by the auto-invoked CLI step.

**Rejected alternatives:**
- *Full revert of Phase A (git revert 943a7f4)*: throws out the structural improvements (build_pass2_prompt diff arg fix, fence-escape pattern, JSONL telemetry, snapshot exclusion mechanism) that stand on their own value.
- *Mock-mode verifier shipped by default*: a hardcoded `kept = input` would masquerade as functionality; the user explicitly preferred no fake/no-op verifier over a real-looking stub.
- *In-Claude-Code Task-tool verifier client*: out of scope here; revisit if/when a Task() invocation from the stage prompt is acceptable as the verifier-client implementation.

**Source:** Direct user direction post-release-0-10-0 review cycle.

## 📐 ADR-009 — Phase C verifier-dependent validation replaced by prompt-only static guards (2026-05-11)

**Status:** Accepted (2026-05-11, via /hm:plan Interview Round 6)

**Context:** ADR-008 stripped the auto-invoked verifier and the wall-time baseline (A7). 3 of the original 7 Phase C acceptance criteria assumed the verifier ran in the pipeline AND that a `walltime_baseline_0_10_0.json` fixture existed:
1. `test_pass2_no_reintroduction.py` — Pass 2 output `⊆` verifier-kept set on adversarial fixture.
2. `test_review_walltime.py` (Phase C2) — `current_p50 ≤ 3.0 × baseline_p50` integration test.
3. Labeled-fixture mode — `verifier_false_drop_n / verifier_false_keep_n` `incorrect_rate < 0.05` over 10 entries.

None of the 3 can be auto-tested in the target env (no API key → no verifier auto-invocation → no false-drop/false-keep stats → no walltime baseline).

**Decision:**
1. Replace `test_pass2_no_reintroduction` with **`test_reviewer_prompts_contain_agentic_depth_clauses`** — a grep-based structural test asserting each of the 5 reviewer prompts contains the exact substrings below. Mechanical, deterministic, no LLM in the loop.

   **Required substring contract — LOCKED at PLAN time** (each reviewer body MUST contain EVERY listed substring as a verbatim case-sensitive match; the test fails if any one is missing):

   | Reviewer | Required substrings |
   |----------|---------------------|
   | `code-reviewer.md` | `Read changed files end-to-end`, `Grep to confirm before flagging`, `git log for prior intent`, `trace runtime path` |
   | `security-reviewer.md` | `Read changed files end-to-end`, `Grep to confirm before flagging`, `git log for prior intent`, `Grep for related sinks` |
   | `performance-reviewer.md` | `Read changed files end-to-end`, `Grep to confirm before flagging`, `git log for prior intent`, `Grep for hot-path callers` |
   | `concurrency-reviewer.md` | `Read changed files end-to-end`, `Grep to confirm before flagging`, `git log for prior intent`, `Grep for lock acquisitions` |
   | `ux-reviewer.md` | `Read changed files end-to-end`, `Grep to confirm before flagging`, `git log for prior intent`, `Grep for related accessibility patterns` |

   Rationale: the first 3 substrings are the common agentic-depth floor (full-context Read + verify-via-Grep + check-prior-intent-via-git-log) — they MUST appear verbatim in every reviewer body. The 4th substring is reviewer-specific to verify the agentic depth is *meaningfully* customized for the reviewer's domain (not just the same generic instruction pasted into 5 files). Substrings are locked here so /hm:execute does not face an interview round mid-implementation.
2. **Drop** the wall-time cost ceiling entirely. Wall-time is manual / out-of-band per ADR-008. No `tests/structural/test_review_walltime.py`, no `walltime_baseline_*.json` fixture.
3. **Drop** the labeled-fixture `incorrect_rate` precision/recall measurement entirely. Without auto-invocation, the `verifier_false_*` counters never get populated. Precision/recall regression is now catchable only through manual `/hm:review` inspection on real PRs.
4. **Eliminate Phase C2** (was: walltime regression test). Phase C becomes 2 sub-phases: C1 (reviewer prompt rewrite + new grep-audit static guards) and C2 (0.11.0 ship — was C3).
   - *Considered and rejected*: repurpose old C2 as a separate "static-guard test consolidation" phase. Rejected because rewriting the 5 reviewer prompts AND adding the test that audits them are not separable work — they belong in the same PR cycle (the test is meaningless without the rewritten prompts, and the rewritten prompts have no static signal without the test).

**Consequences:**
- ✅ Phase C is executable in the target env. No LLM dependency for CI gating.
- ✅ Reviewer prompt drift remains statically detectable via the grep-audit clauses.
- ✅ Smaller blast radius — 2 sub-phases instead of 3; one less integration test to maintain.
- ⚠️ Quality regression (more false positives from agentic depth) is no longer auto-detectable. Catch path is now: manual review of `/hm:review` output on real PRs + the orchestrator consensus filter.
- ⚠️ Cost regression (slower reviews from agentic tool use) has no auto-floor. User discretion only.
- ⚠️ The agentic-depth rewrite ships without a precision/recall safety net — the cost-of-being-wrong is bounded by the existing P0/P1-only grade gate (P2/P3 false positives don't lower grade).

**Rejected alternatives:**
- **Keyword-density audit** (count Read/Grep/git log occurrences) — rejected because it doesn't pin specific instruction content; could pass with prompts that mention the tools but don't actually instruct depth.
- **Section-presence audit** (only checks heading shape) — rejected: too lenient, doesn't verify the agentic-depth wording.
- **LLM-judge audit at PR time** — rejected: requires the same API access that ADR-008 declared unavailable.
- **Quarterly manual audit only** — rejected: defers the regression catch entirely and provides no structural signal at PR-merge time.

**Source:** Interview Round 6 (post-ADR-008 plan revision).

## 📚 Prior Work

- **[[RESEARCH-llm-code-review-2026]]** — Source research; recommended A+B+C, PLAN scopes to A+C.
- **Current `/hm:review` already implements:** two-pass redaction (Phase 0 ablation +47pp precision), OBSERVE→INFER→CONCLUDE reasoning chain, surface+reasoning consensus filter, P0/P1-only grade gate, auto-fix loop with revert-on-failure. Verifier is incremental on top of this strong base.
- **failures.md [fail:review] reviewer-subagent-model-unsupported (2026-05-11):** verifier MUST have a model-unavailable fallback path; integration + unit test both required (ADR-006 fallback contract).
- **failures.md [fail:review] abbreviated-diff-causes-reviewer-false-positives (2026-05-10):** verifier MUST receive full Pass 1 finding records, never abbreviation.
- **failures.md [fail:test] snapshot-regen-inside-worktree (3 recurrences):** every rollback path involving template change MUST finalize the worktree before regen — applied to A3/A6/A7/C1 rollback playbook.

## 🎙️ Interview Transcript

| # | Round | Topic | Cat | Question | Choice | → ADR |
|---|-------|-------|-----|----------|--------|-------|
| 1 | 1 | Approach scope | Scope | Which approaches to cover | **A + C** (B deferred) | ADR-001 |
| 2 | 2 | Verifier slot | Architecture | Where to insert verifier | **Pass 1.5** (redacted) | ADR-002 |
| 3 | 2 | Depth guardrail | Architecture | Constraint shape for C | **Prompt-only**, no hard cap | ADR-003 |
| 4 | 3 | WRONG-criteria | Testing | What makes shipped wrong | verifier>5% incorrect; wall-time 3x; silent build break | ADR-005 |
| 5 | 3 | Snapshot strategy | Testing | Non-deterministic reviewer testing | **Skip snapshot** + structural tests | ADR-005 |
| 6 | 3 | Phasing | Phasing | Single vs split | **Split**: A=0.10.0, C=0.11.0 | ADR-004 |
| 7 | 4 | Telemetry | Observability | Implementation form | **Built-in JSONL** in `.claude/observability/` | ADR-006 |
| 8 | 5 (validator follow-up) | Baseline-capture phase | Phasing | A7 vs extend A6 vs C2-self | **New Phase A7** | (phase change, no new ADR) |
| 9 | 5 | Wrong-1 measure | Testing | Labeled-fixture mode vs downgrade criterion | **Labeled-fixture + new fields** | extends ADR-005 / ADR-006 |
| 10 | 5 | Cost ADR | Risk | Cost ADR vs circuit breaker | **ADR-007** (intent recorded) | ADR-007 |
| 11 | 6 | Pass-2 guard replacement | Testing | Form of static guard post-ADR-008 | **Grep-based prompt clause audit** | ADR-009 |
| 12 | 6 | Cost ceiling replacement | Testing | Wall-time check post-A7-discard | **Drop entirely** — manual on-demand | ADR-009 |
| 13 | 6 | Precision guard replacement | Testing | incorrect_rate replacement | **Drop entirely** | ADR-009 |
| 14 | 6 | Phase C sub-phase shape | Phasing | What happens to C2 | **Eliminate C2 entirely**; C3 → C2 | ADR-009 |

**Rounds:** 6 (4 original + 1 validator follow-up + 1 post-ADR-008 revision). **Layer-3 PASS streak at convergence:** Round 6 single-round PASS (1.0 / 1.0 / 1.0) — accepted given narrow-revision scope.

## 📐 Architecture Decision Records

### ADR-001: Scope = A (verifier) + C (agentic depth); B (repo-graph) deferred
**Status:** Accepted (2026-05-11, via /hm:plan interview)
**Context:** RESEARCH surfaced three approaches (A/B/C) with distinct ROI/risk profiles. B (repo-graph context) has highest implementation effort (~1-2 weeks) and well-documented 5.5x FP-rate amplification (Greptile data: 11 FP vs CodeRabbit 2).
**Decision:** PLAN covers A and C only. B becomes a separate future-PLAN candidate when FP-management story is mature enough to absorb 5x amplification.
**Consequences:**
- ✅ Tractable single-PLAN scope (~10 files total, 2 ship cycles).
- ✅ Lower FP risk — A reduces FP, C amplifies but no graph-induced surge.
- ⚠️ Catch-rate uplift smaller than full A+B+C combo (no ripple-effect findings).
**Rejected alternatives:**
- "A only" — too narrow, leaves Cursor's +75% bugs/run gain on the table.
- "All three (A+B+C)" — 8-10 phases per PLAN unmanageable; single PR diff too large to review.
**Source:** Interview #1.

### ADR-002: Verifier inserted at Pass 1.5 (between Pass 1 and Pass 2), redacted context
**Status:** Accepted (2026-05-11)
**Context:** Existing `two_pass_review` CLI has `redact` (Pass 1 input) and `merge` (Pass 2 output). Anchoring vulnerability is upstream — verifier must see redacted context to preserve Phase 0 ablation's +47pp precision.
**Decision:** Add `verify` subcommand to `src/harness_maker/two_pass_review.py`. Review stage invokes verifier between Pass 1 parallel reviewer call and Pass 2 reviewer re-invocation. Verifier receives `{pass1_findings, pass1_context (redacted)}`, emits `{kept, dropped, stats}`. Verifier role: **reduce-only** — strict subset of input findings, MAY drop or demote severity, MUST NOT introduce new findings.
**Consequences:**
- ✅ Anti-anchoring preserved (verifier sees redacted same as Pass 1).
- ✅ Pipeline determinism for verifier step (single instance, not parallel, no agentic loop in A).
- ✅ Clean partition with Pass 2 (verifier=reduce, Pass 2=context-restore).
- ⚠️ ~30% token cost increase per review session.
**Rejected alternatives:**
- "Final filter" (after Pass 2) — anchoring already happened, too late.
- "Reviewer-internal self-critique" — confirmation bias unresolved per RESEARCH.
**Source:** Interview #2a.

### ADR-003: Agentic depth via prompt-only framing; no token/tool-call cap
**Status:** Accepted (2026-05-11)
**Context:** Cursor BugBot's pipeline→agentic transition (0.4→0.7 bugs/run, 52%→70% resolution rate) used aggressive prompts without explicit hard caps. Cursor blog: "small changes in tool design or availability had an outsized impact on outcomes."
**Decision:** Phase C rewrites reviewer prompts to include: *"investigate every suspicious pattern; use Read/Grep/git log as needed; budget your own token use."* No token cap, no tool-call cap.
**Consequences:**
- ✅ Maximum exploration depth at suspicious sites.
- ✅ Implementation simplicity (prompt change only, no runtime accounting).
- ⚠️ Determinism for reviewer outputs completely abandoned (ADR-005 follows).
- ⚠️ Wall-time and cost variance high → wall-time-only ceiling tracked (ADR-007).
**Rejected alternatives:**
- "Token budget per reviewer" — suppresses exploration precisely when most valuable.
- "Max tool-call count" — arbitrary number; breaks long-tail investigation.
- "Hybrid" — over-engineered; prompt-only is the simplest defensible form.
**Source:** Interview #2b.

### ADR-004: Split release — A ships as 0.10.0, C ships as 0.11.0
**Status:** Accepted (2026-05-11)
**Context:** A is dedup-only / determinism-preserving / low-risk. C is prompt-overhaul / determinism-abandoning / cost-variable. Bundling collapses ability to attribute telemetry regressions to A vs C.
**Decision:** A completes and ships as 0.10.0 with full telemetry. Dedicated Phase A7 captures wall_time baseline on a fixed fixture (p50/p95) committed as `tests/fixtures/walltime_baseline_0_10_0.json`. C ships as 0.11.0 with wall-time assertions against that baseline.
**Consequences:**
- ✅ Telemetry baseline isolation — wall-time delta attribution unambiguous.
- ✅ Smaller per-ship diff, easier review.
- ⚠️ Two release cycles (~1 week longer total than bundled).
**Rejected alternatives:**
- "Bundled single PR" — telemetry confounded.
- "Two separate PLANs" — interview redundancy, ADR duplication.
**Source:** Interview #3c + Interview #8 (Round 5 follow-up — Phase A7 added).

### ADR-005: Reviewer-output paths use structural + labeled-fixture tests; snapshot tests excluded
**Status:** Accepted (2026-05-11)
**Context:** ADR-003 abandons determinism for reviewer outputs. Snapshot tests on reviewer paths would flake or require constant regeneration. Validator critique #3 raised that WRONG-criterion #1 (verifier-incorrect <5%) needs ground-truth labels — pure structural tests are insufficient.
**Decision:** (1) Add `tests/snapshot/EXCLUSIONS.md` listing reviewer-output paths; `tests/snapshot/regenerate.py` reads exclusions. (2) Add structural test `tests/structural/test_reviewer_outputs.py` asserting finding-schema validity, telemetry-schema validity, and verifier behavior on adversarial fixtures. (3) Add **labeled-fixture mode** — `harness.yaml.review.adversarial_fixture: <path>` enables ground-truth labels; structural test computes incorrect-rate from labeled runs.
**Consequences:**
- ✅ Tests stay reliable across non-deterministic reviewer behavior.
- ✅ WRONG-criterion #1 measurable from telemetry.
- ⚠️ Coverage on output text correctness reduced; reliance on structural invariants + labeled fixtures only.
- ⚠️ Labeled fixture must be maintained as adversarial cases evolve.
**Rejected alternatives:**
- "Mock LLM fixed output" — snapshot of mock, not of real behavior (false security).
- "Statistical equivalence" — flaky CI, debugging nightmare.
- "Downgrade WRONG-1 to quarterly manual" — gives up automated regression detection on the headline criterion.
**Source:** Interview #3a, #3b, #9.

### ADR-006: Built-in JSONL telemetry at `.claude/observability/review-{date}.jsonl` with labeled-fixture extension
**Status:** Accepted (2026-05-11)
**Context:** Three WRONG-criteria all require automated measurement. `.claude/observability/` already exists in harness layout (per CLAUDE.md 100% local telemetry rule).
**Decision:** Every `/hm:review` invocation appends one JSONL line via atomic_write (tempfile + os.replace) to `.claude/observability/review-{YYYY-MM-DD}.jsonl`. Concurrent writers (multi-worktree autoloop + Cursor) safely serialize via atomic replace.

**Schema (13 fields):**
```json
{
  "ts": "2026-05-11T14:23:45Z",
  "slug": "task-slug",
  "round": 1,
  "pass1_n": 12,
  "verifier_kept_n": 9,
  "verifier_dropped_n": 3,
  "verifier_false_drop_n": 0,   // labeled-fixture only; else null
  "verifier_false_keep_n": 1,   // labeled-fixture only; else null
  "fixture_label": "adv-fix-001", // null on real runs
  "pass2_kept_n": 7,
  "consensus_passed_n": 5,
  "wall_time_ms": 18432,
  "build_break_count": 0,
  "auto_fix_reverted_n": 0
}
```

**Fallback contract:** If verifier model is unavailable (failures.md 2026-05-11), telemetry record has `verifier_kept_n = pass1_n` and a `fallback: "model_unavailable"` field; processing proceeds Pass 1→Pass 2 directly.
**Consequences:**
- ✅ Automatic WRONG-criteria verification with labeled-fixture mode.
- ✅ 100% local, no external transmission (CLAUDE.md rule).
- ✅ Concurrent-safe via atomic_write.
- ⚠️ Disk growth unbounded long-term — daily rotation, manual cleanup documented in CLAUDE.md.
**Rejected alternatives:**
- "Opt-in" — defeats automatic regression detection.
- "Out-of-scope" — WRONG-criteria become unfalsifiable.
**Source:** Interview #4, #9.

### ADR-007: Cost variance is intentionally unbounded; wall-time is the only enforced ceiling
**Status:** Accepted (2026-05-11); **partially superseded by ADR-009 (2026-05-11)** — the wall-time ceiling enforcement is removed (no auto-test, no baseline). Cost-variance intent (intentionally unbounded) survives; the *enforced* ceiling does not. See ADR-009 Decision #2.
**Context:** ADR-003 selected prompt-only depth, giving up cost-budget controls. Without an explicit decision record, downstream triage of cost incidents would lack policy guidance.
**Decision (as accepted 2026-05-11):** Token cost and tool-call count are intentionally unbounded. The only enforced ceiling was `wall_time_ms ≤ 3.0 × baseline_p50` (originally asserted in old Phase C2 — now eliminated per ADR-009). User-side cost ceilings (Anthropic subscription quotas, Codex billing) are out of scope for this PLAN.
**Consequences (post-ADR-009 amendment):**
- ✅ Decision recorded for future triage ("yes, the 10x cost spike is by design").
- ⚠️ The `3x wall-time ceiling` is no longer enforced anywhere in CI; pathological diffs can cause user-visible cost spikes with no auto-floor.
- ⚠️ Rollback path (revert to 0.10.0 = pre-agentic) remains the only mitigation; manual sanity check at new C2 (0.11.0 ship).
**Rejected alternatives:**
- "Hard token budget" — collapses to ADR-003 alternative (suppresses exploration).
- "Hard wall-time circuit breaker" — adds significant complexity (interrupt agent loop mid-investigation); deferred to a future ADR if observed cost incidents warrant.
**Source:** Interview #10. Amended via ADR-009 (Interview #12 dropped the wall-time ceiling enforcement).

## 🏗️ Technical Design

### Current State
- `src/harness_maker/templates/stages/review.md.j2` — Step 3 runs Pass 1 (redacted, parallel) → Pass 2 (full context) → consensus filter.
- `src/harness_maker/two_pass_review.py` — CLI with `redact`, `merge` subcommands.
- `src/harness_maker/templates/agents/*.md` — code/security/perf/concurrency/ux reviewers (read-only).
- `.claude/observability/` — exists but no review-telemetry emitter yet.
- `tests/snapshot/` — body_sha256 comparison; no exclusion mechanism.

### Affected Components

**Phase A (0.10.0):**
| Path | Action | Why |
|------|--------|-----|
| `src/harness_maker/templates/agents/code-verifier.md` | NEW | Verifier role (read-only, reduce-only prompt) |
| `src/harness_maker/two_pass_review.py` | MOD | Add `verify` subcommand |
| `src/harness_maker/templates/stages/review.md.j2` | MOD | Insert verifier call at Pass 1.5; prompt invariants for Pass 2 |
| `src/harness_maker/review_telemetry.py` | NEW | JSONL emitter via atomic_write |
| `tests/snapshot/EXCLUSIONS.md` | NEW | List reviewer-output paths excluded from snapshot |
| `tests/snapshot/regenerate.py` | MOD | Honor exclusion list |
| `tests/structural/test_verifier_agent.py` | NEW | Verifier-agent permissions + invariant |
| `tests/structural/test_reviewer_outputs.py` | NEW | Schema + verifier-drop on adversarial fixture |
| `tests/structural/test_telemetry_no_leak.py` | NEW | Grep-based lint: no `wall_time_ms` interpolation in `*.j2` except behind frozen filter |
| `tests/structural/test_snapshot_exclusions_effective.py` | NEW | Asserts exclusion mechanism actually filters |
| `tests/structural/test_review_walltime.py` | NEW (Phase C2) | Asserts current run ≤ 3x baseline_p50 |
| `tests/unit/test_two_pass_review.py` | MOD | Cover verify subcommand + model-unavailable fallback |
| `tests/unit/test_review_telemetry.py` | NEW | atomic_write, schema |
| `tests/fixtures/adversarial_findings.json` | NEW | Labeled fixture: 3 known-spurious + 2 known-real findings |
| `tests/fixtures/walltime_baseline_0_10_0.json` | NEW (Phase A7) | p50/p95 baseline at 0.10.0 |
| 5 version-sync files | MOD (Phase A6) | 0.10.0 bump |

**Phase C (0.11.0):**
| Path | Action | Why |
|------|--------|-----|
| `src/harness_maker/templates/agents/{code,security,performance,concurrency,ux}-reviewer.md` | MOD | Prompt rewrite for agentic loop (ADR-003 wording); Pass 2 invariants |
| `src/harness_maker/templates/stages/review.md.j2` | MOD | Step 3 wording for agentic affordance |
| 5 version-sync files | MOD (Phase C3) | 0.11.0 bump |

### Data Flow (post Phase A)

```
git diff
   ↓
Pass 1 reviewers (parallel, REDACTED context)
   ↓
{pass1_findings}                  ← logged: pass1_n
   ↓
VERIFIER (single, REDACTED, reduce-only)
   ↓
{kept ⊆ pass1_findings, dropped}  ← logged: verifier_kept_n / verifier_dropped_n
   ↓                                (+ false_drop/false_keep if fixture_label set)
Pass 2 reviewers (FULL context, must NOT re-introduce dropped findings)
   ↓
{merged}                          ← logged: pass2_kept_n
   ↓
consensus filter (surface + reasoning alignment)
   ↓
{consensus_passed, weak, manual}  ← logged: consensus_passed_n
   ↓
grade gate → auto-fix (with revert)  ← logged: build_break_count / auto_fix_reverted_n
   ↓
telemetry emit (atomic_write JSONL)  ← logged: wall_time_ms total
```

### API Changes

**`python -m harness_maker.two_pass_review verify`** (new subcommand):
- **stdin (JSON):** `{pass1_findings: [...], pass1_context: {...}, fixture_label?: str}`
- **stdout (JSON):** `{kept: [...], dropped: [{finding, reason}], stats: {input_n, kept_n, dropped_n, false_drop_n?, false_keep_n?}}`
- **Invariant:** `set(kept ∪ dropped.finding) == set(pass1_findings)` (no introduction).
- **Fallback:** On model-unavailable exception, returns `{kept: pass1_findings, dropped: [], stats: {…, fallback: "model_unavailable"}}` + logs warning.

**`python -m harness_maker.review_telemetry emit`** (new module):
- **stdin (JSON):** telemetry record (13-field schema per ADR-006).
- **Effect:** atomic_write append to `.claude/observability/review-{YYYY-MM-DD}.jsonl`.
- **Concurrent safety:** atomic_write via tempfile + os.replace prevents PIPE_BUF interleaving.

### Design Decisions Bound to ADRs

- Single verifier instance, not parallel → ADR-002 (reduce-only role).
- Verifier sees redacted context → ADR-002 (anti-anchoring preserved).
- Verifier MUST NOT introduce findings → ADR-002 invariant; enforced by Phase A1 structural test.
- Pass 2 MUST NOT re-evaluate verifier-dropped findings → ADR-002 invariant; enforced by Phase C1 structural test.
- Reviewer model-unavailable fallback path → failures.md 2026-05-11 guard; unit + integration test (Phase A2).
- Prompt-only depth, no caps → ADR-003.
- atomic_write for telemetry → CLAUDE.md §Atomic file write rule + ADR-006 concurrent-safety contract.
- Telemetry numeric fields never interpolated into rendered templates → ADR-005 determinism-leakage prevention; enforced by `test_telemetry_no_leak.py`.

## 📝 Implementation Plan

### Phase A — Verifier Sub-Role (ships as 0.10.0)

#### Phase A status (2026-05-11, /hm:execute -- PHASE A run)

| Phase | Status | Tests added | Tests passing |
|-------|--------|-------------|---------------|
| A1 | **done** | `tests/structural/test_verifier_agent.py` (4) | 4/4 |
| A2 | **done** | `tests/unit/test_two_pass_verify.py` (8) | 8/8 |
| A3 | **done** | `tests/structural/test_review_stage_verifier_wiring.py` (5) | 5/5 |
| A4 | **done** | `tests/unit/test_review_telemetry.py` (11) | 11/11 |
| A5 | **done** | `tests/structural/{test_snapshot_exclusions_effective,test_telemetry_no_leak,test_reviewer_outputs}.py` (12) | 12/12 |
| A6 | **blocked — user step** | Awaiting merge to main + snapshot regen + version bump | — |
| A7 | **blocked — user step** | Awaiting v0.10.0 tag + 5 real /hm:review runs | — |

**A1-A5 verification (from worktree `.worktrees/execute-20260511T1119Z`):**
- 207 tests pass on the A1-A5 surface (`pytest tests/structural/ tests/unit/test_two_pass_verify.py tests/unit/test_review_telemetry.py tests/unit/test_2pass_review.py tests/unit/test_codex_phase6.py tests/unit/test_codex_phase7.py tests/unit/test_synthesize.py`).
- Full pytest (sans snapshots) passes with exit code 0 (`tests/unit/test_synthesize_snapshot.py` excluded — see A6 blocker below).
- `uv run ruff check src/ tests/` → All checks passed.
- `uv run mypy --strict` on new modules (`review_telemetry.py`, `two_pass_review.py`, `synthesize.py`) → no issues.

**A6 blocker (snapshot regen):** Adding `code-verifier` to `_ALL_AGENTS` produces 2 new files per fixture (1 CC `.md` + 1 Codex `.toml`). All 8 `tests/unit/test_synthesize_snapshot.py::test_snapshot_matches[*]` cases fail with `len(filtered) == 60 != expected 59` until the user runs `uv run python tests/snapshot/regenerate.py` **from the main repo root** (not the worktree — failures.md fail:test snapshot-regen-inside-worktree). This step is intentionally manual because regen from a worktree embeds worktree paths into file hashes.

**A7 blocker:** Requires `git tag v0.10.0` first, then 5 runs of `/hm:review` against a representative-diff fixture to compute `walltime_baseline_0_10_0.json`. Cannot be performed inside an `/hm:execute` invocation — the v0.10.0 binary must be installed and `/hm:review` must hit a real LLM. User-orchestrated post-merge step.

**Files changed this run (staged on worktree branch, NOT committed):**

| Path | Action |
|------|--------|
| `src/harness_maker/templates/agents/code-verifier.md.j2` | NEW (wrapper) |
| `src/harness_maker/templates/agents/code-verifier_body.md.j2` | NEW (prompt body) |
| `src/harness_maker/synthesize.py` | MOD (added code-verifier to `_ALL_AGENTS` + `_CODEX_AGENT_META`) |
| `src/harness_maker/two_pass_review.py` | MOD (added `verify` subcommand, `verify_findings()`, `VerifierClient`, `AnthropicVerifierClient`, `ModelUnavailableError`) |
| `src/harness_maker/review_telemetry.py` | NEW (atomic-JSONL emitter, 14-field schema, CLI) |
| `src/harness_maker/templates/stages/review.md.j2` | MOD (Pass 1.5 verifier sub-step + Pass-2 invariant + telemetry emit section) |
| `tests/structural/__init__.py` | NEW |
| `tests/structural/test_verifier_agent.py` | NEW (A1) |
| `tests/structural/test_review_stage_verifier_wiring.py` | NEW (A3) |
| `tests/structural/test_snapshot_exclusions_effective.py` | NEW (A5) |
| `tests/structural/test_telemetry_no_leak.py` | NEW (A5) |
| `tests/structural/test_reviewer_outputs.py` | NEW (A5) |
| `tests/unit/test_two_pass_verify.py` | NEW (A2) |
| `tests/unit/test_review_telemetry.py` | NEW (A4) |
| `tests/snapshot/EXCLUSIONS.md` | NEW (A5 — empty list, mechanism only) |
| `tests/snapshot/regenerate.py` | MOD (reads EXCLUSIONS.md) |
| `tests/unit/test_synthesize_snapshot.py` | MOD (filters via EXCLUSIONS.md) |
| `tests/unit/test_codex_phase6.py` | MOD (bumped agent-count assertion to derive from `_ALL_AGENTS`) |
| `tests/unit/test_synthesize.py` | MOD (comment update) |
| `tests/fixtures/adversarial_findings.json` | NEW (5-finding labeled fixture) |

---

#### Phase A1: Verifier agent definition + permission/invariant tests
- **Scope (in):** `src/harness_maker/templates/agents/code-verifier.md` (new); `tests/structural/test_verifier_agent.py` (new).
- **Scope (out):** `two_pass_review.py`, `review.md.j2`, prompts of other reviewers.
- **Exit criterion:**
  ```bash
  uv run pytest tests/structural/test_verifier_agent.py -v
  ```
  Test asserts: (a) rendered agent file has `permissions.deny` including `Write(*)`, `Edit(*)`, and Bash interpreter denies (`python`, `node`, `sh`, `bash`, `eval *`); (b) prompt body contains the invariant phrase "MUST NOT introduce findings"; (c) frontmatter `content_hash` present.
- **Risk:** low (single new file).
- **Rollback point:** revert this commit; no prior phase touched.

#### Phase A2: `two_pass_review verify` subcommand + model-fallback unit test
- **Scope (in):** `src/harness_maker/two_pass_review.py` MOD (add `verify` subcmd); `tests/unit/test_two_pass_review.py` MOD.
- **Scope (out):** stage template, telemetry emitter, agents.
- **Exit criterion:**
  ```bash
  uv run pytest tests/unit/test_two_pass_review.py -v
  ```
  Tests required:
  - `test_verify_drops_unverified_inference` — adversarial fixture, expects ≥1 drop.
  - `test_verify_handles_empty_findings` — input `[]` → output `kept=[], dropped=[]`.
  - `test_verify_preserves_kept_finding_fields` — schema parity.
  - `test_verify_invariant_no_introduction` — `set(kept ∪ dropped) == set(input)`.
  - `test_verify_falls_back_on_model_unavailable` — `mock_anthropic_client` raises model-unavailable → returns `kept=input, fallback="model_unavailable"` + warning logged.
- **Risk:** low (additive subcommand).
- **Rollback point:** revert this commit; A1 retained.

#### Phase A3: Review stage wiring + Pass-2 prompt invariant
- **Scope (in):** `src/harness_maker/templates/stages/review.md.j2` MOD (insert verifier call at Pass 1.5; Pass 2 prompt adds "MUST NOT re-evaluate verifier-dropped findings").
- **Scope (out):** agent files (Phase A1, Phase C1), CLI (Phase A2).
- **Exit criterion:**
  ```bash
  uv run pytest tests/snapshot/test_synthesize_snapshot.py  # regen + pass
  uv run pytest tests/e2e/test_review_verifier_wiring.py    # NEW e2e fixture
  ```
  E2E test: runs full review on fixture diff, asserts REVIEW report contains both "Pass 1" and "Verifier" sections, and Pass 2 references are strict subset of verifier-kept findings.
- **Risk:** medium (stage template touches all reviewer invocations).
- **Rollback point:** **(1) discard worktree → (2) `git revert` from main → (3) regen snapshots from main repo.** This rollback pattern applies to every template-touching phase (per failures.md fail:test snapshot-regen-inside-worktree).

#### Phase A4: Telemetry emitter + integration into stage
- **Scope (in):** `src/harness_maker/review_telemetry.py` (new, uses CLAUDE.md atomic_write); call sites in `stages/review.md.j2`; `tests/unit/test_review_telemetry.py` (new).
- **Scope (out):** verifier logic, prompts.
- **Exit criterion:**
  ```bash
  uv run pytest tests/unit/test_review_telemetry.py -v
  uv run pytest tests/integration/test_review_telemetry_e2e.py  # INTEGRATION=1
  ```
  Unit: schema validation, atomic_write correctness, concurrent-write fixture (2 threads).
  Integration: real /hm:review run produces valid JSONL line with all 13 fields.
- **Risk:** low.
- **Rollback point:** revert telemetry module + call sites; no template hash changes if call sites isolated to dedicated block.

#### Phase A5: Structural tests + snapshot exclusion mechanism
- **Scope (in):**
  - `tests/snapshot/EXCLUSIONS.md` (new, lists reviewer-output paths).
  - `tests/snapshot/regenerate.py` MOD (reads EXCLUSIONS.md, skips listed paths).
  - `tests/structural/test_reviewer_outputs.py` (new, schema + verifier-drop on adversarial fixture).
  - `tests/structural/test_snapshot_exclusions_effective.py` (new, asserts exclusion mechanism filters correctly).
  - `tests/structural/test_telemetry_no_leak.py` (new, grep-based lint forbidding `wall_time_ms` interpolation in `*.j2` except behind explicit frozen filter).
  - `tests/fixtures/adversarial_findings.json` (new labeled fixture).
- **Scope (out):** runtime code.
- **Exit criterion:**
  ```bash
  uv run pytest tests/structural/ -v
  uv run pytest tests/snapshot/  # exclusions honored, non-excluded snapshots still pass
  ```
  Each structural test must independently pass; `test_snapshot_exclusions_effective.py` MUST inject a non-deterministic stub into an excluded path and assert the snapshot suite still passes (proves exclusion actually filters).
- **Risk:** low.
- **Rollback point:** revert test files; exclusion list is additive, snapshot regen unaffected.

#### Phase A6: 0.10.0 ship
- **Scope (in):** 5-file version sync (`.claude-plugin/plugin.json`, `.cursor-plugin/plugin.json`, `.codex-plugin/plugin.json`, `pyproject.toml`, `src/harness_maker/__init__.py`), `CHANGELOG.md` (verifier + telemetry), full snapshot regen from **main repo** (not worktree).
- **Scope (out):** Phase C work, Phase A7 baseline.
- **Exit criterion:**
  ```bash
  uv run pytest          # full pass from main repo
  uv run ruff check
  uv run mypy --strict
  ```
  Manual: `/hm:review` on harness-maker itself emits valid telemetry line; `git tag v0.10.0`.
- **Risk:** medium (broad regen sensitive to worktree-path embedding — failures.md fail:test snapshot-regen-inside-worktree applies).
- **Rollback point:** **(1) discard worktree → (2) `git revert` ship commit from main → (3) regen snapshots from main**. Drops back to pre-A1 state.

#### Phase A7: ~~Wall-time baseline capture (post-ship)~~ — **DISCARDED per ADR-008 (2026-05-11)**
This phase is **abandoned**. No `walltime_baseline_0_10_0.json` fixture, no `scripts/capture_baseline.py`, no representative-diff fixture, no N=5 measurement run. Wall-time, if needed, is manual / out-of-band per ADR-008. The placeholder is retained here only so phase numbering A1–A6 stays stable in references; do NOT treat this as pending work.
- **Scope (in):** *(none — phase discarded)*
- **Scope (out):** *(everything — phase discarded)*
- **Exit criterion:** *(none — phase discarded)*
- **Risk:** *(n/a — phase discarded)*
- **Rollback point:** *(n/a — phase discarded)*

### Phase C — Agentic Depth (ships as 0.11.0) — revised per ADR-009

> **ADR-009 (2026-05-11)** revised this section: original C1 lost its `test_pass2_no_reintroduction` and walltime-baseline E2E (both depended on the auto-invoked verifier — stripped by ADR-008). Original C2 (walltime CI test) **eliminated entirely**. Original C3 renumbered as new C2.

#### Phase C1: Reviewer prompt rewrite for agentic loop + grep-audit static guard
- **Scope (in):** `src/harness_maker/templates/agents/{code-reviewer,security-reviewer,performance-reviewer,concurrency-reviewer,ux-reviewer}.md` MOD (add agentic-depth framing per ADR-003 wording — instruct reviewers to use Read on changed files end-to-end and Grep to confirm hypotheses before flagging). + `tests/structural/test_reviewer_prompts_contain_agentic_depth_clauses.py` NEW.
- **Scope (out):** verifier library surface (untouched per ADR-008); telemetry schema (Phase A4) unchanged; **no walltime test**, **no E2E review test**, **no labeled-fixture incorrect_rate test** (all dropped per ADR-009).
- **Exit criterion:**
  ```bash
  uv run pytest tests/snapshot/                                                # regen for changed agents
  uv run pytest tests/structural/test_reviewer_prompts_contain_agentic_depth_clauses.py  # NEW
  uv run ruff check src/ tests/
  uv run mypy --strict src/
  ```
  The new structural test asserts each of the 5 reviewer prompt bodies contains the exact substrings locked in **ADR-009 Decision #1's substring contract table**. Failure mode: any reviewer prompt missing one of the required verbatim substrings → test fails → fix the prompt (do NOT relax the test; the substring contract is the PLAN-locked agentic-depth floor).
- **Risk:** medium (prompt drift, false-positive rate up — no auto-detection per ADR-009; bounded by P0/P1-only grade gate so P2/P3 noise won't lower grades).
- **Rollback point:** **(1) discard worktree → (2) `git checkout v0.10.0 -- src/harness_maker/templates/agents/` from main → (3) regen snapshots from main → (4) delete `tests/structural/test_reviewer_prompts_contain_agentic_depth_clauses.py`**.

#### Phase C2: 0.11.0 ship (was C3 pre-ADR-009)
- **Scope (in):** 5-file version sync (`pyproject.toml`, `src/harness_maker/__init__.py`, `.claude-plugin/plugin.json`, `.cursor-plugin/plugin.json`, `.codex-plugin/plugin.json`), `CHANGELOG.md` Unreleased → 0.11.0, snapshot regen from **main repo** (failures.md count:3 — worktree regen embeds worktree paths).
- **Scope (out):** all prior phases retained as-is.
- **Exit criterion:**
  ```bash
  uv run pytest                              # full pass from main
  uv run ruff check src/ tests/
  uv run mypy --strict src/
  ```
  Manual sanity check: render a sandbox with the new templates and confirm the 5 reviewer agent bodies contain the new agentic-depth clauses (eyeball `tests/fixtures/*/`.claude/agents/`). `git tag v0.11.0`.
- **Risk:** low (mechanical version bump after C1 is GREEN).
- **Rollback point:** **(1) discard worktree → (2) `git revert` C2 ship commit from main → (3) regen snapshots**. Returns to v0.10.0 state.

#### Eliminated: original Phase C2 (walltime CI test)
Per ADR-009 the original C2 is **gone**. No `tests/structural/test_review_walltime.py`, no `tests/fixtures/walltime_baseline_*.json`, no `INTEGRATION=1` walltime gate. Wall-time is manual / out-of-band per ADR-008.

## 🧪 Testing Strategy

**Unit (Phase A2, A4) — final state after ADR-008:**
- `test_two_pass_review.py` / `test_two_pass_verify.py`:
  - `test_verify_drops_unverified_inference`
  - `test_verify_handles_empty_findings`
  - `test_verify_preserves_kept_finding_fields`
  - `test_verify_invariant_no_introduction`
  - `test_verify_demote_*` (5 demote-validation tests)
  - `test_verify_fixture_label_is_fence_escaped_inside_data_region` (release-0-10-0 O1 fix)
  - ~~`test_verify_falls_back_on_model_unavailable`~~ — REMOVED per ADR-008 (depended on `ModelUnavailableError`).
  - ~~`test_verify_cli_rejects_*`~~ — REMOVED per ADR-008 (`verify` subcommand gone).
- `test_review_telemetry.py`:
  - `test_emit_writes_to_daily_file` / `test_emit_appends_subsequent_writes`
  - `test_record_*` (schema validation)
  - `test_emit_concurrent_writers_no_interleave` (4-thread × 25-record fixture, round-trip equality)
  - `test_emit_oversized_slug_rejected_at_schema_layer`
  - `test_emit_absolute_observability_dir_*` (release-0-10-0 O2 fix, 2 tests)

**Structural (Phase A1, A5, C1) — final state after ADR-009:**
- `test_verifier_agent.py` — agent definition contract: permissions deny set, invariant phrase, content_hash. (Retained as contract doc per ADR-008.)
- `test_reviewer_outputs.py` — finding schema on labeled adversarial fixture.
- `test_snapshot_exclusions_effective.py` — inject non-determinism in excluded path, assert suite still passes.
- `test_telemetry_no_leak.py` — grep `wall_time_ms` in `*.j2`, must be only behind frozen filter.
- `test_reviewer_prompts_contain_agentic_depth_clauses.py` (C1, NEW per ADR-009) — grep-audit on 5 reviewer prompts.
- ~~`test_pass2_no_reintroduction.py`~~ — REMOVED per ADR-009 (verifier auto-invocation gone).
- ~~`test_review_walltime.py`~~ — REMOVED per ADR-009 (no baseline, no integration verifier).
- ~~`tests/structural/test_review_stage_verifier_wiring.py`~~ — DELETED per ADR-008 (no Pass 1.5 step to assert).

**Integration (`INTEGRATION=1`):**
- ~~`test_review_telemetry_e2e.py`~~, ~~`test_review_verifier_wiring.py`~~, ~~`test_review_agentic_depth.py`~~ — all REMOVED per ADR-008/ADR-009 (no API key in target env).

**Manual:**
- A6: ✅ ran `/hm:review` on release-0-10-0 (HEAD~2..HEAD). Verifier surfaced as `fallback: model_unavailable` — direct evidence for ADR-008.
- C2: post-ship sanity — render sandbox with new templates, eyeball reviewer agent bodies for agentic-depth clauses.

**Labeled-fixture mode (ADR-005):** **ELIMINATED per ADR-009.** The `tests/fixtures/adversarial_findings.json` file remains as a reference fixture for prompt design but is no longer wired to a structural test. WRONG-criterion #1 (`incorrect_rate < 0.05`) is unenforceable post-ADR-008 — quality regression is now catchable only via manual `/hm:review` inspection on real PRs.

**LLM mock pattern (CLAUDE.md):**
- All unit tests use injected `VerifierClient` mock (via Protocol) instead of the previous `mock_anthropic_client` fixture, since `AnthropicVerifierClient` no longer exists.
- No integration tests gated on `INTEGRATION=1` remain — the verifier surface those tests exercised is library-only post-ADR-008.

## ⚠️ Risks & Mitigation

| # | Risk | Severity | Likelihood | Mitigation |
|---|------|----------|------------|------------|
| 1 | Verifier model unavailable (failures.md 2026-05-11) | n/a | n/a | **OBSOLETE post-ADR-008** — verifier auto-invocation removed entirely; library `verify_findings()` requires caller-supplied client (no API path exists in target env). |
| 2 | Reviewer agentic-depth adds significant wall-time on simple diffs | medium | high | **No auto-detection post-ADR-009.** Manual `/hm:review` wall-time inspection on representative diffs when subjectively painful; no CI gate. ADR-009 Consequences documents accepted risk. |
| 3 | Agentic prompt causes reviewers to fixate on irrelevant areas | high | medium | C1 e2e manual review; rollback to v0.10.0 template via `git checkout v0.10.0 -- agents/`. |
| 4 | Telemetry file disk growth unbounded | low | high | Daily-rotated files; CLAUDE.md docs note manual cleanup playbook. |
| 5 | FP increase from agentic depth (no de-noise mitigation post-ADR-008) | medium | medium | **No auto-detection post-ADR-009.** Catch path: P0/P1-only grade gate bounds blast (P2/P3 noise doesn't lower grade) + manual `/hm:review` inspection on real PRs. Adversarial fixture retained as reference for prompt design, no auto-test. |
| 6 | Snapshot exclusion masks regression in non-reviewer code | medium | low | Exclusion list explicit, reviewed at PR time; `test_snapshot_exclusions_effective.py` asserts mechanism functions correctly. |
| 7 | Worktree-path snapshot corruption (failures.md fail:test) | high | medium | A3/A6/C1/C2 rollback playbook: discard worktree → revert from main → regen from main. *(A7 and old C3 no longer exist post-ADR-008/ADR-009.)* |
| 8 | Verifier prompt drift over time | medium | low | Verifier agent file has `content_hash` frontmatter; KEEP/REPLACE reconcile checks; structural test asserts invariant phrase remains. |
| 9 | Telemetry numeric fields leak into snapshot-tested templates | medium | low | `test_telemetry_no_leak.py` grep-based lint; rejects PR if `wall_time_ms` interpolated in any `*.j2` outside frozen filter. |
| 10 | Concurrent telemetry writes from multiple `/hm:review` sessions corrupt JSONL | medium | low | atomic_write (tempfile + os.replace) per CLAUDE.md §Atomic file write; `test_emit_concurrent_writers` fixture. |
| 11 | Cost variance pathological diff causes 10x token spike | medium | low | ADR-007 records intent; post-ADR-009 **no auto-floor exists** — user discretion only. User can manually disable agentic depth by reverting Phase C1 reviewer-prompt edits if needed. |
| 12 | Adversarial-finding fixture goes stale | low | low | **Downgraded post-ADR-009** — fixture is reference-only (no auto-test wired). Manual quarterly review optional, not gated. |

## ✅ Success Criteria

### 0.10.0 (Phase A complete)
- [x] Verifier agent file exists with permission denies for Write/Edit/Bash interpreters (Phase A1 structural test passes).
- [x] `verify` subcommand drops ≥1 spurious finding per adversarial fixture (≥3 fixtures tested).
- [x] Verifier model-unavailable fallback exercised by unit test (`mock_anthropic_client` exception). Integration test pending A6 (real `/hm:review` run).
- [x] `.claude/observability/review-{date}.jsonl` contains valid per-session entries with all 14 schema fields (1 more than initial PLAN; `fallback` marker added by ADR-006 fallback contract).
- [x] Concurrent-writer fixture produces no interleaved lines AND no byte-tearing (`test_emit_concurrent_writers_no_interleave` round-trip equality, post-review-fix).
- [x] Snapshot exclusion mechanism filters reviewer-output paths (`test_snapshot_exclusions_effective`).
- [x] No `wall_time_ms` interpolation in any `*.j2` file outside frozen filter (`test_telemetry_no_leak`).
- [x] Manual `/hm:review` on harness-maker: 0.10.0 shipped (commit `943a7f4`); release-0-10-0 review cycle on HEAD~2..HEAD produced `work-docs/REVIEW-release-0-10-0-2026-05-11.md`. Verifier surfaced as `fallback: model_unavailable` (no API key) — directly motivating ADR-008. *(A6 closed)*

### 0.11.0 (Phase C complete)
- [x] All 5 reviewer agent prompts contain agentic-depth framing — snapshot regen complete; `## Investigation Steps (agentic depth)` section added to `{code,security,performance,concurrency,ux}-reviewer_body.md.j2`; sha256 baseline in `test_agent_body_partials.py` updated for the 5 modified agents.
- [x] `test_reviewer_prompts_contain_agentic_depth_clauses` (NEW per ADR-009) — grep-audit asserts each of the 5 reviewer prompts contains the required agentic-depth instruction substrings. 5/5 GREEN.
- [x] Manual `/hm:review` on adversarial diff: REVIEW report references tool-call evidence — **DEFERRED (user-orchestrated post-merge)**. Run after `/hm:make --update` rebuilds the `.claude/agents/` from the new 0.11.0 templates. Not blocking 0.11.0 ship.
- [x] No silent build break in auto-fix path — `auto_fix_reverted_n` in telemetry schema retained; existing revert-on-failure logic in stage template untouched.
- [x] All non-reviewer snapshots unchanged across 0.10.0 → 0.11.0 ship commits — 8 snapshot YAMLs regenerated only for the 5 reviewer agent SHAs + version stamp; no spurious file additions or removals.

### Dropped criteria (post-ADR-008 / ADR-009 — recorded for audit trail)

These were original acceptance criteria that became un-auto-testable after ADR-008/ADR-009. They are NOT pending work; they are consciously abandoned. Re-introducing any of them requires a new ADR superseding 008/009.

- ~~`walltime_baseline_0_10_0.json` committed at A7 with p50/p95/mean/n=5/fixture_sha~~ — discarded by ADR-008 (no API key → no real verifier-included baseline possible).
- ~~Pass 2 output ⊆ verifier-kept set (`test_pass2_no_reintroduction`)~~ — discarded by ADR-009 (verifier auto-invocation removed; replaced by `test_reviewer_prompts_contain_agentic_depth_clauses` above).
- ~~`test_review_walltime.py` `current_p50 ≤ 3.0 × baseline_p50` (INTEGRATION=1)~~ — discarded by ADR-009 (no baseline; wall-time is manual / out-of-band).
- ~~Labeled-fixture `incorrect_rate < 0.05` over last 10 entries~~ — discarded by ADR-009 (`verifier_false_*` counters cannot be auto-populated in target env; adversarial fixture retained as reference-only).

## 🔍 Plan Validation

**Validator agent:** `plan-validator` (single pass, Round 5 follow-up integrated).
**Overall outcome:** `NEEDS_REVISION` → `NEEDS_REVISION_RESOLVED` after Round 5 interview + direct revisions.

### Critique resolution table

| # | Critique | Severity | Resolution path | Interview / ADR ref |
|---|----------|----------|-----------------|---------------------|
| 1 | Phase A1 exit uses non-matching `-k verifier` filter | warning | **Revised plan**: explicit `tests/structural/test_verifier_agent.py` with permission + invariant assertions. | Direct revision (no user decision needed). |
| 2 | Phase C2 baseline has no producing phase | critical | **Revised plan**: new Phase A7 dedicated baseline capture; produces `tests/fixtures/walltime_baseline_0_10_0.json`. | Interview #8, ADR-004 extended. |
| 3 | WRONG-criterion #1 (verifier-incorrect <5%) unmeasurable | critical | **Revised plan**: labeled-fixture mode + telemetry fields `verifier_false_drop_n` / `verifier_false_keep_n` / `fixture_label`; structural test computes `incorrect_rate` from last N labeled runs. | Interview #9, ADR-005/006 extended. |
| 4 | Verifier-Pass 2 partition not enforced in prompts | warning | **Revised plan**: A1 prompt invariant "verifier MUST NOT introduce findings" + structural assertion; C1 Pass 2 prompt invariant "MUST NOT re-evaluate verifier-dropped findings" + `test_pass2_no_reintroduction`. | Direct revision. |
| 5 | Determinism leakage risk into snapshot-tested surfaces | warning | **Revised plan**: Risk row #9 added; `test_telemetry_no_leak.py` grep-based lint enforces. | Direct revision. |
| 6 | A3 rollback says regen from main but A3 runs in worktree | warning | **Revised plan**: Standardized rollback playbook on A3/A6/A7/C1/C3 — (1) discard worktree → (2) revert from main → (3) regen from main. | Direct revision. |
| 7 | A5 has no test that exclusions actually take effect | warning | **Revised plan**: `test_snapshot_exclusions_effective.py` added with non-deterministic stub injection. | Direct revision. |
| 8 | Verifier model-unavailable fallback unit test missing | suggestion | **Revised plan**: `test_verify_falls_back_on_model_unavailable` added to Phase A2 unit test list. | Direct revision. |
| 9 | Missing risk: telemetry write contention from concurrent worktrees | warning | **Revised plan**: Risk row #10 added; atomic_write mitigation + `test_emit_concurrent_writers` fixture. | Direct revision. |
| 10 | ADR-003 abandons determinism but no cost-ceiling ADR | warning | **Revised plan**: ADR-007 added recording intent (cost intentionally unbounded; only wall-time is enforced). | Interview #10. |

**Re-validation:** Not triggered for the initial validator pass (NEEDS_REVISION resolved without escalating to MAJOR_REVISION). A second validator pass on the 2026-05-11 PLAN revision (ADR-009) returned `NEEDS_REVISION` with 2 critical + 4 warnings — all addressed inline (duplicate Interview row #10, deferred substring contract, off-topic rejected-alternative, 4 stale Risks & Mitigation rows, Success Criteria checkbox semantics, ADR-007 partial supersedure).

> **Post-ADR-008/ADR-009 tombstone (2026-05-11):**
> - Critique #2's resolution (Phase A7 baseline capture) was subsequently **discarded by ADR-008**. The underlying concern (walltime regression detection) is now consciously accepted as un-auto-testable in the target env.
> - Critique #3's resolution (labeled-fixture mode with `verifier_false_*` counters) was subsequently **eliminated by ADR-009**. The underlying concern (verifier precision/recall measurement) is now consciously accepted as un-auto-testable.
> - Critique #4's resolution (verifier-kept partition in Pass 2 + `test_pass2_no_reintroduction`) was subsequently **eliminated by ADR-009**. The partition is replaced by the CP10 contract (Pass 2 ⊆ Pass 1) which was already enforced in `merge_passes`. The `test_pass2_no_reintroduction` test is gone; the new grep-audit static test (`test_reviewer_prompts_contain_agentic_depth_clauses`) replaces it for a different purpose (prompt-text contract, not Pass-2 set partition).
>
> The pre-ADR-008/009 resolution paths are preserved in the table for historical audit. Re-introducing any of the dropped mechanisms requires a new ADR superseding 008/009.

---

*Plan written 2026-05-11; revised 2026-05-11 per ADR-008 / ADR-009. Phase A is library-only-surface-retained-post-strip. Phase C is ready for `/hm:execute llm-code-review-2026` when user invokes — DO NOT auto-proceed.*
