---
type: plan
task_slug: hm-cost-p3
status: complete
created: 2026-10-21
spec: "[[SPEC-hm-cost-p3]]"
surface_allowance:
  chars: 690
  reason: "SPEC-hm-cost-p3: spec gains the defaults rule and the Open Questions limit (+315), execute the batching rule and the unconditional post-REVIEW check (+317), wrapup the --reuse call (+58), after trimming the new wording and adding review round 1's fixes. Agent-decided under the DRI's autopilot instruction (2026-10-21); folded on main after land."
  delta_doc: BASELINE-DELTA-hm-cost-p3.md
  commands:
    spec: 230
    hm-spec: 230
    execute: 150
    hm-execute: 150
    wrapup: 5
    hm-wrapup: 5
summary: hm check --reuse with a git-dir verdict record, spec defaults instead of Open Questions, execute's REVIEW-then-check order and batching rule, p2 rows moved to docs/evals/history, then a tier-1 re-measure against 10.0x.
---

# PLAN — hm-cost-p3

1. **P1 reuse** — scope: `check.verdict_path`, record write after a fresh exit-0 run, `run(opts, reuse=True)` and `--reuse` (AC-002) · exit: `uv run pytest tests/unit/test_hm_cost_p3_reuse.py` · risk: medium (CLI contract, stale pass) · rollback: revert check.py.
2. **P2 templates** — scope: spec Step 4.6 and Open Questions rule, execute Step 6 order and batching rule, wrapup Step 1 `--reuse`; snapshots and surface allowance (AC-001, AC-003, AC-004) · exit: `uv run pytest tests/unit/test_hm_cost_p3_templates.py tests/structural tests/snapshot tests/render tests/unit/test_overhaul_p1_surface.py` · risk: medium (pinned wording, budgets) · rollback: revert templates and snapshots.
3. **P3 history** — scope: `docs/evals/history/hm-cost-p2.jsonl` from 022d6f2a, p2 bar test reads it and takes the bar as an argument (AC-006) · exit: `uv run pytest tests/integration/test_hm_cost_p3_bar.py::test_ac_006_p2_history tests/integration/test_hm_cost_p2_bar.py` · risk: low · rollback: revert the two test files and the history file.
4. **P4 re-measure** — scope: tier-1 bench with `--jobs 4` on the final committed code after review fixes, rows replace `docs/evals/results.jsonl`, `publish`, `tests/fixtures/hm_cost_p3/harness_shas.json` (AC-005) · exit: `uv run pytest tests/integration/test_hm_cost_p3_bar.py tests/integration/test_overhaul_p1_ship_bar.py` · risk: medium (live model) · rollback: restore results.jsonl and RESULTS.md from HEAD.

## 🚧 Contract Boundaries

### Do not change
- `scripts/bench_light_lane.py` — the measuring instrument stays fixed across baseline and re-measure.
- `src/harness_maker/worktree.py`
- `docs/reference/multi-session-worktree.md`
- `tests/integration/test_overhaul_p1_ship_bar.py`

## ADRs

ADR-001: Reuse lives in `check.run(opts, *, reuse=False)`, not in `Options`, so the compared options stay "every `Options` field except `root`" with no reuse field to exclude. **Decided by:** agent
ADR-002: The fingerprint hashes HEAD's commit id, the gate command list (with its degraded reason) and the pre-run `snapshot`; the record is written only when the run exits 0, from that pre-run fingerprint (an exit-0 run has no `tree_changed`). **Decided by:** agent
ADR-003: A record write failure prints one `hm check: verdict not recorded (...)` line on stderr and never changes the exit or stdout. **Decided by:** agent
ADR-004: SPEC AC-002's `written_by_failed_run` row keeps its gate failing, so the expected exit is 1; the row's oracle_evidence wording ("the gate is then fixed") contradicts the table's exit 1, and the table is the oracle. Recorded for the reviewer; the approved SPEC is not edited, since that would void the DRI's stamp. **Decided by:** agent
ADR-005: p3's bar test reuses p2's `bar_violations` and `counted_shas` with the bar passed as an argument, so one definition of the guards serves both tasks. **Decided by:** agent
ADR-007: The AC-004 stage budgets rise to spec 6 850, execute 7 550, wrapup 3 900 (`tests/unit/test_overhaul_p1_surface.py`), the measured renders after trimming; the aggregate growth is this PLAN's `surface_allowance`. **Decided by:** agent (autopilot authorised by the DRI)
ADR-008: `tests/render/test_review_after_fixes.py` forbade any `hm check --` after the REVIEW write; SPEC AC-003 now requires exactly one, "then always run `hm check --slug <slug>`", so the predicate allows that phrase and still forbids any other invocation there. **Decided by:** agent (SPEC AC-003)
ADR-009: `tests/unit/test_overhaul_p1_hm_check.py`'s `_every_byte` (SPEC-hm-overhaul-p1 AC-005: no byte written, .git included) skips exactly `.git/hm/check-verdict.json`, the record SPEC-hm-cost-p3 IRR-002 places in the git dir; every other byte is still compared. The conflict was not raised when the DRI chose the git dir. **Decided by:** agent (follows IRR-002)
ADR-006: Bench runs use `--jobs 4` and start only after review fixes, on a WIP commit the wrapup squash replaces (feedback_bench_jobs_parallel; the DRI authorised running to wrapup without questions, 2026-10-21). **Decided by:** user (autopilot instruction)
