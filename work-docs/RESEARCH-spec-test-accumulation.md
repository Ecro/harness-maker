---
type: research
task_slug: spec-test-accumulation
status: complete
created: 2026-05-29
tags: [harness-maker, research, spec-driven, testing, mutation, verification]
mtime_warn_days: 7
libs_fetched: []
sources:
  - https://martinfowler.com/articles/exploring-gen-ai/sdd-3-tools.html
  - https://arxiv.org/html/2602.00180v1
  - https://thebcms.com/blog/spec-driven-development
  - https://tessl.io/blog/tessl-launches-spec-driven-framework-and-registry/
  - https://alistairmavin.com/ears/
  - https://github.com/github/spec-kit/issues/1356
  - https://arxiv.org/html/2602.07900v2
  - https://totalshiftleft.ai/blog/future-software-testing-ai-driven-development
  - https://laracopilot.com/blog/ai-test-generation-2026/
related_docs:
  - "[[PLAN-total-spec-coverage]]"
  - "[[PLAN-test-fidelity-gap]]"
  - "[[RESEARCH-test-fidelity-gap]]"
  - "[[RESEARCH-llm-code-review-2026]]"
summary: "Bridge execute↔machine.yaml so the AC→test_id→mutation graph accumulates on the everyday TDD path, not just the backfill loop"
---

# RESEARCH: Spec-based workflow — how spec + test cases accumulate, and where ours leaks

## 🎯 Recommended Direction

**Bridge harness-maker's two disjoint test-authoring pipelines so the machine-verifiable spec graph (`AC → test_ids → executable_predicate/golden_table → mutation_threshold`) accumulates through the *everyday* `/hm:execute` path — not only during the one-time `/hm:loop p5-batch` backfill.**

Today `/hm:spec` writes a rich `SPEC-{slug}.machine.yaml` (per-AC test IDs, predicates, golden tables, mutation tiers), but `/hm:execute` ignores it: it authors `test_s1_*` tests from the prose `## In-Scope Scenarios` and gates them with an LLM `test-reviewer` — no `.machine.yaml`, no mutation run, no AC↔test_id binding. The result is that the **specs and tests you accumulate during normal feature work never bind to each other** the way the SPEC schema promises; that binding is reconstructed retroactively by a separate loop. Closing this gap is the highest-leverage change and it aligns us with the 2026 SOTA consensus that *mutation-guided, oracle-grounded* tests — not coverage counts — are what make an accumulating suite trustworthy. This is informational; `/hm:plan` makes the binding decision.

## 🔍 Refinement Decisions

- `--deep` not set → Phase 0 / Phase 0.5 interview skipped; dove directly into gathering.
- **Discovery lens:** Technical architecture / implementation (primary) + Research / benchmark (secondary). The User-workflow / product-opportunity lens is *not* binding here — the "users" of this workflow are harness-maker's own maintainers (dogfooding), and the question is about internal artifact-graph integrity, not a new user-facing capability. Risk/compliance lens N/A (no new data boundary or permission surface).

## 🛠️ Approaches Found

### Approach A — Unify execute with `.machine.yaml` (recommended)

| Field | Content |
|---|---|
| **Approach** | `/hm:execute` Phase A reads `SPEC-{slug}.machine.yaml`; authors one test per AC against its declared `test_ids[]`; for `mechanical` ACs asserts the `executable_predicate`, for `parametric` ACs parametrizes over `golden_table`, for `judgment` ACs links the `rubric_id`. Phase D (or a tier-gated subset) runs `spec_mutation.gate`. `pending_test` flips to `false` only when the test_id resolves via `pytest --collect-only`. |
| **Assumption** | The dual-file SPEC contract (PLAN-total-spec-coverage ADR-006/007) is the intended source of truth and should drive everyday TDD, not just backfill. |
| **Evidence** | SPEC stage already writes + cross-validates the schema (`spec.md.j2:214-288`); `spec_mutation.threshold_for` / `spec_quality` / `spec_machine.resolve_pytest_selector` modules already exist. SOTA: "stop counting test cases, start defining intent, constraints, and oracles" + "mutation testing is table stakes for AI-written suites" ([laracopilot], [totalshiftleft]). |
| **Trade-off** | Heavier per-phase execute (mutation is slow). Mitigate: tier-gate mutation (T1 only on the everyday path, T2/T3 sampled or deferred to loop), keep scenario-prose tests as a fallback when no `.machine.yaml` exists. |
| **Compatibility** | High — reuses existing modules; `--no-tdd` and SPEC-less tasks still work via the current scenario path as fallback. |
| **Risk** | medium (execute latency; need a clean fallback when machine.yaml absent) |

### Approach B — Spec-as-source / regenerate (Tessl-style)

| Field | Content |
|---|---|
| **Approach** | Treat the SPEC as the editable artifact and regenerate code+tests from it (`// GENERATED FROM SPEC — DO NOT EDIT`), as Tessl's spec-anchored model does ([martinfowler], [tessl]). |
| **Assumption** | Code is disposable output of the spec. |
| **Evidence** | Tessl + spec-kit's `/specify→/plan→/tasks` show ~3–10× first-pass success on non-trivial tasks ([martinfowler]). |
| **Trade-off** | Fundamentally changes our model (we generate *harnesses*, users own *domain code*). Conflicts with [[feedback_domain_content_ownership]] — users author domain code, we don't regenerate it. |
| **Compatibility** | low — contradicts the "user owns domain content" principle. |
| **Risk** | high (model mismatch) |

### Approach C — Keep dual pipelines, strengthen the drift gate

| Field | Content |
|---|---|
| **Approach** | Leave execute as-is; make `observability/spec_drift.scan()` (orphan AC, stale mutation, AC-gap, OQ-overflow) a *blocking* gate in `spec-driven` mode instead of advisory, so divergence between the two pipelines is at least *surfaced* every wrapup. |
| **Assumption** | Reconciliation-after-the-fact is acceptable; we only need to make drift loud. |
| **Evidence** | `spec_drift.scan()` already exists and is `dev_mode`-gated (ADR-013). SOTA "self-policing feedback control loop that compares observed behavior against spec, fails fast" ([thebcms]). |
| **Trade-off** | Doesn't fix the root cause (tests still authored off prose, not AC); only detects drift later. Cheaper to ship. |
| **Compatibility** | high (incremental) |
| **Risk** | low |

## ⚠️ Pitfalls

1. **Tests mirror the implementation, not the spec (the oracle problem).** LLMs generate oracles that capture *what the code does* rather than *what it should do* ([super-productivity], [arxiv 2602.07900]). Our `execute.md.j2:167` already fights this ("assertions match the scenario's **Then** clause exactly; no tautologies/over-mocking/stub-only bodies") and the RED gate (`:200`, "fail for the right reasons") + test-reviewer gate (`:170-184`) are real defenses — **but assertion quality is only *measured* (mutation) on the loop path, never on everyday execute.** A test can pass the reviewer and still be assertion-weak.

2. **Coverage ≠ meaningful suite.** 2026 consensus: mutation testing is now "table stakes"; counting tests or % coverage is the wrong metric ([laracopilot], [totalshiftleft]). We have `spec_mutation` but it is quarantined to `/hm:loop p5-batch`. Risk: a growing suite that *looks* covered but doesn't kill mutants.

3. **Spec↔code drift / spec rot.** Even the leading SDD tools "don't yet fully automate keeping spec ↔ code in sync"; specs "rot within a sprint" if not policed ([thebcms], [martinfowler]). Our `pending_test` accumulation (PLAN-total-spec-coverage: >50 → backfill PLAN, >100 → blocker) is exactly this rot made visible — but the cap is the only forcing function.

4. **Two disjoint pipelines (our specific footgun).** Execute authors `test_s1_*` from scenario prose; `.machine.yaml` expects `tests/path::fn` per AC. The binding `/hm:spec` writes is reconstructed retroactively by `spec_inventory/reverse_map.py` (ADR-010) instead of maintained forward. New features accrue tests that never link to their AC unless the backfill loop runs.

5. **Advisory CI has no forcing function.** PLAN-test-fidelity-gap shipped Layer 1 boundary-parse tests as *advisory only* (ADR-003) — "maintainer can still ship despite a red advisory." Layers 2 (cross-template invariant lints) and 3 (transcript canary + LLM judge) are deferred. The fidelity gap class (consumer parser disagrees with our Python view — 30+ `fix()` commits) is only partially closed.

6. **Single-LLM-judge confirmation bias.** RESEARCH-llm-code-review-2026 flags that the *same* reviewer self-verifies in Pass 2. The same risk applies to the `test-reviewer` gate: it judges tests it may have helped shape. A separate verifier role is the named highest-ROI fix (<1% incorrect findings, Anthropic pattern).

## ❓ Open Questions

1. **Scope of unification (Approach A):** author tests from `test_ids[]` for *all* AC types, or start with `mechanical` (executable_predicate) only and leave `parametric`/`judgment` on the scenario path?
2. **Mutation on the hot path:** run `spec_mutation.gate` in everyday execute Phase D, or only T1 ACs, or sample? What latency budget is acceptable (mutmut is slow)?
3. **Fallback contract:** when no `.machine.yaml` exists (SPEC-less / trivial tasks, `--no-tdd`), does execute silently fall back to scenario-prose tests, or refuse in `spec-driven` mode?
4. **Drift gate teeth:** promote `spec_drift.scan()` from advisory to blocking in `spec-driven` mode (Approach C), and is that orthogonal-to or a prerequisite-for Approach A?
5. **Separate verifier role:** add a dedicated test-verifier (distinct from `test-reviewer`) to break confirmation bias, or fold into the existing gate?
6. **EARS adoption:** spec-kit is adding EARS notation ([github/spec-kit#1356]); our G-W-T is functionally equivalent. Worth aligning AC phrasing to EARS patterns for unwanted-behavior/optional-feature clarity, or is G-W-T sufficient?

## 📚 Sources

- [Understanding SDD: Kiro, spec-kit, Tessl — Martin Fowler](https://martinfowler.com/articles/exploring-gen-ai/sdd-3-tools.html)
- [Spec-Driven Development: From Code to Contract (arXiv 2602.00180)](https://arxiv.org/html/2602.00180v1)
- [SDD: The Definitive 2026 Guide — BCMS](https://thebcms.com/blog/spec-driven-development)
- [Tessl launches spec-driven framework and registry](https://tessl.io/blog/tessl-launches-spec-driven-framework-and-registry/)
- [EARS — Easy Approach to Requirements Syntax (Mavin)](https://alistairmavin.com/ears/)
- [spec-kit EARS integration request #1356](https://github.com/github/spec-kit/issues/1356)
- [Rethinking the Value of Agent-Generated Tests (arXiv 2602.07900)](https://arxiv.org/html/2602.07900v2)
- [The Future of Software Testing in AI-Driven Development (2026) — Total Shift Left](https://totalshiftleft.ai/blog/future-software-testing-ai-driven-development)
- [AI Test Generation and Code Quality Trends for 2026 — Laracopilot](https://laracopilot.com/blog/ai-test-generation-2026/)
- [AI-Generated Tests: Where They Shine and Fall Short — super-productivity](https://super-productivity.com/blog/ai-generated-tests-guide/)

## 🔗 Related Internal Docs

- [[PLAN-total-spec-coverage]] — dual-file SPEC, L1/L2 cluster accumulation, 4-part AI gate, mutation tiers (ADR-001…013)
- [[PLAN-test-fidelity-gap]] / [[RESEARCH-test-fidelity-gap]] — consumer-parser fidelity, 3-layer defense (only Layer 1 shipped)
- [[RESEARCH-llm-code-review-2026]] — verifier-as-separate-role / confirmation-bias finding
- [[feedback_domain_content_ownership]] — users own domain code (constrains Approach B)
