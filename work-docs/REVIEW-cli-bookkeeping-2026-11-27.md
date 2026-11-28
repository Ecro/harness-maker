---
type: review
task_slug: cli-bookkeeping
created: 2026-11-27
spec: "[[SPEC-cli-bookkeeping]]"
reviewer: code-reviewer (1 pass)
verdict: fixed
---

# REVIEW: cli-bookkeeping

One code-reviewer pass over the diff against the SPEC and PLAN. No critical findings. Every
fixable finding was fixed in the same execute; the rest are recorded below with the reason.

## Checked and clean

- The PLAN's "Do not change" files (check.py, worktree.py, review_effect.py) are not in the diff.
- No gate lost in wrapup: `wrapup_land` runs `land_states`/`hold_lines` before staging and exits
  1 with `hold: SPEC <slug> is <state>; irreversible: <ids>`, the same rule the dropped
  `approval-status` call applied.
- `finalize` stamps only on `rc == 0`; `--exempt` with irreversible decisions is refused by
  `approve()` before any write; `_set_md_status` touches only the frontmatter `status:` line.

## Findings

| # | sev | finding | disposition | authority | outcome |
|---|---|---|---|---|---|
| 1 | major | `write_inline_rows` appended a missing block after the tests, so a `parametrize(AC_NNN_ROWS)` above it raised NameError at collection; execute did not say to export before writing tests. | accepted | - | fixed: new blocks go above the first top-level `def`/`class`/decorator; execute says "before its tests (then Edit, never Write over, the file)". Test `test_ac_001_write_puts_a_missing_block_above_the_tests`. |
| 2 | major | `mark-tested --slug` default refused the whole request when one AC had no test yet (e.g. a later phase), contrary to AC-002's wording. | accepted | - | fixed: the default leaves such ACs pending and names them on stderr; it still refuses when nothing binds, and explicit `--ac` never skips. Test `test_ac_002_default_leaves_an_ac_with_no_test_pending`. |
| 3 | minor | Several missing blocks in an empty file were joined with two blank lines, not `golden_inline_text`'s one. | accepted | - | fixed: missing blocks are written as one `golden_inline_text` call. Test `test_ac_001_write_creates_the_same_text_as_inline_for_several_acs`. |
| 4 | minor | A block ending at EOF without a newline was not matched, so a duplicate was appended. CRLF not handled. | accepted | - | fixed for EOF (`\](?:\n|\Z)`); CRLF left as is (the rows are generated LF). |
| 5 | minor | wrapup says "On `land: hold`" but the land prints a `hold:` line and exits 1. | accepted | - | fixed: "(the land exits 1)" added; the `On \`land: hold\`, show each \`irreversible\` decision` anchor is pinned by SPEC-choice-cards, so it stays. |
| 6 | minor | The edited validator-window test scoped to Step 5 only, so a verdict gate in Step 4.6 would pass. | accepted | - | fixed: verdict tokens are banned from Step 4.6 through the stamp; the validator's name only inside Step 5. |
| 7 | minor | Step 5 now sets `status: approved` only with a stamp; "Open Questions empty but DRI declined" stays `draft`. | rejected | agent (SPEC AC-004 / Step 5 rule) | intended (AC-004 ties status to the stamp; the old state "approved but unstamped" was the inconsistency). |
| 8 | minor | `finalize` stamped the yaml before setting status; a SPEC with no frontmatter `status:` ended half-finalized. | accepted | - | fixed: checked before the stamp. Test `test_ac_004_finalize_never_stamps_a_spec_whose_status_it_cannot_set`. |
| 9 | minor | Step 0 `--exempt` now runs `check --all` first, so a minimal SPEC that fails check cannot be stamped. | rejected | agent (SPEC AC-004 / Step 5 rule) | intended: an exempt stamp on a failing SPEC was a hole; Step 5's "on exit 1 nothing is stamped" covers it. |

## Found while dogfooding (pre-existing, follow-up)

- `mark-tested`'s discovery scope is the task's changed test files (SPEC-mark-tested-scope). A
  task that edits another SPEC's `test_ac_NNN_*` tests (this one edited six such files to new
  wording) binds those foreign tests to its own same-numbered ACs. Explicit `--ac` had the same
  behaviour; the new default makes it hit every AC at once. This task's yaml was re-bound with
  explicit `--test-id`. Follow-up: scope discovery to tests the task added, or to files that
  name the slug.

## Deviation from the SPEC text

- `docs/evals/RESULTS.md` is published from committed bench rows (a test re-renders it), so the
  AC-007 result is recorded in `docs/evals/cli-bookkeeping-2026-11-27.md` instead.
- The rebase onto main 593a6ac5 (#83, #84) moved the char baseline for AC-006 and the hm-main
  bench arm from 124c4c8c to 593a6ac5. The SPEC's hashed oracle text still names 124c4c8c; the
  fixture `tests/fixtures/cli_bookkeeping/main_chars.json` is the 593a6ac5 render.
