---
type: spec
task_slug: render-observability-audit
status: approved
created: 2026-08-26
tier: 2
tags: [harness-maker, spec, python, observability, telemetry, documentation, review-gates]
test_framework: pytest
research_doc: "[[RESEARCH-render-observability-audit]]"
summary: "Repair four measurement and documentation defects that mislead the reader of harness-maker's own telemetry"
---

# SPEC — render + observability audit remediation

## 🎯 Intent

The 0.54.1 render is a verified fixed point — re-rendering changes nothing, and structural
health is 82/100. The audit in `RESEARCH-render-observability-audit.md` therefore found no
render defect. What it found instead is that **harness-maker's own measurement layer misleads
the person reading it**, and that two review gates cost real time while producing no measured
discrimination.

The trigger is concrete and self-inflicted: following CLAUDE.md's literal instruction for the
second-opinion loss metric yields **codex 61.3%**, while the shipped reader
(`hm verifier_discrimination report`, which applies `.ledger-exclusions.json`) yields
**2.15%**. The audit itself reproduced that 30× error before finding the tool — the third
recorded instance of the same shape. A harness whose own docs route the reader away from its
own corrected tooling will keep producing decisions sized against wrong numbers.

This SPEC covers **four repairs**. The audit originally proposed two review-gate removals
alongside them; both were withdrawn at planning time on evidence, and the withdrawal is
recorded in Non-Goals rather than dropped silently — see `SPEC-workflow-loop-efficiency`,
which already owns that surface.

## 🌅 Outcomes

After this change:

1. A maintainer who follows CLAUDE.md to compute the second-opinion loss rate gets the **same
   number the shipped tool gets** — the hand-formula path no longer exists as the primary
   instruction.
2. CLAUDE.md sits **at or below the 500-line Production ceiling** with **no knowledge removed**
   — the long narrative blocks live in skills/docs, reachable by pointer, and
   `/hm:health` stops reporting `context_quality:claude_md_within_limit` as failing.
3. Any tool that reads `stage-spans.jsonl` can **join a span to its task and branch**, because
   the `end` row carries the same `task_slug`/`git_branch` its `start` carried. Today every
   `end` row nulls both, so a slug-keyed join silently returns zero spans.
4. The three **deterministic** wrapup-receipt mismatch kinds (`receipt-unparseable`,
   `document-escapes-root`, `promotion-arithmetic`) cannot be produced by a correct delegate
   run, and the three **claim** kinds (`wiki-missing`, `failure-missing`, `promotion-missing`)
   remain individually visible in the ledger rather than folded into one rate.

## 📋 In-Scope Scenarios

### S1: The documented metric agrees with the shipped tool

**Given** a `second-opinion.jsonl` containing rows excluded by `.claude/observability/.ledger-exclusions.json`
**When** a maintainer follows CLAUDE.md's instruction for computing per-model loss rate
**Then** the instruction names `hm verifier_discrimination report` and the exclusions file
**And** the number that instruction produces equals the number the tool produces
**And** no hand-computed `(skipped + failed) / total` formula is presented as the primary path

### S2: CLAUDE.md is within the ceiling without losing knowledge

**Given** CLAUDE.md at 624 lines against the Production limit of 500
**When** the long narrative blocks are relocated to `.claude/skills/` or `docs/`
**Then** `CLAUDE.md` is ≤ 500 lines
**And** `/hm:health` reports `context_quality:claude_md_within_limit` as passing
**And** every relocated block is reachable from CLAUDE.md by an explicit pointer
**And** no relocated block's text is deleted or summarised away

### S3: A closed span can be joined to its task

**Given** a span opened by `task-preflight` for slug `X` on branch `hm/X`
**When** the Stop/PreCompact hook closes it via `worktree span-end`
**Then** the emitted `end` row carries `task_slug: "X"` and `git_branch: "hm/X"`
**And** grouping the ledger by `task_slug` yields that span with both its endpoints

### S4: Deterministic receipt mismatches cannot occur

**Given** a wrapup delegate that ran correctly
**When** its receipt is validated by `wrapup_receipt`
**Then** no `receipt-unparseable`, `document-escapes-root`, or `promotion-arithmetic` mismatch is produced
**And** when the delegate claims a memory entry that does not exist, the mismatch is still
reported under its own distinct kind (`wiki-missing` / `failure-missing` / `promotion-missing`)

## 🚫 Non-Goals

- **Removing Pass 1.5 (`code-verifier` mode A).** **Already shipped.**
  `.claude/commands/hm/review.md` ADR-001 records the removal — "The Pass 1.5 `code-verifier`
  dispatch was removed. It dropped 5 of 261 findings (1.9%) across 41 reviews" — with the
  mode-B PIDA gate deliberately preserved, which is exactly the split this SPEC's interview
  arrived at independently. The audit's "401 findings → 5 drops" figure was computed over
  review-ledger rows written **before** that landing, so it measured a step that no longer runs.
- **Capping `plan-validator` / `test-reviewer` at one attempt.** Reserved, not rejected.
  `SPEC-workflow-loop-efficiency` (stage 1 of a 2-stage landing) names this in its own
  Non-Goals — "Deleting `test-reviewer` Phase A.5, the validator's second pass, or review
  Pass 2. All three are **stage-2 decisions gated on the telemetry this work adds**" — and
  that telemetry (`stage-agents.jsonl`, now 92 rows showing attempts 47/38/6/1) has since
  landed. The evidence to open stage 2 therefore exists; it belongs to that SPEC's stage 2,
  not to this one. Deciding it here would leave two SPECs governing the same surface.
- **The render pipeline.** Verified as a fixed point (`make --audit` → `git status` clean,
  99 files); this work does not change how rendering *works*. It does change **what** one
  template renders: AC-004's producer half edits `templates/agents/stage-delegate_body.md.j2`,
  which regenerates `.claude/agents/stage-delegate.md`, `.codex/agents/stage-delegate.toml`
  and `.agents/skills/` on the next `--update`. That blast radius is declared in the PLAN's
  Phase 2 `merge_hazards`; the earlier wording here ("nothing beyond the two template
  removals") described the withdrawn AC-005/006 and would have read as forbidding it.
- **P0's code half and P1.** Both were already remediated before this audit began — the ledger
  exclusion mechanism and the stdin-first `_span_end_session_id` fix. Not re-done here.
- **P6 (`auto-advance` attribution) and the `hm --help` module list.** Both were probe errors,
  retracted in RESEARCH. No change.
- **C1 — reducing the `/hm:review` 87KB command body.** Real (27.3% of all injected command
  text) but explicitly excluded from this scope by the interview.
- **C5 — `hm:verify` / `hm:wrapup` carry reduction** (0.89 / 0.75 at 486k / 302k ctx/turn).
  Deferred: sizing it requires P3's wall-clock contradiction resolved first.
- **P3 (span duration vs turn attribution contradiction) and P4 (orphan-log 53× duplication).**
  Both real, both out of the chosen six.
- **`antigravity`'s genuine 51.5% loss rate.** It is not in `second_opinion.models`, so it is
  experiment residue, not live cost.
- **Purging the 147 historical polluted ledger rows.** The exclusions file already neutralises
  them for every reader that consults it; AC-001 makes CLAUDE.md one of those readers.

## ⚠️ Constraints

| Constraint | Value | Rationale |
|---|---|---|
| Test framework | `pytest` | `harness.yaml.toolchains[python].commands.test = "uv run pytest -q {path}"`; the whole suite is already pytest. |
| Language | Python 3.12+, no Bash | CLAUDE.md "Runtime / Tooling" — hooks and CLIs are `python -m harness_maker.<module>`. |
| Atomic writes | `atomic_write` pattern | CLAUDE.md "구현 패턴"; any file this touches on the user side must survive interruption. |
| Knowledge preservation | Relocation only, no deletion | AC-002. CLAUDE.md's long narratives are the recorded *why* behind repeated failures; compressing them destroys the evidence that prevents recurrence. |
| Backward compat | Existing `stage-spans.jsonl` rows must still parse | AC-003 adds fields to `end` rows; `SpanEvent` already declares both as `str \| None = None`, so old null-bearing rows stay valid. |
| Determinism | No shell-out at render time | CLAUDE.md ADR-007. AC-004's producer half edits `templates/agents/stage-delegate_body.md.j2`; that edit is static text with no render-time evaluation. |
| Test isolation | No writes to the base repo's ledgers | `tests/unit/test_ledger_isolation.py` AC-001 — the defect this SPEC's AC-001 documents originated exactly there. |

## ✅ Verification Criteria

| Scenario | AC | Verification mode | Test name / manual step |
|---|---|---|---|
| S1 | AC-001 | unit | `test_claude_md_prescribes_shipped_second_opinion_reader` |
| S2 | AC-002 | unit | `test_claude_md_within_production_line_ceiling` |
| S3 | AC-003 | unit (property) | `test_span_end_preserves_start_task_and_branch` |
| S4 | AC-004 | unit (parametric) | `test_deterministic_receipt_mismatch_kinds_absent` |

Supplementary, non-gating: after landing, re-run
`uv run python -m harness_maker.economics composition --root .` and
`hm verifier_discrimination report` to confirm the reported figures move in the predicted
direction. These are observations, not acceptance criteria — the window is 30 days and the
July span population has not aged out.

### AC-001: CLAUDE.md prescribes the shipped second-opinion reader

CLAUDE.md's second-opinion section must name `hm verifier_discrimination report` and
`.claude/observability/.ledger-exclusions.json`, and must not present a bare
`(skipped + failed) / total` hand computation as the primary procedure.

### AC-002: CLAUDE.md is within the Production line ceiling

`CLAUDE.md` is ≤ 500 lines. Every block removed to reach that number is relocated intact and
referenced by an explicit pointer from CLAUDE.md.

### AC-003: A closed span's end row carries its start's task and branch

For any span opened with `task_slug=S` and `git_branch=B` and later closed by `span-end`, the
emitted `end` event carries the same `S` and `B`.

### AC-004: The delegate stops producing deterministically-invalid receipts

The subject is the **producer**, not the detector. `wrapup_receipt`'s validator already
detects all six mismatch kinds correctly — that is why they are visible in
`delegation.jsonl` at all, and `tests/unit/test_wrapup_receipt.py` already asserts detection
for each. What is unfixed is the `stage-delegate` side: it still emits receipts that trip
`promotion-arithmetic` (2026-08-19, 2026-08-23) and `document-escapes-root` (2026-08-17).

A receipt emitted by a correct delegate run produces none of `receipt-unparseable`,
`document-escapes-root`, `promotion-arithmetic`. The three claim-based kinds remain distinct
and reportable — the fix must not reduce the rate by weakening the detector.

## ❓ Open Questions

None. All six items were resolved across three interview rounds.

## 🔍 Refinement Decisions

- **Round 1** — Scope cut from 10 audited findings to the four clearest repairs
  (P0-docs, P7, P2, P5); gate policy answered as full removal rather than measurement-only.
- **Round 2** — The two answers were reconciled: the SPEC carries **six** items (4 repairs +
  2 removals) across two phases. CLAUDE.md reaches ≤ 500 lines by **relocating** long
  narrative blocks to skills/docs, not by compressing them — the narratives are the recorded
  rationale that prevents recurrence.
- **Round 4 (planning-time correction)** — `/hm:plan` Step 1.7's prefilter surfaced
  `SPEC-workflow-loop-efficiency` as overlapping. Verification against the **rendered**
  command surface (not the ledger) showed AC-005 was already shipped, and that AC-006 is
  explicitly reserved as that SPEC's stage-2 decision. Both were withdrawn and the SPEC cut
  from six items to four. The lesson is recorded because the original triage checked
  telemetry and prior source, but not the rendered artifact — the one place a shipped
  removal is actually visible.
- **Round 3** — "Remove Pass 1.5" scoped to **`code-verifier` mode A only**; mode B (the
  cross-model PIDA acceptance gate) is preserved because it is the sole route by which a
  second-opinion finding reaches Step 4's vote, and removing it would break CLAUDE.md's
  k-of-N consensus contract. P5's success bar set at **zero for the three deterministic
  mismatch kinds**, with the three claim-based kinds measured and kept distinguishable —
  promising zero for those would produce an AC no deterministic test could verify.
