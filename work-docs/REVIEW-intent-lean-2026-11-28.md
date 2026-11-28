---
type: review
task_slug: intent-lean
status: APPROVED
created: 2026-11-28
reviewers_invoked: [code-reviewer]
---

# REVIEW — SPEC-intent-lean

One review round over `git diff 593a6ac5` in the `hm/intent-lean` worktree (about 99 files, mostly
deletions). The reviewer ran the SPEC's own tests, the ported question, vocabulary, measure and
digest tests, and probed IRR-002 by hand: a legacy `proposed` record carrying `approval`,
`revisit_when`, `rejected` and `depends_on`, with a CRLF body, kept every key and its body bytes
through `close`. Every finding was fixed in the same round.

## Findings

| id | severity | file:line | finding | disposition | authority |
|----|----------|-----------|---------|-------------|-----------|
| R1 | P1 | src/harness_maker/templates/skills/project-knowledge/SKILL.md.j2:29 | The rendered recipe still passed the removed `--locator` to `hm intent question`, which fails with exit 2 | accepted | SPEC IRR-001 removes `--locator`. This is a carve-out from the Non-Goal "no change to project-knowledge": the citation now rides in `--text-file`, and the test_memory_tier_removed pin is updated to match |
| R2 | P2 | src/harness_maker/templates/stages/wrapup.md.j2:44 | `metric record` was offered unasked for every open goal, which invites an invented value | accepted | SPEC S2 says "a task whose wrapup measured its metric". The text now reads "if this task measured it" |
| R3 | P2 | tests/unit/test_intent_vocabulary.py:135 | The canonical-load assertion was loosened from full `asdict` equality | accepted | SPEC AC-011 says kept-behaviour assertions stay unchanged. The full equality is restored |
| R4 | P2 | tests/unit/test_intent_lean.py:461 | AC-001 measured only the body; the rendered file was 4,071–4,093 characters | accepted | SPEC AC-001 says "rendered SKILL.md ≤ 4,000". The test now measures the whole file, and the skill was trimmed to 3,953 (Claude) and 3,975 (Codex) characters |
| R5 | P3 | src/harness_maker/intent_cli.py:943 | `approve --json X` gave a generic argparse error, not the replacement message | accepted | SPEC AC-002. `main` uses `parse_known_args`, so a removed verb always names its replacement and exits 2 |
| R6 | P3 | tests/unit/test_intent_lean.py:180 | No test covered the `hm` front door without a leading `--root` | accepted | Added `test_ac_002_removed_verb_through_hm_without_root` |
| R7 | P3 | tests/unit/test_intent_lean.py:240 | `show` was not checked for `observed`, and the byte check skipped `question observe` | accepted | SPEC AC-003. Both are added |
| R8 | P3 | tests/unit/test_intent_lean.py:509 | AC-009 proved the gate was gone only by the absence of one name | accepted | Added `"objective_gate" not in get_args(HaltKind)` |
| R9 | P3 | src/harness_maker/templates/skills/project-knowledge/SKILL.md.j2:14 | "under its consent rule" no longer matched the intent-layer skill | accepted | Changed to "written by it" |
| R10 | P3 | README.md:497 | README described unreleased behaviour | accepted | `.claude/intent.yaml` rule: README matches the latest release. The README edit is reverted, and CHANGELOG [Unreleased] notes that it lands in the release PR |

## Coverage of removed behaviour

The superseded ACs are 52 old SPEC ACs, marked `superseded_by: intent-lean` with
`hm spec_machine retire`. Each one asserted behaviour this SPEC removes:

- approval state machine
- proposal path
- revisit/withdrawal/evidence-locator engine
- objective gate
- spec Step 0.5
- workflow-feedback reference

For ACs whose behaviour is kept, only the dead test ids were dropped:

- objective-layer AC-001, AC-002 and AC-019
- intent-file-inputs AC-006
- hm-light-lane-s3a AC-005

The reviewer confirmed two things:

- No live AC points at a deleted test.
- The kept question writers (add, refusals, concurrency, observe and resolve) have ported tests in `tests/unit/test_intent_questions.py`.
