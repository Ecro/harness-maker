---
type: review
task_slug: bench-omc-arm
created: 2026-11-28
spec: "[[SPEC-bench-omc-arm]]"
summary: Two code-reviewer rounds, no P0/P1; P2s fixed, P3s fixed or rejected with reason. Codex second opinion skipped (CLI not installed).
---

# REVIEW — bench-omc-arm

Voters: code-reviewer (rounds 1 and 2). Codex second opinion: `skipped` (CLI not installed),
warn-and-proceed.

## Findings

| id | severity | file:line | finding | disposition | authority |
|---|---|---|---|---|---|
| R1-1 | P2 | scripts/bench_light_lane.py run_cell | omc_env ran outside the cell's try, so an OSError killed the run instead of a setup_error row | accepted | fixed: moved inside the per-session try, omc_env idempotent |
| R1-2 | P2 | scripts/bench_light_lane.py omc_env | an empty HOME means cold tool caches, biasing omc cost/wall | accepted | fixed: OMC_HOME_LINKS symlinks the operator's caches and user installs; .config stays out |
| R1-3 | P2 | tests/unit/test_bench_omc_arm.py | run_cell / saga option wiring untested | accepted | fixed: test_ac_004_run_cell_wiring, test_ac_005_saga_options |
| R1-4 | P2 | scripts/bench_light_lane.py --omc-dir | adding omc to an existing --out is refused (runner hash moves) | accepted | documented in --omc-dir help and SPEC Refinement Decisions |
| R1-5 | P3 | tests/unit/test_bench_omc_arm.py | refusal test asserted only exit 2 | accepted | fixed: asserts the message, a wrong-plugin dir, and that --out is never created |
| R1-6 | P3 | tests/unit/test_bench_omc_arm.py | saga env test used the real HOME, no CLAUDE_CONFIG_DIR check | accepted | fixed: HOME monkeypatched, CLAUDE_CONFIG_DIR asserted |
| R1-7 | P3 | scripts/bench_light_lane.py omc_setup | sha ignored a dirty tree / parent repo | accepted | fixed: .git required, -dirty suffix, git failure raises OmcError |
| R1-8 | P3 | scripts/bench_light_lane.py tier3_block | omc tier-3 rows appear in the tier-3 table | rejected | by design: that table lists every arm with tier-3 rows |
| R1-9 | P3 | scripts/bench_light_lane.py omc_env | CLAUDE_CONFIG_DIR defaults to ~/.claude when unset | rejected | the bench recipe always sets it; live omc cell ran fine (2026-11-28 pilot) |
| R2-1 | P3 | scripts/bench_light_lane.py omc_env | symlink_to raises if a real file of that name exists | accepted | fixed: skip when the path exists or is a link |
| R2-2 | P3 | scripts/saga_bench.py _agent_turn | omc_env runs every turn | rejected | idempotent and a few stat calls per turn; one code path for every turn |
| R2-3 | P3 | scripts/bench_light_lane.py _cmd_run | arms not stripped ("plain, omc") | rejected | the existing unknown-arm check refuses that list anyway, before spend |
| R2-4 | P3 | scripts/bench_light_lane.py omc_setup | OMC writing into its checkout would change the sha on resume | rejected | observed: the checkout stayed clean after a tier-1 cell and a saga run; it fails safe |
