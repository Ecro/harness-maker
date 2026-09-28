---
type: plan
task_slug: intent-file-inputs
status: complete
created: 2026-09-28
tags: [harness-maker, plan, python, intent-layer, cli, injection]
spec: "[[SPEC-intent-file-inputs]]"
interview_rounds: 0
adrs: 4
validator_outcome: NOT_RUN
summary: "File twins for hm intent free-text args; recipes write a mktemp file and pass the path"
spec_need_verdict: add
spec_need_target: intent-file-inputs
---
# PLAN — intent-file-inputs

## 🎯 Executive Summary

Add a `--<name>-file` twin for every free-text argument of the `hm intent` write verbs (nine
twins, IRR-001), resolve them before any write, and switch the three rendered surfaces (wrapup
Step 5.7, spec Step 4.9, the intent-layer skill) from inline text to "write the text with the
Write tool to a `mktemp` path outside the repo, pass the path". Closes the accepted residual P1
`58ef46c950a7b459` from `REVIEW-sdlc-three-loops-gap`. Decisions: SPEC Rounds 1–3 (DRI).

## 📚 Prior Work

- `memory_md upsert-wiki --body-file` — the precedent (`_read_body`, `memory_md.py:798`).
- `REVIEW-sdlc-three-loops-gap-2026-09-27.md` — three review runs each found the next quoting
  site; the structural fix is to take text off the command line.
- Wiki `memory-package-post-tier-removal`: `workflow-feedback.md.j2` is hash-bound trial evidence.
- Failures: `mypy-strict-local-scope-narrower-than-ci` (run `mypy --strict src tests`),
  `test-pins-historical-commit-snapshot`, `hash-bound-evidence-edit-caught-by-suite`.
- `BASELINE-DELTA-verify-delegation.md` — the re-freeze pattern this PLAN reuses (Phase 4).

## 📐 Architecture Decision Records

### ADR-001: Pair each inline flag with its file twin in an argparse mutually exclusive group
**Decided by:** agent
The group gives both-forms and neither-form refusals (`required=True` for required arguments)
with argparse's own message naming both flags, and needs no hand-written cardinality code.

### ADR-002: One resolver, run before dispatch, reads every file twin and replaces the inline attribute
**Decided by:** agent
`intent.resolve_file_args(parser, args)` runs in `intent_cli.main` right after `parse_args`, so
every refusal (missing, non-UTF-8, empty, zero items) happens before any write, and handlers
keep reading `args.claim` etc. unchanged. Errors go through `parser.error("argument --x-file: …")`
(exit 2, argument named).

### ADR-003: Single-value and multi-item semantics are two helpers, not one
**Decided by:** user (source: SPEC Round 2)
Single values: UTF-8 content with trailing `\n` removed, empty refused. Multi-item: one item per
non-empty stripped line, zero items refused. Inline values are never normalised by the resolver.

### ADR-004: Re-freeze the surface baseline in a terminal phase instead of declaring an allowance
**Decided by:** agent
An allowance expires when wrapup marks the PLAN complete and leaves main red by its delta; the
terminal re-freeze with a `BASELINE-DELTA-intent-file-inputs.md` attribution is the pattern the
last re-freeze (`verify-delegation`) used and the one the attribution test reads.

## 🏗️ Technical Design

- `src/harness_maker/intent.py`: parser gains nine twins in exclusive groups; new
  `resolve_file_args` + two private readers.
- `src/harness_maker/intent_cli.py`: keep the parser object, call the resolver after parsing.
- Templates: `stages/wrapup.md.j2` Step 5.7 (observe/add/close, both branches),
  `stages/spec.md.j2` Step 4.9 (`new`), `skills/intent-layer/SKILL.md.j2` (synopsis, write rule
  line, proposal-path `new`).
- Tests: `tests/unit/test_intent_file_inputs.py` (new); render tests that pin old recipe text
  updated; snapshots; autopilot golden; `surface_baseline.json` + delta doc.

## 📝 Implementation Plan

### Phase 1 — CLI file twins and resolver
- depends_on: none
- parallel_group: A
- merge_hazards: none
- scope in: `src/harness_maker/intent.py`, `src/harness_maker/intent_cli.py`, `tests/unit/test_intent_file_inputs.py` (AC-001..004, AC-007)
- scope out: `world.py` (storage unchanged)
- exit: `uv run pytest tests/unit/test_intent_file_inputs.py tests/unit/test_intent_doc_new.py tests/unit/test_intent_doc_record.py tests/unit/test_intent_vocabulary.py` green; `mypy --strict src tests` clean
- risk: medium
- rollback: `git checkout -- src/harness_maker/intent.py src/harness_maker/intent_cli.py`
- status: DONE (A.4 19 failed / 1 justified pass; A.5 PASS round 1)

### Phase 2 — Rendered recipes carry paths
- depends_on: Phase 1
- parallel_group: B
- merge_hazards: snapshots, autopilot golden, render tests shared with other tasks
- scope in: the three templates, `templates/skills/project-knowledge/SKILL.md.j2` (its Route-first sentence described the inline form), `tests/unit/test_intent_file_inputs.py` (AC-005), render tests pinning old text, `tests/snapshot/*.expected.yaml`, `tests/structural/autopilot_gate_golden.json` + its dated docstring entry, `tests/structural/test_instruction_preservation.py` allowlist if a `!` line changed
- scope out: `workflow-feedback.md.j2`
- exit: `uv run pytest tests/unit/test_intent_file_inputs.py tests/render tests/unit/test_render_intent_layer.py tests/unit/test_render_intent_layer_assume_add.py tests/unit/test_intent_vocabulary.py tests/snapshot tests/structural/test_autopilot_gate_render.py tests/structural/test_instruction_preservation.py` green
- risk: medium
- rollback: `git checkout -- src/harness_maker/templates tests`
- status: DONE (render pins updated in test_render_intent_layer, test_render_intent_layer_assume_add, test_memory_tier_removed; golden re-captured: spec + wrapup, all four arms)

### Phase 3 — Surface baseline re-freeze (terminal)
- depends_on: Phase 2
- parallel_group: C
- merge_hazards: `surface_baseline.json` is shared; rebase onto main before re-freezing
- scope in: `tests/structural/surface_baseline.json`, `work-docs/BASELINE-DELTA-intent-file-inputs.md`, round-trip tables if they move
- scope out: templates
- exit: `uv run pytest tests/structural` green
- risk: medium
- rollback: `git checkout -- tests/structural`
- status: DONE (aggregate +297 claude / +297 codex, round trips unchanged; BASELINE-DELTA-intent-file-inputs.md)

### Phase 4 — CHANGELOG
- depends_on: Phase 2
- parallel_group: C
- merge_hazards: CHANGELOG shared (rebase-merge by hand at land)
- scope in: `CHANGELOG.md`
- exit: `[Unreleased]` names the nine twins and their value semantics
- risk: low
- rollback: `git checkout -- CHANGELOG.md`
- status: DONE

## 🚧 Contract Boundaries

### Do not change
- `src/harness_maker/templates/skills/intent-layer/references/workflow-feedback.md.j2` — hash-bound WORLD-INTENT-CLOSED-LOOP evidence
- `src/harness_maker/world.py` — storage and validation stay as they are
- `tests/unit/test_intent_doc_new.py` — AC-006 CLI behaviour oracle
- `tests/unit/test_intent_doc_record.py` — AC-006 CLI behaviour oracle
- `tests/unit/test_intent_vocabulary.py` — AC-006 CLI behaviour oracle
- Advisory: inline flags keep their current behaviour exactly; the resolver never touches an inline value

## 🧪 Testing Strategy

- Unit: `tests/unit/test_intent_file_inputs.py` — Hypothesis property (AC-001), golden cases
  (AC-002, AC-004, AC-007), parametric refusals from the machine SPEC golden table (AC-003),
  render check over Claude + Codex (AC-005).
- Existing CLI behaviour tests untouched (AC-006).
- `mypy --strict src tests`, ruff, full suite once in the background.

## ⚠️ Risks & Mitigation

| Risk | Likelihood | Mitigation |
|---|---|---|
| intent-layer SKILL exceeds 120 newlines | high | edit lines in place; the existing cap test enforces |
| A pinned render test breaks | high | update render pins (allowed by AC-006), never CLI behaviour tests |
| Surface baseline races another session | medium | rebase onto main right before Phase 3 |
| Dogfood recipes fail before release | certain | documented; the rendered harness pins 0.60.4 |

## ✅ Success Criteria

- [x] AC-001 file value equals the original for every single-valued argument
- [x] AC-002 metacharacters stored verbatim
- [x] AC-003 refusals exit non-zero, name the argument, change nothing
- [x] AC-004 multi-item files for scope, out-of-scope, declined
- [x] AC-005 recipes carry paths, call-site set present, Write-tool mktemp instruction
- [x] AC-006 CLI behaviour tests unchanged and green
- [x] AC-007 mixed forms in one call

## Feedback

| Evidence | Affected ID | Update status | Decision | Owner | Authority | Next action |
|---|---|---|---|---|---|---|
| REVIEW-sdlc-three-loops-gap residual P1 58ef46c950a7b459 | none (no intent) | unchanged | Structural fix via file twins | user | SPEC approval 2026-09-27T23:18:40Z | Execute Phases 1-4 |
| REVIEW-intent-file-inputs-2026-09-28 (grade A, confirm-1 clean) | none (no intent) | unchanged | Residual P1 closed; 2 P2 carried (test rename, path scoping) | agent | review run f8dec5471aad | /hm:verify, then wrapup |
| /hm:verify PASS 6/6 (9375 passed; stray empty /tmp/.git removed after a first environmental FAIL) | none (no intent) | unchanged | Ready to land | agent | verify 2026-09-28 | /hm:wrapup |
| wrapup 5.7: q_825d374c6331ed22 observed (confirms) via the new --text-file; metric measure --all 2026-09-28T04:05Z — wiki_fact_entries_28d failed (window open until 2026-10-17) | none (no intent) | measured | Land and push | user | wrapup answers 2026-09-28 | none |
