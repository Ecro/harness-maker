---
type: review
task_slug: review-measurement-fixes
created: 2026-11-21
spec: "[[SPEC-review-measurement-fixes]]"
plan: "[[PLAN-review-measurement-fixes]]"
rounds: 2
summary: Round 1 raised 2 P1 and 3 P2, all accepted and fixed; round 2 found none. Codex second opinion skipped (CLI not installed).
---

# REVIEW — review-measurement-fixes

Reviewer: `code-reviewer`, 2 rounds. Second opinion: `codex` skipped (`CLI not installed: codex`), warn-and-proceed.

## Findings

| id | severity | file:line | finding | disposition | authority |
|---|---|---|---|---|---|
| R1-F1 | P1 | src/harness_maker/templates/stages/execute.md.j2:81 | Reviewer `pre-existing:` prefix not tied to the disposition; a P0/P1 pre-existing row was invisible. Resolution: clause names the prefix; final print lists every P0/P1 `pre-existing` row | accepted | code-reviewer |
| R1-F2 | P1 | src/harness_maker/templates/stages/execute.md.j2:78 | Second-opinion findings could not be `pre-existing` (verifier vocabulary is fixed). Resolution: execute assigns it for any voter's finding, after any verifier verdict | accepted | code-reviewer |
| R1-F3 | P2 | docs/HOW-IT-WORKS.md:190 | Docs (en + ko) listed four dispositions. Resolution: `pre-existing` added to both | accepted | code-reviewer |
| R1-F4 | P2 | src/harness_maker/templates/agents/code-reviewer_body.md.j2:24 | Reviewer scale P0–P2 vs execute's P0–P3. Resolution: `P3: a nit` added; sha re-pinned, snapshots regenerated | accepted | code-reviewer |
| G-F1 | P1 | src/harness_maker/templates/agents/code-reviewer_body.md.j2:24 | The R1-F4 fix rendered `P3` under `reviewers.verbosity: terse`, breaking `test_terse_verbosity_drops_p2_p3_and_reasoning` (found by the post-review `hm check`). Resolution: `P3: a nit` renders only when verbosity is not terse | accepted | hm check |
| R1-F5 | P2 | specs/SPEC-two-pass-review.md:1 | Historical SPEC pointed at the deleted module. Resolution: retirement note after frontmatter | accepted | code-reviewer |

## Gate history

`hm check` at Bind exited 1 three times in a row on render byte pins (agent sha, ask-less ratchet, synthesize snapshot); per the new cap the third went to the DRI, who chose regenerate + a full non-`-x` run. Then exit 0.
