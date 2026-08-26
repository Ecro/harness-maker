---
type: plan
task_slug: render-observability-audit
status: complete
created: 2026-08-26
tags: [harness-maker, plan, python, observability, telemetry, documentation]
spec: "[[SPEC-render-observability-audit]]"
research_doc: "[[RESEARCH-render-observability-audit]]"
interview_rounds: 9
adrs: 5
validator_outcome: MAJOR_REVISION_RESOLVED
summary: "Repair four measurement and documentation defects; withdraw two items found already-shipped or reserved"
spec_need_verdict: change
spec_need_target: render-observability-audit
---

# PLAN — render + observability audit remediation

## 🎯 Executive Summary

**TL;DR** — Four repairs to harness-maker's own measurement and documentation layer, in three
phases. Two items the audit originally proposed were withdrawn at planning time on evidence.

**What.** (1) CLAUDE.md's second-opinion loss-rate instruction routes the reader to the shipped
reader instead of a hand formula. (2) CLAUDE.md drops below the 500-line Production ceiling by
relocating two procedural blocks to `docs/`, losing nothing. (3) `worktree span-end` emits the
`task_slug` / `git_branch` its `start` carried. (4) The wrapup delegate stops producing receipts
that trip the three deterministic mismatch kinds, fixed on both the consumer and producer side.

**Why.** The 0.54.1 render is a verified fixed point — there is no render defect. What the audit
found is that harness-maker's own telemetry misleads its reader: following CLAUDE.md literally
reports codex at **61.3% loss** where the shipped tool reports **2.15%**, and the audit itself
reproduced that 30× error. Separately, every `end` row in `stage-spans.jsonl` nulls the two
fields a task-level join needs, and `delegation.jsonl` still records deterministic receipt
failures as recently as 2026-08-23.

**Key decisions.**
- [ADR-001](#adr-001) — the two review-gate items are withdrawn; verification of "is this already
  done?" belongs against the **rendered artifact**, not the ledger.
- [ADR-002](#adr-002) — the receipt defects are fixed on **both** sides.
- [ADR-003](#adr-003) — `_confined` asks whether a path escapes the root, not whether it is
  absolute; the F-04 security property is preserved by construction, not by the absoluteness test.
- [ADR-004](#adr-004) — CLAUDE.md's oversize blocks are **relocated to `docs/`**, never compressed.

**Estimated impact.** Two Python modules, one Jinja template, one hand-authored Markdown file,
two new `docs/` files. No user-facing behaviour changes; no rendered-command semantics change
except the wrapup delegate brief.

## 📚 Prior Work

- `RESEARCH-render-observability-audit.md` — the measurement this PLAN acts on. Its triage table
  records 2 retracted findings and 2 already-remediated ones; this PLAN retracts 2 more.
- `SPEC-workflow-loop-efficiency` (draft, stage 1 of 2) + `PLAN-workflow-loop-efficiency`
  (complete) — **owns the review-gate surface.** Its shipped ADR-001 removed Pass 1.5, and its
  Non-Goals reserve the validator/A.5 caps for its own stage 2. See ADR-001.
- `tests/unit/test_ledger_isolation.py` — the 2026-08-17 gate that stopped the ledger leak.
  Its docstring records the same 30× misread this PLAN's AC-001 exists to prevent recurring.
- `[[wiki:architecture ledger-exclusions-and-test-isolation]]` (2026-08-17) — the exclusion
  mechanism AC-001 documents.
- `[[fail:design observability-field-with-no-consumer]]` (count:2) — the class AC-003 belongs to:
  a field that is emitted but structurally unjoinable is a field with no consumer.
- `[[fail:design]] subagent-frontmatter-permissions-not-enforced` — the precedent behind ADR-002's
  refusal to fix an LLM-output defect with prompt text alone.

## 🎙️ Interview Transcript

| # | Topic | Category | Question | Options | Choice | Note | → ADR |
|---|---|---|---|---|---|---|---|
| 1 | Scope cut | Scope boundaries | Which of the 10 audited findings enter this work? | all 10 / top 4 / measurement-only / 8 fixes | **top 4** (P0-docs, P7, P2, P5) | Optimisation deferred until the measurement is trustworthy | — |
| 2 | Gate policy | Risk tolerance | If C3/C4 are addressed, in what form? | measure-only / conditional skip / full removal / out of scope | **full removal** | Later withdrawn — see #4 | ADR-001 |
| 3 | Scope reconciliation | Scope boundaries | 4 items or 6? | 6 / 4 / 2 / 7 | **6** (4 repairs + 2 removals) | Superseded by #4 | ADR-001 |
| 4 | CLAUDE.md method | Architecture | How does CLAUDE.md reach ≤500 lines? | relocate to skill/docs / compress / @import split / defer | **relocate** | Narratives are the recorded *why*; compressing destroys the evidence | ADR-004 |
| 5 | Removal blast radius | Contract shape | Does "remove Pass 1.5" include `code-verifier` mode B? | mode A only / whole agent / conditional | **mode A only** | mode B is the sole route a cross-model finding reaches Step 4's vote | ADR-001 |
| 6 | P5 success bar | Testing depth | Zero for all six mismatch kinds, or only the deterministic three? | deterministic-only / all six / ratio threshold | **deterministic three → 0** | The claim kinds cannot be proven zero by a deterministic test | — |
| 7 | Scope correction | Scope boundaries | AC-005 is already shipped and AC-006 is reserved by another SPEC — now what? | cut to 4 / 4 + open stage 2 / override the Non-Goal / re-triage | **cut to 4** | Discovered by `/hm:plan` Step 1.7 prefilter | ADR-001 |
| 8 | Receipt fix site | Architecture | Where do the three deterministic receipt defects get fixed? | both sides / producer only / consumer only / self-validating delegate | **both sides** | Prompt alone is "instruction, not enforcement" | ADR-002, ADR-003 |
| 9 | Narrowing #8 | Risk tolerance | Plan validation showed the consumer half of `promotion-arithmetic` would delete the anti-fabrication control. Accept narrowing #8 to per-defect, or keep "both sides" and amend the SPEC? | accept narrowing / keep both-sides + amend SPEC | **accept narrowing** | Accepted the recorded cost: that defect's producer half is unprovable, covered by ADR-002's 14-day observation window and rollback trigger | ADR-002 |

## 📐 Architecture Decision Records

### ADR-001: Withdraw the two review-gate items; verify "already done" against the rendered artifact
**Status:** Accepted (2026-08-26, via /hm:plan interview)

**Context:** The audit proposed removing Pass 1.5 (`code-verifier` mode A) and capping the
`plan-validator` / `test-reviewer` retry at one attempt, and the user chose full removal for
both. `/hm:plan` Step 1.7's SPEC-need prefilter then surfaced `SPEC-workflow-loop-efficiency`
as overlapping, and verification against the **rendered** command surface showed both were
already settled elsewhere.

**Decision:** Both items are withdrawn from this PLAN and recorded in the SPEC's Non-Goals with
their evidence. This PLAN carries four ACs.

**Evidence:**
- `.claude/commands/hm/review.md:385` — "**No verifier step runs between the passes
  (ADR-001).** The Pass 1.5 `code-verifier` dispatch was removed. It dropped 5 of 261 findings
  (1.9%) across 41 reviews … The `code-verifier` agent itself is unchanged and still live for
  cross-model PIDA **mode B** at Step 3.6; do not re-add a mode A dispatch here." That is the
  exact mode-A/mode-B split interview round 5 arrived at independently.
- `SPEC-workflow-loop-efficiency` Non-Goals — "Deleting `test-reviewer` Phase A.5, the
  validator's second pass, or review Pass 2. All three are **stage-2 decisions gated on the
  telemetry this work adds**" and "Reducing `max_review_rounds` or the validator's 2-pass cap.
  The research specifically recommends against it."

**Consequences:**
- ✅ No phase of this work lands as a no-op, and no AC contradicts a recorded decision.
- ✅ The telemetry that reservation was waiting on now exists (`stage-agents.jsonl`, 92 rows,
  attempts 47/38/6/1), so its stage 2 has the evidence to open — as that SPEC's work, not this one.
- ⚠️ The largest measured saving the audit identified (reviewer re-runs) is not captured here.
- ⚠️ **The generalisable lesson**: the original triage checked the ledger and the module source
  and concluded "not fixed". Both were true and both were misleading — a *shipped removal* is
  visible only in the rendered artifact, and historical ledger rows outlive the step they
  measured. Any future "is this already done?" check must read the rendered surface.

**Rejected alternatives:**
- *Keep AC-006 and override the other SPEC's Non-Goal* — rejected: two draft SPECs would then
  govern the same surface with different rules, and the reservation's stated gate (telemetry)
  is satisfied by opening that SPEC's stage 2, not by bypassing it.
- *Halt and re-triage everything* — rejected: the remaining four were each re-verified against
  current source during this step.

**Source:** Interview #2, #3, #5, #7

### ADR-002: Fix each receipt defect on the side that owns it — not uniformly on both
**Status:** Accepted (2026-08-26, via /hm:plan interview; **narrowed** by plan validation)

**Context:** All three deterministic mismatch kinds originate in a receipt authored by the
`stage-delegate` LLM. Interview #8 chose "both sides". Plan validation then established that
applying that uniformly destroys a control: deriving `promotion_candidates` from
`len(promoted_slugs) + len(promotion_skips)` makes the two sides equal by construction, so
`promotion-arithmetic` becomes structurally unraisable — `wrapup_receipt.py:351-353` names it
"the anti-fabrication check: a summarising main loop inventing a plausible 'N candidates,
M promoted' line produces counts that do not add up". The machine SPEC's golden row for that
kind (`candidates equal promoted + skipped` → `[]`) already passes against unmodified code.

**Decision:** Per-defect, not per-side:

| Defect | Consumer | Producer |
|---|---|---|
| `document-escapes-root` | **change** — accept base-contained absolute paths (ADR-003) | **change** — state repo-relative explicitly |
| `receipt-unparseable` | **change** — widen `WrapupReceipt` to the shapes observed in `delegation.jsonl`, `strict=True` retained, never `extra="allow"` | **change** — state that no field outside the schema may be emitted |
| `promotion-arithmetic` | **UNCHANGED — the check stays exactly as it is** | **change** — the only side that may move |

**Consequences:**
- ✅ The anti-fabrication control survives; the PLAN's own boundary ("reducing the mismatch
  rate by weakening detection fails AC-004") is not violated by its own implementation.
- ✅ Two of three defects still gain enforcement, so a future model ignoring the brief cannot
  reintroduce them.
- ⚠️ **The `promotion-arithmetic` half is producer-only and therefore unprovable by
  deterministic test — recorded, not hidden.** `stage-delegate_body.md.j2:83` already states
  the rule verbatim, and `delegation.jsonl` records violations on 2026-08-19 and 2026-08-23
  *after* that text shipped. A rendered-prompt grep would assert text already on disk and pass
  on day one while proving nothing, so no such test is planned. Instead: **observation window
  of 14 days after Phase 2 lands; rollback trigger = any new `promotion-arithmetic` row in
  `delegation.jsonl` within it**, at which point the consumer-gated reject-and-retry that
  interview #8 declined on cost grounds is re-opened as its own task.
- ⚠️ Two edit sites for one defect class; a future change must keep them consistent.

**Rejected alternatives:**
- *Uniform both-sides (the interview's literal answer)* — rejected on plan validation: it
  deletes the anti-fabrication check for no AC that requires it.
- *Producer only, for all three* — rejected: zero enforcement where enforcement is available.
- *Consumer only* — rejected: the delegate would keep reporting wrong arithmetic and the
  harness would hide it.
- *Delegate self-validates and retries once* — rejected at interview #8 on cost (a serialized
  subagent round-trip on the critical path). Re-opened only by the rollback trigger above.
- *A render-grep asserting the producer text* — rejected: the text it would assert is already
  present and already ignored.

**Source:** Interview #8; narrowed by plan-validator critique 1 and codex finding `cb1bf495`;
narrowing accepted by the user at interview #9 (2026-08-26), which resolves the plan stage's
judgment gate — the acceptance is recorded here rather than only in the autopilot ledger.

### ADR-003: `_confined` asks whether a path escapes the root, not whether it is absolute
**Status:** Accepted (2026-08-26, via /hm:plan interview)

**Context:** `wrapup_receipt._confined` rejects any absolute path because
`Path("/base") / "/etc/hostname"` is `/etc/hostname`, which would let a delegate satisfy
reconciliation with any file on the machine (review F-04). The delegate legitimately reports
paths inside its own worktree in absolute form, so the control fires on truthful receipts.

**Decision:** Accept an absolute path **iff** its `resolve()` is inside the base root, and
relativize it; continue rejecting `..`, symlink escapes, and anything resolving outside. The
predicate becomes the one the mismatch kind is named for.

**Consequences:**
- ✅ The F-04 property is preserved by the containment test, which was always the load-bearing
  half — `resolve()` before `is_relative_to` is what catches a symlink escape, and absoluteness
  never was.
- ✅ A truthful receipt stops producing a structural false positive, the failure mode the
  surrounding comment already names for `document-missing`.
- ⚠️ A security-relevant predicate changes; the regression test must assert the *negative* case
  (`/etc/hostname` still rejected) as loudly as the positive one.

**SPEC authorisation:** this is not a SPEC contradiction. `SPEC-…machine.yaml`'s
`document-escapes-root` golden row is "a receipt listing documents the delegate wrote from
inside `.worktrees/<slug>/`" → `expected: []`, i.e. the SPEC already requires that a contained
worktree path stop raising. The prose SPEC's "the validator already detects all six correctly"
describes the six *kinds*, not this predicate's boundary.

**Second consumer:** `_confined`'s docstring names **two** callers — `documents_updated` and
the verify stage's `record_path`. Widening the predicate changes what verify accepts, so
`record_path` is named in Phase 2's scope and carries its own positive and negative test.

**Rejected alternatives:**
- *Leave `_confined` and relativize upstream only* — rejected: the same absolute path can reach
  the validator from any producer, and the check would still misname what it tests.

**Source:** Interview #8

### ADR-004: Relocate CLAUDE.md's oversize blocks to `docs/`; never compress them
**Status:** Accepted (2026-08-26, via /hm:plan interview)

**Context:** CLAUDE.md is 624 lines against a 500-line Production ceiling and sits in the prefix
of every turn of every session. Its two largest blocks are procedural: the pre-change checklist
(148 lines) and the implementation-pattern conventions (108 lines) — 256 lines, more than the
124 needed.

**Decision:** Relocate both blocks verbatim into `docs/`, leaving an explicit pointer in
CLAUDE.md. Do not compress, summarise, or delete any of the narrative.

**Consequences:**
- ✅ Knowledge loss is zero, and the every-turn cost is separated from the read-when-needed cost.
- ✅ `docs/` avoids the orphan sweep: a new file under `.claude/skills/` that is absent from
  `harness.yaml skills.installed` is classified an orphan (the audit logged 265 such), whereas
  `docs/` is outside the reconciled tree entirely.
- ✅ Editing CLAUDE.md directly is safe here: it carries no provenance frontmatter and no
  `@hm:user:*` markers, so reconcile takes the KEEP path (audit: "KEEP: 3 file(s) preserved
  as-is"). Verified — `make . --audit` left it byte-identical.
- ⚠️ A relocated rule is one indirection further from the agent reading CLAUDE.md; the pointer
  must state what the target contains, not merely that it exists.

**Rejected alternatives:**
- *Compress in place* — rejected: the long narratives are the recorded *why* behind repeated
  failures, and that rationale is the mechanism preventing recurrence.
- *`@import` split* — rejected: an import loads into the same context, so the line-count signal
  would pass while the token cost stayed. `SPEC-workflow-loop-efficiency` independently measured
  the CLAUDE.md ceiling at ~4% of total spend, which is the honest size of this win.
- *Relocate to `.claude/skills/`* — rejected for the orphan-sweep reason above; both target
  blocks are procedural, so the judgment/procedure split lands them in `docs/` anyway.

**Source:** Interview #4

### ADR-005: The withdrawal in ADR-001 must be applied to the SPEC by an owning phase
**Status:** Accepted (2026-08-26, via plan validation)

**Context:** The PLAN frontmatter declares `spec_need_verdict: change`, but the first draft gave
no phase scope over `specs/SPEC-render-observability-audit.md`. A declared SPEC change with no
owning phase does not happen, and the SPEC still carried clauses invalidated by ADR-001 — its
Determinism constraint reasons about "the template changes in AC-005/006", and its Non-Goals
claim "Nothing here changes rendering behaviour beyond the two template removals" while Phase 2
does edit templates.

**Decision:** A dedicated **Phase 0** owns the SPEC and `.machine.yaml` corrections and runs
first, so no later phase reads a stale constraint.

**Consequences:**
- ✅ `/hm:execute` and `/hm:review` read a SPEC consistent with the PLAN they are executing.
- ✅ `paths_to_mutate` gains the surfaces Phase 2 actually touches.
- ⚠️ A fourth phase for a documentation edit; justified because the stale clause directly
  contradicts Phase 2's declared merge hazard and would be read as binding.

**Rejected alternatives:**
- *Fold into Phase 2* (the validator's suggestion) — rejected: Phase 2 is the `medium`-risk
  security-adjacent phase, and blocking a one-file SPEC correction behind it is the same
  serialisation error critique 7 raised about Phase 3.

**Source:** plan-validator critique 8

## 🏗️ Technical Design

### Current state

| Surface | State |
|---|---|
| `CLAUDE.md` | 624 lines, hand-authored, KEEP-preserved by reconcile. Its second-opinion section prescribes a hand formula and names neither the exclusions file nor the shipped reader. |
| `worktree._cli_span_end` (`:5783`) | `emit_event("end", stage=…, cwd=base, session_id=mine)` — omits `task_slug` and `git_branch`, which `_emit_stage_span` supplies on `start`. |
| `wrapup_receipt._confined` (`:223`) | Rejects every absolute path. |
| `wrapup_receipt` promotion check (`:351-353`, `:370`) | The **anti-fabrication check** — correct, and staying (ADR-002). |
| `WrapupReceipt` (`:59`) | `strict=True, extra="forbid"`; the delegate has emitted `steps_skipped` and `drift_verdict` in forbidden shapes. |

### Affected components

- `src/harness_maker/worktree.py` — emitter only (AC-003).
- `src/harness_maker/wrapup_receipt.py` — `_confined`, promotion arithmetic, schema (AC-004).
- `src/harness_maker/templates/agents/stage-delegate_body.md.j2` — **the receipt contract**
  (lines 68-94: the JSON schema and the arithmetic rule). This is the producer surface;
  `wrapup_brief.py` defines the delegate's *input* (`WrapupBrief`: slug, task_branch, base_root,
  worktree_root, locale, changed_files) and carries no receipt field, so it is **out** of scope.
- `CLAUDE.md` + two new `docs/` files (AC-001, AC-002).

### Dependencies

None added. `stage_spans.SpanEvent` already declares `task_slug` and `git_branch` as
`str | None = None`, so AC-003 is additive and every existing null-bearing row still parses.

### Data flow (AC-003)

```
task-preflight ──> _emit_stage_span(stage, git_branch=B, task_slug=S) ──> start row {S, B}
                                                                              │
Stop / PreCompact hook ──> _cli_span_end ──> reads own session's last event ──┘
                                     └────> emit_event("end", …)   ← today: {null, null}
                                                                     after:  {S, B}
```

`_cli_span_end` already locates the open span (`ours[-1]`) to read its `stage`; the same record
carries `task_slug` and `git_branch`. No new lookup is required.

### Design decisions

- AC-003 reads the two fields from the same `ours[-1]` event it already reads `stage` from
  (no new state, no new failure mode) — see ADR-001's lesson on unjoinable fields.
- AC-004's consumer half changes **one predicate** (`_confined`, ADR-003) and **widens one
  schema** to observed shapes. It derives nothing: `promotion_candidates` stays as-is (ADR-002).
- `_confined` has two callers — `documents_updated` and verify's `record_path`. Both change.
- AC-001/AC-002 are text moves, gated by `/hm:health` (ADR-004).

### API changes

None public. `_confined`'s accepted input widens (absolute-but-contained now returns a path
instead of `None`); it is module-private, with two callers, both covered by Phase 2's tests.

## 📝 Implementation Plan

### Phase 0 — apply ADR-001's withdrawal to the SPEC (no AC; enables the rest)

**Status:** DONE

- **depends_on:** `[]`
- **parallel_group:** `parallel-docs`
- **merge_hazards:** `none`
- **Scope — in:** `specs/SPEC-render-observability-audit.md`,
  `specs/SPEC-render-observability-audit.machine.yaml`
- **Scope — out:** every AC's substance; this phase corrects clauses invalidated by ADR-001 only
- **Clauses to correct (enumerated, not open-ended):**
  1. Constraints → Determinism row still reads "the template changes in AC-005/006 are static";
     AC-005/006 no longer exist.
  2. Non-Goals → "Nothing here changes rendering behaviour beyond the two template removals";
     the removals were withdrawn and Phase 2 *does* edit a template.
  3. `.machine.yaml` `mutation_threshold_rationale` still reasons about AC-005/006.
  4. `.machine.yaml` `paths_to_mutate` names `wrapup_brief.py`, which Phase 2 no longer touches;
     drop it. **The stage-delegate template is deliberately NOT added** — `mutmut` mutates Python
     only, so a Jinja path in that list would be a promise the runner cannot keep. Re-justify the
     70 threshold to say so. (Corrected in review round 2: the first draft of this clause said
     "add it", which contradicted the rationale that shipped beside it.)
- **Exit criterion:** `uv run --with $HOME/harness-maker hm spec_machine check --all
  --yaml specs/SPEC-render-observability-audit.machine.yaml
  --md specs/SPEC-render-observability-audit.md --dev-mode spec-driven` exits 0 with
  `quality.blocked: false`, and `rg -n "AC-005|AC-006" specs/SPEC-render-observability-audit*`
  returns only the Non-Goals entries that deliberately record the withdrawal
- **Risk:** `low`
- **Rollback point:** pre-phase HEAD

### Phase 1 — span `end` carries its task and branch (AC-003)

**Status:** DONE

- **depends_on:** `[]`
- **parallel_group:** `parallel-code`
- **merge_hazards:** `none`
- **Scope — in:** `src/harness_maker/worktree.py` (`_cli_span_end`),
  `tests/unit/test_stage_span_end_fields.py` (new)
- **Scope — out:** `src/harness_maker/stage_spans.py` (schema and pairing unchanged),
  `_emit_stage_span`, the settings hook wiring
- **Exit criterion:** `uv run pytest -q tests/unit/test_stage_span_end_fields.py` passes, and
  `uv run pytest -q tests/unit/test_worktree_reader_singleton.py tests/structural/` is green
- **Risk:** `low`
- **Rollback point:** the phase's own commit; nothing depends on it

### Phase 2 — the delegate stops producing invalid receipts (AC-004)

**Status:** DONE

- **depends_on:** `[0]` — Phase 0 removes the SPEC clause that says this phase changes no
  rendering behaviour
- **parallel_group:** `serial-render`
- **merge_hazards:** **larger than the first draft declared.** Editing
  `templates/agents/stage-delegate_body.md.j2` regenerates three trees —
  `.claude/agents/stage-delegate.md`, `.codex/agents/stage-delegate.toml` and
  `.agents/skills/` — in one `/harness-maker:make --update`. Hazard is against **concurrent
  sessions**, not against Phase 0/1/3. (Corrected in the confirmation pass: an earlier draft
  also named `templates/stages/wrapup.md.j2` here, from when the receipt contract was thought
  to live in the dispatching command rather than in the sub-agent's own prompt. This phase
  never edits that file, and it is absent from Scope-in for that reason.)
- **Scope — in:**
  - `src/harness_maker/templates/agents/stage-delegate_body.md.j2` — the receipt contract
    (lines 68-94): state `documents_updated` and `record_path` must be **repo-relative**, and
    that **no field outside the schema** may be emitted
  - `src/harness_maker/wrapup_receipt.py` — `_confined` only (ADR-003) and `WrapupReceipt`
    field shapes, widened to shapes observed in `delegation.jsonl`
  - `tests/unit/test_wrapup_receipt_deterministic_kinds.py` (new)
- **Scope — out (explicit):**
  - **the promotion-arithmetic check** — unchanged, producer-only (ADR-002)
  - `src/harness_maker/wrapup_brief.py` — input contract, carries no receipt field
  - the three claim-based mismatch kinds and their existing detection tests
  - `wrapup_land.py`; the Second Brain promotion path
- **Exit criterion:** `uv run pytest -q tests/unit/test_wrapup_receipt.py
  tests/unit/test_wrapup_receipt_deterministic_kinds.py tests/unit/test_delegation_reason_capture.py`
  passes, **including all four** of: `/etc/hostname` still rejected for `documents_updated`;
  `/etc/hostname` still rejected for `record_path`; a base-contained absolute `record_path`
  accepted; and the unmodified `promotion-arithmetic` golden row still yielding `[]`
- **Risk:** `medium` — changes a predicate a prior security review hardened (ADR-003), and
  takes a render blast radius across three target trees
- **Rollback point:** Phase 0's commit
- **Not gated here (recorded, per ADR-002):** the producer half of `promotion-arithmetic` has
  no deterministic test. Its verification is the 14-day observation window and rollback trigger
  in ADR-002, not a render-grep.

### Phase 3 — CLAUDE.md: correct the metric instruction and reach the ceiling (AC-001, AC-002)

**Status:** DONE

- **depends_on:** `[]` — corrected from the draft's `[1, 2]`. Neither Phase 1 nor Phase 2 touches
  `verifier_discrimination.py` or anything AC-001's text describes; the draft's "code first"
  rationale was misattributed to Interview #8, which was about the receipt fix site and recorded
  no ordering decision.
- **parallel_group:** `parallel-docs`
- **merge_hazards:** `none` — CLAUDE.md is KEEP-preserved (no provenance frontmatter, no
  `@hm:user:*` markers) and the new `docs/` files are outside the reconciled tree
- **Scope — in:** `CLAUDE.md`, two new files under `docs/`,
  `tests/unit/test_claude_md_second_opinion_guidance.py` (new),
  `tests/fixtures/second_opinion_excluded.jsonl` + `tests/fixtures/ledger_exclusions.json` (new)
- **Scope — out:** `templates/claude-md/*.j2` (those render *consuming* projects' CLAUDE.md),
  `.claude/observability/.ledger-exclusions.json`, `verifier_discrimination.py`
- **Exit criterion:** `uv run pytest -q tests/unit/test_claude_md_second_opinion_guidance.py`
  passes — including the **fixture-ledger differential** (below) and the **relocation-integrity**
  assertions — and `uv run python -m harness_maker.cli health . --session-id "$HM_SESSION_ID"`
  no longer lists `context_quality:claude_md_within_limit` in `signals_failed`
- **Risk:** `low`
- **Rollback point:** the phase's own commit

## 🚧 Contract Boundaries

### Do not change

- `src/harness_maker/wrapup_receipt.py` promotion-arithmetic check (`:351-353`, `:370-382`) — the anti-fabrication control; ADR-002 makes this defect producer-only precisely so it survives
- `src/harness_maker/wrapup_brief.py` — the delegate's input contract; it carries no receipt field
- `src/harness_maker/stage_spans.py` — `SpanEvent`'s schema and `_build_spans`' per-session pairing; AC-003 changes the emitter only
- `src/harness_maker/templates/stages/review.md.j2` — Pass 1.5 was already removed here by another PLAN's ADR-001 (see ADR-001)
- `src/harness_maker/templates/stages/execute.md.j2` — the `test-reviewer` A.5 retry path is reserved to `SPEC-workflow-loop-efficiency` stage 2
- `src/harness_maker/second_opinion_invoke.py` — sole owner of second-opinion CLI invocation
- `src/harness_maker/verifier_discrimination.py` and `src/harness_maker/ledger_exclusions.py` — AC-001 documents these; it must not alter their behaviour
- `.claude/observability/.ledger-exclusions.json` — AC-001 documents this file; its contents must not change
- `.claude/agents/code-verifier.md` and `src/harness_maker/templates/agents/code-verifier*` — mode B still dispatches to this agent
- `src/harness_maker/templates/claude-md/` — renders consuming projects' CLAUDE.md, not this repo's
- Advisory: `_confined` must still reject any path whose `resolve()` lands outside the base root, symlink escapes included — for **both** callers. The F-04 property is the point of ADR-003, not a casualty of it
- Advisory: the three claim-based mismatch kinds must remain individually reportable; reducing the mismatch rate by weakening detection fails AC-004

## 🧪 Testing Strategy

**Phase 0.** `spec_machine check --all` is the gate; no new test file.

**Phase 1 — `test_stage_span_end_fields.py` (property-shaped).** For varied `(slug, branch)`
including non-ASCII slugs, hyphenated branches, and the session-less degraded path, assert the
emitted `end` row equals the `start`'s pair. Not a fixture comparison — the relation must hold
for every input, which is what AC-003's `oracle_source: property` requires.

**Phase 2 — `test_wrapup_receipt_deterministic_kinds.py` (parametric + negatives).**
- The SPEC's six golden rows: three deterministic kinds expect `[]`, three claim kinds expect
  their own kind.
- `promotion-arithmetic` row must still pass against the **unmodified** check — this is the
  regression guard for ADR-002's decision, not a formality.
- Four `_confined` cases: `documents_updated` contained-absolute → accepted;
  `documents_updated` `/etc/hostname` → `document-escapes-root`; `record_path`
  contained-absolute → accepted; `record_path` `/etc/hostname` → rejected.
- Schema: each shape observed in `delegation.jsonl` parses; an unobserved extra field still
  raises (`strict=True`, never `extra="allow"`).

**Phase 3 — `test_claude_md_second_opinion_guidance.py` (differential + integrity).**
- **Differential (AC-001's declared oracle).** Build a **fixture** `second-opinion.jsonl`
  carrying rows the fixture `.ledger-exclusions.json` excludes. Execute the procedure CLAUDE.md
  documents over that fixture and compare its per-model loss rate to
  `verifier_discrimination`'s over the same fixture; assert equality. **Fixture, never the live
  ledger** — the SPEC's Test-isolation constraint forbids touching the base repo's ledgers and a
  live read would be non-deterministic. A name-presence grep does **not** satisfy this oracle;
  the machine SPEC's `oracle_evidence` says so explicitly.
- **Relocation integrity (AC-002).** Each relocated block appears **byte-for-byte** in its
  `docs/` target, and CLAUDE.md contains a pointer whose path resolves to that file. Guards the
  three outcomes ADR-004 forbids: deletion, summarisation, dangling pointer.
- **Ceiling.** `CLAUDE.md` ≤ 500 lines.

**Integration.** None required; no phase crosses a process boundary unit tests cannot reach.

**Manual (non-gating).** After Phase 3, `/hm:health` and confirm the signal left `signals_failed`.
After Phase 2, one real `/hm:wrapup` — evidence, **not** verification: the observed base rate is
a handful of rows per month, so one clean run cannot distinguish "fixed" from "did not trip".

**Regression scope.** `targeted-test-selection` over changed files; full suite at `/hm:verify`.
Phase 2 additionally re-runs `tests/unit/test_wrapup_receipt.py` in full.

## ⚠️ Risks & Mitigation

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R1 | ADR-003's widened `_confined` reopens the F-04 escape, **on either caller** | low | **high** | The containment test (`resolve()` then `is_relative_to`) is the control, not absoluteness. Phase 2's exit criterion requires explicit negative assertions for **both** `documents_updated` and `record_path`. Phase carries `medium` risk so review attends to it. |
| R2 | The relocated CLAUDE.md blocks stop being read, so the conventions decay | medium | medium | ADR-004 requires the pointer to state what the target contains; the integrity test asserts the pointer resolves. Accepted cost, recorded. |
| R3 | Another already-shipped item is hiding in the remaining four | low | medium | Each was re-verified against current source at Step 1.7. ADR-001 records the rendered-artifact rule. |
| R4 | Widening `WrapupReceipt` weakens the schema | medium | medium | Widen only to shapes observed in `delegation.jsonl`; `strict=True` retained, `extra="allow"` forbidden, asserted by test. |
| R5 | A concurrent session re-renders while Phase 2's template edits are uncommitted | low | medium | Phase 2 is `serial-render` and now spans three target trees. The 5-layer worktree defense guards the base. Land Phase 2 before any other template work. |
| R6 | Phase 3's line count passes but token cost does not move | medium | low | Known and accepted — `SPEC-workflow-loop-efficiency` independently measured the CLAUDE.md ceiling at ~4%. AC-002 claims the ceiling, not a saving. |
| R7 | **The producer half of `promotion-arithmetic` is unprovable and may no-op** | **medium** | medium | Recorded in ADR-002 rather than papered over with a render-grep that would pass on day one. Mitigation is temporal: 14-day observation window on `delegation.jsonl`; any new `promotion-arithmetic` row re-opens the consumer-gated reject-and-retry as its own task. |
| R8 | Phase 2's larger render blast radius produces drift in `.codex/` / `.agents/` that no test covers | low | medium | `tests/structural/test_is_codex_matches_output_path.py` and the render snapshot suite run in Phase 2's regression scope; re-render is a single `--update`, and `git status` after it is the check. |

## ✅ Success Criteria

- [x] **Phase 0** — `spec_machine check --all` exits 0; no AC-005/006 reasoning survives outside
      the Non-Goals entries that deliberately record the withdrawal
- [x] **AC-001** — CLAUDE.md's guidance names `hm verifier_discrimination report` and
      `.ledger-exclusions.json`, **and** a fixture-ledger differential test shows the documented
      procedure's number equals the tool's
- [x] **AC-002** — `CLAUDE.md` ≤ 500 lines; every relocated block byte-for-byte present in
      `docs/` with a resolving pointer from CLAUDE.md
- [x] **AC-003** — a closed span's `end` row carries its `start`'s `task_slug` and `git_branch`
- [x] **AC-004** — a correct delegate receipt yields none of `receipt-unparseable`,
      `document-escapes-root`, `promotion-arithmetic`; the three claim kinds stay distinct;
      the promotion-arithmetic check is byte-identical to today; `/etc/hostname` still rejected
      on both `_confined` callers
- [x] `/hm:health` no longer reports `context_quality:claude_md_within_limit` as failing
- [x] No file listed under **Do not change** appears in the final diff

## 🔬 Phase D.5 — newly-reachable window (per phase)

Written, not reflected on. `[fail:test] fix-introduced-defect-passes-all-gates` is at count:4
in this repo and every instance ran on a fully green four-gate suite, so a green Phase D is
evidence about the FIXTURES' coverage, not about these repairs.

### Phase 1 (AC-003) — repair, so D.5 applies

1. **Window newly reachable:** `end` rows now carry a non-null `task_slug` / `git_branch`, so
   every reader that groups the ledger by those fields reaches a populated branch it has never
   reached — previously 100% of `end` rows were `(None, None)`, so a slug-keyed group was
   always empty and any "no spans for this task" path was the only one exercised.
   **Absent case** (the repo's most-recurring class, count:8): a span opened WITHOUT a slug —
   `worktree create` with no `--task-slug`, and the 54 session-less spans already in the live
   ledger — still emits `end` with `(None, None)`. That is not a regression to fix: the copy
   is faithful, so absent-in stays absent-out. Behaviour is **explicit skip**, and the mixed
   population (some `end` rows populated, some null) is the new state a reader must tolerate.
2. **Test entering it:** `tests/unit/test_stage_span_end_fields.py::test_span_end_preserves_start_task_and_branch`
   (Hypothesis, populated pair) and `::test_legacy_null_bearing_rows_still_parse` (the absent
   case, asserting a null-bearing row still loads). `::test_end_ignores_a_peers_start_when_copying_the_pair`
   covers the mixed-population interleaving. All three are in this same change.
3. Verified by mutation: deleting the two new kwargs kills
   `test_end_ignores_a_peers_start_when_copying_the_pair`.

### Phase 2 (AC-004) — repair, so D.5 applies

1. **Window newly reachable:** `_confined` now RETURNS A PATH for absolute inputs that resolve
   inside the base. Everything downstream of `_confined` — the `.is_file()` existence check,
   the `document-missing` branch, the verify stage's `record_path` adoption — is reached by
   absolute inputs for the first time; before, every absolute string short-circuited to `None`
   at the first `if`. The schema widening opens a second window: `parse_receipt` now RETURNS A
   RECEIPT for replies carrying `steps_skipped` / `drift_verdict`, so `reconcile` runs on
   replies that previously never got past parsing.
   **Absent case:** a receipt with neither new field is unchanged (both default to
   `()` / `None`) — **default value**, not a migration, and no reconciliation reads them.
2. **Tests entering it:** `test_confined_accepts_a_contained_absolute_path` and
   `test_record_path_accepts_contained_absolute_and_rejects_escaping` (both directions, both
   callers); `test_deterministic_receipt_mismatch_kinds_absent[document-escapes-root]` reaches
   the downstream existence check with an absolute input; `[receipt-unparseable]` and
   `test_schema_accepts_the_shapes_the_delegate_actually_emits` enter the parse window;
   `test_schema_still_forbids_an_unobserved_extra_field` pins that the window did not widen
   past the two named fields. All in this change.
3. Verified by mutation: reverting the `_confined` widening kills
   `test_record_path_accepts_contained_absolute_and_rejects_escaping`; reverting the schema
   widening kills `test_schema_accepts_the_shapes_the_delegate_actually_emits`; and the
   FORBIDDEN change ADR-002 exists to prevent — deriving `promotion_candidates` — kills
   `test_promotion_arithmetic_check_is_unchanged`.

**Gap named, not hidden:** the producer half (`stage-delegate_body.md.j2`) has no test that
distinguishes success from no-op, because the rule it strengthens was already present and
already violated. ADR-002's 14-day observation window on `delegation.jsonl` is its
verification. Recorded as R7, not papered over with a render-grep.

### Phase 3 (AC-001, AC-002) — documentation, not a defect repair in code

No code path changes, so no newly-reachable input window. Stated rather than skipped silently.

## 🔍 Plan Validation

**Outcome:** `MAJOR_REVISION` on pass 1 → **resolved by revision**. Per the project's recorded
single-pass policy, **no second validator pass was run**; the cost is that any critique the
revision did not fully answer surfaces at `/hm:execute` Phase A.5 or `/hm:review` instead.

**Cross-model second opinion — `codex`, `status: invoked`, 89.5 s, 4 findings.** All four were
`accepted` by the validator, two with the remedy refuted:

| codex finding | Disposition | Outcome here |
|---|---|---|
| `cb1bf495` — Phase 2 weakens the detector | accepted (arithmetic half KEEP, `_confined` half REFUTED — the machine SPEC's `document-escapes-root` golden row already sanctions accepting contained worktree paths) | **ADR-002 rewritten per-defect**; promotion-arithmetic is now producer-only and the check is in Contract Boundaries |
| `b18f4f59` — the producer edit site is missing | accepted, verified by grep | `templates/agents/stage-delegate_body.md.j2` added to Phase 2 scope; `wrapup_brief.py` moved to Scope-out; merge_hazards widened to three render trees |
| `272763b1` — AC-004's producer half has no gating exit criterion | accepted; **remedy refuted** — a rendered-prompt grep would assert text already on disk at `:83` and already violated on 2026-08-19/23 | ADR-002 records unprovability with a 14-day observation window and rollback trigger; R7 added |
| `25bdd4fe` — Phase 3's tests do not prove the doc ACs | accepted and **escalated** from P2 to critical for the AC-001 half | Fixture-ledger differential test replaces the name-presence grep; relocation-integrity test added; "live ledger" dropped from the AC-001 checkbox per the SPEC's Test-isolation constraint |

**Validator critiques and their resolution:**

| # | Severity | Critique | Resolution |
|---|---|---|---|
| 1 | critical | Consumer arithmetic derivation deletes the anti-fabrication control | ADR-002 rewritten per-defect; the check is now explicitly Scope-out and a Contract Boundary |
| 2 | critical | Phase 2 omits the file carrying the receipt contract | `stage-delegate_body.md.j2` added; `wrapup_brief.py` dropped; merge_hazards widened |
| 3 | critical | Phase 3's test cannot satisfy AC-001's declared `differential` oracle | Fixture-ledger differential test specified; "live ledger" wording removed |
| 4 | warning | Producer half unverified, and its only mechanism already exists and was ignored | Option (a) taken: unprovability recorded in ADR-002 with observation window + rollback trigger; R7 |
| 5 | warning | `_confined`'s second consumer (`record_path`) unnamed and untested | Named in Phase 2 scope; two `record_path` cases added; R1 extended |
| 6 | warning | AC-002's "relocated intact and pointed to" has no test | Relocation-integrity test added (byte-for-byte + resolving pointer) |
| 7 | warning | Phase 3's `depends_on: [1, 2]` unjustified, rationale misattributed | Corrected to `[]`; the misattribution to Interview #8 is stated and withdrawn |
| 8 | warning | `spec_need_verdict: change` has no owning phase; SPEC carries stale AC-005/006 clauses | **Phase 0** added (ADR-005) with the four clauses enumerated |
| 9 | suggestion | `interview_rounds: 4` contradicts the 8-row transcript | Set to 8 |

**Clean categories reported by the validator:** risk-register, adr-completeness,
missing-interview-rounds, rollback-strategy.
