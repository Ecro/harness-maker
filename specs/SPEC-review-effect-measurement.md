---
type: spec
task_slug: review-effect-measurement
status: approved
created: 2026-10-17
tags: [review, measurement, observability, ledger, escape-attribution, seeded-defects]
test_framework: pytest
interview_rounds: 2
summary: Record each review's outcome at land, attribute post-merge escapes, and audit recall with seeded defects
---

# SPEC — review-effect-measurement

## Intent

Since 0.64.0, review is one `code-reviewer` dispatch inside `/hm:execute` Step 6. Nothing measures whether
it has an effect.

- Every machine record of review was orphaned by the overhaul: `commands/make.md:252`, "inert since 0.64.0".
- The only per-review artifact left is the `## Findings` table that Step 6 writes (`execute.md.j2:76`), and
  no code reads it.
- Escape attribution has never been populated: `later_regression_link` is null in 597/597 rows.
- The one-reviewer default rests on stage-level bench evidence (eval 3, hidden tests at a 1.00 ceiling),
  not on what the review catches or misses.

The project's purpose says "제값을 못 하는 장치는 걷어낸다" (remove a device that does not earn its keep).
That requires a number. Open question `q_825d374c6331ed22` has stayed anecdotal for lack of one.

Because `hm check --slug` is green before Step 6 runs (`execute.md.j2:52`), every finding the review accepts
is marginal over the deterministic gates by construction. Marginal yield therefore needs no counterfactual
machinery. Recall needs a denominator, which only seeded defects provide. Escapes need post-merge
attribution.

Research: `work-docs/RESEARCH-review-effect-measurement.md` (Approach A + B, C rejected).
Intent: none.

## Outcomes

1. Every `wrapup_land` writes one `review` row per task to `<base>/.claude/observability/review_effect.jsonl`.
   The path is under `--base`, never `--worktree`: `task-land` deletes the worktree, and the ledger is
   gitignored, so a worktree copy would vanish. The row counts the task's findings by severity ×
   disposition, or says why it could not: `absent`, `unparseable` or `none`. A ledger failure never changes
   the land's exit code or commit.
2. `/hm:metrics` lists remediation commits that landed after the first recorded review, with slug hints for
   the task that introduced them. The operator's LLM judgment of each is recorded as an `escape` row: which
   task introduced it, whether that task's review flagged it, and whether it was reviewable from the diff.
3. `hm review_effect seed` plants deterministic, manifest-described defects inside a real diff.
   `hm review_effect score` matches a reviewer's findings against the manifest and can record a `recall` row.
   `docs/reference/review-effect.md` describes the in-session audit procedure and the pre-registered decision
   rule.
4. `hm review_effect report` prints raw counts with exact 95% Clopper-Pearson intervals for the three
   quantities: marginal yield, escape miss rate and seeded recall. It never prints a bare percentage, and it
   applies `.ledger-exclusions.json`.
5. The `execute` / `Step 6` entry in `step_sensitivity.REGISTRY` carries a `measure_cmd` that names
   `hm review_effect report`, and `remeasure_on=("model_release",)`.

## In-Scope Scenarios

- **S1 (normal).** A task lands with `work-docs/REVIEW-foo-2026-10-17.md` whose findings table holds
  one accepted P1, one rejected P2 and one duplicate. **When** `wrapup_land --slug foo` succeeds, **then**
  the ledger gains one `review` row for `foo`:
  - `status: parsed`
  - `counts == {"P1": {"accepted": 1}, "P2": {"rejected": 1, "duplicate": 1}}` (keyed by the table's
    severity)
  - `severe_accepted == 1`
  - the REVIEW file name.
- **S2 (edge).** A task lands with no `REVIEW-<slug>-*.md` (for example, an exempt docs task), or with a
  REVIEW whose table body is the single word `none`. **When** it lands, **then** the row has
  `status: absent` (with no counts) or `status: none` (with zero counts). A REVIEW with no parseable
  `## Findings` table gets `status: unparseable` and one warning line on stderr.
- **S3 (failure).** The observability directory is unwritable. **When** `wrapup_land` runs, **then** the
  commit and pop happen exactly as without the ledger. The receipt carries
  `steps.review_effect.status == "error"`, and the exit code is unchanged.
- **S4 (escape).** An earlier commit added `specs/SPEC-bar.md` and a function. A later
  `fix: off-by-one in bar` commit changes that function's lines. **When** `escape-candidates` runs, **then**
  the fix is listed with hint slug `bar`. After
  `hm review_effect escape --commit <sha> --introduced-by bar --flagged no --reviewable yes --reason "…"`,
  `report` counts one missed escape out of one attributed.
- **S5 (seeded recall).** `seed --root <wt> --base <rev> --count 3 --seed 7` mutates three lines in `.py`
  files changed between `<rev>` and HEAD, and writes a manifest. A findings file naming two of those
  file:line positions (±3) **scores** 2/3. `--record` appends a `recall` row.

## Non-Goals

- A randomized hidden-arm or holdout design (Approach C).
- A `round` column in the REVIEW table, and any change to execute's prose.
- Retiring the orphaned pre-0.64 modules: `review_telemetry`, `review_run`, `review_consensus`,
  `review_complexity`, and the `stage_agent_ledger` emit.
- Cost integration with `economics`, including the stale `_VERIFY_SKILLS`.
- LLM-judge scoring of seeded hits (the match is deterministic only).
- A headless bench runner for recall.
- Automating the decision rule. It is recorded, not executed.
- Filling `second-opinion.jsonl`'s `later_regression_link`.

## Constraints

| Constraint | Detail |
|---|---|
| Test framework | `pytest`; unit tests for the parser, CI, seed and score, plus tmp-git-repo integration tests for land and escape-candidates |
| Language | Python only, `mypy --strict`, `ruff`. No Bash scripts |
| Writes | Atomic appends, following `docs/reference/implementation-patterns.md`. No plain `open(path, "w")` |
| External commands | `git` via `subprocess` with a list argv and a timeout. No `shell=True` |
| Land safety | The ledger step is best-effort. Any exception is caught into the receipt. The step runs only after the commit exists |
| Local only | The ledger lives under `.claude/observability/`, which stays gitignored. No network |
| Rates | Every rate comes from `report`, never a hand count. Output shows `k/n [lo, hi]` |
| Surface | No prose added to the `execute` or `wrapup` stage templates. `/hm:metrics` gains at most one step |
| Rendered-harness pin | New verbs reach dogfood only after the next release (the rendered harness runs the released cache) |
| Dependencies | Standard library only. No scipy or numpy. Clopper-Pearson by bisection on the exact binomial tail |
| Seed safety | `seed` refuses a dirty tree (exit 1) and prints the exact restore command. The reference doc says to seed only a scratch worktree, never a task worktree |

## Irreversible Decisions

| id | decision | category | rationale |
|---|---|---|---|
| IRR-001 | New local ledger `<base>/.claude/observability/review_effect.jsonl`, `schema_version: 1`, events `review` / `escape` / `recall`. Fields are listed under **Ledger rows** below | schema/file format/storage layout | A reader is committed to this shape. Later changes need a version bump and a migration-tolerant reader |
| IRR-002 | New CLI contract `hm review_effect {escape-candidates,escape,seed,score,report}` | public API/CLI contract | It is named from `/hm:metrics` prose, the reference doc and `step_sensitivity.measure_cmd` |

**Ledger rows.** Every row carries `schema_version`, `event`, `ts` (UTC ISO-8601), `slug` and
`harness_version`, so a `.ledger-exclusions.json` slug match drops a task's rows of every event type
together.

| Event | Fields | Notes |
|---|---|---|
| `review` | `commit` (the worktree HEAD after the land commit), `review_file` (or null), `status` ∈ {`parsed`, `none`, `absent`, `unparseable`}, `counts` {severity: {disposition: n}}, `severe_accepted`, `unrecognized_n` | |
| `escape` | `commit` (the fix), `verdict` ∈ {`escape`, `not-escape`}, `flagged`, `reviewable`, `reason` (≤ 200 chars) | `slug` is the introducing task, or `unknown` |
| `recall` | `hits`, `seeded`, `model`, `manifest_sha256` | `slug` is the audited task |

## Acceptance Criteria

### AC-001: REVIEW findings table parses into severity × disposition counts
`parse_review(text)` takes the **whole REVIEW file**. It reads the table under the first line that is
exactly `## Findings`, and it looks up columns by header name, so extra columns are tolerated and the
`severity` and `disposition` columns are required. It returns:

- `status`:
  - `parsed`;
  - `none`, when the section's first non-empty line starts with `none`, so trailing text is allowed;
  - `unparseable`, when there is no `## Findings` heading, no table under it, or a required column is
    missing.
- `counts[severity][disposition]`.
- `severe_accepted`, the number of accepted findings with severity P0 or P1.
- `unrecognized_n`.

Severity is normalised by stripping markdown emphasis and backticks and taking the leading `P0`–`P3` token,
case-insensitively. Any other value is counted under `counts["unrecognized"]`, adds to `unrecognized_n` and
emits one stderr warning. It is never treated as non-severe silently. A table under any other heading is
ignored.

### AC-002: wrapup_land records one review row per landed task, under --base
After the land commit exists and **before** the post-commit pop, `wrapup_land` appends one `review` row to
`<base>/.claude/observability/review_effect.jsonl`.

- It reads only files whose names match `REVIEW-<slug>-\d{4}-\d{2}-\d{2}\.md` exactly in the worktree's
  `work-docs/`. When there are several, it reads the latest date, because each review overwrites its dated
  doc.
- With no match it writes `status: absent`.
- The row is keyed by `(slug, commit)`. A rerun through the `already-present` resume path finds the key and
  writes nothing.
- The receipt carries `steps.review_effect`.

### AC-003: a ledger failure never changes the land outcome
With the ledger write forced to fail, `wrapup_land` returns the same exit code and creates the same commit
tree as with a working ledger, and the receipt records `steps.review_effect.status == "error"`.

### AC-004: escape-candidates lists post-review remediation commits with slug hints
The verb lists first-parent commits on the base branch that meet all of these:

- the subject matches `delivery_metrics._REMEDIATION_SUBJECT`;
- the committer date is at or after the earliest `ts` of the non-excluded `review` rows;
- there is no `escape` row for the commit yet.

For each candidate, blame at `<fix>^` over the lines the fix deletes or modifies. Every commit that blame
names is mapped to the slugs of the `specs/SPEC-<slug>.md` paths that commit touches. A fix that only adds
lines gets hint `[]`.

An absent ledger, or one with no review rows, prints one stderr warning and an empty list, and exits 0.

### AC-005: escape records an attribution row
`hm review_effect escape --commit <sha> --verdict escape|not-escape --introduced-by <slug|unknown>
--flagged yes|no|not-reviewed|unknown --reviewable yes|no|unknown --reason "<line>"` validates its
arguments. A bad enum value exits 2. It appends one `escape` row and refuses a second row for the same
commit (exit 1). `not-escape` removes the candidate from future listings and never enters a denominator.

### AC-006: Clopper-Pearson interval is exact
`clopper_pearson(k, n)` uses the standard library only. It matches published exact 95% bounds within 1e-4,
and `lo ≤ k/n ≤ hi` holds for every `0 ≤ k ≤ n ≤ 200`. `n == 0` returns `(0.0, 1.0)`.

### AC-007: report prints counts with intervals and applies exclusions
`report` (text and `--json`) first dedupes `review` rows by slug, keeping the last, and drops every row a
`.ledger-exclusions.json` entry matches. It then shows each of the following as `k/n [lo, hi]`:

- **Reviews by status**, with `unrecognized_n` summed.
- **Marginal yield:** k = rows with `severe_accepted ≥ 1`, and n = rows with status ∈ {`parsed`, `none`}.
- **Escape miss rate:**
  - n = `escape` rows with `verdict: escape` whose slug has a counted review row;
  - k = the subset of those with `flagged: no` and `reviewable: yes`.
- **Seeded recall:** the sum of `hits` over the sum of `seeded`.

An empty or absent ledger prints zeros and exits 0.

### AC-008: seed plants deterministic manifest-described defects inside the diff
`seed --root <tree> --base <rev> --count M --seed N` refuses a dirty tree, exiting 1 and printing the
restore command.

It mutates at most M lines. When fewer candidates exist, it mutates fewer and says so. A line is a candidate
when all of these hold:

- it is an added or modified line of `git diff <base>..HEAD` in a `.py` file;
- it is the first line of an AST `Compare`, `BoolOp` or integer `Constant` node;
- it is not inside a docstring or comment.

The operators are:

- `cmp-flip`: `<`↔`<=`, `>`↔`>=`, `==`↔`!=`;
- `boolop-swap`: `and`↔`or`;
- `const-off-by-one`: `n` → `n + 1`.

It writes a manifest `[{file, line, operator, original, mutated}]` with repo-relative POSIX paths. The
manifest's `(file, line)` set equals the lines `git diff -U0` reports as changed by the seeding. The same
seed gives the same manifest.

### AC-009: score matches findings to seeds within a line window
`score --manifest <m.json> --findings <f.json>` reads findings as a JSON list of `{file, line}`. This is the
code-reviewer's output fields; `line` may be null, and a null never hits.

- A finding can hit a seed when the files match and `|line − seed.line| ≤ 3`. Files match when they are
  equal, or when one is a `/`-boundary suffix of the other.
- Hits are a **maximum bipartite matching**, so each finding hits at most one seed.
- `--record --slug <slug> --model <name>` appends a `recall` row.

### AC-010: /hm:metrics renders the escape-attribution step
Every rendered `/hm:metrics` names `hm review_effect escape-candidates` and `hm review_effect escape`. Only
the Claude target renders it (`commands/hm/metrics.md`); Codex has no metrics surface.

### AC-011: step_sensitivity Step 6 carries a runnable measure_cmd
The registry entry for `execute` `Step 6` has `remeasure_on == ("model_release",)` and a `measure_cmd` of
the form `harness-maker: hm review_effect report …`. The test strips the `<repo>: ` prefix, runs **that
exact registered command** (with the `hm` prefix resolved to this checkout) against an empty project root,
and asserts exit 0.

### AC-012: reference doc records the audit procedure and the pre-registered rule
`docs/reference/review-effect.md` exists. It contains:

- the seeded-audit procedure: in a scratch worktree, run `hm review_effect seed`, dispatch `code-reviewer`
  in session on the seeded diff, save its `{file, line}` findings, and run `hm review_effect score` with
  `--record`;
- the ±3-line false-hit limit;
- these two rule sentences verbatim:

> **Rule 1.** With at least 20 counted reviews (status parsed or none, deduped, after exclusions), if the 95% upper bound of marginal yield is below 25% and the 95% upper bound of seeded recall is below 50%, register a candidate task that makes review opt-in.

> **Rule 2.** With at least 20 counted reviews, if the 95% lower bound of the escape miss rate is above 50%, register a candidate task that reconsiders the lens fan-out default.

- the sentence "This rule is never reinterpreted after it fires."

## Verification

| Scenario | Mode | Test |
|---|---|---|
| S1 | unit + integration | AC-001 golden tables; AC-002 tmp-repo land |
| S2 | unit + integration | AC-001 `none` / unparseable cases; AC-002 absent case |
| S3 | integration | AC-003 differential land, with and without a failing ledger |
| S4 | integration | AC-004 tmp repo with an introducing and a fixing commit; AC-005; AC-007 |
| S5 | unit + integration | AC-008 tmp repo diff check; AC-009 golden |
| — | unit | AC-006, AC-010 (render), AC-011, AC-012 |
| Live audit | manual | One seeded audit on this repo after release, recorded with `--record`. Not a gate |

## Open Questions

none

## Refinement Decisions

- **Round 1** (the user, mid-research, 2026-10-17): "너의 추천대로 수락 진행해" (proceed, accepting your
  recommendation). This accepted RESEARCH's A + B and rejected C.
- **Round 2** (AskUserQuestion):
  - scope = A + B core (seed and score verbs plus the procedure doc, with no headless bench runner);
  - register the proposed decision rule (AC-012);
  - intent = none;
  - **Approve this SPEC and end interview**.
- **Recording at `wrapup_land`, not in template prose.** It runs exactly once per landed task, after the
  final REVIEW exists, and it costs 0 surface. Following the CLAUDE.md note on `derive_deliverable_globs`,
  an un-re-rendered harness gets it too.
- **Absent case is defined** (`status: absent`). This follows the "absent-case = feature black hole"
  correction.
- **A deterministic seed match, not an LLM judge.** Judge noise is "up to 0.67 on identical input". The
  ±3-line window accepts some false hits; the reference doc names that limit.
- **spec-validator (one advisory pass, MAJOR_REVISION, 3 critical) folded in without changing the approved
  design.**
  - The ledger is pinned to `--base`.
  - The severity vocabulary is fixed, with an `unrecognized` bucket.
  - The REVIEW filename is date-anchored, latest date wins.
  - Whole-file parse, by header name.
  - The `(slug, commit)` key, written before the pop.
  - The cutoff is defined by committer date, plus absent-ledger behaviour.
  - A `not-escape` verdict.
  - A denominator for each quantity.
  - The findings schema, suffix match and bipartite matching.
  - Seed candidates are restricted to diff hunks and AST nodes, with an operator list.
  - Row fields are listed per event.
  - The `record` verb is dropped.
  - A stdlib-only constraint.
  - AC-011 runs the registered command.
  - Seed refuses a dirty tree.
  - The rule sentences are verbatim.

  None was left open.
- **Post-land correction (IRR-001 path, re-approved by the DRI on 2026-10-17).** The ledger was
  `review-effect.jsonl`, which matches the `review-*.jsonl` glob that `review_telemetry`,
  `verifier_discrimination`, `feedback.telemetry_grep` and `verification_cache` read as review telemetry.
  On base, its rows failed `ReviewTelemetryRecord` validation. It was renamed to `review_effect.jsonl` before
  any push, and a regression test pins it outside that glob.
- **Execute-time correction (AC-010 wording only).** Codex never rendered `/hm:metrics`, so "both the Claude
  and Codex variants" was vacuous. The machine predicate, which is over every rendered variant, is unchanged.
- **Escape attribution is LLM-judged, with deterministic slug hints.** SZZ-style tracing alone loses about
  17% of fixes as ghost commits.
- **Autopilot is retired (0.64.0).** The user asked for autopilot, so the stages are chained by hand
  without stopping (execute, then wrapup). There is no push.
