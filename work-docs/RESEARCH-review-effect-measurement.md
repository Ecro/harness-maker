---
type: research
task_slug: review-effect-measurement
status: complete
created: 2026-10-17
tags: [review, measurement, observability, ledger, escape-attribution, seeded-defects]
mtime_warn_days: 7
libs_fetched: []
sources:
  - https://research.google/pubs/resolving-code-review-comments-with-machine-learning/
  - https://arxiv.org/abs/2601.01129
  - https://arxiv.org/abs/2507.13499
  - https://arxiv.org/abs/2411.07091
  - https://www.microsoft.com/en-us/research/?p=164195
  - https://arxiv.org/abs/2308.05060
  - https://www.greptile.com/benchmarks
  - https://www.qodo.ai/glossary/what-is-ai-code-review-benchmarks/
  - https://arxiv.org/abs/2509.01494
  - https://icml.cc/virtual/2026/82770
  - https://link.springer.com/article/10.1186/s13063-024-08100-1
  - https://www.recercat.cat/handle/2445/134418
  - https://en.wikipedia.org/wiki/Rule_of_three_(statistics)
  - https://arxiv.org/abs/2404.13076
  - https://arxiv.org/abs/2310.01798
  - https://arxiv.org/abs/2607.10411
related_docs:
  - specs/SPEC-hm-overhaul-p1.md
  - work-docs/ABLATION-pass2-2026-08-05.md
  - work-docs/RESEARCH-workflow-loop-efficiency.md
  - work-docs/RESEARCH-workflow-time-token-savings.md
  - work-docs/RESEARCH-workflow-steps-vs-model-capability.md
  - work-docs/RESEARCH-review-loop-empirics.md
  - work-docs/RESEARCH-ai-review-exit-criteria.md
  - work-docs/RESEARCH-reviewer-lens-fanout-merge.md
  - work-docs/BASELINE-DELTA-review-loop-empirics.md
  - work-docs/PLAN-second-opinion-acceptance-gate.md
  - docs/evals/RESULTS.md
  - docs/evals/README.md
summary: Read the REVIEW table into a ledger, attribute post-merge fixes, seeded recall audit per model release
---

# RESEARCH — review-effect-measurement

**Question.** Since 0.64.0, review is one `code-reviewer` dispatch inside `/hm:execute` Step 6. Does it have
an effect? Specifically: does it catch defects the deterministic gates (`hm check`) miss, how many does it
miss, and is that worth what it costs? This doc covers how to measure that. It does not answer the question.

**Sharper boundary (inference, from the sources below).** There are three different things to measure, and
the project has historically measured only a fourth one:

| Quantity | What it answers | Measured before? |
|---|---|---|
| **Marginal yield**: accepted P0/P1 findings per review, beyond a green `hm check` | Did the review add anything the gates did not? | Partly (finding counts, pre-0.64 ledgers). Never with a validity label |
| **Escape rate**: reviewed tasks whose code later needed a `fix:` that the review should have flagged | What does it miss in real use? | **Never.** `later_regression_link` is null in 597/597 rows |
| **Recall on a known denominator**: seeded defects caught / seeded | What does it miss, given a ground truth? | **Never for detection.** The seeded runs scored loop observables |
| *Activity*: FAIL rate, drop rate, consensus-pass rate | How busy the step was | Yes. This is the only kind the record holds, and it is not effect |

## Recommended Direction

**Approach A as the always-on base, plus Approach B as a periodic remeasure tied to model releases. Do not
build Approach C now.**

The one-line reason: A costs almost no prose because the data is already written. Step 6 writes a findings
table after a green `hm check`, so every accepted finding is marginal over the gates by construction. B is
the only route to a recall denominator. C, the randomized hidden arm, is the only clean counterfactual, but
it ships known defects on purpose or doubles review cost, which a solo developer will not keep up.

This is informational. The SPEC decides.

## Approaches Found

### A. Live outcome ledger: read the REVIEW table, attribute escapes after merge

**What it is.**

1. At wrapup, which already stages `work-docs/REVIEW-<slug>-*.md` (`wrapup.md.j2:53`), a Python reader parses
   the `## Findings` table. It writes one row per review: slug, rounds, findings by severity × disposition,
   reviewer set and harness version.
2. Cost comes from the existing transcript economics, through the `-reviewer` agent suffix.
3. Escapes: when `/hm:metrics` adjudicates a remediation commit, which `delivery_metrics` already does, the
   LLM also answers three questions:
   - Which landed task introduced the defect?
   - Did that task's REVIEW flag the line or root cause?
   - Was the defect reviewable from the diff and SPEC?

   The answer fills a link field that was designed for this and never fed (`later_regression_link`).

**Assumption.** The REVIEW table is written reliably and in a parseable form. Post-merge `fix:` commits,
adjudicated by an LLM, are a usable escape signal at this repo's volume.

**Evidence for.**

- The gate is already green before review. `hm check --slug <slug>` runs at Step 3's end
  (`execute.md.j2:52`), before Step 6 (`:64`). So "accepted after a green gate" already means "the gates
  missed it". No new counterfactual machinery is needed for marginal yield.
- The data is already produced. `execute.md.j2:76` reads: "Write `work-docs/REVIEW-<slug>-<YYYY-MM-DD>.md`
  with a `## Findings` table: `| id | severity | file:line | finding | disposition | authority |`".
- The adjudication hook exists. `delivery_metrics.py:41` defines
  `_REMEDIATION_SUBJECT = re.compile(r'(?i)^(fix|hotfix)\b|^Revert "')`, and `/hm:metrics` already runs LLM
  adjudication over ambiguous fix candidates (`commands/hm/metrics.md.j2:9-11`).
- The link field exists. `codex_ledger.py:33`: "``later_regression_link`` remains a nullable placeholder."
  It is null in 597 of 597 `second-opinion.jsonl` rows (verified 2026-10-17).
- Industry's main metric is this kind of "comment led to a change" count. Atlassian RovoDev defines a "code
  resolution rate of 38.70%" as "comments that triggered code changes in the subsequent commits"
  (arXiv 2601.01129).

**Evidence against.**

- Nothing reads the table today. 0.64.0 orphaned every machine record. `commands/make.md:252`:
  "`instrumentation.stage_agent_ledger` | inert since 0.64.0 — the stages emit no ledger rows". A grep of
  `execute.md.j2` for `review_telemetry`, `review_churn` and `jsonl` finds nothing.
- The table format is young. Only 8 of 230 `work-docs/REVIEW-*.md` contain a `## Findings` heading, so the
  history before 0.64 is not parseable this way.
- Round history is lost. Each review writes one dated doc with no round column, so how yield changes across
  rounds, and the defects that fixes introduce (`caused_by`), cannot be recovered. The past rate of defects
  introduced by fixes was "11/22 … a later phase measured 7/7" (`RESEARCH-ai-review-exit-criteria.md:71-77`).
- "Accepted" means a decision, not a validated defect. There is no applied, fixed or verified state.
  Externally, accepted comments skew toward refactoring: about 18% for refactoring against about 5% for
  functional comments at Mozilla and Ubisoft (arXiv 2411.07091).
- The escape signal is thin and lagged. CFR snapshots read 1/12, 1/17, 2/17, 0/7 and 0/10. Escapes that are
  never fixed stay invisible (survivorship). SZZ-style tracing loses 17.47% of fixes as "ghost commits"
  (arXiv 2308.05060), which is why the link here is LLM-adjudicated rather than computed from blame.
- Same-family self-review bias: "an LLM evaluator scores its own outputs higher than others'"
  (arXiv 2404.13076). The adjudicator that labels a finding valid should not be the reviewer's own verdict.

**Trade-off.** It is cheap and continuous, and it fills a record that would otherwise stay empty. It gives
marginal yield and a lower bound on escapes, never recall.

**Fit.** High. The parse runs in Python at wrapup or in `hm check`, and adds no prose to execute. That
matters because this project's history shows instrumentation prose raising the surface it was meant to cut:
"a cost-REDUCTION plan raised the shipped surface by 7113 chars, because detection and instrumentation are
both prose" ([wiki:architecture] workflow-loop-efficiency-stage-1).

**Risk.** Low to medium. The risk is the recurring one, an instrument that is built but never fed
(`BASELINE-DELTA-review-loop-empirics.md:219-221`: "neither has a live corpus yet"). A wrapup-time parse that
warns on a missing or unparseable table avoids the silent case. See CLAUDE.md "absent-case = feature black
hole".

### B. Seeded-defect recall audit, scored at the root cause, run per model release

**What it is.**

1. Take K real landed task diffs from this repo, with their SPEC and PLAN.
2. Inject known defects into each: mutation-style, plus one or two hand-written "weakened test" cases, since
   Step 6 claims to catch those (`execute.md.j2:66`).
3. Dispatch `code-reviewer` exactly as execute does.
4. Score a hit only when the finding names the injected root cause at the line. Report hits/seeded with an
   exact (Clopper-Pearson) interval.
5. Attach the procedure as the `measure_cmd` of the Step 6 registry entry, which currently has none
   (`step_sensitivity.py:193-201`: INV, `measure_cmd=""`, `remeasure_on=()`).

**Assumption.** Injected defects are close enough to natural ones that recall on them predicts recall in use.

**Evidence for.**

- It is the only denominator available. `verifier_discrimination.py:27`: "A true false-acceptance rate needs
  labelled ground truth (a fixture corpus with known defects)". `RESEARCH-workflow-steps-vs-model-capability.md`
  Q6 left "A labelled corpus … is a separate piece of work" open.
- External practice is converging on it. Qodo uses "100 real merged PRs … with 580 human-validated injected
  issues" (qodo.ai). Greptile traces real bug-fix PRs back to the commits that introduced them, and counts a
  catch only if the tool "identified the faulty code in a line-level comment" (greptile.com/benchmarks).
- It fixes a known failure of the earlier seeded runs. Those scored the loop, not detection:
  `PLAN-second-opinion-acceptance-gate.md:1385-1389`, "a run where the models simply report nothing on the
  seeded defect proves nothing".
- It matches the TUNE discipline, "측정 전엔 새 모델로 전이하지 않는다" (no move to a new model before it is
  measured; CLAUDE.md, Step sensitivity). The round cap 2→3 change and the C1–C3 cut were deferred to an
  AC-010 re-measure that cannot see review recall (`SPEC-hm-overhaul-p1.md:582,586`).

**Evidence against.**

- Injected defects are not natural ones. Qodo: "injected issues may not perfectly match the defects
  developers naturally write".
- Verdict-level scoring inflates results: "verdict-level recall overestimates true detection by up to 54pp"
  (ICML 2026 Task Verification Bench). The scorer has to judge the root cause, and an LLM judge is noisy
  here: "up to 0.67 on identical input" (`docs/evals/README.md:167`).
- It costs real dispatches. K diffs × M seeds × reviewer calls per model release. The bench already showed
  the ceiling problem: hidden-test pass "1.00 … 1.00 … tie" (`docs/evals/RESULTS.md`).

**Trade-off.** It is the only recall number, but it is synthetic and periodic. It answers "is this model's
reviewer still worth running", not "did this task's review help".

**Fit.** Medium to high. `docs/evals/` already has the bench harness and judge conventions, and
`step_sensitivity` already has a slot for `measure_cmd`.

**Risk.** Medium. The scorer is circular if the same family judges root-cause match. Use a deterministic
match (file plus line window plus mutated token) where possible, and a judge only as a fallback.

### C. Randomized hidden arm (n-of-1 alternating treatments)

**What it is.** On a random subset of tasks, the review runs but its findings are sealed. They are not shown
and not fixed, and are revealed only after a set window. Escapes in the sealed arm, compared with the shown
arm, give the causal effect.

**Assumption.** The developer will accept shipping known-flagged defects on purpose, or will pay a double
review to emulate it.

**Evidence for.** It is the only clean counterfactual. N-of-1 trials are "within-patient, multi-period
crossover studies" with randomized order (Trials 2024; search-summary quote). No published AI-review study
has a defect-outcome holdout. Atlassian is a before/after comparison, and Meta's safety trial measured
review time, not defects (arXiv 2601.01129, 2507.13499).

**Evidence against.**

- At this volume (CFR denominators of 7–17 per 28 days), the escape counts per arm will be 0 to 2. Zero
  escapes in n tasks only bounds the rate at about 3/n (rule of three), so a difference cannot be resolved
  in months.
- It deliberately degrades quality, which goes against 제1목표, "기본 품질을 지키면서" (while keeping basic
  quality).
- An earlier ablation on this project was designed and never authorized: `ABLATION-pass2-2026-08-05.md:44`,
  "NOT YET SELECTED — the run has not been authorized".

**Trade-off.** It is causal but underpowered and costly in quality.

**Fit.** Low. **Risk.** High. Revisit only if A and B disagree in a way that matters.

## Pitfalls

- **Activity is not effect.** A FAIL rate, a drop rate or a consensus-pass rate is not detection
  (`ABLATION-pass2-2026-08-05.md:92-93`: "consensus-pass rate is not detection"). plan-validator's 37/40
  MAJOR_REVISION is the cautionary case: "a gate that always says 'revise' has no discrimination"
  (`RESEARCH-workflow-steps-vs-model-capability.md:221-223`).
- **Acceptance is not prevention.** Resolution counts changes, not averted bugs (arXiv 2601.01129,
  2411.07091). Report P0/P1 accepted findings separately from P2 and below.
- **Agreement is not truth.** "three concurring voices (including two cross-model voters) were all wrong
  about a live P1" (`RESEARCH-review-round-inflation.md:58-60`). Validity labels should come from an outcome
  (a test that went red, an escape, a seeded root cause), not from more voters.
- **Hand-computed rates.** "a hand count was 30× off" (CLAUDE.md). Every rate comes from a CLI reader that
  applies `.ledger-exclusions.json`.
- **A `measure_cmd` that measures the wrong thing.** `measure-cmd-names-wrong-cli-verb`
  (`.claude/memory/failures.md:613-614`) reported second-opinion loss "not the plan-validator verdict
  changes", and nothing executed it in a gate. Whatever B attaches must be run once, and its output checked.
- **Side-only denominators.** Earlier rates came from "a denominator that structurally excludes an entire
  preset class" (`RESEARCH-workflow-time-token-savings.md:264-269`). Say which preset and repo every number
  comes from.
- **Stale figures.** Re-measure after the last edit of a task and record the commit
  ([fail:design] gate-constant-stale-by-later-phase).
- **The cost side is half-blind.** `economics.py:127` still names the retired skills:
  `_VERIFY_SKILLS = frozenset({"hm:review", "hm:verify"})`. Review cost survives only through the
  `-reviewer` suffix rule (`:128`, `:349-357`). The lens fan-out and the second opinion have to be included
  when `reviewers.fanout` or `second_opinion.models` is on.
- **Sycophancy.** Misleading framings flipped up to 72% of decisions in code-smell detection
  (arXiv 2607.10411). The REVIEW table's `authority` column for `rejected` is the author arguing with the
  reviewer. Measure rejected findings, because rejections are where a real defect gets argued away.

## Open Questions (for the SPEC)

1. **Where does the parse run?** Options are wrapup, which sees the final REVIEW and already stages it, or
   `hm check`. Does a missing or unparseable `## Findings` table warn or fail?
2. **Round granularity.** Should the REVIEW table gain a `round` column, so yield per round and defects
   introduced by fixes are recoverable? Or is per-review enough? (Cost: a few chars of execute prose.)
3. **Validity state.** Should `accepted` split into "fixed + gate green" versus "accepted, unfixed", or is a
   wrapup-time disposition check enough?
4. **Which ledger?** Revive `review-*.jsonl` with a new schema version, reuse `review_telemetry` (whose
   docstring still says "Per-`/hm:review`"), or start a new file? The orphaned modules
   (`review_run`, `review_consensus`, `review_complexity`, `stage_agent_ledger` emit) also need a decision:
   retire or keep.
5. **Escape attribution owner.** Is it `/hm:metrics` adjudication, so that `later_regression_link` lives in
   delivery-metrics rows, or a separate verb? What counts as "reviewable from the diff and SPEC"?
6. **Seeded audit size.** What K × M gives a useful interval, which mutation operators are used, and how is a
   hit matched (deterministic window first, judge fallback)? Does it live in `docs/evals/` or under
   `step_sensitivity`'s `measure_cmd`?
7. **Decision rule, pre-registered.** What result would cut review, cap it at 1 round, or turn the fan-out
   back on? It must be fixed before the first reading
   (`feedback_honor_preregistered_rules`: 사전 규칙은 발동 후 재해석 금지, a pre-set rule is not
   reinterpreted after it fires).
8. **Scope beyond this repo.** Is this a rendered-harness feature for every consumer project, or
   dogfood-only first? Production ledger rows have been zero before (`RESEARCH-workflow-steps-vs-model-capability.md`
   Q8).

## Sources

**Web** (16)
1. Resolving Code Review Comments with ML, Google 2024: https://research.google/pubs/resolving-code-review-comments-with-machine-learning/
2. RovoDev Code Reviewer, Atlassian 2026: https://arxiv.org/abs/2601.01129
3. AI-Assisted Fixes to Code Review Comments at Scale, Meta 2025: https://arxiv.org/abs/2507.13499
4. Impact of LLM-based Review Comment Generation in Practice, 2024: https://arxiv.org/abs/2411.07091
5. Expectations, Outcomes, and Challenges of Modern Code Review, MSR 2013: https://www.microsoft.com/en-us/research/?p=164195
6. Evaluating SZZ Implementations: Linux Kernel, FSE 2025: https://arxiv.org/abs/2308.05060
7. Greptile AI Code Review Benchmarks, 2025, vendor-run: https://www.greptile.com/benchmarks
8. Qodo, AI code review benchmarks, 2026, vendor: https://www.qodo.ai/glossary/what-is-ai-code-review-benchmarks/
9. SWR-Bench, 2025: https://arxiv.org/abs/2509.01494
10. Task Verification Bench, ICML 2026: https://icml.cc/virtual/2026/82770
11. N-of-1 trials methodological review, Trials 2024 (search-summary quote): https://link.springer.com/article/10.1186/s13063-024-08100-1
12. Single-case alternating treatments designs (search-summary quote): https://www.recercat.cat/handle/2445/134418
13. Rule of three (statistics): https://en.wikipedia.org/wiki/Rule_of_three_(statistics)
14. LLM Evaluators Recognize and Favor Their Own Generations, 2024: https://arxiv.org/abs/2404.13076
15. LLMs Cannot Self-Correct Reasoning Yet, ICLR 2024: https://arxiv.org/abs/2310.01798
16. Mitigating LLM Sycophancy in Code Smell Detection, 2026: https://arxiv.org/abs/2607.10411

**Library docs:** none fetched. The topic is not library-specific.

**Codebase**, opened directly where marked ✔:
- ✔ `src/harness_maker/templates/stages/execute.md.j2:52,64-76`: the gate runs before review, and review
  writes the REVIEW table
- ✔ `src/harness_maker/codex_ledger.py:33,62,76`: `later_regression_link` placeholder, 0/597 filled
- `src/harness_maker/templates/stages/wrapup.md.j2:53`: REVIEW docs are staged at land
- `src/harness_maker/step_sensitivity.py:65,193-201`: Step 6 is INV with no `measure_cmd`, and `_BENCH` is
  unattached
- `src/harness_maker/economics.py:127-128,349-357`: stale `_VERIFY_SKILLS`, and the `-reviewer` suffix rule
- `src/harness_maker/delivery_metrics.py:41,155-177,286,517`: CFR and churn, with no task-level linkage
- `src/harness_maker/verifier_discrimination.py:20-27`: "accept rate is not a true-positive rate"
- `src/harness_maker/commands/make.md:252`: stage_agent_ledger is inert since 0.64.0
- Base `.claude/observability/`: `review-*.jsonl` 157 rows (2026-05-11 to 10-04), `stage-agents.jsonl`
  344 rows with no code-reviewer rows, `review-payloads/` 82 files with no dispositions and `caused_by`
  never `fix-*`

## Related Internal Docs

- `specs/SPEC-hm-overhaul-p1.md`
  - :17-19, :584: eval 3, "no hidden-test or trap gain at tiers 1–2"
  - :188-199: AC-010 bar and result
  - :575-586: the review cuts deferred to AC-010
  - :633-636: "AC-010 does not see that cost"
- `docs/evals/RESULTS.md`, `docs/evals/README.md`: bench ceiling (1.00 tie) and judge noise (0.67)
- `work-docs/ABLATION-pass2-2026-08-05.md`: the ablation was designed and not run, and its natural-experiment
  pitfalls (rounds ≠ reviews, no severity field)
- `work-docs/RESEARCH-workflow-loop-efficiency.md:98-108`: the review funnel, 1.9%, 3.1% and 87% drops
- `work-docs/RESEARCH-workflow-time-token-savings.md:24-27,135-137,264-269`: stage-agent rates, silent
  dispatch loss and a Side-only denominator
- `work-docs/RESEARCH-workflow-steps-vs-model-capability.md:203,221-225,270-276`: discrimination unproven,
  and Q6–Q8
- `work-docs/RESEARCH-review-loop-empirics.md`, `work-docs/PLAN-review-loop-empirics.md`,
  `work-docs/BASELINE-DELTA-review-loop-empirics.md`: fan-out yield, churn r=0.837 (n=6), and instruments
  never fed
- `work-docs/RESEARCH-reviewer-lens-fanout-merge.md:106-114`: the +52% re-read, and C firmware 43% vs 50%
- `work-docs/RESEARCH-ai-review-exit-criteria.md:71-77`, `work-docs/RESEARCH-review-round-inflation.md:19,58-60`:
  fix-introduced defects about 1:1, and voter agreement is not truth
- `work-docs/PLAN-second-opinion-acceptance-gate.md:1385-1389`: seeded runs scored the loop, not detection
- `.claude/intent.yaml` `q_825d374c6331ed22`: the open fan-out recall and plan-validator discrimination
  question
- Memory: [wiki:architecture] workflow-loop-efficiency-stage-1, [fail:design] hardening-with-no-measured-effect,
  [fail:design] gate-constant-stale-by-later-phase
