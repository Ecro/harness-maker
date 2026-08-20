---
type: research
task_slug: ai-work-boundaries
status: complete
created: 2026-08-19
tags: [harness-maker, research, review-loop, contract-boundaries, spec-gaps, wrapup-metrics]
mtime_warn_days: 7
libs_fetched: []
sources: ["~/spoton/work-docs/SYNTHESIS-ai-work-boundaries.md"]
related_docs: ["[[PLAN-review-loop-empirics]]", "[[PLAN-ai-review-exit-criteria]]", "[[PLAN-self-induced-regression-gate]]", "[[PLAN-lens-and-review-fix-verification]]", "[[AUDIT-lens-axis-2026-08]]"]
summary: "Most review-side rules already landed; the real gap is the un-written contract hole — no stage records what the spec deliberately left free"
---

# RESEARCH — AI work boundaries → harness-maker gaps

## 🎯 Recommended Direction

**The review half of the synthesis is already shipped. The unshipped half is the
*contract-hole loop*: `/hm:review` now *detects* oscillation and correctly labels it a
`spec_gap`, but no stage ever writes the hole down — not before (PLAN has no
"deliberately unspecified" section), not after (nothing feeds a detected `spec_gap` back
into the SPEC).** Recommended direction: close that loop end-to-end across
`research → plan/spec → wrapup`, and treat the remaining review-side items
(fixed `max_review_rounds`, grade-A reachability) as a separate measurement question,
not a design change.

Rationale: the synthesis's single strongest datum is that the *only* behaviour that moved
across 47 rounds was the one the contract did not fix, in 1:1 correspondence. harness-maker
now has a detector for exactly that (`hm review_churn oscillation` → `## 🔁 Oscillation`,
`manual-only` `spec_gap`, never moves the grade), which is the expensive half. The cheap
half — a place to write the hole down before and after — does not exist, so every detection
dead-ends at a human-readable heading in one REVIEW file.

## 🔍 Refinement Decisions

Discovery lens: **Technical architecture / implementation** (primary — this is an audit of
this repo's own templates against an external experimental report) + **Research / benchmark**
(the source document is itself the evidence base). `--deep` not set; Phase 0/0.5 skipped.

Method: every synthesis rule in §2 was checked against the *source templates*
(`src/harness_maker/templates/stages/*.j2`), not against documentation. Where a rule was
found, the line is cited. "Landed" means the mechanism exists in the rendered stage, not
that it was verified to fire.

## 🛠️ Approaches Found

### Landed already — do NOT re-plan these

| Synthesis rule | Where it lives | Note |
|---|---|---|
| review: same-reviewer ×N → **category fan-out** | `conditional_router` nine-lens axis; `review.md.j2` dispatch | `[wiki:architecture] nine-lens-axis-and-solo-lens-vote` (2026-08-16). `correctness`/`failure` retired |
| fan-out must include **robustness · naming · style** | same six-category axis (`design·functionality·complexity·robustness·naming·consistency`) | exactly the categories the experiment measured |
| **"0 findings" is not the exit** | `review.md.j2:684` grade gate + `:1070` `Exit reason` enum | exit is grade-threshold / `no-progress` / `cap-exhausted`, never "no findings" |
| **re-review after big fixes, gated on churn** | `review.md.j2:826-861`, `reviewers.rereview_churn_gate` / `rereview_churn_ratio` | this is the r=0.837 rule, implemented as a gate with a null-safe third branch |
| **oscillation is a spec gap, not a defect** | `review.md.j2:1042-1056` `review_churn oscillation` → `manual-only` `spec_gap`, never moves grade | detection landed |
| **every finding gets accept/reject, rejection needs authority** | `review.md.j2:571-589` disposition column; AC-id or `docstring:<path>:<symbol>` | directly encodes "the fixer invents authority when it has none": a docstring-cited rejection still sets `human_review_needed` |
| **ADR records rejected alternatives** | `plan.md.j2:470` ADR template | mandatory field |
| **fixer may run tests, must not edit them** | `review.md.j2:806-807` (with the ADR-006 carve-out for findings whose own target IS a test) | landed |
| **churn measured every round** | `review.md.j2:829-835`; `review_telemetry` `churn_ratio/max_path/measured_n/excluded_n` | measured and persisted |
| **per-repair non-goals ("what I will NOT touch")** | `execute.md.j2:386-411` Phase C.0 | landed 2026-08-17 (PLAN-self-induced-regression-gate ADR-002) — but see gap G2 |
| **absent-case discipline** | `execute.md.j2:514` Phase D.5; CLAUDE.md `failures.md count:8` | landed at *execute* time — see gap G4 |
| SPEC has an out-of-scope surface | `spec.md.j2:99,245` Non-Goals | features not to build — **not** code not to touch (gap G2) |

### Gaps — the actual findings

| # | Gap | Synthesis basis | Where it should go | Risk |
|---|---|---|---|---|
| **G1** | **No "deliberately unspecified" section anywhere.** PLAN's required sections are fixed at 10 (`plan.md.j2:753-771`); none of them is "what the contract leaves free". RESEARCH's `❓ Open Questions` (`research.md.j2:268`) is framed as *questions plan will close*, i.e. things that WILL be decided — the opposite of a slot deliberately left free. | [데이터] the one moved behaviour across 47 rounds was the one the contract did not fix; oscillation point = contract hole, 1:1 | new PLAN section + reframed RESEARCH section | **high** — this is the load-bearing one |
| **G2** | **No durable, citable "Do not change" surface.** Phase C.0's non-goals are *spoken in the turn and written nowhere* ("Nothing is written to disk — this is a declaration, not an artefact", `execute.md.j2:393`), and the template itself admits nothing verifies them afterwards. PLAN phases have `Scope (files in / out)` per phase, which is planning scope, not a prohibition the fixer can cite. | [데이터] contract-less arm: LOC +47%, cog +58%, surviving mutants +50%. [판단] a rejecter with no citable document uses the code's own docstring | PLAN section, persisted; readable by execute + the auto-fix loop | **high** |
| **G3** | **Detected `spec_gap` never returns to the SPEC.** Review reports oscillation rows "with the question each one raises for the human" and stops. Wrapup records design oscillation as `[fail:design]` in `failures.md` (`wrapup.md.j2:484`) — a *failure ledger* entry, not a spec amendment. Nothing proposes the SPEC edit. | [데이터] "고칠 곳은 코드가 아니라 스펙이다" | wrapup step, or a review→spec hand-off | medium-high |
| **G4** | **Absent-case is enforced at execute time, not at AC-authoring time.** The SPEC 6-category interview (`spec.md.j2:92-103`) never asks for the absent case per AC; only `execute.md.j2:514` (post-repair) does. So an AC written today carries the hole into implementation and only the *repair* path catches it. | repo's own most-recurring failure class (count:8) | `spec.md.j2` §2.1 category 3 or the oracle block §2.1.5 | medium |
| **G5** | **`max_review_rounds` is still a fixed int (default 3)** (`review.md.j2:68`), with `cap-exhausted` as a live exit reason. Churn gates *whether to re-review*, not *whether to stop*. The synthesis's point is that a fixed round count is model-dependent and therefore the wrong control (codex reached churn 0 by R3; claude bare went 29→45→73→53→68). | [데이터] churn trajectories diverge by model | `review.md.j2` loop control | medium — but see Open Question Q1 |
| **G6** | **Wrapup records compliance, not code shape.** Wrapup persists AC pass/fail counts, judgment verdicts, grade, and delivery metrics (`/hm:metrics` = CFR + post-merge churn, repo-level and manual). Nothing records **LOC delta · cognitive complexity · worst-function · surviving mutants** for the unit of work — and `wrapup.md.j2` contains zero occurrences of `mutation`/`mutant` despite `spec_mutation.py` + `mutation_receipt.py` existing. | [데이터] all 10 arms × 47 rounds scored 19/19 — compliance distinguishes nothing; every arm difference showed up in the shape metrics | wrapup receipt / observability row | medium |
| **G7** | **Rejected findings are not persisted past the REVIEW file.** Dispositions live in the round record and the REVIEW doc; wrapup's memory step (`wiki.md`/`failures.md`) has no rejection channel. | [판단] "20-26% get rejected and the rationale is an AC citation — the only reusable artifact for the next task" | wrapup Step 5.x memory write | medium |
| **G8** | **Research stage makes no decided/undecided split and never reads what existing tests pin.** The 7 required sections (`research.md.j2`) have no place for "already fixed by the current contract / current tests" vs "open". The synthesis's second research rule — check whether an existing test pins a **production-unreachable** state — has no counterpart anywhere in `research.md.j2` (`reachab` matches only in `execute.md.j2` D.5 and `wrapup.md.j2`). | [데이터] **근거 교체 2026-08-20** (`DELTA-ai-work-boundaries-e7-e8.md` §1): 옛 근거였던 "4/4 회귀가 전부 도달 불가 상태를 고정한 테스트였다"는 은퇴. E8 이 같은 루프를 리뷰어·수정자 둘 다 `src/` 를 읽는 조건으로 재실행하니 그 4개가 10라운드에서 0회. 근본 원인은 테스트가 아니라 **리뷰어에게 호출자를 안 보여준 것**이었다. 규칙(도달성 사전 확인)은 유효하되 이 사례는 그 근거가 아니다 | `research.md.j2` Phase 1 + required sections | medium |
| **G9** | **No `speculative` finding class.** `review.md.j2:1145` demands "evidence (code reference + failure mode + OBSERVE/INFER/CONCLUDE)" for P0/P1 in the *Quality Bar*, and `code-verifier` mode A can DEMOTE — but there is no bucket for a finding that cannot name an input/state, a broken invariant, and a production impact. `grep -i speculative` over all stage templates returns nothing. | [판단] the study never adjudicated finding truth; a finding is not a defect | review finding schema / verifier vocabulary | low-medium |
| **G10** | **Research is not told to avoid performance/quality claims.** Minor, but the synthesis names it as experiment 1's largest error (not validating what the oracle guarantees). | [데이터] | `research.md.j2` Quality Bar | low |

### Three candidate shapes for G1+G2 (the load-bearing pair)

| | A — one new PLAN section | B — extend SPEC Non-Goals | C — a machine artifact |
|---|---|---|---|
| Approach | Add `## 🚧 Contract Boundaries` to PLAN's required sections: *Do-not-change* (surfaces the implementation must leave alone) + *Deliberately unspecified* (slots left free, with the reason) | Split SPEC Non-Goals into "not building" vs "not touching"; add a free-slot list | Emit a `contract-boundaries.yaml` next to the PLAN; execute C.0 and the auto-fix loop read it |
| Assumption | PLAN is the document execute already reads for scope | SPEC is where contracts live, so the boundary belongs there | Prose declarations don't bind; only a read artifact does |
| Evidence for | Execute already loads PLAN phase scope; the oscillation detector's output is per-slug and would slot beside it | Non-Goals already exists and is already interviewed | This repo's own repeated lesson: prose recipes have no execution surface and ship silent-skip bugs (CLAUDE.md, second-opinion §ADR-001) |
| Trade-off | Two more required sections on an already-10-section document; PLAN grows | SPEC-less harnesses (`dev_mode: task-driven`) get nothing | Highest cost; another persisted format needing a reverse mapper (checklist item 6) |
| Compatibility | High — `plan.md.j2:753` is a numbered list, additive | Medium — the 6-category order is load-bearing for the interview | Medium — a new format + reader + render gate |
| Risk | low | medium (SPEC-less blind spot) | medium-high (surface budget; `surface_allowance` applies) |

Note: A and B are not exclusive; the honest split is that **"deliberately unspecified" is a
PLAN concept** (it is an architectural decision to leave a slot free, and it belongs next to
the ADRs that rejected the alternatives) while **"do not change" is closer to SPEC's
Non-Goals** — but SPEC is optional in `task-driven` mode, which argues for putting both in
PLAN and having SPEC feed it when present.

## ⚠️ Pitfalls

1. **Do not re-plan the fan-out.** The nine-lens axis landed 2026-08-16 with a measured Phase-0
   pilot; re-opening it would re-litigate `[wiki:architecture] nine-lens-axis-and-solo-lens-vote`.
2. **G5 is entangled with a known live risk.** The nine-lens change *removed the system's only
   false-positive filter* (a solo lens now carries a full vote — same wiki entry, point 1).
   Grade A requires 0 consensus-passed P0 **and** 0 P1. The synthesis's own datum is that claude
   returned findings on verified-correct code 14/14 times. Replacing the round cap with a churn
   convergence criterion while grade A may be structurally hard to reach could turn a bounded
   `cap-exhausted` into an unbounded loop. **Measure before changing** — the telemetry rows
   already carry `churn_ratio` and `Exit reason` per round.
3. **Prose declarations that nothing reads are this repo's documented failure mode.** Phase C.0
   already says so about itself. Any G2 fix that is only prose repeats it. But an artifact
   nothing reads is worse — cf. `.claude/hooks/hooks.json` (rendered for months, read by
   nobody in Claude Code).
4. **A new PLAN section is a surface-budget event.** `surface_allowance` with a `chars` figure
   and `round_trips` per variant applies; adding sections without one is how the ratchet gets
   silently regenerated (`[wiki:architecture]` last paragraph).
5. **G6's metrics must not become a gate.** `/hm:metrics` explicitly refuses to be one
   ("never a gate, never a score: optimizing the number instead of the work destroys the
   signal — Goodhart"). Recording LOC/cog/mutants must inherit that stance or it will be
   optimized against.
6. **G4 touches the interview's open-ended cap.** Locale `ko` caps open-ended questions at 1
   per turn; an absent-case question per AC must be closed-form (like the §2.1.5 oracle block,
   which explicitly exempts itself) or the interview will stall.
7. **The synthesis's own caveats carry over.** Its contract density (156 lines → 19 AC) is
   above practical average, and it explicitly marks as **[미검정]** whether the contract also
   reduces what AI *misses* (experiment 5's primary metric). Do not plan as if it does — the
   corrected proposition is that boundaries change what AI *adds*, not what it *misses*.

## ❓ Open Questions

- **Q1 (blocks G5).** What do this repo's own `review_telemetry` rows say about the round cap?
  Specifically: how often is `Exit reason: cap-exhausted` (the only exit meaning a higher cap
  would have helped) vs `converged` vs `no-progress`, and what is the `churn_ratio` trajectory
  across rounds within a run? If `cap-exhausted` is rare, G5 is a non-problem and should be
  closed as "measured, not needed".
- **Q2 (blocks G1/G2 shape).** Approach A, B, or C — and if A, do the two lists go in one
  section or two? See the three-way table.
- **Q3.** Is a `spec_gap` fed back as (a) a proposed SPEC edit written by wrapup, (b) an
  `[fail:design]` entry only (status quo), or (c) a blocking item on the next `/hm:plan` for
  the same slug?
- **Q4.** Which shape metrics in G6 are cheap enough to be unconditional? LOC delta and churn
  are free from git; cognitive complexity needs a tool (`ruff` does not compute it; `radon`/
  `lizard` would be a new dependency); surviving mutants already exist in `spec_mutation` but
  only run under the mutation gate. Likely answer: LOC + churn unconditional, mutants when the
  gate ran, cognitive complexity deferred.
- **Q5.** Does G9 (`speculative`) need a new severity class, or is it `code-verifier` mode A's
  DEMOTE with a stricter rubric? A new class costs a schema change and touches
  `codex_adapter.finding_id`'s neighbourhood; a rubric change does not.
- **Q6.** Scope: is this one PLAN or several? G1+G2 are one unit (both are PLAN sections about
  boundaries). G3+G7 are one unit (both are wrapup persistence). G8+G10 are one unit (both are
  research-stage sections). G4, G5, G6, G9 are independent.

## 📚 Sources

- `~/spoton/work-docs/SYNTHESIS-ai-work-boundaries.md` — the source report (experiments 1-4 +
  code-quality metrics; experiment 5 pre-registered, not yet run).
- Its cited upstreams, not read here: `실험기록-ai-review-convergence.md`,
  `실험기록2-스펙먼저.md`, `실험기록3-재리뷰와팬아웃.md`, `STATE-ai-review-experiments.md`,
  `PLAN-process-contract-experiment.md`.
- No external web or library sources — this is an internal audit.

Primary internal evidence (read directly):
`src/harness_maker/templates/stages/{research,spec,plan,execute,review,wrapup,verify}.md.j2`,
`src/harness_maker/{review_telemetry,review_consensus,delivery_metrics}.py`,
`src/harness_maker/templates/commands/hm/metrics.md.j2`.

## 🔗 Related Internal Docs

- [[PLAN-review-loop-empirics]] — ADR-001 (six-category axis), ADR-007 (solo lens = full vote),
  ADR-002 (dispositions + AC-cited rejection), ADR-003 (oscillation as `spec_gap`),
  ADR-004 (churn gating). Consumes most of the synthesis's review section.
- [[PLAN-ai-review-exit-criteria]] — ADR-003 (coverage blocks approval), ADR-005 (confirmation
  pass replaces the approval step), ADR-013 (the monotone lattice recorded as an assumption).
- [[PLAN-self-induced-regression-gate]] — ADR-002 (the pre-repair declaration that became
  Phase C.0, and the reason it references nothing).
- [[PLAN-lens-and-review-fix-verification]] — `status: partial`; Phases 2-5 deferred.
- [[AUDIT-lens-axis-2026-08]], [[BASELINE-DELTA-multi-lens-review-round]].
- `[wiki:architecture] nine-lens-axis-and-solo-lens-vote` (2026-08-16) — the FP-filter removal
  that pitfall 2 depends on.
