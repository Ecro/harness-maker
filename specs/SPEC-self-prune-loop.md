---
type: spec
task_slug: self-prune-loop
status: approved
created: 2026-11-23
tags: [bench, eval, self-prune, model-release]
test_framework: pytest
interview_rounds: 1
summary: When a new default model ships, hm ablates up to 3 candidate instruction blocks on the bench, one at a time, and proposes (never auto-PRs) the cuts that pass deterministic guards.
---

# SPEC-self-prune-loop

## Intent

hm should shrink as models improve: instructions the current model no longer needs cost tokens on
every call. The manual Opus 5.5 cut study (2026-11-17) showed that cutting by reading alone goes
wrong (rubric skills and the reasoning template were proposed, then withdrawn), and that the bench
can be saturated so that "no difference" only prices a step (`[fail:design]
cut-on-saturated-eval-prices-not-values`). So a cut needs an ablation on the bench with guards that
can fail. The step-sensitivity registry alone yields almost no candidates (29 of 31 entries are
INV, 1 TUNE, 1 HOST), so candidates are prose blocks inside rendered files, not steps.

The DRI decided the loop's shape on 2026-11-23 (decision card): run only when a new default model
ships, and output proposals only, never a PR of cuts.

## Outcomes

- The bench has one generic ablation arm, `hm-variant`, driven by a variant file of edits on the
  rendered harness. `hm-novalidator` stays as it is.
- `scripts/self_prune.py` validates candidates (`plan`), turns bench rows into verdicts
  (`decide`), and answers whether a model was already measured (`status`).
- The six non-negotiables (per-task worktree, TDD RED gate, SDD, human approval, IRR lock,
  understanding-delta summary) can never be ablated: `plan` refuses edits inside their sections.
- Verdicts accumulate in `docs/evals/prune-ledger.jsonl`; `decide` prints a proposal table for
  the weekly report.
- `docs/evals/SELF-PRUNE.md` holds the procedure and the trigger prompt; the weekly routine
  gains a detection step (project files, outside the repo).

## In-Scope Scenarios

- **S1 (normal).** Given a baseline out dir (arms plain,hm, tier 2) and one out dir per candidate
  (arm hm-variant), all on the same model, harness and bench, when `decide` runs, then each
  candidate gets adopt, reject or hold with reasons, one ledger row each, and a markdown table.
- **S2 (edge).** Given a candidate whose `detectable_by` is empty (no bench cell can fail the way
  the block prevents), when it otherwise passes every guard, then its verdict is hold
  ("priced, not valued"), never adopt.
- **S3 (failure).** Given a candidate edit that drops or rewrites text inside a protected section,
  or an edit that matches nothing, when `plan` or the bench template build runs, then it is
  refused before any model spend.
- **S4 (failure).** Given a baseline and a candidate dir with different model, harness_sha or
  bench_hash, when `decide` runs, then it exits 2 and writes nothing.

## Non-Goals

- Opening PRs or editing templates from the loop (DRI decision: proposals only).
- Knob ablation by re-rendering with an edited harness.yaml (`make --update` refused a hand-edited
  harness.yaml in a probe, rc=1); a knob whose value is rendered as text is ablated by a `replace`
  edit instead.
- Combining candidates in one arm, or measuring models other than the default one.
- Running a real bench in tests or in CI (CI has no `claude`).
- Automatic candidate generation code: the triggered session's LLM writes the candidates file.

## Constraints

| Constraint | Value |
|---|---|
| Language / tests | Python 3.12, pytest, ruff, mypy --strict |
| Candidates per run | at most 3 |
| Budget | `--total-budget-usd` on every bench call; about $150 per model (estimate) |
| Runner hash | unchanged when no variant is given (existing pinned hashes stay valid) |
| Writes | atomic (`atomic_write` / append helper), per implementation-patterns.md |
| Where it runs | a cloud Claude Code session; never GitHub Actions |

## Irreversible Decisions

none

## Acceptance Criteria

### AC-001: hm-variant applies drop and replace edits to the rendered harness

`apply_variant(root, variant)` applies each edit in order. `drop_heading` removes the section that
starts at a line equal to or starting with that heading text, up to the next heading of the same
or higher level (or end of file). `replace` substitutes `old` with `new` when `old` occurs exactly
once. An edit that changes nothing, a missing file, or a `replace` whose `old` occurs zero or
several times raises `VariantError`.

### AC-002: the bench wires hm-variant safely

`hm-variant` is an hm arm. `run` exits 2 when the arms include `hm-variant` without `--variant`,
or `--variant` is given without that arm. `runner_hash(...)` without a variant equals today's value;
with a variant sha it differs, so rows of different variants never share an out dir. Each
hm-variant row records `variant` (the id).

### AC-003: protected sections cannot be ablated

`self_prune.protected_hits(root, variant)` returns every edit that touches a protected section: a
`drop_heading` whose removed span contains a protected heading, or a `replace` whose `old` sits
under a protected heading. `PROTECTED` names a section for each of the six non-negotiables, and
every protected heading exists in a fresh render of the bench fixture.

### AC-004: plan validates the candidates file

`plan --candidates <file> --render <dir> --out <dir>` exits 0 and writes one `<id>.json` variant
file per candidate when there are at most 3 candidates with unique ids, each with a
`detectable_by` list and edits that apply to a copy of the render with no protected hit; else it
exits 2, names each problem, and writes nothing.

### AC-005: decide applies the guard rule

For one candidate, comparing its tier-2 hm-variant rows with the baseline's tier-2 hm rows:
reject when solved count or trap catches fall; else hold when the mean judge overall falls by more
than 0.3, mean cost does not fall by at least 3%, stalls rise, or `detectable_by` is empty; else
adopt. When the two arms ran different (task, rep) cells, the verdict is hold whatever the
counts say. Mismatched model, harness_sha, bench_hash, judge_model or max_budget_usd, a dir with
no usable tier-2 rows, or candidate rows whose `variant` is not the id in its `variant.json`
exits 2 and writes nothing.

### AC-006: decide records verdicts and status reads them

`decide` appends one ledger row per candidate (model, harness_sha, candidate id, verdict,
reasons, metrics, decided_at) and prints a markdown table with a Maker-pasteable "고쳐줘" line for
each adopted candidate. `status --model <id> --ledger <file>` prints `measured` and exits 0 when
the ledger holds a row for that model, else prints `unmeasured` and exits 1.

## Verification

| Scenario | Mode | Test |
|---|---|---|
| S1 | unit | tests/unit/test_self_prune.py (AC-005, AC-006) |
| S2 | unit | tests/unit/test_self_prune.py (AC-005 golden row) |
| S3 | unit | tests/unit/test_self_prune.py (AC-001, AC-003, AC-004) |
| S4 | unit | tests/unit/test_self_prune.py (AC-005) |
| bench wiring | unit | tests/unit/test_self_prune.py (AC-002) |
| first real run | manual | the triggered session after merge, on the current default model |

## Open Questions

none

## Refinement Decisions

- **Protection lives in a `PROTECTED` table of rendered headings, not a registry flag.** The
  design doc proposed a `protected` field on `step_sensitivity` entries, but registry ordinals do
  not match rendered headings (wrapup renders `Steps 6 → 7.6`, the worktree section has no Step
  ordinal). A structural check against a real render catches renames. Undo cost: minutes.
- **One out dir per candidate, compared with a baseline dir.** Reuses the bench's resume and
  mixed-rows refusal unchanged; the variant sha enters `runner_hash` only when set. Undo: minutes.
- **No `prune-models.json`.** "Measured" is derived from the ledger, one file instead of two.
- **Guards on tier 2 only.** Tier 1 is saturated (plain 15/15). Candidate arms skip tier 1 to
  halve cost; the baseline still runs tier 1 for `hm_cost_ratio_small`.
- **Judge threshold 0.3** sits under the 3-sample band (2/3 / sqrt(3) ≈ 0.38): a larger drop is
  more than noise. Pass and trap use "any drop rejects", conservative at n=21.
- **The decision rule is deterministic Python**, an exception to "LLM judgment first": it is the
  loop's safety rail (an oracle), and candidate selection stays with the LLM.
- **Intent: none.** No active intent; HM-LIGHT-LANE (proposed) targets the cost ratio of small
  tasks, which this serves only indirectly. Relevant open question: `q_fe8d71f72d240ed4` (time
  from model release to TUNE re-measurement has no record field); the ledger's `decided_at`
  provides one.
- **Review round 1 tightened protection and decide** (code-reviewer, 2026-11-23): paths are
  normalised before comparison; edits are checked one by one against the text the edits before
  them leave, over every heading the change spans and every enclosing section; decide refuses
  empty or foreign-variant dirs and holds on unequal cells. These only narrow what the approved
  ACs allow; the machine.yaml is unchanged. Undo: minutes.
- **No irreversible decisions.** The ledger and variant formats are new and read only by
  `self_prune.py`; changing them now costs minutes.
