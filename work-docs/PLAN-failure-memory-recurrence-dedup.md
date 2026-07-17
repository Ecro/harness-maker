---
type: plan
task_slug: failure-memory-recurrence-dedup
status: complete
created: 2026-07-04
tags: [harness-maker, plan, memory, dedup, wrapup, recurrence]
research_doc: "[[RESEARCH-failure-memory-recurrence-dedup]]"
interview_rounds: 3
adrs: 7
validator_outcome: MAJOR_REVISION_RESOLVED
review_grade: A
summary: "Repair recurrence dedup end-to-end: wrapup search-before-write + occurrence-log + escalation last-mile"
---

# PLAN — Repair failure-memory recurrence dedup

## 🎯 Executive Summary

**What:** Make the `count≥3` failure-escalation pipeline actually fire end-to-end, fixing
the defects RESEARCH found: (Gap 1) the dedup key is an LLM-invented slug with no read-back,
so the same failure lands under different slugs and `count` never increments; (Gap 2) design
oscillation is excluded from the failure taxonomy and has no memory anchor to be recognized
against. Plus the validator-surfaced **last mile**: the escalation step itself (Step 5.3,
`count≥3 → pending-proposals.md`) is the same advisory, receipt-less, silent-dead shape — so
even correct counting would not produce the reported missing output.

**Why:** In `~/edge_testfarm_os`, 19/19 failure entries are `count:1` and
`pending-proposals.md` has never been created. Contrast: harness-maker's own
`[fail:design] worktree-finalize-pulls-orphan-wip-into-main` reached `count:3` **only because
a human deliberately reused the slug** — proving the CLI mechanism is sound and the missing
pieces are (a) slug-reuse discipline, (b) a memory anchor for oscillation, and (c) an
observable, non-advisory escalation step.

**Key decisions (interview-locked, 3 rounds):**
- ADR-001 — Gap 1 fix = a **numbered MUST search-before-write step** in wrapup (LLM +
  existing `memory_retrieve`), not CLI-side fuzzy merge.
- ADR-002 — on-match body policy = **occurrence-log accumulation** via an explicit
  `--occurrence-note` CLI flag; count++ and bullet-append are **atomic** (empty note →
  fail-closed).
- ADR-003 — match bias = **under-merge** (uncertain → new entry; never false-merge).
- ADR-004 — a **discriminating one-line receipt** (`dedup: searched K existing failures,
  N considered, M reused`) makes the search observable — `K>0` proves the step executed
  regardless of match outcome. No `/hm:health` smoke (bounded, recorded risk).
- ADR-005 — Gap 2 = **taxonomy expansion in the existing `design` category** (design
  oscillation now qualifies), NOT a new category and NOT a git-churn detector.
- ADR-006 — the search step is **anchored on `wiki.md` design/architecture entries too**, so a
  reversal can be matched against the prior decision it flips (extends `memory_retrieve` scope;
  still no git detector).
- ADR-007 — the **escalation last-mile (Step 5.3) is itself converted to a numbered MUST +
  receipt** so `count≥3 → pending-proposals.md` stops being silent-dead.

**Honest scope of the Gap-2 fix:** oscillation is caught **only when the LLM records the
reversal at wrapup**, anchored against a prior `wiki.md` decision (ADR-005+006). Purely
git-visible churn that the LLM never records at wrapup is **not** caught — git-history mining
is an explicit Non-Goal (see below). This is a deliberate narrowing of RESEARCH approach C.

**Estimated impact:** 1 code file (`memory_md.py` + its CLI), 1 template (`wrapup.md.j2`
Steps 5.2 & 5.3), 2 memory-tier headers (`failures.{en,ko}.md.j2`), plus render + unit tests.
Ships to consumers on next `/harness-maker:make --update` + re-render.

## 📚 Prior Work

- `[wiki:architecture] second-brain-promotion-pipeline` — **load-bearing precedent**: an
  advisory (non-numbered) prompt instruction is silent-skipped ~100%; the fix that worked was
  a *numbered MUST step + an observable receipt* whose count-of-things-evaluated is itself the
  signal. ADR-001/004/007 copy this shape; ADR-004's `K` (searched count) is the
  execution-proof, mirroring the precedent's `N candidates`.
- `[fail:design] worktree-finalize-pulls-orphan-wip-into-main | count:3` — the one entry where
  recurrence counting worked in harness-maker, via manual slug reuse. Confirms `_upsert`
  count++ is correct; only caller discipline was missing.
- RESEARCH-failure-memory-recurrence-dedup — root cause + git evidence (iptables 6×, cron 5×,
  boot-marker 3×). Note RESEARCH required approach C (git-churn detector) for cross-unit reach;
  this PLAN narrows that to LLM-recorded-reversal-anchored-on-wiki (ADR-006) and declares pure
  git-churn mining a Non-Goal.
- Global learning `absent-case = feature black hole` (2026-06-08, count:8) — count++ activates
  only on the present case (prior identical slug); the absent case silently mints `count:1`.

## 🎙️ Interview Transcript

| # | Round | Topic | Category | Choice | → ADR |
|---|-------|-------|----------|--------|-------|
| 1 | 1 | Scope | Scope | Gap 1 + taxonomy (no git-churn detector) | ADR-005 |
| 2 | 1 | Dedup mechanism | Architecture | wrapup forced search (LLM + memory_retrieve) | ADR-001 |
| 3 | 1 | Body-on-match | Contract | occurrence-log accumulation | ADR-002 |
| 4 | 1→2 | Observability | Observability | "none" → reconsidered to one-line receipt | ADR-004 |
| 5 | 2 | Match bias | Risk | under-merge (safe) | ADR-003 |
| 6 | 2 | Thrash recording | Architecture | reuse 'design' category + expand qualifier | ADR-005 |
| 7 | 3 | ADR-005 over-claim | Architecture | extend search anchor to wiki.md (not a detector) | ADR-006 |
| 8 | 3 | Escalation last-mile | Architecture | fix Step 5.3 (numbered MUST + receipt) | ADR-007 |
| 9 | 3 | Existing entries | Scope | forward-only + explicit Non-Goal | Non-Goals |

Round 2 note (Q4): the receipt-less advisory step was shown to reproduce the exact silent-skip
failure from `second-brain-promotion-pipeline`; the user moved "none" → "one-line receipt".
Round 3 note: the plan-validator (MAJOR_REVISION) + Codex CX5 established that taxonomy-only
cannot reach cross-unit oscillation and that Step 5.3 was left silent-dead; interview #7/#8/#9
resolved both plus the migration scope.

## 📐 Architecture Decision Records

### ADR-001: Gap 1 dedup via wrapup search-before-write (LLM), not CLI fuzzy merge
**Status:** Accepted (2026-07-04, via /hm:plan interview)
**Context:** `_upsert` increments `count` only on exact slug match; the slug is invented fresh
each wrapup with no read-back → real recurrences land under distinct slugs.
**Decision:** Add a numbered MUST step to wrapup Step 5.2 that runs `memory_retrieve` before
writing a failure and, on a semantic match, passes **that exact existing slug** so count++
fires. Judgment stays with the LLM; Python owns storage + safety rails.
**Consequences:**
- ✅ Reuses `memory_retrieve`; matches the proven numbered-step+receipt shape.
- ⚠️ Runtime correctness depends on the LLM running the step — mitigated (not eliminated) by
  ADR-004's discriminating receipt + a Phase-2 render-grep proving the step is *present*.
**Rejected alternatives:** CLI-side fuzzy merge (judgment in Python, hard-to-reverse false
merges); hybrid LLM+CLI verify (max cost; deferred hardening).
**Source:** Interview #2

### ADR-002: On-match body = occurrence-log via explicit `--occurrence-note`, atomic with count++
**Status:** Accepted (2026-07-04)
**Context:** Today `_upsert` REPLACES the body on count++, destroying prior-occurrence context;
and count++ is unconditional, so an empty body would increment count with no evidence
(Codex CX2 / validator warning #4). The CLI body also silently means two different things on
new-vs-matched slugs with no guard (validator warning #6).
**Decision:** Add an explicit `--occurrence-note` flag to `upsert-failure`. On a matched slug:
PRESERVE the existing body and APPEND `- [{today}] {note}` (single line, validated non-empty),
`count++` — **append and increment are atomic** (empty/missing note on a match → non-zero exit,
no increment). New slug: `--body-file` full paragraph as today. Safety net: `--body-file` on an
*already-existing* slug appends the body as an occurrence (collapsed) rather than replacing, so
an LLM misjudgment never loses data. Heading keeps first-seen date.
**Consequences:**
- ✅ A `count:N` entry carries exactly N−1 dated occurrence lines + the original → escalation
  evidence is real; no count/evidence divergence.
- ✅ The new-vs-matched CLI semantics are explicit (distinct flag), not a hidden match-branch.
- ⚠️ Entries grow; acceptable (failures rare, count≥3 is the goal). Occurrence bullets
  (`- [..]`) are never heading-shaped (`## [..]`) so the parser/guard are unaffected.
**Rejected alternatives:** Replace (loses context); keep-first+date-range (loses per-occurrence
context); auto-collapse full body with no flag (silent multiline loss — warning #6).
**Source:** Interview #3 + validator warnings #4/#6

### ADR-003: Match bias = under-merge (safe)
**Status:** Accepted (2026-07-04)
**Context:** The search must decide "same failure?" under uncertainty.
**Decision:** Bias toward **under-merge** — not confident → NEW entry. Never false-merge.
**Consequences:** ✅ zero false-merge risk; ⚠️ a borderline recurrence may still mint a new
`count:1` (accepted; occurrence-log aids later human reconcile).
**Rejected alternatives:** reuse-aggressive (merges unrelated failures); explicit same-root-cause
rule (chosen bias simpler to state).
**Source:** Interview #5

### ADR-004: Discriminating one-line wrapup receipt (no health smoke)
**Status:** Accepted (2026-07-04)
**Context:** `pending-proposals.md` never being created went unnoticed for a project's whole
history. A receipt whose only signal is `M` (matches) is near-useless because recurrences are
rare → `M=0` both when the search ran-and-found-nothing and when it was skipped (validator #3).
**Decision:** wrapup Step 5.2 prints `dedup: searched K existing failures, N considered,
M reused`. **`K>0` proves the search executed** independent of outcome; `N`/`M` report the
result. No `/hm:health` smoke this round.
**Consequences:** ✅ silent-skip of the search becomes visible every wrapup; ⚠️ a stale
re-render that drops the step is only caught by the Phase-2 render-grep at CI, not at runtime
(bounded, recorded risk; health smoke deferred).
**Rejected alternatives:** no observability (reproduces silent death); `M`-only receipt
(non-discriminating); receipt + health smoke (deferred).
**Source:** Interview #4 + validator warning #3

### ADR-005: Gap 2 via taxonomy expansion in the existing `design` category
**Status:** Accepted (2026-07-04)
**Context:** Design oscillation is git-churn, not a discrete symptom; Step 5.2's qualifier
excludes "design evolution" → thrash never enters `failures.md`.
**Decision:** No new category, no detector. Amend the qualifier: design **oscillation**
(reverting/re-litigating a prior decision — same file/config flipped back) qualifies as
`[fail:design] <stable-family-slug>`. Add a numbered "did this unit reverse a prior decision?"
check (anchored per ADR-006).
**Consequences:** ✅ catches LLM-recorded reversals without a new module; ⚠️ depends on the LLM
recognizing the reversal at wrapup (see ADR-006 for the anchor; pure git-churn = Non-Goal).
**Rejected alternatives:** git-churn detector (deferred, Non-Goal); new `[fail:thrash]` category
(unnecessary).
**Source:** Interview #1, #6

### ADR-006: Search anchored on wiki.md design/architecture entries (fixes the ADR-005 cross-unit gap)
**Status:** Accepted (2026-07-04, via /hm:plan interview — validator critical #1 / Codex CX5)
**Context:** The reversal check runs at wrapup with no prior-decision context; ADR-001's search
queried `failures.md` only, but design decisions live in `wiki.md`, so a flip had **no anchor**
to be recognized against — the exact evidence (iptables 6× over months, cross-unit) would no-op.
**Decision:** Extend the Step 5.2 search to also surface `wiki.md` `[wiki:architecture]` /
`[wiki:pattern]` entries via `memory_retrieve`, giving the reversal check a memory anchor
("this unit reverted the decision recorded in `[wiki:...] X`"). Still `memory_retrieve` only —
**no git-history mining**.
**Consequences:** ✅ within-unit reversal is now checkable against the prior recorded decision →
repeated flips of the SAME decision accumulate under a stable `[fail:design]` family slug across
units; ⚠️ a flip whose prior decision was never recorded in wiki, or churn the LLM never notices,
is still missed (Non-Goal). The Executive Summary is scoped to this honest reach.
**Rejected alternatives:** demote to within-unit-only + full Non-Goal (honest but leaves the
user's case uncaught); restore a git-churn signal (rejected in Round 1, larger scope).
**Source:** Interview #7

### ADR-007: Escalation last-mile (Step 5.3) converted to numbered MUST + receipt
**Status:** Accepted (2026-07-04, via /hm:plan interview — validator critical #2)
**Context:** No phase touched Step 5.3 (`count≥3 → write pending-proposals.md`). It is the same
unnumbered, receipt-less, LLM-discretionary shape this PLAN proves is silent-dead — so fixing
counting alone still would not produce the reported missing `pending-proposals.md`.
**Decision:** Convert Step 5.3 to a numbered MUST step with a one-line receipt
`escalation: K entries at count≥3, P proposals written`, plus a Success Criterion and a
render-grep asserting the step + receipt are present.
**Consequences:** ✅ the actual reported symptom (no proposals ever written) is directly
addressed and observable; ⚠️ still LLM-authored proposal content (acceptable — same discipline
model as 5.2, now observable).
**Rejected alternatives:** fix counting only (leaves the reported symptom unfixed).
**Source:** Interview #8

## 🚫 Non-Goals (explicit — validator warning #5)

- **Migration of existing `count:1` entries.** This fix is **forward-only by decision**. The 19
  fragmented `~/edge_testfarm_os` entries stay split; a one-shot audit/re-slug command was
  considered and declined (Interview #9). Recurrence accumulates from the next correctly-matched
  occurrence onward.
- **Git-history churn mining / cross-unit oscillation with no wrapup recording.** ADR-006
  anchors only LLM-recorded reversals against `wiki.md`. Purely git-visible flip-flops the LLM
  never records at wrapup are not caught (RESEARCH approach C, deliberately deferred).
- **Wiki-tier occurrence-log.** `wiki.md` deliberately **replaces on match** (current-truth
  semantics); only `failures.md` is cumulative. The asymmetry is intentional (validator #5b /
  Codex CX8).
- **`/hm:health` positive smoke-test** for the recurrence pipeline (ADR-004; the receipt is the
  observability floor this round).

## 🏗️ Technical Design

**Current State:**
- `memory_md.py::_upsert` — match branch (219–228) replaces body, `count++`, first-seen date;
  exact-slug match only (213). No empty-body rejection (169–173).
- `wrapup.md.j2` Step 5.2 (349–369) — "for each new failure pattern", no read-back, qualifier
  excludes design evolution. Step 5.3 (371–382) — advisory `count≥3` escalation, no receipt.
- `memory_retrieve.py` — existing lexical-prefilter + rerank helper.

**Affected Components:** `memory_md.py` (`_upsert` occurrence-log branch + `--occurrence-note`
CLI flag + empty guard); `wrapup.md.j2` Steps 5.2 & 5.3; `failures.{en,ko}.md.j2` headers.

**Dependencies:** none new (reuses `memory_retrieve`).

**Data Flow (wrapup Step 5.2/5.3, new):**
1. For each failure pattern → `memory_retrieve` over **failures.md AND wiki.md design entries**
   (ADR-006).
2. LLM judges match under **under-merge** bias (ADR-003); also checks "did this unit reverse a
   prior recorded decision?" (ADR-005+006).
3. Match → `upsert-failure --slug <existing> --occurrence-note "<one-line>"` → atomic
   count++ + dated bullet (ADR-002). No match → `--body-file` new entry (count:1).
4. Print `dedup: searched K existing failures, N considered, M reused` (ADR-004).
5. Step 5.3 (numbered MUST): for every entry now at `count≥3`, write/update a
   `pending-proposals.md` proposal; print `escalation: K entries at count≥3, P proposals
   written` (ADR-007).

**API Changes:** `upsert-failure` gains `--occurrence-note` (mutually-informative with
`--body-file`); `_upsert` failure-match branch appends instead of replacing and rejects empty
content. `_FAILURE_META_RE` / `_HEADING_RE` unchanged.

## 📝 Implementation Plan

### Phase 1 — `memory_md` occurrence-log + `--occurrence-note` CLI + tests
- `depends_on`: []
- `parallel_group`: serial-core
- `merge_hazards`: `src/harness_maker/memory_md.py` (contract shared with Phase 2) — none within phase
- **Scope (in):** `memory_md.py` (`_upsert` failure-match branch; `--occurrence-note` arg
  parsing + empty-content rejection); `tests/unit/test_memory_md*.py`.
- **Scope (out):** wrapup template, headers.
- **Change:** in `matches and is_failure`: `existing_body = lines[start+1:end]`;
  `occurrence = f"- [{today}] " + " ".join(occ_lines).strip()`; if empty → non-zero exit (no
  increment); else `new_lines = lines[:start] + [heading(count+1), *existing_body, occurrence]
  + lines[end:]`. New CLI flag `--occurrence-note` (single-line source; `--body-file` still
  valid and, on an existing slug, is appended-as-occurrence not replaced). Wiki match unchanged
  (replace).
- **Exit criterion:** `uv run pytest tests/unit/test_memory_md*.py -q` green, incl. new cases:
  (a) 1→2→3→4 repeats produce count:N + N−1 dated bullets + original body, **canonical layout
  locked** (validator #7/CX3); (b) empty `--occurrence-note` on match → non-zero exit, count
  unchanged (CX2/#4); (c) occurrence note containing a `## [fail:...]`-shaped substring is not
  misparsed by `_entry_headings` once prefixed `- [date] ` (CX4); (d) multi-line body passed on
  a matched slug collapses safely (#6); (e) wiki replace-on-match regression intact.
- **Risk:** low · **Rollback:** revert Phase 1 (self-contained; CLI backward-compatible).

### Phase 2 — wrapup Steps 5.2 & 5.3 rewrite + headers + render tests
- `depends_on`: [1]
- `parallel_group`: serial-template
- `merge_hazards`: `wrapup.md.j2` + rendered snapshots
- **Scope (in):** `templates/stages/wrapup.md.j2` Steps 5.2 & 5.3; `failures.{en,ko}.md.j2`
  headers; render/snapshot/grep tests.
- **Change:**
  1. **5.2.0 search-before-write (MUST):** `memory_retrieve` over failures.md **and wiki.md
     design/architecture entries** (ADR-006), under-merge bias (ADR-003).
  2. On reuse: `--occurrence-note` with the exact existing slug.
  3. Receipt `dedup: searched K existing failures, N considered, M reused` (ADR-004).
  4. Qualifier: design **oscillation** (reversing a prior wiki-recorded decision) qualifies as
     `[fail:design] <stable-family-slug>` + the "did this unit reverse a prior decision?" check
     (ADR-005+006).
  5. **5.3 escalation (MUST):** numbered step + receipt `escalation: K entries at count≥3,
     P proposals written` (ADR-007).
  6. `failures.{en,ko}.md.j2` headers document the occurrence-log bullet format.
- **Exit criterion:** render tests green; **grep tests assert the rendered wrapup contains**
  (i) the `memory_retrieve` search step incl. a wiki-anchor reference, (ii) the `dedup: searched`
  receipt, (iii) the numbered 5.3 step + its `escalation:` receipt; ko/en header snapshots
  refreshed.
- **Risk:** medium (template wording drives LLM behavior — keep steps numbered + imperative).
- **Rollback:** revert Phase 2; Phase 1 stands alone (CLI backward-compatible).

### Phase 3 — Re-render harness assets + full suite
- `depends_on`: [1, 2]
- `parallel_group`: serial-render
- `merge_hazards`: rendered `.claude/` assets, snapshot fixtures
- **Scope (in):** re-render so this repo's own `.claude/commands/hm/wrapup.md` + `failures.md`
  header reflect the templates; full `pytest` + `mypy --strict` + `ruff check`/`format --check`.
- **Scope (out):** 5-file version bump (release-time, per CLAUDE.md — handled at wrapup).
- **Exit criterion:** full `uv run pytest` green (background); `mypy --strict` clean; `ruff`
  clean; rendered wrapup shows the new 5.2/5.3 steps + receipts.
- **Risk:** low · **Rollback:** revert Phase 3.

## 🧪 Testing Strategy

- **Unit:** occurrence-log 1→2→3→4 canonical layout; empty-note fail-closed; heading-substring
  safety; multiline-on-match collapse; wiki replace regression.
- **Render/grep:** rendered wrapup contains 5.2 search step (+ wiki anchor), `dedup: searched`
  receipt, numbered 5.3 + `escalation:` receipt; ko/en header snapshot refresh; render
  determinism (freeze_time / generated_at mask) preserved.
- **Integration:** none required — LLM steps are prompt-level, proven by render-grep not a live
  call.
- **Manual:** re-read rendered wrapup to confirm 5.2 AND 5.3 read as numbered MUST, not advisory.

## ⚠️ Risks & Mitigation

| Risk | Severity | Mitigation |
|------|----------|------------|
| LLM skips the search step despite numbering | med | ADR-004 `K>0` receipt surfaces execution every wrapup |
| under-merge misses a genuine recurrence | low | accepted (ADR-003); occurrence-log aids human reconcile |
| count/occurrence divergence on empty note | low | Phase-1 fail-closed guard + unit test (CX2/#4) |
| occurrence bullet parsed as heading | low | `- [..]` ≠ `## [..]`; parser regression test (CX4) |
| Gap-2 misses pure git-churn oscillation | med | scoped honestly as Non-Goal; ADR-006 covers LLM-recorded+wiki-anchored reversals |
| stale re-render drops a step, uncaught at runtime | low | Phase-2 render-grep catches at CI; runtime health smoke deferred (ADR-004) |
| template wording too soft → advisory drift | med | mirror proven numbered-step shape for BOTH 5.2 and 5.3 |

## ✅ Success Criteria

- [x] `_upsert` accumulates count with an occurrence-log (unit-proven 1→2→3→4, canonical layout).
- [x] Empty `--occurrence-note` on a match is fail-closed (count unchanged).
- [x] Rendered wrapup 5.2 contains a numbered search-before-write MUST step querying
      failures.md **and** wiki.md design entries.
- [x] Rendered wrapup prints `dedup: searched K existing failures, N considered, M reused`.
- [x] Rendered wrapup **Step 5.3 is a numbered MUST** printing `escalation: K entries at
      count≥3, P proposals written`.
- [x] Step 5.2 qualifier records design oscillation as `[fail:design]` with a stable family slug.
- [x] `failures.{en,ko}.md.j2` headers document the occurrence-log format.
- [x] Full `pytest` + `mypy --strict` + `ruff` green; re-rendered assets consistent.

**Execution status (2026-07-04):** all 3 phases GREEN. Phase 1 (`memory_md` occurrence-log +
`--occurrence-note`), Phase 2 (wrapup 5.2/5.3 + failures headers + 6 render-grep tests),
Phase 3 (snapshot regen ×8 + full suite). Verification: full `pytest` exit 0, `mypy --strict`
117 files clean, `ruff check`/`format` clean. Changes committed to `hm/failure-memory-recurrence-dedup`
(WIP), awaiting `/hm:wrapup` squash-land. No commit on main.

## 🔍 Plan Validation

- **Round 1 (plan-validator, model=opus) + Codex second opinion (gpt-5.5, `codex_status:
  invoked`):** **MAJOR_REVISION**. Two criticals: (1) ADR-005 taxonomy-only structurally cannot
  reach cross-unit oscillation (no wiki anchor) while the summary over-claimed; (2) the reported
  symptom (`pending-proposals.md` never created) was unaddressed — Step 5.3 left silent-dead.
  Warnings: non-discriminating receipt, count/occurrence divergence, missing Non-Goals, hidden
  CLI match-branch semantics, test-coverage gaps.
- **Resolution:** Interview Round 3 → ADR-006 (wiki-anchored search), ADR-007 (5.3 numbered +
  receipt), forward-only Non-Goals section, ADR-004 receipt made discriminating (`K` proves
  execution), ADR-002 atomic count++/append via `--occurrence-note` + empty guard, Phase-1 test
  matrix expanded (CX2/CX3/CX4/#6). CX7 = DUPLICATE (Phase-2 render-grep already covers it).
- **Codex reconciliation:** CX1 KEEP (accepted-risk, receipt strengthened), CX2 KEEP (Phase 1
  guard), CX3/CX4 KEEP (Phase 1 tests), CX5 KEEP→critical (ADR-006), CX6 KEEP (Non-Goal), CX7
  DUPLICATE, CX8 KEEP (Non-Goal).
- **Re-validation (Round 2, final):** plan-validator (model=opus) → **APPROVED**, no residual
  blockers; all 2 criticals + 5 warnings marked resolved. Confirmed ADR-006's wiki anchor needs
  **no new code** — `memory_retrieve.py:321-336` already loads both `wiki.md` and `failures.md`
  dual-tier, so Phase 2 only points the prompt at an existing capability.
