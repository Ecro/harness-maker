---
type: plan
task_slug: stale-install-recovery
status: complete
created: 2026-11-19
spec: "[[SPEC-stale-install-recovery]]"
summary: Heal dead hook refs at SessionStart, Codex bootstrap fallback, auto-tag releases, document updating.
---

# PLAN — stale-install-recovery

## Phases

- **P1 heal** — scope: new `src/harness_maker/stale_ref_heal.py`; call it from `hooks/sessionstart_drift.run`; `hooks/hooks.json` passes `--plugin-root ${CLAUDE_PLUGIN_ROOT}` (AC-001..004). exit: `uv run pytest tests/unit/test_stale_ref_heal.py tests/unit/test_sessionstart_drift.py -q`. risk: a bad splice corrupts a committed settings.json. rollback: revert the module and the `run()` call.
- **P2 codex** — scope: `codex_setup.py` fallback + `make --update`, `skills/hm-make/SKILL.md` (AC-005, AC-006). exit: `uv run pytest tests/unit/test_codex_setup_fallback.py tests/unit/test_codex_setup.py -q`. risk: masking a real engine error. rollback: revert codex_setup.py.
- **P3 release** — scope: new `src/harness_maker/release_autotag.py`, `.github/workflows/autotag.yml`, CLAUDE.md release section (AC-007..009). exit: `uv run pytest tests/unit/test_release_autotag.py tests/structural/test_autotag_workflow.py -q`. risk: unintended publish (IRR-001). rollback: delete autotag.yml.
- **P4 docs** — scope: README (Updating, Reconcile, Marketplace, Codex), `work-docs/RESEARCH-stale-install-recovery.md` (AC-010, AC-011). exit: `uv run pytest tests/structural/test_update_docs.py -q`. risk: none beyond text. rollback: revert README.

## 🚧 Contract Boundaries

### Do not change

- src/harness_maker/render.py
- src/harness_maker/synthesize.py
- templates/

## ADRs

ADR-001: The running ref is the `--plugin-root` argument (`${CLAUDE_PLUGIN_ROOT}`), falling back to the `CLAUDE_PLUGIN_ROOT` env var — not `synthesize._compute_install_ref()`. The plugin hook runs `uv run --with ${CLAUDE_PLUGIN_ROOT}`, so they name the same directory; the argument is explicit, and its absence (the rendered Codex copy) is what disables the heal. **Decided by:** agent

ADR-002: The splice reuses `render._splice_install_ref` on the command suffix that starts at the chosen `--with` token; the chosen token is the last `--with` before `python -m harness_maker.` that fully expands to a plugin-cache path (`~/.claude/plugins/cache/<mkt>/harness-maker/<ver>`) and is gone. A dev path, URL, bare package name or unexpanded variable is the user's choice and is never repointed (review F1). **Decided by:** agent

ADR-003: Byte preservation is done on raw text: each healed command's JSON-encoded old string is replaced by the JSON-encoded new one; if the encoded old string is not found verbatim, that file is skipped. **Decided by:** agent

ADR-004: Same-session effect observed 2026-11-19 on Claude Code 2.1.328 (`claude -p`): a SessionStart edit to `settings.json` changed the PreToolUse command run later in the same session. The message therefore says no restart is needed, and to restart only if a hook still fails. **Decided by:** agent (experiment, `work-docs/RESEARCH-stale-install-recovery.md`)

ADR-005: Codex fallback triggers when the pinned engine run produced no JSON receipt on stdout and no Python traceback on stderr (a traceback means the engine ran; review F4). **Decided by:** user (SPEC Refinement Decisions)

ADR-006: Auto-tag dispatches `release.yml` with `--ref vX.Y.Z`; `release.yml` jobs are unchanged — only the `dry_run` description and one comment that said dispatch never publishes are corrected (anticipated in the SPEC's Refinement Decisions; review F9). **Decided by:** user (SPEC IRR-001)
