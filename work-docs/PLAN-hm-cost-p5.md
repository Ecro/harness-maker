---
type: plan
task_slug: hm-cost-p5
status: complete
created: 2026-11-10
spec: "[[SPEC-hm-cost-p5]]"
summary: A CLI-computed validator verdict read by spec Step 4.6 with a validator-first approval choice, the cost target moved to 8 in the intent, the bench and the HM-LIGHT-LANE objective, then the tier-1 re-run.
---

# PLAN — hm-cost-p5

- Phase 1 (AC-001, AC-002) — scope: `spec_machine.VALIDATOR_SKIP_MAX_ACS`, `validator_verdict(model)`, the `validator` key in both `check --all` output forms when the yaml loads. exit: `uv run pytest tests/unit/test_hm_cost_p5_validator.py tests/unit/test_spec_machine_check_quiet.py tests/unit/test_spec_machine_check_all.py -q`. risk: existing tests pin exact key sets and a byte-for-byte differential against an older module. rollback: revert.
- Phase 2 (AC-003, AC-004) — scope: `templates/stages/spec.md.j2` Step 2 and Step 4.6, `templates/agents/spec-validator_body.md.j2` Triggers, the `step_sensitivity` entry for spec Step 4.6. exit: `uv run pytest tests/unit/test_hm_cost_p5_templates.py tests/unit/test_overhaul_p1_surface.py tests/structural -q`. risk: the stage must not grow (no `surface_allowance`), and other tests pin stage phrases. rollback: revert.
- Phase 3 (AC-005, AC-007) — scope: `.claude/intent.yaml` target 8, bench `TARGET = 8.0`, verdict tests and the three pinned report texts, `intent/HM-LIGHT-LANE.md` wording and re-approval, republished `docs/evals/RESULTS.md` and README block. exit: `uv run pytest tests/unit/test_hm_cost_p5_target.py tests/unit/test_bench_light_lane.py tests/unit/test_bench_tier3.py -q`. risk: the objective's approval hash covers its text and the target, so the re-stamp must come after every edit. rollback: revert.
- Phase 4 (AC-006) — scope: tier-1 run (plain, hm × 5 × 3), `tests/fixtures/hm_cost_p5/batches.json`, p4 rows moved to `docs/evals/history/hm-cost-p4.jsonl`, the result recorded in the SPEC, metric records. exit: `INTEGRATION=1 uv run pytest tests/integration/test_hm_cost_p5_bar.py tests/integration/test_hm_cost_p4_bar.py -q`. risk: spend ≈ $10; the first complete batch is the result, whatever it says. rollback: none needed (data only).

## 🚧 Contract Boundaries

### Do not change
- `src/harness_maker/spec_machine.py` schema (`AcceptanceCriterion`, `MachineSpec` fields) and `check --all` exit codes
- `src/harness_maker/world.py` (the approval check AC-007 relies on)
- `scripts/bench/tasks/`
- `scripts/bench_light_lane.py` `drop_spec_validator` and the `hm-novalidator` arm

ADR-001: the verdict is a pure function of the loaded model's live AC count, with one constant; no `harness.yaml` knob. **Decided by:** agent
ADR-002: skip by default at ≤ 8 live ACs, and the approval question carries a second label "Approve after spec-validator" that runs the pass regardless of the verdict. **Decided by:** DRI (cards, 2026-11-10)
ADR-003: the spec stage and the spec-validator agent body may not grow; any new wording is paid for by trimming in the same file, so this PLAN declares no `surface_allowance`. **Decided by:** agent (another in-flight PLAN holds an allowance)
ADR-004: cost target 8, and the re-run's bar is the metric's own verdict at that target. **Decided by:** DRI (cards, 2026-11-10)
ADR-005: the HM-LIGHT-LANE objective's text is edited to match and re-approved with `hm intent approve HM-LIGHT-LANE`. **Decided by:** DRI (card, 2026-11-10)
ADR-006: the pinned report texts change by the single substitution `target 5` → `target 8`, checked against the base commit read from git. **Decided by:** agent
