---
type: review
task_slug: retire-autopilot-remnants
status: APPROVED
created: 2026-10-17
spec: "[[SPEC-retire-autopilot-remnants]]"
plan: "[[PLAN-retire-autopilot-remnants]]"
rounds: 2
summary: "Two review rounds (code-reviewer, plus codex second opinion in round 1, which found nothing). 4 of 6 round-1 findings accepted and fixed; round 2 found none. hm check exit 0."
---

# REVIEW — retire-autopilot-remnants (2026-10-17)

## Voters

- Round 1: `code-reviewer` raised 6 findings. The `codex` second opinion was invoked and returned 0
  findings. Each finding therefore had a single voter, so `code-verifier` decided its disposition.
- Round 2: `code-reviewer` checked the fixes and found nothing new. Codex was not called again
  (the vote is frozen at one call per model per review).
- `hm check` raised G1–G4 below. It ran three times: run 1 exit 1, run 2 exit 1, run 3 exit 0.

## RED

`hm check --red` exited 0. AC-003 was red: an all-retired pipeline parsed to `[]`. AC-001, AC-002,
AC-004 and AC-005 were waived as `--green-ok`, because the implementation was written before the
SPEC. All four were confirmed to fail against HEAD source in a scratch worktree (5 failed).

## Findings

| id | severity | file:line | finding | disposition | authority |
|---|---|---|---|---|---|
| F1 | P2 | src/harness_maker/hooks/autopilot_autoarm.py:80 | The shared `drop_retired_stages` makes the autoarm hook arm `[]` for a `[review, verify]` pipeline | rejected | autopilot_autoarm.py:189-190: the `__main__` entry is the exit-0 `_retired_entry` stub (hm.py:110 runpy reaches the same stub), so only tests can call `arm_if_persistent`; SPEC-hm-overhaul-p1 IRR-005 |
| F2 | P2 | tests/unit/test_autopilot_unlimited_caps.py:31 | Three retired-autopilot tests still build their pipeline from the four-stage default; unlimited_caps no longer walks the review/verify transitions | accepted | SPEC Constraints, row "Retired autopilot library tests…"; fixed in unlimited_caps, ask_resolution and level_matrix |
| F3 | P3 | tests/structural/test_repo_output_language.py:16 | AGENTS.md is gitignored, so the AC-004 wording ("both root files") claims more than CI checks | accepted | .gitignore:91; AC-004 reworded, a direct CLAUDE.md assertion added, DRI re-approved |
| F4 | P3 | tests/structural/test_repo_output_language.py:13 | The test called the private `_dim_workflow_clarity`, but the predicate names `compute_readiness` | accepted | machine.yaml AC-004 predicate; the test now uses `compute_readiness(_REPO, Preset.PRODUCTION)` |
| F5 | P3 | CHANGELOG.md:5 | The entry leaves out the all-retired fallback and the silent CLI drop | accepted | SPEC Outcomes 3 and Non-Goals; both lines added |
| F6 | P3 | tests/unit/test_autonomy_config.py:39 | The ordering assertion was loosened | rejected | Not a defect: test_autonomy_config.py:79-80 still pins the exact default order |
| G1 | P2 | tests/unit/test_overhaul_p1_surface.py:573 | The "no auto-advance" row matched `autopilot` inside the rendered `uv run --with <worktree path>`, because this slug contains the word | accepted | Reproduced: the only hit was the install path. The row now strips `_INSTALL_REF` first, and round 2 confirmed this does not weaken it |
| G2 | P2 | tests/render/test_retired_text.py:121,251 | The same path false-positive in the retired-text AC-001 and AC-004 | accepted | Reproduced: every hit was the checkout path. The test now removes `HEAD_SRC.parent` before matching |
| G3 | P3 | tests/structural/test_repo_output_language.py | A new structural gate had no mutation receipt | accepted | test_new_gates_file_a_mutation_receipt.py. Deleting CLAUDE.md:297 made the gate fail (1 failed), the line was restored, and the receipt row was filed at the base ledger |
| G4 | P3 | tests/unit/test_readiness_autoarm_hook.py | An unstaged deletion left the file in `git ls-files`, so test_no_dead_string_pins hit FileNotFoundError | accepted | Deletion staged (`git rm --cached`) |

## Contract boundaries

There is no crossing. `autopilot.py` changes only in comments. `hooks/autopilot_autoarm.py`,
`inert_keys.py`, `render.py` and the `AtomicStage` members are unchanged.

## Notes for wrapup

- The base checkout has one uncommitted row in `.claude/observability/mutation-receipts.jsonl`
  (G3). Past tasks filed these as a separate `chore(observability)` commit on base.
- The spec gate (PreToolUse) inspects Edit/Write only. Before this SPEC existed, the drafted test
  edits went through shell writes and so never met the gate. This is recorded in SPEC Refinement
  Decisions.
