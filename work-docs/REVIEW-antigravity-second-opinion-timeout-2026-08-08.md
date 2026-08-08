---
type: review
task_slug: antigravity-second-opinion-timeout
status: APPROVED
created: 2026-08-08
reviewers_invoked: [code-reviewer, security-reviewer, codex, antigravity]
consensus_method: cross-check
grade: A
human_review_needed: false
drift_verdict:
  # `clean`: every changed file falls inside some PLAN phase's scope, and there is no
  # SPEC, so neither failure value applies. The incomplete phase below is recorded in its
  # own field because the enum has no value for it — calling it a scope_violation would
  # make verify and wrapup read a violation that did not happen.
  result: clean
  scope_violations: []
  scenario_misses: []
  incomplete_phases:
    - "src/harness_maker/codex_adapter.py — named in PLAN Phase 2 Scope-in (new `extract_agy_envelope`) and in the Affected-components table for Phases 2 and 5, but the file is UNCHANGED and no such helper exists; the logic was inlined into second_opinion_invoke.py"
  task_slug: antigravity-second-opinion-timeout
  computed_at: 2026-08-08T00:00:00Z
---

# REVIEW — antigravity-second-opinion-timeout (Round 1)

## 🎯 Round 1 Summary

**Grade A** (consensus-passed P0 = 0, P1 = 0) — but **`human_review_needed: true`**.

The letter is A because **no finding reached K=2**. That is not the same as "no
severe findings": four P1s were raised, each by exactly one voter, at four
different locations, so none could surface-match another. The grade formula
counts only `consensus-passed`, and the `unverified_severe` scan exists for
precisely this shape.

**Voter pool was N=3, not the configured 4.** `antigravity` skipped with
`exit 1: Error: timeout waiting for response` — the base repo's `harness.yaml`
still pins the retired `Gemini 3.1 Pro (High)` tier, because Phase 6's config
change lives on this task branch and has not landed. **The review of the timeout
fix was itself degraded by the timeout the fix removes.** That is a faithful
demonstration of the defect, not an incidental annoyance, and it means one voice
was missing from every consensus decision below.

## 🔍 Drift Findings

**P1 — incomplete phase.** PLAN Phase 2's Scope-in names a new
`extract_agy_envelope` helper in `codex_adapter.py`, and the Affected-components
table assigns that file changes for Phases 2 and 5. `codex_adapter.py` is
**unchanged** and no such helper exists — the envelope handling was inlined into
`second_opinion_invoke.py` instead.

Assessment: the inlining is defensible (the branch logic is tightly coupled to
`invoke()`'s status matrix and needs `done()`), but the PLAN was not updated to
say so, so the deliverable does not match its own scope statement. No scope
*violation* — every changed file is in some phase's scope.

## ✅ Consensus Findings

**None.** No pair of findings satisfied surface match (same file, line ±5, same
severity tier). With one voter lost to timeout and four P1s at four distinct
locations, K=2 was unreachable. This section being empty is the reason the grade
is A and the reason `human_review_needed` is true.

## ⚠️ Weak Consensus

**None** by the strict definition. One near-miss is recorded honestly rather than
promoted:

- `_packaged_schema` leaks its `mkstemp` file when the subsequent write raises.
  `code-reviewer` filed it as **P2** at line 214; `security-reviewer`
  independently observed the same mechanism at line 215 but recorded it under
  `verified_clean` as *"Residual nit, not filed"*. Same file, same defect, same
  reasoning — but Step 4a requires a matching severity tier, and "not filed" is
  not P2. Counting it as consensus would inflate the metric on a severity
  disagreement, so it stays `manual-only` with the corroboration noted here.

## 📝 Manual-Only Findings

### P1 — unfenced untrusted model text (security-reviewer)
`src/harness_maker/second_opinion_invoke.py:600`

The new case-2 branch interpolates `envelope["response"]` — model-authored text —
straight into the `reason` with neither the data fence nor the printable-character
filter that the sibling handler at :655-676 applies and that the module's own
comment calls mandatory (*"C0/C1 controls are dropped so no escape sequence
reaches a terminal raw"*). `_clip` only collapses whitespace; `\x1b`, `\x07`,
`\x00` are not whitespace and survive. The string reaches both the operator's
turn output (as harness voice) and `skip_reason` in the ledger, unredacted.

**Verified directly against the code by the orchestrator.** Introduced by this
change.

### P1 — advisory text misattributes on review/plan (code-reviewer)
`src/harness_maker/second_opinion_invoke.py:92`

`budget_advisory_message` hardcodes *"A trivial smoke this close to the cap means
real review-sized prompts are already failing"*, but `main()` gates emission on
`args.model == "antigravity"` only — not on `args.stage`. A real `/hm:review` or
`/hm:plan` call crossing 60 s therefore prints a line claiming a *trivial smoke*
was slow and that real calls are already failing, immediately after a real call
succeeded. In a module whose docstring names misattribution as the defect class
it exists to remove, this is the module reintroducing it. Introduced by this
change.

### P1 — `invoke()` can raise before the never-raise guard (codex)
`src/harness_maker/second_opinion_invoke.py:433`

`root = base_root.resolve() if … else resolve_base_root(Path.cwd())` executes
before the terminal `try`. `Path.resolve()` can raise `OSError` (symlink loop),
so the never-raise contract has a hole and that path writes zero ledger rows.

**Partly misattributed by the reporter**: codex framed it as *"the new duration
setup leaves initialization outside the guard"*. The `root` line is
**pre-existing**; the `time.monotonic()` this change added beside it cannot raise.
The hole is real, the authorship claim is not.

**This is the round's substantive disagreement — see §6.**

### P1 — prompt-unreadable path bypasses the result and ledger contract (codex)
`src/harness_maker/second_opinion_invoke.py:827`

When `--prompt-file` cannot be read, `main()` writes a `skipped` JSON object
directly and returns without calling `invoke()` / `_result()` / `_emit_row()`.
Two consequences: zero ledger rows for that failure class (so skip-rate telemetry
omits exactly it), and — **newly, because of this change** — the emitted object
lacks `duration_s`, which every other path now carries. One entrypoint, two
result shapes. Verified directly against the code by the orchestrator.

### P2 findings (do not affect the grade)

| # | File:line | Source | Summary |
|---|---|---|---|
| 1 | `_partials/second_opinion_antigravity.md.j2:38` | code-reviewer | Rendered partial still tells the LLM agy has no schema flag; the quoted argv at :80 omits the two new flags |
| 2 | `second_opinion_invoke.py:57` | code-reviewer | Orphaned comment fragment left by an edit; sentence starts mid-clause |
| 3 | `tests/unit/test_second_opinion_agy_envelope.py:189` | code-reviewer | Case-1 and case-4b tests assert only `status`; "envelope" comes from the shared channel label so it is present for every schema-mode failure — assertion invariant over the named dimension |
| 4 | `second_opinion_invoke.py:214` | code-reviewer (+ security, unfiled) | `_packaged_schema` leaks its temp file if the write raises; now on the hot antigravity path |
| 5 | `second_opinion_invoke.py:584` | code-reviewer | Bare-payload guard requires BOTH keys absent, so a `structured_output`-bearing, `status`-less envelope falls into the skip branch |
| 6 | `second_opinion_invoke.py:562` | security-reviewer | Cap bounds parse cost, not resident memory (subprocess already buffered); comment overstates scope |
| 7 | `models.py:421` | code-reviewer (folded) | Same stale "antigravity has no equivalent flags" claim ADR-006 was meant to clear; the structural scan only looks for the retired model literal and cannot catch it |

Finding 7 matters beyond its severity: **ADR-006's Phase 5 exit criterion returned
zero hits, and this site still survived.** The `rg` pattern was built from the
phrasings then known; `models.py:421` uses another. The criterion was
machine-decidable but not complete.

## 🤝 Disagreements

**Never-raise contract — codex vs code-reviewer.** codex filed a P1 saying the
contract is violated at :433. code-reviewer stated the opposite in its summary:
*"Contracts 1–4 all hold… every `return` inside `invoke()` goes through
`done()`"*.

Both reasoned correctly about different regions: code-reviewer verified every
return path **inside** the guarded body; codex looked at the line **before** the
`try` opens. The orchestrator read the code and **codex is right** — the
pre-`try` line is genuinely outside the guard. Recorded rather than averaged: a
reviewer that checks the inside of a function and concludes the whole function is
safe is a pattern worth seeing again.

## 🧊 Cross-model findings (frozen @ round 1)

| id | model | severity | file:line | disposition | note |
|---|---|---|---|---|---|
| `9a5ad9e366c819bf` | codex | P1 | `second_opinion_invoke.py:433` | accepted | Hole real; authorship claim ("new duration setup") refuted — that line predates this change |
| `2ceac758bbbe4925` | codex | P1 | `second_opinion_invoke.py:827` | accepted | Verified; `duration_s` omission is newly introduced |

`antigravity`: **skipped** — `exit 1: Error: timeout waiting for response`. Not a
refutation of anything; the model never spoke this round. Cause is known and is
the subject of this very change (base config still on the retired tier until this
branch lands).

## Iteration 2 (Grade: A → A)

Human review was requested and granted: the operator directed that all 11 round-1
findings be fixed and the change re-reviewed. All 11 were applied, each with a
regression test, and `code-reviewer` re-ran against the fixes.

Fixes applied: 11 (4×P1, 7×P2)

| # | Severity | Summary | File | Status |
|---|----------|---------|------|--------|
| 1 | P1 | Fence + strip untrusted model text on the case-2 sink | `second_opinion_invoke.py` | Applied |
| 2 | P1 | Stage-dependent advisory wording | `second_opinion_invoke.py` | Applied |
| 3 | P1 | `Path.resolve()` moved inside the never-raise guard | `second_opinion_invoke.py` | Applied · **incomplete, see R2-1** |
| 4 | P1 | Prompt-unreadable path routed through `_result` | `second_opinion_invoke.py` | Applied |
| 5–11 | P2 | Stale claims ×3, orphan comment, cap-scope comment, temp leak, bare-payload guard, test assertions | various | Applied |

**One fix was wrong on the first attempt and was corrected before re-review.**
P2-5 was first "fixed" as `elif "status" not in envelope:`, which would have
treated a `structured_output`-bearing envelope as a bare payload and failed
validation. The correct change was to narrow the status check to
`is not None and != "SUCCESS"` — an ABSENT status must not read as failure — with
a dedicated test.

### Round-2 findings (1×P1, 6×P2 — all fixed)

| # | Severity | Finding | Resolution |
|---|----------|---------|------------|
| R2-1 | **P1** | Fix 3 was half-closed: the fallback re-called `Path.cwd()`, the very call that may have raised, from a handler itself outside the guard. Production never passes `--root`, so `base_root is None` is the NORMAL path | `Path(".")` at both sites — degraded but total |
| R2-2 | P2 | `stage` had a default, so a future caller could silently re-inherit the smoke wording | Made a required keyword-only argument |
| R2-3 | P2 | Empty-response message asserted SUCCESS + no `structured_output`; the R1 status-guard fix made both falsifiable | Message now built from observed values |
| R2-4 | P2 | `env_status` unbounded in the fenced excerpt — a long value truncates the closing `>>>` | `_clip(…, 60)` + outer `limit=480` |
| R2-5 | P2 | The non-zero-exit stderr sink still emitted raw CLI text — the sibling security-reviewer flagged in round 1 as "the class is half-closed" | Same fence + strip applied |
| R2-6 | P2 | Partial cited the **refuted** `agy --print --sandbox` probe order as sandbox evidence — the order where `--sandbox` was consumed as the prompt | Corrected to the 2026-07-25 re-verified form |
| R2-7 | P2 | Fix 6 (temp-leak unlink) had no discriminating test | Added one that raises inside the write |

`code-reviewer` verified that every other round-2 test discriminates against the
pre-fix behaviour (each fails with a `TypeError`, a `skipped`, a surviving
`\x1b`, or a missing ledger file) — and identified fix 6 as the sole exception,
which R2-7 closed.

## Gates that fired on the review itself

Two guards caught the **orchestrator**, not the code:

1. **`test_review_payload_persisted`** — this stage's own Step 3.4 requires the
   round's merged payload to be persisted; round 1 skipped it. The gate's message
   forbids clearing it by reconstruction (*"the corpus is only useful if its
   entries are captures"*), so round 1 is recorded in `_KNOWN_MISSING` with that
   reason and round 2 was persisted **before** the re-review ran.
2. **Surface baseline / command-size budget** — the prose fixes regrew the
   rendered surface (codex +98). Paid down by compressing the same additions, per
   the zero-headroom rule; never by raising the frozen baseline.

## What this review revealed about the change's own gates

**ADR-006's Phase 5 exit criterion passed vacuously.** It asserted zero `rg` hits
for the stale "agy has no schema" claim, and returned zero while **three sites
survived**. Two independent reasons:

- **Phrase variants** — `models.py` said *"antigravity has no equivalent flags"*,
  which no pattern in the criterion matched.
- **Line wrapping** — `validate_payload`'s docstring said `"agy has no CLI-level"`
  / newline / `"enforcement"`. A line-oriented `rg` cannot match a claim that
  wraps, and the criterion was built entirely from line-oriented patterns.

The criterion was machine-decidable and still incomplete. That is the same shape
as the defect this whole PLAN addresses — a check that returns green about a
surface it cannot actually see.

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | A     | —             | 4×P1, 7×P2 | —  |
| 2         | A     | 18            | 0          | 0  |

Final grade: **A**
Iterations used: 2 / 3
Exit reason: converged
Status: **APPROVED**
human_review_needed: **false** — every round-1 and round-2 P0/P1 was fixed and
re-verified, so no unverified severe finding remains.
Counters: unreviewed 0 · prior-fix 0 · unattributed 0

**Voter-pool caveat, carried forward.** `antigravity` never voted in either
round (`exit 1: Error: timeout waiting for response`) because the base repo still
pins the retired tier until this branch lands. The A therefore rests on
`code-reviewer` + `security-reviewer` + `codex`, and the model this change exists
to repair was structurally unable to review its own repair.
