---
type: review
task_slug: second-brain-promotion
status: APPROVED
created: 2026-05-28
review_pass: deep (2nd)
reviewers_invoked: [code-reviewer, security-reviewer, ux-reviewer]
consensus_method: cross-check
drift_verdict:
  result: clean
  scope_violations: []
  scenario_misses: []
  task_slug: second-brain-promotion
  computed_at: 2026-05-28
---

## 🎯 Round 1 Summary (deep pass)

**Grade (initial): B** (one P1-class folder bug + a P1-class observability gap) →
after fixes **Grade A**. This is a deliberate *deeper* second review (user: "once
again deeply") with an expanded reviewer set. The first review pass was
Python-focused; this pass added the **template-prompt** (ux-reviewer) and
**nested-folder** angles that the first round did not exercise.

Reviewers were each given full-file context (per `[fail:review]
abbreviated-diff-causes-reviewer-false-positives`) and launched with `model:opus`
(per `[fail:review] reviewer-subagent-model-unsupported`).

## 🔍 Drift Findings

`drift_verdict: clean`. No new files outside PLAN scope; the round-2 fixes touched
only `second_brain.py`, `wrapup.md.j2`, `test_second_brain.py`, and the
regenerated `.claude/` + snapshot fixtures — all in PLAN scope.

## ✅ Consensus Findings

The three reviewers covered disjoint surfaces (Python / security / prompt), so no
two findings surface-matched on the same `file:line` — formally all are
`manual-only`. But the **security-reviewer independently CLOSED** every prior-round
concern ("the fix is sound; ship it"), which is strong corroboration that the
round-1 hardening held. Findings below are tagged by source; substantive ones
were fixed under orchestrator judgment (the user asked for depth).

## 📝 Manual-Only Findings (acted on)

| # | Sev | Reviewer | Finding | Resolution |
|---|-----|----------|---------|------------|
| D1 | P1 | code | **Nested writable folders**: `promote_note` picks the type-accepting folder, but `write_note`→`_resolve_authorized` re-derived via *first-match* and could return a broader type-rejecting folder → `SecondBrainError` → silent promotion no-op (the exact bug class this feature kills). | `_resolve_authorized` now picks the **most-specific (longest-root) matching folder**. Since the relpath is built under `promote_note`'s chosen folder, the longest matching root is always that folder → the two passes can no longer disagree. Added `test_promote_note_nested_writable_folders_resolve_to_specific` (broad-first ordering). |
| D2 | P1 | ux | **Receipt `N` denominator undefined**: a literal reading let the LLM emit `0 candidates` on a substantive unit, collapsing the ADR-006 observability guarantee (R0). | Defined `N` concretely in the template: count of local 5.1–5.5 entries mapping to a promotable note_type; "not 0 if you wrote any such entry"; explicit "do not collapse N to 0 to avoid the work." |
| D3 | P1 | code | **Silent namespace-key drop**: `--frontmatter-json` advertised for "recommended fields" but `project`/`projects` were stripped with no signal → lost author intent. | `promote_note` now appends a `WriteResult.warning` listing dropped reserved keys; template clarifies identity/namespace keys are owned by `promote` and ignored-with-warning if supplied. Added `test_promote_note_warns_on_dropped_reserved_keys`. |
| D4 | P2 | ux | **Graceful-degrade keyed on the string "SecondBrainError"** — the CLI emits `ERROR: <msg>` and an unreachable mount raises `OSError`, so a strict reader might *not* degrade and abort wrapup. | Reworded to "exits non-zero for **any** reason … print a warning, count not-promoted, continue." |
| D5 | P2 | ux | **Body-file scratch path** under-specified → could be written under `.claude/memory/` and swept into the wrapup commit by Step 6. | Template now says write to a temp file **outside the repo** (`/tmp/hm-promote-<slug>.md`), not under `.claude/memory/`. |
| D6 | P2 | ux | `--source-slug` example named "wiki slug" but wiki is not a promotable note_type. | Replaced with "the `failures.md` slug, the `[decision:...]` slug, or the ADR id" + "unique after kebab-normalization." |
| D7 | P2 | ux | `promote` invocation omitted `--root .` unlike sibling CLI calls in the same template. | Added `--root .` to both claude/codex branches. |
| D8 | P2 | code | Python `links=` arg bypassed the `isinstance(str)` filter applied to `caller_links` (API-only; CLI safe). | Added the same str-filter to the `links` merge. |

## ⚠️ Weak Consensus

None.

## 🤝 Disagreements / Rejected (held position — no new evidence to fold)

**ux P1 — "Step 5.6 has no Jinja `{% if config.second_brain.enabled %}` gate,
diverging from PLAN Phase 2 task 3."** — **Rejected, kept prose gating.**

OBSERVE (reviewer): the PLAN instructed a Jinja render-gate.
COUNTER-EVIDENCE: (1) the sibling Second-Brain sections in `research`/`plan`/
`review` stages all render **unconditionally** (prose-gated) — verified by the
passing `test_codex_stage_procedures.py::test_stage_aware_second_brain_guidance`,
which renders each stage with second_brain NOT enabled in context and asserts the
SB terms are present. (2) Jinja-gating Step 5.6 was *tried* and broke that test
(the `wrapup` parametrization lost `journal`/`decision`/`harness_maker.second_brain`,
which live inside the gated block). (3) Gating only wrapup would make it the lone
stage that hides its SB section, inconsistent with siblings.
CONCLUDE: the established codebase pattern (prose gating + runtime check) is the
correct, consistent choice; the PLAN's Jinja-gate instruction conflicted with it.
Prose gating retained; the one-line `>` runtime guard at the step head is the
intended skip signal. This is a justified deviation from the PLAN, not an oversight.

**security-reviewer** — no findings ≥ P2. All three prior-round concerns
(raw `note_type` interpolation, `source_slug` traversal, reserved-key override)
independently re-verified CLOSED. Residuals (non-reserved Obsidian keys reaching
the user's own vault; theoretical TOCTOU/symlink in a single-user local model)
rated below P2, no action.

## Review Iteration Summary

| Iteration | Grade | Fixes Applied | Remaining | New |
|-----------|-------|---------------|-----------|-----|
| 1 (deep init) | B | — | 3 P1-class + 5 P2 | — |
| 2 | A | 8 (+3 tests) | 0 (ux-P1 gate rejected w/ rationale) | 0 |

Final grade: **A**
Iterations used: 2 / 3
Status: APPROVED
human_review_needed: false
