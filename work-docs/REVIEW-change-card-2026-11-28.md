---
type: review
task_slug: change-card
created: 2026-11-28
rounds: 2
---

# REVIEW — change-card

Reviewer: code-reviewer subagent, 2 rounds (round 1 on the first diff, round 2 on the fixes).
A saga bench run between the rounds (hm x3, v1 prose) found one more defect: the model piped
`wrapup_land`'s one-line JSON receipt through `cut -c1-600` and lost the card, and it
paraphrased the spec card instead of printing it. Fixed as F10.

## Findings

| id | severity | file:line | finding | disposition | authority |
|---|---|---|---|---|---|
| F1 | P1 | src/harness_maker/change_card.py (land review branch) | a REVIEW with a missing disposition or no Findings section read as verified | accepted | - |
| F2 | P1 | src/harness_maker/change_card.py (`_record`) | a record from before a later code edit was trusted as verified | accepted | - |
| F3 | P1 | src/harness_maker/templates/stages/spec.md.j2 (Step 2) | the order of writing the SPEC vs showing the card was ambiguous | accepted | - |
| F4 | P2 | src/harness_maker/change_card.py (`_record`) | a record whose overall verdict failed read as "no record" | accepted | - |
| F5 | P2 | tests/unit/test_change_card.py (AC-003) | near-vacuous "3" assertion; stale, foreign, failed, open-review cases untested | accepted | - |
| F6 | P3 | src/harness_maker/change_card.py (`_example_lines`, trim) | two examples instead of one; dropped AC titles had no marker | accepted | - |
| F7 | P3 | scripts/saga_bench.py (`owner_summary`) | `spec_per_ship` read 0 for rows that predate `doc_chars` | accepted | - |
| F8 | P3 | src/harness_maker/templates/stages/wrapup.md.j2 (Step 8) | "null" did not cover an absent key | accepted | - |
| F9 | P3 | src/harness_maker/change_card.py (`_manual_rows`) | any "manual" token in a Verification row matched, not the Mode column | accepted | - |
| F10 | P1 | src/harness_maker/wrapup_land.py, wrapup.md.j2, spec.md.j2 | bench: card lost to a truncated receipt and paraphrased at approval; now written to `.claude/observability/change-card-<slug>.txt` and both stages say print verbatim, no other summary | accepted | - |
| R2-1 | P2 | tests/unit/test_change_card.py (AC-005) | the stale-card unlink was untested (fresh base) | accepted | - |
| R2-2 | P2 | src/harness_maker/templates/stages/wrapup.md.j2 (Step 8) | fallback condition named the receipt key, not the file the step Reads | accepted | - |
| R2-3 | P3 | src/harness_maker/change_card.py (`card_path`) | is `.claude/observability/` gitignored in rendered harnesses? Yes: `cli._ensure_harness_gitignore` seeds it at make | rejected | src/harness_maker/cli.py:614 (`_ensure_harness_gitignore`) |
| R2-4 | P3 | src/harness_maker/change_card.py (`_record`) | whole-repo snapshot in the land path; now hashes code and test paths only | accepted | - |
| R2-5 | P3 | src/harness_maker/templates/stages/spec.md.j2 (Step 2) | validator edits after the card was shown; now "rerun ... the validator's too, before `--approve`" | accepted | - |
