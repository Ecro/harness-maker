---
type: spec
task_slug: understanding-handoff
status: approved
created: 2026-09-26
tags: [harness-maker, spec, python, jinja2, wrapup, adr-provenance, intent-layer]
test_framework: pytest
tier: 2
interview_rounds: 3
intent: UNDERSTANDING-HANDOFF
summary: "wrapup commit carries a ≤5-line Understanding block; PLAN ADRs record Decided by user|agent"
---

# SPEC — understanding-handoff

## 🎯 Intent

The harness takes more of the *how* every release, so a finished task increasingly lands
without the user knowing how the system's assumptions, invariants or boundaries moved —
recovering that means reading the diff. PLAN ADRs also carry no decision owner, so a
trade-off the agent chose inside the agreed scope is indistinguishable from one the user
made. This SPEC implements intent `UNDERSTANDING-HANDOFF` (metric
`understanding_handoff_rate`), for a single senior developer.

## 🌅 Outcomes

- Every `/hm:wrapup` commit that reaches the user's branch carries an English
  `Understanding:` block of at most five bullets — assumption/invariant/boundary changes as
  before -> after, what is still unknown, and which ADRs the agent decided — or the single
  line `Understanding: none`. The same block is printed at the end of the wrapup.
- Under worktree ON the block survives `task-land`'s squash onto main; under worktree OFF
  the Step 6 commit is the final commit and carries it directly.
- `wrapup_land` reports (never blocks) a missing, empty or over-long block on stderr and in
  its JSON receipt, so a silently dropped block is visible at the moment it happens.
- Every ADR `/hm:execute` Step 0 writes carries `**Decided by:** user (source: …)` or
  `**Decided by:** agent`; ADRs without the field are counted as `unmarked`, never
  assumed to be agent decisions.

## 📋 In-Scope Scenarios

### S1: Assumption changed — block lands on main
**Given** a task under worktree ON whose PLAN has ADR-002 marked `**Decided by:** agent`
**When** `/hm:wrapup` writes the Step 6 message with `Understanding:` followed by 1–5 `- ` lines and `task-land` squashes the branch
**Then** the squash commit on the base branch contains the block verbatim
**And** `wrapup_land` prints no understanding warning and its receipt records `steps.understanding.status == "ok"`

### S2: Nothing changed
**Given** a task that moved no assumption, invariant or boundary and whose PLAN has no ADRs (neither agent-decided nor unmarked)
**When** the Step 6 message carries the single line `Understanding: none`
**Then** `wrapup_land` commits without an understanding warning and records `status == "none"`

### S3: Block missing — warn, never block
**Given** a Step 6 message with no line starting with `Understanding:` in its body
**When** `wrapup_land` runs
**Then** it prints one stderr line starting `[wrapup_land] understanding:` naming the problem
**And** the commit is still created, the exit code is unchanged, and the receipt records `status == "missing"`

### S4: Block over-long, empty or malformed
**Given** a Step 6 message whose `Understanding:` header is followed by six `- ` lines (or by zero bullets and no `none`, or whose block is malformed per the grammar)
**When** `wrapup_land` runs
**Then** it prints exactly one `[wrapup_land] understanding:` stderr line, records `status == "too_long"` (or `"empty"` / `"malformed"`) with the bullet count, and commits anyway
**And** the created commit's body equals the supplied message file — the block and the trailers are not rewritten

### S5: Rendered instructions — wrapup and execute
**Given** a harness rendered for Production or Side, with `worktree.enabled` true or false
**When** the wrapup and execute stage commands are rendered
**Then** wrapup's main-loop Step 6 instructs the Understanding block (format, 5-bullet cap including the agent-decided bullet, no file lists, English, placed before trailers) and the closing output repeats the same block
**And** execute Step 0's ADR section requires `**Decided by:** user (source: …)` only for decisions the user explicitly made, `agent` otherwise, and wrapup reports ADRs lacking the field as `unmarked`

## 🚫 Non-Goals

- Scoring the block's content quality automatically (LLM or regex), or asking the user to judge each wrapup — judgment happens in batches of ten, per the intent.
- Blocking a commit or failing `/hm:verify` on a missing block or a missing `Decided by` field.
- A new receipt field on the `stage-delegate` WrapupReceipt, a new file, or a new `harness.yaml` key.
- Parsing PLAN ADRs in Python or cross-checking the agent-decided line against the PLAN.
- A `joint` provenance value; learning/coaching modes; team or reviewer hand-off features.
- The README slogan (deferred until the intent closes `met`).

## ⚠️ Constraints

| Constraint | Value | Rationale |
|---|---|---|
| Test framework | `pytest` | repo standard; render tests use `render()`/`synthesize()` from `harness_maker` |
| Generation point | main-loop wrapup Step 6 only (inline and delegated paths converge there) | the delegate never runs git and its receipt has no message field; one point avoids a second procedure |
| Block language | English, identical text in commit body and closing output | commit messages are English by convention; the batch judgment reads git log, so the terminal copy must match it |
| Block grammar | A **header** is a body line (never the subject) whose right-stripped text is exactly `Understanding:` or `Understanding: none` (case-sensitive). No header → `missing`. Two or more lines whose text starts with `Understanding:` → `malformed`. A line starting `Understanding:` with any other suffix → `malformed`. After an `Understanding:` header, blank lines are skipped, then the **bullet run** is the consecutive lines starting `- `; it ends at the first line that does not (bullets after an interruption are ordinary body text). Bullets 1–5 → `ok`; 0 → `empty`; ≥6 → `too_long`. `Understanding: none` followed (after optional blank lines) by a `- ` line → `malformed`, otherwise → `none`. The cap counts **bullets**, not the header | a closed grammar is what makes the warning deterministic and keeps well-formed LLM layouts (blank line after the header) from warning |
| Provenance line | When the PLAN has any ADR, exactly one bullet `- agent-decided: <ADR ids or none> (unmarked: N)` — `(unmarked: N)` only when N > 0; it counts toward the 5. `Understanding: none` is valid only when there are no understanding changes **and** the PLAN has no ADRs | one place for `unmarked`, inside the budget, so legacy PLANs neither overflow the cap nor produce an undefined shape |
| Warning | stderr prefix `[wrapup_land] understanding:`; exactly one line for `missing|empty|too_long|malformed`, none for `ok|none`; exit code and commit unaffected; receipt key `steps.understanding = {status, bullets}` with status ∈ `ok|none|missing|empty|too_long|malformed` | warn-only per intent; a warning that fired on good blocks would train the user to ignore it |
| Message preservation | `wrapup_land` commits the supplied message unchanged; the classifier only reads it | under worktree OFF the Step 6 commit is final, and under ON `task-land` reuses it — any rewrite would reach the user's branch |
| Compatibility | PLANs written before this change have no `Decided by` field → reported as `unmarked: N`, never as agent | absent-case must be explicit, not a silent no-op |
| Render determinism | no shell-out at render; both presets and both worktree arms render the new prose | CLAUDE.md render rule |
| Surface budget | growth of `wrapup.md`/`execute.md` is attributed in `work-docs/BASELINE-DELTA-understanding-handoff.md` and every size site is re-frozen in the same change: `surface_baseline.json`, `_ATOMIC_RATCHET` in `tests/structural/test_command_size_budget.py`, the delegate-OFF line pin in `tests/unit/test_render_wrapup_delegation.py`, and the `autopilot_gate_golden.json` re-capture | four normative size sites (`[wiki:gotcha] one-rendered-command-size-has-four-normative-sites`); a `surface_allowance` expires at wrapup and would leave main red, so the PLAN re-freezes instead (PLAN ADR-005) |
| Performance | one string scan of the commit message | negligible |

## 🔒 Irreversible Decisions

none — the block is a commit-body text convention and the ADR field a PLAN text convention; both can change from the next commit on. The receipt key is additive JSON output.

## ✅ Verification Criteria

### AC-001: rendered wrapup Step 6 instructs the Understanding block
Main-loop `Steps 6 → 7.6` section (not the delegated span), all four arms (Production/Side × worktree on/off). The section must contain each literal anchor: `Understanding:`, `Understanding: none`, `at most 5 bullets`, `before -> after`, `unknown:`, `English`, `Do not list files`, `before the trailers`.

### AC-002: understanding block classifier matches the golden table
`check_understanding_block(message)` returns the status and bullet count per the grammar.

### AC-003: wrapup_land warns without blocking
For each of the six statuses: exactly one `[wrapup_land] understanding:` stderr line for missing/empty/too_long/malformed and none for ok/none; receipt `steps.understanding` equals the golden `{status, bullets}`; commit created; exit code equal to the with-valid-block run.

### AC-004: task-land squash preserves the block
A branch-tip message carrying the block yields a base-branch squash commit whose body contains it verbatim.

### AC-005: rendered wrapup closing output repeats the block
The rendered stage-end summary (the `✅ **Done:**` line) contains the anchor `Understanding:` block verbatim — tying the closing output to the committed block.

### AC-006: rendered execute ADR section requires Decided by
`**Decided by:** user (source: …)` for explicit user decisions, `agent` otherwise; anchors `**Decided by:**`, `user (source:`, `agent`.

### AC-007: rendered wrapup reports agent-decided and unmarked ADRs
Step 6 instructs the `agent-decided:` bullet from `**Decided by:** agent` ADRs and the `(unmarked: N)` suffix for ADRs lacking the field; anchors `- agent-decided:`, `**Decided by:** agent`, `(unmarked: N)`.

### AC-008: wrapup_land commits the supplied message unchanged
On a temp repo, the commit `wrapup_land` creates has `git log -1 --format=%B` equal to the message file (block and `Co-Authored-By` trailer intact), modulo git's trailing-whitespace cleanup.

| Scenario | Verification mode | Test name / manual step |
|---|---|---|
| S1 | integration + unit | AC-004 `test_task_land_squash_preserves_understanding_block`; AC-003 ok path |
| S2 | unit + integration | AC-002 golden rows `none`; AC-003 silence for `none` |
| S3 | integration | AC-003 `missing` case |
| S4 | unit + integration | AC-002 golden rows `too_long`/`empty`/`malformed`; AC-003; AC-008 |
| S5 | unit (render) | AC-001, AC-005, AC-006, AC-007 render tests |

## ❓ Open Questions

(none)

## 🔎 Spec Validation

spec-validator pass 1: `NEEDS_REVISION` (5 warnings, 0 critical; clean: irreversible-decisions, scope-boundary). Cross-model `codex`: invoked, 9 findings — 6 accepted, 3 rejected (delegate-boundary AC: strict `extra=forbid` receipt already refuses a field; irreversible inventory: text conventions + additive key, no parser; surface-budget AC: already gated by `test_surface_baseline.py`/`test_surface_allowance.py`). All 5 warnings were folded into this revision: closed grammar with `malformed` + golden rows, `unmarked` placed inside the agent-decided bullet with the cap counting bullets, AC-003 parametrized over all statuses, AC-008 for message preservation, literal anchors for AC-001/005/006/007.

## 🔍 Refinement Decisions

- Round 0 (intent interview, 2026-09-26): ≤5 lines, before→after + unknowns + agent ADRs, terminal + commit body, `decided_by` in PLAN ADRs, all presets, no new keys/files, batch judgment of 10 wrapups.
- Round 1: generation at main-loop Step 6 (not a receipt field); `wrapup_land` warn-only check; `user` only for explicitly user-made decisions with source, missing field = `unmarked`.
- Round 2: block grammar fixed (see Constraints); SPEC approved by the DRI.
- Round 3 (post-validation, DRI delegated remaining calls to the agent's recommendations): grammar closed as above; blank line after the header allowed; duplicates and odd suffixes → `malformed`.
- Execute (agent, PLAN ADR-005): the Surface-budget row switched from a declared `surface_allowance` to an attributed re-freeze, because an allowance expires at wrapup and lands main red; the row now names each size site.
- Worktree-OFF path resolved from source: Step 7.7 is not rendered, so the Step 6 commit is final; worktree-ON `task-land` reuses the branch-tip message (`worktree.py` `_branch_tip_message`).
