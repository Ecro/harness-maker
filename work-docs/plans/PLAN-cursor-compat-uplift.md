---
type: plan
task_slug: cursor-compat-uplift
status: planning
created: 2026-05-08
tags: [harness-maker, plan, cursor, compatibility, hooks, agents, permissions, mcp, drift]
spec: null  # research/spec skipped — direct plan from /hm:refresh proposal P1-P6
research_doc: ".claude/observability/refresh/proposed-2026-05-08.md"
interview_rounds: 1
adrs: 0
validator_outcome: PENDING
summary: "Cursor 2.4+/3.x compatibility uplift across hooks schema, agent permission frontmatter, command discovery, MCP propagation, rules docs, and drift detector"
---

# PLAN: Cursor compatibility uplift (P1–P6)

## 🎯 Executive Summary

> **TL;DR:** Six-phase single-PR uplift bringing Cursor target from "templates exist, untested" to "Cursor 2.4 minimum / 3.2 recommended, verified". Phase 0 is a manual-verification fixture that gates Phase 2 + Phase 3 branching.

### What We're Doing

Six related fixes against `templates/cursor/*`, `templates/agents/*`, and the Cursor-side dispatch in `render.py`, all driven by gaps surfaced in `proposed-2026-05-08.md` after researching Cursor 2.4 → 3.2 changelogs (2026-01-22 → 2026-04-24).

### Why It Matters

`targets: cursor` is a documented harness-maker capability but has been frozen mid-Phase-1 since the original Cursor target work. Cursor 2.4 / 2.5 / 3.0 / 3.2 all shipped relevant changes (subagent permission inheritance gap, hooks schema unification, native worktrees, agent-first redesign). Two real correctness risks (P1 hooks schema mismatch, P2 agent permissions written as prose only) become live the moment a user opts into `targets: cursor`.

### Key Decisions (from interview + kairos forensic, 2026-05-08)

- **P1 hooks.json strategy**: **REFRAMED post-forensic.** Original framing ("schema mismatch, delete or rewrite") was wrong. kairos 0.5.7 evidence (metrics.jsonl 4 entries × `event: "stop"` lowercase + `status` + `loop_count` Cursor-only fields) proves the dual-render is **intentional and correct** — `.cursor/hooks.json` (lowercase camelCase + `version: 1`) is Cursor-native, `.claude/hooks/hooks.json` (PascalCase + nested) is Claude-native. Action: **keep dual-render, add explanatory comments** to template + render.py so future sessions don't re-debate.
- **P2 agent permissions**: always include structured `permissions:` block in frontmatter (target-agnostic) — Claude Code accepts unknown frontmatter; Cursor enforces explicitly.
- **P4 commands mirror**: **RESOLVED post-forensic.** kairos 0.5.7 has zero `.cursor/commands/` content yet user confirmed `/hm:*` slash commands worked in Cursor IDE → **Cursor reads `.claude/commands/hm/*.md` natively**. Action: commit to single-source, remove "subject to Phase 1 A4 verification" conditional language from `harness.mdc.j2`.
- **Scope**: single PR with 7 phases (Phase 0 reduced + P1–P6), version bump `0.6.1 → 0.6.2`.

### Estimated Impact

- **Complexity**: Medium
- **Risk Level**: Low–Medium (no current `targets: cursor` users in this repo; sandbox + e2e snapshot coverage adequate)
- **Files Changed**: ~12–18 (6 agent templates + 2 cursor templates + 1–2 dispatch fns in render.py + 1 drift fn + 1 manual checklist + 4 version files + snapshots)

---

## Architectural Touchpoints

| Area | Files | Contract Shift |
|---|---|---|
| Phase 0 verification | `tests/cursor-compat/MANUAL_CHECKLIST.md` | New manual fixture doc |
| Agent permissions | `templates/agents/{executor, code-reviewer, security-reviewer, performance-reviewer, ux-reviewer, concurrency-reviewer}.md.j2` | New frontmatter `permissions:` block (additive, backward-compatible) |
| Cursor hooks | `templates/cursor/hooks.json.j2`, `render.py::_is_cursor_hooks_json` | Delete or rewrite based on Phase 0 outcome |
| Cursor commands | `templates/cursor/commands/` (potential new), `render.py::_is_cursor_command`, `harness.mdc.j2` | Add or remove mirror branch based on Phase 0 outcome |
| Cursor MCP | `templates/cursor/mcp.json.j2`, `render.py` MCP source resolver | Hardcoded `{}` → render from `harness.yaml.mcp_servers` (or shared `.claude/.mcp.json` source) |
| Cursor rules | `templates/cursor/rules/harness.mdc.j2` | Docs additions (min version, /best-of-n interop) |
| Drift detector | `src/harness_maker/relevance.py::detect_version_drift` (or `version_check.py`) | Logic alignment with SessionStart hook |
| Version bump | `.claude-plugin/plugin.json`, `.cursor-plugin/plugin.json`, `pyproject.toml`, `src/harness_maker/__init__.py` | `0.6.1 → 0.6.2` |
| Snapshot fixtures | `tests/snapshot/__snapshots__/`, `tests/e2e/sandbox-plugin-test/.cursor/` | Regenerate after each phase |

---

## Phase Decomposition

### Phase 0 — Forensic evidence capture + (optional) hooks fallback fixture

**Scope (reduced from original plan)**: Most of Phase 0's purpose was resolved by kairos forensic on 2026-05-08. Remaining work:

**Forensic record (must)**:
- Write `tests/cursor-compat/results-2026-05-08.md` documenting kairos evidence:
  - Q-B (commands discovery): **RESOLVED** → Cursor reads `.claude/commands/hm/*.md` natively. Evidence: kairos 0.5.7 has no `.cursor/commands/` directory, user confirmed `/hm:*` slash commands worked in Cursor IDE.
  - Q-A (hooks discovery — partial): **RESOLVED that `.cursor/hooks.json` works in Cursor**. Evidence: kairos `metrics.jsonl` 4 entries × `event: "stop"` (lowercase) + `status: "completed"` + `loop_count: 0` — payload shape is uniquely Cursor-stop per `telemetry.py:11` docstring. Open sub-question: does Cursor *also* read `.claude/hooks/hooks.json` as fallback when `.cursor/hooks.json` is absent? (Lower priority — answer affects only whether dual-render is required vs optional.)
  - Cite exact byte-level evidence (file mtimes, JSONL contents) so future sessions don't re-debate.

**Hooks fallback fixture (optional, defer if blocked)**:
- `tests/cursor-compat/fixture-claude-only/` — sandbox with `.claude/hooks/hooks.json` only, no `.cursor/hooks.json`.
- `tests/cursor-compat/MANUAL_CHECKLIST.md` — 3-step procedure (open in Cursor 3.x, trigger Stop event, check metrics).
- Outcome appended to results doc.

**Exit criterion**:
- `tests/cursor-compat/results-2026-05-08.md` exists, cites kairos evidence with file paths + line numbers + JSONL excerpts.
- Phase 2/3 framings are unblocked regardless of hooks-fallback fixture outcome (current dual-render is correct either way; fallback test only changes whether dual-render is "required" vs "belt-and-suspenders").

**Risk**: Low (was Medium). Forensic evidence is on-disk, no IDE access required. Optional fallback fixture only blocks Phase 2's documentation precision, not its action.

**Rollback point**: Pre-Phase-1.

### Phase 1 — P2 Agent permissions frontmatter

**Scope**: Add structured `permissions:` block to YAML frontmatter of 6 agent templates.

**Files**:
- `templates/agents/executor.md.j2` — keep prose body, add frontmatter `permissions.allow` (Read(*), Write(.worktrees/**), Edit(.worktrees/**), Bash(uv run:*), Bash(pytest:*)) + `permissions.deny` (Write(/etc/**), Write(~/.ssh/**), Bash(curl * | sh), Bash(eval *)).
- `templates/agents/code-reviewer.md.j2` — `permissions.allow: [Read(*), Grep(*), Glob(*), Bash(git diff:*), Bash(git log:*)]` + `permissions.deny: [Write(*), Edit(*), Bash(rm:*), Bash(curl:*), Bash(npm:*)]`.
- Same shape for `security-reviewer.md.j2`, `performance-reviewer.md.j2`, `ux-reviewer.md.j2`, `concurrency-reviewer.md.j2`.
- `templates/agents/_partials/permissions.md.j2` — new partial for the prose section that mirrors the structured fields (DRY, single source for both blocks).
- Verify Claude Code agent loader accepts unknown frontmatter — quick test: copy one template's render to `~/.claude/agents/probe.md` and confirm no warning in `claude --debug`.

**Exit criterion**:
- All 6 agent templates render with `permissions.allow` + `permissions.deny` in frontmatter.
- Snapshot test passes (deterministic render).
- One Cursor 3.x manual probe: spawn an agent that would hit a `Bash(curl:*)` call → Cursor displays deny instead of `ask`-blocking. (Documented in `tests/cursor-compat/results-2026-05-08.md`.)
- `pytest tests/unit/test_render.py -k agents` green.

**Risk**: Low. Frontmatter is additive; Claude Code is permissive on unknown fields. Worst case: a future Claude Code release strict-rejects the field — gate behind `{% if 'cursor' in targets %}` retroactively.

**Rollback point**: Per-agent commit. If any one breaks Claude Code, revert that single template.

### Phase 2 — P1 Cursor hooks.json clarification (REFRAMED)

**Scope**: Original "schema mismatch / delete-or-rewrite" framing was wrong (kairos forensic disproved it). The two hooks files are **deliberately different** — each IDE has its own native schema:

- `.cursor/hooks.json` — Cursor-native (lowercase camelCase: `preToolUse`, `stop`, `preCompact` + `version: 1` flat shape)
- `.claude/hooks/hooks.json` — Claude-native (PascalCase: `PreToolUse`, `Stop`, `PreCompact` + nested `{hooks:[],matcher:}` shape)

Action is now **clarification + safety**, not refactor:

**Files**:
- `templates/cursor/hooks.json.j2` — add Jinja header comment: `{# Cursor-native schema. Do NOT match Claude PascalCase. Cursor 2.4+ reads this lowercase shape natively. See work-docs/plans/PLAN-cursor-compat-uplift.md Phase 2 + tests/cursor-compat/results-2026-05-08.md. #}`
- `src/harness_maker/render.py` — add docstring to `_is_cursor_hooks_json` (or wherever cursor hooks render dispatches) explicitly stating "two divergent schemas by design, not bug."
- `templates/hooks/hooks.json.j2` (Claude side) — symmetric comment so the divergence is documented from both ends.
- `CLAUDE.md` §Plugin 구조 (Claude Code + Cursor 공식 spec) — append "**Hook schemas diverge by design**: Cursor reads `.cursor/hooks.json` lowercase; Claude reads `.claude/hooks/hooks.json` PascalCase. Verified empirically via kairos 0.5.7 metrics forensic 2026-05-08."

**Optional consolidation (defer)**: If Phase 0 fallback fixture proves Cursor 2.4+ reads `.claude/hooks/hooks.json` as a fallback, single-source becomes possible. Defer this to a future minor version — current dual-render works empirically and changing it has non-zero regression risk.

**Exit criterion**:
- Comments present in 3 locations (Cursor template, Claude template, render.py).
- CLAUDE.md updated.
- `pytest tests/snapshot -k cursor_hooks` green (unchanged content).
- New unit test `tests/unit/test_cursor_hooks_schema.py::test_cursor_uses_lowercase_keys` asserts the rendered cursor hooks file has `"preToolUse"` (not `"PreToolUse"`) — guards against accidental "fix" by future-Claude.

**Risk**: Low. Documentation only; no behavior change.

**Rollback point**: single revert per file.

### Phase 3 — P4 Cursor commands single-source commit (RESOLVED to Branch A)

**Scope**: kairos forensic resolved Q-B. Cursor reads `.claude/commands/hm/*.md` natively. Commit to single-source:

**Files**:
- `templates/cursor/rules/harness.mdc.j2` — remove the conditional paragraph:
  > "Cursor recognises this location (subject to Phase 1 A4.command-discover verification — if it fails, `.cursor/commands/` mirrors will be added)."

  Replace with:
  > "Cursor 2.4+ reads `.claude/commands/hm/*.md` natively (verified empirically via kairos 0.5.7, 2026-05-08). No `.cursor/commands/` mirror is required."
- `src/harness_maker/render.py` — `_is_cursor_command` dispatch is currently dead code (no template directory feeds it). Decide:
  - **Keep + comment**: leave dispatch in place with comment "currently unused — reserved if Cursor breaks single-source in a future version."
  - **Remove**: delete `_is_cursor_command` and the dispatch branch in `render_all`. Cleaner, but requires reintroducing if Cursor changes behavior later.

  **Recommendation**: Remove. If Cursor changes, reintroduce with a Phase 0 fixture that proves the need. YAGNI > defensive code per CLAUDE.md §코드 스타일.
- `tests/cursor-compat/results-2026-05-08.md` — record kairos evidence + user confirmation as primary source.

**Exit criterion**:
- `harness.mdc.j2` no longer contains "Phase 1 A4" conditional language.
- `_is_cursor_command` either removed or annotated as reserved.
- Snapshot regenerated; `pytest tests/snapshot -k cursor_rules` green.
- New unit test `tests/unit/test_render.py::test_no_cursor_commands_rendered` asserts `targets: [claude-code, cursor]` render produces zero files under `.cursor/commands/` — guards against accidental reintroduction.

**Risk**: Low. Single-source is empirically verified. Worst case (future Cursor regression): users see `/hm:*` not appear in picker → reintroduce mirror via new minor version.

**Rollback point**: per-file revert.

### Phase 4 — P5 Cursor MCP propagation

**Scope**: Replace hardcoded `{"mcpServers": {}}` in `templates/cursor/mcp.json.j2` with a render that reads the same source as Claude.

**Files**:
- `templates/cursor/mcp.json.j2` — `{ "mcpServers": {{ mcp_servers | tojson }} }` driven by template var.
- `render.py` — pass `mcp_servers` from `harness.yaml.mcp_servers` (or `.claude/.mcp.json` if existing) into both Claude and Cursor template contexts.
- `templates/harness-yaml/Production.yaml.j2` + `Side.yaml.j2` — document `mcp_servers:` key (currently absent in both).
- `models.py` — extend `HarnessConfig` with `mcp_servers: dict[str, McpServer] = {}` (Pydantic model).

**Exit criterion**:
- `pytest tests/unit/test_render.py -k mcp_propagation` — new test that adds 1 server to harness.yaml, asserts both `.claude/.mcp.json` and `.cursor/mcp.json` contain identical `mcpServers` block.
- Snapshot of `.cursor/mcp.json` differs only in path, not content.

**Risk**: Low. Additive; no current users have MCP servers in this project.

**Rollback point**: revert template + render dispatch + Pydantic model in one commit.

### Phase 5 — P3 harness.mdc.j2 docs uplift

**Scope**: Update Cursor rules file with current 2026-05 truth.

**Edits to `templates/cursor/rules/harness.mdc.j2`**:
- Add line near top: `> Minimum supported Cursor: 2.4 (2026-01-22). Recommended: 3.2 (2026-04-24).`
- New section `## Worktree interop with Cursor 3.x` — explain that `/best-of-n` and `/worktree` work alongside harness-maker because cleanup is prefix-matched (`phase-*`, `autoloop-*` reserved for harness; Cursor's `/best-of-n` uses different prefixes).
- Remove "subject to Phase 1 A4.command-discover verification" caveat after Phase 3 commits to a branch.
- Update "Phase 2.4 sidecar metadata" reference if still relevant after Phase 4.

**Exit criterion**:
- `pytest tests/snapshot -k cursor_rules` green.
- `wc -l` of rendered `.cursor/rules/harness.mdc` ≤ 200 (Side preset cap per CLAUDE.md context-lint).
- Content-linter passes.

**Risk**: Low. Docs only.

**Rollback point**: single file revert.

### Phase 6 — P6 Drift detector alignment

**Scope**: Find why `detect_version_drift()` returned False while SessionStart hook reported drift on the same `.claude/harness.yaml` (0.5.7) vs installed plugin (0.6.1).

**Investigation steps**:
1. `grep -rn "detect_version_drift\|version_drift" src/harness_maker/` — locate definition.
2. `grep -rn "harness.yaml\|harness_maker_version" src/harness_maker/hooks/` — find SessionStart hook's drift check.
3. Diff the two logics: are they reading different fields? Different files? Different version sources?

**Likely fix locations** (educated guess pending step 1):
- `src/harness_maker/relevance.py::detect_version_drift` — alignment fix.
- `src/harness_maker/hooks/session_start.py` (or wherever the hook lives) — make it the single source of drift logic.
- Add unit test: simulate `harness.yaml` with version `0.5.7` while `__version__ = "0.6.1"` → assert both code paths return drift=True with identical version strings.

**Exit criterion**:
- New unit test `tests/unit/test_drift_alignment.py::test_session_start_and_refresh_agree` passes.
- Re-run `/hm:refresh` on this project → drift section shows `1` (not `0`).
- Hook + detector reference the same comparison function (single source).

**Risk**: Low. Investigation may surface a bigger inconsistency (e.g., per-component versioning) — escalate via stuck agent if so.

**Rollback point**: per-fn commit; revert detector if hook semantics turn out to be the buggy side.

### Phase 7 — Version bump + release notes

**Scope**: Bump 0.6.1 → 0.6.2 across the four files (CLAUDE.md "버전업 정책" — three files plus `__init__.py` and the two manifests, total **four**).

**Files**:
- `.claude-plugin/plugin.json` — `"version": "0.6.2"`
- `.cursor-plugin/plugin.json` — `"version": "0.6.2"`
- `pyproject.toml` — `version = "0.6.2"`
- `src/harness_maker/__init__.py` — `__version__ = "0.6.2"`
- `CHANGELOG.md` (if exists; otherwise add release note in commit body) — entries P1–P6 mapped to Phase 1–6 outcomes.

**Exit criterion**:
- `grep -rn '"version"\|__version__\|^version' .claude-plugin/ .cursor-plugin/ pyproject.toml src/harness_maker/__init__.py` returns four lines, all `0.6.2`.
- Final autoloop wrapup commit: `feat(0.6.2): cursor-compat uplift — agent permissions + hooks/commands single-source verified + MCP propagation + drift detector aligned`.

**Risk**: Low (mechanical).

---

## Risk Register

| ID | Risk | Phase | Likelihood | Impact | Mitigation |
|---|---|---|---|---|---|
| R1 | ~~Phase 0 manual verify blocked~~ **Phase 0 Q-A and Q-B resolved by kairos forensic — risk retired** | 0 | — | — | n/a |
| R2 | Claude Code strict-rejects unknown frontmatter `permissions:` | 1 | Low | Med (breaks Claude target) | Pre-flight test against `~/.claude/agents/probe.md` before bulk edit; gate with `{% if 'cursor' in targets %}` if needed |
| R3 | Cursor 3.x changes hooks schema in a future release (regression of dual-render assumption) | 2 | Low | Med | Snapshot test asserts lowercase Cursor keys (`preToolUse` not `PreToolUse`). Document version pin: "verified on Cursor 3.2 / kairos 0.5.7 / harness-maker 0.6.x" |
| R4 | Future Cursor release stops reading `.claude/commands/` natively (regression of P4 single-source assumption) | 3 | Low | Med | Snapshot test asserts no `.cursor/commands/` files rendered. If Cursor regresses, reintroduce mirror via dispatch fn — keep `_is_cursor_command` (option Keep+comment) instead of deleting. **Reconsider Phase 3 file disposition** if user prefers defensive option |
| R5 | MCP propagation invalidates existing reconcile hashes | 4 | Med | Low | Snapshot regeneration is automatic; reconcile hash diff is expected on next render and not user-visible (block-merge markers untouched) |
| R6 | Drift detector fix changes existing test expectations | 6 | Med | Low | Update existing tests in same commit; if cascading, escalate to stuck |
| R7 | Forensic conclusion misreads kairos evidence (e.g. metrics were actually written by Claude Code, not Cursor) | 0,2,3 | Low | High (entire reframing collapses) | Cross-check: `telemetry.py:11` docstring explicitly states `status/loop_count` are Cursor-only fields; all 4 entries have those fields → Claude origin ruled out. Plus user empirically confirmed `/hm:*` worked in Cursor (independent evidence path) |

---

## Rollback Strategy

**Granularity**: per-phase commit. Each phase's exit-criterion failure stops the autoloop, preserves the worktree (CLAUDE.md `--debug-worktree` semantics), and emits a wrapup `BLOCKED:` log entry.

**Hard rollback points**:
- After Phase 0: results doc + manual checklist exist; safe to halt before any template touched.
- After Phase 1: agent permissions live; hooks/commands untouched. Releasable as 0.6.2-rc1 if remaining phases blocked.
- After Phase 4: MCP + permissions + hooks/commands all done; rules+drift remaining. Releasable as 0.6.2.
- After Phase 7: full release. No rollback after this point — fix-forward only.

**Per-phase rollback**: each phase's "Rollback point" sub-bullet specifies the smallest revert unit (single template, single dispatch fn, single test).

---

## Unknowns

### Resolved by kairos forensic (2026-05-08)

1. ~~**Q-A**: Cursor hooks discovery scope~~ — RESOLVED: `.cursor/hooks.json` (lowercase Cursor-native schema) is read by Cursor; `.claude/hooks/hooks.json` (PascalCase Claude-native schema) is read by Claude Code. Each IDE owns its own file. Sub-question (does Cursor *also* read `.claude/hooks/hooks.json` as fallback?) is open but non-blocking.
2. ~~**Q-B**: Cursor commands discovery scope~~ — RESOLVED: Cursor reads `.claude/commands/hm/*.md` natively. No `.cursor/commands/` mirror needed.

### Still requiring resolution during execute

3. **Q-C** (Phase 1 sub-question): does Claude Code agent loader accept unknown frontmatter fields like `permissions:` without warning? Pre-flight probe before bulk edit.
4. **Q-D** (Phase 6 sub-question): which side (SessionStart hook vs `detect_version_drift`) has correct semantics? They disagree; investigation in Phase 6 will identify which to align to.

---

## Quality Bar

- ✅ Independent reader can predict file diff per phase: yes — every phase lists exact files + edits.
- ✅ Each exit criterion is checkable: pytest invocations, manual verification artifacts, grep checks.
- ✅ Risks are concrete: R1–R6 each name a specific failure mode + specific mitigation.

<!-- @hm:user:extra-quality-checks -->
<!-- Project-specific quality bar items. Preserved across harness-maker upgrades. -->
<!-- @hm:/user:extra-quality-checks -->

---

## Cross-references

- Refresh proposal: `.claude/observability/refresh/proposed-2026-05-08.md` (P1–P7)
- Prior cursor work: `work-docs/plans/PLAN-cursor-target-impl.md`, `PLAN-cursor-target-support.md`, `PLAN-cursor-rootcause.md`
- Manual checklist scaffold (to be created in Phase 0): `tests/cursor-compat/MANUAL_CHECKLIST.md`
- CLAUDE.md sections: §Targets 정책, §보안/권한, §버전업 정책, §무언가를 고치거나 개선하기 전에 (체크리스트 #2 외부 소비자 파서 정합성, #5 fingerprint 기반 분기, #8 Integration 경계 한 줄 테스트)

<!-- @hm:user:extensions -->
<!-- Free-form project-specific additions to the plan. Preserved across harness-maker upgrades. -->
<!-- @hm:/user:extensions -->
