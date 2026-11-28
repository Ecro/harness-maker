---
type: spec
task_slug: intent-model-progress-rule
status: approved
created: 2026-11-28
tags: [harness-maker, spec, docs, intent]
test_framework: pytest
interview_rounds: 0
summary: "Record the DRI's design rule — hm keeps only what the model does not and will not do, and stays lean — as an intent.yaml rule and in CLAUDE.md's first goal."
---

# SPEC — intent-model-progress-rule

## Intent

The DRI stated the design rule on 2026-11-27/28: as models improve, hm should lightly add only
what the model does not do now and will not do later (the seven hm-only functions), and remove
or move to the CLI what the model already does. The DRI asked to put it into the intent.

## Outcomes

- O1. `.claude/intent.yaml` `rules` carries the rule, naming the seven functions.
- O2. CLAUDE.md's first-goal block carries the same rule, because no stage or CLI reads
  `intent.yaml` `rules` at session time (`IntentFile.rules` has no caller), while CLAUDE.md is
  loaded every turn.

## In-Scope Scenarios

- **S1 (normal).** Given the repo, When `hm intent status --json` runs, Then `state` is `ok` and
  the rule is the second `rules` entry.

## Non-Goals

- No change to the intent layer's code, skill or stage text (analysed separately in this thread).
- No edit of other rules, purpose, metrics or open questions.

## Irreversible Decisions

None. Documentation only.

## Acceptance Criteria

None (non-code change; Step 0 allows `ac: []`).

## Verification

| Scenario | Mode | Check |
|---|---|---|
| S1 | manual | `hm intent status --json` → `state: ok` |

## Open Questions

None.

## Refinement Decisions

- Skip check: two docs, acceptance obvious, no API or format change, reversible in minutes.
- Also added to CLAUDE.md (agent choice): an `intent.yaml` rule alone would not reach any session.
