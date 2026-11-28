---
type: plan
task_slug: intent-lean
status: planning
created: 2026-11-28
spec: "[[SPEC-intent-lean]]"
summary: "Rewrite the intent runtime as a lean canonical-only module, keep migrate's legacy reader, cut the engine, the legacy CLI and the dead prompt surface."
---

# PLAN — intent-lean

- Phase 1 — core runtime. scope: `intent.py` (canonical-only schema + new parser), `intent_cli.py` (records, questions, metrics, status, show, CLI), `intent_migrate.py` (own legacy reader); delete `world.py`, `intent_vocabulary.py`, `evidence_locator.py`. exit: `uv run pytest tests/unit/test_intent_lean.py -q -k "ac_002 or ac_003 or ac_004 or ac_005 or ac_006 or ac_009 or ac_011"`. risk: losing a kept behaviour (measure, record, questions) in the move. rollback: `git checkout main -- src/harness_maker/`.
- Phase 2 — consumers. scope: `world_model_digest.py` intents block and trim, `autopilot_caps.py` objective gate, `command_registry.py`, `hm.py`. exit: `uv run pytest tests/unit/test_intent_lean.py -q -k "ac_007 or ac_009"`. risk: digest over 1,500 bytes. rollback: revert those files.
- Phase 3 — prompt surface. scope: intent-layer SKILL, its reference file and `synthesize.py` entries, spec Step 0.5, wrapup Step 5, Maker skill, help pages, `step_sensitivity.py`, skeleton comment. exit: `uv run pytest tests/unit/test_intent_lean.py -q -k "ac_001 or ac_008"`. risk: golden render / size-baseline drift. rollback: revert templates.
- Phase 4 — data and docs. scope: `.claude/intent.yaml` Cursor rule, `intent/HM-LIGHT-LANE.md` close, `docs/reference/world-model.md`, CHANGELOG. exit: `uv run pytest tests/unit/test_intent_lean.py -q -k ac_010`. risk: none beyond data. rollback: revert the files.
- Phase 5 — tests. scope: delete tests whose subject is removed; port kept ones; re-pin goldens and baselines. exit: `uv run pytest -n 4 -q`. risk: deleting a test that guarded kept behaviour. rollback: restore the test file.

## 🚧 Contract Boundaries

### Do not change

- `.claude/intent/metrics.yaml`
- `intent/LOOP-OPT-IN.md`
- `intent/SOURCE-PLAN-STEPS.md`
- `intent/UNDERSTANDING-HANDOFF.md`
- `intent/WORLD-INTENT-CLOSED-LOOP.md`
- `src/harness_maker/templates/rubrics/`

## ADRs

- ADR-001: The runtime speaks only the canonical vocabulary (`statement`, `metric_id`, `out_of_scope`, `open|confirmed|wrong`); the legacy names live only in `intent_migrate.py`. **Decided by:** agent
- ADR-002: Records keep every key they carry on rewrite of another file; a goal record is only ever rewritten by `close`, which keeps unknown legacy keys (`approval`, `revisit_when`, `depends_on`, `rejected`) as they are. **Decided by:** user (SPEC IRR-002)
- ADR-003: `evidence_locator.py` is deleted with the staleness engine; its only importer was `world.py`. **Decided by:** agent
- ADR-004: Removed verbs stay as argparse subcommands that print the replacement and exit 2, so `command_registry`'s misroute guard never redirects them. **Decided by:** user (SPEC AC-002)
- ADR-005: Question `status` values stored as canonical `open|confirmed|wrong`; `observe --relation contradicts` sets `wrong`, `supersedes` replaces the claim and keeps history, `resolve` keeps today's allowed moves (open→confirmed|wrong, wrong→confirmed|open). **Decided by:** agent
