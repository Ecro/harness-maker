# objective_scope_drift — AC-017 judgment INPUTS

Four (PLAN, objective) pairs the judgment-reviewer runs the CURRENT rendered `/hm:review`
Step 3.3 lens over at judgment time (both targets: `.claude/commands/hm/review.md` and
`.agents/skills/hm-review/SKILL.md`). Inputs only — no recorded output lives here, so a
stored good answer cannot carry a pass (SPEC AC-017, PLAN ADR-004).

| case | expected `scope_drift` finding |
|---|---|
| `in_scope` | none |
| `outside_scope_not_named` | one — the telemetry upload is outside `scope` and `non_scope` does not name it |
| `inside_non_scope` | one — the renderer rewrite is inside `non_scope` |
| `hypothesis_subject_omitted` | one — the hypothesis's subject (interview length) is absent from the PLAN |
