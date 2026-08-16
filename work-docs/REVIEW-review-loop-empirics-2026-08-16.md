---
type: review
task_slug: review-loop-empirics
status: CHANGES_REQUESTED
created: 2026-08-16
reviewers_invoked: [design, functionality, complexity, robustness, naming, consistency, security, concurrency, tests, codex, antigravity]
consensus_method: per-lens-sovereignty (ADR-007)
drift_verdict:
  result: scope_violation
  scope_violations:
    - src/harness_maker/render.py
    - src/harness_maker/personalization_audit.py
    - src/harness_maker/foreign_config.py
    - src/harness_maker/template_globals.py
    - src/harness_maker/command_registry.py
    - src/harness_maker/hm.py
    - src/harness_maker/surface_allowance.py
    - src/harness_maker/templates/harness-yaml/Production.yaml.j2
    - src/harness_maker/templates/harness-yaml/Side.yaml.j2
  scenario_misses: []
  task_slug: review-loop-empirics
  computed_at: 2026-08-16T10:30:00Z
---

# REVIEW — Phases 2–4 (commit `ab161e08`)

## 🎯 Round 1 Summary

**Grade: F. Status: CHANGES_REQUESTED. `human_review_needed: true`.**

This is the first live run of the nine-lens axis the diff itself introduces, dispatched against
the commit that introduced it. It found a **P0 in the grade path**: on the exact three-verb call
sequence `review.md.j2` prescribes, three `consensus-passed` P0 findings graded **A**.

The change had a full green suite, `ruff`, `ruff format` and `mypy --strict` at land time. Every
defect below is in the gap those cover: the seam between a tested library and the rendered prose
that calls it.

## 🔍 Drift Findings

Nine source files outside any PLAN phase's declared scope (frontmatter). All defensible — the
Jinja-globals cluster is what makes the axis a single source of truth, and `surface_allowance` is
ADR-010's amendment — but none were named in the phase scope, so the drift gate reports them
rather than silently accepting the widening. `P1`, informational.

No scenario misses: AC-001..009, 015, 017 are the phases' declared set; AC-010..014, 016, 018,
019 belong to Phases 5–7.

## ✅ Consensus Findings

### P0

**`grade` fails open on an untagged file** — `review_consensus.py:254`, `review.md.j2` Steps
4d/4e/Grade Computation. Raised independently by **robustness** (at P0), **design**,
**functionality** and **consistency**; reproduced by execution.

`tag` and `record` printed to stdout only, while the template handed the same temp path to all
three verbs and never said to write anything back. `grade_from_findings` read `raw.get("tag")`
and `continue`d on anything that was not `consensus-passed` — so an absent tag was
indistinguishable from `manual-only`. Every finding skipped, counts zero, grade `A`,
`human_review_needed` false, exit 0.

```
$ tag --file f.json ; record --file f.json ; grade --file f.json
{"counts": {"P0": 0, ...}, "grade": "A", "human_review_needed": false}
# f.json holds three consensus-passed P0s. The table says F.
```

This is the failure class `review_consensus.py`'s own module docstring says it exists to
eliminate, reintroduced one layer up. **Fixed** — three ways, because one was not enough:
`tag`/`record` now write in place; an unknown tag is counted at its own severity and reported;
`grade` exits 1 whenever `errors` is non-empty.

### P1

| # | Finding | Voices | Fixed |
|---|---|---|---|
| 1 | A rejection citing **`AC-999`** — an id in no SPEC — cleared a P0 with `human_review_needed: false`. `_authority_kind` checked the citation's SHAPE; citing a contract that does not exist is typing a string. | codex | ✅ `grade --spec` verifies ids against the machine SPEC; without `--spec` no AC citation clears |
| 2 | **Side could never dispatch `security`, `concurrency` or `tests`.** `lens_dispatch` iterated the mandatory set, so the three routable lenses were absent from every Side render — while the routing bullet said the router "may drop" them. Subtraction from a set the renderer never produced. | codex, design, naming | ✅ dispatch = mandatory ∪ routable; a router can only drop what was dispatched |
| 3 | **`test-reviewer` is not in `_PROD_ENABLED_REVIEWERS`** while `tests` is a mandatory Production lens → the coverage gate demands a result from an agent the config never enabled → `blocks_approval: true` forever. | design | ✅ added |
| 4 | **On the codex target every new mandated call rendered as an inert `!` line.** The coverage verdict, the tag, the disposition and the grade were prose-only there — exactly the self-report hole `exercised_lenses` exists to close. | robustness | ✅ all six calls now `is_codex`-branched |
| 5 | The `tag` CLI **dropped `reasoning_diverges`**, so `weak-consensus` — a row in the shipped tag table — was unreachable through the CLI the template calls the sole decider. | codex, design, functionality, consistency | ✅ passed through |
| 6 | **One voice-less finding aborted the whole `tag` batch** (exit 2, no output) — and the stage *produces* voice-less findings by design (Step 4d says to omit an `unresolved` cross-model finding's voices; Step 4e requires it to stay in the file). | codex, functionality, robustness | ✅ empty voices → `manual-only`, the tag the skill already specifies |
| 7 | **`aggregate_headroom` sums across every in-flight PLAN.** No ownership key, and the gates pass only the repo root — so a change that earned zero headroom passes on another PLAN's budget, with the message reporting only the total. Fails open in the multi-session case this repo runs by default. | concurrency | ✅ refuses to sum; >1 active allowance is a loud error |
| 8 | `_load` **silently dropped** non-mapping entries, so a finding could vanish before the disposition column was assigned — satisfying AC-006's completeness invariant by not existing. | codex, consistency | ✅ raises |
| 9 | **`MANDATORY_LENSES` is the full vocabulary**, not any preset's mandatory set. A reader who "fixed" it to be genuinely mandatory-scoped would make `review_telemetry.emit` reject a legitimate Side row carrying a router-selected `security`, losing an append-only row. | naming | ✅ `KNOWN_LENSES` is the real name; the old one is a documented deprecated alias |
| 10 | `_ACTIVE_STATUSES` covered only `planning`, but `plan.md.j2`'s ADR-halt path writes **`blocked`** — maximally in-flight. Expiring there fails the ratchet with a message steering the author to regenerate `surface_baseline.json`, the destructive act the allowance exists to remove. | robustness | ✅ `blocked` is active |
| 11 | The auto-fix loop's coverage call hardcodes `--round 1 --round 2 --round <this round>`, skipping intermediate rounds — past round 3 a lens that only succeeded in round 3 is never read, reinstating the permanently-unapprovable review. | functionality | ✅ prose corrected to one flag per round |
| 12 | `reviewers.rereview_churn_gate` / `_ratio` ship into user `harness.yaml` under a **present-tense** comment describing behaviour no rendered stage implements. The absent-case/silent-no-op class CLAUDE.md records at count:8. | complexity, consistency | ⏸️ deferred — Phase 6 wires it; see Follow-ups |

## ⚠️ Weak Consensus

None. No finding had two voices whose reasoning diverged.

## 📝 Manual-Only Findings

Out-of-diff escalations. Real, but not defects of this change — filed rather than graded:

- **P1 `freeze.py:156` — unsanitised `--slug` builds a filesystem path.** `store_review_base`
  does `mkdir(parents=True)` + `write_text`, and `reap` does `unlink`, on a slug the model
  substitutes from PLAN frontmatter. The sibling in this very diff (`lens_coverage.round_dir`)
  applies a containment check; `freeze.py` is now the one slug surface with neither that nor the
  `_TASK_SLUG_RE` allowlist. *(security)*
- **P1 `codex_ledger._migrate_legacy_ledger` — exists()-then-append TOCTOU.** Two concurrent
  `/hm:review` runs both see the new path absent and each append the full legacy history,
  permanently doubling the per-invocation denominator CLAUDE.md designates load-bearing.
  *(concurrency)*
- **P1 `lens_coverage` — `run_id` isolates invocations in file CONTENT but not in the PATH.**
  Two sessions reviewing one slug write the same `<slug>/<round>/<lens>.json`; the later write
  wins and the earlier session's own lens is reported missing, unfixably. The F2 fix closes
  sequential re-runs only. *(concurrency)*
- **P2 `surface_allowance` — `delta_doc` joined unvalidated** (`path.parent / delta_doc`).
  *(security)*
- **P2 `review_telemetry`** forces `confirm_pass_ran` onto non-terminal rows, which cannot know
  it. *(functionality)*
- **P2 `consensus-arbiter`** still renders, tagging with a fourth value (`scope-exempted`) on a
  field name (`consensus_tag`) `review_consensus` does not know. *(design)*
- **P2 two owners of `human_review_needed`** — the CLI computes it, then the Grade Gate's prose
  overwrites it from `unverified_severe`, which is a different rule and cannot see the
  provenance carve-out. *(design, functionality)*

## 🤝 Disagreements

Only on severity, never on existence:

- The grade fail-open: **robustness P0**, design/functionality/consistency **P1**. Taken as P0 —
  the higher call is right, since the failure direction is a silent APPROVE.
- `routable_lenses` having no dispatch consumer: **codex P1**, design/naming **P2**. Taken as P1
  once execution confirmed Side can never run `security` at all.

## Test-quality findings (tests lens, 7 findings — all P2/P3)

Not graded (P2), but they explain **why the P0 shipped green**:

- No render test binds `hm review_consensus {tag,record,grade}` into the rendered command at all.
  Deleting all three calls and reverting Step 4 to prose would have failed nothing but a
  round-trip *count*, satisfiable by any four unrelated `!` lines.
- `build_round_record` was tested only in the fail-safe direction; a mutant stamping every
  finding `unresolved` passed the file. ✅ fixed — a preservation arm now exists.
- AC-001 declares `oracle_source: golden` while every assertion compares the render to the same
  production constant the renderer reads. Renaming a lens moves both and stays green.
- `test_the_pass_re_reads_the_frozen_cross_model_set` is vacuous in the configuration it renders
  (`second_opinion.models` empty ⇒ the whole paragraph is `{% if %}`-ed out).
- Two confirmation-pass anchors are polarity-blind (`"iteration_count" in block` for a docstring
  claiming "must not increment").

## 🧊 Cross-model findings (frozen @ round 1)

**codex** — `status: invoked`, 5 findings, **all 5 confirmed by execution**, all accepted. It was
the sole voice on the `AC-999` laundering hole and the first to call the Side dispatch gap P1.

**antigravity** — `status: failed`, twice. `agy` returned `status: SUCCESS` with an empty
`response` and no `structured_output`, at 151 KB and again at 40 KB. `warn-and-proceed` per
`failure_policy`. Per CLAUDE.md this belongs in the degradation **numerator** — a model that ran
and returned an unusable payload is as absent as one that never ran.

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (init)  | F     | 11            | 1 deferred + 7 manual-only | — |

Final grade: **F** at round 1 · Status: **CHANGES_REQUESTED** · `human_review_needed: true`
Exit reason: `changes-applied-pending-re-review`
Voter pool: 9 reviewer lenses + 2 cross-model (1 usable)

## Axis merge (interview #24, after the review)

The run's own redundancy numbers were the input to a follow-up decision: **nine lenses → seven.**

| lens | findings | also raised by another lens | exclusive |
|---|---|---|---|
| consistency | 5 | **4 (80 %)** | 1 |
| design | 8 | 4 (50 %) | 3 |
| complexity | 5 | 2 (40 %) | 3 (1 of them a false positive) |
| robustness | 5 | 2 (40 %) | 3 |
| functionality | 9 | 3 (33 %) | 6 |
| naming | 7 | 1 (14 %) | 7 |
| security | 3 | **0** | 3 |
| concurrency | 6 | **0** | 5 |
| tests | 10 | **0** | 10 |

`complexity` folds into `design` — both its overlaps were with `design`, and its exclusive
findings were shape questions (a decision function with no caller, dataclasses crossing no
boundary, three CLI round trips where one would do). `naming` folds into `consistency` — the most
redundant lens, whose one exclusive finding was a constant duplicated across two modules, which is
what the merged lens is for; both work by reading two places and comparing. The zero-redundancy
three are untouched, as are `robustness` and `functionality`.

**Caveat:** n=1 — one diff, one run per lens. The source experiment measured median Jaccard 0.36
between two runs of one reviewer, so a re-run would redraw some groups; `consistency` at 80 % is
4 findings out of 5.

## Follow-ups (not fixed here)

1. **Phase 6 must wire the churn gate or the knob must go.** Two lenses independently called the
   present-tense `harness.yaml` comment a lie, and CLAUDE.md's most-recurring failure class is
   exactly this. If Phase 6 slips, reword the comment to future tense in the meantime.
2. **`freeze.py` slug containment** — the one slug surface without a guard its own siblings apply.
3. **`lens_coverage` results path should carry the `run_id`**, not only the file content.
4. **`codex_ledger` migration needs `O_EXCL`.**
5. **One owner for `human_review_needed`** — either the CLI learns `source`, or the gate consumes
   the CLI's value verbatim.
6. **A render test that binds the three `review_consensus` calls**, in the shape
   `test_the_coverage_call_carries_its_full_flag_set` already uses for `lens_coverage`.
