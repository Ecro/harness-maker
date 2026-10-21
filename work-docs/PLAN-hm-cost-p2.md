---
type: plan
task_slug: hm-cost-p2
status: complete
created: 2026-10-21
spec: "[[SPEC-hm-cost-p2]]"
surface_allowance:
  chars: 281
  reason: "SPEC-hm-cost-p2: execute gains the short-PLAN rule, the edit-in-place rule, export-golden parametric tests and the verbatim IRR categories and the stdlib property fallback (+226); wrapup adds --optional specs/SPEC-<slug>.golden.json (+41); spec nets about 0 after trims. Pinned wording elsewhere left no further cuts (DRI decision 2026-10-21). Aggregate +262 claude, +280 codex, inside the approved 263/281."
  delta_doc: BASELINE-DELTA-hm-cost-p2.md
  commands:
    execute: 70
    hm-execute: 70
summary: Golden rows via exported JSON (no harness_maker import in user tests), approval folded into spec_machine check, compact hm check output, exact IRR categories, edit-in-place and short PLAN in the stage templates, then a tier-1 re-measure against the 12.5x bar.
---

# PLAN — hm-cost-p2

1. **P1 spec_machine** — scope: `golden_json_path`/`golden_export` helpers, `export-golden` verb, command registry, `approval` field in `spec_machine check` (AC-001, AC-005 CLI half) · exit: `uv run pytest tests/unit/test_hm_cost_p2_spec_machine.py` · risk: low · rollback: revert spec_machine.py and command_registry.py.
2. **P2 check** — scope: golden comparison in `ac_section` and `red_section`, keep-set compaction with `--full` (AC-002, AC-006) · exit: `uv run pytest tests/unit/test_hm_cost_p2_check.py` · risk: medium (CLI output contract) · rollback: revert check.py.
3. **P3 templates and land** — scope: spec/execute/wrapup stage templates, `wrapup_land.derive_deliverable_globs`, re-captured snapshots and surface baseline (AC-003, AC-004, AC-005 template half, AC-007, AC-008, AC-010) · exit: `uv run pytest tests/unit/test_hm_cost_p2_templates.py tests/structural tests/render` · risk: medium (instruction preservation, goldens) · rollback: revert templates and snapshots.
4. **P4 re-measure** — scope: tier-1 bench on a clean committed tree, rows replace `docs/evals/results.jsonl`, `RESULTS.md` re-published, `tests/fixtures/hm_cost_p2/harness_shas.json` (AC-009) · exit: `uv run pytest tests/integration/test_hm_cost_p2_bar.py tests/integration/test_overhaul_p1_ship_bar.py` · risk: medium (live model, needs a commit on `hm/hm-cost-p2`) · rollback: restore results.jsonl and RESULTS.md from HEAD.

## 🚧 Contract Boundaries

### Do not change
- `scripts/bench_light_lane.py` — the measuring instrument stays fixed across the 2026-10-21 baseline and the re-measure.
- `src/harness_maker/worktree.py`
- `docs/reference/multi-session-worktree.md`
- `tests/integration/test_overhaul_p1_ship_bar.py`

## ADRs

ADR-001: The golden export, its path and the drift comparison live in `spec_machine` (`golden_json_path`, `golden_export`); `check.py` and the verb both call them, so the projection has one definition. **Decided by:** agent
ADR-002: Compaction happens in `check.run` behind `Options.full` (default `True` for programmatic callers; the CLI passes `full=args.full`), because only `run` sees each section's exit code. **Decided by:** agent
ADR-003: A passing section keeps a keep-set key only when its value is non-empty, so `waived: []` and `green_before: []` do not survive compaction; the test helper applies the same rule. **Decided by:** agent
ADR-004: `spec_machine check` computes `approval` with `approval_state_of` on the `--yaml`/`--md` it was given and the slug from the file name, not from a guessed root: a cwd default reported `no_spec` for any SPEC outside cwd (found in Phase C). **Decided by:** agent
ADR-006: The 263/281-char surface growth is held as this PLAN's `surface_allowance`, the AC-004 execute/wrapup budgets rise to 7 250/3 850, and the baseline is re-frozen from main after land. **Decided by:** user (AskUserQuestion, 2026-10-21)
ADR-007: Tests that read a passing `hm check` section's detail migrate to `--full` (eval3 replay); tests pinning `spec_machine check` bytes strip the additive `approval` key; overhaul AC-009's tables list `export-golden` and the dropped spec `approval-status`. **Decided by:** agent (IRR-002/IRR-003 of the SPEC)
ADR-008: The first P4 run (harness 60e5502a8641, archive `~/hm-eval-archive/hm-eval-t1-p2-2026-10-21.tgz`) missed AC-009 as pre-registered: transcript ratio 11.14 passed, but hm passed 12/15 against plain 15/15. All three misses stopped in execute after recording Hypothesis as an `IRR new external dependency` for a property AC, and the bench gives no DRI turn after execute, so no code was written. The execute template now asks for a seeded stdlib `random` loop when the project lacks Hypothesis and forbids adding it. AC-009 is judged on the re-run alone; the missed run stays archived and is cited in the REVIEW. **Decided by:** user (AskUserQuestion, 2026-10-21)
ADR-005: P4's bench needs a clean committed tree; the commit on `hm/hm-cost-p2` is a WIP the wrapup squash replaces, and making it is the DRI's call because execute never commits. **Decided by:** agent (asks the DRI at P4)
