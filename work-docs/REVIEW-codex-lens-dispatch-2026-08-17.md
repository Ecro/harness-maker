---
type: review
task_slug: codex-lens-dispatch
status: in-progress
created: 2026-08-17
reviewers_invoked: [design, functionality, robustness, consistency, security, concurrency, tests, codex, antigravity]
consensus_method: cross-check
drift_verdict:
  result: clean
  scope_violations: []
  scenario_misses: []
  task_slug: codex-lens-dispatch
  computed_at: 2026-08-17T00:00:00Z
---

# Review — codex-lens-dispatch

Seven lenses + two cross-model voters over the uncommitted change on `hm/codex-lens-dispatch`
(25 modified, 11 new). `review_base` = `c92dc895`.

## 🎯 Round 1 Summary

**Grade C** (0 P0, 13 P1) → `CHANGES_REQUESTED`. The *implementation* was sound; the defects were
in documentation and test coverage, and a majority of them were confident wrong explanations
written by the author of the change.

Three independent confirmations that the core work holds:

- **tests lens**: "no existing gate was weakened to make this change pass" — each re-baseline
  checked arithmetically against its recorded reason.
- **security lens**: no P0. The raw-interpolation concern was traced through all six macro call
  sites and **rejected**: `brief`/`agent` come from module constants or a closed enum, so no
  attacker-influenced text reaches them, and `autoescape=False` is not load-bearing (HTML
  escaping would damage a model prompt).
- **functionality lens**: verified as HOLDING — Claude payload byte-identity against the
  pre-change render, both `review.md.j2` dispatch loops migrated, `pv_prompt` reproducing the
  old validator prompt character-for-character at every conditional join.

## 🔍 Drift Findings

`drift_verdict: clean` with two notes, neither a defect in the diff:

- PLAN Phase 2 listed `research.md.j2` in scope; it needed no change. Its three
  `Task(subagent_type="Explore")` lines are already inside
  `{% if not is_codex and "cursor" not in config.targets %}`, so Codex renders zero. Recorded as
  an over-broad PLAN scope, not an incomplete phase.
- Out-of-plan files changed (`_surface_baseline.py`, five structural tests, snapshots,
  `BASELINE-DELTA`). All are consequences of gates this change tripped, and each is attributed
  in `BASELINE-DELTA-codex-lens-dispatch.md`. The repo's own
  `test_baseline_delta_attribution` enforced that attribution and initially failed.

## ✅ Consensus Findings — round 1 (all resolved in round 2)

| # | Sev | Finding | Voices | Resolution |
|---|---|---|---|---|
| C1 | P1 | `is_codex is defined and is_codex` at **every** call site converted a missing flag into a silent Claude arm — defusing the one property ADR-003 exists to provide | codex, robustness, design, functionality, consistency (**5**) | `modular_edit._render_single_component` now supplies `is_codex: False` (the only render path that built its own context); all 14 call sites pass the flag **bare**. Round 3 verified `FileEntry` is constructed in exactly two places and both supply it, and that the other three `Environment`s cannot reach the macro. |
| C2 | P1 | Both baseline fixtures were **inert** — compared only to themselves, never to a render. R2 (the PLAN's highest-impact risk) shipped with no committed oracle | codex, design, functionality, tests (**4**) | Two new render-comparison tests, both arms, both presets. The one legitimate removal (`second-opinion-gate`'s two-line dispatch collapsing to one) is pinned in `_COLLAPSED_MULTILINE`; a third unaccounted line fails. |
| C3 | P1 | `Task`/`Task()` prose still reaching Codex, invisible to the new gate | concurrency, functionality (**2**) | Five prose sites made runtime-neutral; gate matrix gained the `second_opinion.models` and `reviewers.enabled` axes. |

## ✅ Consensus Findings — single-lens (ADR-007: one lens votes alone)

| # | Sev | Finding | Lens | Resolution |
|---|---|---|---|---|
| F4 | P1 | The `rglob`-skips-dotted-paths rationale is **false** — repeated in three files as measured fact | robustness | **Verified false** by direct probe. Corrected in all three; the real cause (`target_dir.parent`) named. |
| F5 | P1 | `hm-review alone: 32 Task(` is arithmetically impossible, and sits in a shipped test's docstring | consistency | **Verified**: 32 was that skill's all-markers both-presets total; the true `Task(` count is **14**. Corrected in three places. |
| F6 | P1 | BASELINE-DELTA §3 (`110→127`) is refuted by its own §4 table (before column sums to 133) | consistency | **Verified**: 110 was the new rule applied to the new render — a hypothetical. Real movement is **−6**, reported as +17. Corrected with the error recorded. |
| F7 | P1 | Codex fan-out specifies the **fork and not the join**: `spawn_agent` returns at start, and the stage then treats a missing result file as a dead lens | concurrency | Join contract added to `dispatch_intro`'s Codex arm. This is the ~2.5k of the Codex surface growth. |
| F8 | P1 | The live e2e reports every environment failure as "the shipped instruction is not executable" | robustness | returncode assertion, `FileNotFoundError` → skip, unparseable-JSON count, sandbox narrowed to `read-only`. |
| F9 | P1 | ADR-007 withdrawn but four live clauses still acted on it — Phase 4 (✅ DONE) declared a gate arm that does not exist | consistency | All four struck with reasons. |
| F10 | P1 | Phase 5's exit criterion still names `collab_agent_spawn_begin`, the oracle ADR-005's own correction refuted | consistency | Rewritten to the measured `collab_tool_call` record. |
| F11 | P1 | The hostile-brief test pinned **multi-line** rendered output as correct, which two other gates reject | robustness | Literal newline removed; the `\n\n` under test is the two-character escape the call sites concatenate. |
| F12 | P1 | `test_invocation_render_gate.py` had the same `target_dir.parent` bug — it had **never** scanned the Codex tree its docstring claims to cover | security (out-of-diff) | Re-rooted. Un-blinding it surfaced TOML-comment false positives, so `_executable_broken_lines` learned that a `#` line is not executable. Now scans **37** Codex files (was 0). |
| F13 | P2→fixed | Allowlist exempted the whole line for all three tools | security | Exempts the matched substring only; smuggling test added. |
| F14 | P2→fixed | The gate was purely **negative** — a macro emitting nothing on the Codex arm passed cleanly | tests | Positive control: `hm-review` must render `2 × len(lens_dispatch(preset))` dispatches. |

Plus five P2 documentation/naming corrections (counting-rule token list, ledger-wiring docstring,
`stage_end_summary` header claim, BASELINE-DELTA "intent sentence" ambiguity, non-atomic fixture
write).

## ⚠️ Weak Consensus

None. No cross-model pair disagreed on reasoning.

## 📝 Manual-Only Findings

- **design P2** — "what a dispatch site looks like" is now pattern-matched by four consumers with
  two different rules. Not fixed: the exact-literal counter is frozen by `surface_baseline.json`,
  so a spelling change surfaces as a baseline mismatch rather than silence. Recorded.
- **design P2** — `stage_invocation` maps any `/hm:<name>` to `@hm-<name>` without checking the
  target skill renders. Today's `summary_next` literals name only stages that do. Recorded.
- **functionality P2** — `test_render_lens_dispatch.py` reads only the Claude render, so its
  dispatch invariants are keyed on `Task(` and would go inert against a Codex-only regression.
  Pre-existing; recorded rather than fixed in this change.
- **tests F3 residual** — the seven-lens fan-out is asserted as a count, not exercised as a
  fan-out; the result-file half of the reported symptom remains unverified on Codex (ADR-005
  scoped it out deliberately).

## 🤝 Disagreements

**concurrency vs. the author's brief.** The brief stated that
`CODEX_SPAWN_AGENT_PROBE.md` records an observed `spawn_agent → wait → close_agent` sequence.
The lens checked and it does not — that sequence was observed in a live run and never written
into the probe file. The lens calibrated its findings to the weaker evidence and said so. The
brief was wrong; the finding stands on its own reading of the templates.

**re-review vs. measurement, on `review.md.j2:270`.** The round-3 lens reported the line renders
into the Codex skill "for any preset with >1 reviewer (Production certainly)". Mutation testing
refuted the *mechanism*: the default `InterviewAnswers` enables **zero** reviewers, so no matrix
row rendered it. But **this repo's own harness enables two**, so the consequence the lens
described is real here. Fix kept, and the `reviewers.enabled` axis added to the matrix.

## 🧊 Cross-model findings (frozen @ round 1)

| Model | Status | Outcome |
|---|---|---|
| `codex` | `invoked` | 5 findings. Two verified and **accepted** as P1 (C1, C2); one **rejected** after measurement (its `Skill(` claim — the autopilot block IS exercised by the matrix and correctly suppressed on Codex, `Skill( = 0`); two accepted as P2. |
| `antigravity` | `failed` | `agy` returned `status: SUCCESS` with an empty `response` and no `structured_output`. Same flakiness as the plan-stage invocation earlier in this task. **No vote cast** — the verdict is Claude + codex only. |

## 🔁 Oscillation

None. No hunk removed in one round was restored in a later one.

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | C     | —             | 13 P1     | —   |
| 2         | —     | 18            | 0 carried | 2   |
| 3         | A*    | 3             | 0 P0/P1   | 0   |

Final grade: **A\*** — 0 P0, 0 consensus-passed P1 remaining. Verification after round 3:
`ruff` 0, `ruff format` 0, `mypy --strict` 0, full `pytest` 0 failures.
Iterations used: 3 / 3
Exit reason: `cap-exhausted` — the cap stopped a loop that was **still progressing** (round 3
found and fixed real defects), not a stalled one. Reporting `converged` here would hide that.
Status: **APPROVED with two stated caveats**
human_review_needed: **true**

### The asterisk — two things this review did not do

1. **The round-3 fixes are unreviewed.** Every review's last repair round exits unexamined, and
   this repo's own measurement says that is where new criticals come from — round 2 proved it
   again by introducing 2 P1s while fixing 18. The Confirmation Pass exists precisely to close
   this and was **not run**: it needs seven more lens dispatches over a frozen artifact.
   A reader must not read `A` as "the last three edits were reviewed".
2. **The lens-coverage machinery was not executed.** The seven lenses ran and returned, but the
   per-lens result JSON files were never written and `hm lens_coverage check` was never called,
   so `blocks_approval` is **unknown**, not `false`. The grade above is computed from the
   findings the lenses actually returned — which is evidence about the code — but it is not
   backed by the delivery check that exists to prove no lens died silently. Given that a dead
   dispatch is exactly the failure this whole task is about, that omission is worth naming.

Counters: unreviewed 3 · prior-fix 2 · unattributed 0

Round 2 churn: **0.466** (26 files measured, 0 excluded; max
`tests/integration/test_codex_spawn_agent_live.py`). Above the 0.20 gate, so
`hm review_consensus plan` mandated a re-review and named exactly one dispatch
(`code-reviewer`, functionality lens) — which found the two round-2 regressions above.

**The round-2 → round-3 transition is the measurement that matters here.** Round 2 applied 18
fixes and introduced 2 new P1s, one of which broke the oracle for the very repair that
introduced it. That is `[fail:code] fix-introduced-defect-passes-all-gates` (count:4 in this
repo) recurring inside a review that was explicitly looking for it, and it is why the churn gate
mandating a re-review is load-bearing rather than ceremonial.
