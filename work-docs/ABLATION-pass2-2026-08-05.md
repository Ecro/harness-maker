---
type: ablation
task_slug: workflow-loop-efficiency
phase: 5
created: 2026-08-05
status: pre-registered
arm: post-removal
adrs: [ADR-006, ADR-007]
summary: "Pre-registration + natural-experiment analysis for the Pass 2 contextual-verdict ablation"
---

# Ablation — Pass 2 (contextual verdict), post-removal arm

> **Read the arm before the result (ADR-007).** This measures the pipeline **after**
> ADR-001 removed the Pass 1.5 verifier dispatch. The inherited "+47pp precision on
> anchoring-prone diffs" claim was measured on a pipeline that **contained** Pass 1.5.
> The two are not directly comparable, and an unqualified `reproduced: false` could not
> distinguish "the claim was wrong" from "the pipeline changed underneath it".
> §4 states the mismatch explicitly. **Pass 2 stays in the pipeline regardless of the
> result** — deletion is a stage-2 decision, not this artifact's.

---

## 1. Pre-registration (written BEFORE the run)

Everything in this section was committed before any measurement was taken. Its purpose is
narrow and specific: the honesty of the run is an **accepted waiver** (SPEC AC-005 — it is
not gated, by decision at interview #10), so pre-registration is what makes that waiver
survivable. A bad measurement then costs a re-run, not a shipped regression.

| Parameter | Value |
|---|---|
| **Corpus** | 8 archived diffs drawn from `work-docs/REVIEW-*.md` whose commit range still resolves, selected by `git log` order — **not** by outcome. Selection list is frozen in §1.1 before the run. |
| **Run count** | 3 independent runs per arm per diff (reviewer output is nondeterministic — CLAUDE.md records this as strong enough to require id-keyed voter merge). |
| **Arms** | `pass1_only` (rubric-only, metadata redacted, stop after Pass 1) vs `pass1_plus_pass2` (current shipped pipeline). |
| **Model / prompt version** | `claude-opus-5`; rendered review stage at the P1 commit of this branch. Both arms use the **same** render — the `pass1_only` arm stops early, it does not use a different template. |
| **Cache handling** | Each run is a fresh dispatch. Prompt-cache reads are permitted (they do not change output distribution) but no run reuses another run's *output*. |
| **Cost computation** | Output tokens per arm, summed across runs, from the dispatch accounting — **not** wall-clock, which is confounded by queueing. Wall-clock is recorded separately and marked as such. |
| **Tolerated delta** | Pre-declared: a precision drop of **≤ 5pp** for `pass1_only` is "no material detection loss". |
| **Stage-2 decision rule** | Pre-declared: recommend removing Pass 2 **only if** `pass1_only` precision is within the tolerated delta **and** the cost saving exceeds 15% of review-stage output tokens. Any other outcome recommends keeping Pass 2. This rule is fixed now so it cannot be fitted to the result. |

### 1.1 Frozen corpus

**Status: NOT YET SELECTED — the run has not been authorized.** This subsection is the
gate: the eight commit ranges must be written here, and this file committed, *before* the
first dispatch. A corpus chosen after seeing any result is not a corpus.

### 1.2 `reproduced` is per-expected-id, not a boolean

The inherited claim names specific anchoring-prone conditions. Each becomes an expected id
with its own verdict and, on failure, a **cause** — one of `arm-mismatch` (the condition
depended on Pass 1.5, which no longer exists), `not-reproduced` (the condition exists and
the effect did not appear), or `not-measurable` (the corpus contained no instance).
A bare `false` would collapse three different meanings, and the first of them is expected
by construction in this arm.

---

## 2. Result

**NOT YET RUN.** Keys `{diffs, pass1_only, pass1_plus_pass2, delta, reproduced}` are
populated here after the run authorized against §1. They are deliberately absent rather
than zero-filled — see §3.2 for what this repo's own ledger cost is of writing `0` where
"not measured" is the truth.

---

## 3. Natural-experiment analysis (recorded, NON-BLOCKING — ADR-006 part 1)

This section needed no new measurement. The ledger at `.claude/observability/review-*.jsonl`
already contains rounds in which the verifier did not run, recorded **before** this change
existed — so the comparison cannot be circular. It is also **observational, confounded, and
does not gate the landing.**

### 3.1 Groups

66 rows across 20 ledger files. Grouping is by the `fallback` value, which is the only
signal in the schema for whether the verifier ran:

| Group | `fallback` values | n (rounds) | Σ `pass1_n` | Σ `consensus_passed_n` | mean `consensus_passed_n / pass1_n` | median |
|---|---|---|---|---|---|---|
| **verifier absent** | `verifier_deferred` (×2), `adr-008-no-auto-verifier`, `pass1_5_stripped_adr_008`, `pass1.5+pass2_redaction_skipped`, `no-verifier-no-formal-pass2` | 6 | 41 | 5 | **0.1286** | 0.1429 |
| **verifier present** | `null` | 54 | 304 | 39 | **0.1135** | 0.0000 |
| *other fallback* (excluded) | `model_unavailable`, `manual-user-override`, `manual-orchestrator-fix`, `local-review-no-subagents`, `rereview_skipped`, `re-review-with-full-context` | 6 | 10 | 1 | 0.0833 | 0.0833 |

The middle group is excluded rather than folded into either arm: each of those six values
describes a *different* degradation, and none of them says whether the verifier ran.

**Direction:** the consensus-pass rate is **higher** without the verifier (0.1286 vs
0.1135, a +1.5pp difference in means). That is the direction a reduce-only filter predicts
— it can only remove findings — and it is consistent with the measured lifetime drop rate
of 1.9% (5 of 261 findings across 41 reviews). It is **not** evidence that removal is safe:
consensus-pass rate is not detection, and the effect is far inside the noise this n permits.

### 3.2 Three corrections this analysis forced

**(a) The PLAN's "41 rounds where it did run" is wrong.** The verifier-present group is
**54** rounds, not 41. The number 41 appears twice by coincidence: it is the RESEARCH
document's count of *reviews* (not rounds), and it is also `Σ pass1_n` of the
verifier-**absent** group in the table above. Rounds and reviews are different units and
the PLAN conflated them. Nothing downstream depended on the figure; it is corrected here.

**(b) The severity distribution is not computable — the field does not exist.** P5's exit
criterion asks for "the severity distribution between the two groups". The ledger's full
key set is `{ts, slug, round, pass1_n, verifier_kept_n, verifier_dropped_n,
verifier_false_drop_n, verifier_false_keep_n, fixture_label, pass2_kept_n,
consensus_passed_n, wall_time_ms, build_break_count, auto_fix_reverted_n, fallback}` —
**there is no severity field, and there never was.** Findings are counted, never
classified, so severity cannot be recovered from this data at any n. This is a **third**
unimplementable element in ADR-006, after live re-invocation (nondeterminism) and
deterministic re-injection (no persisted payload). It is recorded, not worked around:
fabricating a distribution from REVIEW prose would make the executor author the oracle it
is graded against, which is exactly the defect AC-007's `oracle_evidence` exists to avoid.
**ADR-006 part 2 (forward payload persistence, P3) is what makes it computable from the
next landing on.**

**(c) The "verifier absent" rows encode the same state two incompatible ways.** All six
carry non-null `verifier_kept_n` / `verifier_dropped_n` despite the verifier not running:

| slug | round | `pass1_n` | `verifier_kept_n` | `verifier_dropped_n` | convention |
|---|---|---|---|---|---|
| `llm-code-review-2026-phase-c` | 1 | 5 | 5 | 0 | passthrough |
| `memory-md-operations` | 1 | 14 | 14 | 0 | passthrough |
| `wrapup-context-carry` | 1 | 9 | 9 | 0 | passthrough |
| `health-plugin-bugs-2026-05` | 1 | 6 | 0 | 0 | zero-fill |
| `test-fidelity-gap` | 1 | 7 | 0 | 0 | zero-fill |
| `health-plugin-bugs-2026-05` | 2 | 0 | 0 | 0 | (degenerate — `pass1_n` is 0) |

Two writers, two conventions, one meaning. Worse, the three `zero-fill` rows **violate the
schema's own documented invariant** `input_n == kept_n + dropped_n` (6≠0, 7≠0) — and the
model accepted them, because `0` was a legal value for a field whose real state was
"absent".

This is the concrete cost of the ambiguity ADR-002 closes. The nullability landed in P1 for
a forward-looking reason; this table is the retrospective evidence that the reason was
real, in this repo, in this file. It also means the **verifier-absent group in §3.1 is not
internally consistent** — a further reason the comparison is an analysis and not a gate.

---

## 4. Arm mismatch versus the inherited claim (ADR-007, exit criterion 3)

The inherited claim — **"+47pp precision on anchoring-prone diffs"** — was measured on a
pipeline containing Pass 1.5. That dispatch no longer exists (ADR-001). Therefore:

- Any expected id in §1.2 whose mechanism ran **through** Pass 1.5 is expected to come back
  `arm-mismatch`, and that is a correct result, not a failure of the ablation.
- The measured numbers in §2, once run, are **not** directly comparable to the +47pp
  figure. Stage 2 must read this section before reading §2.
- Pass 2 is retained regardless of §2's outcome.

---

## 5. What this artifact does NOT establish

- **Not a detection check.** Stage 1 ships with **no blocking detection check** (PLAN R6,
  the accepted AC-008 waiver). §3 is observational and §2 is not yet run.
- **Not gated for honesty.** SPEC AC-005 — accepted waiver, interview #10. §1 is the
  mitigation, not a gate.
- **Not a severity comparison.** See §3.2(b) — structurally impossible from this ledger.
