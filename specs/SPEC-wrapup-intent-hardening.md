---
type: spec
task_slug: wrapup-intent-hardening
status: approved
created: 2026-10-04
tags: [harness-maker, spec, jinja2, intent-layer, wrapup, shell-safety]
test_framework: pytest
tier: 2
interview_rounds: 2
summary: "Wrapup 5.7: mark source rows in their own table; format-check every non-file shell argument"
---

# SPEC — wrapup-intent-hardening

## 🎯 Intent

The intent-surface-diet review left two follow-ups in wrapup Step 5.7. The first is that step 5's
"a row taken from a SPEC or RESEARCH table in that table too" can be read as "mark it in the
PLAN table". If it is read that way, the source row stays `pending` and the next wrapup offers it
again. The second is that 5.7 and the close block put repo-derived values on a shell line with no
format check: intent, question and metric ids, `--value` and `--locator`. Memory
`[fail:design] repeat-p1-same-shell-quoting-seam` asks that the whole seam be audited in one pass,
so this SPEC covers every non-file argument and not only the ids.

## 🌅 Outcomes

- A row taken from a SPEC or RESEARCH `## Feedback` table is marked in that same table, so no
  later wrapup offers it again.
- Every non-file argument that 5.7 or the close block puts on a shell line is checked against a
  stated format just before the write runs, after any edit made through Other. A value that fails
  runs nothing for its item and prints one line. The other items continue.
- Everything outside 5.7 in the wrapup render is unchanged.

## 📋 In-Scope Scenarios

### S1: Source rows are marked where they live
**Given** a 5.7 batch that includes a `pending` row from this task's SPEC or RESEARCH `## Feedback` table
**When** step 5 marks the outcome of that row
**Then** the marking sentence contains the phrase `in its own table as well as in the PLAN table`
**And** that same sentence names all three outcomes: `recorded`, `failed` and `declined` (so a shown-but-unselected source row is declined where it lives)
**And** the phrase "in that table too" no longer appears

### S2: A malformed argument skips its item, not the batch
**Given** a selected item whose argument fails its format, for example a question id `bad id;x` or a `--value` of `ten`
**When** step 5 reaches that item
**Then** the instruction says to run nothing for it, print `[intent] malformed <argument> — skipped <item>`, and continue with the remaining items
**And** `<argument>` is the argument's name (for example `question id`) and `<item>` is the item's kind, never a value. The line is agent output, not a shell command
**And** a first malformed failure marks the row `failed` with reason `malformed <argument>`. A re-offered row that is still malformed becomes `declined`, following the existing re-offer rule

### S3: Every non-file argument has a stated whole-value format
**Given** the 5.7 and close-block renders for Claude and Codex
**When** the format rules are read
**Then** they say the **whole value** must match, with these exact patterns:
- intent id `[A-Z0-9][A-Z0-9-]*` (a leading alphanumeric, so the id can never be read as an option)
- question id and metric id `[a-z0-9_]+`
- `--value` `-?[0-9]+(\.[0-9]+)?` (no exponent, no `nan`/`inf`)
- `--locator` `[A-Za-z0-9._/][A-Za-z0-9._/-]*:[0-9]+-[0-9]+`
- `--relation`, `--status` and `--observed` only the values listed on their command line

**And** an "argument" means every `<placeholder>` on an `hm intent` command line except `--*-file` values. The render-time `--with` install path is not a placeholder
**And** the check runs just before each write, after the selection and after any edit. On Claude the edit comes through Other. On Codex it comes in the numbered reply

### S4: Close refuses a malformed intent id
**Given** a PLAN whose `intent:` value fails `[A-Z0-9][A-Z0-9-]*` as a whole value
**When** the close block is reached
**Then** it prints `[intent] intent id malformed — skipping close` before the close question and asks no close question

## 🚫 Non-Goals

- No validation added to the `hm intent` CLI. The CLI already rejects bad ids. The gap is the shell line the agent composes before the CLI runs.
- Paths for `--*-file` arguments are not checked. They come from `mktemp` and are not authored values.
- No change to review 3.3. It already checks `[A-Z0-9-]+`.
- No change to the 5.7 structure: one record batch, the 16-item cap and the close question all stay.
- No `superseded` AC state. That is a separate follow-up task.

## ⚠️ Constraints

| Constraint | Value | Rationale |
|---|---|---|
| Test framework | `pytest` | The repo standard. The render tests live in `tests/unit/` |
| Render arms | Claude and Codex, both presets | The 5.7 text forks on `is_codex` |
| Golden discipline | Pre-change wrapup render captured from HEAD, install path normalized to `<SRC>` | `[wiki] render-golden-path-and-spec-hash`: renders embed the install path |
| Surface budget | Growth recorded per key in `BASELINE-DELTA-wrapup-intent-hardening.md` | The structural ratchet requires an attribution row |
| Security | No free text and no unchecked repo-derived value on a shell line | Closes the seam named in the Intent |
| Verification limit | Render tests prove the instruction text, not agent execution | Tier 2: the agent follows prose; no runtime harness executes 5.7 |
| Golden base | `f57cef3b5585ad07464bb687acfe507bd7bf461d` | The pre-change commit this task branches from |

## 🔒 Irreversible Decisions

none. This changes prompt text only. No CLI contract, file format or permission boundary moves.

## ✅ Verification Criteria

Tests live in `tests/unit/test_wrapup_intent_hardening.py`. Its goldens are in `tests/fixtures/wrapup_intent_hardening/goldens.json`.

| Scenario | Verification mode | Test name / manual step |
|---|---|---|
| S1 | unit | `test_ac001_source_rows_marked_in_own_table` |
| S2 | unit | `test_ac003_malformed_skips_item` |
| S3 | unit | `test_ac002_every_arg_has_a_format` |
| S4 | unit | `test_ac004_close_rejects_malformed_id` |
| all | unit | `test_ac005_render_outside_57_unchanged` |
| all | structural | the ratchet tests bound to AC-006 |

### AC-001: Source rows are marked in their own table
### AC-002: Every non-file shell argument has a stated format
### AC-003: A malformed argument skips only its item
### AC-004: Close refuses a malformed intent id
### AC-005: Wrapup text outside 5.7 is unchanged
### AC-006: Moved budgets carry attribution and the suite is green

## ❓ Open Questions

(none)

## 🔍 Refinement Decisions

- Round 1:
  - Intent link: none.
  - Malformed handling: skip the item and print one line, the same policy as review 3.3.
  - Scope: every non-file argument of 5.7 and the close block, following the seam lesson.
  - Autopilot is on.
- Round 1, after review (spec-validator NEEDS_REVISION plus codex): the following were pinned.
  - The source-row phrase, including declined.
  - The malformed re-offer rule: first failure → failed, re-offer → declined.
  - Whole-value patterns, including `--value`.
  - The argument boundary.
  - Per-arm edit-then-check order.
  - Logging the name, not the value.
  - The golden base sha.
- Trade-off recorded: the `--locator` path class is narrower than the CLI's (`.+`, `evidence_locator.py:16`). A citation of a path with spaces or non-ASCII characters is skipped as malformed. Shell safety wins over locator reach. A≤B stays the CLI's check (`evidence_locator.py:94-95`).
- /hm:review round 1 (grade A; user chose to fix the core P2s): the intent id and the locator path must start with an alphanumeric (or `.`/`/` for the path), so a value can never be read as an option. `<item>` is the item's kind. The malformed clause points at the existing re-offer rule instead of restating it.
