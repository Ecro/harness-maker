---
type: review
task_slug: review-loop-empirics
status: APPROVED
created: 2026-08-15
reviewers_invoked: [code-reviewer, security-reviewer, codex, antigravity]
consensus_method: cross-check
drift_verdict:
  result: scope_violation
  scope_violations:
    - src/harness_maker/synthesize.py
    - src/harness_maker/interview.py
    - src/harness_maker/templates/harness-yaml/Production.yaml.j2
    - src/harness_maker/templates/harness-yaml/Side.yaml.j2
    - src/harness_maker/review_churn.py
    - tests/structural/surface_baseline.json
  scenario_misses: []
  task_slug: review-loop-empirics
  computed_at: 2026-08-15T00:00:00Z
human_review_needed: true
---

# REVIEW — review-loop-empirics (Phase 0 + Phase 1)

## 🎯 Round 1 Summary

Scope: PLAN Phase 0 (axis pilot, documents only) and Phase 1 (churn-gate config surface + two
`review.md.j2` brief clauses). Grade **B** at round 1 → one auto-fix round → **A**.
Status **APPROVED**, `human_review_needed: true`.

## 🔍 Drift Findings

**P1 — scope_violation, with a recorded rationale.** Phase 1's declared scope named
`models.py` and `presets.py`. The change also touched `synthesize.py`, `interview.py`, both
`harness-yaml/*.j2` templates, added `review_churn.py`, and re-froze
`tests/structural/surface_baseline.json`.

- The first four are the config-plumbing chain the scope implied but did not enumerate: a key on
  `InterviewAnswers` that `synthesize` does not carry and `answers_from_harness_yaml` does not
  read back is not a config surface, it is a dead field. Under-specified PLAN, not drift in intent.
- `surface_baseline.json` is ADR-009, written during this phase and attributed in
  `BASELINE-DELTA-review-loop-empirics.md`.
- `presets.py` is in scope and **did not change** — deliberately deferred to Phase 2 with the lens
  list, recorded in the PLAN's Phase 1 deviation note.

No scenario misses: Phase 1's ACs are AC-012 and AC-017, both covered.

## ✅ Consensus Findings

### P1 — `answers_from_harness_yaml` silently restored the default for a malformed value
`consensus-passed [2/4]` · voices: `codex`, `antigravity` · **FIXED this round**

The reverse mapper dropped a present-but-invalid `rereview_churn_gate` /
`rereview_churn_ratio` out of the `update` dict, so it fell through to the model default with no
diagnostic. `review_churn`'s strict resolvers raise for exactly those inputs, but **the YAML load
path never called them** — so AC-012's "malformed value is a load-time error" was true of the
helper and false of the system. The comment directly above the code claimed the opposite
guarantee.

Both cross-model voters found this independently; neither Claude reviewer rated it P1.

### P2 — the same defect, rated a tier lower
`consensus-passed [2/4]` · voices: `code-reviewer`, `security-reviewer` · **FIXED by the same edit**

Same site, same mechanism, P2 rather than P1: `security-reviewer` noted the sibling
`mechanical_checks` / `toolchains` handlers in the same function both `logger.warning` on their
drop path and this one did not; `code-reviewer` framed it as the comment overstating its guarantee.
Not merged with the P1 cluster — Step 4a does not bridge tiers.

`security-reviewer` also recorded a mitigating fact worth keeping: a malformed **gate** value can
only ever resolve to `True`, so the failure direction was fail-safe-on. Only the **ratio** could be
silently retuned.

## ⚠️ Weak Consensus

None.

## 📝 Manual-Only Findings

### P1 — the reverse-mapper branch shipped with zero test coverage
`manual-only` · voice: `code-reviewer` · **FIXED this round** (not required to be)

The sibling keys `grade_threshold` / `max_review_rounds` have present-value and absent-key
round-trip tests in `test_answers_from_harness_yaml.py`; the new keys had none. The only new test
imported `review_churn` directly and never exercised `answers_from_harness_yaml`, which is the sole
path a re-render uses. A wrong key name or a wrong guard would have shipped silently.

**This is the finding that sets `human_review_needed`.** It is a `manual-only` P1 by tag even
though it was fixed, because one voice raised it and the auto-fix loop is not authorized to act on
single-source findings — the fix here was a deliberate operator choice, recorded rather than
laundered into a consensus it never had.

### P2 — the golden-table test coerced every row to `str`
`manual-only` · voice: `antigravity` · **FIXED this round**

`_reviewers_block(str(row.input["config"]))` meant the resolver only ever saw strings, so the
`isinstance(raw, bool)` guard — which exists because `True` is an `int` subclass and a bare numeric
check would read it as `1.0` — was never reached by any row. The fixture now yields the native types
PyYAML would produce, and a dedicated bool-rejection test was added.

## 🤝 Disagreements

One, and it is the substantive one: **severity on the silent-fallback defect.** Both cross-model
voters said P1; both Claude reviewers said P2. The tiers were not bridged (Step 4c), so the P1
cluster set the grade. The disagreement is real rather than cosmetic — the Claude reviewers weighted
the fact that `review_churn` is not yet wired into any control flow, so nothing today can be
mis-gated by a bad ratio; the cross-model voters weighted the stated contract, which the code did
not honour regardless of whether a consumer exists yet. **The contract reading is the one that
generalises**, since Phase 6 wires the consumer.

## 🧊 Cross-model findings (frozen @ round 1)

`frozen_at_round: 1` · `models: [codex, antigravity]`

| id | source | severity | file:line | summary | disposition | status |
|---|---|---|---|---|---|---|
| `c6be0754c39b1983` | codex | P1 | `interview.py:1203` | Malformed gate/ratio silently falls back on the real load path instead of erroring | accepted | resolved |
| `e75d6adc8ec40045` | antigravity | P1 | `interview.py:1202` | Same — `answers_from_harness_yaml` swallows present-but-malformed values | accepted | resolved |
| `3b745dc30d8a4446` | antigravity | P2 | `test_review_churn_config.py:35` | Test coerces golden rows to `str`, so the bool guard is never exercised | accepted | resolved |

Both models were invoked exactly once, at round 1, per the Production mandatory matrix. No model
was re-invoked for the fix round.

## Iteration 1 (Grade: B → A)

Fixes applied: 3

| # | Severity | Summary | File | Status |
|---|----------|---------|------|--------|
| 1 | P1 | Route both keys through the strict resolvers; warn loudly instead of dropping | `src/harness_maker/interview.py` | Applied · caused_by=none |
| 2 | P1 | Add round-trip, absent-key and malformed-value tests for the reverse mapper | `tests/unit/test_answers_from_harness_yaml.py` | Applied · caused_by=none |
| 3 | P2 | Give the golden-table fixture native YAML types; add a bool-rejection test | `tests/unit/test_review_churn_config.py` | Applied · caused_by=none |

**Design note on fix #1.** The obvious fix — raise `ChurnConfigError` from the reverse mapper —
was rejected. That path is the *migration* path: a typo would make a harness un-re-renderable, and
both sibling handlers in the same function warn-and-drop. The hard error stays where the value is
consumed (`review_churn` raises), which is where fail-closed belongs. So there is now exactly one
definition of "valid" (the resolvers) with two response policies by call site, and a test pins the
warning text at the migration site.

Remaining: 0 | New issues introduced: 0

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | B     | —             | 4         | —   |
| 2         | A     | 3             | 0         | 0   |

Final grade: **A**
Iterations used: 2 / 3
Exit reason: converged
Status: **APPROVED**
human_review_needed: **true**

⚠️ Grade A but 1 unverified severe finding present (manual-only P1 — the untested reverse mapper,
raised by a single voice). It was fixed, but it never passed consensus, so the flag stands.

Counters: unreviewed 3 · prior-fix 0 · unattributed 0

**`unreviewed_fix_count: 3`** — all three fixes landed in the terminal round and no reviewer was
re-spawned over them. That is the exact gap this PLAN's own confirmation pass exists to close, and
this review ran on the *shipped* stage, which does not have it yet. Read the A accordingly.
