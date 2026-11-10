---
type: plan
task_slug: hm-cost-p4
status: complete
created: 2026-11-10
spec: "[[SPEC-hm-cost-p4]]"
surface_allowance:
  chars: 230
  reason: "SPEC-hm-cost-p4: execute gains the test-naming and no-copy rules and a conditional Step 1 read (+97 net), spec the behaviour-unchanged rule (+131), after trimming the new wording. DRI-confirmed 2026-11-10 (ADR-004); folded on main after land."
  delta_doc: BASELINE-DELTA-hm-cost-p4.md
  commands:
    spec: 135
    hm-spec: 135
    execute: 100
    hm-execute: 100
summary: One AC-test matcher and the gate's pytest runner in spec_machine, read-only discovery in check --red, template and stale-text edits, an hm-novalidator bench arm, then the tier-1 re-run.
---

# PLAN — hm-cost-p4

- Phase 1 (AC-001, AC-002) — scope: `spec_machine` collects with `check.pytest_runner` over the gate commands (PATH `pytest` fallback); one matcher `ac_tests_for(ac_id, nodeids)` (case id first, then function name) used by `mark_tested` discovery and `_collectable_ac_tests`. exit: `uv run pytest tests/unit/test_hm_cost_p4_binding.py -q`. risk: rule-3 / find-unbound behaviour on repos without `.venv`. rollback: revert the phase commit.
- Phase 2 (AC-003) — scope: `check.red_section` resolves empty `test_ids` through the matcher over a collect of the changed test files, with the static fallback for a file that fails to collect; full mode unchanged. exit: `uv run pytest tests/unit/test_hm_cost_p4_binding.py -q`. risk: a slow collect on big suites (scoped to changed test files). rollback: revert.
- Phase 3 (AC-004..AC-007) — scope: execute/spec templates, consensus-arbiter, `io_utils` advisory, `docs/ARCHITECTURE.md`. exit: `uv run pytest tests/unit/test_hm_cost_p4_templates.py tests/unit/test_overhaul_p1_surface.py tests/structural/test_command_size_budget.py -q`. risk: stage char budgets. rollback: revert.
- Phase 4 (AC-008) — scope: `scripts/bench_light_lane.py` arm `hm-novalidator`. exit: `uv run pytest tests/unit/test_hm_cost_p4_bench.py tests/unit/test_bench_light_lane.py -q`. risk: arm plumbing keyed on `arm == "hm"`. rollback: revert.
- Phase 5 (AC-009) — scope: tier-1 run (plain, hm, hm-novalidator × 5 × 3), `tests/fixtures/hm_cost_p4/batches.json`, result recorded in the SPEC. exit: `uv run pytest tests/integration/test_hm_cost_p4_bar.py -q`. risk: spend ≈ $20; a miss is recorded, not rerun. rollback: none needed (data only).

## 🚧 Contract Boundaries

### Do not change
- `src/harness_maker/check.py` full-mode `ac_section` semantics (pending_test still fails)
- `src/harness_maker/spec_machine.py` schema (`AcceptanceCriterion` fields)
- `scripts/bench/tasks/`

ADR-001: discovery lives in one pure function in `spec_machine` (`ac_tests_for`), imported by `check`, so the three consumers cannot drift. **Decided by:** agent
ADR-002: RED discovery collects only test files that are changed or untracked vs HEAD, so a large suite is not collected. **Decided by:** agent
ADR-003: the hm-novalidator template is the hm template with the `## Step 4.6` section of every rendered spec command removed. **Decided by:** agent
ADR-004: The AC-004 stage budgets rise to spec 6 950 and execute 7 610 (`tests/unit/test_overhaul_p1_surface.py`), the measured renders after one trim; the aggregate growth is this PLAN's `surface_allowance` (BASELINE-DELTA-hm-cost-p4.md). **Decided by:** DRI (confirmed 2026-11-10)
