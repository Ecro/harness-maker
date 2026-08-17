---
type: research
task_slug: lens-and-review-fix-verification
status: complete
created: 2026-08-17
tags: [harness-maker, research, python, review-pipeline, lens-coverage, telemetry, second-opinion]
mtime_warn_days: 7
libs_fetched: []
sources: []
related_docs: [[[PLAN-multi-lens-review-round]], [[PLAN-second-opinion-invocation-and-slug-cap]], [[REVIEW-harness-maker-spec-alignment-2026-08-17]]]
summary: "Lens axis works end-to-end; three defects sit around it — ledger pollution, stale routing prose, missing per-finding lens stamp"
---

# Research — lens usage and recent review fixes across three projects

## 🎯 Recommended Direction

**The seven-lens review axis works.** It has been exercised exactly once at runtime
(neuroTerm, run_id `20260817T0459Z`, in flight while this research ran), and that run
delivered all seven lens result files, passed `lens_coverage check` with `missing: []`,
and produced a coherent solo-lens-vote verdict. All three projects render the axis
identically at 0.52.4, all required lens agents are installed, and the 217 lens/review
unit tests are green.

What does **not** hold is the instrumentation and the prose around it. Three defects
found, none of which the render-grep gates can see, all of which fit the failure class
CLAUDE.md already names — *the artifact on disk is correct and only the runtime value is
wrong*:

1. **P1 — the unit suite writes into the live second-opinion ledger.** ~140 pytest runs'
   worth of synthetic `slug: "s"` rows, 83 of them since 2026-08-14. They corrupt the one
   metric CLAUDE.md prescribes for this subsystem: a naive read says codex has a 90.7%
   loss rate over the last two days; excluding the synthetic rows it is 0%.
2. **P2 — Step 3's routing paragraph still describes the retired agent axis.** It is what
   made the live neuroTerm run stamp `reviewers_invoked: [… performance-reviewer,
   ux-reviewer …]` — two agents the seven-lens dispatch never spawns.
3. **P2 — the per-finding `lens` stamp is absent on every finding in the live run.** The
   template mandates it precisely because ADR-007's solo-lens vote is undecidable without
   it; 19/19 findings shipped unstamped and the coverage gate cannot detect this.

The binding trade-off: (1) is cheap and its cost is already sunk (every future health
reading is wrong until it is fixed and the rows are excluded), (2) is one paragraph, and
(3) needs a machine check, not stronger prose — an instruction the model has already
ignored once will be ignored again.

## 🔍 Refinement Decisions

Discovery lens: **Technical architecture / implementation** (primary) + **Risk /
compliance** (secondary — the ledger-pollution finding). `--deep` was not set; the topic
named its own scope.

Concurrency note, recorded because it constrains what can be claimed: **two other
sessions were live during this research.** neuroTerm was mid-`/hm:review` on
`harness-maker-spec-alignment` (REVIEW doc written 14:35, one minute before it was read),
and the harness-maker base working tree grew from 4 to 46 modified files between two
consecutive `git status` calls (14:21→14:35). Nothing here was written to either.

## 🛠️ Approaches Found

### What was verified, per project

| Project | Version | targets | preset | Lens axis rendered | Lens exercised at runtime |
|---|---|---|---|---|---|
| harness-maker | 0.52.4 | — (self) | Production | ✅ 7 lenses | ❌ last review 2026-08-07, predates the axis |
| ~/neuroTerm | 0.52.4 | claude-code, codex | Production | ✅ 7 lenses | ✅ **live run, all 7 delivered** |
| ~/spoton | 0.52.4 | claude-code, codex | Production | ✅ 7 lenses | ❌ last review 2026-07-25 |

Evidence for the neuroTerm run — the only runtime evidence that exists:

```
.hm-lens-results/harness-maker-spec-alignment/20260817T0459Z/1/
  design.json functionality.json robustness.json consistency.json
  security.json concurrency.json tests.json
→ hm lens_coverage check … --preset Production
  {"blocks_approval": false, "exercised": [all 7], "missing": [], "preset": "Production"}
```

Every file carries `lens` matching its stem and the correct `run_id`, so the F2 run-id
gate and the fail-closed liveness rule both behave as documented.

### Approach A — trust the render gates (status quo)

| Field | Content |
|---|---|
| Assumption | If the template renders the mechanism, the mechanism runs |
| Evidence | Contradicted three times here: the ledger rows, the stale routing paragraph, and the missing per-finding stamp all render "correctly" |
| Trade-off | Zero cost, zero detection |
| Compatibility | Already the default |
| Risk | **high** — this is the `is_codex` failure mode CLAUDE.md documents verbatim |

### Approach B — fix the three defects, add one machine check

| Field | Content |
|---|---|
| Assumption | Two are one-line/one-paragraph edits; only the lens stamp needs a gate |
| Evidence | `soi.main()` in `tests/unit/test_second_opinion_invoke.py:740` resolves base root from the real cwd; `lens_coverage` already parses every result file, so it can assert the stamp there. **Corrected 2026-08-17:** this row also named `tests/unit/test_second_opinion_budget_advisory.py:160`, which is not a leak site — it passes `--root str(tmp_path)`. The claim came from matching polluted rows' `skip_reason` text against test names instead of reading the call |
| Trade-off | The stamp check must be advisory-or-blocking — blocking it retroactively invalidates the one good run |
| Compatibility | No schema change; `exercised_lenses` already opens every file |
| Risk | low |

### Approach C — also retire the dead reviewer surface

| Field | Content |
|---|---|
| Assumption | `ux-reviewer` / `performance-reviewer` are no longer reachable through `/hm:review` |
| Evidence | `lens_dispatch("Production")` returns 7 dispatches over `code-reviewer` ×4, `security-reviewer`, `concurrency-reviewer`, `test-reviewer`. Neither optional reviewer appears. Both are still installed in all three projects and still listed in `conditional_router.OPTIONAL_REVIEWERS` |
| Trade-off | Removing them is a behaviour change users may notice; leaving them is dead weight that already misled one REVIEW doc |
| Compatibility | Touches `conditional_router`, the routing prose, and every rendered harness |
| Risk | medium — defer to `plan`; not a correctness defect |

## ⚠️ Pitfalls

- **Reading the second-opinion ledger without filtering `slug == "s"`.** Measured today:
  since 2026-08-16 the raw numbers are codex 39 skipped / 4 invoked (90.7% loss) and
  antigravity 4 failed / 0 invoked (100% loss). After excluding the synthetic rows: codex
  ~0% loss, antigravity ~57% (4 failed of 7 — a real, separate degradation with the
  documented `status: SUCCESS` + empty `response` signature). CLAUDE.md already warns that
  merging models or dropping `failed` distorts this reading; a third distortion —
  test-authored rows — now has to be excluded too.
- **Treating a green `lens_coverage check` as proof the lens contract held.** It checks
  file presence, `lens`, and `run_id`. It does not check the per-finding stamp, and the
  one live run passed the gate with 19/19 findings unstamped.
- **Reading harness-maker's own review telemetry as evidence about the lens axis.** Its
  newest row is 2026-08-07; the axis landed 2026-08-16. Same for spoton (2026-07-25).
  Absence of `lenses_exercised` in those rows is age, not failure.
- **Running the test suite while investigating this.** Every full run appends fresh
  synthetic rows to the file being measured.
- **Concurrent sessions.** `git status` is not stable across two calls in this repo right
  now; a test failure observed here may belong to another session's in-flight WIP rather
  than to the reviewed change.

## ❓ Open Questions

1. Should the per-finding `lens` stamp be enforced in `lens_coverage` (blocking) or
   reported (advisory)? Blocking is the only thing that will actually hold, but it fails
   the one review currently in flight.
2. Do the synthetic `slug: "s"` rows get **excluded at read time** (a filter in whatever
   aggregates the ledger, plus `.ledger-exclusions.json`) or **purged** from the file?
   Purging rewrites history another session may be reading.
3. Is antigravity's ~57% real failure rate in scope here, or its own task? It is the
   documented `structured_output`-absent path, unrelated to the lens work.
4. Approach C — retire `ux-reviewer` / `performance-reviewer`, or keep them installed for
   `--with-reviewers` use?
5. ~~Structural-test failures~~ — **resolved, not an open question.** Eight structural
   tests fail in the base working tree (`test_command_size_budget[execute]`,
   `test_roundtrip_budget` ×3, `test_surface_baseline` ×2, aggregate surface, and
   `test_new_gates_file_a_mutation_receipt`). Re-run on a clean checkout of the same
   commit in an isolated worktree: **61 passed**. Every failure is attributable to another
   session's uncommitted `execute.md.j2` growth plus its new un-receipted structural gate.
   None touches the review or lens work.

## 📚 Sources

All evidence is local. No external source was fetched — the question is entirely about
this machine's state.

- `hm lens_coverage check` output, neuroTerm worktree `harness-maker-spec-alignment`
- `.claude/observability/second-opinion.jsonl` (harness-maker: 317 rows; spoton: 32 rows)
- `hm review_consensus finalize` smoke — solo lens voice → `consensus-passed`, solo
  cross-model voice → `manual-only`, grade computed, `human_review_needed: true`
- `uv run pytest tests/unit/test_lens_coverage.py test_render_lens_axis.py
  test_render_lens_dispatch.py test_review_churn_config.py test_review_churn_gate.py
  test_review_consensus.py test_review_telemetry.py test_consensus.py -q` → 217 passed
- `uv run pytest tests/structural -q` → 8 failed in the dirty base; the same four files →
  61 passed in a clean worktree at the same commit
- `git log` 2026-08-15..17 on `src/harness_maker/templates/stages/review.md.j2`

## 🔗 Related Internal Docs

- [[REVIEW-harness-maker-spec-alignment-2026-08-17]] — the live neuroTerm review that
  supplied the only runtime lens evidence
- [[PLAN-second-opinion-invocation-and-slug-cap]] — ADR-001/005, the shared invoker that
  the polluting tests call
- CLAUDE.md § *Cross-model second opinion* — the skip-rate reading protocol the synthetic
  rows break
- CLAUDE.md § *렌더 컨텍스트 플래그는 출력 경로에서 파생시킬 것* — the `is_codex` precedent
  for "template and artifact both read correct, only the runtime value is wrong"
