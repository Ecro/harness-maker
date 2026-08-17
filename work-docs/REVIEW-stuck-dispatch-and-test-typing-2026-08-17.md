---
type: review
task_slug: stuck-dispatch-and-test-typing
status: APPROVED
created: 2026-08-17
reviewers_invoked: [code-reviewer, security-reviewer, concurrency-reviewer, test-reviewer, codex, antigravity]
consensus_method: cross-check
review_base: ea8087ff (working tree vs HEAD)
run_id: 20260817T0633Z
drift_verdict:
  result: clean
  scope_violations: []
  scenario_misses: []
  task_slug: stuck-dispatch-and-test-typing
  computed_at: 2026-08-17T06:33:00Z
  note: >-
    No PLAN or SPEC exists for this slug — the work was an ad-hoc fix plus a typing sweep, not a
    /hm:plan task. Scope drift is therefore undecidable rather than clean; recorded as clean with
    this caveat so wrapup and verify are not blocked by a document that was never written.
---

# Review: stuck-dispatch-and-test-typing

**Declared deviation.** The change under review is uncommitted in the **base** working tree. The
stage's `task-preflight` would have created a worktree from base HEAD, which contains none of it,
so the review ran in base. `review_base` is `HEAD` (`ea8087ff`); `freeze resolve-base` returned
`474245dd`, one commit earlier, and was not used — `ea8087ff` is an already-landed re-render, not
part of this work.

**Second deviation.** The cross-model prompt files were built with shell redirection
(`{ printf …; cat diff; } > $tmp`) rather than the Write tool. The diff is 232 KB; routing it
through Write would have loaded it into the orchestrator's context for no benefit. Redirection
performs no expansion of the redirected bytes, so the injection concern the stage raises about
`echo '<json>' |` does not apply.

## 🎯 Round 1 Summary

**Grade: D** — 1 P0 and 8 P1 consensus-passed findings. All were introduced by this change; none
are pre-existing defects the change merely touched.

Lens coverage: all 7 exercised (`design, functionality, robustness, consistency, security,
concurrency, tests`), `blocks_approval: false`.

The single most important result: **four independent lenses converged on a defect the full test
suite could not see** — the brief instructed `stuck` to write a file it has no tool for. Every
test was green, `mypy --strict` was clean on 648 files, and the escalation this change exists to
deliver would have surfaced a path to a file that was never created on 100% of Claude Code
blocker runs.

## 🔍 Drift Findings

None. See the `drift_verdict` caveat in the frontmatter.

## ✅ Consensus Findings

Per ADR-007 one reviewer-lens voice is sovereign, so each of these is `consensus-passed`. The
voice count is recorded because convergence is the signal worth keeping.

| # | Sev | Voices | Finding |
|---|---|---|---|
| 1 | **P0** | 4 | Brief orders `stuck` to Write the escalation note and return its path; `stuck.md.j2` grants `tools: Read, Grep, Glob`. On Claude Code the write cannot execute, so the stage surfaces a path to a nonexistent file. `stuck_body.md.j2` Step 5 carried the same dead instruction, and nothing in this repo has ever read `.claude/memory/escalations/`. |
| 2 | P1 | 2 | The gate's order assertion measured a **bullet** containing "Dispatch `stuck`", not the dispatch site. It was green on a template whose fenced call sat six lines BELOW the surface step — the exact arrangement the gate's own docstring says it rejects. |
| 3 | P1 | 2 | Attributed baseline movement was wrong: `+1373` claimed against `+1136` measured by the machine-generated baseline. Root cause found by measurement, not argument — the ratchet's base `41222` was already stale by 237 chars. |
| 4 | P1 | 2 | No CI gate for the test tree's typing. `ci/nightly/release` all ran `mypy --strict src`, so the 616→0 sweep would have rotted on the first unannotated helper. |
| 5 | P1 | 1 | `dispatch_intro()` and the fenced call rendered **outside** the blocked conditional, so a run exiting Step 4 GREEN read an unqualified "Dispatch each item below" imperative. |
| 6 | P1 | 2 | "Skip only if it dies" was the only degrade clause — undefined in observable terms, and on Codex it contradicts the join contract's rule that a silent agent is not a failed one. A blocked run could withhold the failure output indefinitely. |
| 7 | P1 | 1 | The brief interpolates verbatim repo-controlled text (test stderr, ADR bodies) into a sub-agent prompt whose reply is surfaced to the user, with none of the untrusted-data framing every sibling dispatch uses. |
| 8 | P1 | 1 | The docstring / delta doc / CHANGELOG claimed "a token check would have been green through the whole period this defect shipped". **False**: the rendered `execute.md` at HEAD contains `stuck` zero times. |
| 9 | P1 | 1 | The gate's advisory check had been relaxed until one template clause satisfied both of its conjuncts, so no mutation could red the decider-naming half alone. |
| 10 | P2 | 2 | Three `monkeypatch` **spy** sites were rewritten from module-attribute to bare-module targets. No race (verified: identical singletons, suite is serial), but a spy whose assertion passes on zero calls loses its guard against a silently vacuous pass. |
| 11 | P2 | 2 | Doc errors: `_ROUND_TRIPS` names no symbol (it is `_CLAUDE_ROUND_TRIPS`); "both rendered Codex surfaces" — there is one per stage; "all three targets" — three documents, two target variants. |
| 12 | P2 | 3 | Typing-sweep widenings that erased checking rather than expressing it: `Confidence.HIGH == "high"` → a duplicate of a sibling assertion; `_bp() -> Any`; two `readiness` `_find` helpers keeping a suppression their siblings do not have; `AC004_ROWS` shape. |

## ⚠️ Weak Consensus

None.

## 📝 Manual-Only Findings

Cross-model (`codex`) findings with a single voice and no agreeing lens:

- P3 `pyproject.toml` — the `regenerate` override makes that module `Any` at its two call sites.
  Accepted as documented scope, not fixed: the alternative (per-site `# type: ignore`) trades one
  narrow suppression for two.
- P3 `tests/unit/test_review_telemetry_{confirm,churn}.py` — `list[Any]` on the pydantic
  `ErrorDetails` helper. Left as-is; the concrete type is a pydantic internal.

## 🤝 Disagreements

None across tiers. The concurrency lens and the security lens reached **opposite conclusions on
the same monkeypatch rewrite** — concurrency verified no race is introduced (identical module
singletons; `addopts` and all three CI invocations are serial; xdist workers are separate
processes), while security wanted the old form restored. Both are right about different
properties, and the applied fix (dotted-string target) satisfies both.

## 🧊 Cross-model findings (frozen @ round 1)

| model | status | note |
|---|---|---|
| `codex` | invoked | 5 findings, all P2/P3 widening/scope observations. One (`Confidence`) was independently raised by two lenses and fixed; the rest are recorded above as manual-only. |
| `antigravity` | **failed** | `agy` returned `status: SUCCESS` with an empty `response` and no `structured_output`. Known intermittent behaviour on large prompts; warn-and-proceed per `failure_policy`. No voice cast. |

### Iteration 2 (Grade: D → A)

Fixes applied: 12 (every consensus-passed finding from round 1)

| # | Severity | Summary | Status |
|---|----------|---------|--------|
| 1 | P0 | `stuck` Write/tools mismatch | Applied — note returned inline; `stuck_body` Step 5, Hard Rules, agent description and `synthesize.py` description all corrected |
| 2 | P1 | order assertion measured a bullet | Applied — reads `_DISPATCH_STUCK`'s offset; mutation-verified (moving the fence below the surface step turns it red, which the old assertion accepted) |
| 3 | P1 | wrong attributed movement | Applied — both endpoints measured; stale base recorded |
| 4 | P1 | no CI gate for test typing | Applied — `mypy --strict src tests` in ci/nightly/release (parity comment honoured) |
| 5 | P1 | dispatch rendered unconditionally | Applied — four numbered steps under a blocked-path-only sentence |
| 6 | P1 | unbounded degrade | Applied — `[stuck] unavailable` branch |
| 7 | P1 | no untrusted-data framing | Applied — the `wrapup.md.j2` clause |
| 8 | P1 | false "token check" justification | Applied — withdrawn in all three places |
| 9 | P1 | advisory conjuncts collapsed | Applied — split into two properties on different loci |
| 10 | P2 | spy vacuity | Applied — three sites back to dotted-string targets |
| 11 | P2 | doc-name errors | Applied |
| 12 | P2 | typing widenings that erased checking | Applied — `tag_finding` widened to `Sequence[object]` at the source instead |

Re-review verdict: **6 of 9 fully resolved, 3 new P2s**, all applied in the same round:

| # | Severity | Summary | Status |
|---|----------|---------|--------|
| 13 | P2 | `docs/HOW-IT-WORKS{,.ko}.md` still documented the removed file write (3 places each + a tree node) | Applied |
| 14 | P2 | "Everything under this heading" pointed at `### Step 4`, which also spans the GREEN exit | Applied — "the four steps below" |
| 15 | P2 | degrade list omitted the *has not answered* case the Codex join contract forbids calling a failure | Applied — fourth arm added |

Remaining: 0 | New issues introduced: 0
Churn: not measured (`review_churn` pins were not taken — the round ran outside a task worktree;
recorded as unmeasured rather than as zero).

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | D     | —             | 12        | —   |
| 2         | **A** | 15            | 0         | 3   |

Final grade: **A**
Iterations used: 2 / 3
Exit reason: converged
Status: APPROVED
human_review_needed: false

No `manual-only` or `weak-consensus` finding sits at P0/P1 (the two manual-only items are P3
scope observations from `codex`), so `unverified_severe` is false.

Verification after the final round: `ruff check`, `ruff format --check`, `mypy --strict src tests`
(648 files) all green; full pytest green with zero failures.

## Notes for the next reader

The result worth carrying forward is not the finding count. It is that **a change with a green
full suite, a green `mypy --strict` over 648 files, a dedicated structural gate, and a
mutation receipt still shipped a P0** — the escalation this change exists to deliver would have
handed the user a path to a file that cannot exist, on every Claude Code blocker run. Four lenses
found it independently; no automated check in this repo could have. The gate's own order
assertion was simultaneously green on a template arrangement its docstring said it rejected.

Two mechanisms did the work, and both are cheap: **measure both endpoints** (that is what turned
"the attribution looks off" into a proven 237-char stale base), and **dispatch lenses that do not
share a rubric** (the security and concurrency lenses reached opposite conclusions about the same
monkeypatch rewrite, and the fix satisfies both).
