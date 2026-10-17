# Review effect measurement

SPEC: `specs/SPEC-review-effect-measurement.md`. RESEARCH: `work-docs/RESEARCH-review-effect-measurement.md`.

`/hm:execute` Step 6 runs one `code-reviewer` after `hm check` is already green, so every finding it accepts
is one the deterministic gates missed. This page covers how that effect is recorded, and what decision the
numbers trigger.

## What is recorded

All rows go to `<base>/.claude/observability/review_effect.jsonl` (local, gitignored, `schema_version: 1`).

| Event | Written by | When |
|---|---|---|
| `review` | `wrapup_land` | Once per landed task, keyed `(slug, commit)`. It reads the latest `work-docs/REVIEW-<slug>-<YYYY-MM-DD>.md` `## Findings` table |
| `escape` | `hm review_effect escape` | From `/hm:metrics` Step 1.4, one verdict per remediation commit |
| `recall` | `hm review_effect score --record` | One seeded audit (below) |

A `review` row's `status` is one of four values:

- `parsed`
- `none`: the review found nothing
- `absent`: there is no REVIEW file
- `unparseable`: there is no `## Findings` table, or it has no `severity` or `disposition` column

Severity is read as `P0` to `P3`. Any other value is counted under `unrecognized` with a warning; it is never
treated as non-severe silently. A ledger failure never changes the land, and the receipt shows
`steps.review_effect.status: error`.

## Reading it

`hm review_effect report --root .` (or `--json`) prints three quantities, each as `k/n [lo, hi]` with an exact
Clopper-Pearson interval. Never quote a bare percentage.

- **Marginal yield.** Reviews with at least one accepted P0/P1, over counted reviews. A counted review has
  status `parsed` or `none`, is deduped by slug with the last row kept, and comes after
  `.ledger-exclusions.json`.
- **Escape miss rate.** Escapes with `flagged: no` and `reviewable: yes`, over every `verdict: escape` row
  whose slug has a counted review.
- **Seeded recall.** Seeded defects hit, over seeded defects.

Limits:

- `accepted` means a decision, not a validated defect.
- Escapes that are never fixed are invisible.
- A seed hit is a finding in the same file within ±3 lines. That window accepts some false hits: a finding
  about something else on a nearby line counts.

## Seeded audit (per model release)

`step_sensitivity` lists this as the execute Step 6 `measure_cmd` (`remeasure_on: model_release`).

1. Pick a landed task diff. Make a **scratch worktree** at its landed commit:
   `git worktree add /tmp/audit <commit>`. Never use a task worktree, because `seed` edits files.
2. `hm review_effect seed --root /tmp/audit --base <commit>^ --count 5 --seed <n> --manifest /tmp/m.json`.
   It refuses a dirty tree. It mutates only added or modified executable lines in the diff's `.py` files,
   with three operators:
   - `cmp-flip`: `<`↔`<=`, `>`↔`>=`, `==`↔`!=`
   - `boolop-swap`: `and`↔`or`
   - `const-off-by-one`: `n`→`n + 1`
3. In session, dispatch `code-reviewer` on `git -C /tmp/audit diff <commit>^` together with that task's SPEC,
   exactly as execute Step 6 does. Do not tell it that defects were seeded. Save its findings as a JSON list
   of `{file, line}` to `/tmp/f.json`.
4. `hm review_effect score --root . --manifest /tmp/m.json --findings /tmp/f.json --record --slug <slug>
   --model <model>`.
5. `git -C /tmp/audit checkout -- .`, then `git worktree remove /tmp/audit`.

## Pre-registered decision rule

Fixed by the DRI on 2026-10-17 (SPEC round 2), before any reading existed. It registers a candidate task; it
does not change anything by itself.

> **Rule 1.** With at least 20 counted reviews (status parsed or none, deduped, after exclusions), if the 95% upper bound of marginal yield is below 25% and the 95% upper bound of seeded recall is below 50%, register a candidate task that makes review opt-in.

> **Rule 2.** With at least 20 counted reviews, if the 95% lower bound of the escape miss rate is above 50%, register a candidate task that reconsiders the lens fan-out default.

This rule is never reinterpreted after it fires. A better rule goes to the next measurement window, not this
one.
