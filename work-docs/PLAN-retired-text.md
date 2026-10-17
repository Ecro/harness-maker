---
type: plan
task_slug: retired-text
status: planning
created: 2026-10-17
spec: "[[SPEC-retired-text]]"
summary: "Templates first (AC-001..004), then docs (AC-007), then the two test fixes (AC-005, AC-006); goldens re-captured, baseline folded"
---

# PLAN — retired-text

## Phases

1. Templates. scope: consensus-arbiter_body, _partials/hard_rules, commands/hm/health, skills/worktree-isolator, skills/intent-layer, skills/world-model, settings/{Side,Production}.json.j2, codex/hooks.json.j2. exit: `uv run pytest -q tests/render/test_retired_text.py tests/render/test_render_maker_front_door.py`. risk: goldens and surface baseline move. rollback: revert the template edits.
2. Goldens. scope: tests/snapshot/*.expected.yaml, tests/unit/test_agent_body_partials.py pins (strictness_reference is a pre-change reference and stays; the surface shrank, so the baseline is folded from main after merge). exit: `uv run pytest -q -n auto tests/structural tests/render`. risk: a golden re-captured from the wrong render. rollback: git checkout the fixtures.
3. Docs. scope: CLAUDE.md, docs/ARCHITECTURE.md, docs/reference/world-model.md, README.md, README.ko.md. exit: `uv run pytest -q tests/unit/test_retired_text_docs.py`. risk: CLAUDE.md char budget. rollback: revert.
4. Ship-bar alias. scope: tests/integration/test_overhaul_p1_ship_bar.py, tests/fixtures/overhaul_p1/harness_sha_aliases.json. exit: `uv run pytest -q tests/integration/test_overhaul_p1_ship_bar.py`. risk: alias accepted without tree check. rollback: revert.
5. Replay digest. scope: tests/integration/test_overhaul_p1_eval3_replay.py, tests/fixtures/hm_check_eval3/harness_manifest*.json, scripts/regen_eval3_harness_manifest.py. exit: `uv run pytest -q -n auto tests/integration/test_overhaul_p1_eval3_replay.py`. risk: manifest recomputed from the replay instead of originals. rollback: revert.

## 🚧 Contract Boundaries

### Do not change
- src/harness_maker/templates/hooks/hooks.json.j2
- src/harness_maker/autopilot.py
- src/harness_maker/render.py
- docs/evals/results.jsonl
- tests/fixtures/hm_check_eval3/*/expected.json

## ADRs

ADR-001: Mixed user/harness hook groups keep their old status message; the merge code is not changed. **Decided by:** user (SPEC-retired-text card 2026-10-17)
ADR-002: The squash alias is checked by `src`/`scripts` tree hash of its target, recorded from the source while it was known. **Decided by:** user (SPEC card)
ADR-003: Whitespace collapse applies only inside `.md` YAML frontmatter. **Decided by:** user (SPEC card)
ADR-004: The provenance file records one entry per original run (run id, harness commit SHA, digest); the script recomputes from `/var/tmp/hm-eval-3/runs`. **Decided by:** agent
ADR-005: The Maker briefing line drops "**autopilot**"; the digest keeps the field (Python untouched). **Decided by:** agent
