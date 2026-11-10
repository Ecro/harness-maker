---
type: spec
task_slug: wrapup-gate
status: approved
created: 2026-11-10
tags: [hm-check, review-gate, contract-boundaries, wrapup]
test_framework: pytest
interview_rounds: 0
summary: At wrapup, hm check fails a non-doc change with no REVIEW record (unless the SPEC is exempt), and every hm check compares the task diff with the PLAN's Do not change list itself.
---

# SPEC — wrapup-gate

## Intent

Two checks in the quality floor are judged by the model that does the work, and both can be
skipped silently (RESEARCH-hm-non-token-improvements F4, weekly proposal HR-020).

- **Review.** `hm check --slug demo` on a task with a code change and no REVIEW file returned
  `"review": {"ok": true, "gating": false, "reason": "no REVIEW record"}` and exit 0. Then
  `wrapup_land` (REVIEW is `--optional`) and `task-land` landed it (F4, reproduced). A typed
  `/hm:wrapup`, or a model that skips execute's Step 6, is not stopped. Eval 3 showed that
  models skip steps.
- **Contract boundaries.** execute Step 4 tells the model to compare `git diff --name-only HEAD`
  with the PLAN's `### Do not change` list. No Python reads that list. In a close analogue
  (arXiv 2611.05094), the orchestrator judging its own scope check stopped only 4 of 11
  recorded crossings.

Both become deterministic `hm check` results. This follows the DRI's decision of 2026-11-10
(card B: block, one SPEC with HR-020).

## Outcomes

- `hm check --slug <s> --require-review` (wrapup's call) exits 1 with
  `review.reason: "no REVIEW record for a non-doc change"` when all of these hold: the working
  tree changes a non-doc path, no `REVIEW-<s>-<date>.md` exists, and the SPEC is not `exempt`.
- Without `--require-review` (execute's pre-review gate), the review section is exactly as
  today.
- Every `hm check` (not `--red`) has a `contract` section. A changed path that matches a
  bare-path `### Do not change` entry of `PLAN-<s>.md` fails with exit 1 and names the path,
  unless a user-decided PLAN ADR `allows:` it. A changed path that matches a qualified entry
  (text after the path, such as "`check.py` full-mode semantics") is listed under
  `contract.advisory` for the reviewer and does not fail.
- execute Step 4 stops making the model compare paths. It reads the `contract` section instead,
  and the PLAN instruction names the `allows:` form.

## In-Scope Scenarios

- **S1 (normal):** a task edits `src/app.py` and execute wrote its REVIEW. Wrapup's
  `hm check --reuse --require-review` passes as before.
- **S2 (failure, skipped review):** the same task with no REVIEW file. Wrapup's gate exits 1 and
  names the reason, even when `--reuse` finds execute's identical exit-0 line.
- **S3 (edge):** an exempt SPEC, or a change that touches only `*.md` files and the task's own
  records. No REVIEW is required.
- **S4 (failure, crossing):** the PLAN lists `src/api/**` under `Do not change` and the diff
  touches `src/api/v1.py`. `hm check` exits 1 with `contract.crossed: ["src/api/v1.py"]`.
- **S5 (edge, authorised):** the PLAN has `ADR-002: … allows: src/api/v1.py. **Decided by:**
  user`. The crossing is listed under `contract.allowed` and passes. The same ADR decided by
  `agent` does not count.
- **S6 (edge, qualified):** the bullet is "`` `check.py` `` full-mode `ac_section` semantics" and
  the task edits `check.py`. The path is listed under `contract.advisory` and the check passes.

## Non-Goals

- Judging review quality or the content of the REVIEW. The existing disposition checks stay as
  they are.
- Requiring a review for an exempt SPEC. Exempt is the small-change path from spec Step 0.
- Checking committed history. execute never commits, so the task diff is the working tree
  against HEAD (`changed_paths`, the set the `security` section already uses).
- Judging a qualified bullet. Only a model can tell whether "full-mode semantics" changed, so
  such a bullet stays the reviewer's.
- Moving the requirement into `wrapup_land` or `task-land`.

## Constraints

| Constraint | Value | Why |
|---|---|---|
| test framework | pytest | project standard |
| non-doc path | a `changed_paths` entry outside `work_docs.dir`, `.claude/memory/`, `.claude/observability/` and `specs/SPEC-<slug>.*`, that either is a prompt (`CLAUDE.md`, `AGENTS.md`, `SKILL.md`, or any file under an `agents/`, `commands/` or `skills/` directory) or is not `*.md`/`*.rst`/`*.txt` | `is_code_or_test` misses templates, configs and locks, and Markdown that steers an agent is behaviour. Records and ledgers are not the change. With no HEAD, every file is changed: a first commit is all change |
| exempt | `approval.state == "exempt"` waives the requirement. `approved`, `legacy`, and `missing` at `auto_full` require it | an exempt SPEC is the "no interview" path; `legacy` is treated like `missing` everywhere in `hm check` |
| reuse | `require_review` is not part of the verdict key. On an identical reprint the review section is recomputed when the flag is set, and the exit code follows the usual precedence | otherwise execute's exit-0 line would carry wrapup past the check (S2), and keying on the flag would cost wrapup its gate reuse |
| Do not change entry | each `-`/`*` bullet under `### Do not change` up to the next heading. The path is the first backticked span (bold allowed around it), else the first word with `*` and trailing `.,;:` stripped. Text after it (other than punctuation) makes the bullet *qualified*, which is advisory. A bullet whose first word is `none` means no entries. A trailing `/` means `<dir>/**`; a name with no glob character matches itself and `<name>/**`, so `src/api` cannot fail open | real PLANs often protect a behaviour inside a file (`PLAN-hm-cost-p4`, `PLAN-retire-autopilot-remnants`), and a path match cannot judge that |
| glob dialect | `check_reuse.glob_match` (anchored, `*` within a segment, `**` any depth) | one dialect in `hm check` |
| allows | on an ADR line (`ADR-NNN` after optional `#`, `-`, `*`, `|`, `>` and spaces) that also says `Decided by:` `user` or `DRI`, each `allows: <path-or-glob>` (in backticks, or a bare token ending at whitespace, `,` or `;`, trailing `.` dropped); a crossed path is allowed when any allow pattern matches it | HR-020's minimal rule. An agent-decided allowance would let the model that crossed the boundary authorise itself |
| PLAN lookup | `<checked root>/<work_docs.dir>/PLAN-<slug>.md`, the checked root being the task worktree | the PLAN lives with the task |
| no PLAN / no list | `contract: {ok: true, reason: "no PLAN"}` or `"no Do not change list"`; non-gating | execute Step 0.3 already requires the list; the gate must not fail exempt tasks that have no PLAN |
| `--red` | `contract` is skipped like `review` | RED runs before any code |
| Python only, `mypy --strict`, ruff | — | CLAUDE.md |

## Irreversible Decisions

| id | decision | category | rationale |
|---|---|---|---|
| IRR-001 | `hm check` gains `--require-review` and a `contract` section (`{ok, crossed, allowed, advisory}` or `{ok, reason}`), and exits 1 on an unauthorised crossing or, with the flag, on an unreviewed non-doc change. A bare-path `Do not change` bullet changes meaning from model-judged to path-matched. A user-decided PLAN ADR gains the `allows: <path>` form that `hm check` parses | public API/CLI contract | rendered stage commands, users' scripts and existing PLANs depend on the exit contract and the PLAN format |

## Acceptance Criteria

### AC-001: --require-review fails an unreviewed non-doc change

Over the golden table, `review.ok`, the reason and the exit code match exactly (S1, S2, S3).
Each row also runs without the flag and behaves as today: ok, exit 0.

### AC-002: an identical reprint does not carry wrapup past the review requirement

Given a recorded exit-0 line from a run without the flag, and no REVIEW file, a
`--reuse --require-review` run on the identical tree exits 1 with the review reason. It runs no
gate command (S2).

### AC-003: the contract section follows the Do not change list and its ADR allowances

Over the golden table, `contract.ok`, `crossed`, `allowed` and `advisory` match exactly. Rows
cover a plain path, `**`, a trailing-slash directory, an untracked file, a qualified bullet, a
user-decided, a DRI-decided and an agent-decided `allows:` ADR, `###` and `- **ADR-**` ADR
prefixes, a bare directory name, trailing punctuation, a `none`-prefixed name that is not
`none`, the `none` bullet, no PLAN and a qualified bullet on another file (S4, S5, S6). A `--red` run reports `contract` as
skipped.

### AC-004: the stage text hands the comparison and the requirement to hm check

In both the Claude and the Codex render, wrapup's gate call is `hm check --slug <slug> --reuse
--require-review`. execute Step 4 no longer contains `Compare \`git diff --name-only HEAD\``,
and it names `contract.crossed` as the stop. execute Step 0's PLAN instruction names
`allows: <path>`.

## Verification

| scenario | mode | test |
|---|---|---|
| S1–S3 | unit | `tests/unit/test_wrapup_gate.py::test_ac_001_*`, `test_ac_002_*` |
| S4, S5 | unit | `tests/unit/test_wrapup_gate.py::test_ac_003_*` |
| templates | unit | `tests/unit/test_wrapup_gate.py::test_ac_004_*` |

## Open Questions

none

## Refinement Decisions

- No interview. The DRI chose the direction on card B (2026-11-10) and later said to proceed on
  the recommended option through merge without asking (2026-11-10 13:26Z). The HOW defaults
  above are the agent's. The one irreversible decision is recorded as IRR-001 and approved
  under that delegation.
- A flag, not a stage-sensing rule. execute's own gate runs before its review, so an
  always-on requirement would fail every execute.
- Wider than `is_code_or_test`. A template- or config-only change would otherwise land
  unreviewed, and hm's own product is mostly templates.
- spec-validator (one pass, 2 critical, 3 major, 4 minor), all taken:
  - qualified bullets are advisory;
  - only a user-decided `allows:` counts;
  - ADR lines may carry heading, bullet, bold or table prefixes;
  - prompt Markdown is non-doc;
  - `legacy` requires a review;
  - every AC-001 row also runs without the flag;
  - `.claude/observability/` is excluded, and the no-HEAD case is stated;
  - the PLAN lookup is named and a `--red` check is added;
  - AC-004 asserts `contract.crossed`.

  The meaning change of a bare-path bullet is recorded in IRR-001.
- code-reviewer round 1 (2 major, 4 minor, 1 nit), all taken: bare-name normalisation, `none`
  word boundary, `DRI` counts as the user (existing PLANs write it), the reprint also recomputes
  `contract`, a CLI test, and an existing section-set pin moves.
