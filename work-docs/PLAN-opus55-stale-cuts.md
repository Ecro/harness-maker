---
type: plan
task_slug: opus55-stale-cuts
status: complete
created: 2026-11-17
spec: "[[SPEC-opus55-stale-cuts]]"
summary: "Remove the stale worktree-isolator skill, the dead session-snapshot hook with its hot tier, and the CLAUDE.md stub lines, by the existing retirement paths."
---

# PLAN — opus55-stale-cuts

- [x] Phase 1 — scope: `tests/render/test_opus55_stale_cuts.py` (six AC tests) and the 0.65.5 path fixture; exit: `uv run hm check --red --slug opus55-stale-cuts`; risk: low; rollback: delete the test file.
- [x] Phase 2 — scope: templates (`claude-md/*`, `skills/worktree-isolator/`, `memory/session-readme.md.j2`, `settings/*.json.j2`, `codex/hooks.json.j2`, `stages/execute.md.j2`), the skill lists (`synthesize`, `interview`), `render._HARNESS_RETIRED_HOOK_INVOCATIONS`, and `hooks/flush_session.py` as a stub; exit: `uv run pytest tests/render/test_opus55_stale_cuts.py -q`; risk: medium (a brownfield re-render must not drop a user's hook); rollback: revert the commit.
- [x] Phase 3 — scope: tests that pin the old render (snapshots, hook tables, skill counts, surface budgets), docs (README en/ko, HOW-IT-WORKS en/ko, ARCHITECTURE, CONTRIBUTING) and CHANGELOG; exit: `uv run ruff check . && uv run ruff format --check . && uv run mypy --strict src && uv run pytest -q`; risk: low; rollback: revert the commit.

## 🚧 Contract Boundaries

### Do not change

- src/harness_maker/gates/
- src/harness_maker/check.py
- src/harness_maker/spec_machine.py
- src/harness_maker/worktree.py
- src/harness_maker/templates/stages/spec.md.j2
- src/harness_maker/templates/stages/wrapup.md.j2
- src/harness_maker/templates/rubrics/
- src/harness_maker/templates/skills/agent-quality-rubric/
- src/harness_maker/templates/skills/ai-readiness-rubric/
- src/harness_maker/templates/skills/context-linter/

## Decisions

- ADR-001: Retire by the existing paths only (`RETIRED_SKILLS`, orphan sweep, `_HARNESS_RETIRED_HOOK_INVOCATIONS`); no new retirement mechanism. **Decided by:** agent
- ADR-002: `hooks/flush_session.py` stays as an exit-0 stub that reads stdin and writes nothing, as 0.64.0 did for `telemetry` and `autopilot_autoarm`; its progress-snapshot code is deleted. **Decided by:** agent
- ADR-003: Codex `Stop` held only `flush_session`, so the `Stop` key leaves `.codex/hooks.json` rather than rendering an empty list. **Decided by:** agent
- ADR-004: The scope is three items, not the five the DRI saw on the card: the reasoning-template and rubric-skill cuts were withdrawn when the render disproved the research (SPEC, Refinement Decisions). **Decided by:** agent, reported to the DRI
- ADR-005: `worktree.py`'s module docstring names the worktree-isolator skill; it is inside `Do not change` and stays as is (a comment, not behaviour). **Decided by:** agent
- ADR-006: `templates/hooks/hooks.json.j2` and `cursor_retire`'s shipped entry keep naming `flush_session`. Both exist only to recognise a pristine file an older release wrote; changing them would stop that match. **Decided by:** agent
- ADR-007: ACs of older SPECs that describe the removed behaviour are retired with `hm spec_machine retire --by opus55-stale-cuts` (`SPEC-flush-session` AC-001, `SPEC-retired-text` AC-003, the skeleton ACs of `SPEC-tpl-SKILL-md` and `SPEC-tpl-session-readme-md`), and their tests are deleted, not rewritten to pass. Tests of ACs that stay live lose only the rows naming the retired skill and hook. **Decided by:** agent
- ADR-008: `test_hook_host`'s control (a hook that acts as the Cursor copy) moves from `flush_session`'s file write to `permission_gate`'s `PermissionRequest` answer on stdout. No remaining settings hook writes to the tree on that payload, and without a control the silence test above it proves nothing. **Decided by:** agent
- ADR-009: Two guards added after review, both inside existing mechanisms: the orphan sweep keeps `agents/openai.yaml` beside a kept `SKILL.md` (`reconcile._guards_a_kept_skill`), and `_merge_hooks_json` drops an event emptied by retirement. ADR-001 still holds: no new way to retire something. **Decided by:** agent
- ADR-010: `SPEC-hm-overhaul-p1` AC-009's hot-tier clause is amended by this SPEC's IRR-001; its test is deleted and unbound. An earlier draft rewrote that test to assert the opposite, which ADR-007 forbids; the reviewer caught it. **Decided by:** agent
