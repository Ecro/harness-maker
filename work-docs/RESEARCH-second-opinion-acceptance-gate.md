---
type: research
task_slug: second-opinion-acceptance-gate
status: complete
created: 2026-07-30
tags: [harness-maker, research, second-opinion, review-loop, consensus, termination]
mtime_warn_days: 7
libs_fetched: []
sources: []
related_docs: ["[[PLAN-second-opinion-multi-model]]", "[[PLAN-second-opinion-invocation-and-slug-cap]]", "[[PLAN-crossmodel-codex-gaps]]", "[[fail:design friction-looking-guard-was-load-bearing-safety]]", "[[fail:tooling agy-print-flag-swallows-next-flag]]"]
summary: "Review-path second opinion has no refutation gate and an unbounded voter; freeze the vote + measure disposition"
---

# RESEARCH — second-opinion acceptance gate & review-loop termination

## 🎯 Recommended Direction

**The user's two complaints have two different root causes, and only one of them is
about "accepting too easily".** The non-termination is caused by an *unbounded,
stochastic voter* re-entering the auto-fix loop; the easy-acceptance is caused by the
review path having **no refutation gate at all**, while the plan path already has one
(PIDA). Recommended: **(B) freeze each model's vote to exactly one invocation per
`/hm:review` + (C) restore per-finding disposition rows so acceptance rate becomes
measurable**, then decide the threshold change (A: port PIDA to review) on evidence
rather than on guess.

Rationale: B is a prose-only change to `review.md.j2` and is the *binding* fix for
"끝이 안남" — it removes the mechanism by which each auto-fix round can inject brand-new
findings. C is cheap (the ledger schema already carries `finding_ref` +
`disposition`) and is the only way to answer "너무 쉽게 받아들이나?" with a number
instead of an impression. A is the principled fix but its threshold choice
(K=2 vs "≥1 Claude voice required") is unanswerable without C, and the current
recall-favoring K=2 is a **deliberate** ADR-006 decision that must not be reverted on
vibes — see Pitfalls.

## 🔍 Refinement Decisions

`--deep` not set → Phase 0 / Phase 0.5 interview skipped.

**Discovery lens:** Technical architecture / implementation + Risk / compliance.
The topic is a narrow internal control-flow question about this repo's own review
templates; the user-workflow lens does not apply (no user-facing artifact surface
is in question), and the coverage guard for broad/trend/roadmap topics is N-A.

## 🛠️ Approaches Found

### Diagnosis first — what the code actually does

**Asymmetric scrutiny (this is the "too easily accepted" mechanism):**

| Path | Filters a finding must survive |
|---|---|
| Claude reviewer finding | Pass 1 (rubric-only, metadata redacted) → **Pass 1.5 `code-verifier`** (reduce-only KEEP/DROP/DEMOTE) → **Pass 2** (authoritative; a Pass-1 finding absent from Pass 2 is **dropped**, CP10) → Step 4 consensus |
| codex / antigravity finding | *(none)* → Step 4 consensus |

`review.md.j2:168-298` defines the three Claude passes; `Step 3.5`
(`review.md.j2:300-324`) injects the adapted model findings **after** Pass 2, straight
into the Step 4 input list. There is no verifier, no refutation, no context-restore
pass for them on the review path.

Three further accelerants, all in-template and all deliberate:

1. **The surface predicate is relaxed only for them.** `review.md.j2:337-347` — a
   second-opinion finding with `needs_relaxation: true` (null `file`/`line`) may match
   on *symbol/message similarity* instead of `file` + `line ± 5`. The template states
   the motive plainly: "Without this relaxation a null-location second-opinion finding
   would always degrade to `manual-only`, making its vote cosmetic." The relaxation
   exists **to raise their accept rate**.
2. **K = 2 is fixed and recall-favoring.** `review.md.j2:305-307` — "more models make
   agreement *easier* to reach (recall-favoring), never a rising bar." With both models
   enabled, **codex + antigravity agreeing with zero Claude corroboration reaches K=2**
   → `consensus-passed` → auto-fix eligible (`review.md.j2:370`) → counts toward
   `P0_count`/`P1_count` exactly like a reviewer-sourced finding (`review.md.j2:410-415`).
3. **The plan path has the gate the review path lacks.** `plan-validator_body.md.j2:116-125`
   defines **PIDA**: form a rebuttal `KEEP` / `REFUTE` with concrete evidence, let a
   test oracle settle it, and on no-oracle set `unresolved` + surface (never block).
   Review has no PIDA equivalent. The debate protocol is already written, already
   shipped, and wired on exactly one of the two stages.

**Unmeasurable (why the user can only *suspect* over-acceptance):** `codex_ledger.py:43-47`
still declares `finding_ref: str` and `disposition: Literal["accepted","rejected","duplicate","unresolved"]`,
but the current writer emits **one row per invocation** with `finding_ref: "n/a"`,
`disposition: "unresolved"` (CLAUDE.md, PLAN-second-opinion-invocation-and-slug-cap).
`/hm:metrics` carries only a cost annotation for second opinion
(`metrics.md.j2:237`) — no acceptance-rate panel. **The acceptance rate is currently
not recorded anywhere.**

**Non-termination (this is the "끝이 안남" mechanism):** `max_review_rounds` (default 3,
`review.md.j2:68`) bounds the round *count*, but the Auto-Fix Loop's step 4
(`review.md.j2:492`) says only "re-spawn ONLY reviewers whose scope was touched by
applied fixes" — **it never says what happens to the cross-model voters.** Step 3.5
lives under `## Procedure — Round 1 (initial review)` (`review.md.j2:100`), while
step 5 says "Recompute grade … (Step 4 consensus filter again)". Both readings are
defective:

- **(a) not re-invoked** → after round 1 the voter pool shrinks from N to Claude-only.
  A finding that reached `consensus-passed` *only* because a model supplied the second
  voice can never be re-confirmed nor cleared; on recompute it degrades to
  `manual-only`, which **does not lower the grade** (`review.md.j2:408`) — so the letter
  improves while the defect stands. It surfaces only as `unverified_severe` →
  `human_review_needed`, which in **loop mode explicitly does not halt**
  (`review.md.j2:448-452`).
- **(b) re-invoked** → a **fresh stochastic voter every round**. Each call is a new model
  run against changed code, so novel findings appear each round; "Remaining / New issues
  introduced" (`review.md.j2:507`) never drains. The loop then exhausts
  `max_review_rounds` and exits `CHANGES_REQUESTED` — terminating by *cap*, never by
  *convergence*. That is exactly the reported symptom.

**And the loop layer amplifies (b):** `/hm:loop` improve-mode runs the 4-gate
convergence check **every iter** (`loop.md.j2:694`) and Gate 1 includes
"review grade ≥ B" (standard) or "= A" (thorough) (`loop.md.j2:210-238`). A review whose
grade is a moving target means `convergence_streak` never accumulates.

**Precedent for the missing bound already exists in-repo:** the plan stage caps its own
re-validate explicitly — "re-run validator **once only** (no infinite loop)"
(`plan.md.j2:557`).

### Approach A — Port PIDA to the review path

| Field | Content |
|---|---|
| Approach | Every Step-3.5 finding must be dispositioned `KEEP`/`REFUTE` by a Claude verifier *before* it becomes a Step-4 voter; `unresolved` → `manual-only`, never auto-fix eligible. |
| Assumption | The plan stage's PIDA prose transfers to review (review *does* have a test oracle — `pytest`/`ruff`/`mypy` — so fewer `unresolved` than plan). |
| Evidence | `plan-validator_body.md.j2:116-125` (protocol exists, shipped); `codex_ledger.py:46` (disposition enum already models the outcomes); review's Pass 1.5 `code-verifier` is a reduce-only agent that already does exactly this shape for Claude findings. |
| Trade-off | One extra verifier pass per review round (context + latency). Requires deciding whether `unresolved` feeds `unverified_severe` (blocking interactive) or stays silent. |
| Compatibility | High — reuses the existing `code-verifier` agent shape and the existing ledger enum. Prose + one agent invocation; no schema change. |
| Risk | medium — a reduce-only Claude verifier judging a cross-model finding re-introduces the single-model blind spot that second opinion exists to cover (see Pitfalls #2). |

### Approach B — Freeze the cross-model vote at round 1 (idempotent voter)

| Field | Content |
|---|---|
| Approach | Invoke each enabled model **exactly once per `/hm:review` invocation**. Carry its adapted findings forward as fixed records across rounds 2..N; mark one `resolved` when an applied fix touches its `file:line` (or its matched symbol). No new model findings after round 1. |
| Assumption | A model's round-1 finding set is a sufficient sample; confirming the *fix* is the verify stage's job, not a re-vote's. |
| Evidence | `review.md.j2:100` already scopes Step 3.5 under "Round 1 (initial review)" — B makes the existing structure explicit rather than inventing a rule. `plan.md.j2:557` is the in-repo precedent for a hard "once only" bound. |
| Trade-off | The model never sees the fixed code, so it cannot confirm or retract; a fix that half-addresses its finding is not caught until `/hm:verify`. Also caps cost at 1 call/model/review (Production currently pays per round). |
| Compatibility | Highest — prose-only edit to `review.md.j2` (Step 3.5 heading scope + a "carry-forward, do not re-invoke" clause in Auto-Fix Loop step 4). Python change: none. |
| Risk | low |

### Approach C — Per-finding disposition ledger + acceptance-rate metric

| Field | Content |
|---|---|
| Approach | Restore one ledger row **per finding disposition** (in addition to the per-call row), and add a `/hm:metrics` panel: per-model accept / reject / duplicate / unresolved counts and accept-rate. |
| Assumption | The user's question ("too easily?") is empirical and currently unanswerable. |
| Evidence | `codex_ledger.py:43-47` already declares `finding_ref` + the 4-value `disposition` enum — the capability was designed and is now unused on the review path (CLAUDE.md notes the row semantics changed to per-call). `metrics.md.j2:237` has cost only. |
| Trade-off | Changes no behavior — it is instrumentation, so it does not by itself stop the loop or tighten acceptance. Requires a distinct denominator from the existing skip-rate (CLAUDE.md already warns the skip-rate denominator changed and that `stage: "health"` rows must be excluded). |
| Compatibility | High — schema already supports it; one writer call site + one metrics panel. |
| Risk | low |

## ⚠️ Pitfalls

1. **The Step-4a relaxation is not an accident — do not naively tighten it.** ADR-001
   added it precisely because without it every null-location second-opinion finding
   degrades to `manual-only` and the vote becomes cosmetic (`review.md.j2:345-346`).
   Reverting it re-creates the bug it fixed. Any tightening must keep null-location
   findings *votable* while making them *refutable*.
2. **A friction-looking guard can be load-bearing.** `[fail:design]
   friction-looking-guard-was-load-bearing-safety` — a per-session relaxation of the
   worktree queue-guard passed a Grade-A review and was then reverted after a k-of-3
   re-review found it re-opened a count:3 contamination. The lesson applies directly
   here: recall-favoring K=2 may be compensating for the *absence* of a review-path
   refutation gate. **Tighten K and add the gate in the same change, or neither** —
   tightening K alone lowers recall with no compensating precision mechanism.
3. **Do not calibrate any threshold on pre-0.44 ledger data.** `[fail:tooling]
   agy-print-flag-swallows-next-flag` — until 2026-07-25 the antigravity recipe ran
   `agy --print --sandbox …`, so `--sandbox` was consumed as the prompt and **every
   antigravity vote this harness ever cast was vacuous**, recorded as
   `status: failed`. Any historical impression of "the models agree a lot" is
   codex-only. C must gather fresh data before A picks a number.
4. **Render-grep tests on this prose are brittle.** `[fail:test]
   test-pins-retired-implementation-name` (count:3) — assertions pinning a literal
   string in these templates go false-RED when a correct rewrite moves the string.
   Gate on an observable (e.g. "the rendered Auto-Fix Loop contains a
   do-not-re-invoke clause reachable from Step 3.5's model list"), not on a sentence.
5. **Inference, not verified — `scope_aware_consensus` may false-merge null-location
   findings.** `conditional_router.py:57-68` groups by the **exact** key
   `f"{file}:{line}:{severity}"` and promotes to `consensus-passed` when
   `len(reviewers) >= 2`. Two *unrelated* null-location findings (one codex, one
   antigravity) at the same severity produce the identical key `None:None:P0` →
   `consensus-passed`, and `merged = dict(group[0])` **discards every other finding in
   the group**. Preconditions I did not verify: that the `consensus-arbiter` path
   (`consensus-arbiter_body.md.j2:64` is the only caller) is actually engaged for
   second-opinion findings, and that the adapted findings carry `reviewer` set to the
   model name (the adapter emits `source`, and Step 4 is executed as LLM prose). If
   both hold, this is a false-accept **and** a silent-loss path.
6. **Tag-vocabulary divergence.** The Step 4d table (`review.md.j2:368-372`) lists only
   `consensus-passed` / `weak-consensus` / `manual-only`, but the Python helper also
   emits **`scope-exempted`**, documented as "treated as valid, auto-fix eligible" for a
   *single*-reviewer finding (`conditional_router.py:47-51`, `:79-81`). A lone finding
   being auto-fix eligible contradicts the prose table. (For a model name,
   `REVIEWER_SCOPES.get("codex", [])` is empty → `is_in_reviewer_scope` returns False
   → `manual-only`, so the current risk is confined to Claude reviewers — but the two
   surfaces disagree and one of them is wrong.)
7. **`human_review_needed` has no runtime reader on the loop path** — an accepted
   limitation (ADR-003, `review.md.j2:448-452`). Do not design a fix whose safety
   depends on that flag stopping anything during `/hm:loop`.

## ❓ Open Questions

1. **Is Step 3.5 intended to re-run in rounds 2..N?** The template does not say, and
   the two readings have opposite failure modes (see Diagnosis). This is a decision,
   not something to infer — it is the single question that determines whether B is
   "make explicit" or "change behavior".
2. **Should an `unresolved` second-opinion finding feed `unverified_severe`?** If yes,
   interactive runs STOP more often; if no, it is invisible in loop mode (pitfall #7).
3. **Does K stay 2 when the pool contains ≥2 non-Claude voters?** i.e. should
   `consensus-passed` require **at least one Claude voice**? This is the literal crux of
   "너무 쉽게 받아들이는 건 아닌지". ADR-006 fixed K=2 deliberately; changing it needs
   an ADR that supersedes it.
4. **Cost ceiling per `/hm:review`.** Production currently mandates every enabled model
   on every review; if models re-run per round, worst case is
   `len(models) × max_review_rounds` calls. What is the acceptable ceiling?
5. **Where does the fix live?** B is prose-only (`review.md.j2`); C touches the ledger
   writer (Python) + `metrics.md.j2`; A adds an agent invocation. Confirm the intended
   split before `/hm:plan` writes phases.
6. **Verify pitfall #5's preconditions** — is `scope_aware_consensus` on the live
   second-opinion path at all, or is Step 4 purely LLM prose? Determines whether that
   false-merge is a real bug or dead code.

## 📚 Sources

No external sources consulted — the question is entirely about this repository's own
review/plan templates and consensus helpers, where the code is authoritative. Every
claim above cites a file:line in this repo or is explicitly labeled as inference
(pitfalls #5, #6).

Internal code citations:
- `src/harness_maker/templates/stages/review.md.j2` — 68, 100, 168-298, 300-324, 337-347, 368-372, 401-416, 428-466, 468-510
- `src/harness_maker/templates/stages/plan.md.j2` — 510-543, 550, 557, 562
- `src/harness_maker/templates/agents/plan-validator_body.md.j2` — 107-125
- `src/harness_maker/templates/agents/_partials/second_opinion_dispatch.md.j2` — whole file
- `src/harness_maker/conditional_router.py` — 23-38, 41-92
- `src/harness_maker/codex_ledger.py` — 31-47
- `src/harness_maker/models.py` — 509-535
- `src/harness_maker/templates/commands/hm/loop.md.j2` — 210-238, 694
- `src/harness_maker/templates/commands/hm/metrics.md.j2` — 237
- `CLAUDE.md` — "Cross-model second opinion (multi-model)" block (ledger row semantics, ADR-006 K=2, ADR-008 output contract)

## 🔗 Related Internal Docs

- [[PLAN-second-opinion-multi-model]] — ADR-006 (K=2 fixed), ADR-003 (mandatory matrix), ADR-008 (output contract)
- [[PLAN-second-opinion-invocation-and-slug-cap]] — ADR-001 (invoker owns both CLIs), ADR-008 (7-branch degrade matrix), per-call ledger row
- [[PLAN-crossmodel-codex-gaps]] — ADR-004 (PIDA debate flow on the plan path)
- [[fail:design friction-looking-guard-was-load-bearing-safety]] — trace a guard at runtime before relaxing it (pitfall #2)
- [[fail:tooling agy-print-flag-swallows-next-flag]] — every pre-0.44 antigravity vote was vacuous (pitfall #3)
- [[fail:test test-pins-retired-implementation-name]] — false-RED from pinning template literals (pitfall #4)
- [[fail:design degraded-fallback-can-reintroduce-the-very-bug-it-guards]] — a later review can correctly reverse an earlier one; record supersedes explicitly
