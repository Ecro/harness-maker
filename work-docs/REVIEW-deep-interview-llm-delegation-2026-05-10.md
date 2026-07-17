---
type: review
task_slug: deep-interview-llm-delegation
status: APPROVED
created: 2026-05-10
reviewers_invoked: [code-reviewer, ux-reviewer]
consensus_method: cross-check
---

## 🎯 Round 1 Summary

**Grade: D** — 10 valid P1 findings across all 4 templates; 0 P0, ~8 P2.
**Blocker type**: UX contract violations + internal consistency gaps in gate logic.
**Note**: 2 code-reviewer findings (plan.md.j2 "stubs") are false positives — caused by abbreviated diff in review prompt; actual plan.md.j2 has full gate content.

---

## 🔍 Drift Findings

No scope drift. All 4 modified files are in PLAN Phase 1-4 scope. Version bump files are in Phase 0 scope. No PLAN-scoped files are missing changes.

---

## ✅ Consensus Findings

*No consensus-passed findings (all findings are single-source from code-reviewer or ux-reviewer).*

---

## ⚠️ Weak Consensus

*None — reviewers covered largely orthogonal aspects (structural vs UX).*

---

## 📝 Manual-Only Findings

### P1 — Must Fix

**CR-P1a** | `loop.md.j2` L265 | **Step numbered "4-H" creates gap after 4-E** (4-F, 4-G exist elsewhere in the doc)
- code-reviewer: LLM cross-referencing step labels will find gap 4-E → 4-H; expects 4-F and 4-G in between.
- The prose "before persisting context (4-F)" correctly names the next step, but the label gap signals missing steps.
- Fix: Rename to "4-E.5" or add a note that 4-F and 4-G are defined elsewhere in the document.

**CR-P1b** | `loop.md.j2` L278 | **`test_reliability` double-mapped to both Inputs and Context axes in Layer 1**
- code-reviewer: A gap in `test_reliability` causes both axes to score low, triggering CLARITI for both → redundant questions about the same field.
- Fix: Inputs → `test_reliability` only; Context → `priority` + `immediate_task` (or omit `test_reliability` from Context).

**CR-P1c** | `research.md.j2` L103 | **Layer 2 has 4 probe candidates vs 5 in spec/plan/loop**
- code-reviewer: Inconsistent coverage surface — research gate missing a depth/time-scope probe.
- Fix: Add 5th probe: "What **time or depth** constraints apply — quick scan vs exhaustive survey?" → scope bounds.

**UX-P1a** | `spec.md.j2` L91 | **Gate fires even when user chose "SPEC is sufficiently clear — end interview"**
- ux-reviewer: User signals done in §2.1 but gate adds up to 12 more questions before they can actually leave.
- Fix: Add at top of §2.5: "If the user chose 'SPEC is sufficiently clear — end interview' in any prior §2.1 round, skip §2.5 and proceed to §2.2."

**UX-P1b** | `plan.md.j2` L198 | **Gate runs even when user chose "Plan is sufficiently clear" in Step B**
- ux-reviewer: Step B installs the early-exit option from Round 2 onward; Step E then runs the gate before honoring it.
- Fix: Add at top of gate in Step E: "If the user chose 'Plan is sufficiently clear — end interview' in Step B this round, skip the gate and exit immediately."

**UX-P1c** | `research.md.j2` L70 | **"Skip — proceed with topic as given" in Phase 0 does NOT guard Phase 0.5**
- ux-reviewer: Phase 0.5's only guard is `--deep` (same as Phase 0). User who skips Phase 0 still hits the full gate.
- Fix: Add at top of Phase 0.5: "If the user chose 'Skip — proceed with topic as given' in Phase 0, skip Phase 0.5 and proceed to Phase 1."

**UX-P1d** | `research.md.j2` L109 | **Layer 3 score formula uses "SC×30%" but research has no Stopping Criteria dimension**
- ux-reviewer: "SC" collides with loop.md.j2's `stopping_criteria`. The research gate's third axis is "Output Quality Criteria".
- Fix: Change Layer 3 display label from "Success Criteria (output)" to "Output Criteria" and use "OQ" abbreviation in the formula description.

**UX-P1e** | `loop.md.j2` L321 | **Escape hatch at 3 NEEDS is prose-embedded, not enumerated options**
- ux-reviewer: Other loop escape hatches (ADR-009) use explicit option lists; this one uses a single prose question with no named options.
- Fix: Specify options explicitly: "Option A: Proceed with accepted ambiguity / Option B: Refine further (re-enter Layer 1)."

**UX-P1f** | `spec.md.j2` L123 (also plan.md.j2, research.md.j2, loop.md.j2) | **MUST NOT repeat rule uses unlabeled question types**
- ux-reviewer: LLM must decide "same type" by semantic similarity over possibly compacted context — unreliable.
- Fix: Assign stable short labels to the 5 types (REJECT / METHOD / STAKEHOLDER / STYLE / PERF) and change rule to "MUST NOT reuse a type label from a prior gate round."

**UX-P1g** | `plan.md.j2` L238 (also spec.md.j2, loop.md.j2) | **Score monotonicity "written justification" has no specified output location or effect**
- ux-reviewer: LLM may block, silently skip, or ask user a meta-question — all wrong. Rule needs an output target.
- Fix: Specify "append a one-line `[score-drop-reason]: ...` note to the Layer 3 display block, then apply the drop."

### P2 — Optional Polish

**CR-P2a** | `loop.md.j2` L309, `spec.md.j2` L131, `plan.md.j2` ~L234 | Python f-string `{g*0.4+c*0.3+sc*0.3:.2f}` in display template
- This IS pseudocode convention for showing LLM computation format — widely understood. **Accepted as-is.**

**CR-P2b** | `loop.md.j2` L317 | Convergence streak reset condition unspecified (NEEDS resets to 0?)
- Fix (optional): "A NEEDS result resets the streak counter to 0; PASS increments by 1."

**CR-P2c** | `research.md.j2` L72 | --deep guard repeated in Phase 0.5 header (redundant per outer Phase 0 guard)
- Fix (optional): Remove "(only when `--deep` is set)" from Phase 0.5 heading; add inline note "Same guard as Phase 0."

**UX-P2a** | `spec.md.j2` L91 | Section numbered §2.5 skips between §2.1 and §2.2
- Accepted: §2.5 as an "additive gate insertion" number is clear enough for LLM reading.

**UX-P2b** | `research.md.j2` L103 | MUST NOT repeat cross-rubric prohibition may over-suppress Phase 0-covered probes
- Fix (optional): Map Phase 0 question types to gate type labels explicitly.

**UX-P2c** | `loop.md.j2` L267 | Gate locale unspecified — should follow loop's `{{ config.locale }}`
- Fix (optional): Add locale instruction to gate header.

**UX-P2d** | `spec.md.j2` L145 | Escape hatch only offers 2 options; no "mark this axis LLM-inferred"
- Accepted: 2 options is sufficient; marking per-axis LLM-inferred adds complexity without clear benefit.

**UX-P2e** | `plan.md.j2` L247 | `---` separator inside Step E creates visual ambiguity about section boundary
- Fix (optional): Replace `---` with a blank line.

---

## 🤝 Disagreements

*No cross-reviewer disagreements on severity.*

---

## 🔧 Round 1 → Round 2 Action Plan

All valid P1 findings are **manual-only** (single-source). Auto-fix does not apply.
Applying all 7 substantive P1 fixes manually before Round 2.

**False positives dropped:**
- code-reviewer plan.md.j2 "Layer 1 placeholder" and "Full gate text stub" — artifacts of abbreviated diff in review prompt; actual template has full gate content (verified via grep).

---

## Round 2 — After P1 fixes (code-reviewer only)

**Grade: B** — 11/12 fixes confirmed; research.md.j2 monotonicity rule missing `[score-drop-reason]` output location.

**Remaining P1:** research.md.j2 L121 — `[score-drop-reason]` not added.

Applied fix: updated monotonicity rule in research.md.j2 to match spec/plan/loop.

---

## Round 3 — Final check

**Grade: A** — All P1 findings resolved. No remaining issues.
- `monotonicity_fixed: true`
- `remaining_p1s: []`

1149 tests pass. Ruff clean. Mypy clean. REVIEW **APPROVED**.
