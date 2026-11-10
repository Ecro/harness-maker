---
type: review
task_slug: ask-less
created: 2026-11-10
spec: "[[SPEC-ask-less]]"
plan: "[[PLAN-ask-less]]"
rounds: 1
reviewers: [code-reviewer]
summary: "One code-reviewer round: 8 findings (3 major, 3 minor, 2 nit). Seven accepted and fixed; F8 rejected as a SPEC non-goal."
---

# REVIEW — ask-less

One code-reviewer round raised 8 findings. Seven were accepted and fixed. F8 was rejected because
the SPEC lists it as a non-goal, and nothing is unresolved. Before review, a spec-validator pass
raised 8 critiques, and all of them were folded into the SPEC (see its Refinement Decisions). The
cross-model second opinion is not configured for this harness. No `Do not change` path was
crossed.

The fixes changed the AC-004 literal. The SPEC was amended in place and approved again. Two more
pins of SPEC-hm-cost-p3 moved with the Step 3 and Step 4.6 text, and the SPEC's C5 decision
records them. Trimming the text kept AC-007 within its 5 × rule-delta allowance. The command
surface grew by 714 chars (claude) and 711 chars (codex). PLAN `surface_allowance` and
BASELINE-DELTA carry the measured numbers.

## Findings

| id | severity | file:line | finding | disposition | authority |
|---|---|---|---|---|---|
| F1 | major | src/harness_maker/templates/stages/spec.md.j2 (Step 4.6) | Step 4.6 still said "an irreversible-decision or oracle critique is never a default". This contradicted SPEC C5, which fixes an oracle critique as a default and sends it to Open Questions only when no independent oracle exists. Fix: the sentence now separates the two cases; the pin `tests/unit/test_hm_cost_p3_templates.py:38` moved | accepted | SPEC Refinement Decisions C5 |
| F2 | major | src/harness_maker/templates/skills/intent-layer/SKILL.md.j2:11 | "**Read freely, write only on an answer.**" contradicted the unasked records of IRR-001. Fix: "Read freely; write per the rule below." | accepted | SPEC IRR-001 |
| F3 | major | src/harness_maker/templates/stages/spec.md.j2 (Step 2) | "Show that list with the approval question" had no antecedent in Step 2. Fix: "Show your Refinement Decisions with the approval question". The AC-004 literal, its predicate and its test were amended, and the SPEC was approved again | accepted | SPEC AC-004, O4 |
| F4 | minor | src/harness_maker/templates/stages/wrapup.md.j2 (Step 5) | The intent block's "approved SPEC" did not say where Step 5 reads that state, because `approval-status` first runs in Step 6. Fix: the block names `approval-status` | accepted | SPEC AC-005 |
| F5 | minor | src/harness_maker/templates/skills/intent-layer/SKILL.md.j2 (rule item 3) | "outside a task" is not a term IRR-001 uses. Fix: "any write without an approved SPEC", which is IRR-001's own boundary and covers both the exempt and the no-task cases | accepted | SPEC IRR-001 |
| F6 | minor | tests/render/test_ask_less.py (AC-005) | The AC-005 test pinned fragments and not the full record forms, and it did not check that the records come before "Anything else". Fix: the four full forms are pinned and each must precede the asked clause | accepted | SPEC AC-005 |
| F7 | nit | specs/SPEC-choice-cards.md | SPEC-choice-cards did not say that its rule text was superseded. Fix: a note points to SPEC-ask-less rule R | accepted | SPEC Constraints (Superseded pins) |
| F8 | nit | src/harness_maker/templates/skills/intent-layer/SKILL.md.j2 | The "wrapup Step 5.7" pointer is stale | rejected | SPEC Non-Goals: "The stale "wrapup Step 5.7" pointer in the intent-layer skill is not fixed here." |

Also found by the gate rather than the reviewer: `tests/unit/test_intent_file_inputs.py::test_recipes_carry_no_inline_text`
(SPEC-intent-file-inputs) needs each wrapup intent call on its own line with its `-file` flags.
The one-line rewrite had dropped them. Each record is now its own bullet with `--claim-file` /
`--text-file`, and the asked example is `hm intent close <id> … --note-file <f>`. The kept-list
pins and the AC-005 literals follow the full `hm intent question …` forms. The surface allowance
was re-measured on top of SPEC-wrapup-gate: 800 chars on claude and 797 on codex. The gate also
caught `tests/unit/test_schema_migration.py:143`, which pinned the removed "(closed ones are
unlimited)"; it now pins "at most 3 questions per round". The full suite also caught
`test_world_intent_feedback.py` (the reference keeps "If consent is pending or declined, write
nothing and mark the update pending or declined") and `test_hm_cost_p5_templates.py:76`, which
now allows the measured +34 chars of the spec stage.
