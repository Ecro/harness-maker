---
type: review
task_slug: lens-and-review-fix-verification
status: CHANGES_REQUESTED
final_grade: B
human_review_needed: true
iterations_used: 3
exit_reason: cap-exhausted
created: 2026-08-17
reviewers_invoked: [design, functionality, robustness, consistency, security, concurrency, tests]
consensus_method: cross-check
run_id: ea8087ff-20260817T0757Z
review_base: 474245dde0c8c8c311c2fc6643b5ea91bbe0b2b5
lens_coverage: {exercised: 7, missing: [], blocks_approval: false}
drift_verdict:
  result: scope_violation
  scope_violations:
    - tests/unit/test_ledger_exclusions_call_sites.py
  scenario_misses: []
  task_slug: lens-and-review-fix-verification
  computed_at: 2026-08-17T08:05:00+09:00
---

# Review — lens-and-review-fix-verification (Phase 1 only)

## 🎯 Round 1 Summary

**Grade C** (P0 0 · P1 10 · P2 5) against threshold **A** → **CHANGES_REQUESTED**.
Lens coverage 7/7, `blocks_approval: false`. `review_consensus finalize` returned no errors.
Phase D (full `tests/unit` + `tests/structural`) is **green, rc=0** — every finding below is a
defect the suite does not catch, which is the point of the stage.

**Scope reviewed** — Phase 1 only. Phases 2-5 of the PLAN were never started.

| file | state |
|---|---|
| `src/harness_maker/ledger_exclusions.py` | new, 101 lines |
| `src/harness_maker/verifier_discrimination.py` | modified |
| `tests/conftest.py` | modified (+57) |
| `tests/unit/test_ledger_isolation.py` | new, 385 |
| `tests/unit/test_ledger_exclusions.py` | new, 173 |
| `tests/unit/test_ledger_exclusions_call_sites.py` | new, 381 |

**The headline is F4**: the mechanism is correct and wired, and **it is not configured**, so the
150 polluting rows this whole task exists to remove are still in every aggregate on disk. Two
lenses found it independently by escalating outside the worktree to the base repo's gitignored
`.claude/observability/`.

## 🔍 Drift Findings

**P1 — scope violation.** `tests/unit/test_ledger_exclusions_call_sites.py` is not in Phase 1's
declared scope-in list. It was authored in response to Phase A.5 round 1 and is squarely within
the phase's intent, so this is a bookkeeping drift rather than a real scope escape — but the PLAN
was never amended to name it.

**Declared-but-unchanged (not a violation, worth recording).** Phase 1's scope-in names
`tests/unit/test_second_opinion_invoke.py` and `tests/unit/test_second_opinion_budget_advisory.py`.
Neither changed, and correctly so: the prevention-at-the-fixture design made per-site edits
unnecessary. The PLAN predicted a different repair shape than the one that shipped.

## ✅ Consensus Findings

### P1

**F1 — the redirect compares an UNRESOLVED `project_root`** · `tests/conftest.py:96` ·
voices: robustness, functionality, concurrency, security, codex, antigravity *(6)*
`target = Path(project_root)` is not resolved, but `codex_ledger.emit` resolves it afterwards. So
a relative or symlinked root fails the lexical containment test, the redirect declines, and the
row lands in the live checkout. **Reachable, not theoretical**: `second_opinion_invoke.invoke()`'s
`except` branch sets `root = Path(".")` — the source comment names its trigger as a concurrent
`task-land` removing the worktree — and that value flows unchanged to `emit`. Verified locally:
`Path("/abs").is_relative_to(Path("."))` returns `False` (it does not raise, correcting
antigravity's stated mechanism; the consequence is identical). Secondary: the predicate is
ancestor-only, so a `project_root` *inside* the checkout is also left alone.

**F2 — `live_env` silently doubles as an AC-001 opt-out** · `tests/conftest.py:83` ·
voices: consistency, design, concurrency, tests *(4)*
`pyproject.toml` registers that marker as an opt-out of the **session-env pin** only. A test
marked for env reasons also loses the ledger redirect, and
`test_no_test_module_bypasses_the_ledger_redirect` scans for re-patching and fixture shadowing —
never for markers. Zero uses today, so latent; the marker's own description invites the use that
re-opens the leak.

**F3 — `from harness_maker.codex_ledger import emit` is immune to the redirect** ·
`tests/conftest.py:101` · voices: functionality, concurrency *(2)*
A from-import binds the real function into the importing module's globals at import time;
`monkeypatch.setattr(codex_ledger, "emit", …)` rebinds only the module attribute.
**`tests/unit/test_second_opinion_ledger.py` already uses that idiom** at six call sites. All six
pass `project_root=tmp_path` today so nothing leaks — but the gate reports clean over a module
that is structurally outside the protection, and `_tainted_aliases` already computes the import
shape without anything consuming it for this purpose.

**F4 — the mechanism ships UNCONFIGURED** · `.claude/observability/.ledger-exclusions.json` ·
voices: design, functionality *(2)*
The base repo's file is still the legacy one-key map. 144 `slug: "s"` rows plus 6 canary rows are
still counted in numerator and denominator. **Phase 1 exit conjunct 2 is unmet on disk**; the
64.9%-vs-1.3% correction exists only inside `tmp_path` fixtures.
**Cause, stated plainly:** the file was promoted to the list form during execute and then
*deliberately reverted*, because base code cannot read the list form until this branch lands — a
promoted file made the pre-existing `aiexit-exec-p2b` exclusion silently stop applying. The
revert was right; **not recording it as a land-time step was not**. This is the absent-case class
(count:8) with the migration step skipped.

**F5 — dead duplicate `EXCLUSIONS_FILE` with a stale schema comment** ·
`verifier_discrimination.py:56` · voices: consistency, design *(2)*
Nothing reads it after the promotion, and its comment still documents `{"<run-id>": "<why>"}` as
the schema — while **SPEC and PLAN both name it as "the only exclusion reader"**. A maintainer
routed there writes the map form, which excludes nothing on the second-opinion ledger. Verbatim
the defect this phase fixes. Related: `load_exclusions`'s new docstring cites "everything the
docstring above `EXCLUSIONS_FILE` says about loudness and fail-open" — that comment says nothing
about either. The citation points at text that does not exist.

**F6 — `report` filters for the first time and discloses nothing** ·
`verifier_discrimination.py:439` · voices: security, robustness, concurrency *(3)*
The filter was a guaranteed no-op on this ledger before; it is now live, and `to_payload` has no
exclusions field. One line in a gitignored file removes a whole stage from the denominator and
the output looks clean. Worse in the extreme: an over-broad entry empties the row set and `main`
prints *"no rows at {ledger} — nothing to report. This is not a clean bill of health; it is an
absence of evidence"* — pointing the operator at an intact, full ledger.

**F7 — `load` accepts an entry with no `value`** · `ledger_exclusions.py:78` ·
voices: functionality, robustness, codex, antigravity *(4)*
Missing → `""` (matches rows whose field is empty); `null` → the literal `"None"`. Either way an
inert-looking-configured predicate, with no stderr line — while the neighbouring unknown-`key`
branch shouts. `reason` has the same asymmetry.

**F8 — `excluded_run_ids` drops the key and collapses same-value entries** ·
`verifier_discrimination.py:252` · voices: security, consistency, codex, antigravity *(4)*
A slug entry and a stage entry sharing a value render as one line under a name that says run ids.
The field is the sole published audit trail for a suppression control. (Consistency also verified
the inline comment's premise is false: `excluded_run_ids` has exactly one reader, a test.)

**F9 — predicate delegation asserted at 2 of 3 call sites** ·
`test_ledger_exclusions_call_sites.py:269` · voices: tests *(1, solo-lens vote per ADR-007)*
`marginal_gain` is absent from the `is_excluded`-patched probe, so a private predicate at exactly
the site a coverage lens once found unexercised passes the whole set.

**F10 — the invoke canary depends on unpinned repo config** ·
`test_ledger_isolation.py:118` · voices: tests *(1)*
`status == "invoked"` is reachable only because the base repo's `harness.yaml` happens to carry
the default `output_schema_path`. An unrelated edit outside this worktree turns the test red, and
the cheapest fix available to whoever hits it is to delete the assertion two rounds repaired.

### P2

- **F11** `_restores_the_real_emit` has no positive control — `assert not offenders` is true both
  when nothing bypasses and when the detector is dead · tests
- **F12** `load` treats every JSON object as a legacy map, so a new-schema file written as a
  single object is silently mis-read; untested · tests
- **F13** the redirect forwards `**kw` untouched, so an absolute `observability_dir` with a
  substituted `project_root` trips `emit`'s containment guard inside an autouse fixture ·
  design, codex, antigravity
- **F14** the `_TESTS_ROOT` comment omits the `None` arm and says "lands inside this checkout"
  where the code means "contains the tests tree" · consistency, tests
- **F15** the loud branches of `load` (non-dict entry, top-level scalar) have no test ·
  functionality

## ⚠️ Weak Consensus

None.

## 📝 Manual-Only Findings

None. Every cross-model finding was independently corroborated by at least one Claude lens.

## 🤝 Disagreements

- **Severity split on F7 and F8.** `functionality` and `security` rated at P1 what `codex`
  (P2/P3), `antigravity` (P2) and `robustness` (P2) rated lower. Per Step 4c tiers are not
  bridged; recorded at P1 on the strength of the lens votes, with the split noted here.
- **F1 mechanism, refuted.** antigravity claimed `is_relative_to` *raises* `ValueError` on mixed
  absolute/relative paths. It returns `False` (verified on this interpreter). Same consequence,
  wrong mechanism — the finding stands, its explanation does not.
- **F7 exploitability, partial.** `security` examined the same code and judged the coercion **not
  exploitable**, because `value is None: continue` and `entry.key not in row` defuse both
  collision vectors. That does not contradict F7 — the defect is silence, not a security hole —
  and the two readings are recorded together rather than averaged.

## 🧊 Cross-model findings (frozen @ round 1)

Both models were invoked exactly once, at round 1. `codex` status `invoked` (4 findings),
`antigravity` status `invoked` (6 findings) — notable because antigravity `failed` on the
`SUCCESS`+empty-response path during this task's own `/hm:plan`, which is the class Phase 4 exists
to make countable.

| id | model | finding | disposition | folded into |
|---|---|---|---|---|
| 75ec1e94 | codex | relative/symlinked project roots bypass isolation | accepted | F1 |
| 8b0243a2 | codex | `project_root=None` over-broad; `observability_dir` breakage | accepted | F13 |
| d1bc1a4b | codex | malformed list entries become active predicates | accepted | F7 |
| e79baaa9 | codex | `excluded_run_ids` loses entries on value collision | accepted | F8 |
| 1007ca4f | antigravity | mixed abs/rel comparison (claimed ValueError) | accepted, mechanism refuted | F1 |
| d16c5934 | antigravity | `target` not resolved; symlink bypass | accepted | F1 |
| c5a320fc | antigravity | `observability_dir` + substituted root trips the guard | accepted | F13 |
| 2ae3b25d | antigravity | `entry.key not in row` raises on a pydantic model | rejected | — no caller passes a model; `read_rows` yields dicts |
| e06fe235 | antigravity | `value` null/missing coercion | accepted | F7 |
| f782ea29 | antigravity | `excluded_run_ids` collision + name | accepted | F8 |

**Disposition method, stated because it deviates.** No separate `code-verifier` mode-B PIDA
dispatch was run. Every cross-model finding that votes was independently corroborated by at least
one Claude lens reading the same code, which is a stricter bar than PIDA's refutation gate; the
one finding no lens corroborated (`2ae3b25d`) was checked against source and rejected. The
deviation is recorded rather than hidden.

## Iteration 2 (Grade: C → C) — repair round

Fixes applied: 14 of 15. F4 is not fixable in this branch and was recorded in the PLAN as a
`🛬 REQUIRED LAND-TIME STEP` with the exact JSON and an ordering warning.

| # | Severity | Summary | Status |
|---|---|---|---|
| F1 | P1 | unresolved `project_root` comparison | Applied — resolve + both directions |
| F2 | P1 | `live_env` doubles as the ledger opt-out | Applied — new `live_ledger` marker, registered |
| F3 | P1 | from-import `emit` bypasses the redirect | Applied — module converted **and** gate widened |
| F4 | P1 | mechanism ships unconfigured | **Deferred to land time** — recorded, not fixed |
| F5 | P1 | dead `EXCLUSIONS_FILE` + stale schema comment | Applied — deleted; bogus citation corrected |
| F6 | P1 | `report` filters and discloses nothing | Applied — `exclusions` block + branched stderr |
| F7 | P1 | `value` missing/null → inert predicate | Applied — rejected loudly; `reason` warns |
| F8 | P1 | `excluded_run_ids` lossy and misnamed | Applied — lossless sibling published |
| F9 | P1 | delegation asserted at 2 of 3 sites | Applied — `marginal_gain` added to the probe |
| F10 | P1 | canary depends on unpinned repo config | Applied — `load_config` pinned |
| F11 | P2 | offender predicate had no positive control | Applied |
| F12 | P2 | single-object new-schema file mis-read | Applied — detected and rejected |
| F13 | P2 | absolute `observability_dir` trips the guard | Applied — dropped on redirect |
| F14 | P2 | `_TESTS_ROOT` comment ≠ predicate | Applied |
| F15 | P2 | loud branches of `load` untested | Applied |

Remaining: 1 (F4) | New issues introduced: 3
Churn: 0.297 (max: `tests/unit/test_ledger_exclusions.py`, measured 9, excluded 0)

## Iteration 3 (Grade: C → B) — churn-gated re-review, then repair

Churn 0.297 ≥ 0.20, so the gate authorised one `functionality` dispatch over the repair hunks.
**All three findings were created by iteration 2's own repairs**, which is the pattern this
repo's history predicts and the reason the gate exists.

| # | Severity | Summary | Status |
|---|---|---|---|
| R3-1 | P1 | The hardened `_patch_calls` requires an `ast.Name` target, so `monkeypatch.setattr(soi.codex_ledger, "emit", …)` is invisible — and **that spelling already exists at `test_second_opinion_invoke.py:826`**. Three of four spellings closed; the one in the tree left open. | Applied — `_is_codex_ledger_ref` accepts dotted module refs; the spelling added to the positive control |
| R3-2 | P1 | F6/F8's new payload fields and the all-excluded stderr branch had **no tests** — reverting all three hunks left the suite green, and they are precisely the fields whose silent loss reproduces the original defect. | Applied — 4 tests pinning `exclusions.applied`, `rows_dropped`, the branched message, and the lossless record |
| R3-3 | P2 | The positive control seeded `_REAL` into `tainted` by hand, so it could not fail on a `_tainted_aliases` regression. | Applied — seed removed |

Also fixed, from the same reviewer's unfiled observations: `specs/SPEC-*.md` and
`work-docs/PLAN-*.md` still pointed at the deleted `verifier_discrimination.EXCLUSIONS_FILE` —
F5's "routed to the wrong name" hazard, surviving one file over. Both repointed.

Remaining: 1 (F4) | New issues introduced: 0
Churn: 0.205 (measured over r2-post → r3-post)
Oscillation scan (`review_churn oscillation --rounds 2,3`): `[]` — no hunk was removed and
restored.

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | C     | —             | 15        | —   |
| 2         | C     | 14            | 1         | 3   |
| 3         | B     | 3             | 1         | 0   |

Final grade: **B**
Iterations used: 3 / 3
Exit reason: **cap-exhausted** — the churn gate authorised a round 4 (churn 0.205 ≥ 0.20) and
`max_review_rounds: 3` forbade it. This is the exit that says a higher cap would have helped:
round 3 both resolved findings and introduced none, so the loop was still moving when it stopped.
Status: **CHANGES_REQUESTED** (B < threshold A)
human_review_needed: **true** (cap exhausted)
`confirm_pass_ran: false` — the confirmation pass runs only on the APPROVED path.

**Verification at the stopping point:** `uv run pytest tests/unit tests/structural` → **rc=0**,
green. `ruff check` clean, `mypy --strict` clean on both changed source modules.

## The one thing standing between B and A

**F4, and it cannot be closed here.** Promoting `.claude/observability/.ledger-exclusions.json`
to the list form makes the base repo's current reader take the "is not an object" branch and
exclude **nothing** — silently disabling the `aiexit-exec-p2b` entry that already exists. It was
promoted during execute, that breakage was observed, and it was reverted. So the grade honestly
carries one open P1: the mechanism is correct, wired, tested, and **not yet configured**, and the
150 polluting rows remain in every aggregate on disk until the branch lands and the file is
promoted in the same operation.

The PLAN's `🛬 REQUIRED LAND-TIME STEP` section holds the exact JSON, the ordering warning, and
the verification command.
