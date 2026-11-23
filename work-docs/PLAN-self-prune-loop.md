---
type: plan
task_slug: self-prune-loop
status: complete
created: 2026-11-23
spec: "[[SPEC-self-prune-loop]]"
summary: Generic hm-variant bench arm plus scripts/self_prune.py (plan / decide / status) and the SELF-PRUNE procedure doc; proposals only.
---

# PLAN-self-prune-loop

- Phase 1 — bench arm. scope: `scripts/bench_light_lane.py` (`VariantError`, `apply_variant`, `hm-variant` in VARIANT_ARMS, `--variant`, `runner_hash(variant_sha=)`, row `variant`). exit: `uv run pytest tests/unit/test_self_prune.py -k "ac_001 or ac_002" -q`. risk: a changed runner hash would orphan every pinned report hash. rollback: revert the file.
- Phase 2 — self_prune. scope: new `scripts/self_prune.py` (PROTECTED, protected_hits, plan, decide, status) and `docs/evals/SELF-PRUNE.md`. exit: `uv run pytest tests/unit/test_self_prune.py -q`. risk: a protected heading renamed in a template silently unprotects it (covered by AC-003's render check). rollback: delete the new files.

## 🚧 Contract Boundaries

### Do not change

- `src/harness_maker/step_sensitivity.py`
- `templates/`
- `docs/evals/results.jsonl`
- `docs/evals/RESULTS.md`

## ADRs

ADR-001: Output is proposals only; the loop never opens a PR of cuts. **Decided by:** user (decision card 2026-11-23)
ADR-002: Protection is a table of rendered headings in `self_prune.py`, checked against a real render, not a registry field. **Decided by:** agent
ADR-003: One bench out dir per candidate; the variant sha enters `runner_hash` only when set, so existing hashes stay valid. **Decided by:** agent
ADR-004: The verdict rule is deterministic Python (oracle); the LLM in the triggered session writes the candidates file. **Decided by:** agent
