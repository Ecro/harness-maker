---
type: plan
task_slug: maker-digest-session-id
status: complete
created: 2026-11-16
spec: "[[SPEC-maker-digest-session-id]]"
summary: The Claude Maker injection loses its two shell variables (the session id comes from the host's substitution, the home prefix is written `~`); a render test, a live boundary test and the docs follow.
---

# PLAN — maker-digest-session-id

One phase is enough: the change is two template expressions plus their tests and docs.

- [x] Phase 1 — Claude injection uses `${CLAUDE_SESSION_ID}` and a `~` home prefix; Codex keeps `$HM_SESSION_ID` and `$HOME`. scope: `src/harness_maker/templates/skills/world-model/SKILL.md.j2`, `tests/render/test_render_maker_digest_session_id.py`, `tests/integration/test_boundary_maker_default_permissions.py`, `CLAUDE.md`, `docs/reference/world-model.md`, `CHANGELOG.md`, `tests/snapshot/*.expected.yaml` (regenerated). exit: `uv run pytest tests/render/test_render_maker_digest_session_id.py tests/render/test_render_maker_front_door.py tests/render/test_render_sessionid_wiring.py -q`. risk: the rendered Maker's 4,689-char cap (the token adds 5 chars per use, `~` saves 4 per use of the prefix). rollback: revert both template expressions (the `src` rewrite and the `sid` choice).

## 🚧 Contract Boundaries

### Do not change

- src/harness_maker/world_model.py
- src/harness_maker/world_model_digest.py
- src/harness_maker/hooks/sessionid_envfile.py
- tests/render/test_render_maker_front_door.py

## Decisions

ADR-001: The Claude variant passes `--session-id "${CLAUDE_SESSION_ID}"`, a host skill substitution, instead of reading a session-id file in the digest. **Decided by:** agent
ADR-002: The Codex variant keeps `"$HM_SESSION_ID"`; it is a model-issued shell command with no host substitution. **Decided by:** agent
ADR-003: The live default-permission check is an advisory boundary test (`INTEGRATION=1`, `claude` on PATH), not an AC: `hm check` counts a skipped test as a failure. **Decided by:** agent
ADR-004: If the size cap is exceeded, trim Maker prose elsewhere by the same count rather than raise the cap. **Decided by:** agent
ADR-005: The Claude Maker writes a plugin path under the home directory as `~/…` in its `hm` prefix (the injected line, `allowed-tools` and the "`hm` below means" line together), because no `allowed-tools` rule matches a command that holds `$HOME`; found during execute when AC-001 failed on the rendered path, confirmed live. **Decided by:** agent
